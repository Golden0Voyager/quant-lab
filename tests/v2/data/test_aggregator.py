"""Tests for core/data/aggregator.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quant_lab.core.data.aggregator import (
    StockAggregator,
    _compute_peg,
    _compute_ps_ttm,
    aggregate,
)
from tests.v2.helpers import make_mock_fetcher


class TestAggregator:
    @patch("quant_lab.core.data.aggregator.ValuationFetcher")
    @patch("quant_lab.core.data.aggregator.PerformanceFetcher")
    @patch("quant_lab.core.data.aggregator.SentimentFetcher")
    @patch("quant_lab.core.data.aggregator.MacroETFFetcher")
    @patch("quant_lab.core.data.aggregator.ConsensusFetcher")
    @patch("quant_lab.core.data.aggregator.RecentKlineFetcher")
    @patch("quant_lab.core.data.aggregator.QuarterlyTrendFetcher")
    @patch("quant_lab.core.data.aggregator.IndustryCompareFetcher")
    @patch("quant_lab.core.data.aggregator.TopHoldersFetcher")
    @patch("quant_lab.core.data.aggregator.ThemeSentimentFetcher")
    @patch("quant_lab.core.data.aggregator.MarketEnvFetcher")
    @patch("quant_lab.core.data.aggregator.LockupFetcher")
    @patch("quant_lab.core.data.aggregator.ChipFetcher")
    @patch("quant_lab.core.data.aggregator.InstitutionFetcher")
    @patch("quant_lab.core.data.aggregator.CompetitorFetcher")
    @patch("quant_lab.core.data.aggregator.SmartMoneyFetcher")
    @patch("quant_lab.core.data.aggregator.NewsFetcher")
    @patch("quant_lab.core.data.aggregator.SupportResistanceFetcher")
    def test_stock_aggregation(
        self,
        mock_sr_cls: MagicMock,
        mock_news_cls: MagicMock,
        mock_sm_cls: MagicMock,
        mock_comp_cls: MagicMock,
        mock_inst_cls: MagicMock,
        mock_chip_cls: MagicMock,
        mock_lock_cls: MagicMock,
        mock_me_cls: MagicMock,
        mock_ts_cls: MagicMock,
        mock_th_cls: MagicMock,
        mock_ic_cls: MagicMock,
        mock_qt_cls: MagicMock,
        mock_rk_cls: MagicMock,
        mock_con_cls: MagicMock,
        mock_macro_cls: MagicMock,
        mock_sent_cls: MagicMock,
        mock_perf_cls: MagicMock,
        mock_val_cls: MagicMock,
    ) -> None:
        mock_val_cls.return_value = make_mock_fetcher({"pe_ttm_raw": 15.0})
        mock_perf_cls.return_value = make_mock_fetcher({"revenue_ttm_raw": 100.0, "market_cap": 500.0})
        mock_sent_cls.return_value = make_mock_fetcher({"sentiment": "中性"})
        mock_macro_cls.return_value = make_mock_fetcher({"usdcnh_rate": 7.2})
        mock_con_cls.return_value = make_mock_fetcher({"eps_growth_rate_raw": 0.2})
        mock_rk_cls.return_value = make_mock_fetcher({"current_price": 50.0, "ma20": 48.0})
        mock_qt_cls.return_value = make_mock_fetcher({"qt_signal": "上升"})
        mock_ic_cls.return_value = make_mock_fetcher({"peer_count": 10})
        mock_th_cls.return_value = make_mock_fetcher({"holder_count": 5})
        mock_ts_cls.return_value = make_mock_fetcher({"stock_sentiment": "偏多"})
        mock_me_cls.return_value = make_mock_fetcher({"market_sentiment": "偏暖"})
        mock_lock_cls.return_value = make_mock_fetcher({"lockup_risk_level": "低风险"})
        mock_chip_cls.return_value = make_mock_fetcher({"chip_profit_ratio_raw": 60.0})
        mock_inst_cls.return_value = make_mock_fetcher({"fund_holding_count": 20})
        mock_comp_cls.return_value = make_mock_fetcher({"competitors": []})
        mock_sm_cls.return_value = make_mock_fetcher({"north_consecutive_days": 3})
        mock_news_cls.return_value = make_mock_fetcher({"news_source": "东财公告"})
        mock_sr_cls.return_value = make_mock_fetcher({"resistance_price": 55.0})

        result = aggregate("000001", "平安银行", asset_type="stock")

        assert result["code"] == "000001"
        assert result["name"] == "平安银行"
        assert result["type"] == "stock"
        assert result["pe_ttm_raw"] == 15.0
        assert result["current_price"] == 50.0
        assert result["resistance_price"] == 55.0
        assert result["peg_raw"] == 75.0
        assert "高估" in result["peg_signal"]
        assert result["ps_ttm_raw"] == 5.0

        mock_sr_cls.return_value.fetch.assert_called_once()
        _, kwargs = mock_sr_cls.return_value.fetch.call_args
        assert "context" in kwargs

    @patch("quant_lab.core.data.aggregator.SentimentFetcher")
    @patch("quant_lab.core.data.aggregator.MacroETFFetcher")
    @patch("quant_lab.core.data.aggregator.MarketEnvFetcher")
    def test_etf_aggregation(
        self,
        mock_me_cls: MagicMock,
        mock_macro_cls: MagicMock,
        mock_sent_cls: MagicMock,
    ) -> None:
        mock_sent_cls.return_value.fetch.return_value = {"sentiment": "中性"}
        mock_macro_cls.return_value.fetch.return_value = {"usdcnh_rate": 7.2}
        mock_me_cls.return_value.fetch.return_value = {"market_sentiment": "偏暖"}

        result = aggregate("510300", "沪深300ETF", asset_type="etf")

        assert result["type"] == "etf"
        assert result["sentiment"] == "中性"
        assert "pe_ttm_raw" not in result
        assert "peg" not in result

    @patch("quant_lab.core.data.aggregator.ValuationFetcher")
    @patch("quant_lab.core.data.aggregator.PerformanceFetcher")
    @patch("quant_lab.core.data.aggregator.SentimentFetcher")
    @patch("quant_lab.core.data.aggregator.MacroETFFetcher")
    @patch("quant_lab.core.data.aggregator.ConsensusFetcher")
    @patch("quant_lab.core.data.aggregator.RecentKlineFetcher")
    @patch("quant_lab.core.data.aggregator.QuarterlyTrendFetcher")
    @patch("quant_lab.core.data.aggregator.IndustryCompareFetcher")
    @patch("quant_lab.core.data.aggregator.TopHoldersFetcher")
    @patch("quant_lab.core.data.aggregator.ThemeSentimentFetcher")
    @patch("quant_lab.core.data.aggregator.MarketEnvFetcher")
    @patch("quant_lab.core.data.aggregator.LockupFetcher")
    @patch("quant_lab.core.data.aggregator.ChipFetcher")
    @patch("quant_lab.core.data.aggregator.InstitutionFetcher")
    @patch("quant_lab.core.data.aggregator.CompetitorFetcher")
    @patch("quant_lab.core.data.aggregator.SmartMoneyFetcher")
    @patch("quant_lab.core.data.aggregator.NewsFetcher")
    @patch("quant_lab.core.data.aggregator.SupportResistanceFetcher")
    def test_fetcher_failure_graceful(
        self,
        mock_sr_cls: MagicMock,
        mock_news_cls: MagicMock,
        mock_sm_cls: MagicMock,
        mock_comp_cls: MagicMock,
        mock_inst_cls: MagicMock,
        mock_chip_cls: MagicMock,
        mock_lock_cls: MagicMock,
        mock_me_cls: MagicMock,
        mock_ts_cls: MagicMock,
        mock_th_cls: MagicMock,
        mock_ic_cls: MagicMock,
        mock_qt_cls: MagicMock,
        mock_rk_cls: MagicMock,
        mock_con_cls: MagicMock,
        mock_macro_cls: MagicMock,
        mock_sent_cls: MagicMock,
        mock_perf_cls: MagicMock,
        mock_val_cls: MagicMock,
    ) -> None:
        mock_val_cls.return_value = make_mock_fetcher({"pe_ttm_raw": 10.0})
        mock_perf_cls.return_value = make_mock_fetcher({})
        mock_sent_cls.return_value = make_mock_fetcher({})
        mock_macro_cls.return_value = make_mock_fetcher({})
        mock_con_cls.return_value = make_mock_fetcher({})
        mock_rk_cls.return_value = make_mock_fetcher({"current_price": 100.0})
        mock_qt_cls.return_value = make_mock_fetcher({})
        mock_ic_cls.return_value = make_mock_fetcher({})
        mock_th_cls.return_value = make_mock_fetcher({})
        mock_ts_cls.return_value = make_mock_fetcher({})
        mock_me_cls.return_value = make_mock_fetcher({})
        mock_lock_cls.return_value = make_mock_fetcher({})
        mock_chip_cls.return_value = make_mock_fetcher({})
        mock_inst_cls.return_value = make_mock_fetcher({})
        mock_comp_cls.return_value = make_mock_fetcher({})
        mock_sm_cls.return_value = make_mock_fetcher({})
        mock_news_cls.return_value = make_mock_fetcher({})

        sr_mock = MagicMock()
        # simulate what @safe_fetch would return on failure
        sr_mock.fetch.return_value = {"_error": "boom", "_dimension": "support_resistance"}
        mock_sr_cls.return_value = sr_mock

        result = aggregate("000001", "平安银行", asset_type="stock")

        assert result["code"] == "000001"
        assert result["current_price"] == 100.0


class TestComputePegException:
    def test_peg_exception_handler(self) -> None:
        data: dict = {"pe_ttm_raw": "abc", "eps_growth_rate_raw": "def"}
        _compute_peg(data)
        assert "peg" not in data

    def test_peg_zero_growth(self) -> None:
        data: dict = {"pe_ttm_raw": 10.0, "eps_growth_rate_raw": 0}
        _compute_peg(data)
        assert "peg" not in data

    def test_peg_negative_growth(self) -> None:
        data: dict = {"pe_ttm_raw": 10.0, "eps_growth_rate_raw": -5.0}
        _compute_peg(data)
        assert "peg" not in data


class TestComputePsTtmException:
    def test_ps_ttm_exception_handler(self) -> None:
        data: dict = {"market_cap": "abc", "revenue_ttm_raw": "def"}
        _compute_ps_ttm(data)
        assert "ps_ttm" not in data

    def test_ps_ttm_zero_revenue(self) -> None:
        data: dict = {"market_cap": 1000.0, "revenue_ttm_raw": 0}
        _compute_ps_ttm(data)
        assert "ps_ttm" not in data


class TestStockAggregatorClass:
    @patch("quant_lab.core.data.aggregator.ValuationFetcher")
    @patch("quant_lab.core.data.aggregator.PerformanceFetcher")
    @patch("quant_lab.core.data.aggregator.SentimentFetcher")
    @patch("quant_lab.core.data.aggregator.MacroETFFetcher")
    @patch("quant_lab.core.data.aggregator.ConsensusFetcher")
    @patch("quant_lab.core.data.aggregator.RecentKlineFetcher")
    @patch("quant_lab.core.data.aggregator.QuarterlyTrendFetcher")
    @patch("quant_lab.core.data.aggregator.IndustryCompareFetcher")
    @patch("quant_lab.core.data.aggregator.TopHoldersFetcher")
    @patch("quant_lab.core.data.aggregator.ThemeSentimentFetcher")
    @patch("quant_lab.core.data.aggregator.MarketEnvFetcher")
    @patch("quant_lab.core.data.aggregator.LockupFetcher")
    @patch("quant_lab.core.data.aggregator.ChipFetcher")
    @patch("quant_lab.core.data.aggregator.InstitutionFetcher")
    @patch("quant_lab.core.data.aggregator.CompetitorFetcher")
    @patch("quant_lab.core.data.aggregator.SmartMoneyFetcher")
    @patch("quant_lab.core.data.aggregator.NewsFetcher")
    @patch("quant_lab.core.data.aggregator.SupportResistanceFetcher")
    def test_classmethod_delegates(
        self, mock_sr_cls: MagicMock, mock_news_cls: MagicMock,
        mock_sm_cls: MagicMock, mock_comp_cls: MagicMock,
        mock_inst_cls: MagicMock, mock_chip_cls: MagicMock,
        mock_lock_cls: MagicMock, mock_me_cls: MagicMock,
        mock_ts_cls: MagicMock, mock_th_cls: MagicMock,
        mock_ic_cls: MagicMock, mock_qt_cls: MagicMock,
        mock_rk_cls: MagicMock, mock_con_cls: MagicMock,
        mock_macro_cls: MagicMock, mock_sent_cls: MagicMock,
        mock_perf_cls: MagicMock, mock_val_cls: MagicMock,
    ) -> None:
        for cls in (
            mock_val_cls, mock_perf_cls, mock_sent_cls, mock_macro_cls,
            mock_con_cls, mock_rk_cls, mock_qt_cls, mock_ic_cls,
            mock_th_cls, mock_ts_cls, mock_me_cls, mock_lock_cls,
            mock_chip_cls, mock_inst_cls, mock_comp_cls, mock_sm_cls,
            mock_news_cls, mock_sr_cls,
        ):
            cls.return_value = make_mock_fetcher({})

        result = StockAggregator.aggregate("000001", "平安银行")
        assert result["code"] == "000001"
        assert result["name"] == "平安银行"
