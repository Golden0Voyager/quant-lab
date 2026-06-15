"""Tests for quant_lab.core.memory.migration."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

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

    def test_fallback_to_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            date_dir = os.path.join(tmpdir, "notadate")
            os.makedirs(date_dir)
            path = os.path.join(date_dir, "100000_平安银行_fast.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# 平安银行（000001）投资分析\n")
            parsed = _parse_report_file(path)
            assert parsed is not None
            assert parsed["symbol"] == "000001"

    def test_fallback_to_6digit_code_in_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            date_dir = os.path.join(tmpdir, "260527")
            os.makedirs(date_dir)
            path = os.path.join(date_dir, "100000_某股票_fast.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("某只股票 002594 的分析\n")
            parsed = _parse_report_file(path)
            assert parsed is not None
            assert parsed["symbol"] == "002594"

    def test_no_symbol_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            date_dir = os.path.join(tmpdir, "260527")
            os.makedirs(date_dir)
            path = os.path.join(date_dir, "100000_某股票_fast.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("没有任何代码的分析\n")
            parsed = _parse_report_file(path)
            assert parsed is None

    def test_rating_pattern_strong_buy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            date_dir = os.path.join(tmpdir, "260527")
            os.makedirs(date_dir)
            path = os.path.join(date_dir, "100000_平安银行_fast.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# 平安银行（000001）\n投资评级：强烈买入\n")
            parsed = _parse_report_file(path)
            assert parsed is not None
            assert parsed["rating"] == "强烈买入"

    def test_rating_pattern_english(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            date_dir = os.path.join(tmpdir, "260527")
            os.makedirs(date_dir)
            path = os.path.join(date_dir, "100000_平安银行_fast.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# 平安银行（000001）\nrating: STRONG_BUY\n")
            parsed = _parse_report_file(path)
            assert parsed is not None
            assert parsed["rating"] == "STRONG_BUY"

    def test_confidence_parse_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            date_dir = os.path.join(tmpdir, "260527")
            os.makedirs(date_dir)
            path = os.path.join(date_dir, "100000_平安银行_fast.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# 平安银行（000001）\n置信度: abc\n")
            parsed = _parse_report_file(path)
            assert parsed is not None
            assert parsed["confidence"] is None

    def test_read_error_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            date_dir = os.path.join(tmpdir, "260527")
            os.makedirs(date_dir)
            path = os.path.join(date_dir, "100000_平安银行_fast.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# 平安银行（000001）\n")
            os.chmod(path, 0o000)
            try:
                parsed = _parse_report_file(path)
                assert parsed is None
            finally:
                os.chmod(path, 0o644)

    def test_confidence_parse_exception(self, tmp_path: object) -> None:
        report_dir = os.path.join(str(tmp_path), "250101")
        os.makedirs(report_dir)
        f = os.path.join(report_dir, "120000_平安银行_fast.md")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("# 平安银行（000001）\n\n评级：买入\n置信度：abc\n")
        result = _parse_report_file(f)
        assert result is not None
        assert result["confidence"] is None


class TestRunMigration:
    """Tests for ``run_migration``."""

    def test_dry_run_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
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

    def test_report_root_not_exist(self) -> None:
        from quant_lab.core.memory import migration

        orig_root = migration.REPORT_ROOT
        migration.REPORT_ROOT = "/nonexistent/path"
        try:
            stats = run_migration()
            assert stats["total"] == 0
        finally:
            migration.REPORT_ROOT = orig_root

    def test_skips_non_date_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "notadate"))
            from quant_lab.core.memory import migration

            orig_root = migration.REPORT_ROOT
            migration.REPORT_ROOT = tmpdir
            try:
                stats = run_migration(dry_run=True)
                assert stats["total"] == 0
            finally:
                migration.REPORT_ROOT = orig_root

    def test_skips_non_md_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            date_dir = os.path.join(tmpdir, "260527")
            os.makedirs(date_dir)
            with open(os.path.join(date_dir, "100000_平安银行_fast.txt"), "w") as f:
                f.write("test")
            from quant_lab.core.memory import migration

            orig_root = migration.REPORT_ROOT
            migration.REPORT_ROOT = tmpdir
            try:
                stats = run_migration(dry_run=True)
                assert stats["total"] == 0
            finally:
                migration.REPORT_ROOT = orig_root

    def test_skips_non_dir_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "260527.txt"), "w") as f:
                f.write("not a dir")
            from quant_lab.core.memory import migration

            orig_root = migration.REPORT_ROOT
            migration.REPORT_ROOT = tmpdir
            try:
                stats = run_migration(dry_run=True)
                assert stats["total"] == 0
            finally:
                migration.REPORT_ROOT = orig_root

    def test_skipped_unparsable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            date_dir = os.path.join(tmpdir, "260527")
            os.makedirs(date_dir)
            with open(os.path.join(date_dir, "bad_name.md"), "w") as f:
                f.write("test")
            from quant_lab.core.memory import migration

            orig_root = migration.REPORT_ROOT
            migration.REPORT_ROOT = tmpdir
            try:
                stats = run_migration(dry_run=True)
                assert stats["total"] == 1
                assert stats["skipped"] == 1
            finally:
                migration.REPORT_ROOT = orig_root

    def test_actual_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            date_dir = os.path.join(tmpdir, "260527")
            os.makedirs(date_dir)
            path = os.path.join(date_dir, "100000_平安银行_fast.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# 平安银行（000001）投资分析\n评级: 买入\n")
            from quant_lab.core.memory import migration

            orig_root = migration.REPORT_ROOT
            migration.REPORT_ROOT = tmpdir
            try:
                stats = run_migration(dry_run=False)
                assert stats["total"] == 1
                assert stats["imported"] == 1
            finally:
                migration.REPORT_ROOT = orig_root

    def test_import_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            date_dir = os.path.join(tmpdir, "260527")
            os.makedirs(date_dir)
            path = os.path.join(date_dir, "100000_平安银行_fast.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# 平安银行（000001）投资分析\n")
            from quant_lab.core.memory import migration

            orig_root = migration.REPORT_ROOT
            migration.REPORT_ROOT = tmpdir
            try:
                with patch(
                    "quant_lab.core.memory.migration.AnalysisMemoryLog"
                ) as mock_log_cls:
                    mock_log = MagicMock()
                    mock_log.store_decision.side_effect = Exception("DB error")
                    mock_log_cls.return_value = mock_log
                    stats = run_migration(dry_run=False)
                    assert stats["errors"] == 1
            finally:
                migration.REPORT_ROOT = orig_root


class TestMain:
    def test_main_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            from quant_lab.core.memory import migration

            orig_root = migration.REPORT_ROOT
            migration.REPORT_ROOT = tmpdir
            try:
                with patch("sys.argv", ["migration", "--dry-run"]):
                    migration.main()
                output_path = os.path.join(tmpdir, "migration_report.json")
                assert os.path.exists(output_path)
            finally:
                migration.REPORT_ROOT = orig_root

    def test_main_function(self, tmp_path: object) -> None:
        from quant_lab.core.memory.migration import main

        report_dir = os.path.join(str(tmp_path), "Report")
        os.makedirs(report_dir)
        with patch("quant_lab.core.memory.migration.REPORT_ROOT", report_dir), \
             patch("builtins.print"):
            import sys
            old_argv = sys.argv
            sys.argv = ["migration", "--dry-run"]
            try:
                main()
            finally:
                sys.argv = old_argv
