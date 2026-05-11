"""InvokeLLMStep — 调用 LLM 生成分析结果."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from quant_lab.core.llm.factory import create_client
from quant_lab.core.llm.structured import invoke_structured_or_freetext
from quant_lab.core.pipeline.base import PipelineStep
from quant_lab.core.pipeline.state import AnalysisState
from quant_lab.core.schemas import StockAnalysis

logger = logging.getLogger(__name__)


class InvokeLLMStep(PipelineStep):
    """调用 LLM 生成分析结果.

    Args:
        provider: LLM provider 名称.
        model: 模型 ID；*None* 时使用 provider 默认模型.
        temperature: 采样温度.
        structured: 是否尝试结构化输出 (StockAnalysis schema).
        deep_model: 深度分析时使用的模型（覆盖 *model*）。
    """

    name = "invoke_llm"

    def __init__(
        self,
        provider: str,
        model: str | None = None,
        *,
        temperature: float = 0.3,
        structured: bool = True,
        deep_model: str | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.structured = structured
        self.deep_model = deep_model

    def run(self, state: AnalysisState) -> AnalysisState:
        prompt = state.prompt
        if not prompt:
            logger.warning("⚠️ Prompt 为空，跳过 LLM 调用")
            return self._stamp(state, "invoke_llm")

        model = self.model
        if state.need_deep_analysis and self.deep_model:
            model = self.deep_model
            logger.info("🧠 深度分析使用模型: %s", model)

        client = create_client(self.provider, model=model)

        if self.structured:
            logger.debug("🎯 尝试结构化输出 (StockAnalysis)")
            result = invoke_structured_or_freetext(
                client,
                prompt,
                StockAnalysis,
                temperature=self.temperature,
            )
            if isinstance(result, BaseModel):
                return self._stamp(
                    state.model_copy(
                        update={
                            "response": result.core_logic or "",
                            "structured_output": result,
                        }
                    ),
                    "invoke_llm",
                )
            # fallback to free text
            return self._stamp(
                state.model_copy(update={"response": result}),
                "invoke_llm",
            )

        # free-text only
        response = client.chat(prompt, temperature=self.temperature)
        return self._stamp(
            state.model_copy(update={"response": response}),
            "invoke_llm",
        )
