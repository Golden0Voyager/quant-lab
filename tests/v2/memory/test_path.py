"""Tests for quant_lab.core.memory.path."""

from __future__ import annotations

import pytest

from quant_lab.core.memory.path import safe_ticker_component


class TestSafeTickerComponent:
    """Tests for ``safe_ticker_component``."""

    def test_plain_code(self) -> None:
        assert safe_ticker_component("000001") == "000001"

    def test_us_ticker(self) -> None:
        assert safe_ticker_component("BRK.B") == "BRK_B"

    def test_hk_ticker(self) -> None:
        assert safe_ticker_component("00700.HK") == "00700_HK"

    def test_path_traversal(self) -> None:
        assert safe_ticker_component("../etc/passwd") == "etc_passwd"

    def test_multiple_special_chars(self) -> None:
        assert safe_ticker_component("a::b//c") == "a_b_c"
