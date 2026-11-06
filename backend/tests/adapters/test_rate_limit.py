from log_whisperer.adapters.inbound.http.rate_limit import SlidingWindowLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_window_slides() -> None:
    clock = Clock()
    limiter = SlidingWindowLimiter(2, window=60, clock=clock)
    assert limiter.allow("a")
    clock.now += 30
    assert limiter.allow("a")
    assert not limiter.allow("a")
    clock.now += 30.5
    assert limiter.allow("a")
    assert not limiter.allow("a")


def test_clients_are_counted_separately() -> None:
    limiter = SlidingWindowLimiter(1, clock=Clock())
    assert limiter.allow("a")
    assert limiter.allow("b")
    assert not limiter.allow("a")


def test_idle_clients_are_evicted_once_per_window() -> None:
    clock = Clock()
    limiter = SlidingWindowLimiter(5, window=60, clock=clock)
    for i in range(100):
        limiter.allow(f"10.0.0.{i}")
    assert limiter.tracked_clients == 100
    clock.now += 61
    limiter.allow("fresh")
    assert limiter.tracked_clients == 1
