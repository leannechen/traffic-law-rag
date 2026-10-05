"""把開放資料 ZIP 解析成目標法規的中介 JSON（data/processed/{pcode}.json）。

XML 以串流讀取：每讀完一部 <法規> 就判斷是否為目標，不是的立刻丟棄，
目標以外的法規內容不會寫入磁碟。
"""

import argparse
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Literal, cast
from xml.etree import ElementTree as ET

from app.core.config import get_settings
from app.ingestion.targets import Target, load_targets
from app.schemas.law import ParsedArticle, ParsedLaw

ARTICLE_NO_RE = re.compile(r"^\s*第\s*(\d+(?:-\d+)?)\s*條\s*$")
PCODE_RE = re.compile(r"pcode=(\w+)")
HEADING_RE = re.compile(r"^\s*第\s*\S+\s*([編章節款目])")
DELETED_RE = re.compile(r"^\s*[（(]\s*已?刪除\s*[）)]\s*$")
# 款：「一、」「（一）」開頭的行；沒有這些開頭的換行是新的一項
SUB_ITEM_RE = re.compile(r"^\s*(?:[一二三四五六七八九十]+、|[（(][一二三四五六七八九十]+[）)])")
NAME_SUFFIX_RE = re.compile(r"[（(][\d.\s]*訂定[）)]\s*$")
HEADING_LEVELS = "編章節款目"


class ParseError(Exception):
    pass


def normalize_law_name(name: str) -> str:
    """去掉資料中偶爾附在名稱後的「（92.09.24  訂定）」。"""
    return NAME_SUFFIX_RE.sub("", name.strip())


def split_paragraphs(text: str) -> list[str]:
    paragraphs: list[str] = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        if paragraphs and SUB_ITEM_RE.match(line):
            paragraphs[-1] += "\n" + line.strip()
        else:
            paragraphs.append(line.strip())
    return paragraphs


def _chapter_label(headings: dict[str, str]) -> str | None:
    labels = [headings[level] for level in HEADING_LEVELS if level in headings]
    return " ".join(labels) or None


def parse_articles(law: ET.Element) -> tuple[list[ParsedArticle], int]:
    """回傳 (有效條文, 被排除的刪除條文數)。"""
    articles: list[ParsedArticle] = []
    deleted = 0
    headings: dict[str, str] = {}
    for node in law.findall("法規內容/*"):
        if node.tag == "編章節":
            label = (node.text or "").strip()
            m = HEADING_RE.match(label)
            if m:
                level = m.group(1)
                # 設定某一層會清掉比它更深的層
                for deeper in HEADING_LEVELS[HEADING_LEVELS.index(level) :]:
                    headings.pop(deeper, None)
                headings[level] = label
        elif node.tag == "條文":
            no_text = node.findtext("條號") or ""
            m = ARTICLE_NO_RE.match(no_text)
            if not m:
                raise ParseError(f"無法解析條號：{no_text!r}")
            text = (node.findtext("條文內容") or "").strip()
            if not text or DELETED_RE.match(text):
                deleted += 1
                continue
            articles.append(
                ParsedArticle(
                    article_no=m.group(1),
                    chapter=_chapter_label(headings),
                    text=text,
                    paragraphs=split_paragraphs(text),
                )
            )
        else:
            raise ParseError(f"未預期的節點：{node.tag}")
    return articles, deleted


def iter_target_laws(
    zip_path: Path, targets: dict[str, Target], data_version: str
) -> Iterator[tuple[ParsedLaw, int]]:
    """串流讀 ZIP 內的 XML，只產出目標且未廢止的法規（附刪除條文數）。"""
    with zipfile.ZipFile(zip_path) as zf:
        member = next(n for n in zf.namelist() if n.lower().endswith(".xml"))
        with zf.open(member) as fh:
            update_date = ""
            for event, elem in ET.iterparse(fh, events=("start", "end")):
                if event == "start":
                    if elem.tag == "LAWS":
                        update_date = elem.get("UpdateDate", "")
                    continue
                if elem.tag != "法規":
                    continue
                m = PCODE_RE.search(elem.findtext("法規網址") or "")
                target = targets.get(m.group(1)) if m else None
                abolished = bool((elem.findtext("廢止註記") or "").strip())
                if m and target and not abolished:
                    articles, deleted = parse_articles(elem)
                    level = (elem.findtext("法規性質") or "").strip()
                    if level not in ("法律", "命令"):
                        raise ParseError(f"{m.group(1)} 法規性質異常：{level!r}")
                    yield (
                        ParsedLaw(
                            pcode=m.group(1),
                            law_name=normalize_law_name(elem.findtext("法規名稱") or ""),
                            law_short_name=target.short_name,
                            law_level=cast(Literal["法律", "命令"], level),
                            amended_date=(elem.findtext("最新異動日期") or "").strip(),
                            source_update_date=update_date,
                            data_version=data_version,
                            articles=articles,
                        ),
                        deleted,
                    )
                elem.clear()  # 丟掉這部法規，避免整份 XML 堆在記憶體


def latest_raw_dir(raw_root: Path) -> Path:
    dirs = sorted(p for p in raw_root.glob("????-??-??") if p.is_dir())
    if not dirs:
        raise ParseError(f"{raw_root} 底下沒有資料，先執行 python -m app.ingestion.fetch")
    return dirs[-1]


def parse_all(raw_dir: Path, out_dir: Path) -> list[tuple[ParsedLaw, int]]:
    targets = {t.pcode: t for t in load_targets()}
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[tuple[ParsedLaw, int]] = []
    for name in ("law.zip", "order.zip"):
        results.extend(iter_target_laws(raw_dir / name, targets, raw_dir.name))
    missing = set(targets) - {law.pcode for law, _ in results}
    if missing:
        raise ParseError(f"找不到目標法規（可能已廢止或 pcode 錯誤）：{sorted(missing)}")
    for stale in out_dir.glob("*.json"):  # processed 只留目標法規
        stale.unlink()
    for law, _ in results:
        (out_dir / f"{law.pcode}.json").write_text(law.model_dump_json(indent=2), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="data/raw/ 底下的日期資料夾，預設最新")
    args = parser.parse_args()
    data_dir = get_settings().data_dir
    raw_dir = data_dir / "raw" / args.date if args.date else latest_raw_dir(data_dir / "raw")
    results = parse_all(raw_dir, data_dir / "processed")
    print(f"data_version = {raw_dir.name}")
    print(f"{'pcode':10} {'法規':28} {'性質':4} {'異動日':9} {'有效條文':>6} {'刪除':>4}")
    for law, deleted in results:
        print(
            f"{law.pcode:10} {law.law_name[:26]:28} {law.law_level:4} {law.amended_date:9} "
            f"{len(law.articles):>8} {deleted:>4}"
        )


if __name__ == "__main__":
    main()
