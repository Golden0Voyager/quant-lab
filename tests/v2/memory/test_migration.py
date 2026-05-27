"""Tests for quant_lab.core.memory.migration."""

from __future__ import annotations

import os
import tempfile

import pytest

from quant_lab.core.memory.migration import _parse_report_file, run_migration


class TestParseReportFile:
    """Tests for ``_parse_report_file``."""

    def test_parse_stock_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            date_dir = os.path.join(tmpdir, "260527")
            os.makedirs(date_dir)
            path = os.path.join(date_dir, "100000_平安银行_fast.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# 平安银行（000001）投资分析\n\n")
                f.write("> 生成时间: 2026-05-27 10:00:00\n\n")
                f.write("## 数据概览\n")
                f.write("评级: 买入\n")
                f.write("置信度: 0.85\n")

            parsed = _parse_report_file(path)
            assert parsed is not None
            assert parsed["symbol"] == "000001"
            assert parsed["stock_name"] == "平安银行"
            assert parsed["analysis_mode"] == "fast"
            assert parsed["rating"] == "买入"
            assert parsed["confidence"] == 0.85

    def test_parse_valuation_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            date_dir = os.path.join(tmpdir, "260526")
            os.makedirs(date_dir)
            path = os.path.join(date_dir, "175621_蓝晓科技_估值分析.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# 蓝晓科技（300487）估值分析\n")

            parsed = _parse_report_file(path)
            assert parsed is not None
            assert parsed["symbol"] == "300487"
            assert parsed["stock_name"] == "蓝晓科技"
            assert parsed["analysis_mode"] == "估值分析"

    def test_parse_no_symbol(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_fast.md", delete=False, encoding="utf-8"
        ) as f:
            f.write("# 某只股票的分析\n")
            path = f.name

        try:
            parsed = _parse_report_file(path)
            # No 6-digit code in content → should fail to extract symbol
            assert parsed is None
        finally:
            os.unlink(path)

    def test_parse_unmatched_filename(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("# 000001\n")
            path = f.name

        try:
            parsed = _parse_report_file(path)
            assert parsed is None
        finally:
            os.unlink(path)


class TestRunMigration:
    """Tests for ``run_migration``."""

    def test_dry_run_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Patch REPORT_ROOT temporarily
            from quant_lab.core.memory import migration
            orig_root = migration.REPORT_ROOT
            migration.REPORT_ROOT = tmpdir
            try:
                stats = run_migration(dry_run=True)
                assert stats["total"] == 0
                assert stats["imported"] == 0
            finally:
                migration.REPORT_ROOT = orig_root

    def test_dry_run_imports_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            date_dir = os.path.join(tmpdir, "260527")
            os.makedirs(date_dir)
            with open(os.path.join(date_dir, "100000_平安银行_fast.md"), "w", encoding="utf-8") as f:
                f.write("# 平安银行（000001）投资分析\n")

            from quant_lab.core.memory import migration
            orig_root = migration.REPORT_ROOT
            migration.REPORT_ROOT = tmpdir
            try:
                stats = run_migration(dry_run=True)
                assert stats["total"] == 1
                assert stats["imported"] == 1
                assert stats["details"][0]["symbol"] == "000001"
            finally:
                migration.REPORT_ROOT = orig_root
