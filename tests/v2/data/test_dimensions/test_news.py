"""Tests for NewsFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quant_lab.core.data.dimensions.news import NewsFetcher


class TestNewsFetcher:
    @patch("analyst_base.get_eastmoney_announcements")
    def test_happy_path(self, mock_announce: MagicMock) -> None:
        mock_announce.return_value = ["公告1", "公告2"]

        fetcher = NewsFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["news_summary"] == "[东财公告] 2条"
        assert "公告1" in result["news_context"]
        assert result["news_source"] == "东财公告"

    @patch("analyst_base.get_eastmoney_announcements")
    @patch("analyst_base.match_relevant_telegraphs")
    @patch("analyst_base.format_telegraph_for_report")
    def test_cls_combined(
        self,
        mock_format: MagicMock,
        mock_cls: MagicMock,
        mock_announce: MagicMock,
    ) -> None:
        mock_announce.return_value = ["公告1"]
        mock_cls.return_value = [{"title": "电报1"}]
        mock_format.return_value = "格式化电报内容"

        fetcher = NewsFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["news_source"] == "东财公告+财联社电报"
        assert "财联社" in result["news_context"]

    @patch("analyst_base.get_eastmoney_announcements")
    @patch("analyst_base.match_relevant_telegraphs")
    @patch("quant_lab.core.data.dimensions.news.DDGS")
    def test_ddgs_fallback(
        self,
        mock_ddgs_cls: MagicMock,
        mock_cls: MagicMock,
        mock_announce: MagicMock,
    ) -> None:
        mock_announce.return_value = []
        mock_cls.return_value = []

        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = [
            {"title": "平安银行新闻", "body": "内容"},
            {"title": "其他新闻", "body": "无关"},
        ]
        mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs

        fetcher = NewsFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["news_source"] == "全网搜索"
        assert "平安银行新闻" in result["news_context"]

    @patch("analyst_base.get_eastmoney_announcements")
    @patch("analyst_base.match_relevant_telegraphs")
    @patch("quant_lab.core.data.dimensions.news.DDGS")
    def test_all_empty(
        self,
        mock_ddgs_cls: MagicMock,
        mock_cls: MagicMock,
        mock_announce: MagicMock,
    ) -> None:
        mock_announce.return_value = []
        mock_cls.return_value = []

        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = []
        mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs

        fetcher = NewsFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["news_summary"] == "静默"
        assert result["news_source"] == "无"
