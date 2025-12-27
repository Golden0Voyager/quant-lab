#!/usr/bin/env python3
"""
自选股缓存预热脚本
建议每天盘后运行，提前缓存第二天需要的数据
"""

import sys
from analyst_cached import warm_up_cache, get_cache_info
from main import MY_WATCHLIST, DAD_WATCHLIST

def main():
    """主函数"""
    print("=" * 70)
    print("📦 自选股缓存预热工具")
    print("=" * 70)

    # 选择要预热的列表
    if len(sys.argv) > 1:
        if sys.argv[1] == "dad":
            watchlist = DAD_WATCHLIST
            print(f"\n✅ 预热列表: Dad's Watchlist ({len(watchlist)} 只)")
        elif sys.argv[1] == "all":
            watchlist = MY_WATCHLIST + DAD_WATCHLIST
            print(f"\n✅ 预热列表: 全部自选股 ({len(watchlist)} 只)")
        else:
            print(f"\n❌ 未知参数: {sys.argv[1]}")
            print("用法: python warm_up_cache.py [my|dad|all]")
            return
    else:
        watchlist = MY_WATCHLIST
        print(f"\n✅ 预热列表: MY_WATCHLIST ({len(watchlist)} 只)")

    # 显示列表
    print("\n包含标的:")
    for stock in watchlist:
        print(f"  - {stock['name']} ({stock['code']})")

    # 开始预热
    print("\n" + "=" * 70)
    warm_up_cache(watchlist)

    # 显示统计
    print("\n" + "=" * 70)
    print("📊 缓存统计")
    print("=" * 70)
    get_cache_info()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
