from pathlib import Path

import pytest

from app.ingestion.chunk import load_processed
from eval.dataset import load_dataset

PROCESSED = Path(__file__).parents[2] / "data" / "processed"
CATEGORIES = {"fine_amount", "definition", "accident", "cross_law", "colloquial", "out_of_scope"}


def test_dataset_shape() -> None:
    questions = load_dataset()
    assert 25 <= len(questions) <= 50
    ids = [q.id for q in questions]
    assert len(ids) == len(set(ids))
    assert {q.category for q in questions} == CATEGORIES
    refusals = [q for q in questions if q.should_refuse]
    assert len(refusals) >= 4
    assert all(q.category == "out_of_scope" for q in refusals)
    for q in questions:
        if q.should_refuse:
            assert not q.expected_chunk_ids and not q.expected_facts
        else:
            assert q.expected_chunk_ids and q.expected_facts
            assert len(q.expected_chunk_ids) == len(set(q.expected_chunk_ids))


@pytest.mark.skipif(not any(PROCESSED.glob("*.json")), reason="data/processed 尚未產生")
def test_expected_articles_exist_in_data() -> None:
    laws = load_processed(PROCESSED)
    known = {f"{law.pcode}:{a.article_no}" for law in laws for a in law.articles}
    for q in load_dataset():
        for article_id in q.expected_chunk_ids:
            assert article_id in known, f"{q.id}: {article_id} 不存在（或是刪除條文）"
