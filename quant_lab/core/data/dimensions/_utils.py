"""Shared utilities for dimension fetchers."""

from __future__ import annotations

from datetime import datetime


def get_report_date() -> str:
    """Return the most recently available report date string (YYYYMMDD)."""
    now = datetime.now()
    year, month = now.year, now.month
    if month >= 11:
        return f"{year}0930"
    elif month >= 8:
        return f"{year}0630"
    elif month >= 5:
        return f"{year}0331"
    return f"{year - 1}0930"
