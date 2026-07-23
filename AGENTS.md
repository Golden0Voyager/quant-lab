# AGENTS.md — Quant Lab 项目规范

## ⚠️ 环境约束（强制）

- **包管理器**：`uv pip install <pkg>`（禁止 `pip` / `python -m pip`）
- **运行脚本**：`uv run python <script.py>`

---

## 🧠 核心业务逻辑与隔离

- **数据源**: 深度依赖 `AkShare` 获取 A 股实时数据。
- **数据安全**: `cache/`, `all_stock_data/` 严禁提交至 Git。
- **报告管理**: `Report/` 下生成的分析文件仅限本地存储。

---

## Git Workflow 与规范

- **一文件一提交**: 严禁将多文件打包在一个 commit 中。Commit message 采用中英双语，英文块在前，中文在后。
- **New Feature 流程**: 开发新功能 (new feature) 时，建议走 `/git-feature` 流程（使用 `/git-feature start` 创建分支，完成开发后使用 `/git-feature done` 完成推送/PR/合入/清理全流程）。
- **分支规范**: 禁止直接在 `main` 上开发，必须在 `feat/*`、`fix/*`、`refactor/*` 等分支上进行。
