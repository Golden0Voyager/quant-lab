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
        self.etf_cache_file = cache_file.replace('.json', '_etf.json')
        self.fund_cache_file = cache_file.replace('.json', '_fund.json')
        
        self.stock_list = None  # A股列表
        self.hk_stock_list = None  # 港股列表
        self.etf_list = None  # ETF列表
        self.fund_list = None  # 场外基金列表
        
        self.include_hk = include_hk
        self._load_or_fetch_stock_list()
        self._load_or_fetch_etf_list()
        self._load_or_fetch_fund_list()
        
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

    def _load_or_fetch_etf_list(self):
        """加载或获取 ETF 列表"""
        if os.path.exists(self.etf_cache_file):
            with open(self.etf_cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                cache_date = datetime.fromisoformat(cache_data['date'])
                if datetime.now() - cache_date < timedelta(days=7):
                    self.etf_list = cache_data['data']
                    return

        print("📥 正在获取最新 ETF 列表...")
        self._fetch_and_cache_etf_list()

    def _fetch_and_cache_etf_list(self, max_retries=3):
        """从 AkShare 获取 ETF 列表并缓存（使用新浪源确保稳定性）"""
        import time
        # 清除临时代理环境变量，确保国内接口直连
        env_copy = os.environ.copy()
        for var in ['http_proxy', 'https_proxy', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY']:
            if var in os.environ:
                del os.environ[var]

        for attempt in range(max_retries):
            try:
                # 采用新浪源，因为它在境外环境下响应更稳健
                df_etf = ak.fund_etf_category_sina(symbol="ETF基金")
                if df_etf is not None and not df_etf.empty:
                    self.etf_list = []
                    for _, row in df_etf.iterrows():
                        # 清洗代码：去除 sh/sz 前缀
                        raw_code = str(row['代码'])
                        clean_code = raw_code.replace('sh', '').replace('sz', '')
                        self.etf_list.append({
                            'code': clean_code,
                            'name': str(row['名称']),
                            'asset_type': 'etf'
                        })
                    cache_data = {'date': datetime.now().isoformat(), 'data': self.etf_list}
                    with open(self.etf_cache_file, 'w', encoding='utf-8') as f:
                        json.dump(cache_data, f, ensure_ascii=False, indent=2)
                    print(f"✅ 已缓存 {len(self.etf_list)} 只 ETF 信息")
                    # 恢复环境变量
                    os.environ.clear()
                    os.environ.update(env_copy)
                    return
            except Exception as e:
                time.sleep(2 * (attempt + 1))
        
        # 恢复环境变量
        os.environ.clear()
        os.environ.update(env_copy)
        self.etf_list = []

    def _load_or_fetch_fund_list(self):
        """加载或获取场外基金列表"""
        if os.path.exists(self.fund_cache_file):
            with open(self.fund_cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                cache_date = datetime.fromisoformat(cache_data['date'])
                if datetime.now() - cache_date < timedelta(days=7):
                    self.fund_list = cache_data['data']
                    return

        print("📥 正在获取最新场外基金列表...")
        self._fetch_and_cache_fund_list()

    def _fetch_and_cache_fund_list(self, max_retries=3):
        """从 AkShare 获取场外基金列表并缓存（增加代理容错）"""
        import time
        env_copy = os.environ.copy()
        for var in ['http_proxy', 'https_proxy', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY']:
            if var in os.environ:
                del os.environ[var]

        for attempt in range(max_retries):
            try:
                df_fund = ak.fund_open_fund_daily_em()
                self.fund_list = []
                for _, row in df_fund.iterrows():
                    self.fund_list.append({
                        'code': str(row['基金代码']),
                        'name': str(row['基金简称']),
                        'asset_type': 'fund'
                    })
                cache_data = {'date': datetime.now().isoformat(), 'data': self.fund_list}
                with open(self.fund_cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                print(f"✅ 已缓存 {len(self.fund_list)} 只场外基金信息")
                os.environ.clear()
                os.environ.update(env_copy)
                return
            except Exception as e:
                time.sleep(2 * (attempt + 1))
        
        os.environ.clear()
        os.environ.update(env_copy)
        self.fund_list = []

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
        智能查找标的（股票、ETF、场外基金）

        Args:
            query: 代码或名称（支持模糊匹配）

        Returns:
            - 精确匹配：返回 {'code': '...', 'name': '...', 'market': '...', 'asset_type': '...'}
            - 多个匹配：返回列表
            - 无匹配：返回 None
        """
        if not self.stock_list:
            print("❌ 基础列表为空，无法查询")
            return None

        query = query.strip()

        # --- 1. 构建搜索全集 (按优先级排序) ---
        search_list = []
        
        # A股 (标记 asset_type)
        for s in self.stock_list:
            item = s.copy()
            item['market'] = 'A'
            item['asset_type'] = 'stock'
            search_list.append(item)

        # 港股 (懒加载)
        is_hk_query = query.upper().endswith('.HK') or (query.isdigit() and len(query) == 5)
        if self.include_hk and not self._hk_loaded and is_hk_query:
            self._load_or_fetch_hk_stock_list()
            self._hk_loaded = True
        
        if self.include_hk and self.hk_stock_list:
            for s in self.hk_stock_list:
                item = s.copy()
                item['market'] = 'HK'
                item['asset_type'] = 'stock'
                search_list.append(item)

        # ETF
        if self.etf_list:
            search_list.extend(self.etf_list)

        # 场外基金
        if self.fund_list:
            search_list.extend(self.fund_list)

        # --- 2. 精确匹配策略 ---
        # 代码精确匹配 (针对基金代码 6位数字)
        for item in search_list:
            if item['code'] == query or item['code'] == query.zfill(6 if item['asset_type']=='fund' else 5):
                return item

        # 名称精确匹配
        for item in search_list:
            if item['name'] == query:
                return item

        # --- 3. 智能模糊匹配 ---
        clean_query = query.replace(' ', '').upper()
        matches = []
        
        for item in search_list:
            clean_name = item['name'].upper()
            # 移除常见前缀以增强匹配
            for prefix in ['*ST', 'ST', 'XD', 'XR', 'DR', 'N']:
                if clean_name.startswith(prefix):
                    clean_name = clean_name[len(prefix):]
                    break
            
            if clean_query in clean_name or clean_query in item['code']:
                matches.append(item)
            elif clean_name in clean_query:
                matches.append(item)

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            # 去重处理 (防止不同接口重复记录)
            seen = set()
            unique_matches = []
            for m in matches:
                key = f"{m['code']}_{m['asset_type']}"
                if key not in seen:
                    unique_matches.append(m)
                    seen.add(key)
            return unique_matches if len(unique_matches) > 1 else unique_matches[0]
        
        return None

    def format_matches(self, matches):
        """格式化多个匹配结果"""
        if not matches:
            return "未找到匹配的标的"

        result = "找到多个匹配项：\n"
        type_map = {'stock': '股票', 'etf': '场内ETF', 'fund': '场外基金'}
        for i, item in enumerate(matches, 1):
            market_tag = "[港]" if item.get('market') == 'HK' else "[A]"
            asset_tag = type_map.get(item.get('asset_type', 'stock'), '标的')
            result += f"  [{i}] {market_tag}{asset_tag} {item['code']} - {item['name']}\n"
        return result


def smart_stock_query(query):
    """
    智能标的查询（便捷函数）
    """
    finder = StockFinder()
    
    # 检测是否为美股代码（纯字母，或带.的纯字母如 BRK.B）
    is_us = query.isalpha() or ('.' in query and query.replace('.', '').isalpha())
    if is_us:
        print(f"✅ 探测到: [美股代码] {query}")
        return query, query, 'US', 'stock'
        
    result = finder.find(query)

    if result is None:
        print(f"❌ 未找到匹配的标的: {query}")
        return None, None, None, None

    # 单个匹配
    if isinstance(result, dict):
        market = result.get('market', 'A')
        asset_type = result.get('asset_type', 'stock')
        type_str = "港股" if market == 'HK' else ("ETF" if asset_type == 'etf' else ("场外基金" if asset_type == 'fund' else "A股"))
        print(f"✅ 找到: [{type_str}] {result['code']} - {result['name']}")
        return result['code'], result['name'], market, asset_type

    # 多个匹配
    if isinstance(result, list):
        print(finder.format_matches(result))
        print("\n💡 提示：请使用更精确的关键词，或直接使用代码")
        return None, None, None, None


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
