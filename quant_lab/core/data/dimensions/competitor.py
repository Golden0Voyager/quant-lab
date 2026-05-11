"""Competitor comparison dimension fetcher."""

from __future__ import annotations

import logging
from typing import Any

import akshare as ak  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions._utils import get_report_date
from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.dimensions.industry_compare import (
    _get_industry,
    _yjbb_cache,
)
from quant_lab.core.data.sources._utils import no_proxy

logger = logging.getLogger(__name__)


class CompetitorFetcher:
    """Fetch peer competitor comparison data."""

    name = "competitor"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str, **kwargs: Any) -> dict[str, Any]:
        """Return competitor data for *symbol*."""
        data: dict[str, Any] = {}
        report_date = get_report_date()
        data["competitor_data_date"] = (
            f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
        )

        industry = _get_industry(symbol)
        if not industry:
            data["competitor_summary"] = "无法获取行业分类"
            return data

        data["industry_name"] = industry

        try:
            if report_date not in _yjbb_cache:
                with no_proxy():
                    _yjbb_cache[report_date] = ak.stock_yjbb_em(date=report_date)

            yjbb_df = _yjbb_cache[report_date]
            if yjbb_df is not None and not yjbb_df.empty:
                peers = yjbb_df[yjbb_df["所处行业"] == industry].copy()
                if not peers.empty:
                    competitors = peers[peers["股票代码"] != symbol]
                    revenue_col = "营业总收入-营业总收入"
                    if revenue_col in competitors.columns:
                        competitors = competitors.copy()
                        competitors[revenue_col] = pd.to_numeric(
                            competitors[revenue_col], errors="coerce"
                        )
                        competitors = competitors.sort_values(
                            revenue_col, ascending=False
                        )

                    comp_list: list[dict[str, Any]] = []
                    for _, row in competitors.head(5).iterrows():
                        comp: dict[str, Any] = {
                            "code": row.get("股票代码", ""),
                            "name": row.get("股票简称", ""),
                        }
                        roe = row.get("净资产收益率")
                        if pd.notna(roe):
                            comp["roe"] = f"{float(roe):.2f}%"
                        revenue_yoy = row.get("营业总收入-同比增长")
                        if pd.notna(revenue_yoy):
                            comp["revenue_yoy"] = f"{float(revenue_yoy):.2f}%"
                        profit_yoy = row.get("净利润-同比增长")
                        if pd.notna(profit_yoy):
                            comp["profit_yoy"] = f"{float(profit_yoy):.2f}%"
                        gross_margin = row.get("销售毛利率")
                        if pd.notna(gross_margin):
                            comp["gross_margin"] = f"{float(gross_margin):.2f}%"
                        comp_list.append(comp)

                    data["competitors"] = comp_list
                    data["industry_peer_count"] = len(peers)
        except Exception:  # noqa: BLE001
            pass

        if data.get("competitors"):
            names = [c.get("name", "") for c in data["competitors"][:3]]
            data["competitor_summary"] = (
                f"行业: {industry} | 主要对手: {', '.join(names)}"
            )
        else:
            data["competitor_summary"] = (
                f"行业: {industry}" if industry else "暂无竞争对手数据"
            )

        return data
