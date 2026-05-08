"""Tests for SentimentFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quant_lab.core.data.dimensions.sentiment import SentimentFetcher


class TestSentimentFetcher:
    @patch("quant_lab.core.data.dimensions.sentiment.fetch_xueqiu_spot")
    @patch("quant_lab.core.data.dimensions.sentiment.ak")
    def test_xueqiu_success(self, mock_ak: MagicMock, mock_xq: MagicMock) -> None:
        mock_xq.return_value = {"量比": "1.5", "周转率": "2.3"}
        mock_ak.stock_hsgt_individual_em.return_value = None

        fetcher = SentimentFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["volume_ratio"] == "1.50"
        assert result["turnover_rate"] == "2.30%"
        assert result["volume_alert"] == "正常"
        assert "sentiment_summary" in result
        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.sentiment.fetch_xueqiu_spot")
    @patch("quant_lab.core.data.dimensions.sentiment.fetch_stock_info_eastmoney")
    @patch("quant_lab.core.data.dimensions.sentiment.ak")
    def test_xueqiu_fail_fallback_eastmoney(
        self,
        mock_ak: MagicMock,
        mock_em: MagicMock,
        mock_xq: MagicMock,
    ) -> None:
        mock_xq.return_value = None
        mock_em.return_value = {"换手率": "1.8"}
        mock_ak.stock_hsgt_individual_em.return_value = None

        fetcher = SentimentFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["turnover_rate"] == "1.80%"
        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.sentiment.fetch_xueqiu_spot")
    @patch("quant_lab.core.data.dimensions.sentiment.fetch_stock_info_eastmoney")
    @patch("quant_lab.core.data.dimensions.sentiment.ak")
    def test_high_volume_alert(
        self,
        mock_ak: MagicMock,
        mock_em: MagicMock,
        mock_xq: MagicMock,
    ) -> None:
        mock_xq.return_value = {"量比": "3.0", "周转率": "5.0"}
        mock_ak.stock_hsgt_individual_em.return_value = None

        fetcher = SentimentFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "放量" in result["volume_alert"]
