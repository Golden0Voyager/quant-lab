#!/usr/bin/env python3
"""
详细的网络和 API 诊断
"""

import os
import sys

# 修复路径，确保在 tests 目录下也能找到根目录的模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import socket
import time

def test_dns():
    """测试 DNS 解析"""
    print("\n" + "="*60)
    print("1. DNS 解析测试")
    print("="*60)

    hosts = [
        "dashscope.aliyuncs.com",
        "www.baidu.com",  # 对照组
    ]

    for host in hosts:
        try:
            ip = socket.gethostbyname(host)
            print(f"✓ {host:30s} -> {ip}")
        except Exception as e:
            print(f"✗ {host:30s} -> 失败: {e}")


def test_tcp_connection():
    """测试 TCP 连接"""
    print("\n" + "="*60)
    print("2. TCP 连接测试")
    print("="*60)

    endpoints = [
        ("dashscope.aliyuncs.com", 443),
        ("www.baidu.com", 443),
    ]

    for host, port in endpoints:
        try:
            start = time.time()
            sock = socket.create_connection((host, port), timeout=10)
            latency = (time.time() - start) * 1000
            sock.close()
            print(f"✓ {host}:{port:5d} 连接成功 (延迟: {latency:.0f}ms)")
        except Exception as e:
            print(f"✗ {host}:{port:5d} 连接失败: {type(e).__name__}")


def test_http_request():
    """测试 HTTP 请求"""
    print("\n" + "="*60)
    print("3. HTTP 请求测试（使用 requests）")
    print("="*60)

    try:
        import requests

        # 测试简单的 GET 请求
        url = "https://www.baidu.com"
        print(f"测试: {url}")

        response = requests.get(url, timeout=10)
        print(f"✓ 状态码: {response.status_code}")
        print(f"✓ 响应长度: {len(response.content)} bytes")

    except Exception as e:
        print(f"✗ 失败: {type(e).__name__} - {e}")


def test_dashscope_https():
    """测试 DashScope HTTPS 连接"""
    print("\n" + "="*60)
    print("4. DashScope HTTPS 测试")
    print("="*60)

    try:
        import requests

        url = "https://dashscope.aliyuncs.com"
        print(f"测试: {url}")

        response = requests.get(url, timeout=10)
        print(f"✓ 状态码: {response.status_code}")
        print(f"✓ 服务器响应")

    except Exception as e:
        print(f"✗ 失败: {type(e).__name__}")
        print(f"   详情: {str(e)[:100]}")


def test_openai_client_simple():
    """测试 OpenAI 客户端（最简配置）"""
    print("\n" + "="*60)
    print("5. OpenAI 客户端测试（无超时）")
    print("="*60)

    try:
        from openai import OpenAI

        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            print("✗ 未找到 API Key")
            return

        print(f"API Key: {api_key[:10]}...{api_key[-4:]}")

        # 不设置超时，让请求自然完成
        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        print("发送请求（无超时限制）...")
        start = time.time()

        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": "你好"}],
        )

        elapsed = time.time() - start
        result = completion.choices[0].message.content

        print(f"✓ 成功！耗时: {elapsed:.2f}秒")
        print(f"   响应: {result[:50]}...")

    except Exception as e:
        print(f"✗ 失败: {type(e).__name__}")
        print(f"   详情: {str(e)[:200]}")

        # 打印更详细的错误
        import traceback
        print("\n详细错误:")
        traceback.print_exc()


def test_openai_with_httpx():
    """测试使用 httpx 直接调用"""
    print("\n" + "="*60)
    print("6. 直接 HTTPX 调用测试")
    print("="*60)

    try:
        import httpx
        import json

        api_key = os.getenv("DASHSCOPE_API_KEY")

        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": "qwen-plus",
            "messages": [{"role": "user", "content": "你好"}],
        }

        print(f"URL: {url}")
        print("发送请求...")

        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=data)

        print(f"✓ 状态码: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"✓ 响应: {content[:50]}...")
        else:
            print(f"   响应: {response.text[:200]}")

    except Exception as e:
        print(f"✗ 失败: {type(e).__name__}")
        print(f"   详情: {str(e)[:200]}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("网络和 API 详细诊断")
    print("="*60)

    test_dns()
    test_tcp_connection()
    test_http_request()
    test_dashscope_https()
    test_openai_client_simple()
    test_openai_with_httpx()

    print("\n" + "="*60)
    print("诊断完成")
    print("="*60 + "\n")
