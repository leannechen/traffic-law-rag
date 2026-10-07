from app.pipeline.articles import ArticleText
from app.pipeline.gate import check_gate
from app.pipeline.generate import (
    REFUSAL_MARKER,
    build_user_prompt,
    generate_answer,
    load_prompt,
    parse_answer,
)
from app.pipeline.rewrite import rewrite_question
from tests.fakes import FakeLLM


def test_parse_answer_extracts_unique_citations_in_order() -> None:
    parsed = parse_answer("罰六百元[[A:1]]，另依規定[[B:2]][[A:1]]。")
    assert parsed.citations == ["A:1", "B:2"]
    assert not parsed.refused
    assert "[[A:1]]" in parsed.text


def test_parse_answer_detects_refusal_marker() -> None:
    parsed = parse_answer("[[REFUSE]]")
    assert parsed.refused and parsed.text == "" and parsed.citations == []


def test_refusal_marker_is_not_counted_as_a_citation() -> None:
    parsed = parse_answer("條文沒有規定。[[REFUSE]]")
    assert parsed.refused and parsed.citations == []


def test_parse_answer_without_citations() -> None:
    parsed = parse_answer("沒有任何標記的答案")
    assert parsed.citations == [] and not parsed.refused


def test_parse_answer_ignores_malformed_markers() -> None:
    parsed = parse_answer("壞掉的 [[A:1] 與 [A:2]] 與 [[]]")
    assert parsed.citations == []


def art(article_id: str, text: str) -> ArticleText:
    return ArticleText(article_id=article_id, law_short_name="測", article_no="1", text=text)


def test_prompt_lists_every_article_with_its_id() -> None:
    prompt = build_user_prompt("問題？", [art("K:53", "原文一"), art("K:35", "原文二")])
    assert 'id="K:53"' in prompt and 'id="K:35"' in prompt
    assert "原文一" in prompt and "原文二" in prompt
    assert prompt.rstrip().endswith("問題？\n</問題>")


def test_system_prompt_states_the_key_rules() -> None:
    system = load_prompt("generate.md")
    assert REFUSAL_MARKER in system
    assert "[[id]]" in system
    assert "一字不改" in system


def test_generate_answer_parses_model_output() -> None:
    llm = FakeLLM("紅燈右轉罰六百元以上一千八百元以下[[K:53]]。")
    result = generate_answer(llm, "紅燈右轉？", [art("K:53", "…")])
    assert result.answer.citations == ["K:53"]
    assert llm.calls[0]["effort"] == "medium"


def test_safety_refusal_is_treated_as_refusal_not_an_answer() -> None:
    llm = FakeLLM("some partial text", refused=True)
    result = generate_answer(llm, "問題", [art("K:1", "x")])
    assert result.answer.refused and result.answer.text == ""


def test_rewrite_keeps_original_first_and_adds_rewrites() -> None:
    llm = FakeLLM('{"queries": ["闖紅燈 右轉 罰鍰", "紅燈右轉 處罰"]}')
    queries, tin, tout = rewrite_question(llm, "紅燈右轉會被罰多少錢？")
    assert queries == ["紅燈右轉會被罰多少錢？", "闖紅燈 右轉 罰鍰", "紅燈右轉 處罰"]
    assert (tin, tout) == (10, 5)
    assert llm.calls[0]["json_schema"] is not None and llm.calls[0]["effort"] == "low"


def test_rewrite_dedupes_and_caps_at_three() -> None:
    llm = FakeLLM('{"queries": ["原問題", "a", "a", "b", "c", "d"]}')
    queries, _, _ = rewrite_question(llm, "原問題")
    assert queries == ["原問題", "a", "b", "c"]  # 原始問題 + 最多 3 個改寫


def test_rewrite_falls_back_to_original_on_bad_output() -> None:
    for bad in ["not json", '{"queries": "oops"}', '{"other": 1}', "[]"]:
        queries, _, _ = rewrite_question(FakeLLM(bad), "原問題")
        assert queries == ["原問題"], bad


def test_rewrite_falls_back_when_model_refuses() -> None:
    queries, _, _ = rewrite_question(FakeLLM('{"queries": ["x"]}', refused=True), "原問題")
    assert queries == ["原問題"]


def test_gate() -> None:
    assert check_gate(0.41, 0.40).passed
    assert check_gate(0.40, 0.40).passed  # 等於門檻算通過
    assert not check_gate(0.39, 0.40).passed
    assert not check_gate(None, 0.40).passed  # 沒有檢索結果
