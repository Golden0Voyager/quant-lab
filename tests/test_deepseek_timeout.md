# test_deepseek_timeout.py

测试 DeepSeek API 调用的超时和重试机制。

## 功能

### test_deepseek_call()
- 使用 180 秒超时调用 deepseek-v3.2
- 最多重试 3 次，采用指数退避（1s, 2s, 4s）
- 发送投资分析 prompt 并验证响应质量

### test_timeout_comparison()（默认注释）
- 对比不同超时时间（30/60/120/180秒）在不同复杂度 prompt 下的表现
- 用于确定最优超时配置

## 运行

```bash
cd /Users/hainingyu/Code/quant_lab
uv run python tests/test_deepseek_timeout.py
```

## 输出示例

```
[尝试 1/3] 正在调用 DeepSeek API...
✅ 调用成功！
耗时: 45.30 秒
```

## 使用场景

- 验证 DeepSeek 超时优化是否生效
- 评估当前网络环境下 DeepSeek 的响应时间
- 调整超时参数时的基准测试
