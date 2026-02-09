"""
股票代码/名称智能查询模块
支持：代码查询、名称查询、模糊匹配
支持市场：A股、港股
"""

import akshare as ak
import json
import os
from datetime import datetime, timedelta

class StockFinder:
    """股票查询工具类"""

    def __init__(self, cache_file=None, include_hk=True):
        if cache_file is None:
            # 默认缓存到 cache/ 目录
            script_dir = os.path.dirname(os.path.abspath(__file__))
            cache_dir = os.path.join(script_dir, "cache")
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, "stock_list_cache.json")

        self.cache_file = cache_file
        self.hk_cache_file = cache_file.replace('.json', '_hk.json')
        self.stock_list = None  # A股列表
        self.hk_stock_list = None  # 港股列表
        self.include_hk = include_hk
        self._load_or_fetch_stock_list()
        # 港股列表改为懒加载，仅在实际需要时获取
        self._hk_loaded = False

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

    def _fetch_and_cache_stock_list(self, max_retries=3):
        """从 AkShare 获取股票列表并缓存（带重试机制）"""
        import time

        for attempt in range(max_retries):
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
                return  # 成功，退出

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 递增等待时间
                    print(f"⚠️  获取失败，{wait_time}秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    print(f"⚠️  获取股票列表失败: {e}")
                    # 尝试加载过期缓存作为备用
                    self._load_expired_cache()

    def _load_expired_cache(self):
        """加载过期缓存作为备用（网络失败时）"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.stock_list = cache_data['data']
                    cache_date = datetime.fromisoformat(cache_data['date'])
                    print(f"📋 已加载备用缓存（{len(self.stock_list)}只，更新于{cache_date.strftime('%Y-%m-%d')}）")
                    return
            except Exception:
                pass
        self.stock_list = []

    def _load_or_fetch_hk_stock_list(self):
        """加载或获取港股列表"""
        # 尝试从缓存加载
        if os.path.exists(self.hk_cache_file):
            try:
                with open(self.hk_cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    cache_date = datetime.fromisoformat(cache_data['date'])

                    # 如果缓存不超过7天，使用缓存
                    if datetime.now() - cache_date < timedelta(days=7):
                        self.hk_stock_list = cache_data['data']
                        print(f"📋 已加载港股列表缓存（{len(self.hk_stock_list)}只，更新于{cache_date.strftime('%Y-%m-%d')}）")
                        return
            except Exception:
                pass

        # 缓存过期或不存在，重新获取
        print("📥 正在获取港股列表...")
        self._fetch_and_cache_hk_stock_list()

    def _fetch_and_cache_hk_stock_list(self, max_retries=3):
        """从 AkShare 获取港股列表并缓存（优先新浪源，东财备用）"""
        import time

        for attempt in range(max_retries):
            try:
                # 优先使用新浪源（稳定，不受代理影响）
                try:
                    df_hk = ak.stock_hk_spot()
                    name_col = '中文名称'
                    code_col = '代码'
                except Exception:
                    # 备用：东财源
                    df_hk = ak.stock_hk_main_board_spot_em()
                    name_col = '名称'
                    code_col = '代码'

                # 转换为字典列表
                self.hk_stock_list = []
                for _, row in df_hk.iterrows():
                    code = str(row[code_col]).zfill(5)  # 确保5位代码
                    name = str(row[name_col]).strip()
                    if name and name != 'nan':
                        self.hk_stock_list.append({
                            'code': code,
                            'name': name,
                            'market': 'HK'
                        })

                # 保存缓存
                cache_data = {
                    'date': datetime.now().isoformat(),
                    'data': self.hk_stock_list
                }
                with open(self.hk_cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)

                print(f"✅ 已缓存 {len(self.hk_stock_list)} 只港股信息")
                return  # 成功，退出

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"⚠️  获取港股列表失败，{wait_time}秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    print(f"⚠️  获取港股列表失败: {e}")
                    self._load_expired_hk_cache()

    def _load_expired_hk_cache(self):
        """加载过期的港股缓存作为备用"""
        if os.path.exists(self.hk_cache_file):
            try:
                with open(self.hk_cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.hk_stock_list = cache_data['data']
                    cache_date = datetime.fromisoformat(cache_data['date'])
                    print(f"📋 已加载港股备用缓存（{len(self.hk_stock_list)}只，更新于{cache_date.strftime('%Y-%m-%d')}）")
                    return
            except Exception:
                pass
        self.hk_stock_list = []

    def find(self, query):
        """
        智能查找股票

        Args:
            query: 股票代码或名称（支持模糊匹配）

        Returns:
            - 精确匹配：返回 {'code': '600519', 'name': '贵州茅台', 'market': 'A'}
            - 多个匹配：返回列表 [{'code': '...', 'name': '...', 'market': '...'}, ...]
            - 无匹配：返回 None
        """
        if not self.stock_list:
            print("❌ 股票列表为空，无法查询")
            return None

        query = query.strip()

        # 处理港股代码格式（去除 .HK 后缀）
        is_hk_query = False
        if query.upper().endswith('.HK'):
            query = query[:-3]
            is_hk_query = True

        # 如果是5位数字，优先在港股中查找
        if query.isdigit() and len(query) == 5:
            is_hk_query = True

        # 合并搜索列表
        all_stocks = []
        for stock in self.stock_list:
            stock_with_market = stock.copy()
            stock_with_market['market'] = stock.get('market', 'A')
            all_stocks.append(stock_with_market)

        # 懒加载港股列表：仅港股查询时才加载
        if self.include_hk and not self._hk_loaded and is_hk_query:
            self._load_or_fetch_hk_stock_list()
            self._hk_loaded = True

        if self.include_hk and self.hk_stock_list:
            for stock in self.hk_stock_list:
                stock_with_market = stock.copy()
                stock_with_market['market'] = 'HK'
                all_stocks.append(stock_with_market)

        # 如果明确是港股查询，只在港股列表中搜索
        if is_hk_query and self.include_hk and self.hk_stock_list:
            search_list = [s for s in all_stocks if s['market'] == 'HK']
        else:
            search_list = all_stocks

        # 1. 尝试精确代码匹配
        for stock in search_list:
            if stock['code'] == query or stock['code'] == query.zfill(5):
                return stock

        # 2. 尝试精确名称匹配
        for stock in search_list:
            if stock['name'] == query:
                return stock

        # 3. 智能模糊匹配（去除常见前缀）
        # 清理查询词：去除空格
        clean_query = query.replace(' ', '')

        matches = []
        for stock in search_list:
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
            market_tag = "[港]" if stock.get('market') == 'HK' else "[A]"
            result += f"  [{i}] {market_tag} {stock['code']} - {stock['name']}\n"
        return result


def smart_stock_query(query):
    """
    智能股票查询（便捷函数）

    Args:
        query: 股票代码或名称

    Returns:
        (code, name, market) 元组，如果有多个匹配返回 (None, None, None)
        market: 'A' 或 'HK'
    """
    finder = StockFinder()
    result = finder.find(query)

    if result is None:
        print(f"❌ 未找到匹配的股票: {query}")
        return None, None, None

    # 单个匹配
    if isinstance(result, dict):
        market = result.get('market', 'A')
        market_tag = "[港股]" if market == 'HK' else "[A股]"
        print(f"✅ 找到: {market_tag} {result['code']} - {result['name']}")
        return result['code'], result['name'], market

    # 多个匹配
    if isinstance(result, list):
        print(finder.format_matches(result))
        print("\n💡 提示：请使用更精确的关键词，或直接使用股票代码")
        return None, None, None


# 测试代码
if __name__ == "__main__":
    finder = StockFinder()

    print("\n" + "="*60)
    print("测试1: 通过代码查询 A股")
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
    print("测试4: 港股代码查询 (小米)")
    print("="*60)
    result = finder.find("01810")
    print(result)

    print("\n" + "="*60)
    print("测试5: 港股名称查询 (小米集团)")
    print("="*60)
    result = finder.find("小米集团")
    print(result)

    print("\n" + "="*60)
    print("测试6: 带.HK后缀查询")
    print("="*60)
    result = finder.find("01810.HK")
    print(result)

    print("\n" + "="*60)
    print("测试7: 不存在的股票")
    print("="*60)
    result = finder.find("不存在的股票")
    print(result)
