"""Critical-key registry for parity tests.

For each dimension, list the keys whose v2-vs-legacy values must match
exactly (with float tolerance). Other keys (formatted strings, summary
text) may diverge slightly without failing the test.
"""

from __future__ import annotations

CRITICAL_KEYS: dict[str, list[str]] = {
    "valuation": [
        "pe_ttm_raw",
        "pb_raw",
        "dividend_yield_raw",
        "market_cap",
    ],
    "performance": [
        "revenue_ttm_raw",
        "revenue_yoy",
        "profit_yoy",
        "gross_margin",
        "roe",
        "eps",
    ],
    "sentiment": [
        "volume_ratio",
        "turnover_rate",
    ],
    "consensus": [
        "eps_forecast_current_raw",
        "eps_forecast_next_raw",
        "eps_growth_rate_raw",
        "target_price_avg",
    ],
    "recent_kline": [
        "boll_mid",
        "boll_upper",
        "boll_lower",
        "boll_width",
        "boll_position",
    ],
    "quarterly_trend": [
        # list data; parity checks length and first element keys
    ],
    "industry_compare": [
        "peer_count",
        "roe_median",
        "roe_rank",
        "roe_total",
        "roe_value",
        "gross_margin_median",
        "revenue_yoy_median",
        "profit_yoy_median",
    ],
    "top_holders": [
        # list data; parity checks list length
    ],
    "support_resistance": [
        "resistance_price",
        "support_price",
        "resistance_type",
        "support_type",
    ],
    "theme_sentiment": [
        "stock_sentiment",
    ],
    "macro_etf": [
        "usdcnh_rate",
    ],
    "lockup": [
        "lockup_risk_level",
        "lockup_6m_total_pct",
    ],
    "chip": [
        "chip_profit_ratio_raw",
        "chip_avg_cost_raw",
    ],
    "institution": [
        "fund_holding_count",
    ],
}

# Keys where v2 may legitimately add new fields not in legacy.
# Parity test asserts v2_keys >= legacy_keys - IGNORED_KEYS.
IGNORED_KEYS: set[str] = {
    "_internal_debug",
}
