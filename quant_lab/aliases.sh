# ============================================
# Quant Lab V3.0 快捷命令别名配置
# 添加到 ~/.zshrc 或 ~/.bashrc
# 更新日期: 2025-12-22
# ============================================

# 设置动态库路径（用于 WeasyPrint PDF 生成）
# 必须在 Python 启动前设置，否则 WeasyPrint 无法找到 glib 库
export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:${DYLD_FALLBACK_LIBRARY_PATH:-}"

# ============================================
# 基础命令（使用函数包装以确保环境变量生效）
# ============================================
stock() {
    DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:${DYLD_FALLBACK_LIBRARY_PATH:-}" \
    python /Users/hainingyu/Code/quant_lab/main.py "$@"
}

# ============================================
# 单股查询 - 基础模式
# ============================================
# 快速查询（auto模式，智能触发）
stock-check() { stock --analysis-mode auto --stock "$@"; }
# 快速分析（fast模式，仅Worker）
stock-fast() { stock --analysis-mode fast --stock "$@"; }
# 深度分析（deep模式，默认prompt）
stock-deep() { stock --analysis-mode deep --stock "$@"; }

# ============================================
# 单股查询 - Prompt版本 (V3.0 新增)
# ============================================
# 价值投资分析（deep + value_first）
stock-value() { stock --analysis-mode deep --prompt-version value_first --stock "$@"; }
# 量化评分分析（deep + quant_hybrid）
stock-quant() { stock --analysis-mode deep --prompt-version quant_hybrid --stock "$@"; }
# 专业研报分析（deep + professional）
stock-pro() { stock --analysis-mode deep --prompt-version professional --stock "$@"; }

# ============================================
# Watchlist 分析 - 智能模式 (auto)
# ============================================
stock-my() { stock --list my --analysis-mode auto "$@"; }
stock-dad() { stock --list dad --analysis-mode auto "$@"; }
stock-erin() { stock --list erin --analysis-mode auto "$@"; }

# ============================================
# Watchlist 分析 - 深度模式 (deep)
# ============================================
stock-my-deep() { stock --list my --analysis-mode deep "$@"; }
stock-dad-deep() { stock --list dad --analysis-mode deep "$@"; }
stock-erin-deep() { stock --list erin --analysis-mode deep "$@"; }

# ============================================
# Watchlist 分析 - Prompt版本 (V3.0 新增)
# ============================================
# 价值版深度分析
stock-my-value() { stock --list my --analysis-mode deep --prompt-version value_first "$@"; }
stock-dad-value() { stock --list dad --analysis-mode deep --prompt-version value_first "$@"; }
stock-erin-value() { stock --list erin --analysis-mode deep --prompt-version value_first "$@"; }
# 量化版深度分析
stock-my-quant() { stock --list my --analysis-mode deep --prompt-version quant_hybrid "$@"; }
stock-dad-quant() { stock --list dad --analysis-mode deep --prompt-version quant_hybrid "$@"; }
stock-erin-quant() { stock --list erin --analysis-mode deep --prompt-version quant_hybrid "$@"; }
# 专业版深度分析
stock-my-pro() { stock --list my --analysis-mode deep --prompt-version professional "$@"; }
stock-dad-pro() { stock --list dad --analysis-mode deep --prompt-version professional "$@"; }
stock-erin-pro() { stock --list erin --analysis-mode deep --prompt-version professional "$@"; }

# ============================================
# 工具命令
# ============================================
# 查看今日报告
alias stock-report='ls -lt /Users/hainingyu/Code/quant_lab/Report/$(date +%y%m%d)/ 2>/dev/null || echo "今日暂无报告"'
# 实时日志
alias stock-log='tail -f /tmp/quant_lab_log.txt'
# 查看缓存状态 (V3.0 新增)
alias stock-cache='sqlite3 /Users/hainingyu/Code/quant_lab/quant_cache.db "SELECT symbol, datetime(cached_at, \"unixepoch\", \"localtime\") as cached_time FROM data_cache ORDER BY cached_at DESC LIMIT 20;"'
# 清除缓存 (V3.0 新增)
alias stock-cache-clear='rm -f /Users/hainingyu/Code/quant_lab/quant_cache.db && echo "缓存已清除"'

# ============================================
# 帮助命令
# ============================================
alias stock-help='echo "
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📊 Quant Lab V3.0 快捷命令使用指南
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【单股查询 - 基础】⭐ 最常用
  stock-check 广东宏大           智能分析 (auto模式)
  stock-fast 600519              快速分析 (fast模式)
  stock-deep 002683:广东宏大     深度分析 (deep模式)

【单股查询 - Prompt版本】🆕 V3.0
  stock-value 广东宏大           价值投资分析 (估值+盈利质量)
  stock-quant 广东宏大           量化评分分析 (多因子打分)
  stock-pro 广东宏大             专业研报分析 (机构风格)

【Watchlist 智能分析】(auto模式)
  stock-my                       智能分析 My
  stock-dad                      智能分析 Dad
  stock-erin                     智能分析 Erin

【Watchlist 深度分析】(deep模式，默认prompt)
  stock-my-deep                  深度分析 My
  stock-dad-deep                 深度分析 Dad
  stock-erin-deep                深度分析 Erin

【Watchlist + Prompt版本】🆕 V3.0 完整覆盖
  stock-{my,dad,erin}-value      价值投资版
  stock-{my,dad,erin}-quant      量化评分版
  stock-{my,dad,erin}-pro        专业研报版

【工具命令】
  stock-report                   查看今日报告列表
  stock-log                      实时查看运行日志
  stock-cache                    查看缓存状态 🆕
  stock-cache-clear              清除所有缓存 🆕
  stock-help                     显示此帮助信息

【Prompt版本说明】
  professional  机构研报风格 (默认)
  value_first   价值投资视角 (中长期)
  quant_hybrid  多因子量化评分 (系统化)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"'

# ============================================
# Crontab 自动化任务示例
# ============================================
# 每天15:30 智能分析 My Watchlist（添加到 crontab -e）：
# 30 15 * * 1-5 /Users/hainingyu/Code/quant_lab/.venv/bin/python /Users/hainingyu/Code/quant_lab/main.py --no-interaction --list my --analysis-mode auto >> /tmp/quant_lab_log.txt 2>&1

# 每周五 深度分析 Erin Watchlist（量化评分版）：
# 40 15 * * 5 /Users/hainingyu/Code/quant_lab/.venv/bin/python /Users/hainingyu/Code/quant_lab/main.py --no-interaction --list erin --analysis-mode deep --prompt-version quant_hybrid >> /tmp/quant_erin.log 2>&1
