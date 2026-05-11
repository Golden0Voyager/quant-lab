"""News / sentiment dimension fetcher."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from quant_lab.core.data.dimensions.base import safe_fetch

logger = logging.getLogger(__name__)

try:
    from ddgs import DDGS  # type: ignore[import-untyped]
except ImportError:
    DDGS = None  # type: ignore[misc,assignment]


class NewsFetcher:
    """Fetch news and announcements for a stock.

    TODO: migrate analyst_base dependencies to dedicated source modules.
    """

    name = "news"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str, **kwargs: Any) -> dict[str, Any]:
        """Return news data for *symbol*."""
        data: dict[str, Any] = {}

        try:
            from analyst_base import (
                format_telegraph_for_report,
                get_eastmoney_announcements,
                match_relevant_telegraphs,
            )
        except ImportError:
            data["news_summary"] = None
            data["news_source"] = None
            data["news_data_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            return data

        news_list: list[str] = []
        news_source = "无"
        cls_telegraphs: list[Any] = []

        # Engine 0: Eastmoney announcements
        try:
            announcements = get_eastmoney_announcements(symbol, limit=15)
            if announcements:
                news_list = announcements
                news_source = "东财公告"
        except Exception:  # noqa: BLE001
            pass

        # Engine 1: CLS telegraphs
        try:
            cls_telegraphs = match_relevant_telegraphs(
                stock_code=symbol,
                stock_name=stock_name,
                hours=24,
                min_score=5,
                max_items=8,
            )
            if cls_telegraphs:
                if news_list:
                    news_source = "东财公告+财联社电报"
                else:
                    cls_formatted = format_telegraph_for_report(cls_telegraphs)
                    news_list = [cls_formatted]
                    news_source = "财联社电报"
        except Exception:  # noqa: BLE001
            pass

        # Engine 2: DuckDuckGo fallback
        if not news_list and DDGS is not None:
            try:
                with DDGS() as ddgs:
                    query = f"{stock_name} 股票"
                    results = list(
                        ddgs.text(
                            query, region="cn-zh", timelimit="w", max_results=15
                        )
                    )
                    for r in results:
                        title = r.get("title", "")
                        body = r.get("body", "")
                        if (
                            stock_name in (title + " " + body)
                            or symbol in (title + " " + body)
                        ):
                            news_list.append(title)
                            if len(news_list) >= 15:
                                break
                    if news_list:
                        news_source = "全网搜索"
            except Exception:  # noqa: BLE001
                pass

        # Assemble output
        if news_list or cls_telegraphs:
            all_news: list[str] = []
            for item in news_list:
                all_news.append(f"- {item}")
            if cls_telegraphs and news_source == "东财公告+财联社电报":
                all_news.append("\n【财联社行业/政策快讯】")
                cls_formatted = format_telegraph_for_report(cls_telegraphs)
                all_news.append(cls_formatted)

            total_count = len(news_list) + len(cls_telegraphs)
            data["news_summary"] = f"[{news_source}] {total_count}条"
            data["news_context"] = "\n".join(all_news)
            data["news_source"] = news_source
        else:
            data["news_summary"] = "静默"
            data["news_context"] = "当前无任何新闻或资讯"
            data["news_source"] = "无"

        data["news_data_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        return data
