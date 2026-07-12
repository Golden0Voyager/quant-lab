"""Recent K-line + BOLL dimension fetcher."""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any

import akshare as ak  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.config import get_settings
from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.sources._utils import no_proxy, safe_float

logger = logging.getLogger(__name__)


def _fetch_kline_df(symbol: str) -> pd.DataFrame | None:
    """Fetch K-line DataFrame from local database (优先), falling back to online APIs."""
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")

    # 策略0: 本地 SQLite 数据库
    try:
        settings = get_settings()
        db_path = settings.resolved_core_db_path
        if os.path.exists(db_path):
            db_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
            db_end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
            conn = sqlite3.connect(db_path)
            query = """
            SELECT trade_date as 日期, open as 开盘, close as 收盘, high as 最高, low as 最低,
                   volume as 成交量, amount as 成交额, turnover_rate as 换手率,
                   pct_change as 涨跌幅, amplitude as 振幅
            FROM daily_bars
            WHERE ts_code = ? AND trade_date >= ? AND trade_date <= ?
            ORDER BY trade_date ASC
            """
            df = pd.read_sql_query(query, conn, params=(symbol, db_start, db_end))
            conn.close()
            if df is not None and len(df) >= 20:
                if "日期" in df.columns:
                    df["日期"] = df["日期"].astype(str)
                logger.info("Loaded %d K-line records for %s from local database.", len(df), symbol)
                return df
    except Exception as e:
        logger.debug("Failed to fetch K-line for %s from local database: %s", symbol, e)

    # 策略1: 东财
    try:
        with no_proxy():
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )
        if df is not None and not df.empty:
            return df
    except Exception:  # noqa: BLE001
        pass

    # 策略2: 新浪
    try:
        sina_sym = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
        df = ak.stock_zh_a_daily(
            symbol=sina_sym, start_date=start_date, end_date=end_date, adjust="qfq"
        )
        if df is not None and not df.empty:
            df = df.rename(
                columns={
                    "close": "收盘",
                    "open": "开盘",
                    "high": "最高",
                    "low": "最低",
                    "volume": "成交量",
                    "date": "日期",
                }
            )
            return df
    except Exception:  # noqa: BLE001
        pass

    # 策略3: 腾讯
    try:
        tencent_sym = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
        df = ak.stock_zh_a_hist_tx(
            symbol=tencent_sym,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
        if df is not None and not df.empty:
            df = df.rename(
                columns={
                    "close": "收盘",
                    "open": "开盘",
                    "high": "最高",
                    "low": "最低",
                    "amount": "成交额",
                    "date": "日期",
                }
            )
            if "成交量" not in df.columns:
                df["成交量"] = 0
            return df
    except Exception:  # noqa: BLE001
        pass

    return None


class RecentKlineFetcher:
    """Fetch recent 20-day K-line data and BOLL bands."""

    name = "recent_kline"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str) -> dict[str, Any]:
        """Return recent 20-day K-line + BOLL indicators."""
        data: dict[str, Any] = {}

        hist_df = _fetch_kline_df(symbol)
        if hist_df is None or len(hist_df) < 20:
            raise ValueError("K-line数据不足20日")

        recent_20d = hist_df.tail(20).copy()
        recent_20d["量比"] = recent_20d["成交量"] / (
            recent_20d["成交量"].shift(1).rolling(window=5).mean()
        )
        recent_20d["振幅"] = (
            (recent_20d["最高"] - recent_20d["最低"])
            / recent_20d["收盘"].shift(1)
        ) * 100

        data["recent_20d_data"] = []
        for _, row in recent_20d.iterrows():
            data["recent_20d_data"].append(
                {
                    "date": str(row.get("日期", ""))[:10],
                    "open": safe_float(row.get("开盘")),
                    "close": safe_float(row.get("收盘")),
                    "high": safe_float(row.get("最高")),
                    "low": safe_float(row.get("最低")),
                    "change_pct": safe_float(row.get("涨跌幅")),
                    "amplitude": safe_float(row.get("振幅")),
                    "volume": safe_float(row.get("成交量")),
                    "amount": safe_float(row.get("成交额")),
                    "turnover_rate": safe_float(row.get("换手率")),
                    "volume_ratio": safe_float(row.get("量比")),
                }
            )

        # BOLL
        boll_mid = hist_df["收盘"].rolling(window=20).mean()
        boll_std = hist_df["收盘"].rolling(window=20).std()
        boll_upper = boll_mid + 2 * boll_std
        boll_lower = boll_mid - 2 * boll_std

        if pd.notna(boll_mid.iloc[-1]):
            data["boll_mid"] = round(boll_mid.iloc[-1], 2)
            data["boll_upper"] = round(boll_upper.iloc[-1], 2)
            data["boll_lower"] = round(boll_lower.iloc[-1], 2)
            if boll_mid.iloc[-1] > 0:
                data["boll_width"] = round(
                    (boll_upper.iloc[-1] - boll_lower.iloc[-1])
                    / boll_mid.iloc[-1]
                    * 100,
                    2,
                )

            current_price = safe_float(hist_df.iloc[-1]["收盘"])
            if current_price and data["boll_upper"] and data["boll_lower"]:
                boll_range = data["boll_upper"] - data["boll_lower"]
                if boll_range > 0:
                    pos_pct = (current_price - data["boll_lower"]) / boll_range * 100
                    data["boll_position"] = round(pos_pct, 1)
                    if pos_pct > 100:
                        data["boll_status"] = "突破上轨，极强"
                    elif pos_pct > 80:
                        data["boll_status"] = "接近上轨，偏强"
                    elif pos_pct < 0:
                        data["boll_status"] = "跌破下轨，极弱"
                    elif pos_pct < 20:
                        data["boll_status"] = "接近下轨，偏弱"
                    else:
                        data["boll_status"] = "中轨附近"

        return data
