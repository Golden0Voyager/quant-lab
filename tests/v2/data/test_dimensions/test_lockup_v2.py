"""Extended tests for LockupFetcher — covering uncovered branches."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.lockup import LockupFetcher


class TestLockupFetcherV2:
    @patch("quant_lab.core.data.dimensions.lockup.ak")
    def test_release_date_parse_exception(self, mock_ak: MagicMock) -> None:
        """Lines 52-53: bad date → skip row."""
        mock_ak.stock_restricted_release_queue_em.return_value = pd.DataFrame(
            {
                "解禁日期": ["not-a-date"],
                "解禁数量": [50000000],
                "占流通股比例": [2.5],
            }
        )
        fetcher = LockupFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "_error" not in result
        assert result["lockup_events"] == []

    @patch("quant_lab.core.data.dimensions.lockup.ak")
    def test_past_date_skipped(self, mock_ak: MagicMock) -> None:
        """Line 57: release_date < today → skip."""
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        mock_ak.stock_restricted_release_queue_em.return_value = pd.DataFrame(
            {
                "解禁日期": [yesterday],
                "解禁数量": [50000000],
                "占流通股比例": [2.5],
            }
        )
        fetcher = LockupFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert result["lockup_events"] == []

    @patch("quant_lab.core.data.dimensions.lockup.ak")
    def test_pct_parse_exception(self, mock_ak: MagicMock) -> None:
        """Lines 94-95: bad pct → skip."""
        mock_ak.stock_restricted_release_queue_em.return_value = pd.DataFrame(
            {
                "解禁日期": [(date.today() + timedelta(days=30)).strftime("%Y-%m-%d")],
                "解禁数量": [50000000],
                "占流通股比例": ["not_a_number"],
            }
        )
        fetcher = LockupFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert "_error" not in result

    @patch("quant_lab.core.data.dimensions.lockup.ak")
    def test_medium_risk(self, mock_ak: MagicMock) -> None:
        """Line 100: medium risk branch."""
        mock_ak.stock_restricted_release_queue_em.return_value = pd.DataFrame(
            {
                "解禁日期": [(date.today() + timedelta(days=30)).strftime("%Y-%m-%d")],
                "解禁数量": [50000000],
                "占流通股比例": [4.0],  # total_pct_6m = 4.0, > 3 but < 10
            }
        )
        fetcher = LockupFetcher()
        result = fetcher.fetch("000001", "平安银行")
        assert result["lockup_risk_level"] == "中风险"
