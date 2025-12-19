#!/usr/bin/env python3
"""
测试新的报告命名方式
"""
from datetime import datetime
import os

# 模拟报告生成
now = datetime.now()
date_folder = now.strftime('%y%m%d')  # 251217
report_base = "Report"
report_dir = os.path.join(report_base, date_folder)

# 文件名
time_prefix = now.strftime('%H%M%S')  # 115230
filename = os.path.join(report_dir, f"{time_prefix}_Monitor_Report.md")

print("="*60)
print("📋 新的报告命名方式演示")
print("="*60)
print(f"\n当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\n存储结构:")
print(f"  Report/")
print(f"  └── {date_folder}/          # 年月日文件夹")
print(f"      └── {time_prefix}_Monitor_Report.md   # 时间_报告名.md")
print(f"\n完整路径: {filename}")

print(f"\n示例：如果今天多次生成报告:")
for hour, minute in [(9, 30), (14, 30), (20, 0)]:
    example_time = f"{hour:02d}{minute:02d}00"
    example_file = os.path.join(report_base, date_folder, f"{example_time}_Monitor_Report.md")
    print(f"  {example_file}")

print("\n" + "="*60)
print("✅ 优势:")
print("  1. 按日期自动分类，便于查找")
print("  2. 同一天可生成多次报告，不会覆盖")
print("  3. 文件名直接显示生成时间")
print("  4. 时间格式简洁（YYMMDD + HHMMSS）")
print("="*60)
