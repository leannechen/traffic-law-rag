"""BM25 關鍵字檢索（記憶體內）。中文需先斷詞，這裡提供兩種斷詞法：

- jieba：詞典斷詞，詞意完整，但詞典不是為法律用語與口語訓練的，會切錯。
- bigram：每兩個相鄰漢字當一個詞，不需詞典，不會「切錯」，代價是詞表較大、較吵。
"""

import logging
import math
import re
from collections import Counter
from typing import Literal

import jieba

jieba.setLogLevel(logging.WARNING)

Tokenizer = Literal["jieba", "bigram"]

_CJK = re.compile(r"[一-鿿]")
_TOKEN_CHARS = re.compile(r"[一-鿿A-Za-z0-9]+")


def tokenize(text: str, method: Tokenizer = "jieba") -> list[str]:
    if method == "bigram":
        tokens: list[str] = []
        for run in _TOKEN_CHARS.findall(text):
            if len(run) == 1:
                tokens.append(run)
            else:
                tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
        return tokens
    return [
        t for t in jieba.lcut(text) if _TOKEN_CHARS.fullmatch(t) and (len(t) > 1 or _CJK.match(t))
    ]


class BM25Index:
    def __init__(
        self, docs: list[str], method: Tokenizer = "jieba", k1: float = 1.5, b: float = 0.75
    ):
        self.method = method
        self._k1, self._b = k1, b
        self._tf = [Counter(tokenize(d, method)) for d in docs]
        self._len = [sum(tf.values()) for tf in self._tf]
        self._avg = (sum(self._len) / len(docs)) if docs else 0.0
        df: Counter[str] = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        n = len(docs)
        self._idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def scores(self, query: str) -> list[float]:
        terms = [t for t in tokenize(query, self.method) if t in self._idf]
        out = []
        for tf, length in zip(self._tf, self._len, strict=True):
            s = 0.0
            for t in terms:
                f = tf.get(t, 0)
                if f:
                    norm = f + self._k1 * (1 - self._b + self._b * length / self._avg)
                    s += self._idf[t] * f * (self._k1 + 1) / norm
            out.append(s)
        return out

    def search(self, query: str, n: int) -> list[tuple[int, float]]:
        """回傳 (文件索引, 分數)，分數為 0 的不回傳。"""
        ranked = sorted(enumerate(self.scores(query)), key=lambda x: (-x[1], x[0]))
        return [(i, s) for i, s in ranked[:n] if s > 0]
