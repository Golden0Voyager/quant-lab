"""Tests for ThemeSentimentFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.theme_sentiment import (
    ThemeSentimentFetcher,
    _concept_board_cache,
)


class TestThemeSentimentFetcher:
    def setup_method(self) -> None:
        _concept_board_cache["data"] = None
        _concept_board_cache["time"] = None

    @patch("quant_lab.core.data.dimensions.theme_sentiment.ak")
    def test_happy_path(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_comment_detail_zlkp_jgcyd_em.return_value = pd.DataFrame(
            {
                "日期": ["2025-01-01"],
                "机构参与度": [4.0],
            }
        )
        mock_ak.stock_board_concept_name_em.return_value = pd.DataFrame(
            {
                "板块名称": ["人工智能", "芯片", "新能源"],
                "涨跌幅": [5.5, 3.2, 1.8],
            }
        )

        fetcher = ThemeSentimentFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["stock_sentiment"] == "偏多"
        assert result["hot_concepts"] == ["人工智能", "芯片", "新能源"]
        assert result["hot_concepts_change"] == ["+5.50%", "+3.20%", "+1.80%"]
        assert "情绪：偏多" in result["theme_sentiment_summary"]

    @patch("quant_lab.core.data.dimensions.theme_sentiment.ak")
    def test_bearish_sentiment(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_comment_detail_zlkp_jgcyd_em.return_value = pd.DataFrame(
            {
                "日期": ["2025-01-01"],
                "机构参与度": [1.0],
            }
        )
        mock_ak.stock_board_concept_name_em.return_value = pd.DataFrame()

        fetcher = ThemeSentimentFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["stock_sentiment"] == "偏空"

    @patch("quant_lab.core.data.dimensions.theme_sentiment.ak")
    def test_empty_dataframe(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_comment_detail_zlkp_jgcyd_em.return_value = pd.DataFrame()
        mock_ak.stock_board_concept_name_em.return_value = pd.DataFrame()

        fetcher = ThemeSentimentFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["theme_sentiment_summary"] == "暂无情绪题材数据"

    @patch("quant_lab.core.data.dimensions.theme_sentiment.ak")
    def test_exception(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_comment_detail_zlkp_jgcyd_em.side_effect = Exception("API down")

        fetcher = ThemeSentimentFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" in result
        assert result["_dimension"] == "theme_sentiment"
