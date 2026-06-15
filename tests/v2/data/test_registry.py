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

    def test_register_overwrite_warning(self) -> None:
        registry = DimensionRegistry()
        fetcher1 = MagicMock()
        fetcher2 = MagicMock()
        registry.register("test", fetcher1)
        registry.register("test", fetcher2)
        assert registry.get("test") is fetcher2

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
        assert fetcher.calls == []
        cache.get.assert_called_once_with("valuation", "000001")

    def test_fetch_with_cache_hit_v2(self) -> None:
        from quant_lab.core.data.cache import DataCacheFacade

        mock_cache = MagicMock(spec=DataCacheFacade)
        mock_cache.get.return_value = {"cached": True}
        registry = DimensionRegistry(cache=mock_cache)
        fetcher = MagicMock()
        registry.register("test", fetcher)
        result = registry.fetch("test", "000001", "平安银行", use_cache=True)
        assert result == {"cached": True}
        fetcher.fetch.assert_not_called()

    def test_fetch_with_cache_miss(self) -> None:
        cache = MagicMock()
        cache.get.return_value = None

        reg = DimensionRegistry(cache=cache)
        fetcher = FakeFetcher(return_value={"pe": 10.5})
        reg.register("valuation", fetcher)

        result = reg.fetch("valuation", "000001", "平安银行")
        assert result == {"pe": 10.5}
        cache.set.assert_called_once_with("valuation", "000001", {"pe": 10.5})

    def test_fetch_with_cache_miss_and_write(self) -> None:
        from quant_lab.core.data.cache import DataCacheFacade

        mock_cache = MagicMock(spec=DataCacheFacade)
        mock_cache.get.return_value = None
        registry = DimensionRegistry(cache=mock_cache)
        fetcher = MagicMock()
        fetcher.fetch.return_value = {"result": "data"}
        registry.register("test", fetcher)
        result = registry.fetch("test", "000001", "平安银行", use_cache=True)
        assert result == {"result": "data"}
        mock_cache.set.assert_called_once_with("test", "000001", {"result": "data"})

    def test_fetch_with_cache_does_not_store_errors(self) -> None:
        cache = MagicMock()
        cache.get.return_value = None

        reg = DimensionRegistry(cache=cache)
        fetcher = FakeFetcher(return_value={"_error": "boom", "_dimension": "test"})
        reg.register("valuation", fetcher)

        reg.fetch("valuation", "000001", "平安银行")
        cache.set.assert_not_called()

    def test_fetch_error_no_cache_write(self) -> None:
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        registry = DimensionRegistry(cache=mock_cache)
        fetcher = MagicMock()
        fetcher.fetch.return_value = {"_error": "fail", "_dimension": "test"}
        registry.register("test", fetcher)
        result = registry.fetch("test", "000001", "平安银行", use_cache=True)
        assert "_error" in result
        mock_cache.set.assert_not_called()

    def test_fetch_not_registered(self) -> None:
        registry = DimensionRegistry()
        result = registry.fetch("nonexistent", "000001", "平安银行")
        assert "_error" in result

    def test_fetch_all(self) -> None:
        reg = DimensionRegistry()
        reg.register("a", FakeFetcher(return_value={"k": "a"}))
        reg.register("b", FakeFetcher(return_value={"k": "b"}))

        results = reg.fetch_all("000001", "平安银行")
        assert results == {"a": {"k": "a"}, "b": {"k": "b"}}

    def test_fetch_all_v2(self) -> None:
        registry = DimensionRegistry()
        f1 = MagicMock()
        f1.fetch.return_value = {"a": 1}
        f2 = MagicMock()
        f2.fetch.return_value = {"b": 2}
        registry.register("d1", f1)
        registry.register("d2", f2)
        result = registry.fetch_all("000001", "平安银行")
        assert "d1" in result
        assert "d2" in result

    def test_list_dimensions(self) -> None:
        reg = DimensionRegistry()
        reg.register("a", FakeFetcher())
        reg.register("b", FakeFetcher())
        assert sorted(reg.list_dimensions()) == ["a", "b"]

    def test_list_dimensions_v2(self) -> None:
        registry = DimensionRegistry()
        registry.register("a", MagicMock())
        registry.register("b", MagicMock())
        assert set(registry.list_dimensions()) == {"a", "b"}
