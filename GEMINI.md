# Project Intelligence: Quant Lab

这是独立的量化分析项目，专注于 A 股数据的抓取、清洗与 AI 研判。

## 🚀 运行环境 (Runtime)
- **环境管理**: `uv` (强制)
- **数据来源**: AkShare
- **启动指令**: `uv run python <script.py>`

## 🧠 AI 协作规范 (AI Patterns)
- **推荐模型**: **Gemini 1.5 Pro** (复杂策略逻辑) 或 **GLM-4** (数据获取脚本编写)。
- **核心逻辑**: 基于 `AkShare` 获取实时数据，严禁硬编码 API 密钥。

## 📁 隔离规范 (Isolation)
- **数据缓存**: `cache/`, `all_stock_data/` 严禁提交。
- **报告**: `Report/` 下生成的分析文件仅限本地存储。