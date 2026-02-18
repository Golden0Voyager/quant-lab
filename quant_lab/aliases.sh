# ============================================
# Quant Lab V4.0 快捷命令配置（精简版）
# 添加到 ~/.zshrc: source ~/Code/quant_lab/aliases.sh
# 更新日期: 2026-02-08
# ============================================

# ============================================
# 基础命令
# ============================================
stock() {
    python /Users/hainingyu/Code/quant_lab/main.py "$@"
}

# ============================================
# 单股分析（核心2个命令）
# ============================================
stock-check() { stock --analysis-mode auto --stock "$@"; }   # 智能分析（日常最常用）
stock-deep() { stock --analysis-mode deep --stock "$@"; }    # 深度分析（买入决策）

# ============================================
# Watchlist 分析（6个命令）
# ============================================
# 智能模式（日常跟踪）
stock-my() { stock --list my --analysis-mode auto "$@"; }
stock-dad() { stock --list dad --analysis-mode auto "$@"; }
stock-erin() { stock --list erin --analysis-mode auto "$@"; }

# 深度模式（周末复盘）
stock-my-deep() { stock --list my --analysis-mode deep "$@"; }
stock-dad-deep() { stock --list dad --analysis-mode deep "$@"; }
stock-erin-deep() { stock --list erin --analysis-mode deep "$@"; }

# ============================================
# 估值分析（4个命令）
# ============================================
stock-val() { stock --valuation "$@"; }                      # 单股快速估值
stock-batch-val() { stock --batch-valuation "$@" --delay 3.0; }  # 批量估值

# Watchlist 批量估值
stock-val-my() {
    python -c "
import json
with open('/Users/hainingyu/Code/quant_lab/watchlists.json') as f:
    stocks = json.load(f)['my']
    print('\n'.join([f\"{s['name']} {s['code']}\" for s in stocks]))
" | stock --batch-valuation /dev/stdin --yes
}

stock-val-dad() {
    python -c "
import json
with open('/Users/hainingyu/Code/quant_lab/watchlists.json') as f:
    stocks = json.load(f)['dad']
    print('\n'.join([f\"{s['name']} {s['code']}\" for s in stocks]))
" | stock --batch-valuation /dev/stdin --yes
}

stock-val-erin() {
    python -c "
import json
with open('/Users/hainingyu/Code/quant_lab/watchlists.json') as f:
    stocks = json.load(f)['erin']
    print('\n'.join([f\"{s['name']} {s['code']}\" for s in stocks]))
" | stock --batch-valuation /dev/stdin --yes
}

# ============================================
# 工具命令
# ============================================
alias stock-report='ls -lt /Users/hainingyu/Code/quant_lab/Report/$(date +%y%m%d)/ 2>/dev/null || echo "今日暂无报告"'
alias stock-log='tail -f /tmp/quant_lab_log.txt'
alias stock-cache='sqlite3 /Users/hainingyu/Code/quant_lab/quant_cache.db "SELECT symbol, datetime(cached_at, \"unixepoch\", \"localtime\") as cached_time FROM data_cache ORDER BY cached_at DESC LIMIT 20;"'
alias stock-cache-clear='rm -f /Users/hainingyu/Code/quant_lab/quant_cache.db && echo "缓存已清除"'

# 缓存预热（盘后运行，第二天查数据更快）
stock-warm() { stock --warm-cache "${1:-my}"; }
alias stock-warm-all='stock --warm-cache all'

# PDF 转换监控
stock-pdf() {
    cd /Users/hainingyu/Code/quant_lab
    python /Users/hainingyu/Code/quant_lab/md2pdf_tool.py --dir /Users/hainingyu/Code/quant_lab/Report "$@"
}
alias stock-pdf-stop='pkill -f md2pdf_tool.py && echo "PDF 监控进程已关闭"'

# ============================================
# 帮助命令
# ============================================
alias stock-help='echo "
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📊 Quant Lab V4.0 快捷命令使用指南（精简版）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【单股分析】⭐ 核心2个命令
  stock-check 广东宏大           智能分析（日常最常用，自动触发深度）
  stock-deep 600519              深度分析（买入决策，完整研报）

【Watchlist 分析】📋 6个命令
  stock-my                       智能分析 My（日常跟踪）
  stock-dad                      智能分析 Dad
  stock-erin                     智能分析 Erin

  stock-my-deep                  深度分析 My（周末复盘）
  stock-dad-deep                 深度分析 Dad
  stock-erin-deep                深度分析 Erin

【估值分析】🎯 4个命令
  stock-val 600519               单股快速估值（PE/PB/PS/PCF+历史分位）
  stock-batch-val stocks.txt     批量估值（从文件，带3秒延迟）
  stock-val-my                   My Watchlist 批量估值
  stock-val-dad                  Dad Watchlist 批量估值
  stock-val-erin                 Erin Watchlist 批量估值

【工具命令】
  stock-warm                     预热缓存 My（盘后运行）
  stock-warm dad                 预热缓存 Dad
  stock-warm-all                 预热全部缓存
  stock-report                   查看今日报告列表
  stock-pdf                      🚀 启动 PDF 自动转换监控（实时生成 PDF）
  stock-log                      实时查看运行日志
  stock-cache                    查看缓存状态
  stock-cache-clear              清除所有缓存
  stock-help                     显示此帮助信息

【使用场景】
  • 日常盘后跟踪：stock-check 广东宏大
  • 周末深度复盘：stock-my-deep
  • 快速估值筛选：stock-val 贵州茅台
  • 批量估值监控：stock-val-my

【高级用法】（需要时直接用参数）
  # 切换分析模式
  stock --analysis-mode fast --stock 600519        # 快速模式
  stock --analysis-mode deep --stock 600519        # 深度模式
  stock --analysis-mode auto --stock 600519        # 智能模式

  # 切换Prompt风格（深度分析时）
  stock --analysis-mode deep --prompt-version professional --stock 600519  # 机构研报（默认）
  stock --analysis-mode deep --prompt-version value_first --stock 600519   # 价值投资
  stock --analysis-mode deep --prompt-version quant_hybrid --stock 600519  # 量化评分

  # 批量估值（快速模式）
  stock --batch-valuation stocks.txt --delay 0.5 --yes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
精简说明：从30+命令精简到13个核心命令，保留最常用场景
如需特殊分析模式，请使用上方【高级用法】中的完整参数
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"'

# ============================================
# Crontab 自动化任务示例
# ============================================
# 每天15:30 智能分析 My Watchlist（添加到 crontab -e）：
# 30 15 * * 1-5 /Users/hainingyu/Code/quant_lab/.venv/bin/python /Users/hainingyu/Code/quant_lab/main.py --no-interaction --list my --analysis-mode auto >> /tmp/quant_lab_log.txt 2>&1
