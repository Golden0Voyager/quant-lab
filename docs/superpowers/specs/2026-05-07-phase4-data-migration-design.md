# Phase 4 数据层重组完成方案 (设计稿 / Spec)

**日期**：2026-05-07
**作者**：Haining + Claude（brainstorming session）
**状态**：Draft，等待用户批准
**背景文档**：`docs/01-refactor/implementation-plan-v2.md`、`docs/01-refactor/tradingagents-borrowing-notes.md`

## 1. 目标

把 `analyst_data.py`（3196 行单文件，19 个 `fetch_*_data` 函数）全量迁移为 v2 数据层架构（`quant_lab/core/data/`），1:1 对等，迁完后接入 `main.py`。

**完成定义**：

- 19 个 legacy `fetch_*_data` 函数全部由 `dimensions/<name>.py` 中的 `DimensionFetcher` 实现替代
- 每个迁移维度具备：单元测试（happy path + 降级） + parity 测试（与 legacy 输出关键 key 一致）
- `sources/` 按数据源拆分（eastmoney / xueqiu / sina / tencent / ths / baidu / macro）
- `main.py` 增加 `--v2` flag，可端到端跑通深度分析与批量估值
- 全 v2 测试 + ruff + mypy 全绿
- legacy `analyst_data.py` 仍保留，由 Phase 9 统一删除

**非目标**：

- 改进数据维度的业务逻辑（保持 legacy 行为）
- 删除 `analyst_data.py`（留给 Phase 9）
- 引入 LangGraph / LangChain
- 优化性能（保持当前缓存层不变）

## 2. 核心设计决策

| 决策 | 取舍 | 已选项 |
|---|---|---|
| 范围 | 全量迁 / 核心迁 / 端到端走通 | **全量 1:1 迁移** |
| 测试纪律 | 严格 TDD / 同步交付 / 后补测试 / 分级 | **严格 TDD（先测后码）** |
| v2 接入时机 | 一次性接入 / 分批接入带 fallback / 早期接入子集 | **全部迁完后一次性接入** |
| sources 组织 | 按数据源 / 按业务领域 / 单文件 / 单文件分节 | **按数据源拆分** |
| 1:1 验证 | mock 级 parity / 端到端手动 / schema 超集 / 不验证 | **mock 级 parity 测试** |
| 迁移路线 | sources 先重构 / 维度优先 / 原样搬迁 | **sources 先重构再分组迁维度** |

## 3. 目标目录结构

```
quant_lab/core/data/
├── __init__.py                     # 导出 + build_default_aggregator()
├── aggregator.py                   # 已存在
├── cache.py                        # 已存在
├── registry.py                     # 已存在
├── dimensions/
│   ├── base.py                     # DimensionFetcher Protocol + safe_fetch
│   ├── valuation.py                ✅ 已迁
│   ├── performance.py              ✅ 已迁
│   ├── sentiment.py                ✅ 已迁
│   ├── consensus.py                ✅ 已迁
│   ├── recent_kline.py             ⏳ 源 fetch_recent_20d_and_boll
│   ├── quarterly_trend.py          ⏳
│   ├── industry_compare.py         ⏳ 源 fetch_industry_comparison
│   ├── top_holders.py              ⏳
│   ├── chip.py                     ⏳
│   ├── smart_money.py              ⏳
│   ├── institution.py              ⏳
│   ├── lockup.py                   ⏳
│   ├── competitor.py               ⏳
│   ├── theme.py                    ⏳ 源 fetch_theme_sentiment_data
│   ├── news.py                     ⏳
│   ├── support_resist.py           ⏳ 源 fetch_support_resistance_data
│   ├── macro_etf.py                ⏳
│   ├── market_env.py               ⏳
│   └── extended.py                 ⏳
├── sources/
│   ├── base.py                     # 已存在
│   ├── _utils.py                   # safe_float / no_proxy
│   ├── eastmoney.py                # ⏳ 拆 akshare_.py + 新增东财调用
│   ├── xueqiu.py                   # ⏳ 拆 akshare_.py
│   ├── sina.py                     # ⏳ 拆 akshare_.py
│   ├── tencent.py                  # ⏳
│   ├── ths.py                      # ⏳
│   ├── baidu.py                    # 已存在
│   └── macro.py                    # ⏳ shibor / fx / index_daily
└── (移除 akshare_.py)               # 重构完成后删除

tests/v2/data/
├── test_aggregator.py              # 已存在
├── test_cache.py                   # 已存在
├── test_registry.py                # 已存在
├── test_dimensions/
│   ├── test_valuation.py           ✅
│   ├── test_performance.py         ✅
│   ├── test_sentiment.py           ⏳ 现缺
│   ├── test_consensus.py           ⏳ 现缺
│   └── test_<remaining 15>.py
├── test_sources/                   # 新增
│   ├── test_eastmoney.py
│   ├── test_xueqiu.py
│   ├── test_sina.py
│   ├── test_tencent.py
│   ├── test_ths.py
│   ├── test_baidu.py
│   └── test_macro.py
├── parity/                         # 新增
│   ├── conftest.py                 # mock_all_sources fixture
│   ├── test_valuation_parity.py
│   ├── test_performance_parity.py
│   └── test_<其余 17>.py
└── fixtures/                       # 真实数据快照
    ├── valuation_000001.json
    └── ...
```

## 4. sources/ 重构细节

### 4.1 拆分映射

| 新文件 | 包含函数（首批） |
|---|---|
| `eastmoney.py` | `fetch_stock_info_eastmoney`, `fetch_eastmoney_kline`, `fetch_financial_report` (stock_yjbb_em), `fetch_north_flow` (stock_hsgt_*), `fetch_chip_distribution` (stock_cyq_em), `fetch_lockup_release` (stock_restricted_release_queue_em), `fetch_market_activity` (stock_market_activity_legu), `fetch_concept_board` (stock_board_concept_*), `fetch_industry_board` (stock_board_industry_*) |
| `xueqiu.py` | `fetch_xueqiu_spot`, `fetch_xueqiu_basic_info` |
| `sina.py` | `fetch_sina_kline` |
| `tencent.py` | `fetch_tencent_kline` (stock_zh_a_hist_tx) |
| `ths.py` | `fetch_profit_forecast_ths`, `fetch_industry_summary_ths` |
| `baidu.py` | `fetch_valuation_percentile`（保持现状） |
| `macro.py` | `fetch_shibor`, `fetch_fx_quote`, `fetch_index_daily` |

### 4.2 统一约定

1. 顶部 `import akshare as ak`（或 `requests`）
2. 所有函数返回 `dict[str, Any] | None`，不返回 DataFrame
3. 异常一律捕获 → 返回 `None` + `logger.debug`
4. 国内源的 akshare 调用一律包 `with no_proxy()`
5. 函数命名：`fetch_<具体内容>`（不带源后缀，文件名已表明源）

### 4.3 重构步骤（保持现有 4 维度不破坏）

1. 新建 6 个空源文件骨架
2. 当前 `akshare_.py` 函数逐一移到对应新文件，原 `akshare_.py` 改为 re-export shim
3. 更新已迁 4 个维度的 import 路径
4. 删除 `akshare_.py` shim，跑全测试确认绿
5. 给每个源文件补 happy path 单元测试（mock akshare）

## 5. dimensions 分组迁移顺序

**前置 Step 2.5（先于 Step 3 完成）**：补 sentiment / consensus 单元测试 + 给已迁的 valuation / performance / sentiment / consensus 4 维度补 parity 测试与 fixture。这是 sources 重构（Step 3）的安全网——重构期间任何 import 路径错误都会被这批测试捕获。

| 组 | Step | 维度 | 主要数据源 | legacy 行数 |
|---|---|---|---|---|
| 行情技术类 | 4 | `recent_kline`, `quarterly_trend`, `industry_compare`, `top_holders` | eastmoney + sina + tencent | 约 230 |
| 资金筹码类 | 5 | `chip`, `smart_money`, `institution`, `lockup`, `competitor` | eastmoney 资金/筹码 | 约 720 |
| 舆情主题类 | 6 | `theme`, `news`, `support_resist` | ths + eastmoney 舆情 | 约 340 |
| 宏观环境类 | 7 | `macro_etf`, `market_env`, `extended` | macro + 综合 | 约 750 |

**为何这个顺序**：

1. 行情技术类作为分组样板（复杂度低、数据源相对独立）
2. 资金筹码类共享 eastmoney 源文件（前一组已打好）
3. 舆情主题类引入 ths 这个新源
4. 宏观环境类含 `market_env`、`extended` 这种聚合型维度，依赖前置维度产出

### 每维度的 TDD 工作流

对组内每个维度 D：

1. 读 legacy `fetch_<D>_data`，列出输入/输出 contract
2. 写 `tests/v2/data/test_dimensions/test_<D>.py`：
   - happy path（mock 数据源返回标准 dict）
   - 1-2 个降级路径（数据源返回 None）
3. 跑测试 → 红
4. 在 `dimensions/<D>.py` 写 fetcher class，遵循 `base.DimensionFetcher` Protocol
   - 如需新 source 函数，先在 `sources/<src>.py` 加（带单元测试）
5. 跑测试 → 绿
6. 写 parity 测试（见 §6）
7. 跑全 v2 测试 + ruff + mypy
8. 单独 commit（双语 commit message，conventional commits 格式）

### 每组 checkpoint

- 跑全量 v2 测试
- 在记忆 `project_v2_plan.md` 更新进度
- Push 到 main（或合并 worktree）

## 6. Parity 测试设计

### 6.1 目的

捕获迁移过程中无意改变的计算逻辑，确保 v2 与 legacy 关键字段输出一致。

### 6.2 设计

```python
# tests/v2/data/parity/test_valuation_parity.py（示意）
def test_valuation_parity():
    fixture = load_fixture("valuation_000001.json")

    with mock_all_sources(fixture):
        legacy_out = analyst_data.fetch_valuation_data("000001", "平安银行")
        v2_out = ValuationFetcher().fetch("000001", "平安银行")

    assert set(v2_out.keys()) >= set(legacy_out.keys()) - IGNORED_KEYS
    for key in CRITICAL_KEYS["valuation"]:
        assert v2_out[key] == legacy_out[key], f"{key} 不一致"
```

### 6.3 关键约定

1. **fixture 来源**：每个维度抓一次真实数据存 `tests/v2/fixtures/<dimension>_<symbol>.json`，签入仓库
2. **CRITICAL_KEYS**：每个维度定义"必须 1:1 对等"的 key 列表（raw 数值字段）
3. **容忍范围**：浮点用 `pytest.approx(rel=1e-6)`，字符串严格相等
4. **降级 parity**：每维度再加 `test_<D>_parity_fallback`，所有 source 返回 None，确认两端都进入降级分支

### 6.4 fixture JSON 格式

按"源模块 → 函数名 → 返回值"两层嵌套，便于 mock_all_sources 直接消费：

```json
{
  "xueqiu": {
    "fetch_xueqiu_spot": {
      "市盈率(TTM)": "15.5",
      "市净率": "1.2",
      "股息率(TTM)": "3.5",
      "总市值": "5000000000"
    }
  },
  "baidu": {
    "fetch_valuation_percentile": {
      "10y": 45.2,
      "5y": 50.0
    }
  },
  "eastmoney": {
    "fetch_stock_info_eastmoney": null
  }
}
```

返回值为 `null` 表示让该 source 函数返回 `None`（用于降级测试）。

### 6.5 mock_all_sources fixture

`tests/v2/data/parity/conftest.py` 提供统一上下文管理器：

```python
@contextmanager
def mock_all_sources(fixture: dict[str, Any]):
    """根据 fixture 内容，patch 所有 sources/ 中的 fetch_* 函数。"""
    patches = []
    for source_module, calls in fixture.items():
        for func_name, return_value in calls.items():
            patcher = patch(f"quant_lab.core.data.sources.{source_module}.{func_name}",
                           return_value=return_value)
            patches.append(patcher)
            patcher.start()
    try:
        yield
    finally:
        for p in patches:
            p.stop()
```

## 7. 集成（Step 8-9）

### 7.1 StockAggregator 全量集成（Step 8）

`quant_lab/core/data/__init__.py` 增加便捷工厂：

```python
def build_default_aggregator(cache: DataCacheFacade | None = None) -> StockAggregator:
    cache = cache or DataCacheFacade()
    registry = DimensionRegistry(cache=cache)

    registry.register("valuation", ValuationFetcher())
    registry.register("performance", PerformanceFetcher())
    registry.register("sentiment", SentimentFetcher())
    registry.register("consensus", ConsensusFetcher())
    registry.register("macro_etf", MacroEtfFetcher())
    registry.register("recent_kline", RecentKlineFetcher())
    registry.register("quarterly_trend", QuarterlyTrendFetcher())
    registry.register("industry_compare", IndustryCompareFetcher())
    registry.register("top_holders", TopHoldersFetcher())
    registry.register("chip", ChipFetcher())
    registry.register("smart_money", SmartMoneyFetcher())
    registry.register("institution", InstitutionFetcher())
    registry.register("lockup", LockupFetcher())
    registry.register("competitor", CompetitorFetcher())
    registry.register("theme", ThemeFetcher())
    registry.register("news", NewsFetcher())
    registry.register("support_resist", SupportResistFetcher())
    registry.register("market_env", MarketEnvFetcher())
    registry.register("extended", ExtendedFetcher())

    return StockAggregator(registry)
```

集成测试 `tests/v2/data/test_aggregator_full.py`：

- mock 全部 19 个维度（用 fixture），断言 aggregator 返回字段总数与 legacy `fetch_full_stock_data` 一致
- 跨维度计算回归测试（如 PEG 计算依赖 valuation + consensus）

### 7.2 main.py 接入（Step 9）

不新建 `main_v2.py`，直接在 `main.py` 增加 `--v2` flag：

```python
if args.v2:
    from quant_lab.core.data import build_default_aggregator
    aggregator = build_default_aggregator()
    data = aggregator.aggregate(symbol, stock_name, asset_type=asset_type)
else:
    data = analyst_data.fetch_full_stock_data(symbol, stock_name, asset_type)
# 后续 prompt 构建/AI 调用复用同一份代码
```

后续步骤：

1. CLI 帮助文本更新
2. 真实股票端到端验证（人工抽样 3-5 只观察列表股票，对比 v2 与 legacy 输出关键字段）
3. 记忆里 v2_plan 状态切到"Phase 4 完成"

## 8. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 真实 fixture 抓不到（API 限流/封 IP） | 部分维度无 parity 测试基线 | 每个维度抓 1-2 次保留快照，遵循 quant-lab 守则的并发控制 |
| `akshare_.py` 拆分导致已迁 4 维度暂时报错 | sources 重构期短暂红 | 用 re-export shim 过渡，全测试绿后再删 shim |
| legacy `fetch_<D>_data` 内有依赖全局 state（如 module 级 cache） | 直接迁会丢失行为 | 每个维度迁前先读源码识别全局 state，迁时显式传参 |
| 19 维度 × TDD × parity 工作量大 | 节奏拖太久 | 按分组每组 checkpoint，可分多次 session 推进；每组完成立即更新 v2_plan 记忆 |
| 真实端到端验证发现差异 | Step 9 卡住 | 抽样 3-5 只股票即可，发现差异回到对应维度补 fix，不阻塞整体 |

## 9. 进度跟踪

迁移进度记录在记忆 `project_v2_plan.md`，每完成一组维度更新一次。

**Phase 4 整体步骤回顾**：

- ✅ Step 1：sources/ 与 dimensions/ 骨架 + 基础设施
- ✅ Step 2：4 个核心维度迁移（valuation/performance/sentiment/consensus）
- ⏳ Step 2.5：补 sentiment/consensus 单元测试 + 4 维度 parity 测试
- ⏳ Step 3：sources/ 拆分重构
- ⏳ Step 4：行情技术类 4 维度
- ⏳ Step 5：资金筹码类 5 维度
- ⏳ Step 6：舆情主题类 3 维度
- ⏳ Step 7：宏观环境类 3 维度
- ⏳ Step 8：StockAggregator 全量集成 + 集成测试
- ⏳ Step 9：main.py `--v2` flag + 端到端验证

## 10. 验收标准

- [ ] 19 个维度全部存在于 `dimensions/<name>.py`
- [ ] `analyst_data.py` 19 个 `fetch_*_data` 函数仍存在但不再被新代码引用
- [ ] 每维度具备：≥ 2 个单元测试（happy path + 降级）+ 2 个 parity 测试（正常 + 降级）
- [ ] `akshare_.py` 已删除
- [ ] `sources/` 含 7 个源文件（eastmoney / xueqiu / sina / tencent / ths / baidu / macro），每个 ≥ 1 个单元测试
- [ ] 测试规模预期：当前 81 + 单元 ~60（15 维度 × 4 + sentiment/consensus 补 8）+ parity ~76（19 × 4）+ sources ~20 + 集成 ~5 ≈ **240+ 测试**，全绿
- [ ] `ruff check .` 无 violations
- [ ] `mypy quant_lab/core/data/` 无 error
- [ ] `python main.py --v2 --list my --analysis-mode deep` 端到端跑通
- [ ] 抽 3-5 只股票，v2 与 legacy 输出 CRITICAL_KEYS 字段一致（人工抽检）
