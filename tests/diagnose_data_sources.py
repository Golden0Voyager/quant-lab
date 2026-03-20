"""
多数据源管理器 - 解决数据缺失问题
实现智能降级和容错机制
"""

import logging
import akshare as ak
import pandas as pd
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class DataSourceManager:
    """
    数据源管理器：智能多源降级 + 质量监控

    设计理念：
    - 永远不返回空数据
    - 自动降级到备用数据源
    - 记录数据源成功率
    - 优先使用成功率高的源
    """

    def __init__(self):
        # 数据源成功率统计
        self.source_stats = {
            'tushare': {'success': 0, 'fail': 0},
            'eastmoney': {'success': 0, 'fail': 0},
            'sina': {'success': 0, 'fail': 0},
            'cached': {'success': 0, 'fail': 0}
        }

    def get_valuation_data(self, symbol: str, stock_name: str) -> Tuple[Dict[str, Any], str]:
        """
        获取估值数据（PE/PB/PS/股息率）

        Returns:
            (数据字典, 数据源名称)
        """
        # 数据源降级链路
        sources = [
            ('eastmoney_spot', self._fetch_from_eastmoney_spot),
            ('sina', self._fetch_from_sina),
        ]

        for source_name, fetch_func in sources:
            try:
                logger.info(f"🔄 尝试数据源: {source_name}")
                data = fetch_func(symbol, stock_name)

                if self._validate_valuation_data(data):
                    self._record_success(source_name)
                    logger.info(f"✅ 数据源 {source_name} 成功")
                    return data, source_name
                else:
                    logger.warning(f"⚠️  数据源 {source_name} 返回数据不完整")
                    self._record_fail(source_name)

            except Exception as e:
                logger.warning(f"❌ 数据源 {source_name} 失败: {type(e).__name__}")
                self._record_fail(source_name)
                continue

        # 所有数据源失败，返回空壳数据
        logger.error(f"❌ 所有数据源均失败，返回降级数据")
        return self._get_fallback_data(), "fallback"

    def _fetch_from_eastmoney_spot(self, symbol: str, stock_name: str) -> Dict[str, Any]:
        """
        方案1：东方财富个股实时行情（快速但不含估值）+ 单独查询估值
        """
        data = {}

        # 1. 获取基础信息
        info_df = ak.stock_individual_info_em(symbol=symbol)
        if not info_df.empty:
            info_dict = dict(zip(info_df['item'], info_df['value']))
            market_cap = info_dict.get('总市值', None)
            if market_cap:
                data['market_cap'] = float(market_cap)
                data['market_cap_display'] = f"{float(market_cap)/1e8:.0f}亿"

        # 2. 尝试获取A股行情（包含PE/PB）- 使用缓存优化
        # 为避免慢速，只查询特定股票
        try:
            # 使用个股财务分析获取估值（更快）
            financial_df = ak.stock_a_lg_indicator(symbol=symbol)
            if not financial_df.empty:
                latest = financial_df.iloc[-1]

                # 提取估值指标
                pe_ttm = latest.get('市盈率', None)
                pb = latest.get('市净率', None)

                if pd.notna(pe_ttm) and pe_ttm > 0:
                    data['pe_ttm'] = f"{float(pe_ttm):.2f}"
                    data['pe_ttm_raw'] = float(pe_ttm)
                else:
                    data['pe_ttm'] = "N/A"
                    data['pe_ttm_raw'] = None

                if pd.notna(pb) and pb > 0:
                    data['pb'] = f"{float(pb):.2f}"
                    data['pb_raw'] = float(pb)
                else:
                    data['pb'] = "N/A"
                    data['pb_raw'] = None

                # ROE（顺便获取）
                roe = latest.get('净资产收益率', None)
                if pd.notna(roe):
                    data['roe'] = f"{float(roe):.2f}%"
                    data['roe_raw'] = float(roe)

        except Exception as e:
            logger.debug(f"个股财务分析失败: {e}")
            # 继续尝试其他字段

        # 3. 股息率（单独查询）
        try:
            dividend_df = ak.stock_dividend_cninfo(symbol=symbol)
            if not dividend_df.empty:
                latest_dividend = dividend_df.iloc[-1]
                div_yield = latest_dividend.get('股息率(%)', None)
                if pd.notna(div_yield) and div_yield > 0:
                    data['dividend_yield'] = f"{float(div_yield):.2f}%"
                    data['dividend_yield_raw'] = float(div_yield)
                else:
                    data['dividend_yield'] = "无分红"
                    data['dividend_yield_raw'] = 0
        except Exception as e:
            logger.debug(f"股息率查询失败: {e}")
            data['dividend_yield'] = "N/A"
            data['dividend_yield_raw'] = 0

        # 填充默认值
        if 'pe_ttm' not in data:
            data['pe_ttm'] = "N/A"
            data['pe_ttm_raw'] = None
        if 'pb' not in data:
            data['pb'] = "N/A"
            data['pb_raw'] = None
        if 'dividend_yield' not in data:
            data['dividend_yield'] = "N/A"
            data['dividend_yield_raw'] = 0

        # PS暂时无法计算（需要营收数据）
        data['ps_ttm'] = "N/A"
        data['ps_ttm_raw'] = None

        # 生成摘要
        data['valuation_summary'] = (
            f"PE-TTM: {data['pe_ttm']} | "
            f"PB: {data['pb']} | "
            f"PS-TTM: {data['ps_ttm']} | "
            f"股息率(TTM): {data['dividend_yield']}"
        )

        return data

    def _fetch_from_sina(self, symbol: str, stock_name: str) -> Dict[str, Any]:
        """
        方案2：新浪财经API（备用）
        """
        data = {}

        try:
            # 新浪实时行情
            realtime_df = ak.stock_zh_a_spot()
            stock_data = realtime_df[realtime_df['代码'] == symbol]

            if not stock_data.empty:
                stock = stock_data.iloc[0]

                # 提取估值数据
                pe_ttm = stock.get('市盈率动态', None)
                if pd.notna(pe_ttm) and pe_ttm > 0:
                    data['pe_ttm'] = f"{float(pe_ttm):.2f}"
                    data['pe_ttm_raw'] = float(pe_ttm)

                pb = stock.get('市净率', None)
                if pd.notna(pb) and pb > 0:
                    data['pb'] = f"{float(pb):.2f}"
                    data['pb_raw'] = float(pb)

                market_cap = stock.get('总市值', None)
                if pd.notna(market_cap):
                    data['market_cap'] = float(market_cap)
                    data['market_cap_display'] = f"{float(market_cap)/1e8:.0f}亿"

        except Exception as e:
            logger.debug(f"新浪API失败: {e}")

        # 填充默认值
        for key in ['pe_ttm', 'pb', 'ps_ttm', 'dividend_yield']:
            if key not in data:
                data[key] = "N/A"
                data[f"{key}_raw"] = None if key != 'dividend_yield' else 0

        data['valuation_summary'] = (
            f"PE-TTM: {data['pe_ttm']} | "
            f"PB: {data['pb']} | "
            f"PS-TTM: {data['ps_ttm']} | "
            f"股息率(TTM): {data['dividend_yield']}"
        )

        return data

    def _validate_valuation_data(self, data: Dict[str, Any]) -> bool:
        """
        验证估值数据完整性

        至少需要满足以下条件之一：
        - PE-TTM 有效
        - PB 有效
        - 股息率 > 0
        """
        has_pe = data.get('pe_ttm') != "N/A" and data.get('pe_ttm_raw') is not None
        has_pb = data.get('pb') != "N/A" and data.get('pb_raw') is not None
        has_dividend = data.get('dividend_yield_raw', 0) > 0

        # 至少有一个估值指标有效
        return has_pe or has_pb or has_dividend

    def _get_fallback_data(self) -> Dict[str, Any]:
        """
        降级数据：所有数据源失败时返回
        """
        return {
            'pe_ttm': "N/A",
            'pe_ttm_raw': None,
            'pb': "N/A",
            'pb_raw': None,
            'ps_ttm': "N/A",
            'ps_ttm_raw': None,
            'dividend_yield': "N/A",
            'dividend_yield_raw': 0,
            'market_cap': None,
            'market_cap_display': "N/A",
            'valuation_summary': "⚠️ 估值数据获取失败，所有数据源均不可用",
            'pe_percentile': "N/A",
            'pb_percentile': "N/A",
            'dividend_percentile': "N/A"
        }

    def _record_success(self, source_name: str):
        """记录数据源成功"""
        if source_name in self.source_stats:
            self.source_stats[source_name]['success'] += 1

    def _record_fail(self, source_name: str):
        """记录数据源失败"""
        if source_name in self.source_stats:
            self.source_stats[source_name]['fail'] += 1

    def get_success_rates(self) -> Dict[str, float]:
        """
        获取各数据源成功率

        Returns:
            {数据源: 成功率}
        """
        rates = {}
        for source, stats in self.source_stats.items():
            total = stats['success'] + stats['fail']
            if total > 0:
                rates[source] = stats['success'] / total * 100
            else:
                rates[source] = 0.0
        return rates

    def print_stats(self):
        """打印数据源统计"""
        rates = self.get_success_rates()

        print("\n" + "="*60)
        print("📊 数据源质量报告")
        print("="*60)

        for source, rate in sorted(rates.items(), key=lambda x: x[1], reverse=True):
            stats = self.source_stats[source]
            total = stats['success'] + stats['fail']

            if total > 0:
                emoji = "✅" if rate >= 80 else "⚠️" if rate >= 50 else "❌"
                print(f"{emoji} {source:15s}: {rate:5.1f}% ({stats['success']}/{total})")

        print("="*60)


# 全局单例
_data_source_manager = None

def get_data_source_manager() -> DataSourceManager:
    """获取全局数据源管理器（单例）"""
    global _data_source_manager
    if _data_source_manager is None:
        _data_source_manager = DataSourceManager()
    return _data_source_manager


if __name__ == "__main__":
    # 测试数据源管理器
    manager = DataSourceManager()

    # 测试多只股票
    test_stocks = [
        ("688122", "西部超导"),
        ("600519", "贵州茅台"),
        ("000001", "平安银行"),
    ]

    for symbol, name in test_stocks:
        print(f"\n{'='*60}")
        print(f"测试: {name} ({symbol})")
        print(f"{'='*60}")

        data, source = manager.get_valuation_data(symbol, name)

        print(f"✅ 数据源: {source}")
        print(f"📊 估值摘要: {data['valuation_summary']}")
        print(f"   PE-TTM: {data['pe_ttm']}")
        print(f"   PB: {data['pb']}")
        print(f"   股息率: {data['dividend_yield']}")
        print(f"   市值: {data.get('market_cap_display', 'N/A')}")

    # 打印统计
    manager.print_stats()
