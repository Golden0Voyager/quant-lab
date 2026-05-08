"""Shared fixtures for parity tests.

`mock_akshare` patches raw akshare functions per fixture, transparently
covering both v2 sources and legacy analyst_data code paths since both
import via `import akshare as ak`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import akshare as ak  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    """Load a fixture JSON file from tests/v2/fixtures/."""
    path = FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _build_return_value(spec: Any) -> Any:
    """Convert a fixture spec into the akshare function return value."""
    if spec is None:
        return None
    if isinstance(spec, dict) and "_columns" in spec:
        return pd.DataFrame(spec["_rows"], columns=spec["_columns"])
    return spec


@contextmanager
def mock_akshare(fixture: dict[str, Any]) -> Iterator[None]:
    """Patch akshare functions per fixture.

    Top-level fixture keys are raw akshare function names (e.g.
    ``stock_yjbb_em``). Values follow the spec defined in the design doc.
    A ``None`` value makes the patched function raise to simulate a
    failed/empty source.
    """
    patches = []
    for func_name, spec in fixture.items():
        if not hasattr(ak, func_name):
            continue
        if spec is None:
            patcher = patch.object(
                ak, func_name, side_effect=Exception(f"mocked: {func_name}")
            )
        else:
            patcher = patch.object(
                ak, func_name, return_value=_build_return_value(spec)
            )
        patches.append(patcher)
        patcher.start()
    try:
        yield
    finally:
        for p in patches:
            p.stop()
