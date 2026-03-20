#!/usr/bin/env python3
"""
简单的 API 连接测试
"""

import os
import sys

# 修复路径，确保在 tests 目录下也能找到根目录的模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI

# 配置
API_KEY = os.getenv("DASHSCOPE_API_KEY")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

print("测试 API 连接...")
print(f"API Key: {API_KEY[:10]}...{API_KEY[-4:]}")
print(f"Base URL: {BASE_URL}")
print()

try:
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=60.0)

    print("发送测试请求...")
    completion = client.chat.completions.create(
        model="qwen-plus",
        messages=[{"role": "user", "content": "你好"}],
    )

    print("✅ 成功！")
    print(f"响应: {completion.choices[0].message.content}")

except Exception as e:
    print(f"❌ 失败: {type(e).__name__}")
    print(f"详情: {e}")

    # 尝试打印更多调试信息
    import traceback
    print("\n完整错误堆栈:")
    traceback.print_exc()
