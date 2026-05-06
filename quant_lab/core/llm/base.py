"""LLM client Protocol definition."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMClient(Protocol):
    """抽象协议：所有 LLM provider 必须实现此接口."""

    @property
    def model_name(self) -> str:
        """返回当前使用的模型名称."""
        ...

    def chat(
        self,
        prompt: str,
        *,
        schema: type[T] | None = None,
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> str | T:
        """发送 prompt 并返回文本或结构化对象.

        Args:
            prompt: 用户 prompt.
            schema: 若提供，尝试返回该 Pydantic schema 的实例.
            temperature: 采样温度.
            **kwargs: provider 特定的额外参数.

        Returns:
            schema 为 None 时返回自由文本字符串；
            schema 不为 None 时返回 schema 实例（若 provider 支持结构化输出）.
        """
        ...
