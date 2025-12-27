#!/usr/bin/env python3
"""
修复版的东方财富新闻接口
替代 akshare.stock_news_em
"""
import json
import re
import pandas as pd
import requests


def stock_news_em_fixed(symbol: str = "603777") -> pd.DataFrame:
    """
    东方财富-个股新闻-最近 10 条新闻（修复版）

    修复内容：
    1. 动态提取 JSONP callback 函数名（不再硬编码）
    2. 更健壮的 JSON 解析逻辑
    3. 更好的错误处理

    :param symbol: 股票代码
    :type symbol: str
    :return: 个股新闻
    :rtype: pandas.DataFrame
    """
    url = "https://search-api-web.eastmoney.com/search/jsonp"
    inner_param = {
        "uid": "",
        "keyword": symbol,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "default",
                "pageIndex": 1,
                "pageSize": 10,
                "preTag": "<em>",
                "postTag": "</em>"
            }
        }
    }

    # 动态生成 callback 参数（使用当前时间戳）
    import time
    timestamp = int(time.time() * 1000)
    callback = f"jQuery{timestamp}"

    params = {
        "cb": callback,
        "param": json.dumps(inner_param, ensure_ascii=False),
        "_": str(timestamp)
    }

    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "referer": f"https://so.eastmoney.com/news/s?keyword={symbol}"
    }

    r = requests.get(url, params=params, headers=headers, timeout=10)
    data_text = r.text

    # 🔧 修复点：使用正则表达式动态提取 JSON 内容
    # 匹配 jQuery...({...}) 格式
    match = re.search(r'jQuery\d+_\d+\((.*)\)$', data_text)
    if match:
        json_text = match.group(1)
    else:
        # 如果正则匹配失败，尝试简单去除首尾
        if '(' in data_text and data_text.endswith(')'):
            json_text = data_text[data_text.index('(') + 1:-1]
        else:
            raise ValueError("无法解析 JSONP 响应格式")

    # 解析 JSON
    data_json = json.loads(json_text)

    # 检查是否有新闻数据
    if 'result' not in data_json or 'cmsArticleWebOld' not in data_json['result']:
        return pd.DataFrame()  # 返回空 DataFrame

    news_list = data_json['result']['cmsArticleWebOld']
    if not news_list:
        return pd.DataFrame()

    # 构建 DataFrame
    temp_df = pd.DataFrame(news_list)
    temp_df["url"] = "http://finance.eastmoney.com/a/" + temp_df["code"] + ".html"
    temp_df.rename(
        columns={
            "date": "发布时间",
            "mediaName": "文章来源",
            "code": "-",
            "title": "新闻标题",
            "content": "新闻内容",
            "url": "新闻链接",
            "image": "-",
        },
        inplace=True,
    )
    temp_df["关键词"] = symbol
    temp_df = temp_df[
        [
            "关键词",
            "新闻标题",
            "新闻内容",
            "发布时间",
            "文章来源",
            "新闻链接",
        ]
    ]

    # 清理标题中的 HTML 标签
    temp_df["新闻标题"] = (
        temp_df["新闻标题"]
        .str.replace(r"<em>", "", regex=True)
        .str.replace(r"</em>", "", regex=True)
    )

    return temp_df


# 测试函数
if __name__ == "__main__":
    print("🧪 测试修复版新闻接口...\n")

    test_symbols = ["002920", "000988", "600519"]

    for symbol in test_symbols:
        print(f"{'='*60}")
        print(f"测试股票: {symbol}")
        print('='*60)

        try:
            df = stock_news_em_fixed(symbol)

            if df.empty:
                print(f"⚠️ 未获取到新闻数据")
            else:
                print(f"✅ 成功获取 {len(df)} 条新闻")
                print(f"\n前 3 条新闻标题:")
                for idx, title in enumerate(df['新闻标题'].head(3), 1):
                    print(f"  {idx}. {title}")

        except Exception as e:
            print(f"❌ 失败: {e}")

        print()
