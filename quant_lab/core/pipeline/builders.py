"""Pipeline builders — pre-configured pipelines for each analysis mode."""

from __future__ import annotations

from quant_lab.core.data.cache import DataCacheFacade
from quant_lab.core.pipeline.base import PipelineStep
from quant_lab.core.pipeline.state import AnalysisState
from quant_lab.core.pipeline.steps.build_prompt import BuildPromptStep
from quant_lab.core.pipeline.steps.evaluate_signals import EvaluateSignalsStep
from quant_lab.core.pipeline.steps.fetch_data import FetchDataStep
from quant_lab.core.pipeline.steps.invoke_llm import InvokeLLMStep
from quant_lab.core.pipeline.steps.save_report import SaveReportStep
from quant_lab.core.pipeline.steps.store_memory import StoreMemoryStep


def build_auto_pipeline(
    provider: str = "modelscope",
    model: str | None = None,
    deep_model: str | None = None,
    prompt_version: str = "professional",
    use_cache: bool = True,
    cache: DataCacheFacade | None = None,
) -> list[PipelineStep]:
    """自动模式 pipeline：先评估信号，再决定 worker / brain.

    Args:
        provider: LLM provider.
        model: 默认模型（用于 worker 和未触发深度的场景）.
        deep_model: 深度分析专用模型；*None* 时与 *model* 相同.
        prompt_version: Brain prompt 风格.
        use_cache: 是否使用数据缓存.
        cache: 可选的缓存实例.
    """
    return [
        FetchDataStep(use_cache=use_cache, cache=cache),
        EvaluateSignalsStep(),
        BuildPromptStep(prompt_version=prompt_version),
        InvokeLLMStep(
            provider=provider,
            model=model,
            deep_model=deep_model,
        ),
        SaveReportStep(),
        StoreMemoryStep(cache=cache),
    ]


def build_deep_pipeline(
    provider: str = "modelscope",
    model: str | None = None,
    deep_model: str | None = None,
    prompt_version: str = "professional",
    use_cache: bool = True,
    cache: DataCacheFacade | None = None,
) -> list[PipelineStep]:
    """强制深度分析 pipeline（跳过信号评估，直接走 brain）."""
    return [
        FetchDataStep(use_cache=use_cache, cache=cache),
        _ForceDeepStep(),
        BuildPromptStep(prompt_version=prompt_version),
        InvokeLLMStep(provider=provider, model=model),
        SaveReportStep(),
        StoreMemoryStep(cache=cache),
    ]


def build_fast_pipeline(
    provider: str = "modelscope",
    model: str | None = None,
    deep_model: str | None = None,
    prompt_version: str = "professional",
    use_cache: bool = True,
    cache: DataCacheFacade | None = None,
) -> list[PipelineStep]:
    """快速分析 pipeline（跳过信号评估，直接走 worker）."""
    return [
        FetchDataStep(use_cache=use_cache, cache=cache),
        _SkipDeepStep(),
        BuildPromptStep(),
        InvokeLLMStep(provider=provider, model=model, structured=False),
        SaveReportStep(),
        StoreMemoryStep(cache=cache),
    ]


class _ForceDeepStep(PipelineStep):
    """内部 step：强制设置 need_deep_analysis=True."""

    name = "force_deep"

    def run(self, state: AnalysisState) -> AnalysisState:
        return self._stamp(
            state.model_copy(
                update={
                    "need_deep_analysis": True,
                    "signal_score": 99,
                    "triggers": ["用户指定深度分析"],
                }
            ),
            "force_deep",
        )


class _SkipDeepStep(PipelineStep):
    """内部 step：强制设置 need_deep_analysis=False."""

    name = "skip_deep"

    def run(self, state: AnalysisState) -> AnalysisState:
        return self._stamp(
            state.model_copy(
                update={
                    "need_deep_analysis": False,
                    "signal_score": 0,
                    "triggers": [],
                }
            ),
            "skip_deep",
        )
