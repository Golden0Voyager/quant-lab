"""Theme sentiment dimension fetcher."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.sources._utils import no_proxy, safe_float

logger = logging.getLogger(__name__)

_concept_board_cache: dict[str, Any] = {"data": None, "time": None}


class ThemeSentimentFetcher:
    """Fetch theme sentiment and hot concept boards."""

    name = "theme_sentiment"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str, **kwargs: Any) -> dict[str, Any]:
        """Return theme sentiment and hot concept data."""
        data: dict[str, Any] = {
            "theme_sentiment_data_date": datetime.now().strftime("%Y-%m-%d")
        }

        # 1. 机构参与度 / 情绪
        with no_proxy():
            cyd_df = ak.stock_comment_detail_zlkp_jgcyd_em(symbol=symbol)
        if cyd_df is not None and not cyd_df.empty:
            latest = cyd_df.iloc[-1]
            score: float | None = None
            for col in cyd_df.columns:
                if "参与度" in str(col) or "机构" in str(col):
                    score = safe_float(latest[col])
                    if score is not None:
                        break
            if score is None and len(cyd_df.columns) >= 2:
                score = safe_float(latest.iloc[1])

            if score is not None:
                if score > 3.5:
                    data["stock_sentiment"] = "偏多"
                elif score < 1.5:
                    data["stock_sentiment"] = "偏空"
                else:
                    data["stock_sentiment"] = "中性"

        # 2. 热门概念板块（带 5 分钟缓存）
        global _concept_board_cache
        now = datetime.now()
        if (
            _concept_board_cache["data"] is None
            or _concept_board_cache["time"] is None
            or (now - _concept_board_cache["time"]).seconds > 300
        ):
            with no_proxy():
                concept_df = ak.stock_board_concept_name_em()
            _concept_board_cache["data"] = concept_df
            _concept_board_cache["time"] = now
        else:
            concept_df = _concept_board_cache["data"]

        if concept_df is not None and not concept_df.empty:
            change_col = None
            for col in concept_df.columns:
                if "涨跌幅" in str(col) or "涨幅" in str(col):
                    change_col = col
                    break

            name_col = None
            for col in concept_df.columns:
                if "板块名称" in str(col) or "名称" in str(col):
                    name_col = col
                    break

            if change_col and name_col:
                sorted_df = concept_df.sort_values(by=change_col, ascending=False)
                top3 = sorted_df.head(3)
                data["hot_concepts"] = top3[name_col].tolist()

                changes: list[str] = []
                for _, row in top3.iterrows():
                    chg = safe_float(row[change_col])
                    if chg is not None:
                        changes.append(f"{chg:+.2f}%")
                    else:
                        changes.append("N/A")
                data["hot_concepts_change"] = changes

        parts: list[str] = []
        if data.get("stock_sentiment"):
            parts.append(f"情绪：{data['stock_sentiment']}")
        if data.get("hot_concepts"):
            parts.append(f"热门概念：{'、'.join(data['hot_concepts'][:3])}")

        data["theme_sentiment_summary"] = (
            " | ".join(parts) if parts else "暂无情绪题材数据"
        )

        return data
