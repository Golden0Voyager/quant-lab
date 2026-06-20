"""
产品配置
定义所有可购买的产品和服务
"""

from enum import Enum
from typing import Any


class ProductType(Enum):
    """产品类型"""
    SINGLE_REPORT = "single_report"  # 单次报告
    SUBSCRIPTION = "subscription"  # 订阅包


class Product:
    """产品基类"""
    def __init__(self, sku: str, name: str, price: float, product_type: ProductType,
                 description: str = "", quota: dict[str, int] = None):
        self.sku = sku
        self.name = name
        self.price = price
        self.product_type = product_type
        self.description = description
        self.quota = quota or {}  # 额度配置 {"fast": 3, "deep": 1}

    def to_dict(self) -> dict[str, Any]:
        return {
            "sku": self.sku,
            "name": self.name,
            "price": self.price,
            "product_type": self.product_type.value,
            "description": self.description,
            "quota": self.quota
        }


# ==================== 单次报告产品 ====================
PRODUCTS_SINGLE_REPORT = {
    "fast_report": Product(
        sku="REPORT_FAST_001",
        name="个股快速分析",
        price=1.9,
        product_type=ProductType.SINGLE_REPORT,
        description="Fast模式，基础点评",
        quota={"fast": 1}
    ),
    "deep_report": Product(
        sku="REPORT_DEEP_001",
        name="个股深度报告",
        price=4.9,
        product_type=ProductType.SINGLE_REPORT,
        description="Deep模式，完整分析+3种策略对比",
        quota={"deep": 1}
    ),
    "watchlist_daily": Product(
        sku="REPORT_WATCH_DAILY",
        name="自选股日报",
        price=2.9,
        product_type=ProductType.SINGLE_REPORT,
        description="10只内，Auto模式+异动股深度分析",
        quota={"watchlist_daily": 1}
    ),
    "watchlist_weekly": Product(
        sku="REPORT_WATCH_WEEKLY",
        name="自选股周报",
        price=9.9,
        product_type=ProductType.SINGLE_REPORT,
        description="30只内，Deep模式全面复盘",
        quota={"watchlist_weekly": 1}
    ),
}

# ==================== 订阅包产品 ====================
PRODUCTS_SUBSCRIPTION = {
    "basic": Product(
        sku="SUB_BASIC_MONTH",
        name="入门包（月付）",
        price=19.9,
        product_type=ProductType.SUBSCRIPTION,
        description="10份深度报告 + 30份快速分析",
        quota={"fast": 30, "deep": 10, "days": 30}
    ),
    "pro": Product(
        sku="SUB_PRO_MONTH",
        name="专业包（月付）",
        price=49.0,
        product_type=ProductType.SUBSCRIPTION,
        description="50份深度报告 + 无限快速分析 + 每日自选股报告",
        quota={"fast": 999, "deep": 50, "watchlist_daily": 30, "days": 30}
    ),
    "premium": Product(
        sku="SUB_PREMIUM_MONTH",
        name="旗舰包（月付）",
        price=99.0,
        product_type=ProductType.SUBSCRIPTION,
        description="无限深度报告 + 每日自选股报告 + 自定义报告模板",
        quota={"fast": 9999, "deep": 9999, "watchlist_daily": 30, "watchlist_weekly": 4, "days": 30}
    ),
}

# ==================== 所有产品 ====================
ALL_PRODUCTS = {**PRODUCTS_SINGLE_REPORT, **PRODUCTS_SUBSCRIPTION}


def get_product_by_sku(sku: str) -> Product:
    """根据SKU获取产品"""
    for product in ALL_PRODUCTS.values():
        if product.sku == sku:
            return product
    return None


def get_all_products() -> dict[str, Product]:
    """获取所有产品"""
    return ALL_PRODUCTS


def get_products_by_type(product_type: ProductType) -> dict[str, Product]:
    """根据类型获取产品"""
    if product_type == ProductType.SINGLE_REPORT:
        return PRODUCTS_SINGLE_REPORT
    elif product_type == ProductType.SUBSCRIPTION:
        return PRODUCTS_SUBSCRIPTION
    return {}
