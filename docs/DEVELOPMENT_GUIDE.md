# Quant Lab - AI 量化分析系统开发文档

> **当前版本**: V5.0 (Global & Web Edition)
> **最后更新**: 2026-03-08
> **维护者**: Haining Yu

---

## 目录

1. [系统概述](#1-系统概述)
2. [模块架构 (V5.0)](#2-模块架构-v50)
3. [核心功能演进](#3-核心功能演进)
4. [命令行参数与快捷命令](#4-命令行参数与快捷命令)
5. [全球分析模式 (OpenBB)](#5-全球分析模式-openbb)
6. [报告与 PDF 系统](#6-报告与-pdf-系统)
7. [数据层与并行抓取](#7-数据层与并行抓取)
8. [缓存与网络优化](#8-缓存与网络优化)
9. [Web API 架构 (Flask)](#9-web-api-架构-flask)
10. [AI 配置与模型调度](#10-ai-配置与模型调度)
11. [数据来源与准确性](#11-数据来源与准确性)
12. [版本迭代历史](#12-版本迭代历史)

---

## 1. 系统概述

### 1.1 定位

Quant Lab V5.0 是一套从 CLI 进化到 **AI-Native 全栈量化分析** 的系统。它不仅服务于 A 股，还扩展到了全球视野：

- **多市场覆盖**: A 股、港股、美股（TSLA/AAPL等）及全球宏观指数。
- **深度研判**: 结合基础面、技术面、资金面、舆情面及全球宏观背景。
- **自动化产出**: 一键生成专业级 Markdown 及 PDF 分析报告。
- **服务化能力**: 提供完整的 RESTful API 接口，支持 JWT 认证与支付集成。

### 1.2 核心架构 (双循环系统)

- **CLI 循环**: 极速命令行工具，用于日常监控、深度复盘和缓存预热。
- **Web 循环**: 基于 Flask 的后端，为前端或第三方应用提供量化分析服务。

---

## 2. 模块架构 (V5.0)

### 2.1 文件结构

```
quant_lab/
├── main.py                  # CLI 入口 + 批量估值 + 全球模式调度
├── ai_config.py             # 核心配置：多模型 Profile + 网络优化 (IPv4/代理)
├── analyst_openbb.py        # [NEW] OpenBB 集成：全球宏观 + 行业分析
├── md2pdf_tool.py           # [NEW] 报告转换：Markdown 转 PDF 核心逻辑
├── analyst_integration.py   # [ENHANCED] 并行数据整合引擎 (6-workers)
├── valuation_analyzer.py    # [ENHANCED] 17步估值 + AI 深度分析 (带超时机制)
├── analyst_data.py          # 13+ 维度增强数据获取
├── analyst_brain.py         # 智能决策层 (信号评估得分)
├── api/                     # [EXPANDED] 完整 Web 后端
│   ├── app.py               # Flask 入口 (JWT/CORS/Limiter)
│   ├── routes/              # 蓝图：analyze, auth, payment, health
│   └── models/              # SQLAlchemy 数据库模型
├── Report/                  # 分析报告输出 (MD + PDF)
└── cache/                   # SQLite 缓存 (TTL 策略)
```

---

## 3. 核心功能演进

| 功能模块 | V4.0 (旧) | V5.0 (当前) |
|:---|:---|:---|
| **分析市场** | 仅 A 股 + 基础港股 | **全球市场** (含美股/指数/宏观) |
| **数据抓取** | 串行获取 | **并行抓取** (ThreadPoolExecutor) |
| **输出格式** | 仅 Markdown | **Markdown + PDF** (专业排版) |
| **网络层** | 基础重试 | **自适应优化** (东财直连/Yahoo代理注入) |
| **API 层** | 简单示例 | **企业级后端** (JWT/限流/支付) |
| **AI 模型** | 固定配置 | **Profile 切换** (Kimi/DeepSeek/GLM) |

---

## 4. 命令行参数与快捷命令

### 4.1 新增核心参数

| 参数 | 说明 | 示例 |
|:---|:---|:---|
| `--global TICKER` | 运行全球股票分析模式 | `python main.py --global NVDA` |
| `--yes / -y` | 批量模式下自动确认 | `python main.py --batch-valuation list.txt -y` |
| `--delay` | 批量分析间隔时间 | `python main.py --batch-valuation list.txt --delay 1.0` |

### 4.2 常用快捷命令 (V5.0 推荐)

- `stock-check [CODE]` : 智能分析 (Auto 模式)。
- `stock-global [TICKER]` : 全球分析 (美股/指数)。
- `stock-val [CODE]` : 快速估值 + AI 深度分析。
- `stock-warm [my|all]` : 缓存预热，加速查询。

---

## 5. 全球分析模式 (OpenBB)

### 5.1 数据链路
通过 `analyst_openbb.py` 调用 OpenBB SDK：
1. **全球宏观**: 获取美债 10Y 收益率、DXY 美元指数、恒生指数等。
2. **个股分析**: 获取美股技术总结、基本面概要及行业地位。
3. **AI 整合**: 结合宏观背景为个股提供全球化视野的投资建议。

### 5.2 网络处理
由于全球数据源（如 Yahoo Finance）受限，系统在 `ai_config.py` 中实现了**线程局部代理注入**：
- 仅在 OpenBB 抓取线程启用代理，不影响国内 API 的直连速度。

---

## 6. 报告与 PDF 系统

### 6.1 自动化转换
系统集成 `md2pdf_tool.py`，在生成 `.md` 报告后自动尝试生成同名 `.pdf`。
- **样式**: 遵循极简主义美学，支持中文排版。
- **场景**: 估值分析、全球分析、深度分析均支持 PDF 输出。

### 6.2 估值分析超时机制
在交互模式下，估值分析会询问是否启动 AI 深度研判。**新增 9 秒超时自动确认**，确保自动化流程不被阻塞。

---

## 7. 数据层与并行抓取

### 7.1 并行化提升
`analyst_integration.py` 采用 `ThreadPoolExecutor(max_workers=6)`：
- 估值、业绩、资金、筹码、机构、竞争对手等 **12+ 维度并行获取**。
- 综合分析耗时从 ~60s 缩短至 ~15s (有缓存时更短)。

### 7.2 信号系统
评分 >= 3 触发 Brain 深度分析。V5.0 增强了对“技术突破”和“大额异动”的敏感度。

---

## 8. 缓存与网络优化

### 8.1 IPv4 优先策略
针对东方财富（eastmoney.com）域名，系统强制使用 **IPv4 协议**，绕过不稳定的 IPv6 路由。

### 8.2 缓存分层
- **行情数据**: 4-10 小时 TTL。
- **宏观数据**: 60 分钟内存缓存。
- **静态列表**: 7 天 TTL。

---

## 9. Web API 架构 (Flask)

### 9.1 核心组件
- **Flask-JWT-Extended**: 处理用户登录、Token 刷新及路由保护。
- **Flask-Limiter**: 防止接口滥用（默认 50次/小时）。
- **SQLAlchemy**: 管理用户信息与分析记录。
- **CORS**: 支持跨域调用。

### 9.2 主要 Endpoints
- `POST /api/auth/login`: 用户登录。
- `GET /api/analyze/stock/<symbol>`: 触发个股分析。
- `POST /api/payment/create`: 支付集成占位。

---

## 10. AI 配置与模型调度

### 10.1 多 Profile 系统
在 `ai_config.py` 中配置 `MODEL_CONFIGS`：
- **deepseek**: 默认主力 (V3.1)。
- **kimi**: 备用方案 (K2-Thinking)。
- **glm**: 高性能备用。

### 10.2 自动降级链路
调用失败时按以下顺序尝试：
`当前主力 (Attempt 1) -> 当前主力 (Attempt 2) -> 备份模型 (Attempt 1) -> 备份模型 (Attempt 2)`

---

## 11. 数据来源与准确性

| 维度 | 数据源 | 延迟 | 评价 |
|:---|:---|:---|:---|
| **A 股基础** | AKShare (东财/新浪) | 1-5min | 极高可信度 |
| **全球行情** | OpenBB (yfinance) | 1min | 行业标准 |
| **实时估值** | 雪球 API | 实时 | 个人投资者首选 |
| **宏观背景** | OpenBB | 实时 | 宏观决策参考 |

---

## 12. 版本迭代历史

### V5.0 (2026-03-08) — 当前版本
- **核心**: 引入全球股票模式 (`--global`) 与 OpenBB 集成。
- **功能**: Markdown 自动转 PDF 功能上线。
- **后端**: 完整 Flask API (JWT/支付/限流) 架构成型。
- **优化**: 并行抓取引擎 (6-workers) 极大提升分析速度。
- **网络**: 代理自动注入与 IPv4 强制优化。

### V4.0 (2026-02-09)
- **核心**: 统一数据获取链路，整合分析别名系统。
- **功能**: 支持 A 股 + 港股。

---
*本文件由 AI 自动生成，旨在记录 Quant Lab 的最新技术演进。*
