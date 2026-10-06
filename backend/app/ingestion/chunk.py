"""把解析後的條文切成 LawChunk。純函式，不碰網路與磁碟（除 load_processed）。

規則（ADR 0003）：
1. 條文 <= MAX_CHARS：整條一個 chunk（切完只剩一塊時亦同，chunk_id 即 article_id）。
2. 超過：依序把「項」累加到上限，不在項中間切。
3. 單一項本身超過上限：退一步在「款」（一、二、三…）的邊界切。
4. 切完最後一塊不到 MIN_TAIL_CHARS 字，併入前一塊（因此最長 MAX_CHARS + TAIL_SLACK）。
"""

import json
from pathlib import Path

from app.schemas.law import LawChunk, ParsedArticle, ParsedLaw

MAX_CHARS = 800
MIN_TAIL_CHARS = 100
TAIL_SLACK = MIN_TAIL_CHARS  # 併入短尾巴後的長度上限 = MAX_CHARS + TAIL_SLACK

SOURCE_URL = "https://law.moj.gov.tw/LawClass/LawSingle.aspx?pcode={pcode}&flno={article_no}"


def _units(article: ParsedArticle) -> list[tuple[int, str]]:
    """切分單位 (所屬項號, 文字)。單一項過長時改用該項的各行（款）。"""
    units: list[tuple[int, str]] = []
    for no, paragraph in enumerate(article.paragraphs, start=1):
        if len(paragraph) > MAX_CHARS:
            units.extend((no, line) for line in paragraph.split("\n"))
        else:
            units.append((no, paragraph))
    return units


def _pack(units: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    groups: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    size = 0
    for unit in units:
        added = len(unit[1]) + (1 if current else 0)
        if current and size + added > MAX_CHARS:
            groups.append(current)
            current, size = [], 0
            added = len(unit[1])
        current.append(unit)
        size += added
    if current:
        groups.append(current)
    return groups


def _join(group: list[tuple[int, str]]) -> str:
    return "\n".join(text for _, text in group)


def _merge_short_tail(groups: list[list[tuple[int, str]]]) -> list[list[tuple[int, str]]]:
    # 前一塊 <= MAX_CHARS、尾巴 < MIN_TAIL_CHARS，合併後必定 <= MAX_CHARS + TAIL_SLACK
    if len(groups) >= 2 and len(_join(groups[-1])) < MIN_TAIL_CHARS:
        return [*groups[:-2], groups[-2] + groups[-1]]
    return groups


def chunk_article(law: ParsedLaw, article: ParsedArticle) -> list[LawChunk]:
    article_id = f"{law.pcode}:{article.article_no}"
    header = " ".join(
        part for part in (law.law_name, article.chapter, f"第 {article.article_no} 條") if part
    )
    base = {
        "pcode": law.pcode,
        "law_name": law.law_name,
        "law_short_name": law.law_short_name,
        "law_level": law.law_level,
        "article_no": article.article_no,
        "chapter": article.chapter,
        "source_url": SOURCE_URL.format(pcode=law.pcode, article_no=article.article_no),
        "amended_date": law.amended_date,
        "data_version": law.data_version,
    }
    groups = [] if len(article.text) <= MAX_CHARS else _merge_short_tail(_pack(_units(article)))
    if len(groups) <= 1:  # 整條一個 chunk（含「超過上限但併完尾巴只剩一塊」）
        return [
            LawChunk(
                chunk_id=article_id,
                paragraph_no=None,
                text=article.text,
                embed_text=f"{header}\n{article.text}",
                **base,
            )
        ]
    chunks = []
    for seq, group in enumerate(groups, start=1):
        text = _join(group)
        chunks.append(
            LawChunk(
                chunk_id=f"{article_id}-p{seq}",
                paragraph_no=group[0][0],
                text=text,
                embed_text=f"{header}\n{text}",
                **base,
            )
        )
    return chunks


def chunk_law(law: ParsedLaw) -> list[LawChunk]:
    return [c for article in law.articles for c in chunk_article(law, article)]


def load_processed(processed_dir: Path) -> list[ParsedLaw]:
    return [
        ParsedLaw.model_validate(json.loads(p.read_text(encoding="utf-8")))
        for p in sorted(processed_dir.glob("*.json"))
    ]


def chunk_all(laws: list[ParsedLaw]) -> list[LawChunk]:
    return [c for law in laws for c in chunk_law(law)]


def check_chunks(chunks: list[LawChunk]) -> None:
    """無空白、無重複 id。"""
    ids = [c.chunk_id for c in chunks]
    if len(ids) != len(set(ids)):
        dup = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"chunk_id 重複：{dup[:5]}")
    empty = [c.chunk_id for c in chunks if not c.text.strip()]
    if empty:
        raise ValueError(f"空白 chunk：{empty[:5]}")
