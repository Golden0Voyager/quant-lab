# test_fix_verification.py

验证 JSON 序列化修复和数据抓取容错性。

## 功能

### 验证 1: JSON 序列化
- 构造包含 numpy 类型（bool_, int64, float64）和 datetime 的数据
- 验证 `QuantJSONEncoder` 能正确编码
- 验证 `DataCache.set/get` 能正确读写这些类型

### 验证 2: 抓取容错性
- 使用不存在的股票代码 "999999" 调用 `fetch_integrated_data()`
- 验证函数不会崩溃，返回有效的字典结构

## 运行

```bash
cd /Users/hainingyu/Code/quant_lab
uv run python tests/test_fix_verification.py
```

## 依赖模块

- `data_cache.DataCache`, `data_cache.QuantJSONEncoder`
- `analyst_integration.fetch_integrated_data`

## 使用场景

- 修改缓存序列化逻辑后的回归测试
- 验证数据抓取的异常处理是否完善
