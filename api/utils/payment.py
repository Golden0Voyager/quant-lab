"""
支付工具类
提供统一的支付接口，支持多种支付方式
"""

import hashlib
import logging
import time
from typing import Any

import requests

from api.config.payment import PaymentMethod, get_payment_config

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """支付错误"""
    pass


class BasePaymentProvider:
    """支付服务商基类"""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def create_payment(self, order_no: str, amount: float, subject: str,
                       payment_method: PaymentMethod, **kwargs) -> dict[str, Any]:
        """
        创建支付订单

        Args:
            order_no: 订单号
            amount: 金额（元）
            subject: 商品名称
            payment_method: 支付方式
            **kwargs: 其他参数

        Returns:
            支付信息字典 {"pay_url": "...", "qr_code": "...", ...}
        """
        raise NotImplementedError

    def verify_notify(self, data: dict[str, Any]) -> bool:
        """
        验证支付回调

        Args:
            data: 回调数据

        Returns:
            是否验证通过
        """
        raise NotImplementedError

    def query_order(self, order_no: str) -> dict[str, Any]:
        """
        查询订单状态

        Args:
            order_no: 订单号

        Returns:
            订单信息
        """
        raise NotImplementedError


class PayJSProvider(BasePaymentProvider):
    """
    PayJS支付服务商
    文档: https://help.payjs.cn/
    """

    def _sign(self, data: dict[str, Any]) -> str:
        """生成签名"""
        # 排序参数
        sorted_keys = sorted([k for k in data if k != 'sign'])
        sign_str = '&'.join([f"{k}={data[k]}" for k in sorted_keys])
        sign_str += f"&key={self.config['key']}"

        # MD5签名
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()

    def create_payment(self, order_no: str, amount: float, subject: str,
                       payment_method: PaymentMethod, **kwargs) -> dict[str, Any]:
        """创建PayJS支付订单"""
        try:
            # 金额转换为分
            total_fee = int(amount * 100)

            # 构建请求参数
            params = {
                "mchid": self.config["mchid"],
                "out_trade_no": order_no,
                "total_fee": total_fee,
                "body": subject,
                "notify_url": self.config["notify_url"],
            }

            # 生成签名
            params["sign"] = self._sign(params)

            # 选择API
            if payment_method == PaymentMethod.WECHAT:
                api_url = self.config["api_url"]  # 扫码支付
            else:
                api_url = self.config["cashier_url"]  # 收银台（支持支付宝）

            # 发送请求
            logger.info(f"创建PayJS支付订单: {order_no}, {amount}元")
            response = requests.post(api_url, data=params, timeout=10)
            result = response.json()

            if result.get("return_code") == 1:
                return {
                    "pay_url": result.get("qrcode") or result.get("payjs_order_id"),
                    "qr_code": result.get("code_url"),
                    "payjs_order_id": result.get("payjs_order_id"),
                }
            else:
                raise PaymentError(f"创建支付失败: {result.get('return_msg', '未知错误')}")

        except Exception as e:
            logger.error(f"创建PayJS支付失败: {e}", exc_info=True)
            raise PaymentError(f"创建支付失败: {str(e)}")

    def verify_notify(self, data: dict[str, Any]) -> bool:
        """验证PayJS回调"""
        try:
            received_sign = data.get("sign", "")
            if not received_sign:
                return False

            # 重新计算签名
            calc_sign = self._sign(data)

            return calc_sign == received_sign

        except Exception as e:
            logger.error(f"验证PayJS回调失败: {e}", exc_info=True)
            return False

    def query_order(self, order_no: str) -> dict[str, Any]:
        """查询PayJS订单状态"""
        try:
            params = {
                "mchid": self.config["mchid"],
                "out_trade_no": order_no,
            }
            params["sign"] = self._sign(params)

            api_url = "https://payjs.cn/api/check"
            response = requests.post(api_url, data=params, timeout=10)
            result = response.json()

            return result

        except Exception as e:
            logger.error(f"查询PayJS订单失败: {e}", exc_info=True)
            return {}


class MockPaymentProvider(BasePaymentProvider):
    """
    模拟支付服务商（用于开发测试）
    """

    def create_payment(self, order_no: str, amount: float, subject: str,
                       payment_method: PaymentMethod, **kwargs) -> dict[str, Any]:
        """创建模拟支付订单"""
        logger.info(f"[模拟支付] 创建订单: {order_no}, {amount}元, {subject}")

        # 返回模拟支付URL
        return {
            "pay_url": f"http://localhost:3000/mock-payment?order_no={order_no}&amount={amount}",
            "qr_code": f"MOCK_QR_{order_no}",
            "mock": True
        }

    def verify_notify(self, data: dict[str, Any]) -> bool:
        """验证模拟回调（总是返回True）"""
        return data.get("mock_payment") == "success"

    def query_order(self, order_no: str) -> dict[str, Any]:
        """查询模拟订单（总是返回已支付）"""
        return {
            "return_code": 1,
            "paid": True,
            "out_trade_no": order_no
        }


class PaymentService:
    """支付服务统一接口"""

    def __init__(self, provider: str = None):
        """
        初始化支付服务

        Args:
            provider: 支付服务商名称 (payjs/mock)
        """
        self.config = get_payment_config(provider)
        self.provider_name = provider or self.config.get("provider", "mock")

        # 根据provider创建对应的支付服务商实例
        if self.provider_name == "payjs":
            self.provider = PayJSProvider(self.config)
        elif self.provider_name == "mock":
            self.provider = MockPaymentProvider(self.config)
        else:
            raise ValueError(f"不支持的支付服务商: {self.provider_name}")

        logger.info(f"初始化支付服务: {self.provider_name}")

    def create_payment(self, order_no: str, amount: float, subject: str,
                       payment_method: PaymentMethod = PaymentMethod.WECHAT,
                       **kwargs) -> dict[str, Any]:
        """创建支付订单"""
        return self.provider.create_payment(order_no, amount, subject, payment_method, **kwargs)

    def verify_notify(self, data: dict[str, Any]) -> bool:
        """验证支付回调"""
        return self.provider.verify_notify(data)

    def query_order(self, order_no: str) -> dict[str, Any]:
        """查询订单状态"""
        return self.provider.query_order(order_no)


def generate_order_no() -> str:
    """生成订单号"""
    import random
    timestamp = int(time.time() * 1000)
    random_num = random.randint(1000, 9999)
    return f"ORD{timestamp}{random_num}"
