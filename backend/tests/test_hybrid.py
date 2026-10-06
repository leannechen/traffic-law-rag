from pathlib import Path

import chromadb
import pytest

from app.core.embedder import InputType
from app.pipeline.bm25 import BM25Index, tokenize
from app.pipeline.retrieve import HybridRetriever, Retriever, rrf


def test_rrf_uses_ranks_not_scores() -> None:
    fused = dict(rrf([["A", "B", "C"], ["C", "B", "D"]], k=60))
    assert fused["B"] == pytest.approx(1 / 62 + 1 / 62)
    assert fused["A"] == pytest.approx(1 / 61)
    assert fused["C"] == pytest.approx(1 / 63 + 1 / 61)
    assert fused["D"] == pytest.approx(1 / 63)


def test_rrf_rewards_agreement_over_a_single_first_place() -> None:
    order = [key for key, _ in rrf([["A", "B"], ["C", "B"]])]
    assert order[0] == "B"  # 兩份榜單都有 B，勝過只在其中一份拿第一的 A、C


def test_rrf_is_deterministic_on_ties() -> None:
    assert rrf([["B"], ["A"]]) == rrf([["B"], ["A"]])
    assert [k for k, _ in rrf([["B"], ["A"]])] == ["A", "B"]  # 同分以 key 排序


def test_tokenize_bigram() -> None:
    assert tokenize("紅燈右轉", "bigram") == ["紅燈", "燈右", "右轉"]
    assert tokenize("甲，乙丙", "bigram") == ["甲", "乙丙"]  # 標點切開，單字保留
    assert tokenize("", "bigram") == []


def test_tokenize_jieba_drops_punctuation() -> None:
    tokens = tokenize("安全帽，機車。", "jieba")
    assert "，" not in tokens and "。" not in tokens
    assert "安全帽" in tokens and "機車" in tokens


def test_jieba_default_dictionary_splits_legal_terms() -> None:
    """已知限制：預設詞典不認得「罰鍰」，會切成「罰」「鍰」（見 ADR 0004）。
    這個測試記錄現況；若詞典更新後行為改變，測試失敗提醒重新評估。"""
    assert "罰鍰" not in tokenize("處罰鍰", "jieba")


@pytest.mark.parametrize("method", ["jieba", "bigram"])
def test_bm25_ranks_matching_document_first(method: str) -> None:
    docs = ["汽車駕駛人闖紅燈者處罰鍰", "機車駕駛人未戴安全帽處罰鍰", "行人穿越道之定義"]
    index = BM25Index(docs, method)  # type: ignore[arg-type]
    assert index.search("安全帽", 3)[0][0] == 1
    assert index.search("完全無關的火星文字", 3) == []  # 沒有任何詞命中就不回傳


def test_bigram_matches_where_jieba_segmentation_disagrees() -> None:
    docs = ["汽車駕駛人闖紅燈者處罰鍰", "行人穿越道之定義"]
    # jieba 把文件裡的「闖紅燈者」切成「闖紅／燈者」，查詢的「闖紅燈」卻是一個詞，對不上
    assert BM25Index(docs, "jieba").search("闖紅燈", 2) == []
    assert BM25Index(docs, "bigram").search("闖紅燈", 2)[0][0] == 0


def test_bm25_rarer_terms_weigh_more() -> None:
    docs = ["罰鍰 罰鍰 罰鍰 一般", "罰鍰 酒駕 特別", "罰鍰 其他"]
    index = BM25Index(docs, "bigram")
    ranked = [i for i, _ in index.search("罰鍰酒駕", 3)]
    assert ranked[0] == 1  # 稀有詞「酒駕」比到處都有的「罰鍰」更有鑑別力


class AxisEmbedder:
    model = "axis-1"

    def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]:
        return [[1.0 + t.count("甲") * 3, 1.0 + t.count("乙") * 3] for t in texts]


def test_hybrid_combines_vector_and_keyword_hits(tmp_path: Path) -> None:
    rows = [
        # (chunk_id, article_no, text)：向量只看甲／乙；BM25 看詞
        ("T:1", "1", "甲甲甲 一般規定"),
        ("T:2", "2", "乙乙乙 酒駕處罰"),  # 向量不像「甲」，但關鍵字「酒駕」命中
        ("T:3", "3", "乙乙 其他事項"),
    ]
    embedder = AxisEmbedder()
    collection = chromadb.PersistentClient(path=str(tmp_path / "idx")).create_collection(
        "test_chunks", metadata={"hnsw:space": "cosine"}
    )
    collection.add(
        ids=[r[0] for r in rows],
        embeddings=embedder.embed([r[2] for r in rows], "document"),  # type: ignore[arg-type]
        documents=[r[2] for r in rows],
        metadatas=[{"pcode": "T", "article_no": r[1], "law_short_name": "測"} for r in rows],
    )
    hybrid = HybridRetriever(Retriever(collection, embedder), collection, "bigram")
    hits = hybrid.search("甲甲 酒駕", k=3)
    ids = [h.article_id for h in hits]
    assert set(ids) == {"T:1", "T:2", "T:3"}
    assert ids.index("T:2") < ids.index("T:3")  # 關鍵字命中的 T:2 勝過兩邊都沒特別的 T:3
    assert all(h.vector_score is not None for h in hits)  # 保留餘弦分數供拒答門檻
    assert [h.rank for h in hits] == [1, 2, 3]
