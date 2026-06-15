"""Extended tests for ThemeSentimentFetcher — covering uncovered branches."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.theme_sentiment import (
    ThemeSentimentFetcher,
    _concept_board_cache,
)


class TestThemeSentimentFetcherV2:
    def setup_method(self) -> None:
        _concept_board_cache["data"] = None
        _concept_board_cache["time"] = None

    @patch("quant_lab.core.data.dimensions.theme_sentiment.ak")
    def test_neutral_sentiment(self, mock_ak: MagicMock) -> None:
        """Line 51: score between 1.5 and 3.5 → '中性'."""
        mock_ak.stock_comment_detail_zlkp_jgcyd_em.return_value = pd.DataFrame(
            {"日期": ["2025-01-01"], "机构参与度": [2.5]}
        )
        mock_ak.stock_board_concept_name_em.return_value = pd.DataFrame()
        fetcher = ThemeSentimentFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert result["stock_sentiment"] == "中性"

    @patch("quant_lab.core.data.dimensions.theme_sentiment.ak")
    def test_score_from_second_column(self, mock_ak: MagicMock) -> None:
        """Line 43: score from second column fallback."""
        mock_ak.stock_comment_detail_zlkp_jgcyd_em.return_value = pd.DataFrame(
            {"日期": ["2025-01-01"], "other_col": [4.0]}
        )
        mock_ak.stock_board_concept_name_em.return_value = pd.DataFrame()
        fetcher = ThemeSentimentFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert result["stock_sentiment"] == "偏多"

    @patch("quant_lab.core.data.dimensions.theme_sentiment.ak")
    def test_concept_cache_hit(self, mock_ak: MagicMock) -> None:
        """Line 66: cache hit path."""
        mock_ak.stock_comment_detail_zlkp_jgcyd_em.return_value = pd.DataFrame()
        # Pre-populate cache
        _concept_board_cache["data"] = pd.DataFrame(
            {"板块名称": ["AI"], "涨跌幅": [5.0]}
        )
        _concept_board_cache["time"] = datetime.now()
        fetcher = ThemeSentimentFetcher()
        fetcher.fetch("000001", "平安银行")
        mock_ak.stock_board_concept_name_em.assert_not_called()

    @patch("quant_lab.core.data.dimensions.theme_sentiment.ak")
    def test_na_change_in_hot_concepts(self, mock_ak: MagicMock) -> None:
        """Line 92: N/A change value in hot concepts."""
        mock_ak.stock_comment_detail_zlkp_jgcyd_em.return_value = pd.DataFrame()
        mock_ak.stock_board_concept_name_em.return_value = pd.DataFrame(
            {
                "板块名称": ["AI", "芯片"],
                "涨跌幅": [None, 3.0],
            }
        )
        fetcher = ThemeSentimentFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "N/A" in result["hot_concepts_change"]
