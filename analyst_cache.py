"""
带缓存的数据抓取模块
在 analyst_data.py 基础上增加智能缓存功能
"""

import logging
import time
from datetime import datetime

from analyst_base import fetch_stock_data
from analyst_data import (
    fetch_chip_data,
    fetch_competitor_data,
    fetch_consensus_data,
    fetch_extended_data,
    fetch_institution_data,
    fetch_lockup_data,
    fetch_macro_etf_data,
    fetch_market_env_data,
    fetch_performance_data,
    fetch_sentiment_data,
    fetch_valuation_data,
)
from data_cache import CacheStrategy, DataCache

logger = logging.getLogger(__name__)

# 全局缓存实例
_cache = None


def get_cache():
    """获取全局缓存实例（单例模式）"""
    global _cache
    if _cache is None:
        _cache = DataCache()  # 使用默认路径 cache/quant_cache.db
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


def fetch_consensus_data_cached(symbol: str, stock_name: str) -> dict:
    """
    获取分析师一致预期数据（带缓存）

    缓存策略：7天
    """
    cache = get_cache()

    cached = cache.get(symbol, 'consensus')
    if cached:
        logger.info(f"✅ 一致预期缓存命中: {stock_name}")
        return cached

    logger.info(f"📊 抓取一致预期: {stock_name}")
    data = fetch_consensus_data(symbol, stock_name)

    cache.set(symbol, 'consensus', data, CacheStrategy.TTL_WEEK)

    return data


def fetch_market_env_data_cached(symbol: str, stock_name: str) -> dict:
    """
    获取大盘/板块环境数据（带缓存）

    缓存策略：盘中5分钟，盘后24小时（智能TTL）
    """
    cache = get_cache()

    cached = cache.get(symbol, 'market_env')
    if cached:
        logger.info(f"✅ 大盘环境缓存命中: {stock_name}")
        return cached

    logger.info(f"🌍 抓取大盘环境: {stock_name}")
    data = fetch_market_env_data(symbol, stock_name)

    cache.set(symbol, 'market_env', data, CacheStrategy.get_ttl('market_env'))

    return data


def fetch_lockup_data_cached(symbol: str, stock_name: str) -> dict:
    """
    获取解禁/减持风险数据（带缓存）

    缓存策略：7天
    """
    cache = get_cache()

    cached = cache.get(symbol, 'lockup')
    if cached:
        logger.info(f"✅ 解禁数据缓存命中: {stock_name}")
        return cached

    logger.info(f"🔓 抓取解禁数据: {stock_name}")
    data = fetch_lockup_data(symbol, stock_name)

    cache.set(symbol, 'lockup', data, CacheStrategy.TTL_WEEK)

    return data


def fetch_chip_data_cached(symbol: str, stock_name: str) -> dict:
    """
    获取筹码分布数据（带缓存）

    缓存策略：盘中5分钟，盘后24小时（智能TTL）
    """
    cache = get_cache()

    cached = cache.get(symbol, 'chip')
    if cached:
        logger.info(f"✅ 筹码数据缓存命中: {stock_name}")
        return cached

    logger.info(f"📊 抓取筹码数据: {stock_name}")
    data = fetch_chip_data(symbol, stock_name)

    cache.set(symbol, 'chip', data, CacheStrategy.get_ttl('chip'))

    return data


def fetch_institution_data_cached(symbol: str, stock_name: str) -> dict:
    """
    获取机构持仓变化数据（带缓存）

    缓存策略：30天（季度数据）
    """
    cache = get_cache()

    cached = cache.get(symbol, 'institution')
    if cached:
        logger.info(f"✅ 机构持仓缓存命中: {stock_name}")
        return cached

    logger.info(f"🏦 抓取机构持仓: {stock_name}")
    data = fetch_institution_data(symbol, stock_name)

    cache.set(symbol, 'institution', data, CacheStrategy.TTL_MONTH)

    return data


def fetch_competitor_data_cached(symbol: str, stock_name: str) -> dict:
    """
    获取竞争对手对比数据（带缓存）

    缓存策略：7天
    """
    cache = get_cache()

    cached = cache.get(symbol, 'competitor')
    if cached:
        logger.info(f"✅ 竞争对手缓存命中: {stock_name}")
        return cached

    logger.info(f"🔍 抓取竞争对手: {stock_name}")
    data = fetch_competitor_data(symbol, stock_name)

    cache.set(symbol, 'competitor', data, CacheStrategy.TTL_WEEK)

    return data


def fetch_extended_data_cached(symbol: str, stock_name: str) -> dict:
    """
    获取扩展数据（带缓存）

    包含：近20日行情、BOLL、季度趋势、行业对比、十大股东
    缓存策略：24小时（智能TTL）
    """
    cache = get_cache()

    cached = cache.get(symbol, 'extended')
    if cached:
        logger.info(f"✅ 扩展数据缓存命中: {stock_name}")
        return cached

    logger.info(f"📊 抓取扩展数据: {stock_name}")
    data = fetch_extended_data(symbol, stock_name)

    cache.set(symbol, 'extended', data, CacheStrategy.get_ttl('stock_base'))

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

    _fetch_start = time.time()

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

    # 5. 扩展数据（近20日行情、BOLL、季度趋势、行业对比、十大股东）—— 带缓存
    if asset_type == "stock":
        try:
            extended = fetch_extended_data_cached(symbol, stock_name)
            result.update(extended)
        except Exception as e:
            logger.error(f"扩展数据抓取失败: {e}")

    # 6. 新增维度（带缓存）
    if asset_type == "stock":
        # 分析师一致预期
        try:
            consensus = fetch_consensus_data_cached(symbol, stock_name)
            result.update(consensus)
        except Exception as e:
            logger.error(f"一致预期抓取失败: {e}")

        # 大盘/板块环境
        try:
            market_env = fetch_market_env_data_cached(symbol, stock_name)
            result.update(market_env)
        except Exception as e:
            logger.error(f"大盘环境抓取失败: {e}")

        # 解禁/减持风险
        try:
            lockup = fetch_lockup_data_cached(symbol, stock_name)
            result.update(lockup)
        except Exception as e:
            logger.error(f"解禁数据抓取失败: {e}")

        # 筹码分布
        try:
            chip = fetch_chip_data_cached(symbol, stock_name)
            result.update(chip)
        except Exception as e:
            logger.error(f"筹码数据抓取失败: {e}")

        # 机构持仓变化
        try:
            institution = fetch_institution_data_cached(symbol, stock_name)
            result.update(institution)
        except Exception as e:
            logger.error(f"机构持仓抓取失败: {e}")

        # 竞争对手对比
        try:
            competitor = fetch_competitor_data_cached(symbol, stock_name)
            result.update(competitor)
        except Exception as e:
            logger.error(f"竞争对手抓取失败: {e}")

    # 7. 交叉计算：PEG = PE-TTM / 预期利润增速
    try:
        pe_ttm_raw = result.get('pe_ttm_raw')
        eps_growth = result.get('eps_growth_rate_raw')
        if pe_ttm_raw and eps_growth and eps_growth > 0:
            peg = pe_ttm_raw / eps_growth
            result['peg'] = f"{peg:.2f}"
            result['peg_raw'] = peg
            if peg < 0.5:
                result['peg_signal'] = f"极度低估(PEG={peg:.2f}<0.5)"
            elif peg < 1:
                result['peg_signal'] = f"偏低估(PEG={peg:.2f}<1)"
            elif peg < 1.5:
                result['peg_signal'] = f"合理(PEG={peg:.2f})"
            elif peg < 2:
                result['peg_signal'] = f"偏高估(PEG={peg:.2f})"
            else:
                result['peg_signal'] = f"高估(PEG={peg:.2f}>2)"
            logger.info(f"✓ PEG计算成功: {result['peg_signal']}")
    except Exception as e:
        logger.debug(f"PEG计算失败: {e}")

    _fetch_elapsed = time.time() - _fetch_start
    logger.info(f"✓ {stock_name}({symbol}) 数据就绪 ({_fetch_elapsed:.1f}s)\n")

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
