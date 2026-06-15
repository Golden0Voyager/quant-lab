"""Extended tests for RecentKlineFetcher — covering uncovered branches."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.recent_kline import RecentKlineFetcher


class TestRecentKlineFetcherV2:
    @patch("quant_lab.core.data.dimensions.recent_kline.ak")
    def test_tencent_fallback(self, mock_ak: MagicMock) -> None:
        """Eastmoney and Sina fail → Tencent fallback (lines 69-83)."""
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame()
        mock_ak.stock_zh_a_daily.side_effect = Exception("sina fail")
        mock_ak.stock_zh_a_hist_tx.return_value = pd.DataFrame(
            {
                "date": pd.date_range("2026-04-01", periods=25, freq="D").strftime(
                    "%Y-%m-%d"
                ),
                "open": [10.0] * 25,
                "close": list(range(10, 35)),
                "high": [11.0] * 25,
                "low": [9.0] * 25,
                "amount": [50000] * 25,
            }
        )

        fetcher = RecentKlineFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert len(result["recent_20d_data"]) == 20

    @patch("quant_lab.core.data.dimensions.recent_kline.ak")
    def test_tencent_no_volume_column(self, mock_ak: MagicMock) -> None:
        """Tencent fallback with no 成交量 column → adds 成交量=0 (line 80)."""
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame()
        mock_ak.stock_zh_a_daily.side_effect = Exception("sina fail")
        mock_ak.stock_zh_a_hist_tx.return_value = pd.DataFrame(
            {
                "date": pd.date_range("2026-04-01", periods=25, freq="D").strftime(
                    "%Y-%m-%d"
                ),
                "open": [10.0] * 25,
                "close": list(range(10, 35)),
                "high": [11.0] * 25,
                "low": [9.0] * 25,
                "amount": [50000] * 25,
            }
        )

        fetcher = RecentKlineFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert len(result["recent_20d_data"]) == 20

    @patch("quant_lab.core.data.dimensions.recent_kline.ak")
    def test_boll_status_below_lower(self, mock_ak: MagicMock) -> None:
        """BOLL status '跌破下轨，极弱' (line 158)."""
        dates = pd.date_range("2026-04-01", periods=25, freq="D").strftime("%Y-%m-%d")
        # Price drops far below BOLL
        closes = [50.0] * 24 + [5.0]
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame(
            {
                "日期": dates,
                "开盘": [50.0] * 25,
                "收盘": closes,
                "最高": [51.0] * 25,
                "最低": [49.0] * 25,
                "涨跌幅": [0.0] * 25,
                "成交量": [1000] * 25,
                "成交额": [50000] * 25,
                "换手率": [1.5] * 25,
            }
        )

        fetcher = RecentKlineFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["boll_position"] < 0
        assert "极弱" in result["boll_status"]

    @patch("quant_lab.core.data.dimensions.recent_kline.ak")
    def test_boll_status_near_lower(self, mock_ak: MagicMock) -> None:
        """BOLL status '接近下轨，偏弱' (line 160)."""
        dates = pd.date_range("2026-04-01", periods=25, freq="D").strftime("%Y-%m-%d")
        # 24 increasing values + low last close → near lower band
        closes = list(range(10, 34)) + [15]
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame(
            {
                "日期": dates,
                "开盘": [10.0] * 25,
                "收盘": closes,
                "最高": [c + 1 for c in closes],
                "最低": [c - 1 for c in closes],
                "涨跌幅": [0.0] * 25,
                "成交量": [1000] * 25,
                "成交额": [50000] * 25,
                "换手率": [1.5] * 25,
            }
        )

        fetcher = RecentKlineFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["boll_position"] < 20
        assert "偏弱" in result["boll_status"]

    @patch("quant_lab.core.data.dimensions.recent_kline.ak")
    def test_boll_status_mid(self, mock_ak: MagicMock) -> None:
        """BOLL status '中轨附近' (line 162)."""
        dates = pd.date_range("2026-04-01", periods=25, freq="D").strftime("%Y-%m-%d")
        # 24 increasing values + mid-range last close → near middle band
        closes = list(range(10, 34)) + [24]
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame(
            {
                "日期": dates,
                "开盘": [10.0] * 25,
                "收盘": closes,
                "最高": [c + 1 for c in closes],
                "最低": [c - 1 for c in closes],
                "涨跌幅": [0.0] * 25,
                "成交量": [1000] * 25,
                "成交额": [50000] * 25,
                "换手率": [1.5] * 25,
            }
        )

        fetcher = RecentKlineFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert 20 <= result["boll_position"] <= 80
        assert "中轨附近" in result["boll_status"]

    @patch("quant_lab.core.data.dimensions.recent_kline.ak")
    def test_eastmoney_exception(self, mock_ak: MagicMock) -> None:
        """Eastmoney exception → sina fallback (line 35-36)."""
        mock_ak.stock_zh_a_hist.side_effect = Exception("EM fail")
        mock_ak.stock_zh_a_daily.return_value = pd.DataFrame(
            {
                "date": pd.date_range("2026-04-01", periods=25, freq="D").strftime(
                    "%Y-%m-%d"
                ),
                "open": [10.0] * 25,
                "close": list(range(10, 35)),
                "high": [11.0] * 25,
                "low": [9.0] * 25,
                "volume": [1000] * 25,
            }
        )

        fetcher = RecentKlineFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.recent_kline.ak")
    def test_sina_exception(self, mock_ak: MagicMock) -> None:
        """Sina exception → tencent fallback (line 56-57)."""
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame()
        mock_ak.stock_zh_a_daily.side_effect = Exception("sina fail")
        mock_ak.stock_zh_a_hist_tx.return_value = pd.DataFrame(
            {
                "date": pd.date_range("2026-04-01", periods=25, freq="D").strftime(
                    "%Y-%m-%d"
                ),
                "open": [10.0] * 25,
                "close": list(range(10, 35)),
                "high": [11.0] * 25,
                "low": [9.0] * 25,
                "amount": [50000] * 25,
            }
        )

        fetcher = RecentKlineFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.recent_kline.ak")
    def test_tencent_exception(self, mock_ak: MagicMock) -> None:
        """Tencent exception → returns None (line 82-83)."""
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame()
        mock_ak.stock_zh_a_daily.return_value = pd.DataFrame()
        mock_ak.stock_zh_a_hist_tx.side_effect = Exception("tencent fail")

        fetcher = RecentKlineFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" in result
