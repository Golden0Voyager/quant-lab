"""Tests for quant_lab.core.llm.rate_limit."""

from __future__ import annotations

import time
from unittest.mock import patch

from quant_lab.core.llm.rate_limit import RateLimiter, get_limiter


class TestRateLimiter:
    def test_acquire_basic(self) -> None:
        limiter = RateLimiter(qps=10, rpm=100, name="test")
        limiter.acquire()
        assert len(limiter._window) == 1

    def test_acquire_qps_throttle(self) -> None:
        limiter = RateLimiter(qps=2, rpm=100, name="test")
        limiter.acquire()
        start = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.4

    def test_acquire_rpm_throttle(self) -> None:
        limiter = RateLimiter(qps=100, rpm=2, name="test")
        limiter.acquire()
        limiter.acquire()
        start = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.05

    def test_window_cleanup(self) -> None:
        limiter = RateLimiter(qps=100, rpm=100, name="test")
        limiter._window = [time.monotonic() - 70]  # old entry
        limiter.acquire()
        assert len(limiter._window) == 1


class TestGetLimiter:
    def test_known_provider(self) -> None:
        limiter = get_limiter("sensenova")
        assert limiter is not None
        assert limiter.name == "sensenova"
        assert limiter.qps == 1

    def test_unknown_provider(self) -> None:
        limiter = get_limiter("unknown")
        assert limiter is None

    def test_singleton(self) -> None:
        limiter1 = get_limiter("sensenova")
        limiter2 = get_limiter("sensenova")
        assert limiter1 is limiter2
