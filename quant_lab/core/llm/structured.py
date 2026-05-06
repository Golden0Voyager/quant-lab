"""Structured-output 工具：优先 schema，失败降级自由文本."""

from __future__ import annotations

import logging
from typing import Any, cast

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def invoke_structured_or_freetext[T: BaseModel](
    client: Any,
    prompt: str,
    schema: type[T],
    *,
    temperature: float = 0.3,
    max_retries: int = 1,
) -> T | str:
    """尝试以 structured-output 模式调用 LLM；失败时降级为自由文本.

    Args:
        client: 已初始化的 LLM 客户端 (需支持 ``client.beta.chat.completions.parse`` 或
            通过 ``client.chat.completions.create(response_format=...)`` 输出结构化结果).
        prompt: 发送给模型的 prompt.
        schema: 期望输出的 Pydantic schema 类.
        temperature: 采样温度.
        max_retries: 结构化失败后的重试次数.

    Returns:
        若结构化成功返回 schema 实例；否则返回原始自由文本字符串.
    """
    model_name: str = getattr(client, "_model", "")

    # 1. 尝试 structured output (OpenAI SDK ≥ 1.8 的 parse API)
    for attempt in range(1, max_retries + 1):
        try:
            completion = client.beta.chat.completions.parse(
                model=model_name,
                messages=[
                    {"role": "system", "content": "请按指定 JSON Schema 输出结果。"},
                    {"role": "user", "content": prompt},
                ],
                response_format=schema,
                temperature=temperature,
            )
            parsed = cast(T | None, completion.choices[0].message.parsed)
            if parsed is not None:
                logger.debug(
                    "Structured output succeeded for %s on attempt %d",
                    schema.__name__,
                    attempt,
                )
                return parsed
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
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": "你是一位资深量化分析师，请用自然语言输出分析结论。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        content: str = completion.choices[0].message.content or ""
        return content
    except Exception as exc:
        logger.error("Free-text fallback also failed: %s", type(exc).__name__)
        raise
