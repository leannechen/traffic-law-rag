"""全站每日提問上限：付費 API 的第二道防線（第一道是供應商端的花費上限）。

限制：計數存在程式記憶體，只在單一實例有效，重新啟動（含 Fly 機器停機後喚醒）就歸零；
所以它擋的是「一般的濫用」，擋不住有意的、會讓機器反覆重啟的攻擊。底線是供應商端的花費上限。
"""

import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime


class DailyBudget:
    def __init__(self, max_per_day: int, clock: Callable[[], float] = time.time) -> None:
        self._max = max_per_day
        self._clock = clock
        self._day = self._today()
        self._used = 0
        self._lock = threading.Lock()

    def _today(self) -> str:
        return datetime.fromtimestamp(self._clock(), UTC).strftime("%Y-%m-%d")

    def try_acquire(self) -> bool:
        """還有額度就扣一次並回傳 True；今天（UTC）用完了回傳 False。"""
        with self._lock:
            today = self._today()
            if today != self._day:
                self._day, self._used = today, 0
            if self._used >= self._max:
                return False
            self._used += 1
            return True
