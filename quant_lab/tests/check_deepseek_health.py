#!/usr/bin/env python3
"""
DeepSeek API 健康检查脚本
快速诊断 API 连接和超时问题
"""

import os
import sys

# 修复路径，确保在 tests 目录下也能找到根目录的模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from openai import OpenAI

# 颜色代码
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_status(status, message):
    """打印状态信息"""
    if status == "success":
        print(f"{GREEN}✓{RESET} {message}")
    elif status == "error":
        print(f"{RED}✗{RESET} {message}")
    elif status == "warning":
        print(f"{YELLOW}⚠{RESET} {message}")
    elif status == "info":
        print(f"{BLUE}ℹ{RESET} {message}")


def check_api_key():
    """检查 API Key"""
    print("\n" + "="*60)
    print("1. 检查 API Key")
    print("="*60)

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if api_key:
        masked_key = api_key[:8] + "..." + api_key[-4:]
        print_status("success", f"API Key 已配置: {masked_key}")
        return api_key
    else:
        print_status("error", "未找到 DASHSCOPE_API_KEY 环境变量")
        print_status("info", "请设置环境变量：export DASHSCOPE_API_KEY='your-key'")
        return None


def check_network():
    """检查网络连接"""
    print("\n" + "="*60)
    print("2. 检查网络连接")
    print("="*60)

    import socket
    try:
        # 尝试解析域名
        host = "dashscope.aliyuncs.com"
        ip = socket.gethostbyname(host)
        print_status("success", f"DNS 解析成功: {host} -> {ip}")

        # 尝试连接
        sock = socket.create_connection((host, 443), timeout=5)
        sock.close()
        print_status("success", f"网络连接正常")
        return True

    except socket.gaierror:
        print_status("error", "DNS 解析失败")
        return False
    except socket.timeout:
        print_status("error", "连接超时")
        return False
    except Exception as e:
        print_status("error", f"网络错误: {type(e).__name__}")
        return False


def test_api_call(api_key, timeout=30):
    """测试 API 调用"""
    print("\n" + "="*60)
    print(f"3. 测试 API 调用 (超时: {timeout}秒)")
    print("="*60)

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        timeout=timeout
    )

    test_prompt = "请用一句话介绍你自己"

    try:
        print_status("info", f"正在调用 qwen-plus 模型...")
        start_time = time.time()

        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": test_prompt}],
        )

        elapsed = time.time() - start_time
        result = completion.choices[0].message.content

        print_status("success", f"qwen-plus 调用成功 (耗时: {elapsed:.2f}秒)")
        print(f"   响应: {result[:100]}...")

        return True

    except Exception as e:
        print_status("error", f"qwen-plus 调用失败: {type(e).__name__}")
        print(f"   详情: {str(e)[:200]}")
        return False


def test_deepseek(api_key):
    """测试 DeepSeek 模型"""
    print("\n" + "="*60)
    print("4. 测试 DeepSeek-V3.2 (超时: 180秒)")
    print("="*60)

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        timeout=180.0
    )

    test_prompt = "请用50字简要介绍贵州茅台的投资价值"

    for attempt in range(2):  # 最多尝试2次
        try:
            print_status("info", f"正在调用 DeepSeek (尝试 {attempt + 1}/2)...")
            start_time = time.time()

            completion = client.chat.completions.create(
                model="deepseek-v3.2",
                messages=[{"role": "user", "content": test_prompt}],
            )

            elapsed = time.time() - start_time
            result = completion.choices[0].message.content

            print_status("success", f"DeepSeek 调用成功 (耗时: {elapsed:.2f}秒)")
            print(f"   响应: {result[:150]}...")

            # 给出性能评估
            if elapsed < 60:
                print_status("success", "性能优秀：响应时间 < 60秒")
            elif elapsed < 120:
                print_status("warning", "性能正常：响应时间 60-120秒")
            else:
                print_status("warning", "性能较慢：响应时间 > 120秒，建议检查网络")

            return True

        except Exception as e:
            error_type = type(e).__name__
            elapsed = time.time() - start_time

            print_status("error", f"DeepSeek 调用失败 (尝试 {attempt + 1}/2)")
            print(f"   错误类型: {error_type}")
            print(f"   耗时: {elapsed:.2f}秒")

            if attempt == 0:
                print_status("info", "等待2秒后重试...")
                time.sleep(2)

    return False


def check_timeout_settings():
    """检查超时设置"""
    print("\n" + "="*60)
    print("5. 检查代码中的超时设置")
    print("="*60)

    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()

            # 查找 call_ai 函数中的超时设置
            if 'timeout_duration = 180.0 if "deepseek"' in content:
                print_status("success", "main.py 中 DeepSeek 超时已优化为 180秒")
            elif 'timeout=30.0' in content and 'call_ai' in content:
                print_status("warning", "main.py 中超时仍为 30秒，建议更新")
            else:
                print_status("info", "未找到超时设置，请手动检查")

            # 检查重试逻辑
            if '2 ** attempt' in content or 'wait_time = 2' in content:
                print_status("success", "已实现指数退避重试策略")
            else:
                print_status("warning", "未发现指数退避重试策略")

    except FileNotFoundError:
        print_status("warning", "未找到 main.py 文件，跳过检查")


def main():
    """主函数"""
    print("\n" + "="*60)
    print("DeepSeek API 健康检查")
    print("="*60)

    # 1. 检查 API Key
    api_key = check_api_key()
    if not api_key:
        print("\n" + RED + "❌ 检查失败：请先配置 API Key" + RESET)
        sys.exit(1)

    # 2. 检查网络
    network_ok = check_network()
    if not network_ok:
        print("\n" + RED + "❌ 检查失败：网络连接异常" + RESET)
        sys.exit(1)

    # 3. 测试快速模型
    quick_ok = test_api_call(api_key, timeout=30)
    if not quick_ok:
        print("\n" + RED + "❌ 检查失败：API 调用异常" + RESET)
        sys.exit(1)

    # 4. 测试 DeepSeek
    deepseek_ok = test_deepseek(api_key)

    # 5. 检查代码设置
    check_timeout_settings()

    # 最终总结
    print("\n" + "="*60)
    print("检查总结")
    print("="*60)

    if deepseek_ok:
        print(GREEN + "✓ 所有检查通过！DeepSeek API 工作正常" + RESET)
        print("\n建议：")
        print("  - DeepSeek 响应时间通常为 60-120 秒")
        print("  - 如需快速分析，使用 qwen-plus 模型")
        print("  - 批量分析时，建议添加延时避免频繁请求")
    else:
        print(YELLOW + "⚠ DeepSeek API 可能存在问题" + RESET)
        print("\n建议：")
        print("  - 检查网络连接是否稳定")
        print("  - 确认 API Key 权限是否包含 DeepSeek 模型")
        print("  - 稍后重试或联系技术支持")

    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断检查")
        sys.exit(0)
