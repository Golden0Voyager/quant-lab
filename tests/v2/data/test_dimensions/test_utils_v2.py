"""Extended tests for _utils.py (dimension fetchers) — covering get_report_date branches."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from quant_lab.core.data.dimensions._utils import get_report_date


class TestGetReportDateV2:
    def test_november(self) -> None:
        with patch("quant_lab.core.data.dimensions._utils.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 15)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert get_report_date() == "20250930"

    def test_august(self) -> None:
        with patch("quant_lab.core.data.dimensions._utils.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 8, 15)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert get_report_date() == "20250630"

    def test_may(self) -> None:
        with patch("quant_lab.core.data.dimensions._utils.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 5, 15)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert get_report_date() == "20250331"

    def test_january(self) -> None:
        with patch("quant_lab.core.data.dimensions._utils.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert get_report_date() == "20240930"
