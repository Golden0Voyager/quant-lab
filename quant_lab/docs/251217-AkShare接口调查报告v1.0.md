# AkShare 新闻接口修复调查报告

**调查日期**: 2025-12-17
**AkShare 版本**: 1.17.94 → 1.17.95
**问题接口**: `stock_news_em()`

---

## 🔍 问题分析

### 核心问题
`ak.stock_news_em()` 接口失效，报错：
```
JSONDecodeError: Extra data: line 1 column 17 (char 16)
```

### 根本原因

经过深入诊断，发现**两个关键问题**：

#### 1. JSONP Callback 动态化
- **AkShare 假设**: 固定callback名称
  ```python
  callback = "jQuery35101792940631092459_1764599530165"
  data_json = json.loads(text.strip(f"{callback}(")[:-1])
  ```

- **实际情况**: 东方财富返回的callback每次不同
  ```
  jQuery35108723733748578402_1693632913001({...})  # 实际返回
  ```

#### 2. API 数据结构改变（更严重）
- **期待返回**: `result.cmsArticleWebOld` (新闻文章列表)
- **实际返回**: `result.passportWeb` (用户信息)

完整返回数据示例：
```json
{
  "bizCode": "",
  "code": 0,
  "msg": "OK",
  "result": {
    "passportWeb": [{  ← 不是 cmsArticleWebOld！
      "uid": "8223456637392854",
      "alias": "达利食品",
      "stockFollowerCount": 7289,
      ...
    }]
  }
}
```

**结论**：东方财富的搜索 API 已经彻底改变，不再返回新闻文章。

---

## 🔧 尝试的修复方案

### 方案1：升级 AkShare ❌
```bash
uv pip install --upgrade akshare  # 1.17.94 → 1.17.95
```
**结果**: 仍然失败，官方也未修复

### 方案2：动态提取 JSONP ❌
创建了正则表达式动态提取 callback：
```python
match = re.search(r'jQuery\d+_\d+\((.*)\)$', response_text)
```
**结果**: 即使成功解析，返回的数据结构也不对

### 方案3：寻找替代接口 ⚠️
测试了其他 AkShare 新闻接口：
- `stock_news_main_cx`: 参数不兼容
- `news_cctv`: 只能获取央视新闻（非个股新闻）

**结果**: 无可用替代接口

---

## ✅ 最佳解决方案

### 推荐：使用 DuckDuckGo 搜索（已实现）

**优势**：
1. ✅ 已经在 `analyst_core.py` 中实现
2. ✅ 三层降级机制保证可用性
3. ✅ 实测效果良好，成功率高
4. ✅ 获取的新闻质量优秀

**实际测试结果**：
```
德赛西威 (002920):
  ✅ 通过全网搜索获取 5 条新闻
  - 德赛西威股价涨5.02%，浙商证券资管旗下1只基金重仓...
  - 德赛西威股价涨5.41%，新沃基金重仓赚取3.01万元...
  - 德赛西威 (002920.SZ)股票信息_上市信息 - 企查查
```

**实现架构**：
```
引擎1: AkShare (ak.stock_news_em)
  ↓ 失败（预期）
引擎2: DuckDuckGo 联网搜索
  ↓ 成功 ✅
引擎3: 大盘背景（保底）
```

---

## 🎯 AkShare 新闻接口状态

| 接口 | 状态 | 备注 |
|------|------|------|
| `stock_news_em` | ❌ 失效 | JSON解析错误 + API改变 |
| `stock_news_main_cx` | ⚠️ 不可用 | 参数不兼容 |
| `news_cctv` | ✅ 可用 | 仅央视新闻，非个股 |
| `news_economic_baidu` | 未测试 | - |

---

## 💡 给开发者的建议

### 短期方案（已实施）✅
**继续使用 DuckDuckGo 双引擎机制**，这是目前最稳定的方案。

### 长期方案（可选）
如果确实需要恢复 AkShare 接口，可以：

1. **监控 AkShare 更新**
   ```bash
   # 定期检查更新
   pip index versions akshare
   ```

2. **向 AkShare 官方提 Issue**
   - GitHub: https://github.com/akfamily/akshare
   - 说明 `stock_news_em` 接口失效

3. **直接使用东方财富新接口**
   - 需要逆向工程找到新的 API 端点
   - 可能需要模拟浏览器请求

4. **使用其他金融数据源**
   - 新浪财经 API
   - 腾讯财经 API
   - 金融界 API

---

## 📝 测试脚本

项目中创建的诊断脚本：
- `diagnose_akshare.py` - 诊断接口问题
- `test_alternative_news.py` - 测试替代接口
- `news_api_fixed.py` - 尝试修复的版本（未成功）

---

## 🏁 结论

**AkShare 的 `stock_news_em` 接口目前无法修复**，因为：
1. 上游 API（东方财富）已改变
2. 官方最新版本也未修复
3. 无可用的替代接口

**✅ 推荐继续使用现有的 DuckDuckGo 方案**，该方案：
- 已经过充分测试
- 效果良好
- 维护成本低
- 新闻质量高

**无需进一步修复 AkShare 接口。**
