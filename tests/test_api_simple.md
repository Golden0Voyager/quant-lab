# test_api_simple.py

最简单的 API 连接测试，验证 DashScope 平台和 qwen-plus 模型是否可用。

## 功能

- 读取 `DASHSCOPE_API_KEY` 环境变量
- 使用 OpenAI SDK 向 qwen-plus 发送 "你好"
- 成功时打印响应内容，失败时打印完整错误堆栈

## 运行

```bash
cd /Users/hainingyu/Code/quant_lab
uv run python tests/test_api_simple.py
```

## 使用场景

- 快速验证 API Key 是否有效
- 确认 DashScope 服务是否可达
- 最小化依赖的连通性测试（仅依赖 openai 库）
