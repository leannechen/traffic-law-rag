from datetime import UTC, datetime

from app.core.budget import DailyBudget


class Clock:
    def __init__(self, iso: str) -> None:
        self.now = datetime.fromisoformat(iso).replace(tzinfo=UTC).timestamp()

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_the_limit_then_refuses() -> None:
    budget = DailyBudget(3, clock=Clock("2026-10-08T10:00:00"))
    assert [budget.try_acquire() for _ in range(5)] == [True, True, True, False, False]


def test_resets_on_the_next_utc_day() -> None:
    clock = Clock("2026-10-08T23:59:00")
    budget = DailyBudget(1, clock=clock)
    assert budget.try_acquire() is True
    assert budget.try_acquire() is False
    clock.now += 120  # 跨過 UTC 午夜
    assert budget.try_acquire() is True
