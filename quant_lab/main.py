import os
import sys
import time
import logging
from openai import OpenAI
from analyst_core import fetch_stock_data
from analyst_brain_v2 import AnalystBrainV2 as AnalystBrain  # V2: 量化增强版（阈值3分）
from stock_finder import smart_stock_query  # 智能股票查询
from datetime import datetime
import threading
import argparse
import markdown
from weasyprint import HTML, CSS

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

# === AI 模型配置 ===
# 支持多个AI模型供应商，可根据需要切换
MODEL_CONFIGS = {
    "qwen": {
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-flash",  # 可选: qwen-max, qwen-turbo, qwen-plus
        "description": "阿里通义千问 - 推荐用于金融分析"
    },
    "deepseek": {
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "deepseek-v3.2",
        "description": "DeepSeek V3.2 (via DashScope) - 推理能力强，适合金融分析"
    },
    "deepseek-official": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "description": "DeepSeek 官方API - 需要单独的API Key"
    },
    "glm": {
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "glm-4.6",
        "description": "智谱GLM-4 - 原默认模型"
    },
}

# 选择要使用的模型 (可选: "qwen", "deepseek", "deepseek-official", "glm")
ACTIVE_MODEL = "qwen"

# 获取激活模型的配置
active_config = MODEL_CONFIGS[ACTIVE_MODEL]
API_KEY = os.getenv(active_config["api_key_env"], "sk-你的Key")
BASE_URL = active_config["base_url"]
DEFAULT_MODEL = active_config["model"]

# === 自选股列表 ===
# My Watchlist
MY_WATCHLIST = [
    # --- 深市 ---
    {"code": "002028", "name": "思源电气"},
    {"code": "002475", "name": "立讯精密"},
    {"code": "002920", "name": "德赛西威"},
    {"code": "002683", "name": "广东宏大"},
    {"code": "003816", "name": "中国广核"},
    {"code": "300308", "name": "中际旭创"},
    # --- 沪市 ---
    {"code": "600030", "name": "中信证券"},
    {"code": "600036", "name": "招商银行"},
    {"code": "600276", "name": "恒瑞医药"},
    {"code": "600363", "name": "联创光电"},
    {"code": "600519", "name": "贵州茅台"},
    {"code": "688122", "name": "西部超导"},
    # --- ETF ---
    {"code": "159206", "name": "卫星ETF"},
    {"code": "159857", "name": "光伏ETF"},
    {"code": "164906", "name": "中概互联网LOF"},
]

# Dad's Watchlist
DAD_WATCHLIST = [
    # --- 科技/电子/通信 ---
    {"code": "000988", "name": "华工科技"},  # 激光技术龙头
    {"code": "600990", "name": "四创电子"},  # 雷达第一股
    {"code": "300348", "name": "长亮科技"},  # 金融科技
    {"code": "000063", "name": "中兴通讯"},  # 5G/通信龙头
    {"code": "601727", "name": "上海电气"},  # 装备制造龙头
    # --- 消费/医疗/其他 ---
    {"code": "600729", "name": "重庆百货"},  # 零售/高分红
    {"code": "300753", "name": "爱朋医疗"},  # 疼痛管理/医疗器械
    {"code": "002838", "name": "道恩股份"},  # 改性塑料/弹性体
    {"code": "002086", "name": "东方海洋"},  # 海洋经济
    # --- 特殊关注 (ST) ---

    {"code": "002647", "name": "ST仁东"},    # 第三方支付 (注意风险)
]

# Erin's Watchlist
ERIN_WATCHLIST = [
    {"code": "002683", "name": "广东宏大"},
    {"code": "601088", "name": "中国神华"},
    {"code": "600901", "name": "江苏金租"},
    {"code": "600690", "name": "海尔智家"},
]

# Watchlist 映射
WATCHLIST_MAP = {
    "my": MY_WATCHLIST,
    "dad": DAD_WATCHLIST,
    "erin": ERIN_WATCHLIST,
}

def get_user_choice_with_timeout(timeout=30):
    """
    获取用户选择的 watchlist，带超时功能

    Args:
        timeout: 超时时间（秒），默认30秒

    Returns:
        选择的 watchlist 名称，超时则返回 'my'
    """
    user_input = [None]  # 使用列表以便在线程中修改

    def get_input():
        try:
            user_input[0] = input().strip().lower()
        except:
            pass

    print("\n" + "="*60)
    print("📋 请选择要分析的 Watchlist：")
    print("="*60)
    print("  [1] my    - My Watchlist      (15 只股票)")
    print("  [2] dad   - Dad's Watchlist   (10 只股票)")
    print("  [3] erin  - Erin's Watchlist  (4 只股票)")
    print("="*60)
    print(f"⏱️  请在 {timeout} 秒内输入数字或名称 (默认: my): ", end="", flush=True)

    # 启动输入线程
    input_thread = threading.Thread(target=get_input)
    input_thread.daemon = True
    input_thread.start()

    # 等待输入或超时
    input_thread.join(timeout)

    if user_input[0] is None:
        print(f"\n⏰ 超时未输入，使用默认选项: my")
        return "my"

    # 处理用户输入
    choice = user_input[0]

    # 支持数字或名称
    if choice in ["1", "my"]:
        return "my"
    elif choice in ["2", "dad"]:
        return "dad"
    elif choice in ["3", "erin"]:
        return "erin"
    else:
        print(f"⚠️  无效输入 '{choice}'，使用默认选项: my")
        return "my"

def call_ai(prompt, model=None):
    """
    调用AI模型进行分析

    Args:
        prompt: 提示词
        model: 指定模型（可选），不指定则使用默认模型
    """
    if model is None:
        model = DEFAULT_MODEL

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=30.0)
    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return completion.choices[0].message.content
        except Exception as e:
            logging.warning(f"AI调用失败 (尝试 {attempt + 1}/3): {type(e).__name__}")
            time.sleep(1)
    return "AI 响应超时"

def generate_pdf_from_markdown(md_filepath):
    """
    将 Markdown 报告转换为 PDF

    Args:
        md_filepath: Markdown 文件路径

    Returns:
        PDF 文件路径，失败则返回 None
    """
    try:
        # 读取 Markdown 文件
        with open(md_filepath, 'r', encoding='utf-8') as f:
            md_content = f.read()

        # 转换 Markdown 为 HTML
        html_content = markdown.markdown(
            md_content,
            extensions=['extra', 'tables', 'nl2br']
        )

        # 添加 CSS 样式（支持中文）
        css_style = """
        @page {
            size: A4;
            margin: 2cm;
        }
        body {
            font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            font-size: 24pt;
        }
        h2 {
            color: #34495e;
            border-bottom: 2px solid #95a5a6;
            padding-bottom: 5px;
            margin-top: 20px;
            font-size: 18pt;
        }
        h3 {
            color: #555;
            font-size: 14pt;
        }
        blockquote {
            background-color: #f8f9fa;
            border-left: 4px solid #3498db;
            padding: 10px 15px;
            margin: 15px 0;
        }
        code {
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: "Monaco", "Courier New", monospace;
        }
        strong {
            color: #e74c3c;
            font-weight: bold;
        }
        ul, ol {
            margin-left: 20px;
        }
        hr {
            border: none;
            border-top: 1px solid #ddd;
            margin: 20px 0;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #3498db;
            color: white;
        }
        """

        # 完整 HTML 文档
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{css_style}</style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        # 生成 PDF 文件路径
        pdf_filepath = md_filepath.replace('.md', '.pdf')

        # 转换为 PDF
        HTML(string=full_html).write_pdf(pdf_filepath)

        logging.info(f"✅ PDF报告已生成: {pdf_filepath}")
        return pdf_filepath

    except Exception as e:
        logging.error(f"❌ PDF生成失败: {e}")
        return None

def run_single_stock_mode(stock_code, stock_name=None, analysis_mode="auto"):
    """
    运行单个股票查询模式

    Args:
        stock_code: 股票代码或名称（支持智能识别）
        stock_name: 股票名称（可选）
        analysis_mode: 分析模式 ('fast' | 'deep' | 'auto')
    """
    # 🎯 智能识别：如果用户输入的是名称或模糊关键词，自动查找代码
    if stock_name is None or not stock_code.isdigit():
        # 尝试智能查询
        resolved_code, resolved_name = smart_stock_query(stock_code)

        if resolved_code is None:
            # 查询失败（可能是多个匹配或未找到）
            print("\n💡 建议：")
            print("  1. 使用完整的股票代码（如：600519）")
            print("  2. 使用完整的股票名称（如：贵州茅台）")
            print("  3. 如果有多个匹配，请使用股票代码查询")
            return

        # 查询成功，更新代码和名称
        stock_code = resolved_code
        stock_name = resolved_name

    # 如果没有提供名称，使用代码作为名称
    if stock_name is None:
        stock_name = stock_code

    # 初始化 Brain 层
    brain = None
    if analysis_mode in ['deep', 'auto']:
        # 可选模型：deepseek-v3.2（深度推理，慢）| qwen-max（快速，稳定）
        brain = AnalystBrain(model="deepseek-v3.2")  # 如遇超时可改为 qwen-max

    print(f"\n{'='*60}")
    print(f"🔍 单股查询模式")
    print(f"📅 日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 标的: {stock_name} ({stock_code})")
    print(f"⚙️  分析模式: {analysis_mode.upper()}")
    print(f"{'='*60}\n")

    # 获取数据
    try:
        data = fetch_stock_data(stock_code, stock_name)
    except Exception as e:
        logging.error(f"❌ 数据获取失败: {e}")
        return

    # 构建 Prompt（复用监控模式的逻辑）
    if data['type'] == 'index':
        prompt = f"""
        你是一位宏观策略师。请点评大盘指数【{stock_name}】：
        - 趋势位置: {data['tech_summary']}

        要求：基于技术面趋势，判断当前大盘环境是【偏暖/震荡/偏冷】，并给出一句话操作建议。
        """
    elif data['type'] == 'etf':
        prompt = f"""
        你是一位ETF交易员。请点评行业ETF【{stock_name}】：
        - 赛道趋势: {data['tech_summary']}

        要求：判断该行业赛道是【强势/弱势】，并给出一句话建议。
        """
    else:
        news_prompt = f"- 舆情: {data['news_context']}\n  (数据源: {data.get('news_source', '未知')})"
        prompt = f"""
        你是一位专业的股票分析师。请对个股【{stock_name}】进行客观、平衡的点评：

        **数据概览**：
        - 资金面: {data['money_summary']}
        - 技术面: {data['tech_summary']}
        {news_prompt}

        **分析要求**：
        1. 同时指出积极因素和风险因素，避免单方面倾向
        2. 给出明确的**评级**（看多/中性/看空）和**核心理由**（2-3句话）
        3. 操作建议要具体且实用

        **注意**：✅表示资金流入（利好），❌表示资金流出（利空）
        """

    # 判断是否使用深度分析
    use_deep_analysis = False
    trigger_reasons = []
    signal_score = 0

    if analysis_mode == 'deep':
        use_deep_analysis = True
        trigger_reasons = ["用户指定深度分析模式"]
    elif analysis_mode == 'auto' and brain:
        use_deep_analysis, trigger_reasons, signal_score = brain.evaluate_signal_strength_v2(data)
        if use_deep_analysis:
            logging.info(f"✅ 触发深度分析: {signal_score}分 - {', '.join(trigger_reasons)}")

    # 执行分析
    try:
        if use_deep_analysis and brain:
            print(f"🧠 触发深度分析 (评分{signal_score}分): {', '.join(trigger_reasons)}\n")
            summary = brain.deep_analyze_stock(data)
            analysis_label = "🧠 Brain 深度分析"
        else:
            summary = call_ai(prompt)
            analysis_label = f"🤖 Worker 快速分析 [{data['type'].upper()}]"

        # 输出到控制台
        print(f"\n{'='*60}")
        print(f"{analysis_label}:")
        print(f"{'='*60}\n")
        print(f"**资金面**: {data['money_summary']}")
        print(f"**技术面**: {data['tech_summary']}")
        print(f"**舆情**: {data['news_summary']}")
        if data.get('news_source') and data['news_source'] != "无":
            print(f"  - 新闻来源: {data['news_source']}")
        print(f"\n{summary}\n")
        print(f"{'='*60}\n")

        # 保存到报告文件
        now = datetime.now()
        date_folder = now.strftime('%y%m%d')
        script_dir = os.path.dirname(os.path.abspath(__file__))
        report_dir = os.path.join(script_dir, "Report", date_folder)
        os.makedirs(report_dir, exist_ok=True)

        # 文件名：日期_时间_股票名称_模式.md（更清晰）
        date_prefix = now.strftime('%y%m%d')
        time_prefix = now.strftime('%H%M%S')
        mode_suffix = {"fast": "Fast", "deep": "Deep", "auto": "Auto"}.get(analysis_mode, "")
        filename = os.path.join(report_dir, f"{date_prefix}_{time_prefix}_{stock_name}_{mode_suffix}.md")

        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# 个股分析报告: {stock_name} ({stock_code})\n\n")
            f.write(f"> 生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"> 分析模式: {analysis_label}\n\n")
            if use_deep_analysis:
                f.write(f"> 触发条件: 评分{signal_score}分 - {', '.join(trigger_reasons)}\n\n")
            f.write(f"## 数据概览\n\n")
            f.write(f"- **资金面**: {data['money_summary']}\n")
            f.write(f"- **技术面**: {data['tech_summary']}\n")
            f.write(f"- **舆情**: {data['news_summary']}\n")
            if data.get('news_source') and data['news_source'] != "无":
                f.write(f"  - 新闻来源: {data['news_source']}\n")
            f.write(f"\n## AI分析\n\n{summary}\n")

        print(f"✅ Markdown报告已保存: {filename}")

        # 同时生成 PDF 报告
        pdf_file = generate_pdf_from_markdown(filename)
        if pdf_file:
            print(f"✅ PDF报告已保存: {pdf_file}\n")
        else:
            print(f"⚠️  PDF生成失败，但Markdown报告已保存\n")

    except Exception as e:
        logging.error(f"❌ AI分析失败: {e}")

def run_monitor_mode(watchlist_name="my", analysis_mode="fast"):
    """
    运行监控模式

    Args:
        watchlist_name: watchlist 名称 ('my', 'dad', 'erin')
        analysis_mode: 分析模式 ('fast' 快速模式 | 'deep' 深度模式 | 'auto' 智能触发)
    """
    watchlist = WATCHLIST_MAP.get(watchlist_name, MY_WATCHLIST)
    watchlist_display = {
        "my": "My Watchlist",
        "dad": "Dad's Watchlist",
        "erin": "Erin's Watchlist"
    }.get(watchlist_name, "Unknown Watchlist")

    # 初始化 Brain 层（如果需要深度分析）
    brain = None
    if analysis_mode in ['deep', 'auto']:
        # 可选模型：deepseek-v3.2（深度推理，慢）| qwen-max（快速，稳定）
        brain = AnalystBrain(model="deepseek-v3.2")  # 如遇超时可改为 qwen-max
        logging.info("🧠 Brain 层已激活（深度分析模式）")

    analysis_mode_display = {
        "fast": "快速模式 (Worker Layer)",
        "deep": "深度模式 (Worker + Brain)",
        "auto": "智能模式 (自动触发 Brain)"
    }.get(analysis_mode, "未知模式")

    print("\n🛡️ 启动【多策略监控模式】...")
    print(f"📅 日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🤖 Worker模型: {ACTIVE_MODEL.upper()} ({DEFAULT_MODEL}) - {active_config['description']}")
    if brain:
        print(f"🧠 Brain模型: {brain.model}")
    print(f"⚙️  分析模式: {analysis_mode_display}")
    print(f"📋 选择列表: {watchlist_display}")
    print(f"📊 监控标的: {len(watchlist)} 只\n")

    report_content = f"# 每日投资晨报 ({datetime.now().strftime('%Y-%m-%d')})\n\n"
    report_content += f"> 本报告由AI自动生成，仅供参考，不构成投资建议\n\n"
    report_content += f"> **Watchlist**: {watchlist_display}\n\n"
    report_content += f"> **分析模式**: {analysis_mode_display}\n\n"

    success_count = 0
    fail_count = 0
    deep_analysis_count = 0  # 使用深度分析的股票数

    for idx, stock in enumerate(watchlist, 1):
        print(f"\n{'='*50}")
        print(f"[{idx}/{len(watchlist)}] 扫描: {stock['name']} ({stock['code']})")
        print('='*50)

        # 1. 获取数据
        try:
            data = fetch_stock_data(stock['code'], stock['name'])
        except Exception as e:
            logging.error(f"数据获取失败: {e}")
            fail_count += 1
            continue

        # 2. 🎯 根据资产类型，生成不同的 Prompt
        if data['type'] == 'index':
            # === 指数策略 ===
            prompt = f"""
            你是一位宏观策略师。请点评大盘指数【{stock['name']}】：
            - 趋势位置: {data['tech_summary']} (重点关注是否站上年线/20日线)
            - 资金/舆情: 指数级资金无法精确统计，请忽略个股资金。

            要求：基于技术面趋势，判断当前大盘环境是【偏暖/震荡/偏冷】，并给出一句话操作建议（如：轻仓参与/控制仓位）。
            """
        elif data['type'] == 'etf':
            # === ETF 策略 ===
            prompt = f"""
            你是一位ETF交易员。请点评行业ETF【{stock['name']}】：
            - 赛道趋势: {data['tech_summary']}
            - 资金面: ETF不看个股主力资金，重点看K线趋势强度。

            要求：判断该行业赛道是【强势/弱势】，并给出一句话建议（如：右侧交易/左侧潜伏）。
            """
        else:
            # === 个股策略 (平衡版，避免过度悲观) ===
            news_prompt = f"- 舆情: {data['news_context']}\n  (数据源: {data.get('news_source', '未知')})"

            prompt = f"""
            你是一位专业的股票分析师。请对个股【{stock['name']}】进行客观、平衡的点评：

            **数据概览**：
            - 资金面: {data['money_summary']}
            - 技术面: {data['tech_summary']}
            {news_prompt}

            **分析要求**：
            1. **同时指出积极因素和风险因素**，避免单方面倾向
            2. 资金、技术、舆情三个维度权重相当，综合判断
            3. 给出明确的**评级**（看多/中性/看空）和**核心理由**（2-3句话）
            4. 操作建议要具体且实用（如：逢低关注、短线谨慎、持仓观察等）

            **注意事项**：
            - 如果舆情来自"全网搜索"，需判断新闻的时效性和相关性
            - ✅表示资金流入（利好），❌表示资金流出（利空）
            - 分析时保持客观中立，既不过度乐观也不过度悲观
            """

        try:
            # 🎯 判断是否需要深度分析
            use_deep_analysis = False
            trigger_reasons = []

            if analysis_mode == 'deep':
                # 强制深度分析模式
                use_deep_analysis = True
                trigger_reasons = ["用户指定深度分析模式"]
            elif analysis_mode == 'auto' and brain:
                # 智能触发模式：评估信号强度（V2返回3个值）
                use_deep_analysis, trigger_reasons, signal_score = brain.evaluate_signal_strength_v2(data)
                if use_deep_analysis:
                    logging.info(f"✅ 触发深度分析: {signal_score}分 - {', '.join(trigger_reasons)}")

            # 执行分析
            if use_deep_analysis and brain:
                # 使用 Brain 层深度分析
                deep_analysis_count += 1
                print(f"🧠 触发深度分析: {', '.join(trigger_reasons)}")
                summary = brain.deep_analyze_stock(data)
                analysis_label = "🧠 Brain 深度分析"
            else:
                # 使用 Worker 层快速分析
                summary = call_ai(prompt)
                analysis_label = f"🤖 Worker 快速分析 [{data['type'].upper()}]"

            print(f"\n{analysis_label}:")
            print(f"{summary}\n")

            # 写入报告
            report_content += f"## {stock['name']} ({stock['code']})\n\n"
            report_content += f"**资产类型**: {data['type'].upper()}\n\n"
            if use_deep_analysis:
                if 'signal_score' in locals():
                    report_content += f"**分析模式**: 🧠 深度分析 (评分{signal_score}分: {', '.join(trigger_reasons)})\n\n"
                else:
                    report_content += f"**分析模式**: 🧠 深度分析 ({', '.join(trigger_reasons)})\n\n"
            report_content += f"- **趋势**: {data['tech_summary']}\n"
            report_content += f"- **资金**: {data['money_summary']}\n"
            report_content += f"- **舆情**: {data['news_summary']}\n"
            if data.get('news_source') and data['news_source'] != "无":
                report_content += f"  - 新闻来源: {data['news_source']}\n"
            report_content += f"\n**AI点评**:\n\n{summary}\n\n"
            report_content += "---\n\n"

            success_count += 1
        except Exception as e:
            logging.error(f"AI分析失败 [{stock['name']}]: {e}")
            fail_count += 1

        time.sleep(0.5)

    # 添加报告统计
    report_content += f"\n## 报告统计\n\n"
    report_content += f"- 成功分析: {success_count} 只\n"
    report_content += f"- 失败: {fail_count} 只\n"
    if brain:
        report_content += f"- 深度分析: {deep_analysis_count} 只 (🧠 Brain)\n"
        report_content += f"- 快速分析: {success_count - deep_analysis_count} 只 (🤖 Worker)\n"
    report_content += f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

    # 保存到 quant_lab/Report/YYMMDD/ 目录
    now = datetime.now()
    date_folder = now.strftime('%y%m%d')  # 251218
    # 获取脚本所在目录，确保报告保存在正确位置
    script_dir = os.path.dirname(os.path.abspath(__file__))
    report_base = os.path.join(script_dir, "Report")
    report_dir = os.path.join(report_base, date_folder)
    os.makedirs(report_dir, exist_ok=True)

    # 文件名：日期_时间_列表名_模式.md（更清晰）
    date_prefix = now.strftime('%y%m%d')  # 251218
    time_prefix = now.strftime('%H%M%S')  # 151046
    mode_suffix = {"fast": "Fast", "deep": "Deep", "auto": "Auto"}.get(analysis_mode, "")
    list_name_map = {"my": "My列表", "dad": "Dad列表", "erin": "Erin列表"}
    list_display = list_name_map.get(watchlist_name, watchlist_name)
    filename = os.path.join(report_dir, f"{date_prefix}_{time_prefix}_{list_display}_{mode_suffix}.md")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"\n{'='*50}")
    print(f"✅ Markdown报告已生成: {filename}")

    # 同时生成 PDF 报告
    pdf_file = generate_pdf_from_markdown(filename)
    if pdf_file:
        print(f"✅ PDF报告已生成: {pdf_file}")
    else:
        print(f"⚠️  PDF生成失败，但Markdown报告已保存")

    print(f"📊 统计: 成功 {success_count} | 失败 {fail_count}")
    if brain:
        print(f"🧠 深度分析: {deep_analysis_count} 只 | 🤖 快速分析: {success_count - deep_analysis_count} 只")
    print(f"{'='*50}\n")

# ... (调研模式和主入口保持不变) ...
if __name__ == "__main__":
    # 添加命令行参数支持
    parser = argparse.ArgumentParser(description='Quant Lab - AI量化分析系统 (支持双层架构)')
    parser.add_argument(
        '--list',
        choices=['my', 'dad', 'erin'],
        help='指定要分析的 watchlist (my/dad/erin)，不指定则交互式选择'
    )
    parser.add_argument(
        '--stock',
        metavar='CODE[:NAME]',
        help='单股查询模式，格式: 股票代码[:股票名称]，如 "600519" 或 "600519:贵州茅台"'
    )
    parser.add_argument(
        '--no-interaction',
        action='store_true',
        help='非交互模式，直接使用默认 watchlist (my)，适合 cron 任务'
    )
    parser.add_argument(
        '--analysis-mode',
        choices=['fast', 'deep', 'auto'],
        default='fast',
        help='分析模式：fast=快速(仅Worker) | deep=深度(Worker+Brain) | auto=智能触发 (默认: fast)'
    )

    args = parser.parse_args()

    # === 单股查询模式 ===
    if args.stock:
        # 解析股票代码和名称
        if ':' in args.stock:
            stock_code, stock_name = args.stock.split(':', 1)
        else:
            stock_code = args.stock
            stock_name = None

        print(f"🔍 启动单股查询模式: {args.stock}")
        run_single_stock_mode(stock_code.strip(), stock_name.strip() if stock_name else None, args.analysis_mode)
        sys.exit(0)

    # === Watchlist 监控模式 ===
    # 确定使用哪个 watchlist
    if args.no_interaction:
        # 非交互模式：直接使用 my（或通过 --list 指定）
        selected_watchlist = args.list if args.list else 'my'
        print(f"🤖 非交互模式：使用 {selected_watchlist.upper()} Watchlist")
    elif args.list:
        # 命令行指定了 list，直接使用
        selected_watchlist = args.list
        print(f"📋 命令行指定：使用 {selected_watchlist.upper()} Watchlist")
    else:
        # 交互模式：询问用户选择（带30秒超时）
        selected_watchlist = get_user_choice_with_timeout(timeout=30)

    # 运行监控模式
    run_monitor_mode(watchlist_name=selected_watchlist, analysis_mode=args.analysis_mode)