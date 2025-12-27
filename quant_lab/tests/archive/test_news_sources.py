#!/usr/bin/env python3
"""
测试各种金融新闻数据源
"""
import requests
import json
from datetime import datetime

TEST_SYMBOL = "002920"  # 德赛西威
TEST_NAME = "德赛西威"

print("="*70)
print("🔍 金融新闻数据源可用性测试")
print("="*70)

# ==================== 方案1: 新浪财经 ====================
print("\n【方案1】新浪财经 API")
print("-"*70)
try:
    # 新浪财经个股新闻接口
    url = f"https://feed.sina.com.cn/api/roll/get"
    params = {
        "pageid": "153",
        "lid": "2509",
        "k": TEST_NAME,
        "num": "10",
        "page": "1"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn/"
    }

    r = requests.get(url, params=params, headers=headers, timeout=10)
    print(f"状态码: {r.status_code}")

    if r.status_code == 200:
        data = r.json()
        if 'result' in data and 'data' in data['result']:
            news_list = data['result']['data']
            print(f"✅ 成功获取 {len(news_list)} 条新闻")
            print(f"数据格式: {list(news_list[0].keys()) if news_list else 'N/A'}")
            if news_list:
                for i, item in enumerate(news_list[:3], 1):
                    print(f"  {i}. {item.get('title', 'N/A')}")
        else:
            print(f"⚠️ 响应格式不符: {list(data.keys())}")
    else:
        print(f"❌ 请求失败")
except Exception as e:
    print(f"❌ 错误: {e}")

# ==================== 方案2: 腾讯财经 ====================
print("\n【方案2】腾讯财经 API")
print("-"*70)
try:
    # 腾讯财经新闻接口
    stock_code = f"sz{TEST_SYMBOL}" if TEST_SYMBOL.startswith(("0", "3")) else f"sh{TEST_SYMBOL}"
    url = f"https://qt.gtimg.cn/q={stock_code}"

    r = requests.get(url, timeout=10)
    print(f"状态码: {r.status_code}")

    if r.status_code == 200:
        print(f"✅ 接口可访问")
        print(f"响应示例: {r.text[:200]}...")

        # 尝试新闻接口
        news_url = f"https://stock.gtimg.cn/data/index.php"
        params = {
            "appn": "news",
            "action": "get",
            "code": stock_code,
            "num": "10"
        }
        r2 = requests.get(news_url, params=params, timeout=10)
        if r2.status_code == 200:
            print(f"✅ 新闻接口响应: {r2.text[:150]}...")
        else:
            print(f"⚠️ 新闻接口状态: {r2.status_code}")
    else:
        print(f"❌ 请求失败")
except Exception as e:
    print(f"❌ 错误: {e}")

# ==================== 方案3: 雪球 ====================
print("\n【方案3】雪球 API")
print("-"*70)
try:
    # 雪球个股动态接口
    stock_code = f"SZ{TEST_SYMBOL}" if TEST_SYMBOL.startswith(("0", "3")) else f"SH{TEST_SYMBOL}"
    url = f"https://stock.xueqiu.com/v5/stock/timeline/news.json"
    params = {
        "symbol": stock_code,
        "count": 10
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": f"https://xueqiu.com/S/{stock_code}",
        "Cookie": "xq_a_token=dummy"  # 雪球需要token
    }

    r = requests.get(url, params=params, headers=headers, timeout=10)
    print(f"状态码: {r.status_code}")

    if r.status_code == 200:
        data = r.json()
        if 'data' in data and 'items' in data['data']:
            news_list = data['data']['items']
            print(f"✅ 成功获取 {len(news_list)} 条动态")
            if news_list:
                for i, item in enumerate(news_list[:3], 1):
                    print(f"  {i}. {item.get('title', item.get('description', 'N/A')[:50])}")
        else:
            print(f"⚠️ 响应格式: {list(data.keys())}")
    elif r.status_code == 403:
        print(f"⚠️ 需要认证（Cookie/Token）")
    else:
        print(f"❌ 状态码: {r.status_code}")
except Exception as e:
    print(f"❌ 错误: {e}")

# ==================== 方案4: 东方财富（资讯中心）====================
print("\n【方案4】东方财富资讯中心")
print("-"*70)
try:
    # 东方财富资讯中心API
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
    params = {
        "sr": -1,
        "page_size": 10,
        "page_index": 1,
        "ann_type": "A",
        "client_source": "web",
        "stock_list": TEST_SYMBOL
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    r = requests.get(url, params=params, headers=headers, timeout=10)
    print(f"状态码: {r.status_code}")

    if r.status_code == 200:
        data = r.json()
        if 'data' in data and 'list' in data['data']:
            news_list = data['data']['list']
            print(f"✅ 成功获取 {len(news_list)} 条公告")
            if news_list:
                for i, item in enumerate(news_list[:3], 1):
                    print(f"  {i}. {item.get('title', item.get('art_title', 'N/A'))}")
        else:
            print(f"⚠️ 响应格式: {list(data.keys())}")
    else:
        print(f"❌ 状态码: {r.status_code}")
except Exception as e:
    print(f"❌ 错误: {e}")

# ==================== 方案5: 网易财经 ====================
print("\n【方案5】网易财经")
print("-"*70)
try:
    # 网易财经新闻接口
    stock_code = f"0{TEST_SYMBOL}" if TEST_SYMBOL.startswith(("0", "3")) else f"1{TEST_SYMBOL}"
    url = f"https://quotes.money.163.com/service/chddata.html"
    params = {
        "code": stock_code,
        "start": "20250101",
        "end": datetime.now().strftime("%Y%m%d"),
        "fields": "TCLOSE"
    }

    r = requests.get(url, params=params, timeout=10)
    print(f"状态码: {r.status_code}")

    if r.status_code == 200:
        print(f"✅ 接口可访问（数据接口）")
        # 尝试新闻接口
        news_url = f"https://money.163.com/stock/{TEST_SYMBOL}.html"
        r2 = requests.get(news_url, timeout=10)
        print(f"新闻页面状态: {r2.status_code}")
    else:
        print(f"❌ 状态码: {r.status_code}")
except Exception as e:
    print(f"❌ 错误: {e}")

# ==================== 方案6: 同花顺 ====================
print("\n【方案6】同花顺 API")
print("-"*70)
try:
    # 同花顺新闻接口
    url = "http://news.10jqka.com.cn/realtimenews.html"
    params = {
        "page": 1,
        "tag": TEST_SYMBOL
    }

    r = requests.get(url, params=params, timeout=10)
    print(f"状态码: {r.status_code}")

    if r.status_code == 200:
        print(f"✅ 接口可访问")
        print(f"响应类型: {r.headers.get('content-type', 'unknown')}")
    else:
        print(f"❌ 状态码: {r.status_code}")
except Exception as e:
    print(f"❌ 错误: {e}")

print("\n" + "="*70)
print("测试完成")
print("="*70)
