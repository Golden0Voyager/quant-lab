# example_main_enhanced.py

双层 AI 分析系统的集成示例，展示完整的 Worker + Brain 分析流程。

## 功能

### analyze_stock_with_four_dimensions()
核心分析函数，包含 4 个步骤：

1. **数据抓取** — 调用 `fetch_integrated_data()` 获取多维度数据
2. **信号评估** — 调用 `evaluate_enhanced_signals()` 计算信号得分
3. **AI 分析** — 根据模式选择 Worker (qwen-flash) 或 Brain (deepseek-v3.2)
4. **格式化输出** — 生成包含技术/资金/估值/业绩/情绪五维摘要的报告

### batch_analyze_watchlist()
批量分析自选股列表，逐只执行完整分析流程。

## 运行

```bash
cd /Users/hainingyu/Code/quant_lab

# 默认测试（广东宏大 + 贵州茅台）
uv run python tests/example_main_enhanced.py

# 指定股票
uv run python tests/example_main_enhanced.py --code 002683 --name 广东宏大

# 指定分析模式
uv run python tests/example_main_enhanced.py --code 600519 --name 贵州茅台 --mode deep
```

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--code` | 股票代码 | 无（使用测试用例） |
| `--name` | 股票名称 | "未知" |
| `--mode` | 分析模式：auto/fast/deep | auto |

## 依赖模块

- `analyst_integration` — 数据获取 + Prompt构建 + 信号评估
- `analyst_brain.AnalystBrain` — Brain层深度分析

## 使用场景

- 理解双层分析系统的完整工作流程
- 作为自定义分析脚本的模板
- 验证 Worker/Brain 切换逻辑
