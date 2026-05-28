"""OpenAI 兼容族客户端（DeepSeek / Qwen / GLM / ModelScope / DashScope / OpenRouter）."""

from __future__ import annotations

import logging
from typing import Any, TypeVar, cast

from openai import OpenAI
from pydantic import BaseModel

from quant_lab.core.net import make_llm_session

from .rate_limit import get_limiter

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleClient:
    """OpenAI 兼容 API 的通用封装.

    支持所有 OpenAI-compatible endpoint（ModelScope、DashScope、OpenRouter 等）。
    通过 ``make_llm_session()`` 创建 ``httpx.Client`` 显式禁用系统代理，
    避免 Clash 等工具把国内 API 误路由到海外节点。
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout: float = 180.0,
        provider: str = "",
    ) -> None:
        self._model = model
        self._timeout = timeout
        self._limiter = get_limiter(provider) if provider else None

        http_client = make_llm_session(timeout=timeout)
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            http_client=http_client,
        )

    @property
    def model_name(self) -> str:
        return self._model

    def chat(
        self,
        prompt: str,
        *,
        schema: type[T] | None = None,
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> str | T:
        if schema is not None:
            try:
                return self._chat_structured(prompt, schema, temperature)
            except Exception:
                logger.warning(
                    "Structured output failed for %s, falling back to free text",
                    self._model,
                )
        return self._chat_free_text(prompt, temperature)

    def _chat_structured(
        self,
        prompt: str,
        schema: type[T],
        temperature: float,
    ) -> T:
        if self._limiter:
            self._limiter.acquire()
        completion = self._client.beta.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": "请按指定 JSON Schema 输出结果。"},
                {"role": "user", "content": prompt},
            ],
            response_format=schema,
            temperature=temperature,
        )
        parsed = cast(T | None, completion.choices[0].message.parsed)
        if parsed is None:
            raise RuntimeError("OpenAI parse returned None")
        return parsed

    def _chat_free_text(self, prompt: str, temperature: float) -> str:
        if self._limiter:
            self._limiter.acquire()
        completion = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一位资深量化分析师，请用自然语言输出分析结论。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        return completion.choices[0].message.content or ""


class DeepSeekClient(OpenAICompatibleClient):
    """DeepSeek 专用客户端，额外处理 reasoning_content.

    DeepSeek R1 等 thinking-mode 模型会在 ``message.reasoning_content`` 中
    返回思维链内容。此子类在日志中记录 reasoning_content 长度，便于调试。
    """

    def _chat_free_text(self, prompt: str, temperature: float) -> str:
        if self._limiter:
            self._limiter.acquire()
        completion = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一位资深量化分析师，请用自然语言输出分析结论。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        msg = completion.choices[0].message
        content = msg.content or ""

        # DeepSeek thinking-mode: record reasoning chain length
        reasoning = getattr(msg, "reasoning_content", None)
        if reasoning:
            logger.debug(
                "DeepSeek reasoning_content length: %d chars",
                len(reasoning),
            )
        return content
