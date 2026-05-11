"""Industry comparison dimension fetcher."""

from __future__ import annotations

import logging
from typing import Any, cast

import akshare as ak  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions._utils import get_report_date
from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.sources._utils import no_proxy

logger = logging.getLogger(__name__)

# Module-level caches (mirrors legacy behaviour).
_industry_cache: dict[str, str | None] = {}
_yjbb_cache: dict[str, Any] = {}


def _get_industry(symbol: str) -> str | None:
    """Resolve industry name for *symbol* (with cache)."""
    if symbol in _industry_cache:
        return _industry_cache[symbol]

    report_date = get_report_date()

    # Strategy 1: stock_yjbb_em
    try:
        if report_date not in _yjbb_cache:
            with no_proxy():
                _yjbb_cache[report_date] = ak.stock_yjbb_em(date=report_date)
        yjbb_df = _yjbb_cache[report_date]
        if yjbb_df is not None and not yjbb_df.empty:
            row = yjbb_df[yjbb_df["股票代码"] == symbol]
            if not row.empty:
                industry = cast(str | None, row.iloc[0].get("所处行业"))
                if industry:
                    _industry_cache[symbol] = industry
                    return industry
    except Exception:  # noqa: BLE001
        pass

    # Strategy 2: stock_individual_info_em
    try:
        with no_proxy():
            info_df = ak.stock_individual_info_em(symbol=symbol)
        if info_df is not None and not info_df.empty:
            row = info_df[info_df["item"] == "行业"]
            if not row.empty:
                industry = cast(str | None, row.iloc[0]["value"])
                if industry:
                    _industry_cache[symbol] = industry
                    return industry
    except Exception:  # noqa: BLE001
        pass

    _industry_cache[symbol] = None
    return None


class IndustryCompareFetcher:
    """Fetch industry peer comparison metrics."""

    name = "industry_compare"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str) -> dict[str, Any]:
        """Return industry median and rank for key metrics."""
        data: dict[str, Any] = {}

        industry = _get_industry(symbol)
        if not industry:
            raise ValueError("无法获取行业分类")

        data["industry_name"] = industry

        report_date = get_report_date()
        with no_proxy():
            df = ak.stock_yjbb_em(date=report_date)
        if df is None or df.empty:
            raise ValueError("业绩报表为空")

        peers = df[df["所处行业"] == industry].copy()
        if peers.empty:
            raise ValueError("同行为空")

        data["peer_count"] = len(peers)
        me = peers[peers["股票代码"] == symbol]

        for col, key in [
            ("净资产收益率", "roe"),
            ("销售毛利率", "gross_margin"),
            ("营业总收入-同比增长", "revenue_yoy"),
            ("净利润-同比增长", "profit_yoy"),
        ]:
            valid = pd.to_numeric(peers[col], errors="coerce").dropna()
            if valid.empty:
                continue
            data[f"{key}_median"] = round(valid.median(), 2)

            if not me.empty:
                my_val = pd.to_numeric(me[col].iloc[0], errors="coerce")
                if pd.notna(my_val):
                    rank = int((valid < my_val).sum() + 1)
                    data[f"{key}_rank"] = rank
                    data[f"{key}_total"] = len(valid)
                    data[f"{key}_value"] = round(float(my_val), 2)

        return data
