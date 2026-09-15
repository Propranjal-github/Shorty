from __future__ import annotations

from time import sleep

import pytest

from app.core.rate_limiter import RateLimiter


def test_burst_then_reject() -> None:
    limiter = RateLimiter(capacity=3, refill_per_second=0.0001)
    assert all(limiter.allow("1.2.3.4") for _ in range(3))
    assert limiter.allow("1.2.3.4") is False


def test_refill_restores_budget() -> None:
    limiter = RateLimiter(capacity=1, refill_per_second=1000)
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False
    sleep(0.02)  # 1000/s * 0.02 = 20 tokens, capped at capacity 1
    assert limiter.allow("ip") is True


def test_keys_are_isolated() -> None:
    limiter = RateLimiter(capacity=1, refill_per_second=0.0001)
    assert limiter.allow("a") is True
    assert limiter.allow("b") is True  # separate bucket
    assert limiter.allow("a") is False


def test_invalid_params_raise() -> None:
    with pytest.raises(ValueError):
        RateLimiter(capacity=0, refill_per_second=1)
    with pytest.raises(ValueError):
        RateLimiter(capacity=1, refill_per_second=0)
