"""Xueqiu real-time-quote source wrappers."""

from __future__ import annotations

import logging
import os
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


def fetch_xueqiu_spot(symbol: str, token: str | None = None) -> dict[str, Any] | None:
    """Fetch real-time spot data from Xueqiu (requires XUEQIU_TOKEN env)."""
    if token is None:
        token = os.getenv("XUEQIU_TOKEN") or os.getenv("XQ_TOKEN")
    if not token:
        return None

    xq_symbol = (
        f"SZ{symbol}"
        if symbol.startswith(("000", "001", "002", "003", "300"))
        else f"SH{symbol}"
    )
    try:
        df = ak.stock_individual_spot_xq(symbol=xq_symbol, token=token)
        if df is None or df.empty:
            return None
        return dict(zip(df["item"], df["value"], strict=False))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Xueqiu spot failed for %s: %s", symbol, exc)
        return None
