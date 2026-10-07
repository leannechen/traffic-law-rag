from app.pipeline.answer import AnswerResult
from eval.dataset import EvalQuestion
from eval.gen_eval import article_of, evaluate_generation
from tests.fakes import chunk


def q(
    qid: str,
    expected: list[str],
    facts: list[str] | None = None,
    *,
    refuse: bool = False,
    category: str = "fine_amount",
) -> EvalQuestion:
    return EvalQuestion(
        id=qid,
        question=f"問題{qid}",
        category=category,
        expected_chunk_ids=expected,
        expected_facts=[] if refuse else (facts or ["x"]),
        should_refuse=refuse,
        verified=True,
    )


def result(question: str, retrieved: list[str], **kw: object) -> AnswerResult:
    base: dict[str, object] = dict(
        question=question, queries=[question],
        retrieved=[chunk(f"{a}", "t", 0.7, rank=i) for i, a in enumerate(retrieved, 1)],
        gate_passed=True, gate_top_score=0.7, gate_threshold=0.4, refused=False,
        input_tokens=100, output_tokens=10,
    )  # fmt: skip
    return AnswerResult(**{**base, **kw})


def run(questions: list[EvalQuestion], results: dict[str, AnswerResult]) -> dict:  # type: ignore[type-arg]
    return evaluate_generation(questions, lambda text: results[text])


def test_article_of_strips_chunk_suffix() -> None:
    assert article_of("K0040012:35-p2") == "K0040012:35"
    assert article_of("K0040012:53-1") == "K0040012:53-1"  # 「條之一」不是切塊


def test_citation_accuracy_counts_hit_on_any_expected_article() -> None:
    out = run(
        [q("a", ["K:1"]), q("b", ["K:2"]), q("c", ["K:3"])],
        {
            "問題a": result("問題a", ["K:1"], answer="x", citations_valid=["K:1"]),
            "問題b": result("問題b", ["K:2"], answer="x", citations_valid=["K:9"]),  # 引用了別條
            "問題c": result("問題c", ["K:3"], refused=True, refusal_layer="model"),  # 被誤拒
        },
    )
    m = out["metrics"]
    assert m["citation_accuracy"] == round(1 / 3, 4)  # 誤拒也算錯
    assert m["citation_accuracy_answered"] == 0.5  # 只看有作答的兩題
    assert m["false_refusals"] == "1/3" and m["false_refusals_by_layer"] == {"model": 1}


def test_citation_of_split_chunk_matches_its_article() -> None:
    out = run(
        [q("a", ["K:35"])],
        {"問題a": result("問題a", ["K:35"], answer="x", citations_valid=["K:35-p2"])},
    )
    assert out["metrics"]["citation_accuracy"] == 1.0


def test_invalid_citations_are_counted() -> None:
    out = run(
        [q("a", ["K:1"])],
        {"問題a": result("問題a", ["K:1"], answer="x", citations_valid=["K:1"],
                         citations_invalid=["K:99", "K:98"])},
    )  # fmt: skip
    assert out["metrics"]["invalid_citations"] == 2
    assert out["metrics"]["answers_with_invalid_citation"] == 1


def test_number_accuracy_is_micro_averaged_over_answered_questions() -> None:
    out = run(
        [q("a", ["K:1"]), q("b", ["K:2"]), q("c", ["K:3"])],
        {
            "問題a": result("問題a", ["K:1"], answer="x", numbers_total=2, numbers_matched=2),
            "問題b": result("問題b", ["K:2"], answer="x", numbers_total=2, numbers_matched=1,
                            numbers_unmatched=["9元"]),
            "問題c": result("問題c", ["K:3"], refused=True, refusal_layer="gate"),  # 不計入
        },
    )  # fmt: skip
    assert out["metrics"]["number_accuracy"] == 0.75
    assert out["metrics"]["answers_all_numbers_ok"] == 0.5


def test_fact_amount_coverage_uses_expected_facts() -> None:
    facts = ["處新臺幣六百元以上一千八百元以下罰鍰"]
    out = run(
        [q("a", ["K:1"], facts)],
        {
            "問題a": result(
                "問題a", ["K:1"], answer="罰六百元到一千八百元[[K:1]]", citations_valid=["K:1"]
            )
        },
    )
    assert out["metrics"]["fact_amount_coverage"] == 1.0
    out = run(
        [q("a", ["K:1"], facts)],
        {"問題a": result("問題a", ["K:1"], answer="罰六百元[[K:1]]", citations_valid=["K:1"])},
    )
    assert out["metrics"]["fact_amount_coverage"] == 0.5


def test_refusal_accuracy_and_layers() -> None:
    questions = [
        q("a", ["K:1"]),
        q("b", ["K:2"]),
        q("o1", [], refuse=True, category="out_of_scope"),
        q("o2", [], refuse=True, category="out_of_scope"),
        q("o3", [], refuse=True, category="out_of_scope"),
    ]
    results = {
        "問題a": result("問題a", ["K:1"], answer="x", citations_valid=["K:1"]),  # 正確作答
        "問題b": result("問題b", ["K:2"], refused=True, refusal_layer="model"),  # 誤拒
        "問題o1": result("問題o1", [], refused=True, refusal_layer="gate"),  # 正確拒答
        "問題o2": result("問題o2", ["K:7"], refused=True, refusal_layer="model"),  # 正確拒答
        "問題o3": result("問題o3", ["K:7"], answer="亂答"),  # 該拒答卻作答
    }
    m = run(questions, results)["metrics"]
    assert m["refusal_accuracy"] == 0.6  # 5 題中對 3 題
    assert m["out_of_scope_refused"] == "2/3"
    assert m["out_of_scope_refused_by_layer"] == {"gate": 1, "model": 1}


def test_recall_and_mrr_use_the_final_retrieved_list() -> None:
    out = run(
        [q("a", ["K:2"])],
        {"問題a": result("問題a", ["K:1", "K:2"], answer="x", citations_valid=["K:2"])},
    )
    assert out["metrics"]["recall_at_5"] == 1.0 and out["metrics"]["mrr"] == 0.5


def test_unverified_questions_are_skipped() -> None:
    unverified = q("a", ["K:1"]).model_copy(update={"verified": False})
    out = run([unverified], {})
    assert out["counts"]["verified"] == 0


def test_citation_precision_counts_extra_citations() -> None:
    out = run(
        [q("a", ["K:1"]), q("b", ["K:2"])],
        {
            "問題a": result(
                "問題a", ["K:1"], answer="x", citations_valid=["K:1", "K:9"]
            ),  # 多引用一條
            "問題b": result("問題b", ["K:2"], answer="x", citations_valid=["K:2"]),
        },
    )
    assert out["metrics"]["citation_precision"] == round(2 / 3, 4)
    assert out["metrics"]["citation_accuracy"] == 1.0  # 寬鬆定義：多引用不扣分
