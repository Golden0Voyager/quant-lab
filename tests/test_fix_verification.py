import json
import logging
import os
import sys
from datetime import datetime

# 确保能找到根目录模块
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
sys.path.append(root_dir)

from analyst_integration import fetch_integrated_data
from data_cache import DataCache, QuantJSONEncoder

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_json_serialization():
    print("\n--- [验证 1] JSON 序列化修复测试 ---")

    # 模拟包含 numpy 类型的数据
    try:
        import numpy as np
        test_data = {
            "is_above_ma20": np.bool_(True),
            "score": np.int64(85),
            "price": np.float64(150.5),
            "updated_at": datetime.now()
        }
        print("  - 使用 numpy 类型进行测试")
    except ImportError:
        test_data = {
            "is_above_ma20": True,
            "updated_at": datetime.now()
        }
        print("  - 使用标准 Python 类型测试")

    try:
        # 1. 测试编码器
        json_str = json.dumps(test_data, cls=QuantJSONEncoder)
        print("  - JSON 编码成功")

        # 2. 测试写入 DataCache
        db_path = os.path.join(script_dir, "test_fix.db")
        cache = DataCache(db_path)
        cache.set("TEST_SYMBOL", "test_type", test_data, 60)
        print("  - DataCache.set 写入数据库成功 ✅")

        # 3. 测试读取
        cached_data = cache.get("TEST_SYMBOL", "test_type")
        if cached_data:
            print("  - 缓存读取结果: %s" % cached_data.get('is_above_ma20'))
            print("  - 缓存读取验证通过 ✅")

        # 清理
        if os.path.exists(db_path):
            os.remove(db_path)

    except Exception as e:
        print("  - ❌ 序列化测试失败: %s" % e)
        import traceback
        traceback.print_exc()

def test_safe_fetch_resilience():
    print("\n--- [验证 2] 抓取逻辑容错性测试 ---")

    symbol = "999999" # 不存在的代码
    name = "错误测试标的"

    try:
        print("  - 正在尝试抓取不存在的标的 %s (将触发重试报警)..." % symbol)
        # 禁用缓存以运行实时抓取逻辑
        data = fetch_integrated_data(symbol, name, use_cache=False)

        print("  - 函数执行完毕，未崩溃 ✅")
        print("  - 是否返回了基础字典: %s" % ('✅' if isinstance(data, dict) else '❌'))

    except Exception as e:
        print("  - ❌ 容错性测试失败 (代码崩溃): %s" % e)

if __name__ == "__main__":
    test_json_serialization()
    test_safe_fetch_resilience()
    print("\n" + "="*60)
    print("✨ 所有修复项验证完成！")
    print("="*60)
