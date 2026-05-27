"""Tests for quant_lab.core.memory.log."""

from __future__ import annotations

import os
import tempfile

import pytest

from quant_lab.core.memory.log import AnalysisMemoryLog


class TestAnalysisMemoryLog:
    """Tests for ``AnalysisMemoryLog`` CRUD and state machine."""

    @pytest.fixture
    def temp_db(self):
        """Provide a temporary SQLite database path."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        os.unlink(path)

    @pytest.fixture
    def log(self, temp_db: str):
        """Fresh memory log instance backed by a temp DB."""
        return AnalysisMemoryLog(db_path=temp_db)

    def test_store_and_get_pending(self, log: AnalysisMemoryLog) -> None:
        entry_id = log.store_decision(
            symbol="000001",
            stock_name="平安银行",
            date="2026-05-27",
            rating="买入",
            confidence=0.85,
            triggers=["资金异动"],
            analysis_mode="auto",
            report_path="/tmp/report.md",
        )
        assert entry_id is not None
        assert entry_id.isdigit()

        pending = log.get_pending_entries()
        assert len(pending) == 1
        assert pending[0]["symbol"] == "000001"
        assert pending[0]["rating"] == "买入"
        assert pending[0]["status"] == "pending"

    def test_get_pending_filtered_by_symbol(self, log: AnalysisMemoryLog) -> None:
        log.store_decision(symbol="000001", stock_name="A", date="2026-05-27", triggers=[], analysis_mode="fast", report_path="")
        log.store_decision(symbol="000002", stock_name="B", date="2026-05-27", triggers=[], analysis_mode="fast", report_path="")

        pending = log.get_pending_entries(symbol="000001")
        assert len(pending) == 1
        assert pending[0]["symbol"] == "000001"

    def test_resolve_with_outcome(self, log: AnalysisMemoryLog) -> None:
        entry_id = log.store_decision(
            symbol="000001",
            stock_name="平安银行",
            date="2026-05-27",
            rating="买入",
            confidence=0.85,
            triggers=["资金异动"],
            analysis_mode="auto",
            report_path="/tmp/report.md",
        )

        record = log.resolve_with_outcome(
            entry_id=entry_id,
            raw_return=0.05,
            alpha_return=0.02,
            reflection="判断正确，资金持续流入",
        )
        assert record is not None
        assert record["status"] == "resolved"
        assert record["raw_return"] == 0.05
        assert record["alpha_return"] == 0.02
        assert record["reflection"] == "判断正确，资金持续流入"

        # Should no longer appear in pending
        pending = log.get_pending_entries()
        assert len(pending) == 0

    def test_resolve_nonexistent_entry(self, log: AnalysisMemoryLog) -> None:
        result = log.resolve_with_outcome("99999", 0.0, 0.0)
        assert result is None

    def test_past_context(self, log: AnalysisMemoryLog) -> None:
        # Store and resolve a decision
        eid = log.store_decision(
            symbol="000001", stock_name="平安银行", date="2026-05-20",
            rating="买入", confidence=0.8, triggers=["资金流入"],
            analysis_mode="auto", report_path="",
        )
        log.resolve_with_outcome(eid, 0.03, 0.01, "超预期")

        ctx = log.get_past_context("000001", n_same=5, n_cross=0)
        assert "000001" in ctx
        assert "2026-05-20" in ctx
        assert "买入" in ctx
        assert "超预期" in ctx

    def test_past_context_cross_symbol(self, log: AnalysisMemoryLog) -> None:
        eid1 = log.store_decision(
            symbol="000001", stock_name="A", date="2026-05-20",
            rating="买入", triggers=[], analysis_mode="auto", report_path="",
        )
        log.resolve_with_outcome(eid1, 0.05, 0.02)

        eid2 = log.store_decision(
            symbol="000002", stock_name="B", date="2026-05-20",
            rating="持有", triggers=[], analysis_mode="auto", report_path="",
        )
        log.resolve_with_outcome(eid2, -0.01, -0.03)

        ctx = log.get_past_context("000001", n_same=1, n_cross=1)
        assert "000001" in ctx
        assert "000002" in ctx

    def test_past_context_empty(self, log: AnalysisMemoryLog) -> None:
        ctx = log.get_past_context("000001")
        assert ctx == ""

    def test_stats(self, log: AnalysisMemoryLog) -> None:
        log.store_decision(symbol="000001", stock_name="A", date="2026-05-27", triggers=[], analysis_mode="fast", report_path="")
        log.store_decision(symbol="000002", stock_name="B", date="2026-05-27", triggers=[], analysis_mode="fast", report_path="")

        stats = log.get_stats()
        assert stats["total"] == 2
        assert stats["pending"] == 2
        assert stats["resolved"] == 0
        assert stats["symbols"] == 2
