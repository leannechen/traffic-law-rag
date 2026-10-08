"""Chroma 的客戶端不能同時建立（見 app/api/deps.py）：第一次使用時的建立必須一次一個。"""

import threading
import time
from collections.abc import Callable
from typing import Any

import pytest

from app.api import deps as deps_module


class Probe:
    """記錄同時有幾個執行緒在「建立」裡。"""

    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.calls = 0
        self._lock = threading.Lock()

    def build(self) -> object:
        with self._lock:
            self.active += 1
            self.calls += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.05)  # 讓其他執行緒有機會同時闖進來
        with self._lock:
            self.active -= 1
        return object()


def run_concurrently(fn: Callable[[], Any], n: int = 8) -> None:
    threads = [threading.Thread(target=fn) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def test_ask_deps_are_never_built_by_two_threads_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    probe = Probe()
    monkeypatch.setattr(deps_module, "_build_ask_deps", probe.build)
    run_concurrently(deps_module.get_ask_deps)
    assert probe.max_active == 1


def test_collection_is_never_opened_by_two_threads_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    probe = Probe()
    monkeypatch.setattr(deps_module, "_collection_cached", probe.build)
    run_concurrently(deps_module._collection)
    assert probe.max_active == 1
