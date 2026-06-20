"""
简单的API测试脚本
"""
import os
import sys
import time

import requests

# 添加项目根目录到路径
sys.path.insert(0, '/Users/hainingyu/Code/quant_lab')
os.chdir('/Users/hainingyu/Code/quant_lab')

# 启动Flask应用
from threading import Thread

from api.app import app


def run_app():
    app.run(host='0.0.0.0', port=5002, debug=False, use_reloader=False)

# 在后台线程中运行应用
server_thread = Thread(target=run_app, daemon=True)
server_thread.start()

# 等待服务器启动
time.sleep(3)

print("=" * 60)
print("测试API接口...")
print("=" * 60)

# 测试health接口
try:
    response = requests.get('http://localhost:5002/health')
    print("\n✅ /health 接口测试:")
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {response.json()}")
except Exception as e:
    print(f"\n❌ /health 接口测试失败: {e}")

# 测试ping接口
try:
    response = requests.get('http://localhost:5002/ping')
    print("\n✅ /ping 接口测试:")
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {response.json()}")
except Exception as e:
    print(f"\n❌ /ping 接口测试失败: {e}")

print("\n" + "=" * 60)
print("测试完成！按Ctrl+C退出...")
print("=" * 60)

# 保持运行
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\n退出测试")
