# diagnose_network.py

网络和 API 详细诊断脚本，逐层排查连接问题。

## 功能

按顺序执行 6 项测试：

1. **DNS 解析** — 测试 `dashscope.aliyuncs.com` 和 `www.baidu.com`（对照组）
2. **TCP 连接** — 测试 443 端口连通性和延迟
3. **HTTP 请求** — 使用 requests 库测试基础 HTTP
4. **DashScope HTTPS** — 测试 DashScope 服务端 HTTPS 响应
5. **OpenAI 客户端** — 使用 OpenAI SDK 调用 qwen-plus（无超时限制）
6. **HTTPX 直接调用** — 绕过 SDK，直接用 httpx 发送 POST 请求

## 运行

```bash
cd /Users/hainingyu/Code/quant_lab
uv run python tests/diagnose_network.py
```

## 使用场景

- API 调用失败但不确定是网络还是 API 问题时
- 代理/VPN 环境下验证连通性
- 从 DNS → TCP → HTTP → SDK 逐层定位故障点
