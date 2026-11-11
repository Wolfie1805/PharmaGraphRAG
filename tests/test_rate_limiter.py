"""Tests for RateLimiter behavior."""

import time

import pytest

from app.ingestion.rate_limiter import RateLimiter


def test_rate_limiter_spacing():
    # 10 requests per second -> interval is 0.10s
    limiter = RateLimiter(requests_per_second=10.0)

    start = time.monotonic()
    limiter.wait()
    limiter.wait()
    limiter.wait()
    duration = time.monotonic() - start

    # 3 calls at 10 rps should take at least ~0.20s
    assert duration >= 0.18


def test_rate_limiter_invalid_rate():
    with pytest.raises(ValueError):
        RateLimiter(requests_per_second=0.0)
    with pytest.raises(ValueError):
        RateLimiter(requests_per_second=-2.5)

