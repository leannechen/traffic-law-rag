"""串流中的標記解析：把模型一段一段吐出的文字，整理成「文字」與「引用」兩種項目。

兩個問題：
1. 引用標記 `[[K0040012:53]]` 可能被切在兩個 delta 之間（`[[K00` ＋ `40012:53]]`）。
   做法：標記沒收完整之前先暫存，保證送出去的文字裡不會有半個標記。
2. 拒答標記 `[[REFUSE]]` 出現在回答的開頭：先暫存開頭幾個字元，確認不是拒答才開始送文字。
   （拒答時使用者不應先看到一點碎字。）
"""

from dataclasses import dataclass

REFUSAL_MARKER = "[[REFUSE]]"
MAX_MARKER_LENGTH = 80  # 超過這個長度還沒收到 ]]，就當成一般文字，避免一直暫存


@dataclass(frozen=True)
class Text:
    text: str


@dataclass(frozen=True)
class Citation:
    marker: str  # 原樣標記，例如 "[[K0040012:53]]"
    chunk_id: str  # 去掉 [[ ]] 後的 id


@dataclass(frozen=True)
class Refusal:
    pass


Item = Text | Citation | Refusal


class StreamParser:
    def __init__(self) -> None:
        self._buffer = ""
        self._started = False  # 是否已通過開頭的拒答檢查
        self.refused = False

    def feed(self, delta: str) -> list[Item]:
        if self.refused:
            return []
        self._buffer += delta
        items: list[Item] = []
        if not self._started:
            if REFUSAL_MARKER.startswith(self._buffer.lstrip()):
                if self._buffer.lstrip() == REFUSAL_MARKER:
                    self.refused = True
                    self._buffer = ""
                    return [Refusal()]
                return []  # 還可能是拒答標記的一部分，繼續等
            self._started = True
        items.extend(self._drain(final=False))
        return items

    def finish(self) -> list[Item]:
        """串流結束：把還暫存的內容送出（沒收完整的標記視為一般文字）。"""
        if self.refused:
            return []
        self._started = True
        return self._drain(final=True)

    def _drain(self, *, final: bool) -> list[Item]:
        items: list[Item] = []
        while self._buffer:
            start = self._buffer.find("[[")
            if start == -1:
                # 結尾若是單獨一個 "["，可能是下一段 "[[" 的前半，留著
                keep = 1 if (not final and self._buffer.endswith("[")) else 0
                self._emit_text(items, self._buffer[: len(self._buffer) - keep])
                self._buffer = self._buffer[len(self._buffer) - keep :]
                break
            if start > 0:
                self._emit_text(items, self._buffer[:start])
                self._buffer = self._buffer[start:]
            end = self._buffer.find("]]")
            if end == -1:
                if final or len(self._buffer) > MAX_MARKER_LENGTH:
                    self._emit_text(items, self._buffer)
                    self._buffer = ""
                break  # 標記還沒收完整，等下一段
            marker = self._buffer[: end + 2]
            self._buffer = self._buffer[end + 2 :]
            body = marker[2:-2]
            if marker == REFUSAL_MARKER:
                self.refused = (
                    True  # 回答中途才出現拒答標記：之前的文字已送出，由呼叫端決定如何收尾
                )
                self._buffer = ""
                items.append(Refusal())
                break
            if body and "\n" not in body and "[" not in body:
                self._emit_text(items, marker)
                items.append(Citation(marker=marker, chunk_id=body))
            else:
                self._emit_text(items, marker)  # 不像標記的雙括號，原樣當文字
        return items

    @staticmethod
    def _emit_text(items: list[Item], text: str) -> None:
        if not text:
            return
        if items and isinstance(items[-1], Text):
            items[-1] = Text(items[-1].text + text)  # 合併相鄰文字
        else:
            items.append(Text(text))
