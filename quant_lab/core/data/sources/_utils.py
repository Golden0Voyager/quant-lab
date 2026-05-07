"""Shared utilities for data source adapters."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import pandas as pd  # type: ignore[import-untyped]


@contextmanager
def no_proxy() -> Generator[None, None, None]:
    """Temporarily remove proxy env vars so requests hit domestic APIs directly.

    Mirrors the behaviour of ``analyst_data.no_proxy``.
    """
    proxy_keys = (
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "all_proxy",
        "ALL_PROXY",
    )
    saved = {k: os.environ[k] for k in proxy_keys if k in os.environ}
    for k in saved:
        del os.environ[k]
    try:
        yield
    finally:
        for k, v in saved.items():
            os.environ[k] = v


def safe_float(value: Any) -> float | None:
    """Safely convert *value* to float, returning *None* on failure or NaN."""
    try:
        if pd.isna(value):
            return None
        return float(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None
