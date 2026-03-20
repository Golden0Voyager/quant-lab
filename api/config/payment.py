"""
支付配置
"""

import os
from enum import Enum


class PaymentMethod(Enum):
    """支付方式"""
    WECHAT = "wechat"  # 微信支付
    ALIPAY = "alipay"  # 支付宝


# ==================== 支付配置 ====================
PAYMENT_CONFIG = {
    # 支付服务商（建议使用聚合支付）
    # 可选: payjs, pingpp, stripe等
    "provider": os.getenv("PAYMENT_PROVIDER", "payjs"),

    # PayJS配置（示例）
    "payjs": {
        "mchid": os.getenv("PAYJS_MCHID", ""),  # 商户号
        "key": os.getenv("PAYJS_KEY", ""),  # 通信密钥
        "api_url": "https://payjs.cn/api/native",  # 扫码支付API
        "cashier_url": "https://payjs.cn/api/cashier",  # 收银台API
    },

    # Ping++配置（示例）
    "pingpp": {
        "app_id": os.getenv("PINGPP_APP_ID", ""),
        "api_key": os.getenv("PINGPP_API_KEY", ""),
        "private_key_path": os.getenv("PINGPP_PRIVATE_KEY_PATH", ""),
    },

    # 回调URL
    "notify_url": os.getenv("PAYMENT_NOTIFY_URL", "http://localhost:5000/api/payment/notify"),
    "return_url": os.getenv("PAYMENT_RETURN_URL", "http://localhost:3000/payment/success"),

    # 订单配置
    "order_timeout": 1800,  # 订单超时时间（秒），默认30分钟
}


def get_payment_config(provider: str = None) -> dict:
    """获取支付配置"""
    if provider is None:
        provider = PAYMENT_CONFIG["provider"]

    config = PAYMENT_CONFIG.get(provider, {})
    config["notify_url"] = PAYMENT_CONFIG["notify_url"]
    config["return_url"] = PAYMENT_CONFIG["return_url"]

    return config


def validate_payment_config(provider: str = None) -> bool:
    """验证支付配置是否完整"""
    config = get_payment_config(provider)

    # 检查必要的配置项
    if not config:
        return False

    # 根据不同的支付服务商检查不同的配置项
    if provider == "payjs":
        return bool(config.get("mchid") and config.get("key"))
    elif provider == "pingpp":
        return bool(config.get("app_id") and config.get("api_key"))

    return True
