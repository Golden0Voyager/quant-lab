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
YAHOO_PROXY_URL = os.getenv('YAHOO_PROXY', 'http://127.0.0.1:8118')

# ==================== 全局网络配置优化 ====================

def init_global_network():
    """初始化全局网络设置，提升数据抓取稳定性"""
    # 1. 压制 urllib3 连接重试的噪音日志（RemoteDisconnected 等连接级重试）
    logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)

    # 2. 东方财富域名强制使用 IPv4（其 IPv6 路由不稳定）
    _original_getaddrinfo = socket.getaddrinfo
    def _prefer_ipv4(host, port, family=0, type=0, proto=0, flags=0):
        if host and isinstance(host, str) and 'eastmoney.com' in host:
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
            self.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })

            # Yahoo Finance 代理注入：当 OpenBB fetch 线程设置了 _yahoo_proxy.active 时，
            # 直接将代理写入 session.proxies（不依赖 trust_env）
            if getattr(_yahoo_proxy, 'active', False):
                proxy_url = getattr(_yahoo_proxy, 'proxy_url', YAHOO_PROXY_URL)
                if proxy_url:
                    self.proxies = {'http': proxy_url, 'https': proxy_url}

            # 添加自动重试适配器（仅重试 HTTP 状态码错误，连接级错误由上层处理）
            retry_strategy = Retry(
                total=2,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                connect=1,  # 连接错误最多重试 1 次（减少无效等待）
                read=1,     # 读取错误最多重试 1 次
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
    "kimi": {
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "kimi-k2-thinking",
        "backup_model": "glm-4.7",
        "description": "Kimi K2 (Moonshot) - 默认主力模型"
    },
    "glm": {
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "glm-4.7",
        "backup_model": "qwen-plus",
        "description": "智谱 GLM-4.7 - 强力备用模型"
    },
    "qwen": {
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "backup_model": "kimi-k2-thinking",
        "description": "阿里通义千问 Plus - 稳定基座"
    },
    "deepseek": {
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "deepseek-v3.1",
        "backup_model": "qwen-plus",
        "description": "DeepSeek V3.1 - 主力模型 (V3.2需关闭免费额度限制后切换)"
    },
}

# 当前激活的配置名称
ACTIVE_PROFILE = "deepseek"

def get_current_config():
    """获取当前激活的完整配置字典"""
    return MODEL_CONFIGS.get(ACTIVE_PROFILE, MODEL_CONFIGS["kimi"])

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
        logging.warning(f"⚠️  未找到环境变量 {config['api_key_env']}，AI 功能可能无法使用")

    # 创建不走代理的 HTTP 客户端（DashScope 是国内服务，无需代理）
    http_client = httpx.Client(
        timeout=timeout,
        proxy=None  # 显式禁用代理
    )

    return OpenAI(
        api_key=api_key,
        base_url=config["base_url"],
        timeout=timeout,
        http_client=http_client
    )
