"""End-to-end tests for the full pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quant_lab.core.pipeline.builders import (
    build_auto_pipeline,
    build_deep_pipeline,
    build_fast_pipeline,
)
from quant_lab.core.pipeline.runner import PipelineRunner
from quant_lab.core.pipeline.state import AnalysisState


class TestAutoPipelineE2E:
    """Tests the full auto-mode pipeline with mocked external deps."""

    @patch("quant_lab.core.pipeline.steps.save_report._md_to_pdf", return_value=False)
    @patch("builtins.open")
    @patch("os.makedirs")
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_worker_path(
        self,
        mock_agg: MagicMock,
        mock_create_client: MagicMock,
        mock_makedirs: MagicMock,
        mock_open: MagicMock,
        mock_pdf: MagicMock,
    ) -> None:
        """Signal score < 3 → worker quick analysis path."""
        mock_agg.return_value = {
            "name": "平安银行",
            "code": "000001",
            "type": "stock",
            "tech_summary": "均线多头排列",
            "money_summary": "正常",
            "smart_money_summary": "北向连续3日流入",
            "volume_alert": "正常",
        }

        client = MagicMock()
        client.chat.return_value = "Worker 快速分析结果"
        mock_create_client.return_value = client

        cache = MagicMock()
        cache.get.return_value = None

        steps = build_auto_pipeline(
            provider="modelscope",
            model="deepseek-v3",
            deep_model="deepseek-r1",
            use_cache=True,
            cache=cache,
        )
        runner = PipelineRunner(steps)
        initial = AnalysisState(symbol="000001", stock_name="平安银行")
        result = runner.run(initial)

        # Verify completed all steps
        assert len(result.completed_steps) == 6
        assert result.failed_steps == []

        # Verify state transitions
        assert result.state.stage == "store_memory"
        assert result.state.raw_data["tech_summary"] == "均线多头排列"
        assert result.state.signal_score < 3
        assert result.state.need_deep_analysis is False
        assert "300字以内" in result.state.prompt
        assert result.state.response == "Worker 快速分析结果"
        assert result.state.report_path is not None
        assert "平安银行" in result.state.report_path

        # Verify timestamps recorded for each stage
        for step_name in result.completed_steps:
            assert step_name in result.state.timestamps

        # Verify LLM called with worker model
        mock_create_client.assert_called_once_with("modelscope", model="deepseek-v3")

    @patch("quant_lab.core.pipeline.steps.save_report._md_to_pdf", return_value=False)
    @patch("builtins.open")
    @patch("os.makedirs")
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_brain_path(
        self,
        mock_agg: MagicMock,
        mock_create_client: MagicMock,
        mock_makedirs: MagicMock,
        mock_open: MagicMock,
        mock_pdf: MagicMock,
    ) -> None:
        """Signal score >= 3 → brain deep analysis path."""
        mock_agg.return_value = {
            "name": "平安银行",
            "code": "000001",
            "type": "stock",
            "tech_summary": "均线多头排列",
            "money_summary": "✅ 主力净流入 15亿",
            "smart_money_summary": "北向连续3日流入",
            "volume_alert": "量比异动",
            "holder_trend": "筹码集中，大户吸筹",
            "market_cap_yi": 100,
            "valuation_summary": "PE 15倍",
            "pe_percentile": "25%",
            "pb_percentile": "75%",
            "pe_ttm": "15.2",
            "pb": "1.2",
        }

        client = MagicMock()
        client.chat.return_value = "Brain 深度分析结果"
        mock_create_client.return_value = client

        cache = MagicMock()
        cache.get.return_value = None

        steps = build_auto_pipeline(
            provider="modelscope",
            model="deepseek-v3",
            deep_model="deepseek-r1",
            use_cache=True,
            cache=cache,
        )
        runner = PipelineRunner(steps)
        initial = AnalysisState(symbol="000001", stock_name="平安银行")
        result = runner.run(initial)

        # Verify brain path taken
        assert result.state.signal_score >= 3
        assert result.state.need_deep_analysis is True
        assert "深度研判" in result.state.prompt
        assert result.state.response == "Brain 深度分析结果"

        # Verify deep model used
        mock_create_client.assert_called_once_with("modelscope", model="deepseek-r1")

        # Verify report saved
        assert result.state.report_path is not None
        assert "deep" in result.state.report_path


class TestDeepPipelineE2E:
    @patch("quant_lab.core.pipeline.steps.save_report._md_to_pdf", return_value=False)
    @patch("builtins.open")
    @patch("os.makedirs")
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_forces_brain(
        self,
        mock_agg: MagicMock,
        mock_create_client: MagicMock,
        mock_makedirs: MagicMock,
        mock_open: MagicMock,
        mock_pdf: MagicMock,
    ) -> None:
        """build_deep_pipeline always forces deep analysis regardless of signals."""
        mock_agg.return_value = {
            "name": "平安银行",
            "code": "000001",
            "type": "stock",
            "tech_summary": "正常",
            "money_summary": "正常",
        }

        client = MagicMock()
        client.chat.return_value = "强制深度分析"
        mock_create_client.return_value = client

        steps = build_deep_pipeline(provider="modelscope", model="qwen-max")
        runner = PipelineRunner(steps)
        initial = AnalysisState(symbol="000001", stock_name="平安银行")
        result = runner.run(initial)

        assert result.state.need_deep_analysis is True
        assert result.state.signal_score == 99
        assert result.state.triggers == ["用户指定深度分析"]
        assert "深度研判" in result.state.prompt
        mock_create_client.assert_called_once_with("modelscope", model="qwen-max")


class TestFastPipelineE2E:
    @patch("quant_lab.core.pipeline.steps.save_report._md_to_pdf", return_value=False)
    @patch("builtins.open")
    @patch("os.makedirs")
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_forces_worker(
        self,
        mock_agg: MagicMock,
        mock_create_client: MagicMock,
        mock_makedirs: MagicMock,
        mock_open: MagicMock,
        mock_pdf: MagicMock,
    ) -> None:
        """build_fast_pipeline always uses worker and unstructured output."""
        mock_agg.return_value = {
            "name": "平安银行",
            "code": "000001",
            "type": "stock",
            "tech_summary": "均线多头排列",
            "money_summary": "✅ 主力净流入 15亿",
            "volume_alert": "量比异动",
            "market_cap_yi": 100,
        }

        client = MagicMock()
        client.chat.return_value = "快速分析"
        mock_create_client.return_value = client

        steps = build_fast_pipeline(provider="modelscope", model="deepseek-v3")
        runner = PipelineRunner(steps)
        initial = AnalysisState(symbol="000001", stock_name="平安银行")
        result = runner.run(initial)

        assert result.state.need_deep_analysis is False
        assert result.state.signal_score == 0
        assert "300字以内" in result.state.prompt
        # Verify unstructured (structured=False)
        client.chat.assert_called_once()
        _, kwargs = client.chat.call_args
        assert "schema" not in kwargs


class TestPipelineErrorHandlingE2E:
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_continue_on_fetch_failure(
        self,
        mock_agg: MagicMock,
        mock_create_client: MagicMock,
    ) -> None:
        """Even if aggregate returns empty data, pipeline should complete gracefully."""
        mock_agg.return_value = {}

        client = MagicMock()
        client.chat.return_value = ""
        mock_create_client.return_value = client

        steps = build_fast_pipeline(
            provider="modelscope",
            model="deepseek-v3",
            use_cache=False,
        )
        runner = PipelineRunner(steps, abort_on_error=False)
        initial = AnalysisState(symbol="000001", stock_name="平安银行")
        result = runner.run(initial)

        # All steps attempted
        assert len(result.completed_steps) == 6
        assert result.failed_steps == []
        assert result.state.error is None
