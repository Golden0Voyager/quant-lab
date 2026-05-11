"""Tests for core/data/aggregator.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quant_lab.core.data.aggregator import aggregate


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
        def make_mock(payload: dict) -> MagicMock:
            m = MagicMock()
            m.fetch.return_value = payload
            return m

        mock_val_cls.return_value = make_mock({"pe_ttm_raw": 15.0})
        mock_perf_cls.return_value = make_mock({"revenue_ttm_raw": 100.0, "market_cap": 500.0})
        mock_sent_cls.return_value = make_mock({"sentiment": "中性"})
        mock_macro_cls.return_value = make_mock({"usdcnh_rate": 7.2})
        mock_con_cls.return_value = make_mock({"eps_growth_rate_raw": 0.2})
        mock_rk_cls.return_value = make_mock({"current_price": 50.0, "ma20": 48.0})
        mock_qt_cls.return_value = make_mock({"qt_signal": "上升"})
        mock_ic_cls.return_value = make_mock({"peer_count": 10})
        mock_th_cls.return_value = make_mock({"holder_count": 5})
        mock_ts_cls.return_value = make_mock({"stock_sentiment": "偏多"})
        mock_me_cls.return_value = make_mock({"market_sentiment": "偏暖"})
        mock_lock_cls.return_value = make_mock({"lockup_risk_level": "低风险"})
        mock_chip_cls.return_value = make_mock({"chip_profit_ratio_raw": 60.0})
        mock_inst_cls.return_value = make_mock({"fund_holding_count": 20})
        mock_comp_cls.return_value = make_mock({"competitors": []})
        mock_sm_cls.return_value = make_mock({"north_consecutive_days": 3})
        mock_news_cls.return_value = make_mock({"news_source": "东财公告"})
        mock_sr_cls.return_value = make_mock({"resistance_price": 55.0})

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
        def make_mock(payload: dict) -> MagicMock:
            m = MagicMock()
            m.fetch.return_value = payload
            return m

        mock_val_cls.return_value = make_mock({"pe_ttm_raw": 10.0})
        mock_perf_cls.return_value = make_mock({})
        mock_sent_cls.return_value = make_mock({})
        mock_macro_cls.return_value = make_mock({})
        mock_con_cls.return_value = make_mock({})
        mock_rk_cls.return_value = make_mock({"current_price": 100.0})
        mock_qt_cls.return_value = make_mock({})
        mock_ic_cls.return_value = make_mock({})
        mock_th_cls.return_value = make_mock({})
        mock_ts_cls.return_value = make_mock({})
        mock_me_cls.return_value = make_mock({})
        mock_lock_cls.return_value = make_mock({})
        mock_chip_cls.return_value = make_mock({})
        mock_inst_cls.return_value = make_mock({})
        mock_comp_cls.return_value = make_mock({})
        mock_sm_cls.return_value = make_mock({})
        mock_news_cls.return_value = make_mock({})

        sr_mock = MagicMock()
        # simulate what @safe_fetch would return on failure
        sr_mock.fetch.return_value = {"_error": "boom", "_dimension": "support_resistance"}
        mock_sr_cls.return_value = sr_mock

        result = aggregate("000001", "平安银行", asset_type="stock")

        assert result["code"] == "000001"
        assert result["current_price"] == 100.0
