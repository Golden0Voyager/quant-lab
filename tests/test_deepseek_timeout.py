"""
测试 DeepSeek API 调用优化
验证超时和重试机制是否正常工作
"""

import os
import sys

# 修复路径，确保在 tests 目录下也能找到根目录的模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import logging
from openai import OpenAI

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# API 配置
API_KEY = os.getenv("DASHSCOPE_API_KEY")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_deepseek_call():
    """测试 DeepSeek API 调用"""

    # 准备一个简单的测试提示
    test_prompt = """请简要分析贵州茅台（600519）的投资价值。

要求：
1. 从行业地位、盈利能力、估值水平三个维度分析
2. 给出明确的投资建议
3. 控制在200字以内

请开始分析："""

    print("="*60)
    print("DeepSeek API 调用测试")
    print("="*60)
    print(f"模型: deepseek-v3.2")
    print(f"超时时间: 180秒")
    print(f"重试次数: 3次")
    print("="*60 + "\n")

    # 测试带优化的调用
    timeout_duration = 180.0
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=timeout_duration)

    for attempt in range(3):
        try:
            print(f"[尝试 {attempt + 1}/3] 正在调用 DeepSeek API...")
            start_time = time.time()

            completion = client.chat.completions.create(
                model="deepseek-v3.2",
                messages=[{"role": "user", "content": test_prompt}],
            )

            elapsed_time = time.time() - start_time
            result = completion.choices[0].message.content

            print(f"\n{'='*60}")
            print(f"✅ 调用成功！")
            print(f"{'='*60}")
            print(f"耗时: {elapsed_time:.2f} 秒")
            print(f"\n分析结果：")
            print(f"{'='*60}")
            print(result)
            print(f"{'='*60}\n")

            return result

        except Exception as e:
            error_type = type(e).__name__
            elapsed_time = time.time() - start_time

            print(f"❌ 调用失败 (尝试 {attempt + 1}/3)")
            print(f"   错误类型: {error_type}")
            print(f"   耗时: {elapsed_time:.2f} 秒")
            print(f"   错误详情: {str(e)[:200]}")

            if attempt < 2:
                wait_time = 2 ** attempt
                print(f"   等待 {wait_time} 秒后重试...\n")
                time.sleep(wait_time)

    print("\n" + "="*60)
    print("❌ 所有尝试失败")
    print("="*60)
    return None


def test_timeout_comparison():
    """对比不同超时时间的效果"""

    print("\n" + "="*60)
    print("超时时间对比测试")
    print("="*60)

    test_prompts = {
        "简单": "请用一句话总结贵州茅台的投资价值",
        "中等": "请用100字分析贵州茅台的投资价值",
        "复杂": "请详细分析贵州茅台的投资价值，包括行业、财务、估值等多个维度"
    }

    timeout_settings = [30, 60, 120, 180]

    for complexity, prompt in test_prompts.items():
        print(f"\n测试复杂度: {complexity}")
        print("-" * 60)

        for timeout in timeout_settings:
            client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=timeout)

            try:
                start_time = time.time()
                completion = client.chat.completions.create(
                    model="deepseek-v3.2",
                    messages=[{"role": "user", "content": prompt}],
                )
                elapsed_time = time.time() - start_time

                print(f"  超时{timeout}秒: ✅ 成功 (耗时 {elapsed_time:.2f}秒)")
                break  # 成功后跳出

            except Exception as e:
                print(f"  超时{timeout}秒: ❌ {type(e).__name__}")
                continue


if __name__ == "__main__":
    print("\n开始测试...\n")

    # 测试1：基础功能测试
    test_deepseek_call()

    # 测试2：超时时间对比（可选，注释掉以节省时间）
    # test_timeout_comparison()

    print("\n测试完成！")
