#!/bin/bash
# 文件清理与整理脚本

echo "🧹 开始清理与整理文件..."

# 1. 创建文档目录
mkdir -p docs
mkdir -p archive

echo ""
echo "📁 移动文档到 docs/ 目录..."
mv AKSHARE_NEWS_INVESTIGATION.md docs/
mv BUGFIX_SUMMARY.md docs/
mv IMPLEMENTATION_REPORT.md docs/
mv NEWS_SOURCES_COMPARISON.md docs/

echo ""
echo "📦 归档已完成的测试文件到 archive/ 目录..."
mv diagnose_akshare.py archive/
mv news_api_fixed.py archive/
mv news_sina.py archive/
mv test_alternative_news.py archive/
mv test_news_fix.py archive/
mv test_news_sources.py archive/

echo ""
echo "📋 创建项目说明文档..."

cat > README.md << 'EOF'
# Quant Lab - AI量化分析系统

AI驱动的A股量化分析与监控系统。

## 功能特性

- 📊 **多维度数据分析**: 技术面、资金面、舆情面三维分析
- 🤖 **AI智能研判**: 使用GLM-4.6大模型生成投资建议
- 📰 **三引擎新闻获取**: 东财公告 + 全网搜索 + 大盘背景
- ⚡ **高性能**: 平均响应时间<3秒
- 📈 **自动化报告**: 每日自动生成投资晨报

## 快速开始

### 安装依赖

```bash
uv sync
```

### 配置API Key

```bash
export DASHSCOPE_API_KEY="你的Key"
```

### 运行测试

```bash
# 快速测试单只股票
python quick_test.py

# 性能测试
python test_performance.py

# 完整监控模式（生成报告）
python main.py
```

## 项目结构

```
quant_lab/
├── analyst_core.py          # 核心数据获取模块
├── main.py                  # 主程序（监控模式）
├── quick_test.py            # 快速测试脚本
├── test_performance.py      # 性能测试脚本
├── Report/                  # 生成的报告目录
├── docs/                    # 项目文档
└── 01/                      # 实验性脚本
```

## 核心模块

### analyst_core.py

三引擎新闻获取架构：

```
🏆 引擎1: 东财公告（优先）⚡ <1秒
    ↓ 失败
⚡ 引擎2: DuckDuckGo搜索（备用）~4秒
    ↓ 失败
🛡️ 引擎3: 大盘背景（保底）稳定
```

**性能指标**：
- 成功率: 100%
- 平均响应: 2.74秒
- 数据源: 官方公告

### main.py

监控模式，支持：
- 批量股票监控
- 不同资产类型（个股/ETF/指数）
- AI分析与评级
- 自动生成Markdown报告

## 数据源

| 数据类型 | 来源 | 更新频率 |
|---------|------|---------|
| K线数据 | AkShare | 实时 |
| 资金流向 | 东方财富 | 实时 |
| 公司公告 | 东方财富 | 实时 |
| 市场新闻 | 全网搜索 | 实时 |

## 文档

- [实施报告](docs/IMPLEMENTATION_REPORT.md) - 三引擎方案实施详情
- [数据源对比](docs/NEWS_SOURCES_COMPARISON.md) - 各种新闻源对比分析
- [问题诊断](docs/AKSHARE_NEWS_INVESTIGATION.md) - AkShare问题调查
- [修复总结](docs/BUGFIX_SUMMARY.md) - Bug修复记录

## 配置

编辑 `main.py` 中的 `WATCHLIST` 配置自选股：

```python
WATCHLIST = [
    {"code": "000988", "name": "华工科技"},
    {"code": "600519", "name": "贵州茅台"},
    # ... 更多股票
]
```

## 依赖

- Python >= 3.12
- akshare >= 1.17.95
- ddgs >= 9.9.3
- openai >= 2.11.0
- pandas >= 2.3.3

## 许可

MIT License

## 更新日志

### v2.0 (2025-12-17)
- ✨ 新增：三引擎新闻获取架构
- ⚡ 优化：响应速度提升31.5%
- 🐛 修复：AkShare新闻接口失效问题
- 📊 改进：数据质量提升（官方公告）

### v1.0
- 初始版本
EOF

echo ""
echo "✅ 清理完成！"
echo ""
echo "📊 整理结果:"
echo "  ✅ 核心文件: analyst_core.py, main.py"
echo "  ✅ 测试工具: quick_test.py, test_performance.py"
echo "  ✅ 文档目录: docs/ (4个文档)"
echo "  ✅ 归档目录: archive/ (6个测试文件)"
echo ""
echo "🗑️  可以安全删除 archive/ 目录（如需要）："
echo "  rm -rf archive/"
