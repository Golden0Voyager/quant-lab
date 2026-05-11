"""Smart money (northbound + margin trading) dimension fetcher."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.sources._utils import no_proxy, safe_float

logger = logging.getLogger(__name__)


class SmartMoneyFetcher:
    """Fetch northbound and margin-trading data."""

    name = "smart_money"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str, **kwargs: Any) -> dict[str, Any]:
        """Return smart money data for *symbol*."""
        data: dict[str, Any] = {
            "smart_money_data_date": datetime.now().strftime("%Y-%m-%d")
        }

        # 1. Northbound (沪深港通)
        try:
            with no_proxy():
                hsgt_df = ak.stock_hsgt_individual_em(symbol=symbol)
            if hsgt_df is not None and not hsgt_df.empty:
                recent = hsgt_df.tail(10).copy()

                hold_col = None
                for col in recent.columns:
                    if "持股数量" in str(col) or "持股" in str(col):
                        hold_col = col
                        break

                if hold_col is not None and len(recent) >= 2:
                    diffs = recent[hold_col].diff().dropna()
                    consecutive = 0
                    for d in reversed(diffs.values):
                        d_val = safe_float(d)
                        if d_val is None:
                            break
                        if d_val > 0:
                            if consecutive >= 0:
                                consecutive += 1
                            else:
                                break
                        elif d_val < 0:
                            if consecutive <= 0:
                                consecutive -= 1
                            else:
                                break
                        else:
                            break
                    data["north_consecutive_days"] = consecutive

                    if len(recent) >= 4:
                        val_now = safe_float(recent[hold_col].iloc[-1])
                        val_3d = safe_float(recent[hold_col].iloc[-4])
                        if val_now and val_3d and val_3d > 0:
                            data["north_change_pct_3d"] = round(
                                (val_now / val_3d - 1) * 100, 2
                            )

                for col in recent.columns:
                    if "占" in str(col) and (
                        "流通" in str(col) or "比" in str(col)
                    ):
                        val = safe_float(recent[col].iloc[-1])
                        if val is not None:
                            data["north_holding_ratio"] = round(val, 2)
                            break
        except Exception:  # noqa: BLE001
            pass

        # 2. Margin trading
        try:
            margin_df = None
            if symbol.startswith("6"):
                try:
                    with no_proxy():
                        margin_df = ak.stock_margin_detail_sse(symbol=symbol)
                except Exception:  # noqa: BLE001
                    pass
            else:
                try:
                    with no_proxy():
                        margin_df = ak.stock_margin_detail_szse(symbol=symbol)
                except Exception:  # noqa: BLE001
                    pass

            if margin_df is not None and not margin_df.empty:
                recent_m = margin_df.tail(5).copy()

                for col in recent_m.columns:
                    if "融资余额" in str(col):
                        val = safe_float(recent_m[col].iloc[-1])
                        if val is not None:
                            data["margin_balance"] = round(val / 1e8, 2)
                            if len(recent_m) >= 3:
                                val_prev = safe_float(recent_m[col].iloc[-3])
                                if val_prev:
                                    diff_pct = (val / val_prev - 1) * 100
                                    if diff_pct > 1:
                                        data["margin_balance_trend"] = "增"
                                    elif diff_pct < -1:
                                        data["margin_balance_trend"] = "减"
                                    else:
                                        data["margin_balance_trend"] = "平"
                        break

                rq_col = None
                rz_col = None
                for col in recent_m.columns:
                    if "融券余额" in str(col) and "融券余量" not in str(col):
                        rq_col = col
                    if "融资余额" in str(col):
                        rz_col = col
                if rq_col and rz_col:
                    rq_val = safe_float(recent_m[rq_col].iloc[-1])
                    rz_val = safe_float(recent_m[rz_col].iloc[-1])
                    if rq_val and rz_val and rz_val > 0:
                        ratio = rq_val / (rq_val + rz_val) * 100
                        data["short_selling_ratio"] = round(ratio, 2)
                        if ratio > 20:
                            data["short_selling_level"] = "高位"
                        elif ratio < 5:
                            data["short_selling_level"] = "低位"
                        else:
                            data["short_selling_level"] = "正常"
        except Exception:  # noqa: BLE001
            pass

        parts: list[str] = []
        nc = data.get("north_consecutive_days")
        if nc is not None:
            if nc > 0:
                pct_str = (
                    f" ({data['north_change_pct_3d']:+.2f}%)"
                    if data.get("north_change_pct_3d") is not None
                    else ""
                )
                parts.append(f"北向连续{nc}日加仓{pct_str}")
            elif nc < 0:
                pct_str = (
                    f" ({data['north_change_pct_3d']:+.2f}%)"
                    if data.get("north_change_pct_3d") is not None
                    else ""
                )
                parts.append(f"北向连续{abs(nc)}日减仓{pct_str}")
            else:
                parts.append("北向持仓持平")

        sl = data.get("short_selling_level")
        sr = data.get("short_selling_ratio")
        if sl:
            parts.append(
                f"融券余额：{sl}({sr:.1f}%)" if sr else f"融券余额：{sl}"
            )

        mb = data.get("margin_balance")
        mt = data.get("margin_balance_trend")
        if mb is not None:
            parts.append(f"融资余额{mb:.1f}亿({mt or '？'})")

        data["smart_money_summary"] = (
            " | ".join(parts) if parts else "暂无聪明钱数据"
        )

        return data
