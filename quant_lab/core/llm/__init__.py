"""LLM provider abstraction and structured-output utilities."""

from __future__ import annotations

from .anthropic import AnthropicClient
from .base import LLMClient
from .catalog import ModelCatalog, ModelInfo
from .factory import create_client
from .openai_compat import DeepSeekClient, OpenAICompatibleClient
from .structured import invoke_structured_or_freetext

__all__ = [
    "AnthropicClient",
    "DeepSeekClient",
    "LLMClient",
    "ModelCatalog",
    "ModelInfo",
    "OpenAICompatibleClient",
    "create_client",
    "invoke_structured_or_freetext",
]
