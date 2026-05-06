"""模型目录：白名单、能力描述、配置映射."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class ModelInfo:
    """单个模型的元数据."""

    provider: str
    model_id: str
    display_name: str
    supports_structured: bool = False
    supports_thinking: bool = False
    supports_vision: bool = False
    api_key_env: str = ""
    base_url: str = ""
    description: str = ""


class ModelCatalog:
    """支持的模型白名单."""

    _REGISTRY: ClassVar[dict[str, ModelInfo]] = {
        # ModelScope
        "deepseek-ai/DeepSeek-V3.2": ModelInfo(
            provider="modelscope",
            model_id="deepseek-ai/DeepSeek-V3.2",
            display_name="DeepSeek V3.2",
            supports_structured=True,
            api_key_env="MODELSCOPE_API_KEY",
            base_url="https://api-inference.modelscope.cn/v1",
            description="DeepSeek V3.2 (ModelScope) - 极速通用旗舰，日常主力",
        ),
        "Qwen/Qwen3.5-397B-A17B": ModelInfo(
            provider="modelscope",
            model_id="Qwen/Qwen3.5-397B-A17B",
            display_name="Qwen3.5 旗舰",
            supports_structured=True,
            api_key_env="MODELSCOPE_API_KEY",
            base_url="https://api-inference.modelscope.cn/v1",
            description="Qwen3.5 旗舰 (ModelScope) - 最新一代超长上下文",
        ),
        "deepseek-ai/DeepSeek-R1-0528": ModelInfo(
            provider="modelscope",
            model_id="deepseek-ai/DeepSeek-R1-0528",
            display_name="DeepSeek R1",
            supports_structured=True,
            supports_thinking=True,
            api_key_env="MODELSCOPE_API_KEY",
            base_url="https://api-inference.modelscope.cn/v1",
            description="DeepSeek R1 (ModelScope) - 最强推理，深度分析用",
        ),
        "Qwen/Qwen3-235B-A22B-Thinking-2507": ModelInfo(
            provider="modelscope",
            model_id="Qwen/Qwen3-235B-A22B-Thinking-2507",
            display_name="Qwen3 Thinking",
            supports_structured=True,
            supports_thinking=True,
            api_key_env="MODELSCOPE_API_KEY",
            base_url="https://api-inference.modelscope.cn/v1",
            description="Qwen3 Thinking (ModelScope)",
        ),
        # DashScope
        "glm-4.7": ModelInfo(
            provider="dashscope",
            model_id="glm-4.7",
            display_name="GLM 4.7",
            supports_structured=True,
            api_key_env="DASHSCOPE_API_KEY",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            description="GLM 4.7 (DashScope) - 最新一代超长上下文",
        ),
        "qwen3-vl-plus-2025-12-19": ModelInfo(
            provider="dashscope",
            model_id="qwen3-vl-plus-2025-12-19",
            display_name="Qwen3 VL Plus",
            supports_structured=True,
            supports_vision=True,
            api_key_env="DASHSCOPE_API_KEY",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            description="Qwen3 VL Plus (DashScope) - 多模态",
        ),
        # Anthropic (via native SDK or OpenRouter)
        "claude-sonnet-4-6-20251101": ModelInfo(
            provider="anthropic",
            model_id="claude-sonnet-4-6-20251101",
            display_name="Claude Sonnet 4.6",
            supports_structured=True,
            supports_vision=True,
            api_key_env="ANTHROPIC_API_KEY",
            base_url="",
            description="Claude Sonnet 4.6 - 高智能通用模型",
        ),
    }

    @classmethod
    def lookup(cls, model_id: str) -> ModelInfo | None:
        """按 model_id 查找模型信息."""
        return cls._REGISTRY.get(model_id)

    @classmethod
    def list_models(cls, *, provider: str | None = None) -> list[ModelInfo]:
        """列出所有支持的模型，可按 provider 过滤."""
        models = list(cls._REGISTRY.values())
        if provider:
            models = [m for m in models if m.provider == provider]
        return models

    @classmethod
    def list_providers(cls) -> list[str]:
        """返回所有支持的 provider 名称."""
        return sorted({m.provider for m in cls._REGISTRY.values()})

    @classmethod
    def default_model_for_provider(cls, provider: str) -> str:
        """返回某个 provider 的默认 model_id."""
        for model_id, info in cls._REGISTRY.items():
            if info.provider == provider:
                return model_id
        raise ValueError(f"Unknown provider: {provider}")
