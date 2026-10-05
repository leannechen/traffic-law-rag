import zipfile
from pathlib import Path

import pytest

from app.ingestion import parse
from app.ingestion.parse import (
    iter_target_laws,
    normalize_law_name,
    split_paragraphs,
)
from app.ingestion.targets import Target, load_targets
from app.schemas.law import ParsedLaw

Laws = dict[str, tuple[ParsedLaw, int]]
FIXTURES = Path(__file__).parent / "fixtures"

TARGETS = {
    "K0040012": Target(pcode="K0040012", short_name="道交處罰條例", priority="must"),
    "K0040013": Target(pcode="K0040013", short_name="道安規則", priority="must"),
    "D0080090": Target(pcode="D0080090", short_name="事故處理辦法", priority="must"),
    # 舊版事故處理辦法，已廢止：就算被列為目標也要排除
    "K0040015": Target(pcode="K0040015", short_name="舊版", priority="must"),
}


def make_zip(tmp_path: Path, xml_name: str, zip_name: str) -> Path:
    path = tmp_path / zip_name
    with zipfile.ZipFile(path, "w") as zf:
        zf.write(FIXTURES / xml_name, arcname="data.xml")
        zf.writestr("manifest.csv", "ignored")
    return path


@pytest.fixture
def laws(tmp_path: Path) -> Laws:
    found = {}
    for xml, name in (("law.xml", "law.zip"), ("order.xml", "order.zip")):
        for law, deleted in iter_target_laws(make_zip(tmp_path, xml, name), TARGETS, "2026-10-05"):
            found[law.pcode] = (law, deleted)
    return found


def test_only_targets_and_not_abolished(laws: Laws) -> None:
    # 憲法（非目標）與 K0040015（廢止）都不在結果裡
    assert set(laws) == {"K0040012", "K0040013", "D0080090"}


def test_law_metadata(laws: Laws) -> None:
    law, _ = laws["K0040012"]
    assert law.law_name == "道路交通管理處罰條例"
    assert law.law_short_name == "道交處罰條例"
    assert law.law_level == "法律"
    assert law.data_version == "2026-10-05"
    assert laws["K0040013"][0].law_level == "命令"


def test_law_name_suffix_is_removed(laws: Laws) -> None:
    assert laws["D0080090"][0].law_name == "道路交通事故處理辦法"
    assert normalize_law_name("道路交通事故處理辦法（92.09.24  訂定）") == "道路交通事故處理辦法"
    assert normalize_law_name("道路交通安全規則") == "道路交通安全規則"


def test_article_numbers_and_deleted_articles(laws: Laws) -> None:
    law, deleted = laws["K0040012"]
    assert [a.article_no for a in law.articles] == ["1", "3", "35-1", "53"]
    assert deleted == 1  # 第 28 條為「（刪除）」


def test_chapter_is_tracked(laws: Laws) -> None:
    articles = {a.article_no: a for a in laws["K0040012"][0].articles}
    assert articles["3"].chapter == "第 一 章 總則"
    assert articles["53"].chapter == "第 二 章 汽車"


def test_paragraphs_split_by_line(laws: Laws) -> None:
    articles = {a.article_no: a for a in laws["K0040012"][0].articles}
    art53 = articles["53"]
    assert len(art53.paragraphs) == 2
    assert art53.paragraphs[1].startswith("前項紅燈右轉行為者")
    assert "六百元以上一千八百元以下罰鍰" in art53.paragraphs[1]
    assert len(articles["35-1"].paragraphs) == 4


def test_sub_items_stay_in_their_paragraph(laws: Laws) -> None:
    art3 = next(a for a in laws["K0040012"][0].articles if a.article_no == "3")
    assert len(art3.paragraphs) == 1
    assert "\n一、道路：" in art3.paragraphs[0]


def test_split_paragraphs_handles_sub_items_and_blank_lines() -> None:
    text = "本條定義如下：\n一、甲\n二、乙\n\n前項所稱甲，指…\n（一）子\n（二）丑"
    assert split_paragraphs(text) == [
        "本條定義如下：\n一、甲\n二、乙",
        "前項所稱甲，指…\n（一）子\n（二）丑",
    ]


def test_bad_article_number_raises(tmp_path: Path) -> None:
    xml = (FIXTURES / "law.xml").read_text(encoding="utf-8").replace("第 53 條", "第五十三條")
    bad = tmp_path / "bad.xml"
    bad.write_text(xml, encoding="utf-8")
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(bad, arcname="data.xml")
    with pytest.raises(parse.ParseError, match="條號"):
        list(iter_target_laws(zip_path, TARGETS, "2026-10-05"))


def test_parse_all_writes_only_targets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = tmp_path / "raw" / "2026-10-05"
    raw.mkdir(parents=True)
    make_zip(raw.parent, "law.xml", "law.zip").rename(raw / "law.zip")
    make_zip(raw.parent, "order.xml", "order.zip").rename(raw / "order.zip")
    monkeypatch.setattr(
        parse, "load_targets", lambda: [t for t in TARGETS.values() if t.pcode != "K0040015"]
    )
    out = tmp_path / "processed"
    out.mkdir()
    (out / "OLD.json").write_text("{}")  # 過期檔案要被清掉
    parse.parse_all(raw, out)
    assert sorted(p.name for p in out.glob("*.json")) == [
        "D0080090.json",
        "K0040012.json",
        "K0040013.json",
    ]


def test_missing_target_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = tmp_path / "2026-10-05"
    raw.mkdir()
    make_zip(tmp_path, "law.xml", "law.zip").rename(raw / "law.zip")
    make_zip(tmp_path, "order.xml", "order.zip").rename(raw / "order.zip")
    # K0040015 已廢止，所以列為目標時必須報錯而不是默默略過
    monkeypatch.setattr(parse, "load_targets", lambda: list(TARGETS.values()))
    with pytest.raises(parse.ParseError, match="K0040015"):
        parse.parse_all(raw, tmp_path / "processed")


def test_targets_yaml_is_valid() -> None:
    targets = load_targets()
    pcodes = [t.pcode for t in targets]
    assert len(pcodes) == len(set(pcodes))
    assert {"K0040012", "K0040013", "D0080090"} <= set(pcodes)
    assert "K0040015" not in pcodes  # 廢止的舊版
