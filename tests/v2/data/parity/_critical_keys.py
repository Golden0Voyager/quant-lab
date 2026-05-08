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
}

# Keys where v2 may legitimately add new fields not in legacy.
# Parity test asserts v2_keys >= legacy_keys - IGNORED_KEYS.
IGNORED_KEYS: set[str] = {
    "_internal_debug",
}
