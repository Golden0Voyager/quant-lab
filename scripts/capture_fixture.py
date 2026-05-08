"""Capture an akshare-call fixture for parity tests.

Usage:
    uv run python scripts/capture_fixture.py valuation 000001

Outputs JSON to ``tests/v2/fixtures/<dimension>_<symbol>.json``.

This script intercepts every ``ak.*`` call made during a single legacy
``fetch_<dimension>_data`` invocation and records (function name, return
value) so the same fixture can be replayed deterministically in parity
tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import akshare as ak  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "tests" / "v2" / "fixtures"


def _serialize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.DataFrame):
        cleaned = value.astype(object).where(pd.notna(value), None)
        return {
            "_columns": list(value.columns),
            "_rows": cleaned.values.tolist(),
        }
    return value


def capture(dimension: str, symbol: str) -> None:
    sys.path.insert(0, str(ROOT))
    import analyst_data  # noqa: PLC0415

    captured: dict[str, Any] = {}
    originals: dict[str, Any] = {}

    for attr in dir(ak):
        if not (
            attr.startswith("stock_")
            or attr.startswith("fund_")
            or attr.startswith("macro_")
            or attr.startswith("fx_")
        ):
            continue
        fn = getattr(ak, attr)
        if not callable(fn):
            continue
        originals[attr] = fn

        def make_wrapper(name: str, original: Any) -> Any:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    result = original(*args, **kwargs)
                except Exception:
                    captured[name] = None
                    raise
                captured[name] = _serialize(result)
                return result

            return wrapper

        setattr(ak, attr, make_wrapper(attr, fn))

    func_name = f"fetch_{dimension}_data"
    try:
        legacy_fn = getattr(analyst_data, func_name)
        legacy_fn(symbol, "占位股票名")
    finally:
        for name, fn in originals.items():
            setattr(ak, name, fn)

    out = FIXTURES_DIR / f"{dimension}_{symbol}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(captured, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"Wrote {out} ({len(captured)} akshare calls captured)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "dimension", help="e.g. valuation, performance, sentiment, consensus"
    )
    parser.add_argument("symbol", help="6-digit stock code, e.g. 000001")
    args = parser.parse_args()
    capture(args.dimension, args.symbol)


if __name__ == "__main__":
    main()
