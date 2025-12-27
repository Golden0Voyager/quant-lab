"""
四维数据整合模块（带缓存版）
将缓存功能集成到数据整合流程中
"""

import logging
from analyst_cached import fetch_full_stock_data_cached
from analyst_integration import (
    evaluate_enhanced_signals,
    build_enhanced_prompt
)

logger = logging.getLogger(__name__)

# 上证指数代码白名单 (000开头的指数，避免与深圳主板股票冲突)
SH_INDEX_CODES = {
    "000001",  # 上证综指
    "000016",  # 上证50
    "000300",  # 沪深300
    "000688",  # 科创50
    "000852",  # 中证1000
    "000905",  # 中证500
    "000906",  # 中证800
    "000932",  # 中证消费
    "000985",  # 中证全指
    "000991",  # 全指医药
    "000993",  # 全指信息
}


def detect_asset_type(code: str) -> str:
    """
    自动检测资产类型

    Args:
        code: 股票/指数/ETF代码

    Returns:
        资产类型: "stock" / "etf" / "index"
    """
    # 指数: 1A/1B(上证), 399(深证), 931(中证), H30(港股指数)
    if code.startswith(("1A", "1B", "399", "931", "930", "H30", "sh000", "sz399")):
        return "index"
    # 000开头的上证指数白名单
    if code in SH_INDEX_CODES:
        return "index"
    # ETF/LOF: 15/16(深), 51/56/58(沪)
    if code.startswith(("15", "16", "51", "56", "58")):
        return "etf"
    return "stock"


def fetch_stock_data(symbol: str, stock_name: str) -> dict:
    """
    获取完整四维数据（带缓存，自动检测资产类型）

    这是与原始 analyst_core.fetch_stock_data 兼容的接口
    可以直接替换原有导入，无需修改调用代码

    Args:
        symbol: 股票/指数/ETF代码
        stock_name: 名称

    Returns:
        完整数据字典（包含四维增强数据+缓存加速）
    """
    asset_type = detect_asset_type(symbol)
    return fetch_full_stock_data_cached(symbol, stock_name, asset_type)


def fetch_integrated_data_cached(symbol: str, stock_name: str, asset_type: str = "stock") -> dict:
    """
    整合获取完整四维数据（带智能缓存）

    相比原版 fetch_integrated_data：
    - 自动使用缓存优先策略
    - 减少API调用次数
    - 提升响应速度 3-10倍

    Args:
        symbol: 股票代码
        stock_name: 股票名称
        asset_type: 资产类型（stock/etf/index）

    Returns:
        整合后的完整数据字典
    """
    # 直接使用带缓存的完整抓取函数
    return fetch_full_stock_data_cached(symbol, stock_name, asset_type)


# ==================== 导出接口 ====================

__all__ = [
    'fetch_stock_data',              # 兼容原始接口（带缓存+四维数据）
    'fetch_integrated_data_cached',  # 显式指定资产类型的版本
    'evaluate_enhanced_signals',     # 信号评估
    'build_enhanced_prompt',         # Prompt构建
]


# ==================== 测试代码 ====================

if __name__ == "__main__":
    import time

    symbol = "002683"
    name = "广东宏大"

    print("="*70)
    print("缓存整合测试")
    print("="*70)

    # 第一次调用
    print("\n[第1次] 抓取数据...")
    start = time.time()
    data1 = fetch_integrated_data_cached(symbol, name, "stock")
    time1 = time.time() - start
    print(f"耗时: {time1:.2f}秒")

    # 第二次调用（应该很快）
    print("\n[第2次] 抓取数据（缓存）...")
    start = time.time()
    data2 = fetch_integrated_data_cached(symbol, name, "stock")
    time2 = time.time() - start
    print(f"耗时: {time2:.2f}秒")

    print(f"\n⚡ 加速比: {time1/time2:.1f}x")

    # 信号评估测试
    print("\n" + "="*70)
    print("信号评估测试")
    print("="*70)

    need_deep, triggers, score = evaluate_enhanced_signals(data1)

    print(f"\n综合得分: {score}分")
    print(f"是否触发Brain: {'是' if need_deep else '否'}")

    if triggers:
        print("\n触发信号:")
        for t in triggers:
            print(f"  - {t}")
