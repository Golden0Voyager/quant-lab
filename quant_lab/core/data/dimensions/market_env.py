"""Market environment dimension fetcher."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import akshare as ak  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.base import safe_fetch
from quant_lab.core.data.dimensions.industry_compare import _get_industry
from quant_lab.core.data.sources._utils import no_proxy, safe_float

logger = logging.getLogger(__name__)

# Module-level caches (mirrors legacy behaviour).
_index_cache: dict[str, Any] = {"data": None, "time": None}
_multi_index_cache: dict[str, Any] = {"data": None, "time": None}
_market_breadth_cache: dict[str, Any] = {"data": None, "time": None}
_board_cache: dict[str, Any] = {"data": None, "time": None}
_shibor_cache: dict[str, Any] = {"data": None, "time": None}
_north_flow_cache: dict[str, Any] = {"data": None, "time": None}


class MarketEnvFetcher:
    """Fetch broad market and sector environment data."""

    name = "market_env"

    @safe_fetch
    def fetch(self, symbol: str, stock_name: str, **kwargs: Any) -> dict[str, Any]:
        """Return market environment data."""
        data: dict[str, Any] = {}
        now = datetime.now()
        data["market_env_data_date"] = now.strftime("%Y-%m-%d")

        self._fetch_indices(data, now)
        self._fetch_volume(data, now)
        self._fetch_market_breadth(data, now)
        self._fetch_cross_border_flows(data, now)
        self._fetch_shibor(data, now)
        self._compute_sentiment_score(data)
        self._fetch_sector_ranking(data, symbol, now)
        self._fetch_sector_extremes(data)
        data["market_env_summary"] = self._build_summary(data)

        return data

    # ==================== Block A: Indices ====================

    def _fetch_indices(self, data: dict[str, Any], now: datetime) -> None:
        """Fetch Shanghai composite + multi-index 5-day changes."""
        global _index_cache, _multi_index_cache

        # Shanghai composite (5-min cache)
        if (
            _index_cache["data"] is None
            or _index_cache["time"] is None
            or (now - _index_cache["time"]).total_seconds() > 300
        ):
            try:
                with no_proxy():
                    idx_df = ak.stock_zh_index_daily(symbol="sh000001")
                if idx_df is not None and not idx_df.empty:
                    _index_cache["data"] = idx_df
                    _index_cache["time"] = now
            except Exception:  # noqa: BLE001
                pass

        if _index_cache["data"] is not None and not _index_cache["data"].empty:
            index_df = _index_cache["data"]
            if len(index_df) >= 20:
                latest_close = safe_float(index_df.iloc[-1]["close"])
                close_5d = (
                    safe_float(index_df.iloc[-6]["close"])
                    if len(index_df) >= 6
                    else None
                )
                close_20d = (
                    safe_float(index_df.iloc[-21]["close"])
                    if len(index_df) >= 21
                    else None
                )
                if latest_close and close_5d:
                    data["market_index_change_5d"] = (
                        f"{(latest_close / close_5d - 1) * 100:+.2f}%"
                    )
                if latest_close and close_20d:
                    data["market_index_change_20d"] = (
                        f"{(latest_close / close_20d - 1) * 100:+.2f}%"
                    )
                ma20 = index_df.tail(20)["close"].astype(float).mean()
                data["market_index_above_ma20"] = latest_close > ma20

        # Multi-index (15-min cache)
        multi_indices = [
            ("sh000300", "沪深300"),
            ("sz399006", "创业板指"),
            ("sh000688", "科创50"),
            ("sh000905", "中证500"),
            ("sz399001", "深证成指"),
        ]
        if (
            _multi_index_cache["data"] is None
            or _multi_index_cache["time"] is None
            or (now - _multi_index_cache["time"]).total_seconds() > 900
        ):
            idx_results: dict[str, Any] = {}
            for idx_symbol, idx_name in multi_indices:
                try:
                    with no_proxy():
                        idf = ak.stock_zh_index_daily(symbol=idx_symbol)
                    if idf is not None and not idf.empty and len(idf) >= 6:
                        latest = safe_float(idf.iloc[-1]["close"])
                        prev5 = safe_float(idf.iloc[-6]["close"])
                        if latest and prev5:
                            chg = (latest / prev5 - 1) * 100
                            idx_results[idx_name] = {
                                "close": latest,
                                "change_5d": chg,
                                "df": idf,
                            }
                except Exception:  # noqa: BLE001
                    pass
            if idx_results:
                _multi_index_cache["data"] = idx_results
                _multi_index_cache["time"] = now

        if _multi_index_cache["data"]:
            parts: list[str] = []
            for idx_name in ("沪深300", "创业板指", "科创50", "中证500"):
                info = _multi_index_cache["data"].get(idx_name)
                if info:
                    parts.append(f"{idx_name} {info['change_5d']:+.2f}%")
            if parts:
                data["indices_overview"] = " | ".join(parts)

    # ==================== Block B: Volume ====================

    def _fetch_volume(self, data: dict[str, Any], now: datetime) -> None:
        """Fetch total market volume with 3-tier fallback."""
        global _index_cache, _multi_index_cache

        try:
            amount_available = False

            # Strategy 1: Xueqiu spot
            xq_token = os.getenv("XUEQIU_TOKEN") or os.getenv("XQ_TOKEN")
            if xq_token:
                try:
                    with no_proxy():
                        sh_spot = ak.stock_individual_spot_xq(
                            symbol="SH000001", token=xq_token
                        )
                        sz_spot = ak.stock_individual_spot_xq(
                            symbol="SZ399001", token=xq_token
                        )
                    sh_items = dict(
                        zip(sh_spot["item"], sh_spot["value"], strict=False)
                    )
                    sz_items = dict(
                        zip(sz_spot["item"], sz_spot["value"], strict=False)
                    )
                    sh_amt = float(sh_items["成交额"])
                    sz_amt = float(sz_items["成交额"])
                    if sh_amt > 0 and sz_amt > 0:
                        total_yi = (sh_amt + sz_amt) / 1e8
                        data["market_total_volume"] = self._fmt_volume(total_yi)
                        amount_available = True
                except Exception:  # noqa: BLE001
                    pass

            # Strategy 2: Eastmoney historical amount
            if not amount_available:
                try:
                    em_start = (now - timedelta(days=30)).strftime("%Y%m%d")
                    em_end = now.strftime("%Y%m%d")
                    with no_proxy():
                        sh_em = ak.stock_zh_index_daily_em(
                            symbol="sh000001",
                            start_date=em_start,
                            end_date=em_end,
                        )
                        sz_em = ak.stock_zh_index_daily_em(
                            symbol="sz399001",
                            start_date=em_start,
                            end_date=em_end,
                        )
                    if (
                        sh_em is not None
                        and not sh_em.empty
                        and "amount" in sh_em.columns
                        and sz_em is not None
                        and not sz_em.empty
                        and "amount" in sz_em.columns
                    ):
                        sh_amt = safe_float(sh_em.iloc[-1]["amount"])
                        sz_amt = safe_float(sz_em.iloc[-1]["amount"])
                        if sh_amt and sz_amt:
                            total_amt = sh_amt + sz_amt
                            total_yi = total_amt / 1e8
                            data["market_total_volume"] = self._fmt_volume(
                                total_yi
                            )
                            amount_available = True

                            if len(sh_em) >= 6 and len(sz_em) >= 6:
                                amt_5d: list[float] = []
                                for i in range(
                                    2, min(7, len(sh_em), len(sz_em))
                                ):
                                    s = safe_float(sh_em.iloc[-i]["amount"])
                                    z = safe_float(sz_em.iloc[-i]["amount"])
                                    if s and z:
                                        amt_5d.append(s + z)
                                if amt_5d:
                                    avg_5d = sum(amt_5d) / len(amt_5d)
                                    if avg_5d > 0:
                                        vol_vs = (total_amt / avg_5d - 1) * 100
                                        data["market_volume_vs_5d"] = (
                                            f"{vol_vs:+.1f}%"
                                        )
                                        data["market_volume_vs_5d_raw"] = vol_vs
                except Exception:  # noqa: BLE001
                    pass

            # Strategy 3: Sina volume relative change
            if "market_volume_vs_5d" not in data:
                sh_vol: float | None = None
                sh_vol_5d: list[float] = []
                sz_vol: float | None = None
                sz_vol_5d: list[float] = []

                if (
                    _index_cache["data"] is not None
                    and not _index_cache["data"].empty
                ):
                    sh_df = _index_cache["data"]
                    if "volume" in sh_df.columns and len(sh_df) >= 6:
                        sh_vol = safe_float(sh_df.iloc[-1]["volume"])
                        sh_vol_5d = [
                            safe_float(sh_df.iloc[-i]["volume"])
                            for i in range(2, 7)
                        ]
                        sh_vol_5d = [v for v in sh_vol_5d if v]

                sz_cache = (
                    _multi_index_cache["data"].get("深证成指")
                    if _multi_index_cache["data"]
                    else None
                )
                if sz_cache and "df" in sz_cache:
                    sz_df = sz_cache["df"]
                    if "volume" in sz_df.columns and len(sz_df) >= 6:
                        sz_vol = safe_float(sz_df.iloc[-1]["volume"])
                        sz_vol_5d = [
                            safe_float(sz_df.iloc[-i]["volume"])
                            for i in range(2, 7)
                        ]
                        sz_vol_5d = [v for v in sz_vol_5d if v]

                if sh_vol:
                    today_total = sh_vol + (sz_vol or 0)
                    avg_sh = (
                        sum(sh_vol_5d) / len(sh_vol_5d) if sh_vol_5d else 0
                    )
                    avg_sz = (
                        sum(sz_vol_5d) / len(sz_vol_5d) if sz_vol_5d else 0
                    )
                    avg_total = avg_sh + avg_sz
                    if avg_total > 0:
                        vol_vs = (today_total / avg_total - 1) * 100
                        data["market_volume_vs_5d"] = f"{vol_vs:+.1f}%"
                        data["market_volume_vs_5d_raw"] = vol_vs

            # Volume signal
            vs_5d = data.get("market_volume_vs_5d_raw")
            if vs_5d is not None:
                if vs_5d > 20:
                    data["market_volume_signal"] = "放量"
                elif vs_5d < -20:
                    data["market_volume_signal"] = "缩量"
                else:
                    data["market_volume_signal"] = "正常"
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _fmt_volume(total_yi: float) -> str:
        if total_yi >= 10000:
            return f"{total_yi / 10000:.2f}万亿"
        return f"{total_yi:.0f}亿"

    # ==================== Block C: Market breadth ====================

    def _fetch_market_breadth(self, data: dict[str, Any], now: datetime) -> None:
        """Fetch advance/decline counts and limit up/down."""
        global _market_breadth_cache

        if (
            _market_breadth_cache["data"] is None
            or _market_breadth_cache["time"] is None
            or (now - _market_breadth_cache["time"]).total_seconds() > 600
        ):
            breadth: dict[str, Any] = {}
            try:
                with no_proxy():
                    activity_df = ak.stock_market_activity_legu()
                if activity_df is not None and not activity_df.empty:
                    items = dict(
                        zip(activity_df["item"], activity_df["value"], strict=False)
                    )
                    for key, out_key in (
                        ("上涨", "up"),
                        ("下跌", "down"),
                        ("平盘", "flat"),
                        ("涨停", "limit_up_from_legu"),
                        ("跌停", "limit_down_from_legu"),
                    ):
                        if key in items:
                            breadth[out_key] = int(float(items[key]))
            except Exception:  # noqa: BLE001
                pass

            today_str = now.strftime("%Y%m%d")
            try:
                with no_proxy():
                    zt_df = ak.stock_zt_pool_em(date=today_str)
                breadth["limit_up"] = len(zt_df) if zt_df is not None else 0
            except Exception:  # noqa: BLE001
                pass

            try:
                with no_proxy():
                    dt_df = ak.stock_zt_pool_dtgc_em(date=today_str)
                breadth["limit_down"] = len(dt_df) if dt_df is not None else 0
            except Exception:  # noqa: BLE001
                pass

            if breadth:
                _market_breadth_cache["data"] = breadth
                _market_breadth_cache["time"] = now

        if _market_breadth_cache["data"]:
            b = _market_breadth_cache["data"]
            for key, out_key in (
                ("up", "market_up_count"),
                ("down", "market_down_count"),
                ("flat", "market_flat_count"),
            ):
                if key in b:
                    data[out_key] = b[key]

            if "limit_up" in b:
                data["market_limit_up"] = b["limit_up"]
            elif "limit_up_from_legu" in b:
                data["market_limit_up"] = b["limit_up_from_legu"]
            if "limit_down" in b:
                data["market_limit_down"] = b["limit_down"]
            elif "limit_down_from_legu" in b:
                data["market_limit_down"] = b["limit_down_from_legu"]

            up = b.get("up", 0)
            down = b.get("down", 0)
            if down > 0:
                ratio = up / down
                data["market_advance_decline_ratio"] = f"{ratio:.2f}"
                data["market_advance_decline_ratio_raw"] = ratio
                if ratio > 1.5:
                    data["market_breadth_signal"] = "普涨"
                elif ratio < 0.67:
                    data["market_breadth_signal"] = "普跌"
                else:
                    data["market_breadth_signal"] = "分化"
            elif up > 0:
                data["market_advance_decline_ratio"] = "极端普涨"
                data["market_advance_decline_ratio_raw"] = 99.0
                data["market_breadth_signal"] = "普涨"

    # ==================== Block D: Cross-border flows ====================

    def _fetch_cross_border_flows(
        self, data: dict[str, Any], now: datetime
    ) -> None:
        """Fetch southbound (HK) fund flow."""
        global _north_flow_cache

        if (
            _north_flow_cache["data"] is None
            or _north_flow_cache["time"] is None
            or (now - _north_flow_cache["time"]).total_seconds() > 600
        ):
            try:
                with no_proxy():
                    hsgt_df = ak.stock_hsgt_fund_flow_summary_em()
                if hsgt_df is not None and not hsgt_df.empty:
                    _north_flow_cache["data"] = hsgt_df
                    _north_flow_cache["time"] = now
            except Exception:  # noqa: BLE001
                pass

        if (
            _north_flow_cache["data"] is not None
            and not _north_flow_cache["data"].empty
        ):
            try:
                ndf = _north_flow_cache["data"]
                if "资金方向" in ndf.columns:
                    south_rows = ndf[ndf["资金方向"] == "南向"]
                else:
                    south_rows = pd.DataFrame()
                if (
                    not south_rows.empty
                    and "成交净买额" in south_rows.columns
                ):
                    south_net = south_rows["成交净买额"].astype(float).sum()
                    data["south_total_net_flow"] = f"{south_net:+.1f}亿"
                    data["south_total_net_flow_raw"] = south_net
                    data["south_flow_direction"] = (
                        "净流入港股" if south_net > 0 else "净流出港股"
                    )
                data["north_total_net_flow"] = "2024年8月起已停止实时披露"
            except Exception:  # noqa: BLE001
                pass

    # ==================== Block E: Shibor ====================

    def _fetch_shibor(self, data: dict[str, Any], now: datetime) -> None:
        """Fetch Shibor overnight and 1-week rates."""
        global _shibor_cache

        if (
            _shibor_cache["data"] is None
            or _shibor_cache["time"] is None
            or (now - _shibor_cache["time"]).total_seconds() > 1800
        ):
            try:
                with no_proxy():
                    shibor_df = ak.macro_china_shibor_all()
                if shibor_df is not None and not shibor_df.empty:
                    _shibor_cache["data"] = shibor_df
                    _shibor_cache["time"] = now
            except Exception:  # noqa: BLE001
                pass

        if _shibor_cache["data"] is not None and not _shibor_cache["data"].empty:
            try:
                sdf = _shibor_cache["data"]
                latest = sdf.iloc[-1] if len(sdf) > 0 else None
                if latest is not None:
                    for col_on in ("O/N-定价", "O/N_定价", "O/N", "隔夜"):
                        if col_on in sdf.columns:
                            data["shibor_overnight"] = (
                                f"{float(latest[col_on]):.3f}%"
                            )
                            data["shibor_overnight_raw"] = float(
                                latest[col_on]
                            )
                            break
                    for col_1w in ("1W-定价", "1W_定价", "1W", "1周"):
                        if col_1w in sdf.columns:
                            data["shibor_1w"] = f"{float(latest[col_1w]):.3f}%"
                            break
                    for col_on_chg in (
                        "O/N-涨跌幅",
                        "O/N_涨跌幅",
                        "O/N_涨跌(BP)",
                    ):
                        if col_on_chg in sdf.columns:
                            chg_bp = float(latest[col_on_chg])
                            data["shibor_overnight_change"] = f"{chg_bp:+.1f}bp"
                            data["shibor_overnight_change_raw"] = chg_bp
                            break
                    for col_1w_chg in (
                        "1W-涨跌幅",
                        "1W_涨跌幅",
                        "1W_涨跌(BP)",
                    ):
                        if col_1w_chg in sdf.columns:
                            data["shibor_1w_change_raw"] = float(
                                latest[col_1w_chg]
                            )
                            break

                    on_chg = data.get("shibor_overnight_change_raw", 0)
                    w1_chg = data.get("shibor_1w_change_raw", 0)
                    if on_chg > 5 and w1_chg > 5:
                        data["monetary_signal"] = "收紧"
                    elif on_chg < -5 and w1_chg < -5:
                        data["monetary_signal"] = "宽松"
                    else:
                        data["monetary_signal"] = "平稳"
            except Exception:  # noqa: BLE001
                pass

    # ==================== Sentiment scoring ====================

    def _compute_sentiment_score(self, data: dict[str, Any]) -> None:
        """Compute multi-factor market sentiment score."""
        score = 0
        if data.get("market_index_above_ma20") is True:
            score += 1
        elif data.get("market_index_above_ma20") is False:
            score -= 1

        chg_5d = data.get("market_index_change_5d", "")
        if chg_5d.startswith("+"):
            score += 1
        elif chg_5d.startswith("-"):
            score -= 1

        adr = data.get("market_advance_decline_ratio_raw")
        if adr is not None:
            if adr > 1.5:
                score += 1
            elif adr < 0.67:
                score -= 1

        south_raw = data.get("south_total_net_flow_raw")
        if south_raw is not None:
            if south_raw < -20:
                score += 1
            elif south_raw > 50:
                score -= 1

        vol_signal = data.get("market_volume_signal", "")
        if vol_signal == "放量":
            score += 1
        elif vol_signal == "缩量":
            score -= 1

        if score >= 2:
            data["market_sentiment"] = "偏暖"
        elif score <= -2:
            data["market_sentiment"] = "偏冷"
        else:
            data["market_sentiment"] = "中性"
        data["market_sentiment_score"] = score

    # ==================== Sector ranking ====================

    def _fetch_sector_ranking(
        self, data: dict[str, Any], symbol: str, now: datetime
    ) -> None:
        """Fetch sector ranking for the stock's industry."""
        global _board_cache

        sector_name = _get_industry(symbol)
        if sector_name:
            data["sector_name"] = sector_name

        if (
            _board_cache["data"] is None
            or _board_cache["time"] is None
            or (now - _board_cache["time"]).total_seconds() > 300
        ):
            try:
                with no_proxy():
                    board_df = ak.stock_board_industry_name_em()
                if board_df is not None and not board_df.empty:
                    _board_cache["data"] = board_df
                    _board_cache["time"] = now
            except Exception:  # noqa: BLE001
                pass

            if _board_cache["data"] is None:
                try:
                    with no_proxy():
                        board_df = ak.stock_board_industry_summary_ths()
                    if board_df is not None and not board_df.empty:
                        board_df = board_df.rename(
                            columns={
                                "板块": "板块名称",
                                "净流入": "主力净流入",
                                "总成交额": "成交额",
                            }
                        )
                        _board_cache["data"] = board_df
                        _board_cache["time"] = now
                except Exception:  # noqa: BLE001
                    pass

        if (
            _board_cache["data"] is not None
            and not _board_cache["data"].empty
            and sector_name
        ):
            board_df = _board_cache["data"]
            total_sectors = len(board_df)
            sector_row = board_df[board_df["板块名称"] == sector_name]
            if sector_row.empty:
                sector_row = board_df[
                    board_df["板块名称"].str.contains(
                        sector_name[:2], na=False
                    )
                ]
            if sector_row.empty:
                generic_words = set("行业制造设备服务概念板块及与")
                keywords = set(sector_name) - generic_words
                if keywords:
                    for idx, r in board_df.iterrows():
                        bname = str(r["板块名称"])
                        bkeys = set(bname) - generic_words
                        if keywords & bkeys:
                            sector_row = board_df.loc[[idx]]
                            break

            if not sector_row.empty:
                row = sector_row.iloc[0]
                rank_idx = (
                    board_df.index.get_loc(sector_row.index[0]) + 1
                )
                data["sector_rank"] = f"{rank_idx}/{total_sectors}"
                change_today = safe_float(row.get("涨跌幅"))
                if change_today is not None:
                    data["sector_change_today"] = (
                        f"{change_today:+.2f}%"
                    )
                main_inflow = safe_float(row.get("主力净流入"))
                if main_inflow is not None:
                    data["sector_main_inflow"] = (
                        f"{main_inflow / 1e8:.1f}亿"
                    )

    # ==================== Sector extremes ====================

    def _fetch_sector_extremes(self, data: dict[str, Any]) -> None:
        """Fetch top-3 hot and cold sectors."""
        global _board_cache

        if (
            _board_cache["data"] is not None
            and not _board_cache["data"].empty
        ):
            try:
                board_df = _board_cache["data"]
                if "涨跌幅" in board_df.columns:
                    board_sorted = board_df.sort_values(
                        "涨跌幅", ascending=False
                    )
                    hot3: list[str] = []
                    for _, r in board_sorted.head(3).iterrows():
                        chg = safe_float(r["涨跌幅"])
                        if chg is not None:
                            hot3.append(
                                f"{r['板块名称']} {chg:+.2f}%"
                            )
                    data["hot_sectors_top3"] = hot3

                    cold3: list[str] = []
                    for _, r in board_sorted.tail(3).iterrows():
                        chg = safe_float(r["涨跌幅"])
                        if chg is not None:
                            cold3.append(
                                f"{r['板块名称']} {chg:+.2f}%"
                            )
                    data["cold_sectors_top3"] = cold3
            except Exception:  # noqa: BLE001
                pass

    # ==================== Summary ====================

    @staticmethod
    def _build_summary(data: dict[str, Any]) -> str:
        parts: list[str] = []
        if data.get("market_sentiment"):
            parts.append(
                f"大盘{data['market_sentiment']}(评分{data.get('market_sentiment_score', 'N/A')})"
            )
        if data.get("market_index_change_5d"):
            parts.append(f"上证5日{data['market_index_change_5d']}")
        if data.get("indices_overview"):
            parts.append(data["indices_overview"])
        if data.get("market_total_volume"):
            vol_part = f"成交{data['market_total_volume']}"
            if data.get("market_volume_vs_5d"):
                vol_part += f"(vs5日均{data['market_volume_vs_5d']}"
                if data.get("market_volume_signal"):
                    vol_part += f",{data['market_volume_signal']}"
                vol_part += ")"
            parts.append(vol_part)
        elif data.get("market_volume_vs_5d"):
            vol_part = f"量能vs5日均{data['market_volume_vs_5d']}"
            if data.get("market_volume_signal"):
                vol_part += f"({data['market_volume_signal']})"
            parts.append(vol_part)
        if data.get("market_up_count") is not None and data.get(
            "market_down_count"
        ) is not None:
            parts.append(
                f"涨{data['market_up_count']}/跌{data['market_down_count']} "
                f"涨停{data.get('market_limit_up', '?')}/跌停{data.get('market_limit_down', '?')}"
            )
        if data.get("south_total_net_flow"):
            parts.append(f"南向(港股通){data['south_total_net_flow']}")
        if data.get("sector_name"):
            parts.append(
                f"板块[{data['sector_name']}]排名{data.get('sector_rank', 'N/A')}"
            )
        return " | ".join(parts) if parts else "大盘环境数据不可用"
