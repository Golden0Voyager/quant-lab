"""
支付系统测试脚本
测试完整的支付流程：注册 -> 登录 -> 创建订单 -> 模拟支付回调
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
    app.run(host='0.0.0.0', port=5003, debug=False, use_reloader=False)

# 在后台线程中运行应用
server_thread = Thread(target=run_app, daemon=True)
server_thread.start()

# 等待服务器启动
time.sleep(3)

BASE_URL = "http://localhost:5003"

print("=" * 70)
print("🧪 测试支付系统")
print("=" * 70)

# ==================== 1. 注册用户 ====================
print("\n📝 步骤 1: 注册新用户...")
register_data = {
    "username": f"testuser_{int(time.time())}",
    "email": f"test_{int(time.time())}@example.com",
    "password": "password123"
}

response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
print(f"   状态码: {response.status_code}")

if response.status_code == 201:
    result = response.json()
    access_token = result['data']['access_token']
    user_info = result['data']['user']
    print("   ✅ 注册成功!")
    print(f"   用户名: {user_info['username']}")
    print(f"   免费额度: 快速{user_info['fast_reports_quota']}次, 深度{user_info['deep_reports_quota']}次")
else:
    print(f"   ❌ 注册失败: {response.text}")
    sys.exit(1)

# ==================== 2. 获取产品列表 ====================
print("\n📦 步骤 2: 获取产品列表...")
response = requests.get(f"{BASE_URL}/api/payment/products")
print(f"   状态码: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    single_reports = result['data']['single_reports']
    subscriptions = result['data']['subscriptions']

    print("   ✅ 获取成功!")
    print("\n   📊 单次报告产品:")
    for product in single_reports:
        print(f"      - {product['name']}: ¥{product['price']} (SKU: {product['sku']})")

    print("\n   📅 订阅包产品:")
    for product in subscriptions:
        print(f"      - {product['name']}: ¥{product['price']} (SKU: {product['sku']})")
else:
    print(f"   ❌ 获取失败: {response.text}")
    sys.exit(1)

# ==================== 3. 创建订单 ====================
print("\n🛒 步骤 3: 创建订单...")
# 购买一个深度报告
order_data = {
    "product_sku": "REPORT_DEEP_001",
    "payment_method": "wechat"
}

headers = {"Authorization": f"Bearer {access_token}"}
response = requests.post(f"{BASE_URL}/api/payment/orders/create", json=order_data, headers=headers)
print(f"   状态码: {response.status_code}")

if response.status_code == 201:
    result = response.json()
    order = result['data']['order']
    payment = result['data']['payment']

    print("   ✅ 订单创建成功!")
    print(f"   订单号: {order['order_no']}")
    print(f"   产品: {order['product_name']}")
    print(f"   金额: ¥{order['final_amount']}")
    print(f"   支付链接: {payment['pay_url']}")

    order_no = order['order_no']
else:
    print(f"   ❌ 创建失败: {response.text}")
    sys.exit(1)

# ==================== 4. 模拟支付回调 ====================
print("\n💳 步骤 4: 模拟支付回调...")
# 模拟支付服务商的回调
notify_data = {
    "out_trade_no": order_no,
    "mock_payment": "success",
    "payjs_order_id": f"MOCK_{int(time.time())}"
}

response = requests.post(f"{BASE_URL}/api/payment/notify", json=notify_data)
print(f"   状态码: {response.status_code}")

if response.status_code == 200:
    print("   ✅ 支付回调处理成功!")
else:
    print(f"   ❌ 回调处理失败: {response.text}")

# ==================== 5. 查询订单状态 ====================
print("\n🔍 步骤 5: 查询订单状态...")
response = requests.get(f"{BASE_URL}/api/payment/orders/{order_no}", headers=headers)
print(f"   状态码: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    order = result['data']['order']

    print("   ✅ 查询成功!")
    print(f"   订单状态: {order['status']}")
    print(f"   支付时间: {order.get('paid_at', 'N/A')}")
else:
    print(f"   ❌ 查询失败: {response.text}")

# ==================== 6. 查看用户额度 ====================
print("\n👤 步骤 6: 查看用户最新额度...")
response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
print(f"   状态码: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    user = result['data']['user']

    print("   ✅ 用户信息:")
    print(f"   用户名: {user['username']}")
    print(f"   当前额度: 快速{user['fast_reports_quota']}次, 深度{user['deep_reports_quota']}次")
    print(f"   累计消费: ¥{user['total_spent']}")
else:
    print(f"   ❌ 获取失败: {response.text}")

# ==================== 7. 测试订阅包 ====================
print("\n📦 步骤 7: 测试购买订阅包...")
order_data = {
    "product_sku": "SUB_PRO_MONTH",
    "payment_method": "wechat"
}

response = requests.post(f"{BASE_URL}/api/payment/orders/create", json=order_data, headers=headers)
print(f"   状态码: {response.status_code}")

if response.status_code == 201:
    result = response.json()
    order = result['data']['order']
    print("   ✅ 订单创建成功!")
    print(f"   订单号: {order['order_no']}")
    print(f"   产品: {order['product_name']}")
    print(f"   金额: ¥{order['final_amount']}")

    # 模拟支付
    print("\n   模拟支付回调...")
    notify_data = {
        "out_trade_no": order['order_no'],
        "mock_payment": "success"
    }

    response = requests.post(f"{BASE_URL}/api/payment/notify", json=notify_data)
    if response.status_code == 200:
        print("   ✅ 支付成功!")

        # 再次查看用户信息
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        if response.status_code == 200:
            user = response.json()['data']['user']
            print("\n   📊 订阅后的用户信息:")
            print(f"   用户角色: {user['role']}")
            print(f"   订阅到期: {user.get('subscription_expires', 'N/A')}")
            print(f"   当前额度: 快速{user['fast_reports_quota']}次, 深度{user['deep_reports_quota']}次")
    else:
        print("   ❌ 支付失败")

# ==================== 8. 获取订单列表 ====================
print("\n📋 步骤 8: 获取订单列表...")
response = requests.get(f"{BASE_URL}/api/payment/orders?page=1&per_page=10", headers=headers)
print(f"   状态码: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    orders = result['data']['orders']

    print(f"   ✅ 共有 {result['data']['total']} 个订单")
    for order in orders:
        print(f"      - {order['order_no']}: {order['product_name']} (¥{order['final_amount']}) - {order['status']}")

print("\n" + "=" * 70)
print("✅ 支付系统测试完成!")
print("=" * 70)
print("\n按Ctrl+C退出...")

# 保持运行
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\n退出测试")
