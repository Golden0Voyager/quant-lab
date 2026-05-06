# quant_lab v2 重构升级计划

## Context

quant_lab 当前是 13K 行的 A 股量化分析工具集（13 个根目录 .py 文件），数据维度丰富但**流程层薄**：12 维数据 → 一个超长 prompt → 一次 LLM call → regex 抠决策。三大痛点：

1. **巨石文件**：`analyst_data.py` 3196 行、`valuation_analyzer.py` 3223 行、`main.py` 809 行，单文件耦合多职责
2. **无 schema 哲学**：数据流是 dict、输出是 markdown、决策是 regex，三层都没契约
3. **单 provider 锁定**：`ai_config.py` 只支持 OpenAI 兼容协议，换 Claude/Gemini 要大改造

借鉴刚刚完成调研的 **TradingAgents 框架**（详见 `quant_lab/docs/01-refactor/tradingagents-borrowing-notes.md`）的 7 个工程化骨架点，但**不引入** LangGraph/多 agent 辩论（A 股语境过度工程化）。

**目标**：在 12-15 周内，把 quant_lab 从"脚本集合"升级成可演化的产品，**在保留 v1 可运行的前提下**通过 `quant_lab/core/` 命名空间并行搭建 v2，最终切换。

**预期产出**：
- 4 个独立可替换的层：**数据获取 / LLM / 决策 / 记忆**
- `analyst_*.py` 全部退役，单文件不超过 500 行
- 支持 DeepSeek / Qwen / GLM / Claude / Gemini 五家 provider
- T+1 反思闭环可跑通
- 单元测试覆盖核心路径

---

## 兼容策略

**并行新旧**：所有新代码进入 `quant_lab/core/` 子包（v2 命名空间），老 `analyst_*.py` 保持可跑，迁移完毕后再统一切换。`main.py` 提供过渡期双轨入口（`--legacy` 走老路径）。

---

## 借鉴标识图例

- 🎯 **[TA-Direct]**：直接照搬 TradingAgents 的设计/代码结构
- 🌟 **[TA-Adapted]**：参考 TradingAgents 思路，针对 A 股场景适配
- 💡 **[Original]**：quant_lab 自有创新或保留护城河

---

## 阶段路线图（12-15 周）

### Phase 0 — 基建（Week 1）

**目标**：搭好 v2 命名空间和工程基础设施。

- 新建 `quant_lab/core/` 子包，建立完整目录骨架
- `pyproject.toml` 添加依赖：`pydantic>=2.0`, `pydantic-settings`, `langchain-anthropic`, `questionary`, `anthropic`
- 建立 `tests/v2/` 目录 + `conftest.py`（pytest fixtures，重点是 mock LLM）
- ruff/mypy 配置覆盖到 `core/`
- `core/__init__.py` 暴露顶层 API

**关键文件**：
- 新建 `quant_lab/core/{__init__.py, schemas/, llm/, net/, data/, pipeline/, memory/, config.py, cli.py}`
- 修改 `quant_lab/pyproject.toml`

**验收**：`uv sync` 成功，`pytest tests/v2/` 跑通空测试。

---

### Phase 1 — 结构化输出层 🎯 [TA-Direct]（Week 2-3）

**目标**：用 Pydantic schema 替代 regex 抠结果，从根上消除"模型升级就崩"的风险。

**直接借鉴**：`TradingAgents/tradingagents/agents/schemas.py` + `agents/utils/structured.py` 的双文件模式。

**实现**：
- `core/schemas/stock.py`：A 股核心 schema
  ```python
  class StockRating(str, Enum):
      STRONG_BUY = "强烈买入"; BUY = "买入"; HOLD = "持有"
      REDUCE = "减持"; SELL = "卖出"

  class StockAnalysis(BaseModel):
      rating: StockRating = Field(description="...五档评级...")
      key_signals: list[str] = Field(description="3-5 条关键信号")
      risk_alerts: list[str] = Field(description="主要风险点")
      target_price: float | None = Field(default=None)
      confidence: float = Field(ge=0, le=1)
      time_horizon: str | None = Field(default=None)
  ```
- `core/schemas/fund.py`：基金/ETF 专用 schema（含持仓穿透字段）
- `core/schemas/index.py`：指数/大盘 schema
- `core/schemas/batch.py`：批量估值 schema（17 维）
- `core/schemas/render.py`：每个 schema 配 `render_xxx()` 函数（schema → markdown）— 🎯 直接照搬 TA 的 `render_pm_decision` 模式
- `core/llm/structured.py`：`invoke_structured_or_freetext()` 工具函数 — 🎯 完全照搬 TA 的优雅降级模式（结构化失败自动 fallback 到自由文本）

**关键文件**：
- 参考源：`TradingAgents/tradingagents/agents/schemas.py:32-228`
- 参考源：`TradingAgents/tradingagents/agents/utils/structured.py:1-74`

**验收**：用 mock LLM 跑通 schema 生成 + render 还原 markdown。用真实 DeepSeek/Qwen 各跑 1 只票端到端验证 function-calling 模式。

---

### Phase 2 — LLM Provider 抽象层 🌟 [TA-Adapted]（Week 4-5）

**目标**：解耦 provider，未来接 Claude/Gemini 不用改业务代码。

**适配 TA**：`TradingAgents/tradingagents/llm_clients/` 整套架构，但**不依赖 LangChain**（quant_lab 用原生 `openai`/`anthropic` SDK 即可，更轻）。

**实现**：
- `core/llm/base.py`：定义 `LLMClient` Protocol
  ```python
  class LLMClient(Protocol):
      def chat(self, prompt: str, *, schema: type[BaseModel] | None = None,
               **kwargs) -> str | BaseModel: ...
  ```
- `core/llm/openai_compat.py`：OpenAI 兼容族（DeepSeek/Qwen/GLM/ModelScope/DashScope/OpenRouter）
  - 🌟 借鉴 TA `openai_client.py:52-104` 的 `DeepSeekChatOpenAI` 子类设计，把 DeepSeek thinking-mode 的 `reasoning_content` 回传逻辑封装到子类
- `core/llm/anthropic.py`：Anthropic 客户端（备用，用 anyrouter 中转）
- `core/llm/factory.py`：单一入口 `create_client(provider, model, **kwargs)`
- `core/llm/catalog.py`：模型白名单 + 能力描述（哪些支持 structured/thinking/vision）— 🌟 借鉴 TA 的 `model_catalog.py` + `validators.py`
- 兼容层：`ai_config.py` 标记 `@deprecated`，内部委托给 `core.llm.factory`，老代码无感

**关键文件**：
- 参考源：`TradingAgents/tradingagents/llm_clients/factory.py`
- 参考源：`TradingAgents/tradingagents/llm_clients/openai_client.py:52-176`
- 改造：`quant_lab/ai_config.py:82-167`（保留向后兼容）

**验收**：跑 5 个 provider 各 1 次 ping 测试；老 `analyst_brain.py` 和 `main.py:call_ai` 无修改即可继续工作。

---

### Phase 3 — 网络层重构 🌟 [TA-Adapted + 💡 Original]（Week 6）

**目标**：消除 `ai_config.init_global_network()` 的全局 monkey-patch，改为显式 session 工厂；**保留** quant_lab 独有的国内 API 处理能力（这是 TA 没有的护城河）。

**实现**：
- `core/net/sessions.py`：显式 session 工厂
  - `make_china_session()`：国内 API 用（trust_env=False / 真实 UA / 重试 / 东财强制 IPv4）— 💡 quant_lab 原创
  - `make_yahoo_session()`：Yahoo Finance 用（注入 Clash 代理）— 💡 原创
  - `make_llm_session()`：LLM API 用（按 provider 区分代理策略）
- `core/net/dns.py`：东方财富 IPv4 强制（从 `ai_config.py:26-33` 抽出）
- `core/net/retry.py`：统一重试策略
- 移除：`ai_config.init_global_network()` 标记 deprecated；新代码全部用依赖注入

**关键文件**：
- 抽离自：`quant_lab/ai_config.py:20-76`（旧 monkey-patch 实现）
- 调用方：`core/llm/*` + `core/data/sources/*`

**验收**：`pytest tests/v2/net/` 验证国内/海外 session 隔离；老代码不动，新代码改用注入式 session。

---

### Phase 4 — 数据层重组 🌟 [TA-Adapted + 💡 Original]（Week 7-9，最大工作量）

**目标**：拆解 `analyst_data.py` (3196 行) 和 `valuation_analyzer.py` (3223 行) 两个巨石文件。

**适配 TA**：`tradingagents/dataflows/interface.py` 的 **VENDOR_METHODS 双层路由**模式。

**实现**：
- `core/data/sources/`：每个数据源一个文件（每个 < 300 行）
  - `eastmoney.py`、`sina.py`、`tencent.py`、`akshare.py`、`xueqiu.py`、`jiuquan.py`、`openbb_yahoo.py`
  - 每个 source 实现统一接口：`fetch_kline / fetch_valuation / fetch_news / ...`（不实现的方法 raise NotImplementedError）

- `core/data/registry.py`：🌟 直接借鉴 TA 的双层路由
  ```python
  DATA_SOURCES = {
      "kline": ["eastmoney", "sina", "tencent"],   # 默认降级链
      "valuation": ["xueqiu", "jiuquan"],
      "news": ["eastmoney"],
      ...
  }
  TOOL_OVERRIDES = {  # 单 tool 级覆盖（用户 config 注入）
      "fetch_kline_for_index": "sina",  # 指数走新浪
  }
  ```
  - 一个 `route(method, asset_type)` 函数返回降级序列

- `core/data/dimensions/`：把 `analyst_data.py` 的 12+ 维拆成独立文件
  - `valuation.py`、`performance.py`、`sentiment.py`、`macro.py`、`consensus.py`、`market_env.py`、`lockup.py`、`chip.py`、`institution.py`、`competitor.py`、`smart_money.py`、`theme.py`、`support_resistance.py`
  - 每个维度独立测试、独立缓存

- `core/data/cache.py`：缓存层重写（保留 SQLite + WAL，加入显式 `CacheStrategy`）
  - 维度级 TTL（K 线 24h、新闻 1h、估值 12h）
  - 兼容老 DB schema（`cache/quant_cache.db`），不丢历史缓存

- `core/data/aggregator.py`：聚合多维数据成 `AnalysisInput` Pydantic 对象（取代 `fetch_integrated_data` 返回的 dict）

**关键文件**：
- 拆解源：`quant_lab/analyst_data.py` (3196 行 → ~13 个 < 300 行的文件)
- 拆解源：`quant_lab/valuation_analyzer.py` (3223 行 → 批量估值合并到 `core/data/dimensions/valuation.py`)
- 参考源：`TradingAgents/tradingagents/dataflows/interface.py:31-110`

**验收**：
- 对比测试：v2 数据聚合输出 vs v1 相同 ticker，关键字段一致
- 单元测试：每个 source 用 `responses` 库 mock HTTP 请求

---

### Phase 5 — 流程编排层 🌟 [TA-Adapted]（Week 10）

**目标**：把 `main.py` 里的 `run_single_stock_mode` / `run_global_stock_mode` / `run_monitor_mode` 三个混杂的过程拆成可组合的 Pipeline。

**适配 TA**：参考 `TradingAgents/tradingagents/graph/setup.py` 的 StateGraph 思路，**但不引入 LangGraph**（线性流程足够）。

**实现**：
- `core/pipeline/state.py`：`AnalysisState` Pydantic 模型 — 🌟 借鉴 TA 的 `AgentState`，但更简单（无 messages、无 debate）
  ```python
  class AnalysisState(BaseModel):
      ticker: str
      asset_type: AssetType  # stock/etf/fund/index
      trade_date: date
      raw_data: AnalysisInput | None = None
      prompt: str | None = None
      analysis: StockAnalysis | None = None
      report_path: Path | None = None
      past_context: str = ""  # 🌟 借鉴 TA 的 past_context 字段
  ```
- `core/pipeline/base.py`：`PipelineStep` 抽象基类，`run(state) -> state`
- `core/pipeline/steps/`：可复用步骤
  - `FetchDataStep`、`BuildPromptStep`、`InvokeLLMStep`、`SaveReportStep`、`StoreMemoryStep`
- `core/pipeline/builders.py`：组装预设 pipeline
  - `build_stock_pipeline()`、`build_fund_pipeline()`、`build_index_pipeline()`、`build_global_pipeline()`、`build_batch_valuation_pipeline()`
- `core/pipeline/runner.py`：执行器（含日志、异常隔离、可选 checkpoint）

**关键文件**：
- 参考源：`TradingAgents/tradingagents/graph/setup.py:90-180`
- 拆解源：`quant_lab/main.py:185-450`（三个 mode 函数）

**验收**：现有所有 `python main.py` 用法可以用 `python -m quant_lab.core.cli` 平替（参数兼容）。

---

### Phase 6 — 持续学习闭环 🎯 [TA-Direct]（Week 11-12）

**目标**：让历史 `Report/` 不再是死文件，T+1 反思闭环驱动模型迭代。

**直接照搬**：`TradingAgents/tradingagents/agents/utils/memory.py` 的整体设计（append-only markdown + pending/resolved 状态机）。

**实现**：
- `core/memory/log.py`：`AnalysisMemoryLog` 类
  - `store_decision()`：分析后写一条 `pending` 记录
  - `get_pending_entries()` / `resolve_with_outcome()`：T+1 后回算
  - `get_past_context(ticker, n_same=5, n_cross=3)`：注入 prompt
  - 🎯 完全照搬 TA `memory.py:31-96` 的实现

- `core/memory/reflection.py`：反思生成
  - `Reflector.reflect_on_decision(decision, raw_return, alpha_return)`
  - 用 quick LLM 生成 1-2 句反思（"判断对了/错了什么"）
  - 🎯 借鉴 TA `Reflector` 但 alpha 基准从 SPY 换成沪深 300（000300.SH）

- `core/memory/migration.py`：把现有 `Report/26xxxx/` 历史报告批量导入 memory log
  - 解析每份 .md 提取 ticker / date / rating
  - 拉历史 K 线算实际收益和 alpha
  - 一次性脚本

- `core/memory/path.py`：`safe_ticker_component()` — 🎯 照搬 TA 的路径安全工具，用在 `Report/<ticker>/` 写入路径

**关键文件**：
- 参考源：`TradingAgents/tradingagents/agents/utils/memory.py:1-150`
- 参考源：`TradingAgents/tradingagents/graph/trading_graph.py:229-263`（store + resolve 流程）
- 参考源：`TradingAgents/tradingagents/dataflows/utils.py:safe_ticker_component`
- 数据源：`quant_lab/Report/` 历史目录（260411 ~ 260426 等）

**验收**：
- 跑一次 `python -m quant_lab.core.memory.migration` 把历史报告导入
- 重新分析任一历史 ticker，prompt 中能看到 `past_context` 注入

---

### Phase 7 — 配置中心化 🌟 [TA-Adapted]（Week 13）

**目标**：消灭 `ai_config.ACTIVE_PROFILE` 全局变量，配置可测试可覆盖。

**适配 TA**：参考 `TradingAgents/tradingagents/default_config.py` + `dataflows/config.py:set_config` 模式，**升级**为 Pydantic Settings（TA 用的是普通 dict，quant_lab 直接用 Pydantic 更现代）。

**实现**：
- `core/config.py`：`QuantLabSettings(BaseSettings)`
  - LLM provider/model/timeout
  - 数据源默认路由 + 工具级覆盖
  - 缓存 TTL 配置
  - 反思开关、memory 路径
  - `model_config = SettingsConfigDict(env_file=".env", env_prefix="QUANT_LAB_")`
- `core/watchlists.py`：`Watchlist(BaseModel)` + 加载器（替代 `main.py:33-99` 的 `load_watchlists`）
- `core/config.py:get_settings()` 单例

**关键文件**：
- 参考源：`TradingAgents/tradingagents/default_config.py`
- 替换：`quant_lab/ai_config.py:82-116` (MODEL_CONFIGS + ACTIVE_PROFILE)
- 替换：`quant_lab/main.py:33-99` (load_watchlists + 默认 dict)

**验收**：`tests/v2/config/` 测试可注入不同 settings；CLI 支持 `--config path/to/custom.toml`。

---

### Phase 8 — CLI 入口（Week 14）

**目标**：取代 `main.py` 的 `input()` + 30 秒超时交互，提供更顺手的菜单。

**适配 TA**：`TradingAgents/cli/main.py` 用 `questionary` 的方式。

**实现**：
- `core/cli.py`：基于 `questionary` 的交互式入口
  - 模式选择：单股 / 自选股监控 / 批量估值 / 全球 / 基金穿透
  - watchlist 选择（my/dad/erin）
  - 分析深度选择（fast/auto/deep）
  - LLM provider 选择（覆盖默认）
- `core/cli_args.py`：CLI 参数版本（脚本/cron 用），保持 `--list my --analysis-mode deep` 等老参数兼容
- `quant_lab/main.py`：标记 deprecated，转发到 `core.cli`，加 `--legacy` flag 走老路径

**关键文件**：
- 参考源：`TradingAgents/cli/main.py` + `cli/utils.py`
- 改造：`quant_lab/main.py:114-157`

**验收**：交互式 + 参数式两种入口都能跑通既有 5 种分析模式。

---

### Phase 9 — 切换与退役（Week 15）

**目标**：v1 → v2 正式切换，老 `analyst_*.py` 删除。

**步骤**：
1. 文档：在 README 标注 v2 为默认，v1 进入维护模式
2. 切换：`main.py` 默认走 v2，`--legacy` 才走 v1
3. 一周观察期（v1 v2 双跑，对比报告差异）
4. 删除老文件：`analyst_base.py` / `analyst_data.py` / `analyst_brain.py` / `analyst_cache.py` / `analyst_integration.py` / `analyst_fund.py` / `analyst_openbb.py` / `valuation_analyzer.py` / `data_cache.py` / `ai_config.py` / `stock_finder.py`
5. `pyproject.toml` 清理不再需要的依赖

**保留**：
- `Report/` 目录（已迁入 memory log）
- `cache/quant_cache.db`（v2 兼容）
- `md2pdf_tool.py`（v2 直接 import 复用）
- `api/` 子模块（独立 SaaS 化路径，v2 改造另起计划）

---

## 文件改动总览

### 新增（v2）
```
quant_lab/core/
├── __init__.py
├── config.py              [TA-Adapted] Pydantic Settings
├── cli.py                 [TA-Adapted] questionary 交互
├── watchlists.py
├── schemas/
│   ├── stock.py           [TA-Direct]
│   ├── fund.py            [Original]
│   ├── index.py           [Original]
│   ├── batch.py           [Original]
│   └── render.py          [TA-Direct]
├── llm/
│   ├── base.py            [TA-Adapted] Protocol
│   ├── factory.py         [TA-Adapted]
│   ├── openai_compat.py   [TA-Adapted] DeepSeek 子类
│   ├── anthropic.py       [TA-Adapted]
│   ├── catalog.py         [TA-Adapted]
│   └── structured.py      [TA-Direct] 优雅降级
├── net/
│   ├── sessions.py        [Original] 国内 API 工厂
│   ├── dns.py             [Original] IPv4 强制
│   └── retry.py
├── data/
│   ├── registry.py        [TA-Adapted] 双层路由
│   ├── aggregator.py      [Original]
│   ├── cache.py
│   ├── sources/           [Original] (7+ 数据源各一文件)
│   └── dimensions/        [Original] (12+ 维度各一文件)
├── pipeline/
│   ├── state.py           [TA-Adapted] AnalysisState
│   ├── base.py            [TA-Adapted] PipelineStep
│   ├── steps/
│   ├── builders.py
│   └── runner.py
└── memory/
    ├── log.py             [TA-Direct]
    ├── reflection.py      [TA-Direct]
    ├── path.py            [TA-Direct] safe_ticker_component
    └── migration.py       [Original] Report/ 导入
```

### 修改（兼容层）
- `quant_lab/main.py`：转发到 `core.cli`，保留 `--legacy` flag
- `quant_lab/pyproject.toml`：新依赖

### 退役（Phase 9 删除）
- `analyst_base.py` / `analyst_data.py` / `analyst_brain.py` / `analyst_cache.py` / `analyst_integration.py` / `analyst_fund.py` / `analyst_openbb.py` / `valuation_analyzer.py` / `data_cache.py` / `ai_config.py` / `stock_finder.py`

### 完全保留
- `Report/`、`cache/`、`md2pdf_tool.py`、`api/`、`watchlists.json`、`all_stock_data/`

---

## 验证策略

### 阶段验证（每个 Phase 结束）
- 单元测试：`pytest tests/v2/<phase> -v`
- 类型检查：`mypy quant_lab/core/`
- Lint：`ruff check quant_lab/core/`

### 端到端对比（Phase 4/5/6 结束）
- 同一 ticker / 同一 date，v1 和 v2 各跑一次
- 对比关键字段：`rating`、`tech_summary`、`risk_alerts`
- 允许差异：自由文本部分（LLM 非确定性）
- 不允许差异：数据获取层的数值字段

### 现实压力测试（Phase 9 切换前）
- 在工作日早盘跑 `--list my --analysis-mode deep`，对比 v1 v2 用时和报告质量
- 一次跨 7 天的滚动测试（每天跑 watchlist + 反思闭环）

---

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| 拆 3K 行的 `analyst_data.py` 出问题 | 对比测试 + 老文件保留到 Phase 9 |
| DeepSeek/Qwen 的 structured output 兼容性差 | `invoke_structured_or_freetext` 优雅降级保底 |
| 历史 `Report/` 解析不准（格式不统一） | migration 脚本 dry-run + 人工抽样检查 |
| 网络层改造影响现有数据获取 | Phase 3 优先重构 LLM 网络，数据源网络在 Phase 4 才动 |
| 用户工作流被打断 | `--legacy` flag 保留至少 1 个月 |

---

## 关键决策

1. **不引入 LangGraph**：流程线性，自建轻量 Pipeline 足够，省一个重依赖。
2. **不引入 LangChain**：用原生 `openai`/`anthropic` SDK，更轻；TA 的 Provider 抽象思路照搬即可。
3. **不做多 agent 辩论**：A 股语境下，单 prompt + 多维数据效果接近，token 成本低 5-10 倍。
4. **保留 monkey-patch 兼容性**：Phase 3 不删 `ai_config.init_global_network()`，标记 deprecated，到 Phase 9 才删。
5. **api/ 子模块独立演化**：SaaS 化是另一条线，不在本次重构范围。
