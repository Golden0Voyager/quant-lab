"""Legacy global configuration module (DEPRECATED).

All new code should import from ``quant_lab.core.config`` instead.
This module is kept as a thin backward-compatibility layer and will be
removed in Phase 9.
"""

from __future__ import annotations

import logging
import os
import threading
import warnings

import httpx
from openai import OpenAI

# ==================== Yahoo Finance 代理支持 ====================
# 线程局部变量：OpenBB/yfinance 的 fetch 线程设置此标志后，
# monkey-patched Session.__init__ 会自动注入代理到 session.proxies
# （绕过 trust_env=False 的限制）
_yahoo_proxy = threading.local()

# 默认代理地址（从 v2 配置读取，保留全局变量名供 legacy 引用）
# 延迟求值，避免在导入时触发配置初始化


def _yahoo_proxy_url() -> str:
    """Return the current Yahoo proxy URL from v2 settings."""
    try:
        from quant_lab.core.config import get_settings
        return get_settings().yahoo_proxy_url
    except Exception:
        return os.getenv("YAHOO_PROXY", "http://127.0.0.1:7897")


# 保留旧的全局名称，但使用 property-like 延迟求值
class _LazyProxyURL:
    """Compatibility shim so ``ai_config.YAHOO_PROXY_URL`` still works."""

    def __str__(self) -> str:
        return _yahoo_proxy_url()

    def __repr__(self) -> str:
        return repr(_yahoo_proxy_url())


YAHOO_PROXY_URL = _LazyProxyURL()  # type: ignore[assignment]

# ==================== 全局网络配置优化 (DEPRECATED) ====================


def init_global_network():
    """初始化全局网络设置，提升数据抓取稳定性。

    .. deprecated::
        已弃用。新代码请显式使用 ``quant_lab.core.net`` 中的
        :func:`make_china_session` / :func:`make_yahoo_session` / :func:`make_llm_session`。
    """
    warnings.warn(
        "ai_config.init_global_network() is deprecated. "
        "Use quant_lab.core.net.make_china_session / make_yahoo_session / make_llm_session instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # 1. 压制 urllib3 连接重试的噪音日志
    logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)

    # 2. 东方财富 IPv4 强制
    from quant_lab.core.net.dns import force_ipv4_eastmoney

    force_ipv4_eastmoney()

    # 3. Monkey-patch requests（兼容老代码路径）
    try:
        from quant_lab.core.net.sessions import _install_patched_session_init

        _install_patched_session_init()
        logging.info("✅ 全局网络优化已激活 (国内直连/Yahoo代理注入/重试机制)")
    except Exception as e:
        logging.warning(f"⚠️ 全局网络优化失败: {e}")


# ==================== 全局 AI 配置中心 (DEPRECATED) ====================
# 以下函数和变量已被 quant_lab.core.llm / quant_lab.core.config 取代，
# 保留仅用于向后兼容。

# 支持的模型配置列表
MODEL_CONFIGS = {
    # ==================== ModelScope（魔搭社区，免费 2000次/天） ====================
    "deepseek": {
        "api_key_env": "MODELSCOPE_API_KEY",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3.2",
        "backup_model": "Qwen/Qwen3.5-397B-A17B",
        "description": "DeepSeek V3.2 (ModelScope) - 极速通用旗舰，日常主力",
    },
    "qwen": {
        "api_key_env": "MODELSCOPE_API_KEY",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "model": "Qwen/Qwen3.5-397B-A17B",
        "backup_model": "deepseek-ai/DeepSeek-V3.2",
        "description": "Qwen3.5 旗舰 (ModelScope) - 最新一代超长上下文",
    },
    "r1": {
        "api_key_env": "MODELSCOPE_API_KEY",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "model": "deepseek-ai/DeepSeek-R1-0528",
        "backup_model": "Qwen/Qwen3-235B-A22B-Thinking-2507",
        "description": "DeepSeek R1 (ModelScope) - 最强推理，深度分析用",
    },
    # ==================== DashScope（阿里云百炼，备用） ====================
    "dashscope-glm-4.7": {
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "glm-4.7",
        "backup_model": "qwen3-vl-plus-2025-12-19",
        "description": "GLM 4.7 (DashScope) - 最新一代超长上下文",
    },
}

# 当前激活的配置名称
ACTIVE_PROFILE = "deepseek"


def get_current_config():
    """获取当前激活的完整配置字典"""
    warnings.warn(
        "ai_config.get_current_config is deprecated. "
        "Use quant_lab.core.llm.catalog.ModelCatalog instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # 优先委托给 v2 配置
    try:
        from quant_lab.core.config import get_settings
        return get_settings().model_dump_legacy()
    except Exception:
        return MODEL_CONFIGS.get(ACTIVE_PROFILE, MODEL_CONFIGS["deepseek"])


def get_primary_model_name():
    """获取当前主力模型名称"""
    warnings.warn(
        "ai_config.get_primary_model_name is deprecated. "
        "Use quant_lab.core.llm.factory.create_client instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        from quant_lab.core.config import get_settings
        return get_settings().default_model
    except Exception:
        return get_current_config()["model"]


def get_backup_model_name():
    """获取当前备用模型名称"""
    warnings.warn(
        "ai_config.get_backup_model_name is deprecated. "
        "Use quant_lab.core.llm.factory.create_client instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # 优先使用 legacy MODEL_CONFIGS 中的 backup_model
    config = MODEL_CONFIGS.get(ACTIVE_PROFILE, MODEL_CONFIGS["deepseek"])
    return config.get("backup_model", "glm-4.7")


def create_openai_client(timeout=180.0):
    """
    创建一个统一配置的 OpenAI Client

    .. deprecated::
        已弃用，请使用 ``quant_lab.core.llm.factory.create_client``。
    """
    warnings.warn(
        "ai_config.create_openai_client is deprecated. "
        "Use quant_lab.core.llm.factory.create_client instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    config = get_current_config()
    api_key = os.getenv(config["api_key_env"])

    if not api_key:
        logging.warning(
            f"⚠️  未找到环境变量 {config['api_key_env']}，AI 功能可能无法使用"
        )

    # 创建不走代理的 HTTP 客户端（DashScope 是国内服务，无需代理）
    http_client = httpx.Client(
        timeout=timeout,
        proxy=None,  # 显式禁用代理
        trust_env=False,  # 不读取环境变量中的代理配置（no_proxy 含格式错误的 IPv6）
    )

    return OpenAI(
        api_key=api_key,
        base_url=config["base_url"],
        timeout=timeout,
        http_client=http_client,
    )
