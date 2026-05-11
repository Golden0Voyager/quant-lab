"""Tests for MarketEnvFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions import market_env
from quant_lab.core.data.dimensions.market_env import MarketEnvFetcher


class TestMarketEnvFetcher:
    def setup_method(self) -> None:
        self._orig_caches = {
            "_index_cache": market_env._index_cache.copy(),
            "_multi_index_cache": market_env._multi_index_cache.copy(),
            "_market_breadth_cache": market_env._market_breadth_cache.copy(),
            "_board_cache": market_env._board_cache.copy(),
            "_shibor_cache": market_env._shibor_cache.copy(),
            "_north_flow_cache": market_env._north_flow_cache.copy(),
        }
        for cache in (
            market_env._index_cache,
            market_env._multi_index_cache,
            market_env._market_breadth_cache,
            market_env._board_cache,
            market_env._shibor_cache,
            market_env._north_flow_cache,
        ):
            cache["data"] = None
            cache["time"] = None

    def teardown_method(self) -> None:
        for key, val in self._orig_caches.items():
            getattr(market_env, key).update(val)

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_happy_path(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = "银行"

        # Index daily
        mock_ak.stock_zh_index_daily.side_effect = [
            pd.DataFrame(
                {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
            ),
            pd.DataFrame({"close": [4000] * 6}),
            pd.DataFrame({"close": [2000] * 6}),
            pd.DataFrame({"close": [1000] * 6}),
            pd.DataFrame({"close": [3500] * 6}),
            pd.DataFrame({"close": [11000] * 6, "volume": list(range(1, 7))}),
        ]

        # Volume: Xueqiu spot
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )

        # Market breadth
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {
                "item": ["上涨", "下跌", "平盘", "涨停", "跌停"],
                "value": ["3000", "1500", "200", "80", "20"],
            }
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame({"x": range(80)})
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame(
            {"x": range(20)}
        )

        # Cross-border
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame(
            {
                "资金方向": ["南向"],
                "成交净买额": [30.5],
            }
        )

        # Shibor
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame(
            {
                "O/N-定价": [1.5],
                "1W-定价": [1.8],
                "O/N-涨跌幅": [2.0],
                "1W-涨跌幅": [1.0],
            }
        )

        # Board
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame(
            {
                "板块名称": ["银行", "白酒", "医药"],
                "涨跌幅": [2.5, 5.0, -1.2],
                "主力净流入": [1e9, 2e9, -5e8],
            }
        )

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["market_sentiment"] == "偏暖"
        assert result["market_up_count"] == 3000
        assert result["market_down_count"] == 1500
        assert result["market_limit_up"] == 80
        assert result["market_limit_down"] == 20
        assert "银行" in result["market_env_summary"]
        assert result["sector_rank"] == "1/3"

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_all_exceptions(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = None
        mock_ak.stock_zh_index_daily.side_effect = Exception("fail")

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert "大盘中性" in result["market_env_summary"]

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_volume_em_fallback(
        self, mock_industry: MagicMock, mock_ak: MagicMock
    ) -> None:
        mock_industry.return_value = None

        # No Xueqiu token → skip strategy 1
        # Strategy 2: Eastmoney daily em
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_zh_index_daily_em.side_effect = [
            pd.DataFrame(
                {
                    "close": [3000] * 10,
                    "amount": [1e10] * 10,
                }
            ),
            pd.DataFrame(
                {
                    "close": [11000] * 10,
                    "amount": [8e9] * 10,
                }
            ),
        ]

        # Minimal mocks for other blocks
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {"item": [], "value": []}
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame()
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame()
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame()
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["market_total_volume"] == "180亿"
        assert "market_volume_vs_5d" in result

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_breadth_from_legu_only(
        self, mock_industry: MagicMock, mock_ak: MagicMock
    ) -> None:
        mock_industry.return_value = None

        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {
                "item": ["上涨", "下跌", "平盘", "涨停", "跌停"],
                "value": ["3000", "1500", "200", "80", "20"],
            }
        )
        # ZT/DT pools fail
        mock_ak.stock_zt_pool_em.side_effect = Exception("fail")
        mock_ak.stock_zt_pool_dtgc_em.side_effect = Exception("fail")
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame()
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame()
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["market_limit_up"] == 80
        assert result["market_limit_down"] == 20
        assert result["market_breadth_signal"] == "普涨"
