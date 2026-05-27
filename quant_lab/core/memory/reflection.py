"""Reflection generator — T+1 learning via quick LLM call."""

from __future__ import annotations

import logging
from typing import Any

from quant_lab.core.llm.factory import create_client

logger = logging.getLogger(__name__)


class Reflector:
    """Generate a concise reflection on a past analysis decision.

    Args:
        provider: LLM provider name.
        model: Model ID; *None* uses the provider default.
    """

    def __init__(
        self,
        provider: str = "modelscope",
        model: str | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self._client = create_client(provider, model=model)

    def reflect_on_decision(
        self,
        decision: dict[str, Any],
        raw_return: float,
        alpha_return: float,
    ) -> str:
        """Ask the LLM for a 1-2 sentence reflection.

        The prompt includes the original rating, confidence, triggers,
        and the realised return vs. the CSI 300 benchmark (alpha).

        Returns:
            Free-text reflection (empty string on failure).
        """
        symbol = decision.get("symbol", "unknown")
        date = decision.get("date", "unknown")
        rating = decision.get("rating", "N/A")
        confidence = decision.get("confidence", "N/A")
        triggers = decision.get("triggers", "[]")
        if isinstance(triggers, str):
            import json
            try:
                triggers = json.loads(triggers)
            except Exception:
                triggers = []

        prompt = f"""你是一位量化交易复盘助手。请对以下历史决策进行一句话反思。

标的: {symbol}
决策日期: {date}
评级: {rating}
置信度: {confidence}
触发信号: {', '.join(triggers) if triggers else '无'}
实际收益: {raw_return * 100:.2f}%
相对沪深300 Alpha: {alpha_return * 100:.2f}%

请用1-2句话总结：
1. 这个判断对了还是错了？关键原因是什么？
2. 下次遇到类似信号时应该怎么做？

保持简洁，不超过100字。"""

        try:
            response = self._client.chat(prompt, temperature=0.3)
            reflection = response.strip() if response else ""
            logger.info("🧠 Reflection generated for %s: %s", symbol, reflection[:60])
            return reflection
        except Exception as exc:
            logger.warning("Reflection generation failed: %s", exc)
            return ""
