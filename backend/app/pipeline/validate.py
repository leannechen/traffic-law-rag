"""驗證：引用是否都在本次檢索結果內；答案中的數字是否能在引用的條文原文找到。純函式。"""

import re
from dataclasses import dataclass, field

_DIGITS = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    **{str(d): d for d in range(10)},
}  # fmt: skip
_SMALL_UNITS = {"十": 10, "百": 100, "千": 1000}
_NUM = r"[零〇一二兩三四五六七八九十百千萬億\d,]+"
_UNITS = "立方公分|公里|公分|公尺|公斤|馬力|個月|分鐘|小時|元|年|月|日|天|秒|歲|次|倍|點|人|輛"
_FRACTION_RE = re.compile(rf"({_NUM})分之({_NUM})")
_QUANTITY_RE = re.compile(rf"({_NUM})({_UNITS})")


def chinese_to_int(text: str) -> int:
    """「一千八百」→1800、「一萬零八百」→10800、「一百十」→110、「1,800」→1800。"""
    text = text.replace(",", "")
    if text.isdigit():
        return int(text)

    def section(part: str) -> int:
        total, num = 0, 0
        for ch in part:
            if ch in _SMALL_UNITS:
                total += (num or 1) * _SMALL_UNITS[ch]
                num = 0
            elif ch in _DIGITS:
                num = num * 10 + _DIGITS[ch] if part.isdigit() else _DIGITS[ch]
            else:
                raise ValueError(f"無法解析的數字：{text!r}")
        return total + num

    if "億" in text:
        high, low = text.split("億", 1)
        return (chinese_to_int(high) if high else 1) * 100_000_000 + (
            chinese_to_int(low) if low else 0
        )
    if "萬" in text:
        high, low = text.split("萬", 1)
        return (section(high) if high else 1) * 10_000 + section(low)
    return section(text)


def extract_quantities(text: str) -> list[str]:
    """抽出「數字＋單位」並正規化，如「新臺幣一千八百元」→「1800元」、「二分之一」→「1/2」。

    中文與阿拉伯數字寫法不同但數值相同時，會得到相同的結果。
    """
    found: list[str] = []

    def fraction(m: re.Match[str]) -> str:
        try:
            found.append(f"{chinese_to_int(m.group(2))}/{chinese_to_int(m.group(1))}")
        except ValueError:
            pass
        return " "

    rest = _FRACTION_RE.sub(fraction, text)
    for m in _QUANTITY_RE.finditer(rest):
        try:
            found.append(f"{chinese_to_int(m.group(1))}{m.group(2)}")
        except ValueError:
            continue
    return found


@dataclass(frozen=True)
class CitationCheck:
    valid: list[str]
    invalid: list[str]


def validate_citations(cited: list[str], allowed: set[str]) -> CitationCheck:
    """引用的 chunk_id 必須都在本次提供給模型的條文內；不在的列為 invalid。"""
    unique = list(dict.fromkeys(cited))
    return CitationCheck(
        valid=[c for c in unique if c in allowed], invalid=[c for c in unique if c not in allowed]
    )


@dataclass(frozen=True)
class NumberCheck:
    total: int
    matched: int
    unmatched: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.unmatched


def check_numbers(answer: str, cited_texts: list[str]) -> NumberCheck:
    """答案中的每個數量都必須能在「它引用的條文」中找到（沒有引用就全部找不到）。"""
    source = {q for t in cited_texts for q in extract_quantities(t)}
    quantities = extract_quantities(answer)
    unmatched = [q for q in quantities if q not in source]
    return NumberCheck(len(quantities), len(quantities) - len(unmatched), unmatched)
