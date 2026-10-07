import pytest

from app.pipeline.stream_parser import Citation, Refusal, StreamParser, Text


def run(deltas: list[str]) -> tuple[list[object], StreamParser]:
    parser = StreamParser()
    items: list[object] = []
    for d in deltas:
        items.extend(parser.feed(d))
    items.extend(parser.finish())
    return items, parser


def merged_text(items: list[object]) -> str:
    return "".join(i.text for i in items if isinstance(i, Text))


def citations(items: list[object]) -> list[str]:
    return [i.chunk_id for i in items if isinstance(i, Citation)]


FULL = "罰六百元[[K0040012:53]]。另依規定[[K0040012:35]]處罰。"


@pytest.mark.parametrize("size", [1, 2, 3, 4, 5, 7, 11, 100])
def test_citations_found_for_every_chunk_size(size: int) -> None:
    deltas = [FULL[i : i + size] for i in range(0, len(FULL), size)]
    items, parser = run(deltas)
    assert merged_text(items) == FULL  # 文字不遺失、不重複
    assert citations(items) == ["K0040012:53", "K0040012:35"]
    assert not parser.refused


@pytest.mark.parametrize("cut", range(1, len(FULL)))
def test_split_at_every_position(cut: int) -> None:
    items, _ = run([FULL[:cut], FULL[cut:]])
    assert merged_text(items) == FULL
    assert citations(items) == ["K0040012:53", "K0040012:35"]


def test_no_text_item_ever_contains_half_a_marker() -> None:
    parser = StreamParser()
    for i in range(0, len(FULL), 2):
        for item in parser.feed(FULL[i : i + 2]):
            if isinstance(item, Text):
                assert item.text.count("[[") == item.text.count("]]")


def test_citation_follows_the_text_that_contains_its_marker() -> None:
    items, _ = run(["罰六百元[[K:53]]。"])
    assert items == [Text("罰六百元[[K:53]]"), Citation("[[K:53]]", "K:53"), Text("。")]


def test_text_with_single_brackets_is_untouched() -> None:
    items, _ = run(["陣列 [1] 與 [a]"])
    assert merged_text(items) == "陣列 [1] 與 [a]"
    assert citations(items) == []


def test_trailing_single_bracket_is_held_until_next_delta() -> None:
    parser = StreamParser()
    first = parser.feed("文字 [")
    assert merged_text(list(first)) == "文字 "  # "[" 先留著
    second = parser.feed("[K:1]]")
    assert citations(list(second)) == ["K:1"]


def test_lone_bracket_at_the_end_is_flushed_as_text() -> None:
    items, _ = run(["結尾 ["])
    assert merged_text(items) == "結尾 ["


def test_unterminated_marker_at_end_becomes_plain_text() -> None:
    items, _ = run(["有 [[K0040"])
    assert merged_text(items) == "有 [[K0040" and citations(items) == []


def test_overlong_unterminated_marker_is_released_as_text() -> None:
    items, _ = run(["[[" + "x" * 200])
    assert merged_text(items).startswith("[[xxx") and citations(items) == []


def test_empty_or_odd_double_brackets_are_text_not_citations() -> None:
    items, _ = run(["[[]] 與 [[a[b]]"])
    assert citations(items) == []
    assert merged_text(items) == "[[]] 與 [[a[b]]"


@pytest.mark.parametrize("size", [1, 2, 3, 10, 50])
def test_refusal_at_the_start_emits_no_text(size: int) -> None:
    deltas = ["[[REFUSE]]"[i : i + size] for i in range(0, 10, size)]
    items, parser = run(deltas)
    assert items == [Refusal()]
    assert parser.refused


def test_refusal_with_leading_whitespace() -> None:
    items, parser = run(["\n[[REF", "USE]]"])
    assert items == [Refusal()] and parser.refused


def test_text_after_refusal_is_ignored() -> None:
    parser = StreamParser()
    parser.feed("[[REFUSE]]")
    assert parser.feed("多餘的字") == []
    assert parser.finish() == []


def test_beginning_that_only_looks_like_refusal_is_released() -> None:
    items, parser = run(["[[REF", "ERENCE]] 其實是引用"])
    assert not parser.refused
    assert citations(items) == ["REFERENCE"]


def test_short_answer_that_is_a_prefix_of_the_marker_is_flushed_at_finish() -> None:
    items, _ = run(["[[REF"])
    assert merged_text(items) == "[[REF"  # 串流結束時沒有變成拒答標記，就當一般文字


def test_refusal_in_the_middle_is_reported_after_streamed_text() -> None:
    items, parser = run(["先說了一些話。", "[[REFUSE]]"])
    assert items == [Text("先說了一些話。"), Refusal()]
    assert parser.refused


def test_chinese_text_is_never_split_mid_character() -> None:
    items, _ = run(list("紅燈右轉[[K:1]]罰款"))  # 一次一個字元
    assert merged_text(items) == "紅燈右轉[[K:1]]罰款"
