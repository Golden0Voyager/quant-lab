# check_deepseek_health.py

DeepSeek API 健康检查脚本，用于快速诊断 API 连接和超时问题。

## 功能

按顺序执行 5 项检查：

1. **API Key 检查** — 验证 `DASHSCOPE_API_KEY` 环境变量是否配置
2. **网络连接** — DNS 解析 + TCP 连接 `dashscope.aliyuncs.com:443`
3. **qwen-plus 调用** — 30秒超时，验证 API 基础可用性
4. **DeepSeek-V3.2 调用** — 180秒超时，最多重试2次，并评估响应性能
5. **超时设置检查** — 扫描 `main.py` 中的超时配置和重试策略

## 运行

```bash
cd /Users/hainingyu/Code/quant_lab
uv run python tests/check_deepseek_health.py
```

## 输出示例

```
✓ API Key 已配置: sk-xxxxx...xxxx
✓ DNS 解析成功
✓ qwen-plus 调用成功 (耗时: 1.25秒)
✓ DeepSeek 调用成功 (耗时: 45.30秒)
✓ 性能优秀：响应时间 < 60秒
```

## 使用场景

- DeepSeek 分析超时或无响应时排查
- 新环境部署后验证 API 可用性
- 网络变更后检查连通性
