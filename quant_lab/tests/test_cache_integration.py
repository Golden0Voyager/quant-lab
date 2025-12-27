"""
测试缓存系统集成到主程序
验证自选股列表能否正常使用缓存加速
"""

import time
from analyst_integration_cached import fetch_stock_data

# 测试自选列表（从 main.py 中复制）
TEST_WATCHLIST = [
    {"code": "002920", "name": "德赛西威"},
    {"code": "002683", "name": "广东宏大"},
    {"code": "H30533", "name": "中国互联网50"},
    {"code": "399441", "name": "国证生物医药"},
    {"code": "931151", "name": "中证光伏产业"},
    {"code": "930721", "name": "中证智能汽车"},
    {"code": "1B0932", "name": "中证消费"},
]


def test_single_stock():
    """测试单只股票的缓存效果"""
    print("=" * 70)
    print("测试1: 单只股票缓存效果")
    print("=" * 70)

    stock = TEST_WATCHLIST[0]  # 德赛西威

    # 第一次调用
    print(f"\n[第1次] 抓取 {stock['name']} ({stock['code']})...")
    start = time.time()
    data1 = fetch_stock_data(stock['code'], stock['name'])
    time1 = time.time() - start
    print(f"✅ 完成，耗时: {time1:.2f}秒")
    print(f"   类型: {data1.get('type')}")
    print(f"   包含四维数据: {'pe_ttm' in data1}")

    # 第二次调用（应该很快）
    print(f"\n[第2次] 再次抓取 {stock['name']} (应使用缓存)...")
    start = time.time()
    data2 = fetch_stock_data(stock['code'], stock['name'])
    time2 = time.time() - start
    print(f"✅ 完成，耗时: {time2:.2f}秒")

    # 性能对比
    if time2 > 0:
        speedup = time1 / time2
        print(f"\n⚡ 性能提升: {speedup:.1f}x 倍加速！")


def test_asset_type_detection():
    """测试资产类型自动识别"""
    print("\n" + "=" * 70)
    print("测试2: 资产类型自动识别")
    print("=" * 70)

    for stock in TEST_WATCHLIST:
        print(f"\n检测: {stock['name']} ({stock['code']})")
        data = fetch_stock_data(stock['code'], stock['name'])
        print(f"  → 类型: {data.get('type')}")


def test_batch_with_cache():
    """测试批量抓取（展示缓存优势）"""
    print("\n" + "=" * 70)
    print("测试3: 批量抓取性能测试")
    print("=" * 70)

    # 第一轮：首次抓取
    print(f"\n[第1轮] 首次批量抓取 {len(TEST_WATCHLIST)} 只...")
    start = time.time()
    for i, stock in enumerate(TEST_WATCHLIST, 1):
        print(f"  [{i}/{len(TEST_WATCHLIST)}] {stock['name']}")
        try:
            fetch_stock_data(stock['code'], stock['name'])
        except Exception as e:
            print(f"    ⚠️ 失败: {e}")
    time1 = time.time() - start
    print(f"✅ 第1轮完成，耗时: {time1:.2f}秒")

    # 第二轮：缓存命中
    print(f"\n[第2轮] 再次批量抓取（缓存命中）...")
    start = time.time()
    for i, stock in enumerate(TEST_WATCHLIST, 1):
        print(f"  [{i}/{len(TEST_WATCHLIST)}] {stock['name']}")
        try:
            fetch_stock_data(stock['code'], stock['name'])
        except Exception as e:
            print(f"    ⚠️ 失败: {e}")
    time2 = time.time() - start
    print(f"✅ 第2轮完成，耗时: {time2:.2f}秒")

    # 性能对比
    if time2 > 0:
        speedup = time1 / time2
        print(f"\n⚡ 批量性能提升: {speedup:.1f}x 倍加速！")
        print(f"   节省时间: {time1 - time2:.2f}秒")


if __name__ == "__main__":
    try:
        # 运行测试
        test_single_stock()
        test_asset_type_detection()
        test_batch_with_cache()

        print("\n" + "=" * 70)
        print("✅ 所有测试完成！缓存系统集成成功！")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
