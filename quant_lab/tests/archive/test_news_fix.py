#!/usr/bin/env python3
"""
测试新闻获取功能修复
"""
import logging
from analyst_base import fetch_stock_data

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

print("="*60)
print("🧪 新闻获取功能测试")
print("="*60)

# 测试用例
test_cases = [
    {"code": "000988", "name": "华工科技"},  # 个股
    {"code": "002683", "name": "广东宏大"},  # 个股
]

for idx, stock in enumerate(test_cases, 1):
    print(f"\n{'='*60}")
    print(f"测试 {idx}/{len(test_cases)}: {stock['name']} ({stock['code']})")
    print('='*60)

    try:
        data = fetch_stock_data(stock['code'], stock['name'])

        print(f"\n📊 数据获取结果:")
        print(f"  - 资产类型: {data['type']}")
        print(f"  - 技术面: {data['tech_summary']}")
        print(f"  - 资金面: {data['money_summary']}")
        print(f"  - 舆情概要: {data['news_summary']}")
        print(f"  - 新闻来源: {data.get('news_source', '未知')}")

        print(f"\n📰 新闻详情:")
        print(data['news_context'])

        # 判断是否成功获取新闻
        if data.get('news_source') in ['东方财富', '全网搜索']:
            print(f"\n✅ 成功: 通过 {data['news_source']} 获取到新闻")
        elif data.get('news_source') == '大盘背景':
            print(f"\n⚠️ 降级: 使用大盘背景信息")
        else:
            print(f"\n❌ 失败: 所有新闻源均未获取到数据")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

print(f"\n{'='*60}")
print("✅ 测试完成")
print('='*60)
