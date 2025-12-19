"""
股票代码/名称智能查询模块
支持：代码查询、名称查询、模糊匹配
"""

import akshare as ak
import json
import os
from datetime import datetime, timedelta

class StockFinder:
    """股票查询工具类"""

    def __init__(self, cache_file=None):
        if cache_file is None:
            # 默认缓存到 quant_lab 目录
            script_dir = os.path.dirname(os.path.abspath(__file__))
            cache_file = os.path.join(script_dir, ".stock_list_cache.json")

        self.cache_file = cache_file
        self.stock_list = None
        self._load_or_fetch_stock_list()

    def _load_or_fetch_stock_list(self):
        """加载或获取股票列表"""
        # 尝试从缓存加载
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                cache_date = datetime.fromisoformat(cache_data['date'])

                # 如果缓存不超过7天，使用缓存
                if datetime.now() - cache_date < timedelta(days=7):
                    self.stock_list = cache_data['data']
                    print(f"📋 已加载股票列表缓存（{len(self.stock_list)}只，更新于{cache_date.strftime('%Y-%m-%d')}）")
                    return

        # 缓存过期或不存在，重新获取
        print("📥 正在获取最新股票列表...")
        self._fetch_and_cache_stock_list()

    def _fetch_and_cache_stock_list(self):
        """从 AkShare 获取股票列表并缓存"""
        try:
            # 获取 A 股列表
            df_a = ak.stock_info_a_code_name()

            # 转换为字典列表
            self.stock_list = []
            for _, row in df_a.iterrows():
                self.stock_list.append({
                    'code': row['code'],
                    'name': row['name']
                })

            # 保存缓存
            cache_data = {
                'date': datetime.now().isoformat(),
                'data': self.stock_list
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            print(f"✅ 已缓存 {len(self.stock_list)} 只股票信息")

        except Exception as e:
            print(f"⚠️  获取股票列表失败: {e}")
            self.stock_list = []

    def find(self, query):
        """
        智能查找股票

        Args:
            query: 股票代码或名称（支持模糊匹配）

        Returns:
            - 精确匹配：返回 {'code': '600519', 'name': '贵州茅台'}
            - 多个匹配：返回列表 [{'code': '...', 'name': '...'}, ...]
            - 无匹配：返回 None
        """
        if not self.stock_list:
            print("❌ 股票列表为空，无法查询")
            return None

        query = query.strip()

        # 1. 尝试精确代码匹配
        for stock in self.stock_list:
            if stock['code'] == query:
                return stock

        # 2. 尝试精确名称匹配
        for stock in self.stock_list:
            if stock['name'] == query:
                return stock

        # 3. 智能模糊匹配（去除常见前缀）
        # 清理查询词：去除空格
        clean_query = query.replace(' ', '')

        matches = []
        for stock in self.stock_list:
            # 清理股票名称：去除 XD、XR、DR、ST、*ST、N 等前缀
            clean_name = stock['name']
            for prefix in ['*ST', 'ST', 'XD', 'XR', 'DR', 'N']:
                if clean_name.startswith(prefix):
                    clean_name = clean_name[len(prefix):]
                    break

            # 检查是否匹配（更宽松的匹配）
            # 1. 查询词在股票名或代码中
            if clean_query in clean_name or clean_query in stock['code']:
                matches.append(stock)
            # 2. 股票名在查询词中（如查"贵州茅台"，股票名"贵州茅"）
            elif clean_name in clean_query:
                matches.append(stock)
            # 3. 查询词的主要部分在股票名中（如查"茅台"，匹配"贵州茅"）
            elif len(clean_query) >= 2 and any(clean_query in part for part in [clean_name, stock['name']]):
                matches.append(stock)

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            return matches  # 返回多个匹配，让用户选择
        else:
            return None

    def format_matches(self, matches):
        """格式化多个匹配结果"""
        if not matches:
            return "未找到匹配的股票"

        result = "找到多个匹配项：\n"
        for i, stock in enumerate(matches, 1):
            result += f"  [{i}] {stock['code']} - {stock['name']}\n"
        return result


def smart_stock_query(query):
    """
    智能股票查询（便捷函数）

    Args:
        query: 股票代码或名称

    Returns:
        (code, name) 元组，如果有多个匹配返回 None
    """
    finder = StockFinder()
    result = finder.find(query)

    if result is None:
        print(f"❌ 未找到匹配的股票: {query}")
        return None, None

    # 单个匹配
    if isinstance(result, dict):
        print(f"✅ 找到: {result['code']} - {result['name']}")
        return result['code'], result['name']

    # 多个匹配
    if isinstance(result, list):
        print(finder.format_matches(result))
        print("\n💡 提示：请使用更精确的关键词，或直接使用股票代码")
        return None, None


# 测试代码
if __name__ == "__main__":
    finder = StockFinder()

    print("\n" + "="*60)
    print("测试1: 通过代码查询")
    print("="*60)
    result = finder.find("600519")
    print(result)

    print("\n" + "="*60)
    print("测试2: 通过完整名称查询")
    print("="*60)
    result = finder.find("贵州茅台")
    print(result)

    print("\n" + "="*60)
    print("测试3: 模糊查询")
    print("="*60)
    result = finder.find("茅台")
    if isinstance(result, list):
        print(finder.format_matches(result))
    else:
        print(result)

    print("\n" + "="*60)
    print("测试4: 不存在的股票")
    print("="*60)
    result = finder.find("不存在的股票")
    print(result)
