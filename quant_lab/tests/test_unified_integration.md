# test_unified_integration.py

测试统一数据集成入口（`fetch_integrated_data` 和 `fetch_stock_data`）。

## 功能

以贵州茅台 (600519) 为测试用例，执行 3 个场景：

1. **兼容性接口** — `fetch_stock_data()`，默认使用缓存
2. **显式缓存** — `fetch_integrated_data(use_cache=True)`，验证缓存命中
3. **实时抓取** — `fetch_integrated_data(use_cache=False)`，验证绕过缓存

每个场景检查：
- 耗时是否符合预期（缓存应极短，实时应>1秒）
- 返回数据的完整性（tech_summary、pe_ttm 等字段）
- 缓存一致性（两次缓存查询的 timestamp 应相同）

## 运行

```bash
cd /Users/hainingyu/Code/quant_lab
uv run python tests/test_unified_integration.py
```

## 依赖模块

- `analyst_integration.fetch_integrated_data`
- `analyst_integration.fetch_stock_data`

## 使用场景

- 修改缓存策略后的集成验证
- 确认数据获取接口的行为正确性
