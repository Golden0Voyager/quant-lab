#!/usr/bin/env python3
"""
新浪财经新闻获取模块（替代方案）
优势：免费、稳定、速度快、无需认证
"""
import requests
import pandas as pd
from datetime import datetime


def get_news_sina(stock_name: str, limit: int = 5) -> list:
    """
    从新浪财经获取个股新闻

    Args:
        stock_name: 股票名称（如"德赛西威"）
        limit: 获取新闻数量，默认5条

    Returns:
        新闻标题列表
    """
    url = "https://feed.sina.com.cn/api/roll/get"
    params = {
        "pageid": "153",       # 财经频道
        "lid": "2509",         # 股票分类
        "k": stock_name,       # 关键词
        "num": str(limit),
        "page": "1"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn/"
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if 'result' in data and 'data' in data['result']:
                news_list = data['result']['data']
                # 提取标题
                titles = [item.get('title', '') for item in news_list if item.get('title')]
                return titles[:limit]
    except Exception as e:
        pass

    return []


def get_news_eastmoney_announce(symbol: str, limit: int = 5) -> list:
    """
    从东方财富获取公司公告

    Args:
        symbol: 股票代码（如"002920"）
        limit: 获取公告数量，默认5条

    Returns:
        公告标题列表
    """
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
    params = {
        "sr": -1,
        "page_size": limit,
        "page_index": 1,
        "ann_type": "A",           # 所有公告
        "client_source": "web",
        "stock_list": symbol
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if 'data' in data and 'list' in data['data']:
                ann_list = data['data']['list']
                # 提取标题
                titles = [
                    item.get('title', item.get('art_title', ''))
                    for item in ann_list
                    if item.get('title') or item.get('art_title')
                ]
                return titles[:limit]
    except Exception as e:
        pass

    return []


# ==================== 测试 ====================
if __name__ == "__main__":
    print("="*70)
    print("🧪 测试新浪财经新闻获取")
    print("="*70)

    test_cases = [
        ("德赛西威", "002920"),
        ("华工科技", "000988"),
        ("贵州茅台", "600519")
    ]

    for name, code in test_cases:
        print(f"\n【{name} ({code})】")
        print("-"*70)

        # 测试新浪新闻
        news = get_news_sina(name, limit=5)
        if news:
            print(f"✅ 新浪新闻 ({len(news)}条):")
            for i, title in enumerate(news, 1):
                print(f"  {i}. {title}")
        else:
            print(f"⚠️ 新浪新闻: 无数据")

        # 测试东财公告
        announces = get_news_eastmoney_announce(code, limit=3)
        if announces:
            print(f"\n✅ 东财公告 ({len(announces)}条):")
            for i, title in enumerate(announces, 1):
                print(f"  {i}. {title[:60]}...")
        else:
            print(f"\n⚠️ 东财公告: 无数据")

    print("\n" + "="*70)
    print("测试完成")
    print("="*70)
