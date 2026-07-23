# Project Intelligence: Quant Lab

这是独立的量化分析项目，专注于 A 股数据的抓取、清洗与 AI 研判。

## 🧠 核心业务逻辑
- **数据源**: 深度依赖 `AkShare` 获取 A 股实时数据。
- **启动指令**: `uv run python <script.py>`。

## 📁 隔离规范 (Isolation)
- **数据安全**: `cache/`, `all_stock_data/` 严禁提交至 Git。
- **报告管理**: `Report/` 下生成的分析文件仅限本地存储。

## 🌿 Git Workflow 规范
- **New Feature 流程**: 开发新功能 (new feature) 时，建议走 `/git-feature` 流程（使用 `/git-feature start` 创建分支，完成开发后使用 `/git-feature done` 完成推送/PR/合入/清理全流程）。