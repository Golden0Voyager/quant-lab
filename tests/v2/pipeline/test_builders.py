"""Tests for pipeline builders."""

from __future__ import annotations

from quant_lab.core.pipeline.builders import (
    build_auto_pipeline,
    build_deep_pipeline,
    build_fast_pipeline,
)
from quant_lab.core.pipeline.steps.build_prompt import BuildPromptStep
from quant_lab.core.pipeline.steps.evaluate_signals import EvaluateSignalsStep
from quant_lab.core.pipeline.steps.fetch_data import FetchDataStep
from quant_lab.core.pipeline.steps.invoke_llm import InvokeLLMStep
from quant_lab.core.pipeline.steps.save_report import SaveReportStep
from quant_lab.core.pipeline.steps.store_memory import StoreMemoryStep


class TestBuilders:
    def test_build_auto_pipeline(self) -> None:
        steps = build_auto_pipeline(
            provider="modelscope",
            model="deepseek-v3",
            deep_model="deepseek-r1",
        )
        assert len(steps) == 6
        assert isinstance(steps[0], FetchDataStep)
        assert isinstance(steps[1], EvaluateSignalsStep)
        assert isinstance(steps[2], BuildPromptStep)
        assert isinstance(steps[3], InvokeLLMStep)
        assert isinstance(steps[4], SaveReportStep)
        assert isinstance(steps[5], StoreMemoryStep)

        # Verify InvokeLLMStep config
        llm_step = steps[3]
        assert llm_step.provider == "modelscope"
        assert llm_step.model == "deepseek-v3"
        assert llm_step.deep_model == "deepseek-r1"

    def test_build_deep_pipeline(self) -> None:
        steps = build_deep_pipeline()
        assert len(steps) == 6
        assert isinstance(steps[0], FetchDataStep)
        assert isinstance(steps[2], BuildPromptStep)
        assert isinstance(steps[3], InvokeLLMStep)

    def test_build_fast_pipeline(self) -> None:
        steps = build_fast_pipeline()
        assert len(steps) == 6
        assert isinstance(steps[0], FetchDataStep)
        llm_step = steps[3]
        assert llm_step.structured is False
