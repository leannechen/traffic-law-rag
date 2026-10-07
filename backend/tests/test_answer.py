from app.pipeline.answer import answer_question, retrieve_multi
from tests.fakes import FakeArticles, FakeLLM, FakeSearcher, chunk

ART53 = chunk("K:53", "處新臺幣六百元以上一千八百元以下罰鍰。", 0.72)
ART58 = chunk("K:58", "處新臺幣六百元以上一千二百元以下罰鍰。", 0.60)


def searcher(score: float = 0.72) -> FakeSearcher:
    return FakeSearcher({"紅燈右轉？": [ART53.model_copy(update={"vector_score": score}), ART58]})


def test_gate_refuses_without_calling_the_model() -> None:
    llm = FakeLLM("不該被呼叫")
    result = answer_question(
        "紅燈右轉？", searcher=searcher(0.30), articles=FakeArticles(), llm=llm, threshold=0.40
    )
    assert result.refused and result.refusal_layer == "gate"
    assert llm.calls == []
    assert result.gate_top_score == 0.30 and result.gate_threshold == 0.40


def test_no_retrieval_results_is_refused_by_gate() -> None:
    result = answer_question(
        "沒結果",
        searcher=FakeSearcher({}),
        articles=FakeArticles(),
        llm=FakeLLM("x"),
        threshold=0.40,
    )
    assert result.refused and result.refusal_layer == "gate" and result.gate_top_score is None


def test_model_can_refuse_after_passing_the_gate() -> None:
    llm = FakeLLM("[[REFUSE]]")
    result = answer_question(
        "紅燈右轉？", searcher=searcher(), articles=FakeArticles(), llm=llm, threshold=0.40
    )
    assert result.refused and result.refusal_layer == "model"
    assert result.answer == ""


def test_valid_answer_with_matching_numbers() -> None:
    llm = FakeLLM("紅燈右轉罰六百元以上一千八百元以下[[K:53]]。")
    result = answer_question(
        "紅燈右轉？", searcher=searcher(), articles=FakeArticles(), llm=llm, threshold=0.40
    )
    assert not result.refused
    assert result.citations_valid == ["K:53"] and result.citations_invalid == []
    assert (result.numbers_matched, result.numbers_total) == (2, 2)
    assert result.input_tokens == 10 and result.output_tokens == 5


def test_invented_citation_is_caught_as_invalid() -> None:
    """spec 驗收：故意製造無效引用，必須被標成 invalid。"""
    llm = FakeLLM("罰六百元[[K:53]]，另依[[K:999]]規定。")
    result = answer_question(
        "紅燈右轉？", searcher=searcher(), articles=FakeArticles(), llm=llm, threshold=0.40
    )
    assert result.citations_valid == ["K:53"]
    assert result.citations_invalid == ["K:999"]


def test_citing_a_retrieved_but_not_provided_chunk_is_invalid() -> None:
    # 只有前 5 條會給模型看；第 6 名以後即使被檢索到也不能引用
    hits = [chunk(f"K:{i}", "條文", 0.9 - i / 100) for i in range(1, 8)]
    fake = FakeSearcher({"問題": hits})
    llm = FakeLLM("引用了沒給的條文[[K:7]]")
    result = answer_question(
        "問題", searcher=fake, articles=FakeArticles(), llm=llm, threshold=0.40
    )
    assert result.citations_invalid == ["K:7"]
    assert "K:7" not in llm.calls[0]["user"].split("<問題>")[0]


def test_wrong_number_is_reported() -> None:
    llm = FakeLLM("罰六百元到二千元[[K:53]]。")
    result = answer_question(
        "紅燈右轉？", searcher=searcher(), articles=FakeArticles(), llm=llm, threshold=0.40
    )
    assert result.numbers_unmatched == ["2000元"]


def test_numbers_are_checked_against_cited_chunks_only() -> None:
    # 「一千二百元」在第 58 條，但答案只引用第 53 條 → 對不上
    llm = FakeLLM("罰一千二百元[[K:53]]。")
    result = answer_question(
        "紅燈右轉？", searcher=searcher(), articles=FakeArticles(), llm=llm, threshold=0.40
    )
    assert result.numbers_unmatched == ["1200元"]


def test_answer_without_citations_has_all_numbers_unmatched() -> None:
    llm = FakeLLM("罰六百元。")
    result = answer_question(
        "紅燈右轉？", searcher=searcher(), articles=FakeArticles(), llm=llm, threshold=0.40
    )
    assert result.citations_valid == [] and result.numbers_unmatched == ["600元"]


def test_rewrite_adds_queries_and_gate_uses_original_question_score() -> None:
    legal = [chunk("K:77", "改寫後才找到", 0.95)]  # 改寫查詢分數很高
    fake = FakeSearcher(
        {
            "原問題": [chunk("K:1", "原本的結果", 0.30)],  # 原始問題分數低於門檻
            "法律用語": legal,
        }
    )

    def respond(system: str, user: str) -> str:
        return '{"queries": ["法律用語"]}' if "檢索助理" in system else "[[K:77]]"

    llm = FakeLLM(respond)
    result = answer_question(
        "原問題", searcher=fake, articles=FakeArticles(), llm=llm, threshold=0.40, rewrite=True
    )
    assert result.queries == ["原問題", "法律用語"]
    assert {h.article_id for h in result.retrieved} == {"K:1", "K:77"}
    # 改寫把範圍外問題的分數拉高，但門檻看原始問題，所以仍被擋下
    assert result.refused and result.refusal_layer == "gate"
    assert result.gate_top_score == 0.30


def test_retrieve_multi_fuses_and_keeps_best_vector_score() -> None:
    fake = FakeSearcher(
        {
            "q1": [chunk("A:1", "a", 0.6), chunk("A:2", "b", 0.5)],
            "q2": [chunk("A:2", "b", 0.8), chunk("A:3", "c", 0.4)],
        }
    )
    hits = retrieve_multi(fake, ["q1", "q2"], depth=10)
    ids = [h.article_id for h in hits]
    assert ids[0] == "A:2"  # 兩個查詢都找到它，RRF 排第一
    assert set(ids) == {"A:1", "A:2", "A:3"}
    assert next(h for h in hits if h.article_id == "A:2").vector_score == 0.8
    assert [h.rank for h in hits] == [1, 2, 3]


def test_retrieve_multi_single_query_passes_through() -> None:
    fake = FakeSearcher({"q": [chunk("A:1", "a", 0.6)]})
    assert [h.article_id for h in retrieve_multi(fake, ["q"])] == ["A:1"]


def test_model_gets_the_whole_article_not_just_the_retrieved_chunk() -> None:
    # 第 35 條被切成兩塊，檢索到的是後半塊（K:35-p2）；模型應看到整條原文
    hits = [chunk("K:35-p2", "後半：累犯加重。", 0.7)]
    articles = FakeArticles({"K:35": "前半：罰六萬元。\n後半：累犯加重。"})
    llm = FakeLLM("罰六萬元[[K:35]]。")
    result = answer_question(
        "酒駕？", searcher=FakeSearcher({"酒駕？": hits}), articles=articles, llm=llm, threshold=0.4
    )
    prompt = llm.calls[0]["user"]
    assert 'id="K:35"' in prompt and "前半：罰六萬元。" in prompt and "後半：累犯加重。" in prompt
    assert result.citations_valid == ["K:35"] and result.numbers_unmatched == []


def test_falls_back_to_the_retrieved_chunk_when_article_text_is_missing() -> None:
    llm = FakeLLM("[[K:1]]")
    fake = FakeSearcher({"問題": [chunk("K:1", "只有這一塊", 0.7)]})
    answer_question("問題", searcher=fake, articles=FakeArticles(), llm=llm, threshold=0.4)
    assert "只有這一塊" in llm.calls[0]["user"]
