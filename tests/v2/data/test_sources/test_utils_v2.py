"""Extended tests for sources/_utils — covering uncovered branches."""

from __future__ import annotations

import os
from unittest.mock import patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.sources._utils import no_proxy, safe_float


class TestNoProxyV2:
    def test_removes_proxy_env(self) -> None:
        """Lines 29, 34: delete and restore proxy env vars."""
        with patch.dict(os.environ, {"https_proxy": "http://proxy:7897", "HTTP_PROXY": "http://proxy:7897"}, clear=False):
            with no_proxy():
                assert "https_proxy" not in os.environ
                assert "HTTP_PROXY" not in os.environ
            assert os.environ["https_proxy"] == "http://proxy:7897"
            assert os.environ["HTTP_PROXY"] == "http://proxy:7897"

    def test_no_proxy_vars(self) -> None:
        """When no proxy vars exist, no_proxy still works."""
        with patch.dict(os.environ, {}, clear=True):
            with no_proxy():
                pass


class TestSafeFloatV2:
    def test_value_error(self) -> None:
        """Line 43: ValueError → None."""
        assert safe_float("not_a_number") is None

    def test_type_error(self) -> None:
        """Line 44: TypeError → None."""
        assert safe_float([1, 2, 3]) is None

    def test_nan_value(self) -> None:
        assert safe_float(float("nan")) is None

    def test_valid_float(self) -> None:
        assert safe_float("3.14") == 3.14

    def test_none_value(self) -> None:
        assert safe_float(None) is None
