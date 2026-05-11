"""Institution holding dimension fetcher."""

from __future__ import annotations

import logging
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions._utils import get_report_date
from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.sources._utils import no_proxy, safe_float

logger = logging.getLogger(__name__)


class InstitutionFetcher:
    """Fetch institution / fund holding data with quarter-over-quarter comparison."""

    name = "institution"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str, **kwargs: Any) -> dict[str, Any]:
        """Return institution holding data for *symbol*."""
        quarter = get_report_date()
        if quarter.endswith("0930"):
            quarter_name = f"{quarter[:4]}年三季报"
        elif quarter.endswith("0630"):
            quarter_name = f"{quarter[:4]}年中报"
        elif quarter.endswith("0331"):
            quarter_name = f"{quarter[:4]}年一季报"
        else:
            quarter_name = f"{quarter[:4]}年年报"

        data: dict[str, Any] = {
            "institution_data_date": f"{quarter[:4]}-{quarter[4:6]}-{quarter[6:]} ({quarter_name})"
        }

        institution_fetched = False

        # Strategy 1: Eastmoney fund hold
        with no_proxy():
            fund_df = ak.stock_report_fund_hold(symbol=symbol, date=quarter)
        if fund_df is not None and not fund_df.empty:
            data["fund_holding_count"] = len(fund_df)
            top_funds: list[dict[str, Any]] = []
            for _, row in fund_df.head(5).iterrows():
                fund_info: dict[str, Any] = {}
                for col in fund_df.columns:
                    if "基金" in str(col) and "名" in str(col):
                        fund_info["name"] = str(row[col])[:20]
                    elif "持股" in str(col) and ("数" in str(col) or "量" in str(col)):
                        shares = safe_float(row[col])
                        if shares:
                            fund_info["shares"] = f"{shares / 1e4:.0f}万股"
                    elif "变动" in str(col) or "增减" in str(col):
                        change = safe_float(row[col])
                        if change:
                            fund_info["change"] = f"{change / 1e4:+.0f}万股"
                if fund_info.get("name"):
                    top_funds.append(fund_info)
            data["top_funds"] = top_funds

            for col in fund_df.columns:
                if "占" in str(col) and ("流通" in str(col) or "比" in str(col)):
                    total_pct = fund_df[col].astype(float, errors="ignore").sum()
                    if total_pct > 0:
                        data["fund_holding_pct"] = f"{total_pct:.2f}%"
                        break

            institution_fetched = True

        # Strategy 2: Sina circulate holders fallback
        if not institution_fetched:
            try:
                with no_proxy():
                    df = ak.stock_circulate_stock_holder(symbol=symbol)
                if df is not None and not df.empty:
                    latest_date = df["截止日期"].max()
                    latest_df = df[df["截止日期"] == latest_date]

                    fund_count = 0
                    fund_holders: list[dict[str, Any]] = []
                    for _, row in latest_df.iterrows():
                        holder_name = str(row.get("股东名称", ""))
                        holder_type = str(row.get("股本性质", ""))
                        ratio = row.get("占流通股比例", 0)
                        is_fund = any(
                            kw in holder_name
                            for kw in ["基金", "社保", "保险", "信托", "QFII", "证券"]
                        )
                        is_fund = is_fund or (
                            "境内法人" in holder_type or "境外法人" in holder_type
                        )
                        if is_fund and "有限公司" not in holder_name[:10]:
                            fund_count += 1
                            fund_holders.append(
                                {
                                    "name": holder_name[:20],
                                    "shares": f"{ratio}%",
                                }
                            )

                    data["institution_data_date"] = str(latest_date)[:10]
                    data["fund_holding_count"] = fund_count
                    data["top_funds"] = fund_holders[:5]
                    institution_fetched = True
            except Exception:
                pass

        # Cross-quarter comparison (Eastmoney only)
        if institution_fetched and data.get("fund_holding_count", 0) > 0:
            try:
                if quarter.endswith("0930"):
                    prev_quarter = quarter[:4] + "0630"
                elif quarter.endswith("0630"):
                    prev_quarter = quarter[:4] + "0331"
                elif quarter.endswith("0331"):
                    prev_quarter = str(int(quarter[:4]) - 1) + "1231"
                else:
                    prev_quarter = quarter[:4] + "0930"

                with no_proxy():
                    prev_df = ak.stock_report_fund_hold(symbol=symbol, date=prev_quarter)
                if prev_df is not None and not prev_df.empty:
                    data["fund_holding_count_prev"] = len(prev_df)
                    change = data.get("fund_holding_count", 0) - data["fund_holding_count_prev"]
                    data["fund_holding_change"] = f"{change:+d}"
            except Exception:
                pass

        parts: list[str] = []
        if data.get("fund_holding_count", 0) > 0:
            parts.append(f"{data['fund_holding_count']}家机构持仓")
        if data.get("fund_holding_change"):
            parts.append(f"较上期{data['fund_holding_change']}")
        if data.get("fund_holding_pct"):
            parts.append(f"合计占比{data['fund_holding_pct']}")
        if data.get("top_funds"):
            top_names = [f["name"][:8] for f in data["top_funds"][:2]]
            parts.append(f"含{', '.join(top_names)}")

        data["institution_summary"] = (
            " | ".join(parts) if parts else "暂无机构持仓数据"
        )

        return data
