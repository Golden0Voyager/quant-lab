"""Extended tests for aggregator — covering ETF/index path."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quant_lab.core.data.aggregator import aggregate


class TestAggregatorV2:
    @patch("quant_lab.core.data.aggregator.MarketEnvFetcher")
    @patch("quant_lab.core.data.aggregator.MacroETFFetcher")
    @patch("quant_lab.core.data.aggregator.SentimentFetcher")
    def test_etf_aggregation(self, mock_sentiment_cls, mock_macro_cls, mock_market_cls) -> None:
        mock_sentiment_cls.return_value.fetch.return_value = {"sentiment": "data"}
        mock_macro_cls.return_value.fetch.return_value = {"macro": "data"}
        mock_market_cls.return_value.fetch.return_value = {"market": "data"}
        result = aggregate("399050", "中证互联网", asset_type="etf")
        assert result["type"] == "etf"
        assert "sentiment" in result

    @patch("quant_lab.core.data.aggregator._aggregate_stock")
    def test_stock_aggregation(self, mock_stock: MagicMock) -> None:
        mock_stock.return_value = None
        result = aggregate("000001", "平安银行", asset_type="stock")
        assert result["type"] == "stock"
        mock_stock.assert_called_once()
