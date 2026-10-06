from pathlib import Path

import pytest

from app.ingestion import chunk
from app.ingestion.chunk import MAX_CHARS, check_chunks, chunk_all, chunk_article, load_processed
from app.schemas.law import LawChunk, ParsedArticle, ParsedLaw

PROCESSED = Path(__file__).parents[2] / "data" / "processed"


def make_law(*articles: ParsedArticle) -> ParsedLaw:
    return ParsedLaw(
        pcode="T0000001",
        law_name="測試法",
        law_short_name="測試",
        law_level="法律",
        amended_date="20260101",
        source_update_date="x",
        data_version="2026-10-05",
        articles=list(articles),
    )


def make_article(
    no: str, paragraphs: list[str], chapter: str | None = "第 一 章 總則"
) -> ParsedArticle:
    return ParsedArticle(
        article_no=no, chapter=chapter, text="\n".join(paragraphs), paragraphs=paragraphs
    )


def chunks_of(article: ParsedArticle) -> list[LawChunk]:
    return chunk_article(make_law(article), article)


def test_short_article_is_one_chunk() -> None:
    (c,) = chunks_of(make_article("53", ["甲" * 30, "乙" * 30]))
    assert c.chunk_id == "T0000001:53"
    assert c.paragraph_no is None
    assert c.article_id == "T0000001:53"
    assert c.text == "甲" * 30 + "\n" + "乙" * 30
    assert c.embed_text == "測試法 第 一 章 總則 第 53 條\n" + c.text
    assert c.source_url.endswith("pcode=T0000001&flno=53")


def test_exactly_max_chars_is_not_split() -> None:
    assert len(chunks_of(make_article("1", ["甲" * MAX_CHARS]))) == 1


def test_long_article_splits_between_paragraphs() -> None:
    paragraphs = ["甲" * 500, "乙" * 500, "丙" * 500]
    cs = chunks_of(make_article("35", paragraphs))
    assert [c.chunk_id for c in cs] == ["T0000001:35-p1", "T0000001:35-p2", "T0000001:35-p3"]
    assert [c.paragraph_no for c in cs] == [1, 2, 3]
    assert [c.text for c in cs] == paragraphs
    assert {c.article_id for c in cs} == {"T0000001:35"}  # 切分後仍連到所屬條文
    assert all(c.source_url.endswith("flno=35") for c in cs)


def test_paragraphs_are_packed_up_to_limit() -> None:
    paragraphs = ["甲" * 300, "乙" * 300, "丙" * 300, "丁" * 300]
    cs = chunks_of(make_article("2", paragraphs))
    assert [c.paragraph_no for c in cs] == [1, 3]
    assert all(len(c.text) <= MAX_CHARS for c in cs)


def test_oversized_paragraph_splits_at_sub_items() -> None:
    lines = ["本條定義如下："] + [f"{i}、" + "甲" * 300 for i in "一二三四五"]
    cs = chunks_of(make_article("39", ["\n".join(lines)]))
    assert len(cs) > 1
    assert all(len(c.text) <= MAX_CHARS for c in cs)
    assert {c.paragraph_no for c in cs} == {1}  # 全部來自第 1 項，id 靠序號仍不重複
    assert len({c.chunk_id for c in cs}) == len(cs)
    assert "\n".join(c.text for c in cs) == "\n".join(lines)


def test_short_tail_is_merged_into_previous_chunk() -> None:
    cs = chunks_of(make_article("9", ["甲" * 700, "乙" * 750, "丙" * 50]))
    assert [len(c.text) for c in cs] == [700, 750 + 1 + 50]


def test_missing_chapter_omitted_from_embed_text() -> None:
    (c,) = chunks_of(make_article("1", ["甲" * 10], chapter=None))
    assert c.embed_text.startswith("測試法 第 1 條\n")


def test_check_chunks_rejects_duplicates_and_empty() -> None:
    (c,) = chunks_of(make_article("1", ["甲"]))
    with pytest.raises(ValueError, match="重複"):
        check_chunks([c, c])
    with pytest.raises(ValueError, match="空白"):
        check_chunks([c.model_copy(update={"text": "  "})])


def test_chunking_is_deterministic() -> None:
    law = make_law(make_article("35", ["甲" * 500, "乙" * 500]), make_article("1", ["丙"]))
    assert chunk_all([law]) == chunk_all([law])


@pytest.mark.skipif(not any(PROCESSED.glob("*.json")), reason="data/processed 尚未產生")
def test_real_data_invariants() -> None:
    laws = load_processed(PROCESSED)
    chunks = chunk_all(laws)
    check_chunks(chunks)
    assert max(len(c.text) for c in chunks) <= MAX_CHARS + chunk.TAIL_SLACK
    for law in laws:
        for article in law.articles:
            parts = [c for c in chunks if c.article_id == f"{law.pcode}:{article.article_no}"]
            assert parts, f"{law.pcode}:{article.article_no} 沒有 chunk"
            # 沒有內容遺失或重複：串回去等於整條原文
            assert "\n".join(c.text for c in parts) == "\n".join(article.paragraphs)


def test_single_chunk_after_tail_merge_keeps_article_id() -> None:
    # 總長 > MAX_CHARS，但最後一項不到 MIN_TAIL_CHARS，併回去後只剩一塊
    (c,) = chunks_of(make_article("37", ["甲" * 790, "乙" * 50]))
    assert c.chunk_id == "T0000001:37"
    assert c.paragraph_no is None
