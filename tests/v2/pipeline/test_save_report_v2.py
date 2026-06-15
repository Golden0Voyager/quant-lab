"""Extended tests for SaveReportStep — covering uncovered branches."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quant_lab.core.pipeline.steps.save_report import SaveReportStep
from tests.v2.helpers import make_analysis_state, make_stock_analysis


class TestSaveReportStepV2:
    def test_structured_output_rendered(self, tmp_path: object) -> None:
        """Lines 75-78: structured_output is StockAnalysis → render."""
        step = SaveReportStep(report_dir="/tmp/test_save_report")
        state = make_analysis_state(response="持有")
        state.structured_output = make_stock_analysis()
        with patch("os.makedirs"), patch("builtins.open", MagicMock()):
            result = step.run(state)
        assert result.report_path is not None

    def test_file_write_exception(self) -> None:
        """Lines 88-90: file write exception → error stamp."""
        step = SaveReportStep(report_dir="/tmp/test_save_report")
        state = make_analysis_state(response="持有")
        with patch("os.makedirs"), \
             patch("builtins.open", side_effect=PermissionError("denied")):
            result = step.run(state)
        assert result.error is not None
        assert "save_report" in result.error
