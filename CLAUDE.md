## ⚠️ 环境约束（强制）

- **包管理器**：`uv pip install <pkg>`（禁止 `pip` / `python -m pip`）
- **运行脚本**：`uv run python <script>.py`（禁止直接 `python`）

---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

All development uses `uv`. The virtual environment is already configured.

```bash
# Install dependencies
uv sync

# Run the full v2 test suite
uv run pytest tests/v2/ -q

# Run a single test file
uv run pytest tests/v2/pipeline/test_steps.py -q

# Run a single test method
uv run pytest tests/v2/pipeline/test_steps.py::TestFetchDataStep::test_fetch_without_cache -q

# Lint (v2 scope only)
uv run ruff check quant_lab/core/ tests/v2/

# Type check (mypy is configured to only check quant_lab/core/)
uv run mypy quant_lab/core/

# Run the legacy CLI
python main.py --list my --analysis-mode deep
python main.py --batch-valuation "stock1,stock2" --yes
```

## High-Level Architecture

This codebase is in a **dual-track migration**: legacy scripts at the repo root coexist with the new v2 architecture under `quant_lab/core/`. All new work goes into v2; legacy files (`analyst_*.py`, `main.py`, `valuation_analyzer.py`) are frozen and scheduled for removal in Phase 9.

### v2 Architecture (6 layers)

```
quant_lab/core/
├── schemas/      # Pydantic output contracts (StockAnalysis, FundAnalysis, IndexAnalysis)
├── llm/          # LLMClient Protocol + factory + model catalog
├── net/          # Explicit session factories + DNS IPv4 forcing + retry strategy
├── data/         # DimensionFetcher Protocol + per-source modules + aggregator
│   ├── sources/     # eastmoney, xueqiu, sina, tencent, baidu
│   └── dimensions/  # 15 fetchers: valuation, performance, sentiment, market_env, …
├── pipeline/     # PipelineStep ABC + 6 steps + runner + builders
└── memory/       # Placeholder (Phase 7)
```

**Pipeline flow** (single-stock analysis):

```
FetchDataStep → EvaluateSignalsStep → BuildPromptStep → InvokeLLMStep → SaveReportStep → StoreMemoryStep
```

- `FetchDataStep` calls `aggregate(symbol, stock_name)` which runs 17 `DimensionFetcher`s sequentially.
- `EvaluateSignalsStep` scores 17 signal categories; `signal_score >= 3` triggers deep analysis.
- `BuildPromptStep` selects worker prompt (~300 chars) or brain prompt (deep analysis) based on `need_deep_analysis`.
- `InvokeLLMStep` uses `create_client()` from the LLM factory; auto-switches to `deep_model` when deep analysis is needed.
- `SaveReportStep` writes Markdown to `Report/YYMMDD/` and attempts PDF conversion.

**Builder functions** return pre-configured step lists:
- `build_auto_pipeline()` — signal-driven, auto-switches worker/brain
- `build_deep_pipeline()` — forces brain path (skips signal evaluation)
- `build_fast_pipeline()` — forces worker path, unstructured output

**Data layer design**:
- `DimensionFetcher` is a Protocol with `fetch(self, symbol, stock_name, **kwargs) -> dict`. The `@safe_fetch` decorator catches all exceptions and returns `{"_error": ..., "_dimension": ...}` so the aggregator never crashes.
- `aggregate()` injects upstream context into `SupportResistanceFetcher` (it needs prices/MA/BOLL from prior dimensions).
- Sources (`eastmoney.py`, `xueqiu.py`, etc.) are split by external API, not by business dimension.

**Network layer design**:
- `make_china_session()` — `trust_env=False`, no proxy, browser UA, retry adapter
- `make_yahoo_session()` — injects Clash proxy (`http://127.0.0.1:7897`)
- `make_llm_session()` — `httpx.Client` for LLM APIs
- `prefer_ipv4_for_host()` context manager forces IPv4 for EastMoney (IPv6 is unreliable)

**LLM layer design**:
- `create_client(provider, model)` is the single entry point.
- `ModelCatalog` is a whitelist/registry of supported models (DeepSeek, Qwen, GLM, Claude).
- `invoke_structured_or_freetext()` attempts structured output and falls back to free text.

### Legacy Architecture (frozen)

Root-level Python files are the legacy system:
- `analyst_integration.py` — 1,673-line god class: data aggregation + signal evaluation + prompt building + LLM calling
- `analyst_data.py` — 3,196-line data杂货铺: 12+ dimensions mixed together
- `analyst_base.py` — K-line fetching + technical indicators (MA, RSI, MACD, BOLL)
- `main.py` — CLI entry + dual ThreadPoolExecutor monitor mode
- `valuation_analyzer.py` — batch valuation logic
- `analyst_cache.py` — SQLite cache layer (`cache/quant_cache.db`)

## Project-Specific Rules

When modifying quant_lab code, follow these rules (from `.claude/rules/quant-lab.md`):

1. **Signal confidence**: any signal or analysis output must include a confidence score in `[0, 1]` range.
2. **Signal attribution**: signals must explicitly label their trigger source (e.g. `Source: AkShare K-line`, `Source: Volume Spike`).
3. **Core formulas only in `analyst_base.py`**: do not hard-code calculation formulas in UI or IO logic.
4. **Protect `all_stock_data/`**: never modify or delete files in this directory.
5. **Check cache first**: before writing new read logic, check `cache/` to avoid duplicate API calls.
6. **AkShare priority**: prefer AkShare for A-share data unless explicitly asked for Yahoo Finance (US stocks).
7. **Randomized delays**: implement random sleep when doing batch data scraping to avoid IP bans.

## Tooling Configuration

- **Ruff**: `line-length = 100`, targets Python 3.12, lints `E/F/I/N/W/UP/B/C4/SIM`. `E501` is ignored.
- **Mypy**: `disallow_untyped_defs = true`, only checks `quant_lab/core/` (legacy has too many historical type errors).
- **Pytest**: `testpaths = ["tests/v2"]`, `pythonpath = ["."]`.
- **Network proxy**: Clash at `127.0.0.1:7897` is injected via `.zshrc` (`export https_proxy=...`).

## Cache and Output Directories

- SQLite cache: `cache/quant_cache.db`
- Generated reports: `Report/YYMMDD/`
- Watchlists: `watchlists.json` (contains `my`, `dad`, `erin` lists)

## K-Line Data Fallback Chain

1. EastMoney (`ak.stock_zh_a_hist()`) → `push2his.eastmoney.com` (unstable)
2. Sina (`ak.stock_zh_a_daily()`) → requires `sh`/`sz` prefix (e.g. `sz002594`)
3. Tencent (`ak.stock_zh_a_hist_tx()`) → same prefix format, no volume column

## Important Notes

- When modifying data sources, **clear the `stock_base` and `extended` cache entries** or the pipeline will reuse stale data.
- `md2pdf_tool` is an optional soft dependency (not in `pyproject.toml`). `SaveReportStep` handles its absence gracefully.
- The v2 pipeline is not yet wired into `main.py` (Phase 6). To test v2 end-to-end, use the builder functions and `PipelineRunner` directly.
