"""Tests for quant_lab.core.data.cache."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from quant_lab.core.data.cache import DataCacheFacade


@pytest.fixture
def mock_backend() -> MagicMock:
    """Return a mock DataCache backend."""
    return MagicMock()


@pytest.fixture
def facade(mock_backend: MagicMock) -> DataCacheFacade:
    """Return a DataCacheFacade wired to *mock_backend*."""
    return DataCacheFacade(cache=mock_backend)


class TestDataCacheFacade:
    def test_get_hit(self, facade: DataCacheFacade, mock_backend: MagicMock) -> None:
        mock_backend.get.return_value = {"pe_ttm": 15.2}
        result = facade.get("valuation", "000001")
        assert result == {"pe_ttm": 15.2}
        mock_backend.get.assert_called_once_with("000001", "valuation")

    def test_get_miss(self, facade: DataCacheFacade, mock_backend: MagicMock) -> None:
        mock_backend.get.return_value = None
        result = facade.get("valuation", "000001")
        assert result is None

    def test_set_with_default_ttl(self, facade: DataCacheFacade, mock_backend: MagicMock) -> None:
        facade.set("valuation", "000001", {"pe_ttm": 15.2})
        mock_backend.set.assert_called_once()
        args = mock_backend.set.call_args[0]
        assert args[0] == "000001"
        assert args[1] == "valuation"
        assert args[2] == {"pe_ttm": 15.2}
        # Default TTL for valuation is 24h
        assert args[3] == 24 * 60 * 60

    def test_set_with_custom_ttl(self, facade: DataCacheFacade, mock_backend: MagicMock) -> None:
        facade.set("valuation", "000001", {"pe_ttm": 15.2}, ttl=300)
        args = mock_backend.set.call_args[0]
        assert args[3] == 300

    def test_invalidate(self, facade: DataCacheFacade, mock_backend: MagicMock) -> None:
        facade.invalidate("valuation", "000001")
        mock_backend.set.assert_called_once_with("000001", "valuation", None, 1)
