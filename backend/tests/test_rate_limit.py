import pytest

from app.core.rate_limit import RateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_blocks_after_the_limit_and_reports_retry_after() -> None:
    clock = Clock()
    limiter = RateLimiter(3, 60, clock)
    assert [limiter.check("ip") for _ in range(3)] == [None, None, None]
    clock.now += 10
    assert limiter.check("ip") == 50  # 最早那次在 60 秒後才滑出視窗，還要等 50 秒


def test_allows_again_once_the_window_has_passed() -> None:
    clock = Clock()
    limiter = RateLimiter(1, 60, clock)
    assert limiter.check("ip") is None
    assert limiter.check("ip") == 60
    clock.now += 60
    assert limiter.check("ip") is None


def test_each_client_has_its_own_budget() -> None:
    limiter = RateLimiter(1, 60, Clock())
    assert limiter.check("a") is None
    assert limiter.check("b") is None
    assert limiter.check("a") is not None


def test_blocked_requests_do_not_extend_the_block() -> None:
    clock = Clock()
    limiter = RateLimiter(1, 60, clock)
    limiter.check("ip")
    for _ in range(5):
        clock.now += 5
        assert limiter.check("ip") is not None  # 被擋的請求不計入，不會越擋越久
    clock.now += 40  # 距離第一次剛好 65 秒
    assert limiter.check("ip") is None


def test_retry_after_is_at_least_one_second() -> None:
    clock = Clock()
    limiter = RateLimiter(1, 60, clock)
    limiter.check("ip")
    clock.now += 59.9
    assert limiter.check("ip") == 1


def test_expired_keys_are_pruned_when_too_many() -> None:
    import app.core.rate_limit as module

    clock = Clock()
    limiter = RateLimiter(1, 60, clock)
    original = module.MAX_TRACKED_KEYS
    module.MAX_TRACKED_KEYS = 5
    try:
        for i in range(10):
            limiter.check(f"ip{i}")
        clock.now += 120
        limiter.check("new")
        assert len(limiter._hits) <= 2
    finally:
        module.MAX_TRACKED_KEYS = original


def test_configuration_below_one_is_rejected() -> None:
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(rate_limit_requests=0)
