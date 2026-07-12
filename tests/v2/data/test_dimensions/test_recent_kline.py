from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]
import pytest

from quant_lab.core.data.dimensions.recent_kline import RecentKlineFetcher


@pytest.fixture(autouse=True)
def mock_db_not_exists() -> Generator[None, None, None]:
    with patch("quant_lab.core.data.dimensions.recent_kline.os.path.exists", return_value=False):
        yield


class TestRecentKlineFetcher:
    @patch("quant_lab.core.data.dimensions.recent_kline.ak")
    def test_happy_path(self, mock_ak: MagicMock) -> None:
        """20 days of K-line data produces recent_20d_data + BOLL."""
        dates = pd.date_range("2026-04-01", periods=25, freq="D").strftime("%Y-%m-%d")
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame(
            {
                "日期": dates,
                "开盘": [10.0] * 25,
                "收盘": list(range(10, 35)),
                "最高": [11.0] * 25,
                "最低": [9.0] * 25,
                "涨跌幅": [1.0] * 25,
                "成交量": [1000] * 25,
                "成交额": [50000] * 25,
                "换手率": [1.5] * 25,
            }
        )

        fetcher = RecentKlineFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert len(result["recent_20d_data"]) == 20
        assert result["recent_20d_data"][0]["date"] == "2026-04-06"
        assert "boll_mid" in result
        assert "boll_upper" in result
        assert "boll_lower" in result
        assert "boll_width" in result
        assert "boll_position" in result
        assert "boll_status" in result

    @patch("quant_lab.core.data.dimensions.recent_kline.ak")
    def test_sina_fallback(self, mock_ak: MagicMock) -> None:
        """Eastmoney fails, Sina provides data."""
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame()
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
        assert len(result["recent_20d_data"]) == 20

    @patch("quant_lab.core.data.dimensions.recent_kline.ak")
    def test_all_sources_fail(self, mock_ak: MagicMock) -> None:
        """All K-line sources return empty → safe_fetch wraps as error dict."""
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame()
        mock_ak.stock_zh_a_daily.return_value = pd.DataFrame()
        mock_ak.stock_zh_a_hist_tx.return_value = pd.DataFrame()

        fetcher = RecentKlineFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" in result
        assert result["_dimension"] == "recent_kline"

    @patch("quant_lab.core.data.dimensions.recent_kline.ak")
    def test_boll_position_calculation(self, mock_ak: MagicMock) -> None:
        """BOLL position and status are calculated correctly."""
        dates = pd.date_range("2026-04-01", periods=25, freq="D").strftime("%Y-%m-%d")
        closes = [10.0] * 24 + [15.0]
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame(
            {
                "日期": dates,
                "开盘": [10.0] * 25,
                "收盘": closes,
                "最高": [11.0] * 25,
                "最低": [9.0] * 25,
                "涨跌幅": [0.0] * 25,
                "成交量": [1000] * 25,
                "成交额": [50000] * 25,
                "换手率": [1.5] * 25,
            }
        )

        fetcher = RecentKlineFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["boll_position"] > 0
        assert isinstance(result["boll_status"], str)

    @patch("quant_lab.core.data.dimensions.recent_kline.ak")
    @patch("quant_lab.core.data.dimensions.recent_kline.sqlite3")
    @patch("quant_lab.core.data.dimensions.recent_kline.os.path.exists")
    @patch("quant_lab.core.data.dimensions.recent_kline.get_settings")
    def test_db_loading_happy_path(
        self,
        mock_settings: MagicMock,
        mock_exists: MagicMock,
        mock_sqlite3: MagicMock,
        mock_ak: MagicMock,
    ) -> None:
        """K-line successfully loaded from local database, AkShare not called."""
        mock_settings.return_value.resolved_core_db_path = "/fake/quant_core.db"
        mock_exists.return_value = True

        dates = pd.date_range("2026-04-01", periods=25, freq="D").strftime("%Y-%m-%d")
        mock_conn = MagicMock()
        mock_sqlite3.connect.return_value = mock_conn

        # Mock pd.read_sql_query to return a valid DataFrame
        with patch("pandas.read_sql_query") as mock_read_sql:
            mock_read_sql.return_value = pd.DataFrame(
                {
                    "日期": dates,
                    "开盘": [10.0] * 25,
                    "收盘": list(range(10, 35)),
                    "最高": [11.0] * 25,
                    "最低": [9.0] * 25,
                    "涨跌幅": [1.0] * 25,
                    "成交量": [1000] * 25,
                    "成交额": [50000] * 25,
                    "换手率": [1.5] * 25,
                    "振幅": [2.0] * 25,
                }
            )

            fetcher = RecentKlineFetcher()
            result = fetcher.fetch("000001", "平安银行")

            assert "_error" not in result
            assert len(result["recent_20d_data"]) == 20
            # Akshare should NOT have been called since DB was successful
            mock_ak.stock_zh_a_hist.assert_not_called()
            mock_sqlite3.connect.assert_called_once_with("/fake/quant_core.db")

    @patch("quant_lab.core.data.dimensions.recent_kline.ak")
    @patch("quant_lab.core.data.dimensions.recent_kline.sqlite3")
    @patch("quant_lab.core.data.dimensions.recent_kline.os.path.exists")
    @patch("quant_lab.core.data.dimensions.recent_kline.get_settings")
    def test_db_loading_fallback(
        self,
        mock_settings: MagicMock,
        mock_exists: MagicMock,
        mock_sqlite3: MagicMock,
        mock_ak: MagicMock,
    ) -> None:
        """Local database fails or has no data → falls back to AkShare."""
        mock_settings.return_value.resolved_core_db_path = "/fake/quant_core.db"
        mock_exists.return_value = True

        mock_sqlite3.connect.side_effect = Exception("DB connection error")

        dates = pd.date_range("2026-04-01", periods=25, freq="D").strftime("%Y-%m-%d")
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame(
            {
                "日期": dates,
                "开盘": [10.0] * 25,
                "收盘": list(range(10, 35)),
                "最高": [11.0] * 25,
                "最低": [9.0] * 25,
                "涨跌幅": [1.0] * 25,
                "成交量": [1000] * 25,
                "成交额": [50000] * 25,
                "换手率": [1.5] * 25,
            }
        )

        fetcher = RecentKlineFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert len(result["recent_20d_data"]) == 20
        # Akshare should be called as fallback
        mock_ak.stock_zh_a_hist.assert_called_once()

