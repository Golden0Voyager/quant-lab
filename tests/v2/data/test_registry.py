"""Tests for quant_lab.core.data.registry."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from quant_lab.core.data.registry import DimensionRegistry


class FakeFetcher:
    """Stub fetcher for testing."""

    name = "test_dim"

    def __init__(self, return_value: dict[str, Any] | None = None) -> None:
        self.return_value = return_value or {"field": "value"}
        self.calls: list[tuple[str, str]] = []

    def fetch(self, symbol: str, stock_name: str) -> dict[str, Any]:
        self.calls.append((symbol, stock_name))
        return self.return_value


class TestDimensionRegistry:
    def test_register_and_get(self) -> None:
        reg = DimensionRegistry()
        fetcher = FakeFetcher()
        reg.register("test_dim", fetcher)
        assert reg.get("test_dim") is fetcher
        assert reg.get("missing") is None

    def test_fetch_without_cache(self) -> None:
        reg = DimensionRegistry()
        fetcher = FakeFetcher(return_value={"pe": 10.5})
        reg.register("valuation", fetcher)

        result = reg.fetch("valuation", "000001", "平安银行")
        assert result == {"pe": 10.5}
        assert fetcher.calls == [("000001", "平安银行")]

    def test_fetch_unregistered_dimension(self) -> None:
        reg = DimensionRegistry()
        result = reg.fetch("missing", "000001", "平安银行")
        assert "_error" in result
        assert result["_dimension"] == "missing"

    def test_fetch_with_cache_hit(self) -> None:
        cache = MagicMock()
        cache.get.return_value = {"cached": True}

        reg = DimensionRegistry(cache=cache)
        fetcher = FakeFetcher()
        reg.register("valuation", fetcher)

        result = reg.fetch("valuation", "000001", "平安银行")
        assert result == {"cached": True}
        assert fetcher.calls == []  # fetcher should not be called
        cache.get.assert_called_once_with("valuation", "000001")

    def test_fetch_with_cache_miss(self) -> None:
        cache = MagicMock()
        cache.get.return_value = None

        reg = DimensionRegistry(cache=cache)
        fetcher = FakeFetcher(return_value={"pe": 10.5})
        reg.register("valuation", fetcher)

        result = reg.fetch("valuation", "000001", "平安银行")
        assert result == {"pe": 10.5}
        cache.set.assert_called_once_with("valuation", "000001", {"pe": 10.5})

    def test_fetch_with_cache_does_not_store_errors(self) -> None:
        cache = MagicMock()
        cache.get.return_value = None

        reg = DimensionRegistry(cache=cache)
        fetcher = FakeFetcher(return_value={"_error": "boom", "_dimension": "test"})
        reg.register("valuation", fetcher)

        reg.fetch("valuation", "000001", "平安银行")
        cache.set.assert_not_called()

    def test_fetch_all(self) -> None:
        reg = DimensionRegistry()
        reg.register("a", FakeFetcher(return_value={"k": "a"}))
        reg.register("b", FakeFetcher(return_value={"k": "b"}))

        results = reg.fetch_all("000001", "平安银行")
        assert results == {"a": {"k": "a"}, "b": {"k": "b"}}

    def test_list_dimensions(self) -> None:
        reg = DimensionRegistry()
        reg.register("a", FakeFetcher())
        reg.register("b", FakeFetcher())
        assert sorted(reg.list_dimensions()) == ["a", "b"]
