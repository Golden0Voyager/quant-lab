"""Tests for MarketEnvFetcher."""

from __future__ import annotations

import os
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
        self._orig_xq_token = os.environ.get("XUEQIU_TOKEN")

    def teardown_method(self) -> None:
        for key, val in self._orig_caches.items():
            getattr(market_env, key).update(val)
        if self._orig_xq_token is None:
            os.environ.pop("XUEQIU_TOKEN", None)
        else:
            os.environ["XUEQIU_TOKEN"] = self._orig_xq_token

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

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_fmt_volume_large(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = None
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["15000000000000"]}
        )
        os.environ["XUEQIU_TOKEN"] = "test_token"
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
        assert "万亿" in result.get("market_total_volume", "")

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_volume_signal_shrink(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = None
        sh_vol = [200] * 20 + [10]
        idx_df = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": sh_vol}
        )
        mock_ak.stock_zh_index_daily.return_value = idx_df

        mock_ak.stock_zh_index_daily_em.side_effect = Exception("EM fail")
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
        assert result.get("market_volume_signal") == "缩量"

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_breadth_decline(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
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
                "value": ["500", "2000", "100", "5", "50"],
            }
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame({"x": range(5)})
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame({"x": range(50)})
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame()
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame()
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert result["market_breadth_signal"] == "普跌"
        assert result["market_limit_up"] == 5
        assert result["market_limit_down"] == 50

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_breadth_extreme_up(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
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
                "value": ["3000", "0", "100", "80", "0"],
            }
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame({"x": range(80)})
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame()
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame()
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert result["market_breadth_signal"] == "普涨"
        assert result["market_advance_decline_ratio"] == "极端普涨"

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_shibor_tight(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = None
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {"item": [], "value": []}
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame()
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame()
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame(
            {
                "O/N-定价": [2.5],
                "1W-定价": [3.0],
                "O/N-涨跌幅": [10.0],
                "1W-涨跌幅": [8.0],
            }
        )
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert result["monetary_signal"] == "收紧"

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_shibor_loose(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = None
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {"item": [], "value": []}
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame()
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame()
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame(
            {
                "O/N-定价": [0.5],
                "1W-定价": [0.8],
                "O/N-涨跌幅": [-10.0],
                "1W-涨跌幅": [-8.0],
            }
        )
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert result["monetary_signal"] == "宽松"

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_sentiment_bearish(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = None
        idx_df = pd.DataFrame(
            {"close": list(range(3100, 3079, -1)), "volume": list(range(22, 1, -1))}
        )
        mock_ak.stock_zh_index_daily.return_value = idx_df
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {
                "item": ["上涨", "下跌", "平盘", "涨停", "跌停"],
                "value": ["500", "2000", "100", "5", "50"],
            }
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame({"x": range(5)})
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame({"x": range(50)})
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame(
            {"资金方向": ["南向"], "成交净买额": [60.0]}
        )
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame()
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert result["market_sentiment"] == "偏冷"
        assert result["market_sentiment_score"] <= -2

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_cross_border_south_negative(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = None
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {"item": [], "value": []}
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame()
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame(
            {"资金方向": ["南向"], "成交净买额": [-30.0]}
        )
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame()
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "净流出港股" in result.get("south_flow_direction", "")

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_cross_border_no_south_column(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = None
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {"item": [], "value": []}
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame()
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame(
            {"some_col": [1, 2]}
        )
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame()
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_ths_board_fallback(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = "银行"
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {"item": [], "value": []}
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame()
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame()
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame()
        mock_ak.stock_board_industry_name_em.side_effect = Exception("fail")
        mock_ak.stock_board_industry_summary_ths.return_value = pd.DataFrame(
            {
                "板块": ["银行", "白酒"],
                "涨跌幅": [1.5, -0.5],
                "净流入": [1e9, -5e8],
                "总成交额": [2e10, 1e10],
            }
        )

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "_error" not in result
        assert result.get("sector_rank") == "1/2"

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_sector_keyword_fallback(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = "新能源汽车"
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {"item": [], "value": []}
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame()
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame()
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame()
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame(
            {
                "板块名称": ["汽车零部件", "锂电池"],
                "涨跌幅": [2.0, 3.0],
                "主力净流入": [1e9, 2e9],
            }
        )

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_summary_volume_vs_no_total(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = None
        idx_df = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(100, 121))}
        )
        mock_ak.stock_zh_index_daily.side_effect = [
            idx_df,
            pd.DataFrame({"close": [4000] * 6, "volume": list(range(50, 56))}),
            pd.DataFrame({"close": [2000] * 6}),
            pd.DataFrame({"close": [1000] * 6}),
            pd.DataFrame({"close": [3500] * 6}),
            pd.DataFrame(
                {"close": [11000] * 6, "volume": list(range(80, 86))}
            ),
        ]
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
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

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_shibor_alternative_column_names(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = None
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {"item": [], "value": []}
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame()
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame()
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame(
            {
                "O/N_定价": [1.5],
                "1W_定价": [1.8],
                "O/N_涨跌幅": [2.0],
                "1W_涨跌幅": [1.0],
            }
        )
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert result.get("shibor_overnight") == "1.500%"
        assert result.get("shibor_1w") == "1.800%"

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_sector_extremes(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = "银行"
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {"item": [], "value": []}
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame()
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame()
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame()
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame(
            {
                "板块名称": ["A", "B", "C", "D", "E"],
                "涨跌幅": [5.0, 3.0, 1.0, -1.0, -3.0],
                "主力净流入": [1e9, 2e9, 0, -1e9, -2e9],
            }
        )

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "hot_sectors_top3" in result
        assert "cold_sectors_top3" in result
        assert len(result["hot_sectors_top3"]) == 3

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_volume_em_exception(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = None
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_zh_index_daily_em.side_effect = Exception("EM fail")
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

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_breadth_exception(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = None
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
        mock_ak.stock_market_activity_legu.side_effect = Exception("breadth fail")
        mock_ak.stock_zt_pool_em.side_effect = Exception("zt fail")
        mock_ak.stock_zt_pool_dtgc_em.side_effect = Exception("dt fail")
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame()
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame()
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_cross_border_exception(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = None
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {"item": [], "value": []}
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame()
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()
        mock_ak.stock_hsgt_fund_flow_summary_em.side_effect = Exception("flow fail")
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame()
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_shibor_exception(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = None
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {"item": [], "value": []}
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame()
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame()
        mock_ak.macro_china_shibor_all.side_effect = Exception("shibor fail")
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.market_env.ak")
    @patch("quant_lab.core.data.dimensions.market_env._get_industry")
    def test_board_exception_ths_also_fails(self, mock_industry: MagicMock, mock_ak: MagicMock) -> None:
        mock_industry.return_value = "银行"
        mock_ak.stock_zh_index_daily.return_value = pd.DataFrame(
            {"close": list(range(3000, 3021)), "volume": list(range(1, 22))}
        )
        mock_ak.stock_individual_spot_xq.return_value = pd.DataFrame(
            {"item": ["成交额"], "value": ["50000000000"]}
        )
        mock_ak.stock_market_activity_legu.return_value = pd.DataFrame(
            {"item": [], "value": []}
        )
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame()
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()
        mock_ak.stock_hsgt_fund_flow_summary_em.return_value = pd.DataFrame()
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame()
        mock_ak.stock_board_industry_name_em.side_effect = Exception("em board fail")
        mock_ak.stock_board_industry_summary_ths.side_effect = Exception("ths board fail")

        fetcher = MarketEnvFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "_error" not in result
