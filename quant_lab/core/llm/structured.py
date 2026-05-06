"""Structured-output 工具：优先 schema，失败降级自由文本."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from .base import LLMClient

logger = logging.getLogger(__name__)


def invoke_structured_or_freetext[T: BaseModel](
    client: LLMClient,
    prompt: str,
    schema: type[T],
    *,
    temperature: float = 0.3,
    max_retries: int = 1,
) -> T | str:
    """尝试以 structured-output 模式调用 LLM；失败时降级为自由文本.

    Args:
        client: 符合 LLMClient Protocol 的客户端实例.
        prompt: 发送给模型的 prompt.
        schema: 期望输出的 Pydantic schema 类.
        temperature: 采样温度.
        max_retries: 结构化失败后的重试次数.

    Returns:
        若结构化成功返回 schema 实例；否则返回原始自由文本字符串.
    """
    # 1. 尝试 structured output
    for attempt in range(1, max_retries + 1):
        try:
            result = client.chat(
                prompt,
                schema=schema,
                temperature=temperature,
            )
            if isinstance(result, schema):
                logger.debug(
                    "Structured output succeeded for %s on attempt %d",
                    schema.__name__,
                    attempt,
                )
                return result
        except Exception as exc:
            logger.warning(
                "Structured output failed for %s (attempt %d/%d): %s",
                schema.__name__,
                attempt,
                max_retries,
                type(exc).__name__,
            )

    # 2. 降级：自由文本
    logger.info(
        "Falling back to free-text for %s after %d failed attempts",
        schema.__name__,
        max_retries,
    )
    try:
        return client.chat(prompt, temperature=temperature)
    except Exception as exc:
        logger.error("Free-text fallback also failed: %s", type(exc).__name__)
        raise
