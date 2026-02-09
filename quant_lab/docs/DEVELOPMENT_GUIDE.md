# Quant Lab - AI 量化分析系统开发文档

> **当前版本**: V4.0
> **最后更新**: 2026-02-09
> **维护者**: Haining Yu

---

## 目录

1. [系统概述](#1-系统概述)
2. [模块架构](#2-模块架构)
3. [快速开始](#3-快速开始)
4. [命令行参数与快捷命令](#4-命令行参数与快捷命令)
5. [分析模式详解](#5-分析模式详解)
6. [Prompt 版本系统](#6-prompt-版本系统)
7. [数据层详解](#7-数据层详解)
8. [缓存系统](#8-缓存系统)
9. [估值分析系统](#9-估值分析系统)
10. [新闻舆情引擎](#10-新闻舆情引擎)
11. [配置系统](#11-配置系统)
12. [数据来源与准确性](#12-数据来源与准确性)
13. [故障排查](#13-故障排查)
14. [版本迭代历史](#14-版本迭代历史)

---

## 1. 系统概述

### 1.1 定位

Quant Lab 是一套面向 A 股散户/中小机构的 **AI 量化分析系统**，核心功能包括：

- 个股/指数的多维度分析（技术面、基本面、资金面、舆情面等）
- 快速估值分析（PE/PB/PS/PCF/P_FCF + 历史分位）
- 批量 Watchlist 监控与深度研报生成
- 多风格 AI 分析报告（机构研报 / 价值投资 / 量化评分）

### 1.2 核心架构

```
┌──────────────────────────────────────────────────────────┐
│                     用户输入 (CLI / aliases)              │
│    选择: Watchlist + 分析模式 + Prompt 版本               │
└─────────────────────┬────────────────────────────────────┘
                      │
    ┌─────────────────┴──────────────────┐
    │           stock-deep 路径           │          stock-val 路径
    │    (analyst_integration.py)         │     (valuation_analyzer.py)
    │                                     │
    │  数据获取 (13+ 维度):               │  17步估值数据获取:
    │  • 基础行情+多周期均线              │  • 当前估值 (PE/PB/PS/PCF/P_FCF)
    │  • 技术指标 (MACD/RSI/KDJ/CCI)     │  • 历史分位 (10/5/3/1年)
    │  • 资金流向+聪明钱                  │  • 技术指标+派生指标
    │  • 财务数据+业绩                    │  • 资金面+聪明钱+筹码
    │  • 新闻舆情 (公告+电报)             │  • 舆情数据
    │  • 支撑压力+情绪题材                │  • 分析师预期
    │  • 竞争对手+解禁风险                │  • 解禁/竞争/大盘环境
    │                                     │
    ├─────────────────────────────────────┤
    │        信号评估 (0-10分)             │
    │  RSI超买/超卖、MACD金叉/死叉        │
    │  均线排列、资金异动、重大公告        │
    ├──────────┬──────────────────────────┤
    │ 评分>=3  │  评分<3                  │
    │          │                          │
    ▼          ▼                          ▼
 ┌────────┐ ┌────────┐             ┌────────────┐
 │ Brain  │ │ Worker │             │ DeepSeek   │
 │深度分析│ │快速点评│             │ 估值分析   │
 │60-90秒 │ │5-10秒  │             │ 15-30秒    │
 └───┬────┘ └───┬────┘             └─────┬──────┘
     └──────────┴────────────────────────┘
                │
          ┌─────┴──────┐
          │  生成报告   │
          │ Markdown/PDF│
          └────────────┘
```

### 1.3 双路径设计

| 路径 | 命令 | 用途 | AI模型 |
|------|------|------|--------|
| **stock-deep** | `stock-check/deep/my` | 综合分析（技术+基本面+舆情） | Qwen-Flash (Worker) + DeepSeek-V3.2 (Brain) |
| **stock-val** | `stock-val` | 专注估值（PE/PB分位+现金流） | DeepSeek-V3.2 |

---

## 2. 模块架构

### 2.1 文件结构 (10 个核心模块)

```
quant_lab/
├── main.py                  # CLI入口 + 批量估值 + 缓存预热
├── ai_config.py             # AI模型配置（API Key、模型选择、超时）
├── stock_finder.py          # 股票代码/名称智能查询（A股+港股）
├── data_cache.py            # SQLite缓存层（TTL策略、自动过期）
├── analyst_base.py          # 基础数据获取（行情+财务+新闻）
├── analyst_data.py          # 增强数据获取（13维度：聪明钱/情绪/支撑压力等）
├── analyst_cache.py         # 缓存集成层（缓存+数据获取+预热）
├── analyst_integration.py   # 分析集成（Worker+Brain双层、Prompt模板）
├── analyst_brain.py         # Brain决策层（信号评估+深度分析调度）
├── valuation_analyzer.py    # 独立估值分析（17步数据+LLM prompt）
│
├── aliases.sh               # Shell快捷命令配置
├── watchlists.json          # 自选股列表配置（JSON格式）
├── pyproject.toml           # 项目依赖管理（uv）
│
├── api/                     # Web API层（FastAPI，可选）
│   └── utils/analyzer.py    # API分析器封装
├── smartmoney_hunter/       # 聪明钱猎手子模块
├── tests/                   # 测试用例
├── cache/                   # 缓存文件目录（.gitignore）
│   ├── quant_cache.db       # SQLite缓存数据库
│   ├── stock_list_cache.json      # A股列表缓存
│   └── stock_list_cache_hk.json   # 港股列表缓存
├── Report/                  # 分析报告输出（.gitignore）
└── docs/                    # 开发文档
```

### 2.2 模块依赖关系

```
main.py
 ├── ai_config.py          (AI模型配置)
 ├── stock_finder.py        (股票查询)
 ├── analyst_brain.py       (Brain决策)
 │    └── analyst_integration.py (数据+分析集成)
 │         ├── analyst_base.py    (基础数据)
 │         ├── analyst_data.py    (增强数据)
 │         └── analyst_cache.py   (缓存集成)
 │              └── data_cache.py (SQLite缓存)
 └── valuation_analyzer.py  (估值分析，独立路径)
      └── analyst_data.py    (复用增强数据函数)
```

### 2.3 各模块职责

| 模块 | 主要类/函数 | 职责 |
|------|------------|------|
| `main.py` | `main()`, `StockListParser`, `BatchValuationAnalyzer`, `run_warm_cache()` | CLI入口、参数解析、批量估值、缓存预热 |
| `ai_config.py` | `get_ai_config()` | 统一管理 Worker/Brain 的 API Key、模型名、超时等 |
| `stock_finder.py` | `StockFinder`, `smart_stock_query()` | 股票代码/名称智能查询，支持A股+港股，模糊匹配 |
| `data_cache.py` | `DataCache`, `CacheStrategy` | SQLite 缓存读写，TTL 自动过期，多种缓存策略 |
| `analyst_base.py` | `fetch_stock_data()` | 获取基础行情、多周期均线、财务数据、新闻舆情 |
| `analyst_data.py` | `fetch_smart_money_data()`, `fetch_theme_sentiment_data()`, `fetch_support_resistance_data()` 等13个 | 获取增强数据维度（聪明钱、情绪题材、支撑压力、竞争对手等） |
| `analyst_cache.py` | `fetch_full_stock_data_cached()`, `warm_up_cache()` | 缓存感知的数据获取，Watchlist 预热 |
| `analyst_integration.py` | `fetch_integrated_data()`, `build_enhanced_prompt()`, `_build_brain_prompt()` | 合并所有数据维度，构建Worker/Brain prompt |
| `analyst_brain.py` | `AnalystBrain`, `evaluate_enhanced_signals()` | 信号评估打分，决定是否触发Brain深度分析 |
| `valuation_analyzer.py` | `ValuationAnalyzer`, `ValuationMetrics` | 17步估值数据获取、LLM prompt生成、报告输出 |

---

## 3. 快速开始

### 3.1 安装

```bash
cd /Users/hainingyu/Code/quant_lab
uv sync
```

### 3.2 配置环境变量

```bash
export DASHSCOPE_API_KEY="sk-your-api-key"
```

### 3.3 安装快捷命令

```bash
# 在 ~/.zshrc 中添加:
source ~/Code/quant_lab/aliases.sh
```

### 3.4 第一次运行

```bash
# 快速查询单股
stock-check 广东宏大

# 深度分析
stock-deep 贵州茅台

# 快速估值
stock-val 600519

# 分析 Watchlist
stock-my
```

---

## 4. 命令行参数与快捷命令

### 4.1 完整命令格式

```bash
python main.py [OPTIONS]

# Watchlist 模式
python main.py --list WATCHLIST [--analysis-mode MODE] [--prompt-version VERSION]

# 单股分析模式
python main.py --stock CODE[:NAME] [--analysis-mode MODE] [--prompt-version VERSION]

# 估值模式
python main.py --valuation STOCK

# 批量估值
python main.py --batch-valuation FILE_OR_TEXT [--delay SECONDS] [--yes]

# 缓存预热
python main.py --warm-cache {my|dad|erin|all}
```

### 4.2 参数说明

| 参数 | 值 | 说明 |
|------|-----|------|
| `--list` | `my` / `dad` / `erin` | 选择 Watchlist |
| `--stock` | `600519` / `贵州茅台` / `600519:贵州茅台` | 单股查询 |
| `--analysis-mode` | `fast` / `auto` / `deep` | 分析深度 |
| `--prompt-version` | `professional` / `value_first` / `quant_hybrid` | Prompt 风格（仅 Brain 层生效） |
| `--valuation` | 股票代码或名称 | 快速估值分析 |
| `--batch-valuation` | 文件路径或文本 | 批量估值 |
| `--delay` | 秒数（默认2.0） | 批量分析间隔 |
| `--yes` | 无参数 | 跳过确认直接执行 |
| `--warm-cache` | `my` / `dad` / `erin` / `all` | 缓存预热 |

### 4.3 快捷命令速查

#### 单股分析（核心）
| 命令 | 说明 |
|------|------|
| `stock-check 广东宏大` | 智能分析（auto模式，日常最常用） |
| `stock-deep 600519` | 深度分析（完整研报） |

#### Watchlist 分析
| 命令 | 说明 |
|------|------|
| `stock-my` / `stock-dad` / `stock-erin` | 智能分析（日常跟踪） |
| `stock-my-deep` / `stock-dad-deep` / `stock-erin-deep` | 深度分析（周末复盘） |

#### 估值分析
| 命令 | 说明 |
|------|------|
| `stock-val 600519` | 单股快速估值 |
| `stock-batch-val stocks.txt` | 批量估值（从文件） |
| `stock-val-my` / `stock-val-dad` / `stock-val-erin` | Watchlist 批量估值 |

#### 工具命令
| 命令 | 说明 |
|------|------|
| `stock-warm` / `stock-warm dad` / `stock-warm-all` | 缓存预热 |
| `stock-report` | 查看今日报告 |
| `stock-log` | 实时查看日志 |
| `stock-cache` | 查看缓存状态 |
| `stock-cache-clear` | 清除所有缓存 |
| `stock-help` | 显示帮助 |

#### 高级用法（直接参数）
```bash
# 切换 Prompt 风格
stock --analysis-mode deep --prompt-version value_first --stock 600519   # 价值投资
stock --analysis-mode deep --prompt-version quant_hybrid --stock 600519  # 量化评分

# 批量估值（快速模式）
stock --batch-valuation stocks.txt --delay 0.5 --yes
```

---

## 5. 分析模式详解

### 5.1 三种分析深度

| 模式 | Worker | Brain | 速度 | 适用场景 |
|------|--------|-------|------|---------|
| **fast** | 100% | 0% | 5-10秒/只 | 日常监控、批量扫描 |
| **auto** | 70% | 30% | 5-40秒/只 | 智能决策（推荐） |
| **deep** | 0% | 100% | 60-90秒/只 | 重要决策、周末复盘 |

### 5.2 信号触发机制 (auto 模式)

auto 模式会自动评估信号强度，总分 >= 3 时触发 Brain 深度分析：

| 信号类型 | 评分 | 触发条件 |
|---------|------|---------|
| 重大事件/大额回购 | 3分 | 重组/并购/回购>=5亿 |
| 巨额资金异动 | 3分 | 资金异动>=10亿 |
| RSI 超买/超卖 | 2分 | RSI>70 或 RSI<30 |
| MACD 金叉/死叉 | 2分 | DIF上穿/下穿DEA |
| 技术突破 | 2分 | 距MA20 0-3% |
| 大额资金 | 2分 | 资金异动5-10亿 |
| 均线多头/空头排列 | 1分 | MA5>MA10>MA20>MA60 或反向 |
| 5日涨跌异常 | 1分 | 5日涨跌>8% |
| 站稳年线 | 1分 | 价格>MA250 |

### 5.3 估值分析模式（独立路径）

```bash
stock-val 600519    # 17步数据获取 + AI深度估值分析
```

17步数据包括：当前估值、历史分位、技术指标、均线系统、资金流向、聪明钱动向、筹码分布、支撑压力位、大盘/板块环境、竞争对手、核心财务指标、季度趋势、分析师预期、机构持仓、解禁风险、融资融券、舆情数据。

### 5.4 批量估值

支持多种格式的股票清单：

```text
# 注释行（跳过）
600519 贵州茅台       # 代码+名称
贵州茅台 (600519)     # 名称(代码)
600519                # 纯代码
贵州茅台              # 纯名称
今天关注了帝尔激光和中航光电  # 混合文本
```

```bash
# 从文件
stock-batch-val my_stocks.txt

# 从文本
python main.py --batch-valuation "600519
000858
平安银行"
```

### 5.5 性能参考

| 模式 | 单股耗时 | 10只Watchlist |
|------|---------|--------------|
| fast | ~5秒 | ~1分钟 |
| auto (20%触发) | ~12秒 | ~2分钟 |
| deep (professional) | ~30秒 | ~5分钟 |
| valuation (首次) | ~200秒 | - |
| valuation (缓存) | ~3秒 | - |

---

## 6. Prompt 版本系统

### 6.1 三种风格对比

| 版本 | 核心理念 | 输出特点 | 适合人群 |
|------|---------|---------|---------|
| **professional** | 专业分析师 | 机构研报风格、结构化报告 | 有经验投资者（默认） |
| **value_first** | 价值投资 | 估值锚定+技术择时+催化剂 | 中长期价值投资者 |
| **quant_hybrid** | 量化混合 | 多因子打分表+大白话解释 | 量化爱好者/新手 |

### 6.2 Professional（专业分析师版）

输出包含：综合评级（含置信度）、核心逻辑、关键信号（3条）、操作策略（短线+中线）、风险提示。

### 6.3 Value First（价值投资版）

以估值和盈利质量为核心，关注安全边际和现金流。输出包含：估值分析、盈利质量、投资结论、中长期策略（含理想介入区间）。

### 6.4 Quant Hybrid（量化评分版）

多因子评分表：估值(30%) + 质量(25%) + 动量(25%) + 情绪(20%)。输出包含：因子得分表、综合评级（含得分）、一句话结论（大白话）、关键观察点、操作建议（含仓位建议）。

### 6.5 使用建议

| 投资风格 | 推荐Prompt | 推荐Mode |
|---------|-----------|----------|
| 短线交易 | quant_hybrid | auto |
| 价值投资 | value_first | deep |
| 趋势跟踪 | professional | auto |
| 组合管理 | quant_hybrid | auto |
| 研究分析 | professional | deep |

---

## 7. 数据层详解

### 7.1 数据维度总览 (stock-deep 路径)

analyst_data.py 提供 13+ 个增强数据维度：

| 维度 | 函数 | 数据源 |
|------|------|--------|
| 资金流向 | `fetch_capital_flow_data()` | 东方财富 |
| 聪明钱动向 | `fetch_smart_money_data()` | 东方财富（北向+融资融券） |
| 竞争对手 | `fetch_competitor_data()` | 东方财富 |
| 解禁风险 | `fetch_lockup_data()` | 东方财富 |
| 大盘环境 | `fetch_market_environment()` | AKShare |
| 技术指标 | `fetch_technical_indicators()` | AKShare（MACD/RSI/KDJ/CCI/BOLL） |
| 筹码分布 | `fetch_chip_distribution()` | 东方财富 |
| 分析师预期 | `fetch_analyst_consensus()` | 东方财富 |
| 机构持仓 | `fetch_institutional_holdings()` | 东方财富 |
| 核心财务 | `fetch_core_financials()` | AKShare |
| 情绪题材 | `fetch_theme_sentiment_data()` | 东方财富 |
| 支撑压力 | `fetch_support_resistance_data()` | 计算（MA/BOLL/筹码） |
| 舆情数据 | `fetch_news_data()` | 东财公告+财联社电报 |

### 7.2 技术指标

#### 均线系统（6条）
MA5（周线）、MA10（双周线）、MA20（月线）、MA60（季线）、MA120（半年线）、MA250（年线/牛熊分界）

#### 派生指标（从已有数据计算，无额外API调用）
- **BOLL位置**: 价格在布林带中的百分比位置 (0-100%)
- **均线状态**: 多头排列 / 空头排列 / 均线纠缠
- **趋势位置**: 年线上方(强势) / 年线下方(弱势)
- **涨跌幅**: 5日/20日涨跌幅
- **20日波动率**: 日均振幅
- **20日高低点**: 近期压力/支撑参考

#### MACD
- 金叉（DIF上穿DEA）：看涨 | 死叉（DIF下穿DEA）：看跌

#### RSI(14)
- RSI > 70：超买 | RSI < 30：超卖 | 50-70：偏强 | 30-50：偏弱

---

## 8. 缓存系统

### 8.1 缓存架构

| 缓存类型 | 存储 | TTL | 说明 |
|---------|------|-----|------|
| A股列表 | `cache/stock_list_cache.json` | 7天 | 自动从AKShare刷新 |
| 港股列表 | `cache/stock_list_cache_hk.json` | 7天 | 优先新浪源，东财备用 |
| 行情/指标数据 | `cache/quant_cache.db` (SQLite) | 4-10小时 | 适合盘中多次查询 |
| 历史分位 | `cache/quant_cache.db` (SQLite) | 7天 | 变化不频繁 |

### 8.2 缓存管理

```bash
# 查看缓存状态
stock-cache

# 清除所有缓存
stock-cache-clear

# 清除特定股票缓存
sqlite3 cache/quant_cache.db "DELETE FROM data_cache WHERE symbol = '002683';"

# 预热缓存（盘后运行，加速第二天查询）
stock-warm         # 预热 My Watchlist
stock-warm dad     # 预热 Dad Watchlist
stock-warm-all     # 预热全部
```

### 8.3 性能提升

| 场景 | 无缓存 | 有缓存 | 提升 |
|------|--------|--------|------|
| 估值分析 (stock-val) | ~200秒 | ~3秒 | 99% |
| 综合分析 (stock-deep) | ~60秒 | ~15秒 | 75% |

---

## 9. 估值分析系统

### 9.1 估值指标

| 指标 | 来源 | 准确性 |
|------|------|--------|
| PE-TTM | 雪球API（备用：百度+东财） | 5.0/5.0 |
| PB | 雪球API | 5.0/5.0 |
| PS-TTM | 计算 | 4.8/5.0 |
| PCF | 新浪财报（经营现金流） | 5.0/5.0 |
| P/FCF | 新浪财报（自由现金流） | 5.0/5.0 |
| 股息率 | 雪球API | 5.0/5.0 |
| PEG | PE / 利润增速 | 4.5/5.0 |

### 9.2 历史分位

来源：百度股市通，提供 10年/5年/3年/1年 分位数据。

**注意**：百度算法为黑盒，分位数据仅作辅助参考，不应单独作为买卖依据。周期股慎用。

### 9.3 现金流分析 (PCF/P_FCF)

V1.1 优化后的数据链路：
```
上交所/深交所官方财报 → 新浪财经API → AKShare → 本系统
```

- PCF 覆盖率：~90%（直接从现金流量表获取）
- P/FCF 覆盖率：~85%（列名模糊匹配）
- 负现金流自动识别并提示风险

### 9.4 数据降级策略

估值数据获取采用多源降级：
1. 雪球API（优先）
2. 百度股市通（备用）
3. 东方财富（兜底）

---

## 10. 新闻舆情引擎

### 10.1 四引擎架构

| 引擎 | 名称 | 优先级 | 作用 |
|:---:|:---|:---:|:---|
| 0 | 东财公告 | 最高 | 个股直接信息（交易所官方） |
| 1 | 财联社电报 | 高 | 宏观/行业/政策视角（智能匹配） |
| 2 | DuckDuckGo | 中 | 备用网络搜索 |
| 3 | 大盘背景 | 低 | 保底市场行情信息 |

### 10.2 财联社电报智能匹配

三级相关性评分：
- **直接相关 (10分)**: 明确提到股票名称/代码
- **行业相关 (5-7分)**: 提到所属行业/板块关键词
- **政策相关 (2-3分)**: 重大宏观政策/市场事件

内置行业关键词库：半导体、军工、新能源、化工、新材料、医药、互联网、机械等。可在代码中扩展。

### 10.3 新闻数量配置

在 `analyst_base.py` 中的 `NEWS_CONFIG`：

| 模式 | 东财公告 | 财联社电报 | DuckDuckGo | 总计 |
|------|:---:|:---:|:---:|:---:|
| 精简模式 | 5 | 3 | 5 | 13条 |
| 标准模式 | 10 | 5 | 10 | 25条 |
| **详尽模式** (当前) | 15 | 8 | 15 | 38条 |

---

## 11. 配置系统

### 11.1 自选股列表 (watchlists.json)

```json
{
  "_comment": "自选股列表配置文件",
  "_version": "1.0",
  "my": {
    "name": "My Watchlist",
    "description": "个人自选股列表",
    "stocks": [
      {"code": "002683", "name": "广东宏大", "tags": ["军工"]},
      {"code": "002179", "name": "中航光电", "tags": ["军工", "连接器"]}
    ]
  },
  "dad": { ... },
  "erin": { ... }
}
```

修改后无需重启，下次运行自动加载。如文件不存在或格式错误，自动使用 main.py 中的默认列表。

验证配置：
```bash
python3 -c "import json; json.load(open('watchlists.json'))" && echo "OK"
```

### 11.2 AI 模型配置 (ai_config.py)

- **Worker 层**: Qwen-Flash（通义千问，快速、低成本）
- **Brain 层**: DeepSeek-V3.2（深度推理）
- API Key 通过环境变量 `DASHSCOPE_API_KEY` 配置

### 11.3 雪球 Token 配置

雪球 API 用于获取实时估值数据。Token 获取方法：

1. 打开 https://xueqiu.com 并登录
2. 浏览器开发者工具 → Application → Cookies → 找到 `xq_a_token`
3. 配置方式：
   - 环境变量：`export XQ_TOKEN="your_token"`
   - 或在代码中直接设置

Token 有效期数月到一年。失效时系统会自动降级到百度股市通+东方财富，功能不受影响。

### 11.4 Crontab 自动化

```bash
# 每天15:30 智能分析 My Watchlist
30 15 * * 1-5 /path/to/.venv/bin/python /path/to/main.py --no-interaction --list my --analysis-mode auto >> /tmp/quant_lab_log.txt 2>&1
```

---

## 12. 数据来源与准确性

### 12.1 数据源评级

| 数据类别 | 数据源 | 可信度 | 数据链路 |
|---------|--------|:---:|------|
| 基础行情 | AKShare (东财/新浪) | 5/5 | 交易所 → 东财/新浪 → AKShare |
| 当前估值 | 雪球 API | 5/5 | 交易所 → 雪球计算 |
| 现金流 | 新浪财经报表 | 5/5 | 交易所财报 → 新浪 → AKShare |
| 财务数据 | AKShare (东财) | 5/5 | 上市公司季报/年报 |
| 新闻公告 | 东方财富 | 5/5 | 交易所官方公告 |
| 历史分位 | 百度股市通 | 4/5 | 算法黑盒，仅作参考 |
| 资金流向 | 东财/同花顺 | 3.5/5 | Level-2推算，非官方统计 |

### 12.2 与机构工具对比

| 维度 | 本系统 | Wind/Bloomberg |
|------|--------|----------------|
| 估值准确性 | 5/5 | 5/5 |
| 财务数据 | 5/5 | 5/5 |
| 实时性 | 1-5分钟延迟 | 毫秒级 |
| 覆盖范围 | A股+部分港股 | 全球 |
| 成本 | **免费** | 数万元/年 |

**结论**：核心财务和估值数据达到机构级水平。适合中长期价值投资，不适合高频交易。

### 12.3 已知局限

1. **季度年化误差** (±5%): PS-TTM 使用 Q3数据×4/3 推算
2. **历史分位黑盒**: 百度算法不透明，周期股可能误导
3. **资金流向非官方**: 不同平台大单标准不统一
4. **数据延迟**: 1-5分钟，不适合日内交易

### 12.4 使用建议

| 场景 | 适用性 | 说明 |
|------|:---:|------|
| 中长期价值投资 | 推荐 | 核心数据准确性5/5 |
| 事件驱动策略 | 推荐 | 官方公告实时跟踪 |
| 组合监控 | 推荐 | Watchlist + 智能触发 |
| 高频交易 | 不适用 | 数据延迟1-5分钟 |
| 衍生品交易 | 不适用 | 无期权/期货数据 |

---

## 13. 故障排查

### 13.1 常见问题

#### API 超时
- **正常耗时**: 深度分析60-90秒，估值分析首次200秒
- **若频繁超时**: 检查网络、检查 `DASHSCOPE_API_KEY` 是否有效

#### 技术数据缺失
```bash
# 清除该股票缓存后重试
sqlite3 cache/quant_cache.db "DELETE FROM data_cache WHERE symbol = '002683';"
```

#### 港股列表获取失败
系统已配置新浪源为主、东财为备用。若仍失败：
```bash
# 删除港股缓存重建
rm cache/stock_list_cache_hk.json
# 下次查询港股时自动重建
```

#### 配置文件加载失败
```bash
# 验证 JSON 格式
python3 -c "import json; json.load(open('watchlists.json'))"
```

#### 均线数据不完整
- MA250 需要1年历史数据，新股可能不足
- 系统会自动使用可用数据

### 13.2 数据源故障降级

```
雪球API失败 → 百度股市通 → 东方财富（自动降级）
港股新浪源失败 → 东财港股接口（自动降级）
东财公告获取失败 → 财联社电报 → DuckDuckGo → 大盘背景（四级降级）
```

---

## 14. 版本迭代历史

### V4.0 (2026-02-09) — 当前版本

- **双路径数据统一**: stock-deep 补充聪明钱/情绪题材/支撑压力3维度；stock-val 补充舆情+派生技术指标
- **文件整合**: 删除 prompt_templates.py，合并 warm_up_cache.py 和 batch_valuation.py 到 main.py
- **命名规范化**: analyst_core→analyst_base, analyst_core_enhanced→analyst_data, analyst_brain_v2→analyst_brain, analyst_cached→analyst_cache
- **港股数据源修复**: 新浪源优先，东财备用
- **文档整合**: 22个文档合并为本文件

### V3.0 (2025-12-22)

- 新增多版本 Prompt 系统（professional/value_first/quant_hybrid）
- 新增多周期均线（MA5/10/20/60/120/250）
- 新增 MACD/RSI/量比 技术指标
- 新增支撑阻力位（60日高低点）和涨跌幅统计（5d/20d/60d）
- 新增 SQLite 缓存系统（性能提升100倍+）
- 优化信号触发条件（增加技术指标信号）
- 新增 Watchlist 快捷命令别名

### V2.2 (2025-12-18)

- 新增股票智能查询功能（stock_finder.py）
- 优化报告文件命名格式
- 新增股票列表缓存

### V2.0 (2025-12-17)

- 引入双层 AI 架构（Worker + Brain）
- 智能触发机制（信号评分>=3 触发 Brain）
- 三大 Watchlist 管理（my/dad/erin）

### V1.1 (2025-12-26)

- PCF 数据覆盖率从 ~10% 提升到 ~90%（直接读取财报）
- 新增 P/FCF（自由现金流）指标，覆盖率 ~85%
- 历史分位数据缓存（7天TTL），重复查询性能提升99%

### V1.0 (2025-12-17)

- 初始版本，基础数据获取和 AI 分析
- 支持单股和 Watchlist 分析
- Markdown/PDF 报告输出

---

## 附录

### A. 数据源链接

| 数据源 | 链接 |
|--------|------|
| AKShare | https://github.com/akfamily/akshare |
| 雪球 | https://xueqiu.com |
| 百度股市通 | https://gushitong.baidu.com |
| 东方财富 | https://www.eastmoney.com |
| 财联社 | https://www.cls.cn |
| 上交所 | http://www.sse.com.cn |
| 深交所 | http://www.szse.cn |

### B. 项目依赖

通过 `uv sync` 安装（见 pyproject.toml），核心依赖：
- `akshare` — A股数据获取
- `openai` — AI 模型调用
- `pandas` — 数据处理
- `fpdf2` — PDF 报告生成

### C. 声明

本系统仅供学习和研究使用，不构成投资建议。股市有风险，投资需谨慎。
