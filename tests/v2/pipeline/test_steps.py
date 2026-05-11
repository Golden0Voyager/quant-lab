"""Tests for pipeline steps."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quant_lab.core.pipeline.state import AnalysisState
from quant_lab.core.pipeline.steps.build_prompt import BuildPromptStep
from quant_lab.core.pipeline.steps.evaluate_signals import EvaluateSignalsStep
from quant_lab.core.pipeline.steps.fetch_data import FetchDataStep
from quant_lab.core.pipeline.steps.invoke_llm import InvokeLLMStep
from quant_lab.core.pipeline.steps.save_report import SaveReportStep
from quant_lab.core.pipeline.steps.store_memory import StoreMemoryStep


class TestFetchDataStep:
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_fetch_without_cache(self, mock_agg: MagicMock) -> None:
        mock_agg.return_value = {"pe_ttm": "15.2", "name": "平安银行"}
        step = FetchDataStep(use_cache=False)
        state = AnalysisState(symbol="000001", stock_name="平安银行")
        result = step.run(state)

        assert result.raw_data["pe_ttm"] == "15.2"
        assert result.stage == "fetch_data"
        mock_agg.assert_called_once_with("000001", "平安银行", asset_type="stock")

    @patch("quant_lab.core.pipeline.steps.fetch_data.DataCacheFacade")
    @patch("quant_lab.core.pipeline.steps.fetch_data.aggregate")
    def test_fetch_with_cache_hit(self, mock_agg: MagicMock, mock_cache_cls: MagicMock) -> None:
        cache = MagicMock()
        cache.get.return_value = {"cached": True}
        mock_cache_cls.return_value = cache

        step = FetchDataStep(use_cache=True)
        state = AnalysisState(symbol="000001", stock_name="平安银行")
        result = step.run(state)

        assert result.raw_data == {"cached": True}
        mock_agg.assert_not_called()


class TestEvaluateSignalsStep:
    def test_no_signals(self) -> None:
        step = EvaluateSignalsStep()
        state = AnalysisState(
            symbol="000001",
            stock_name="平安银行",
            raw_data={"money_summary": "正常"},
        )
        result = step.run(state)
        assert result.signal_score == 0
        assert result.need_deep_analysis is False

    def test_volume_alert_signal(self) -> None:
        step = EvaluateSignalsStep()
        state = AnalysisState(
            symbol="000001",
            stock_name="平安银行",
            raw_data={"volume_alert": "量比异动"},
        )
        result = step.run(state)
        assert result.signal_score == 2
        assert result.need_deep_analysis is False

    def test_multiple_signals_trigger_deep(self) -> None:
        step = EvaluateSignalsStep()
        state = AnalysisState(
            symbol="000001",
            stock_name="平安银行",
            raw_data={
                "volume_alert": "量比异动",
                "holder_trend": "筹码集中，大户吸筹",
                "money_summary": "✅ 主力净流入 15亿",
                "market_cap_yi": 100,
            },
        )
        result = step.run(state)
        assert result.signal_score >= 3
        assert result.need_deep_analysis is True
        assert len(result.triggers) >= 3


class TestBuildPromptStep:
    def test_worker_prompt(self) -> None:
        step = BuildPromptStep()
        state = AnalysisState(
            symbol="000001",
            stock_name="平安银行",
            raw_data={
                "name": "平安银行",
                "code": "000001",
                "tech_summary": "均线多头排列",
                "money_summary": "主力净流入",
            },
            need_deep_analysis=False,
        )
        result = step.run(state)
        assert "平安银行" in result.prompt
        assert "均线多头排列" in result.prompt
        assert "300字以内" in result.prompt

    def test_brain_prompt(self) -> None:
        step = BuildPromptStep(prompt_version="professional")
        state = AnalysisState(
            symbol="000001",
            stock_name="平安银行",
            raw_data={
                "name": "平安银行",
                "code": "000001",
                "tech_summary": "均线多头排列",
                "valuation_summary": "PE 15倍",
            },
            need_deep_analysis=True,
        )
        result = step.run(state)
        assert "深度研判" in result.prompt
        assert "投资评级" in result.prompt
        assert "PE 15倍" in result.prompt


class TestInvokeLLMStep:
    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    def test_free_text(self, mock_create: MagicMock) -> None:
        client = MagicMock()
        client.chat.return_value = "这是一个分析结果"
        mock_create.return_value = client

        step = InvokeLLMStep(provider="modelscope", structured=False)
        state = AnalysisState(
            symbol="000001",
            stock_name="平安银行",
            prompt="分析平安银行",
        )
        result = step.run(state)
        assert result.response == "这是一个分析结果"
        client.chat.assert_called_once()

    @patch("quant_lab.core.pipeline.steps.invoke_llm.create_client")
    def test_empty_prompt(self, mock_create: MagicMock) -> None:
        step = InvokeLLMStep(provider="modelscope", structured=False)
        state = AnalysisState(symbol="000001", stock_name="平安银行", prompt="")
        result = step.run(state)
        assert result.response == ""
        mock_create.assert_not_called()


class TestSaveReportStep:
    @patch("quant_lab.core.pipeline.steps.save_report._md_to_pdf", return_value=False)
    @patch("builtins.open")
    @patch("os.makedirs")
    def test_save_markdown(self, mock_makedirs: MagicMock, mock_open: MagicMock, mock_pdf: MagicMock) -> None:
        step = SaveReportStep(report_dir="/tmp/test_reports")
        state = AnalysisState(
            symbol="000001",
            stock_name="平安银行",
            raw_data={"money_summary": "流入", "tech_summary": "多头", "news_summary": "正面"},
            response="分析结果",
            need_deep_analysis=False,
        )
        result = step.run(state)
        assert result.report_path is not None
        assert "平安银行" in result.report_path
        mock_makedirs.assert_called_once()
        mock_open.assert_called_once()


class TestStoreMemoryStep:
    def test_store(self) -> None:
        cache = MagicMock()
        step = StoreMemoryStep(cache=cache)
        state = AnalysisState(
            symbol="000001",
            stock_name="平安银行",
            raw_data={"pe": 15},
            signal_score=3,
            response="分析结果",
        )
        result = step.run(state)
        assert result.stage == "store_memory"
        cache.set.assert_called()
        # First call: extended cache
        assert cache.set.call_args_list[0][0][0] == "extended"
        assert cache.set.call_args_list[0][0][1] == "000001"
