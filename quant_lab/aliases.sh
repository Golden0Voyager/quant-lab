# ============================================
# Quant Lab 快捷命令别名配置
# 添加到 ~/.zshrc 或 ~/.bashrc
# ============================================

# 设置动态库路径（用于 PDF 生成）
export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH"

# 主命令
alias stock='python /Users/hainingyu/Code/quant_lab/main.py'

# Watchlist 快捷命令
alias stock-my='python /Users/hainingyu/Code/quant_lab/main.py --list my --analysis-mode auto'
alias stock-dad='python /Users/hainingyu/Code/quant_lab/main.py --list dad --analysis-mode auto'
alias stock-erin='python /Users/hainingyu/Code/quant_lab/main.py --list erin --analysis-mode auto'

# 单股查询快捷命令
alias stock-check='python /Users/hainingyu/Code/quant_lab/main.py --stock'
alias stock-deep='python /Users/hainingyu/Code/quant_lab/main.py --analysis-mode deep --stock'
alias stock-fast='python /Users/hainingyu/Code/quant_lab/main.py --analysis-mode fast --stock'

# 深度分析整个列表
alias stock-my-deep='python /Users/hainingyu/Code/quant_lab/main.py --list my --analysis-mode deep'
alias stock-dad-deep='python /Users/hainingyu/Code/quant_lab/main.py --list dad --analysis-mode deep'

# 快速查看报告
alias stock-report='ls -lt /Users/hainingyu/Code/quant_lab/Report/$(date +%y%m%d)/ 2>/dev/null || echo "今日暂无报告"'
alias stock-log='tail -f /tmp/quant_lab_log.txt'

# 帮助命令
alias stock-help='echo "
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📊 Quant Lab 快捷命令使用指南
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【基础命令】
  stock --stock 600519              查询单个股票
  stock --list my                   分析 My Watchlist

【单股查询】⭐ 最常用
  stock-check 600519:贵州茅台       快速查询 (auto模式)
  stock-deep 000063:中兴通讯        深度分析
  stock-fast 002475                 快速分析

【Watchlist 分析】
  stock-my                          智能分析 My (auto)
  stock-dad                         智能分析 Dad (auto)
  stock-erin                        智能分析 Erin (auto)
  stock-my-deep                     深度分析 My (deep)
  stock-dad-deep                    深度分析 Dad (deep)

【工具命令】
  stock-report                      查看今日报告列表
  stock-log                         实时查看运行日志
  stock-help                        显示此帮助信息

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"'
