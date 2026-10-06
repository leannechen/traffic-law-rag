import pytest

from app.pipeline.validate import (
    check_numbers,
    chinese_to_int,
    extract_quantities,
    validate_citations,
)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("一千八百", 1800),
        ("五千四百", 5400),
        ("六百", 600),
        ("十五", 15),
        ("二十七", 27),
        ("一萬零八百", 10800),
        ("三萬六千", 36000),
        ("十二萬", 120000),
        ("十八萬", 180000),
        ("二十七萬", 270000),
        ("一百十", 110),
        ("兩百", 200),
        ("1,800", 1800),
        ("18", 18),
        ("3千", 3000),
        ("五百五十", 550),
    ],
)
def test_chinese_to_int(text: str, value: int) -> None:
    assert chinese_to_int(text) == value


def test_chinese_to_int_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        chinese_to_int("甲乙")


def test_extract_quantities_normalizes_and_ignores_ordinals() -> None:
    text = "依第三十五條第一項，處新臺幣六百元以上一千八百元以下罰鍰，並吊扣駕駛執照二年至四年"
    assert extract_quantities(text) == ["600元", "1800元", "2年", "4年"]


def test_extract_quantities_handles_fractions_and_compound_units() -> None:
    assert extract_quantities("加罰二分之一") == ["1/2"]
    assert extract_quantities("汽缸排氣量逾五十立方公分") == ["50立方公分"]
    assert extract_quantities("三十日內、時速四十公里、三個月") == ["30日", "40公里", "3個月"]


def test_arabic_and_chinese_numbers_normalize_to_same_value() -> None:
    assert extract_quantities("罰鍰1,800元") == extract_quantities("罰鍰一千八百元")


def test_validate_citations_flags_unknown_ids() -> None:
    allowed = {"K0040012:53", "K0040012:35-p1"}
    # 故意製造無效引用：捏造的條文、改錯的 id、整條 id 但提供的是切塊
    result = validate_citations(
        ["K0040012:53", "K0040012:999", "K0040012:35", "K0040012:53"], allowed
    )
    assert result.valid == ["K0040012:53"]
    assert result.invalid == ["K0040012:999", "K0040012:35"]


def test_validate_citations_all_valid_and_empty() -> None:
    assert validate_citations(["A:1"], {"A:1"}).invalid == []
    empty = validate_citations([], {"A:1"})
    assert empty.valid == [] and empty.invalid == []


def test_check_numbers_passes_when_copied_from_cited_text() -> None:
    cited = ["處新臺幣六百元以上一千八百元以下罰鍰。"]
    result = check_numbers("罰六百元到一千八百元。", cited)
    assert result.ok and result.total == 2 and result.matched == 2


def test_check_numbers_catches_a_wrong_amount() -> None:
    cited = ["處新臺幣六百元以上一千八百元以下罰鍰。"]
    result = check_numbers("罰六百元到二千元。", cited)
    assert not result.ok
    assert result.unmatched == ["2000元"]
    assert (result.matched, result.total) == (1, 2)


def test_check_numbers_without_citations_everything_is_unmatched() -> None:
    result = check_numbers("罰六百元。", [])
    assert result.unmatched == ["600元"]


def test_check_numbers_flags_derived_figures() -> None:
    cited = ["處新臺幣三千元罰鍰，累犯加罰二分之一。"]
    result = check_numbers("累犯要罰四千五百元。", cited)  # 模型自己算出來的
    assert result.unmatched == ["4500元"]


def test_check_numbers_with_no_numbers_is_ok() -> None:
    result = check_numbers("需要接受講習。", ["應接受講習。"])
    assert result.ok and result.total == 0
