# quant_lab — A股量化分析工具

## 架构

- **`analyst_base.py`**：K线数据获取 + 技术指标（MA, RSI, MACD, BOLL）
- **`analyst_data.py`**：12+ 数据维度（估值、业绩、情绪、宏观等）
- **`analyst_integration.py`**：统一数据管道 + AI prompt 构建
- **`analyst_cache.py`**：SQLite 缓存层（`cache/quant_cache.db`）
- **`analyst_openbb.py`**：Yahoo Finance 全球宏观数据（OpenBB，线程本地代理）
- **`ai_config.py`**：全局网络配置（monkey-patch Session，Yahoo 代理注入）
- **`valuation_analyzer.py`**：批量估值模式（17 维度）

## 常用命令

```bash
# 深度分析
python main.py --list my --analysis-mode deep

# 批量估值
python main.py --batch-valuation "stock1,stock2" --yes
```

## K线数据源（降级顺序）

1. **东财** `ak.stock_zh_a_hist()` → `push2his.eastmoney.com`（不稳定）
2. **新浪** `ak.stock_zh_a_daily()` → 需要 `sh`/`sz` 前缀（如 `sz002594`）
3. **腾讯** `ak.stock_zh_a_hist_tx()` → 同样前缀格式，无成交量列

通用辅助：`analyst_data.fetch_kline_multi_source()`

## 网络配置

- `ai_config.init_global_network()` 对所有 requests.Session 设置 `trust_env=False`
- Yahoo Finance：线程本地代理注入 `_yahoo_proxy`（Clash 127.0.0.1:8118）
- 东财等国内 API：直连（不需代理）
- 东财 IPv6 不可靠 → 通过 `socket.getaddrinfo` monkey-patch 强制 IPv4

## 开发注意事项

- **缓存清理**：修改数据源后必须清理 `stock_base` + `extended` 类型的缓存条目，否则不会拉取新数据
- **观察列表**：`watchlists.json` 包含 my/dad/erin 三个列表
