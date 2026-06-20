"""Tests for LockupFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.lockup import LockupFetcher


class TestLockupFetcher:
    @patch("quant_lab.core.data.dimensions.lockup.ak")
    def test_happy_path(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_restricted_release_queue_em.return_value = pd.DataFrame(
            {
                "解禁日期": ["2026-07-15", "2026-08-20"],
                "解禁数量": [50000000, 120000000],
                "占流通股比例": [2.5, 6.0],
            }
        )

        fetcher = LockupFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert len(result["lockup_events"]) == 2
        assert result["lockup_risk_level"] == "高风险"
        assert result["lockup_6m_total_pct"] == "8.5%"
        assert "最近解禁" in result["lockup_summary"]

    @patch("quant_lab.core.data.dimensions.lockup.ak")
    def test_empty_dataframe(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_restricted_release_queue_em.return_value = pd.DataFrame()

        fetcher = LockupFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" not in result
        assert result["lockup_events"] == []
        assert result["lockup_risk_level"] == "低风险"
        assert result["lockup_6m_total_pct"] == "0%"
        assert result["lockup_summary"] == "近期无解禁"

    @patch("quant_lab.core.data.dimensions.lockup.ak")
    def test_exception(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_restricted_release_queue_em.side_effect = Exception("API down")

        fetcher = LockupFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert "_error" in result
        assert result["_dimension"] == "lockup"

    @patch("quant_lab.core.data.dimensions.lockup.ak")
    def test_low_risk(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_restricted_release_queue_em.return_value = pd.DataFrame(
            {
                "解禁日期": ["2026-06-15"],
                "解禁数量": [1000000],
                "占流通股比例": [1.0],
            }
        )

        fetcher = LockupFetcher()
        result = fetcher.fetch("000001", "平安银行")

        assert result["lockup_risk_level"] == "低风险"
