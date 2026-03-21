# Project Intelligence: Quant Lab

这是独立的量化分析项目，专注于 A 股数据的抓取、清洗与 AI 研判。

## 🚀 运行环境 (Runtime)
- **环境管理**: `uv` (强制)
- **启动指令**: `uv run python <script.py>`
- **Python 版本**: 见 `.python-version`

## 🧠 AI 协作规范 (AI Patterns)
- **推荐模型**: **Gemini 3.0 Pro** (复杂策略逻辑) 或 **GLM-4** (数据获取脚本编写)。
- **核心逻辑**: 基于 `AkShare` 获取实时数据，严禁硬编码 API 密钥。

## 📦 Git 提交规范 (Git Standards)
- **主权仓库**: 这是一个拥有独立历史的仓库。
- **提交信息**: 推荐使用 `feat:`, `fix:`, `refactor:` 等前缀。
