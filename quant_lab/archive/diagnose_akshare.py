#!/usr/bin/env python3
"""
诊断 AkShare 新闻接口问题
"""
import json
import requests

symbol = "002920"  # 德赛西威

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
import time
timestamp = int(time.time() * 1000)
callback = f"jQuery{timestamp}"

params = {
    "cb": callback,
    "param": json.dumps(inner_param, ensure_ascii=False),
    "_": str(timestamp)
}
headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

print("🔍 正在请求东方财富新闻接口...")
r = requests.get(url, params=params, headers=headers)

print(f"\n📊 响应状态码: {r.status_code}")
print(f"📊 响应长度: {len(r.text)} 字符\n")

print("="*60)
print("📄 原始响应内容（前 500 字符）:")
print("="*60)
print(r.text[:500])
print("...")
print("="*60)

# 尝试解析
print("\n🔧 尝试解析 JSONP...")

# AkShare 的解析方式
try:
    # 使用正则表达式动态提取
    import re
    match = re.search(r'(jQuery\d+_\d+)\((.*)\)$', r.text)

    if match:
        actual_callback = match.group(1)
        json_text = match.group(2)
        print(f"\n✅ 成功去除 JSONP wrapper")
        print(f"📊 实际 callback: {actual_callback}")
        print(f"📊 JSON 长度: {len(json_text)} 字符")
        print(f"📊 JSON 开头: {json_text[:200]}")

        # 尝试解析
        data = json.loads(json_text)
        print(f"\n✅ JSON 解析成功！")
        print(f"📊 返回的键: {list(data.keys())}")

        print(f"\n📊 返回数据的所有键:")
        print(f"  顶层: {list(data.keys())}")

        if 'result' in data:
            print(f"  result 层: {list(data['result'].keys())}")

            if 'cmsArticleWebOld' in data['result']:
                news_count = len(data['result']['cmsArticleWebOld'])
                print(f"\n📰 cmsArticleWebOld 新闻数量: {news_count}")

                if news_count > 0:
                    print(f"\n📄 第一条新闻:")
                    first = data['result']['cmsArticleWebOld'][0]
                    print(f"  标题: {first.get('title', 'N/A')}")
                    print(f"  时间: {first.get('date', 'N/A')}")
            else:
                print(f"\n⚠️ result 中没有 cmsArticleWebOld")
                print(f"可用的键: {list(data['result'].keys())}")

                # 尝试找到其他可能的新闻数据
                for key in data['result'].keys():
                    if isinstance(data['result'][key], list) and len(data['result'][key]) > 0:
                        print(f"\n发现列表数据: {key} (长度: {len(data['result'][key])})")
                        print(f"第一条数据示例: {data['result'][key][0]}")
        else:
            print("⚠️ 数据中没有 result 键")
            print(f"完整数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
    else:
        print(f"❌ 响应不是预期的 JSONP 格式")
        print(f"预期开头: {callback}")
        print(f"实际开头: {r.text[:50]}")

except json.JSONDecodeError as e:
    print(f"\n❌ JSON 解析失败:")
    print(f"错误: {e}")
    print(f"位置: 第 {e.lineno} 行, 第 {e.colno} 列")
    print(f"错误信息: {e.msg}")

    # 尝试找出问题
    print(f"\n🔍 问题诊断:")
    json_text = r.text.strip(f"{callback}(")[:-1]
    print(f"去除 wrapper 后的文本长度: {len(json_text)}")
    print(f"开头 100 字符: {json_text[:100]}")
    print(f"结尾 100 字符: {json_text[-100:]}")

except Exception as e:
    print(f"\n❌ 其他错误: {e}")
