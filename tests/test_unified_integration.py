import logging
import os
import sys
import time

# 确保能找到根目录模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyst_integration import fetch_integrated_data, fetch_stock_data

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_unified_api():
    symbol = "600519"
    name = "贵州茅台"

    print("\n🚀 开始测试统一集成入口: %s (%s)" % (name, symbol))
    print("="*60)

    # 1. 测试兼容性接口 fetch_stock_data (默认应使用缓存)
    print("\n[测试 1] 兼容性接口 fetch_stock_data (默认缓存)")
    start = time.time()
    data1 = fetch_stock_data(symbol, name)
    t1 = time.time() - start
    print("  - 耗时: %.2fs" % t1)
    print("  - 数据完整性: %s" % ('✅' if 'tech_summary' in data1 and 'pe_ttm' in data1 else '❌'))

    # 2. 测试显式缓存调用
    print("\n[测试 2] 显式开启缓存 use_cache=True")
    start = time.time()
    data2 = fetch_integrated_data(symbol, name, use_cache=True)
    t2 = time.time() - start
    print("  - 耗时: %.2fs (预期应极短)" % t2)
    print("  - 与测试1数据一致性: %s" % ('✅' if data1.get('timestamp') == data2.get('timestamp') else '⚠️ (数据已更新)'))

    # 3. 测试显式关闭缓存 (实时抓取)
    print("\n[测试 3] 显式关闭缓存 use_cache=False (实时抓取)")
    print("  (由于涉及多个API，请耐心等待...)")
    start = time.time()
    data3 = fetch_integrated_data(symbol, name, use_cache=False)
    t3 = time.time() - start
    print("  - 耗时: %.2fs" % t3)
    print("  - 数据完整性: %s" % ('✅' if 'tech_summary' in data3 else '❌'))
    print("  - 是否绕过缓存: %s" % ('✅' if t3 > 1.0 else '❌ (耗时过短，可能误用了缓存)'))

    print("\n" + "="*60)
    print("✨ 所有集成入口测试完成！")
    print("="*60)

if __name__ == "__main__":
    try:
        test_unified_api()
    except Exception as e:
        print("\n❌ 测试过程中发生错误: %s" % e)
        import traceback
        traceback.print_exc()
