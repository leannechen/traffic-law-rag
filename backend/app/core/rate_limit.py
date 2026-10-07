"""記憶體內的滑動視窗速率限制。

限制：計數存在程式記憶體，只在「單一實例」有效；部署成多個實例時每個實例各算各的，
要改成共用儲存（如 Redis）。重新啟動後計數歸零。
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable

MAX_TRACKED_KEYS = 10_000  # 超過就清掉已過期的，避免被大量不同 IP 撐爆記憶體


class RateLimiter:
    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> int | None:
        """放行回傳 None（並記錄這一次）；超過限制回傳要等幾秒（Retry-After）。"""
        now = self._clock()
        with self._lock:
            if len(self._hits) > MAX_TRACKED_KEYS:
                self._prune(now)
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._max:
                return max(1, math.ceil(self._window - (now - hits[0])))
            hits.append(now)
            return None

    def _prune(self, now: float) -> None:
        for key in [k for k, h in self._hits.items() if not h or now - h[-1] >= self._window]:
            del self._hits[key]
