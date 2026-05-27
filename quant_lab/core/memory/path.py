"""Path utilities for the memory layer."""

from __future__ import annotations

import re


def safe_ticker_component(ticker: str) -> str:
    """Convert a ticker into a filesystem-safe path component.

    Replaces path separators, dots, and other special characters with
    underscores to prevent directory traversal and ensure cross-platform
    compatibility.

    Args:
        ticker: Raw ticker string (e.g. ``"000001.SZ"``, ``"BRK.B"``).

    Returns:
        Sanitised string safe for use in file / directory names.
    """
    # Replace common filesystem-unsafe characters
    safe = re.sub(r'[\\/:*?"<>|\.]', "_", ticker)
    # Collapse multiple underscores
    safe = re.sub(r"_+", "_", safe)
    # Strip leading/trailing underscores
    return safe.strip("_")
