"""
main.py 集成示例
展示如何将四维数据整合到现有的双脑机制中
"""

import logging
import os

from openai import OpenAI

from analyst_brain import AnalystBrain
from analyst_integration import build_enhanced_prompt, evaluate_enhanced_signals, fetch_integrated_data

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

# === AI配置 ===
QWEN_KEY = os.getenv("DASHSCOPE_API_KEY")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_MODEL = "qwen-flash"  # Worker层快速模型
DEEPSEEK_MODEL = "deepseek-v3.2"  # Brain层深度模型

# 初始化AI客户端
qwen_client = OpenAI(api_key=QWEN_KEY, base_url=BASE_URL, timeout=30.0)
brain = AnalystBrain(model=DEEPSEEK_MODEL, api_key=QWEN_KEY, base_url=BASE_URL)


def analyze_stock_with_four_dimensions(symbol: str, stock_name: str, analysis_mode: str = "auto"):
    """
    使用四维数据进行双脑分析

    Args:
        symbol: 股票代码
        stock_name: 股票名称
        analysis_mode: 分析模式
            - "auto": 自动判断（信号>=3分触发Brain）
            - "fast": 强制使用Worker快速分析
            - "deep": 强制使用Brain深度分析

    Returns:
        分析报告文本
    """
    print(f"\n{'='*70}")
    print(f"开始分析: {stock_name} ({symbol})")
    print(f"{'='*70}\n")

    # ============ 步骤1：抓取四维数据 ============
    try:
        # 判断资产类型
        if symbol.startswith(("15", "16", "51", "56", "58")):
            asset_type = "etf"
        elif symbol.startswith(("000001", "399", "sh000", "sz399")):
            asset_type = "index"
        else:
            asset_type = "stock"

        # 整合数据抓取（包含原有数据+四维增强数据）
        data = fetch_integrated_data(symbol, stock_name, asset_type)

    except Exception as e:
        logging.error(f"❌ 数据抓取失败: {e}")
        return f"数据抓取失败: {str(e)}"

    # ============ 步骤2：信号评估（增强版）============
    use_deep_analysis = False
    trigger_reasons = []
    signal_score = 0

    if analysis_mode == "deep":
        use_deep_analysis = True
        trigger_reasons = ["用户指定深度分析模式"]
        signal_score = 999

    elif analysis_mode == "auto":
        # 使用增强版信号评估系统
        use_deep_analysis, trigger_reasons, signal_score = evaluate_enhanced_signals(data)

        if use_deep_analysis:
            print("🔔 触发深度分析！")
            print(f"   综合得分: {signal_score}分")
            print("   触发原因:")
            for reason in trigger_reasons:
                print(f"      - {reason}")
            print()

    # ============ 步骤3：执行分析 ============
    try:
        if use_deep_analysis:
            # 🧠 Brain层：深度分析（DeepSeek）
            print(f"🧠 启动Brain深度分析 (模型: {DEEPSEEK_MODEL})...\n")

            # 使用增强版prompt
            prompt = build_enhanced_prompt(data, analysis_type="brain")

            # 调用Brain层（deepseek-v3.2）
            analysis_result = brain.deep_analyze_stock(data)
            analysis_label = f"🧠 Brain 深度分析 (得分: {signal_score}分)"

        else:
            # 🤖 Worker层：快速分析（Qwen-Flash）
            print(f"🤖 Worker快速分析 (模型: {QWEN_MODEL})...\n")

            # 使用增强版prompt
            prompt = build_enhanced_prompt(data, analysis_type="worker")

            # 调用Worker层（qwen-flash）
            completion = qwen_client.chat.completions.create(
                model=QWEN_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            analysis_result = completion.choices[0].message.content
            analysis_label = "🤖 Worker 快速分析"

    except Exception as e:
        logging.error(f"❌ AI分析失败: {e}")
        return f"AI分析失败: {str(e)}"

    # ============ 步骤4：格式化输出 ============
    report = f"""
{'='*70}
{analysis_label}
{'='*70}

【核心数据摘要】
├─ 技术面: {data.get('tech_summary', 'N/A')}
├─ 资金面: {data.get('money_summary', 'N/A')}
├─ 估值面: {data.get('valuation_summary', 'N/A')}
├─ 业绩面: {data.get('performance_summary', 'N/A')}
└─ 情绪面: {data.get('sentiment_summary', 'N/A')}

{'='*70}
【AI分析报告】
{'='*70}

{analysis_result}

{'='*70}
"""

    return report


def batch_analyze_watchlist(watchlist: list, analysis_mode: str = "auto"):
    """
    批量分析自选股列表

    Args:
        watchlist: 自选股列表 [{"code": "002683", "name": "广东宏大"}, ...]
        analysis_mode: 分析模式
    """
    results = []

    for i, stock in enumerate(watchlist, 1):
        print(f"\n{'#'*70}")
        print(f"# 进度: {i}/{len(watchlist)}")
        print(f"{'#'*70}")

        try:
            report = analyze_stock_with_four_dimensions(
                stock['code'],
                stock['name'],
                analysis_mode
            )
            results.append({
                'code': stock['code'],
                'name': stock['name'],
                'report': report
            })

        except Exception as e:
            logging.error(f"分析失败 {stock['name']}: {e}")
            continue

    return results


# ==================== 测试代码 ====================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="四维数据双脑分析系统")
    parser.add_argument("--code", type=str, help="股票代码（如002683）")
    parser.add_argument("--name", type=str, help="股票名称（如广东宏大）")
    parser.add_argument(
        "--mode",
        type=str,
        default="auto",
        choices=["auto", "fast", "deep"],
        help="分析模式: auto(自动)/fast(快速)/deep(深度)"
    )

    args = parser.parse_args()

    # 测试用例
    if not args.code:
        print("未指定股票代码，使用测试用例...")
        test_stocks = [
            {"code": "002683", "name": "广东宏大"},
            {"code": "600519", "name": "贵州茅台"},
        ]
        batch_analyze_watchlist(test_stocks, analysis_mode="auto")
    else:
        # 单只股票分析
        report = analyze_stock_with_four_dimensions(
            args.code,
            args.name or "未知",
            args.mode
        )
        print(report)
