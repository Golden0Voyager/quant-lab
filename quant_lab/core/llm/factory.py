"""LLM 客户端工厂：单一入口创建任意 provider 的客户端."""

from __future__ import annotations

import logging
import os
from typing import Any

from .anthropic import AnthropicClient
from .base import LLMClient
from .catalog import ModelCatalog
from .openai_compat import DeepSeekClient, OpenAICompatibleClient

logger = logging.getLogger(__name__)


def create_client(
    provider: str,
    model: str | None = None,
    *,
    api_key: str | None = None,
    timeout: float = 180.0,
    **kwargs: Any,
) -> LLMClient:
    """创建指定 provider 的 LLM 客户端.

    Args:
        provider: Provider 名称，如 ``modelscope`` / ``dashscope`` / ``anthropic``.
        model: 模型 ID；若为 None 则使用该 provider 的默认模型.
        api_key: API key；若为 None 则从环境变量读取.
        timeout: 请求超时（秒）.
        **kwargs: 额外参数透传给客户端构造器.

    Returns:
        符合 LLMClient Protocol 的客户端实例.

    Raises:
        ValueError: provider 或 model 不支持.
        RuntimeError: 缺少必要的环境变量或 SDK.
    """
    if model is None:
        model = ModelCatalog.default_model_for_provider(provider)

    info = ModelCatalog.lookup(model)
    if info is None:
        raise ValueError(f"Unsupported model: {model}")
    if info.provider != provider:
        raise ValueError(
            f"Model {model} belongs to provider '{info.provider}', "
            f"not '{provider}'"
        )

    _api_key = api_key or os.getenv(info.api_key_env)
    if not _api_key:
        logger.warning(
            "API key not found for %s (env: %s)",
            provider,
            info.api_key_env,
        )

    if provider in ("modelscope", "dashscope", "openrouter"):
        if "deepseek" in model.lower() and "r1" in model.lower():
            return DeepSeekClient(
                model=model,
                api_key=_api_key or "",
                base_url=info.base_url,
                timeout=timeout,
            )
        return OpenAICompatibleClient(
            model=model,
            api_key=_api_key or "",
            base_url=info.base_url,
            timeout=timeout,
        )

    if provider == "anthropic":
        return AnthropicClient(
            model=model,
            api_key=_api_key or "",
            base_url=info.base_url or None,
            timeout=timeout,
        )

    raise ValueError(f"Unsupported provider: {provider}")
