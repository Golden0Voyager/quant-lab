"""Macro / global indicator dimension fetcher."""

from __future__ import annotations

import logging
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.sources._utils import no_proxy

logger = logging.getLogger(__name__)


class MacroETFFetcher:
    """Fetch global macro indicators (USDCNH, yields, indices, commodities)."""

    name = "macro_etf"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str, **kwargs: Any) -> dict[str, Any]:
        """Return macro data.  ETF premium logic is intentionally omitted in v2
        (moved to a future fund-specific dimension).
        """
        data: dict[str, Any] = {}

        # 1. 离岸人民币汇率
        with no_proxy():
            fx_df = ak.fx_spot_quote()
        if fx_df is not None and not fx_df.empty:
            usdcnh = fx_df[fx_df["货币对"] == "USDCNH"]
            if not usdcnh.empty:
                data["usdcnh_rate"] = f"{float(usdcnh.iloc[0]['买价']):.4f}"
            else:
                data["usdcnh_rate"] = "N/A"
        else:
            data["usdcnh_rate"] = "N/A"

        # 2. OpenBB 全球宏观
        try:
            from quant_lab.analyst_openbb import OpenBBAnalyst  # type: ignore[import-not-found]

            openbb = OpenBBAnalyst(cache_expire_minutes=30)
            global_macro = openbb.fetch_global_macro()
            if global_macro:
                for key in [
                    "us10y_yield",
                    "dxy_index",
                    "sp500",
                    "nasdaq",
                    "dowjones",
                    "usdcny",
                    "hsi_index",
                    "nikkei225",
                    "vix_index",
                    "wti_crude",
                    "gold",
                    "silver",
                    "btc",
                    "us10y_yield_chg",
                    "dxy_index_chg",
                    "sp500_chg",
                    "nasdaq_chg",
                    "dowjones_chg",
                    "usdcny_chg",
                    "hsi_index_chg",
                    "nikkei225_chg",
                    "vix_index_chg",
                    "wti_crude_chg",
                    "gold_chg",
                    "silver_chg",
                    "btc_chg",
                    "vix_level",
                ]:
                    val = global_macro.get(key)
                    if val is not None:
                        data[key] = str(val) if val != "N/A" else "N/A"
                data["global_macro_update"] = global_macro.get("update_time", "N/A")

                def _fmt(label: str, key: str, suffix: str = "", chg_key: str = "") -> str | None:
                    val = global_macro.get(key)
                    if val is None or val == "N/A":
                        return None
                    chg = global_macro.get(chg_key) if chg_key else None
                    chg_str = f"({float(chg):+.2f}%)" if chg and chg != "N/A" else ""
                    return f"{label}: {val}{suffix}{chg_str}"

                parts = [
                    _fmt("美债10Y", "us10y_yield", "%", "us10y_yield_chg"),
                    _fmt("美元指数", "dxy_index", "", "dxy_index_chg"),
                    _fmt("USD/CNY", "usdcny", "", "usdcny_chg"),
                    _fmt("标普500", "sp500", "", "sp500_chg"),
                    _fmt("纳指", "nasdaq", "", "nasdaq_chg"),
                    _fmt(
                        "VIX",
                        "vix_index",
                        f"({global_macro.get('vix_level', '')})",
                        "vix_index_chg",
                    ),
                    _fmt("恒指", "hsi_index", "", "hsi_index_chg"),
                    _fmt("日经225", "nikkei225", "", "nikkei225_chg"),
                    _fmt("WTI原油", "wti_crude", "$", "wti_crude_chg"),
                    _fmt("黄金", "gold", "$", "gold_chg"),
                    _fmt("白银", "silver", "$", "silver_chg"),
                    _fmt("BTC", "btc", "$", "btc_chg"),
                ]
                data["global_macro_summary"] = (
                    " | ".join(p for p in parts if p) or "N/A"
                )
        except Exception:
            data["global_macro_summary"] = "N/A"

        return data
