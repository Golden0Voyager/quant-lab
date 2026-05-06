"""Tests for quant_lab.core.net.retry."""

from __future__ import annotations

from urllib3.util.retry import Retry

from quant_lab.core.net.retry import make_retry_strategy


class TestMakeRetryStrategy:
    """Tests for make_retry_strategy."""

    def test_returns_retry_instance(self) -> None:
        result = make_retry_strategy()
        assert isinstance(result, Retry)

    def test_default_params(self) -> None:
        r = make_retry_strategy()
        assert r.total == 2
        assert r.backoff_factor == 1.0
        assert r.status_forcelist == [429, 500, 502, 503, 504]
        assert r.connect == 1
        assert r.read == 1

    def test_custom_params(self) -> None:
        r = make_retry_strategy(
            total=5,
            backoff_factor=2.0,
            status_forcelist=(503,),
            connect=2,
            read=3,
        )
        assert r.total == 5
        assert r.backoff_factor == 2.0
        assert r.status_forcelist == [503]
        assert r.connect == 2
        assert r.read == 3
