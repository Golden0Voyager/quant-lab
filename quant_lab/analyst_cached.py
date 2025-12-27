"""
带缓存的数据抓取模块
在 analyst_core_enhanced.py 基础上增加智能缓存功能
"""

import logging
from datetime import datetime
from data_cache import DataCache, CacheStrategy
from analyst_core_enhanced import (
    fetch_valuation_data,
    fetch_performance_data,
    fetch_sentiment_data,
    fetch_macro_etf_data
)
from analyst_core import fetch_stock_data

logger = logging.getLogger(__name__)

# 全局缓存实例
_cache = None


def get_cache():
    """获取全局缓存实例（单例模式）"""
    global _cache
    if _cache is None:
        _cache = DataCache("quant_cache.db")
    return _cache


# ==================== 带缓存的数据抓取函数 ====================

def fetch_stock_data_cached(symbol: str, stock_name: str) -> dict:
    """
    获取基础股票数据（带缓存）

    包含：K线、资金流向、新闻
    缓存策略：分层缓存
    - K线：24小时
    - 资金流向：24小时
    - 新闻：1小时
    """
    cache = get_cache()

    # 尝试从缓存读取（使用综合缓存）
    cached = cache.get(symbol, 'stock_base')
    if cached:
        logger.info(f"✅ 基础数据缓存命中: {stock_name}")
        return cached

    # 缓存未命中，抓取新数据
    logger.info(f"📥 抓取基础数据: {stock_name}")
    data = fetch_stock_data(symbol, stock_name)

    # 写入缓存（智能TTL）
    cache.set(symbol, 'stock_base', data, CacheStrategy.get_ttl('stock_base'))

    return data


def fetch_valuation_data_cached(symbol: str, stock_name: str) -> dict:
    """
    获取估值数据（带缓存+历史积累）

    缓存策略：24小时
    额外功能：自动保存历史数据用于分位数计算
    """
    cache = get_cache()

    # 尝试从缓存读取
    cached = cache.get(symbol, 'valuation')
    if cached:
        logger.info(f"✅ 估值数据缓存命中: {stock_name}")
        return cached

    # 缓存未命中，抓取新数据
    logger.info(f"📊 抓取估值数据: {stock_name}")
    data = fetch_valuation_data(symbol, stock_name)

    # 写入缓存（智能TTL）
    cache.set(symbol, 'valuation', data, CacheStrategy.get_ttl('valuation'))

    # 保存历史数据（用于分位数计算）
    today = datetime.now().strftime('%Y-%m-%d')
    cache.save_historical_valuation(symbol, today, data)

    return data


def fetch_performance_data_cached(symbol: str, stock_name: str) -> dict:
    """
    获取业绩数据（带缓存）

    缓存策略：7天（财报季度更新）
    """
    cache = get_cache()

    # 尝试从缓存读取
    cached = cache.get(symbol, 'performance')
    if cached:
        logger.info(f"✅ 业绩数据缓存命中: {stock_name}")
        return cached

    # 缓存未命中，抓取新数据
    logger.info(f"📈 抓取业绩数据: {stock_name}")
    data = fetch_performance_data(symbol, stock_name)

    # 写入缓存（7天）
    cache.set(symbol, 'performance', data, CacheStrategy.TTL_WEEK)

    return data


def fetch_sentiment_data_cached(symbol: str, stock_name: str) -> dict:
    """
    获取资金情绪数据（带分层缓存）

    缓存策略：
    - 实时行情（量比/换手率）：5分钟（交易时间内）/ 24小时（盘后）
    - 北向资金：24小时
    - 股东数据：30天
    """
    cache = get_cache()

    # 判断是否在交易时间
    is_trading = CacheStrategy.is_trading_time()

    # 实时数据：交易时间内短缓存，盘后长缓存
    cache_key = 'sentiment_realtime' if is_trading else 'sentiment_daily'
    ttl = CacheStrategy.get_ttl(cache_key)  # 使用智能TTL

    # 尝试从缓存读取
    cached = cache.get(symbol, cache_key)
    if cached:
        logger.info(f"✅ 情绪数据缓存命中: {stock_name} ({'盘中' if is_trading else '盘后'})")
        return cached

    # 缓存未命中，抓取新数据
    logger.info(f"💰 抓取情绪数据: {stock_name}")
    data = fetch_sentiment_data(symbol, stock_name)

    # 写入缓存
    cache.set(symbol, cache_key, data, ttl)

    return data


def fetch_macro_etf_data_cached(symbol: str, asset_type: str = "stock") -> dict:
    """
    获取宏观数据（带缓存）

    缓存策略：
    - ETF折溢价：5分钟（交易时间内）
    - 汇率：1小时
    """
    cache = get_cache()

    # 尝试从缓存读取
    cached = cache.get(symbol, 'macro')
    if cached:
        logger.info(f"✅ 宏观数据缓存命中: {symbol}")
        return cached

    # 缓存未命中，抓取新数据
    logger.info(f"🌍 抓取宏观数据: {symbol}")
    data = fetch_macro_etf_data(symbol, asset_type)

    # 写入缓存（1小时）
    cache.set(symbol, 'macro', data, CacheStrategy.TTL_HOUR)

    return data


# ==================== 完整数据抓取（带缓存）====================

def fetch_full_stock_data_cached(symbol: str, stock_name: str, asset_type: str = "stock") -> dict:
    """
    获取完整四维数据（带智能缓存）

    自动使用缓存优先策略，减少API调用

    Args:
        symbol: 股票代码
        stock_name: 股票名称
        asset_type: 资产类型

    Returns:
        完整数据字典
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"🔄 开始抓取（智能缓存模式）: {stock_name} ({symbol})")
    logger.info(f"{'='*60}\n")

    result = {
        'code': symbol,
        'name': stock_name,
        'type': asset_type,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    # 1. 基础数据（K线、资金、新闻）
    try:
        base_data = fetch_stock_data_cached(symbol, stock_name)
        result.update(base_data)
    except Exception as e:
        logger.error(f"基础数据抓取失败: {e}")

    # 2. 四维增强数据（仅个股）
    if asset_type == "stock":
        # 估值维度
        try:
            valuation = fetch_valuation_data_cached(symbol, stock_name)
            result.update(valuation)
        except Exception as e:
            logger.error(f"估值数据抓取失败: {e}")

        # 业绩维度
        try:
            performance = fetch_performance_data_cached(symbol, stock_name)
            result.update(performance)
        except Exception as e:
            logger.error(f"业绩数据抓取失败: {e}")

        # 计算市销率 PS-TTM（需要市值和营收数据）
        try:
            market_cap = result.get('market_cap')
            revenue_raw = result.get('revenue_ttm_raw')  # TTM 营收

            if market_cap and revenue_raw and revenue_raw > 0:
                ps_ttm = market_cap / revenue_raw
                result['ps_ttm'] = f"{ps_ttm:.2f}"
                result['ps_ttm_raw'] = ps_ttm

                # 更新估值摘要，包含 PS-TTM
                result['valuation_summary'] = (
                    f"PE-TTM: {result.get('pe_ttm', 'N/A')} | "
                    f"PB: {result.get('pb', 'N/A')} | "
                    f"PS-TTM: {result['ps_ttm']} | "
                    f"股息率(TTM): {result.get('dividend_yield', 'N/A')}"
                )
                logger.info(f"✓ 市销率计算成功: PS-TTM={result['ps_ttm']}")
        except Exception as e:
            logger.debug(f"市销率计算失败: {e}")

    # 3. 资金情绪（所有类型）
    try:
        sentiment = fetch_sentiment_data_cached(symbol, stock_name)
        result.update(sentiment)
    except Exception as e:
        logger.error(f"情绪数据抓取失败: {e}")

    # 4. 宏观数据
    try:
        macro = fetch_macro_etf_data_cached(symbol, asset_type)
        result.update(macro)
    except Exception as e:
        logger.error(f"宏观数据抓取失败: {e}")

    logger.info(f"✅ 数据抓取完成（已使用缓存优化）\n")

    return result


# ==================== 缓存管理工具 ====================

def clear_cache(symbol: str = None, data_type: str = None):
    """
    清理缓存

    Args:
        symbol: 指定股票代码（None=全部）
        data_type: 指定数据类型（None=全部）
    """
    cache = get_cache()

    if symbol is None and data_type is None:
        # 清理所有过期缓存
        cache.clean_expired()
    else:
        # TODO: 实现指定清理
        logger.warning("指定清理功能待实现")


def get_cache_info():
    """获取缓存统计信息"""
    cache = get_cache()
    stats = cache.get_cache_stats()

    print("\n" + "="*60)
    print("缓存统计信息")
    print("="*60)
    print(f"总缓存条目: {stats.get('total_cache', 0)}")
    print(f"有效缓存: {stats.get('valid_cache', 0)}")
    print(f"过期缓存: {stats.get('expired_cache', 0)}")
    print(f"历史数据点: {stats.get('historical_points', 0)}")

    type_dist = stats.get('type_distribution', {})
    if type_dist:
        print("\n按类型分布:")
        for dtype, count in type_dist.items():
            print(f"  - {dtype}: {count}条")
    print("="*60 + "\n")

    return stats


def warm_up_cache(watchlist: list):
    """
    预热缓存（批量抓取并缓存数据）

    适用场景：盘后批量更新缓存

    Args:
        watchlist: 自选股列表 [{"code": "002683", "name": "广东宏大"}, ...]
    """
    logger.info(f"\n🔥 开始缓存预热: {len(watchlist)} 只股票\n")

    success_count = 0
    fail_count = 0

    for i, stock in enumerate(watchlist, 1):
        try:
            logger.info(f"[{i}/{len(watchlist)}] 预热: {stock['name']}")

            # 判断资产类型
            symbol = stock['code']
            if symbol.startswith(("15", "16", "51", "56", "58")):
                asset_type = "etf"
            elif symbol.startswith(("000001", "399", "sh000", "sz399")):
                asset_type = "index"
            else:
                asset_type = "stock"

            # 抓取数据（自动缓存）
            fetch_full_stock_data_cached(symbol, stock['name'], asset_type)
            success_count += 1

        except Exception as e:
            logger.error(f"预热失败 {stock['name']}: {e}")
            fail_count += 1

    logger.info(f"\n✅ 缓存预热完成: 成功 {success_count} | 失败 {fail_count}\n")


# ==================== 测试代码 ====================

if __name__ == "__main__":
    import time

    # 测试1：单只股票（两次调用对比速度）
    print("="*70)
    print("测试1：缓存性能测试")
    print("="*70)

    symbol = "002683"
    name = "广东宏大"

    print("\n第一次调用（无缓存）...")
    start = time.time()
    data1 = fetch_full_stock_data_cached(symbol, name, "stock")
    time1 = time.time() - start
    print(f"耗时: {time1:.2f}秒")

    print("\n第二次调用（使用缓存）...")
    start = time.time()
    data2 = fetch_full_stock_data_cached(symbol, name, "stock")
    time2 = time.time() - start
    print(f"耗时: {time2:.2f}秒")

    print(f"\n⚡ 性能提升: {time1/time2:.1f}x 倍加速！")

    # 测试2：缓存统计
    print("\n" + "="*70)
    print("测试2：缓存统计信息")
    print("="*70)
    get_cache_info()

    # 测试3：批量预热
    print("="*70)
    print("测试3：批量缓存预热")
    print("="*70)

    test_watchlist = [
        {"code": "002683", "name": "广东宏大"},
        {"code": "600519", "name": "贵州茅台"},
    ]

    warm_up_cache(test_watchlist)

    # 再次查看统计
    get_cache_info()
