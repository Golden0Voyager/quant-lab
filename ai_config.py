import os
import logging
import socket
import threading
import httpx
from openai import OpenAI

# ==================== Yahoo Finance 代理支持 ====================
# 线程局部变量：OpenBB/yfinance 的 fetch 线程设置此标志后，
# monkey-patched Session.__init__ 会自动注入代理到 session.proxies
# （绕过 trust_env=False 的限制）
_yahoo_proxy = threading.local()

# 默认代理地址（仅用于 Yahoo Finance，国内 API 全部直连）
YAHOO_PROXY_URL = os.getenv("YAHOO_PROXY", "http://127.0.0.1:8118")

# ==================== 全局网络配置优化 ====================


def init_global_network():
    """初始化全局网络设置，提升数据抓取稳定性"""
    # 1. 压制 urllib3 连接重试的噪音日志（RemoteDisconnected 等连接级重试）
    logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)

    # 2. 东方财富域名强制使用 IPv4（其 IPv6 路由不稳定）
    _original_getaddrinfo = socket.getaddrinfo

    def _prefer_ipv4(host, port, family=0, type=0, proto=0, flags=0):
        if host and isinstance(host, str) and "eastmoney.com" in host:
            return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
        return _original_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = _prefer_ipv4

    # 3. Monkey-patch requests：User-Agent / 重试 / 东方财富绕过代理
    try:
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        _original_session_init = requests.Session.__init__

        def _patched_session_init(self, *args, **kwargs):
            _original_session_init(self, *args, **kwargs)
            # 国内 API 绕过系统代理（Clash 会把东财等域名误路由到海外节点）
            self.trust_env = False
            # 设置通用的真实浏览器 Header
            self.headers.update(
                {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
            )

            # Yahoo Finance 代理注入：当 OpenBB fetch 线程设置了 _yahoo_proxy.active 时，
            # 直接将代理写入 session.proxies（不依赖 trust_env）
            if getattr(_yahoo_proxy, "active", False):
                proxy_url = getattr(_yahoo_proxy, "proxy_url", YAHOO_PROXY_URL)
                if proxy_url:
                    self.proxies = {"http": proxy_url, "https": proxy_url}

            # 添加自动重试适配器（仅重试 HTTP 状态码错误，连接级错误由上层处理）
            retry_strategy = Retry(
                total=2,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                connect=1,  # 连接错误最多重试 1 次（减少无效等待）
                read=1,  # 读取错误最多重试 1 次
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.mount("http://", adapter)
            self.mount("https://", adapter)

        requests.Session.__init__ = _patched_session_init
        logging.info("✅ 全局网络优化已激活 (国内直连/Yahoo代理注入/重试机制)")
    except Exception as e:
        logging.warning(f"⚠️ 全局网络优化失败: {e}")


# ==================== 全局 AI 配置中心 ====================

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
    return MODEL_CONFIGS.get(ACTIVE_PROFILE, MODEL_CONFIGS["deepseek"])


def get_primary_model_name():
    """获取当前主力模型名称"""
    return get_current_config()["model"]


def get_backup_model_name():
    """获取当前备用模型名称"""
    config = get_current_config()
    # 优先使用配置中的 backup_model，如果没有则硬编码一个保底
    return config.get("backup_model", "glm-4.7")


def create_openai_client(timeout=180.0):
    """
    创建一个统一配置的 OpenAI Client

    Args:
        timeout: 超时时间（秒）

    Returns:
        OpenAI: 初始化好的客户端
    """
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
