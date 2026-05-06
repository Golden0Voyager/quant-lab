"""Anthropic 客户端（原生 SDK 封装）."""

from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

from pydantic import BaseModel

try:
    from anthropic import Anthropic
except ImportError as _import_exc:
    Anthropic = None  # type: ignore[misc,assignment]
    _IMPORT_ERROR = _import_exc


logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class AnthropicClient:
    """Anthropic SDK 封装，适配 LLMClient Protocol.

    结构化输出通过 system prompt 强制 JSON + Pydantic 校验实现；
    若校验失败则降级为自由文本。
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 180.0,
    ) -> None:
        if Anthropic is None:
            raise RuntimeError(
                "anthropic SDK is not installed. "
                "Run: uv pip install anthropic"
            ) from _IMPORT_ERROR

        self._model = model
        self._timeout = timeout
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = Anthropic(**kwargs)

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
                    "Anthropic structured output failed for %s, "
                    "falling back to free text",
                    self._model,
                )
        return self._chat_free_text(prompt, temperature)

    def _chat_structured(
        self,
        prompt: str,
        schema: type[T],
        temperature: float,
    ) -> T:
        system = (
            "你必须以有效的 JSON 对象回复，严格匹配以下 schema:\n"
            f"{schema.model_json_schema()}"
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = self._extract_text(response)
        data = json.loads(text)
        return schema(**data)

    def _chat_free_text(self, prompt: str, temperature: float) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._extract_text(response)

    @staticmethod
    def _extract_text(response: Any) -> str:
        for block in response.content:
            text: str = getattr(block, "text", "")
            if text:
                return text
        raise RuntimeError("No text block found in Anthropic response")
