import os
import sys
import time
import logging
import json
import threading
import argparse
import markdown
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import select
import re
from typing import List, Tuple, Optional

# 引入统一 AI 配置与网络优化
import ai_config
ai_config.init_global_network()

# === 使用带缓存的四维数据抓取（性能提升100倍+） ===
from analyst_integration import fetch_stock_data, build_enhanced_prompt
from analyst_brain import AnalystBrain
from stock_finder import smart_stock_query, StockFinder
from valuation_analyzer import ValuationAnalyzer
from md2pdf_tool import md_to_pdf

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

def load_watchlists():
    """
    从 watchlists.json 配置文件加载自选股列表
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, "watchlists.json")

    # 默认列表
    default_watchlists = {
        "my": [
            {"code": "002683", "name": "广东宏大"},
            {"code": "002179", "name": "中航光电"},
            {"code": "002049", "name": "紫光国微"},
            {"code": "688122", "name": "西部超导"},
            {"code": "603508", "name": "思维列控"},
            {"code": "600150", "name": "中国船舶"},
            {"code": "002267", "name": "陕天然气"},
            {"code": "002056", "name": "横店东磁"},
            {"code": "399050", "name": "中证互联网"},
            {"code": "399441", "name": "国证生物医药"},
            {"code": "399971", "name": "中证光伏"},
            {"code": "399976", "name": "中证新能源汽车"},
            {"code": "000932", "name": "中证消费"}
        ],
        "dad": [
            {"code": "000988", "name": "华工科技"},
            {"code": "600990", "name": "四创电子"},
            {"code": "300348", "name": "长亮科技"},
            {"code": "000063", "name": "中兴通讯"},
            {"code": "601727", "name": "上海电气"},
            {"code": "600729", "name": "重庆百货"},
            {"code": "300753", "name": "爱朋医疗"},
            {"code": "002838", "name": "道恩股份"},
            {"code": "002086", "name": "东方海洋"},
            {"code": "002647", "name": "ST仁东"}
        ],
        "erin": [
            {"code": "300059", "name": "东方财富"},
            {"code": "601088", "name": "中国神华"},
            {"code": "600901", "name": "江苏金租"},
            {"code": "600690", "name": "海尔智家"},
            {"code": "002475", "name": "立讯精密"},
            {"code": "688122", "name": "西部超导"}
        ]
    }

    try:
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            watchlists = {}
            for key in ['my', 'dad', 'erin']:
                if key in config and 'stocks' in config[key]:
                    watchlists[key] = [
                        {"code": stock["code"], "name": stock["name"]}
                        for stock in config[key]["stocks"]
                    ]
                else:
                    watchlists[key] = default_watchlists[key]

            logging.info(f"✅ 自选股配置已从 watchlists.json 加载")
            return watchlists
    except Exception as e:
        logging.warning(f"⚠️ 配置文件加载失败，使用默认列表: {e}")

    return default_watchlists

# 加载自选股列表
_watchlists = load_watchlists()
MY_WATCHLIST = _watchlists["my"]
DAD_WATCHLIST = _watchlists["dad"]
ERIN_WATCHLIST = _watchlists["erin"]

# Watchlist 映射
WATCHLIST_MAP = {
    "my": MY_WATCHLIST,
    "dad": DAD_WATCHLIST,
    "erin": ERIN_WATCHLIST,
}

def get_user_choice_with_timeout(timeout=30):
    user_input = [None]
    def get_input():
        try: user_input[0] = input().strip().lower()
        except: pass

    print("\n" + "="*60)
    print("📋 请选择要分析的 Watchlist：")
    print("="*60)
    print(f"  [1] my    - My Watchlist      ({len(MY_WATCHLIST)} 只股票)")
    print(f"  [2] dad   - Dad's Watchlist   ({len(DAD_WATCHLIST)} 只股票)")
    print(f"  [3] erin  - Erin's Watchlist  ({len(ERIN_WATCHLIST)} 只股票)")
    print("="*60)
    print(f"⏱️  请在 {timeout} 秒内输入数字或名称 (默认: my): ", end="", flush=True)

    input_thread = threading.Thread(target=get_input)
    input_thread.daemon = True
    input_thread.start()
    input_thread.join(timeout)

    choice = user_input[0] or "my"
    if choice in ["1", "my"]: return "my"
    elif choice in ["2", "dad"]: return "dad"
    elif choice in ["3", "erin"]: return "erin"
    return "my"

def ask_user_with_timeout(prompt_text, timeout=5, default='n'):
    print(prompt_text, end='', flush=True)
    if sys.platform != 'win32':
        import select
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if rlist:
            response = sys.stdin.readline().strip().lower()
            return response if response else default
        else:
            action = "自动开始" if default == 'y' else "自动跳过"
            print(f"⏱️  {timeout}秒内未响应，{action}")
            return default
    else:
        try:
            # Windows 下暂不支持 select.select 控制标准输入，这里简化处理
            response = input().strip().lower()
            return response if response else default
        except: return default

def call_ai(prompt, model=None):
    current_model = model if model else ai_config.get_primary_model_name()
    backup_model = ai_config.get_backup_model_name()
    attempts_plan = [(current_model, 1), (current_model, 2), (backup_model, 1), (backup_model, 2)]
    
    client = ai_config.create_openai_client(timeout=180.0)
    last_error = None
    
    for model_name, attempt_idx in attempts_plan:
        try:
            logging.info(f"正在调用 {model_name} (尝试 {attempt_idx})...")
            completion = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            result = completion.choices[0].message.content
            logging.info(f"✅ AI调用成功 (模型: {model_name})")
            return result
        except Exception as e:
            last_error = e
            logging.warning(f"AI调用失败 ({model_name} 尝试 {attempt_idx}): {type(e).__name__}")
            time.sleep(1)

    return f"⚠️ AI 分析服务暂时不可用\n\n错误详情: {str(last_error)}"


def run_global_stock_mode(ticker):
    """全球股票分析模式 —— 通过 OpenBB 获取数据，AI 生成分析报告"""
    from analyst_openbb import OpenBBAnalyst

    ticker = ticker.upper()
    print(f"\n{'='*60}\n🌍 全球股票分析模式\n📅 日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🎯 标的: {ticker}\n{'='*60}\n")

    analyst = OpenBBAnalyst(cache_expire_minutes=30)

    # 1. 获取全球宏观背景
    print("📊 获取全球宏观数据...")
    macro = analyst.fetch_global_macro()

    # 2. 获取个股数据
    print(f"📈 获取 {ticker} 行情与技术指标...")
    stock_data = analyst.fetch_stock_analysis(ticker)

    stock_name = stock_data.get('name', ticker)
    print(f"✓ 标的: {stock_name}")
    print(f"✓ 技术面: {stock_data.get('tech_summary', 'N/A')}")
    print(f"✓ 基本面: {stock_data.get('fundamental_summary', 'N/A')}")

    # 3. 构建 prompt
    prompt = analyst.build_global_prompt({**stock_data, 'macro': macro or {}})

    # 4. 调用 AI 分析
    print(f"\n🤖 正在调用 AI 分析...\n")
    try:
        summary = call_ai(prompt)
        analysis_label = "🌍 Global 全球分析"

        print(f"\n{'='*60}\n{analysis_label}:\n{'='*60}\n")
        print(f"**技术面**: {stock_data.get('tech_summary', 'N/A')}")
        print(f"**基本面**: {stock_data.get('fundamental_summary', 'N/A')}")
        if macro:
            macro_parts = []
            if macro.get('us10y_yield') != 'N/A':
                macro_parts.append(f"美债10Y: {macro['us10y_yield']}%")
            if macro.get('dxy_index') != 'N/A':
                macro_parts.append(f"DXY: {macro['dxy_index']}")
            if macro.get('hsi_index') != 'N/A':
                macro_parts.append(f"恒指: {macro['hsi_index']}")
            print(f"**宏观面**: {' | '.join(macro_parts)}")
        print(f"\n{summary}\n{'='*60}\n")

        # 5. 保存报告
        now = datetime.now()
        report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Report", now.strftime('%y%m%d'))
        os.makedirs(report_dir, exist_ok=True)
        filename = os.path.join(report_dir, f"{now.strftime('%H%M%S')}_{ticker}_global.md")

        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# {stock_name}（{ticker}）全球市场分析\n\n")
            f.write(f"> 生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"> 分析模式: {analysis_label}\n\n")
            f.write(f"## 数据概览\n\n")
            f.write(f"- **技术面**: {stock_data.get('tech_summary', 'N/A')}\n")
            f.write(f"- **基本面**: {stock_data.get('fundamental_summary', 'N/A')}\n")
            if macro:
                f.write(f"- **宏观面**: 美债10Y {macro.get('us10y_yield', 'N/A')}% | DXY {macro.get('dxy_index', 'N/A')} | 恒指 {macro.get('hsi_index', 'N/A')}\n")
            f.write(f"\n## AI分析\n\n{summary}\n")

        print(f"✅ Markdown报告已保存: {filename}")
        pdf_path = filename.replace('.md', '.pdf')
        if md_to_pdf(filename, pdf_path):
            print(f"✅ PDF报告已生成: {pdf_path}")
    except Exception as e:
        logging.error(f"❌ AI分析失败: {e}")


def run_single_stock_mode(stock_code, stock_name=None, analysis_mode="auto", prompt_version="professional"):
    market = 'A'
    if stock_name is None or not stock_code.isdigit():
        resolved_code, resolved_name, resolved_market = smart_stock_query(stock_code)
        if resolved_code is None: return
        stock_code, stock_name, market = resolved_code, resolved_name, resolved_market or 'A'

    if market == 'HK':
        print(f"\n⚠️  港股 {stock_code} ({stock_name}) 暂不支持完整AI分析")
        va = ValuationAnalyzer()
        metrics, summary = va.analyze(stock_code, stock_name, market='HK')
        print(summary)
        return

    stock_name = stock_name or stock_code
    brain = AnalystBrain(model=ai_config.get_primary_model_name(), prompt_version=prompt_version) if analysis_mode in ['deep', 'auto'] else None

    print(f"\n{'='*60}\n🔍 单股查询模式\n📅 日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🎯 标的: {stock_name} ({stock_code})\n⚙️  分析模式: {analysis_mode.upper()}\n{'='*60}\n")

    try:
        data = fetch_stock_data(stock_code, stock_name)
    except Exception as e:
        logging.error(f"❌ 数据获取失败: {e}"); return

    # 构建分析提示词
    if data['type'] == 'index':
        prompt = f"你是一位宏观策略师。请点评大盘指数【{stock_name}】：\n- 趋势位置: {data['tech_summary']}\n要求判断环境并给出一句话建议。"
    elif data['type'] == 'etf':
        prompt = f"你是一位ETF交易员。请点评行业ETF【{stock_name}】：\n- 赛道趋势: {data['tech_summary']}\n要求判断强弱并给出一句话建议。"
    else:
        prompt = build_enhanced_prompt(data, analysis_type="worker")

    use_deep_analysis, trigger_reasons, signal_score = (True, ["用户指定深度分析"], 0) if analysis_mode == 'deep' else (brain.evaluate_signal_strength_v2(data) if (analysis_mode == 'auto' and brain) else (False, [], 0))

    try:
        if use_deep_analysis and brain:
            print(f"🧠 触发深度分析 (评分{signal_score}分): {', '.join(trigger_reasons)}")
            print(f"⏳ AI深度分析中，请稍候...\n")
            summary = brain.deep_analyze_stock(data)
            analysis_label = "🧠 Brain 深度分析"
        else:
            summary = call_ai(prompt)
            analysis_label = f"🤖 Worker 快速分析 [{data['type'].upper()}]"

        print(f"\n{'='*60}\n{analysis_label}:\n{'='*60}\n**资金面**: {data['money_summary']}\n**技术面**: {data['tech_summary']}\n**舆情**: {data['news_summary']}\n\n{summary}\n{'='*60}\n")

        # 保存 Markdown 报告
        now = datetime.now()
        report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Report", now.strftime('%y%m%d'))
        os.makedirs(report_dir, exist_ok=True)
        filename = os.path.join(report_dir, f"{now.strftime('%H%M%S')}_{stock_name}_{analysis_mode}.md")

        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# {stock_name}（{stock_code}）投资分析\n\n> 生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n> 分析模式: {analysis_label}\n\n## 数据概览\n\n- **资金面**: {data['money_summary']}\n- **技术面**: {data['tech_summary']}\n- **舆情**: {data['news_summary']}\n\n## AI分析\n\n{summary}\n")

        print(f"✅ Markdown报告已保存: {filename}")
        pdf_path = filename.replace('.md', '.pdf')
        if md_to_pdf(filename, pdf_path):
            print(f"✅ PDF报告已生成: {pdf_path}")
    except Exception as e:
        logging.error(f"❌ AI分析失败: {e}")

def run_monitor_mode(watchlist_name="my", analysis_mode="fast", prompt_version="professional"):
    watchlist = WATCHLIST_MAP.get(watchlist_name, MY_WATCHLIST)
    brain = AnalystBrain(model=ai_config.get_primary_model_name(), prompt_version=prompt_version) if analysis_mode in ['deep', 'auto'] else None

    print(f"\n🛡️ 启动【多策略监控模式】...\n📅 日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n⚙️  分析模式: {analysis_mode}\n📊 监控标的: {len(watchlist)} 只\n")

    now = datetime.now()
    report_content = f"# 每日投资报告（{now.strftime('%Y-%m-%d')}）\n\n> 本报告由AI自动生成，仅供参考。\n\n"
    
    stock_data_map = {}
    total = len(watchlist)
    print(f"📊 数据获取中 (共{total}只)...")
    fetch_start = time.time()
    fetch_lock = threading.Lock()
    fetch_done = [0]

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fetch_stock_data, s['code'], s['name']): s for s in watchlist}
        for future in as_completed(futures):
            stock = futures[future]
            try:
                stock_data_map[stock['code']] = (stock, future.result())
                with fetch_lock:
                    fetch_done[0] += 1
                    elapsed = time.time() - fetch_start
                    print(f"  [{fetch_done[0]}/{total}] ✓ {stock['name']}({stock['code']}) 就绪 ({elapsed:.1f}s)")
            except Exception as e:
                with fetch_lock:
                    fetch_done[0] += 1
                    print(f"  [{fetch_done[0]}/{total}] ✗ {stock['name']}({stock['code']}) 失败: {e}")

    fetch_elapsed = time.time() - fetch_start
    print(f"📊 数据获取完成 ({len(stock_data_map)}/{total}), 耗时 {fetch_elapsed:.1f}s\n")

    # 准备所有分析任务
    analysis_tasks = []
    for code, (stock, data) in stock_data_map.items():
        use_deep, triggers, score = (True, ["强制深度"], 0) if analysis_mode == 'deep' else (brain.evaluate_signal_strength_v2(data) if (analysis_mode == 'auto' and brain) else (False, [], 0))
        analysis_tasks.append((code, stock, data, use_deep, triggers, score))

    # 并行执行 AI 分析（限制并发数 + 限流）
    deep_count = 0
    ai_results = {}
    ai_semaphore = threading.Semaphore(3)  # 最多 3 个并发 AI 调用
    ai_total = len(analysis_tasks)
    ai_lock = threading.Lock()
    ai_done = [0]
    ai_start = time.time()

    print(f"🧠 AI深度分析中 (共{ai_total}只)...")

    def analyze_one(code, stock, data, use_deep):
        ai_semaphore.acquire()
        try:
            t0 = time.time()
            if use_deep and brain:
                result = brain.deep_analyze_stock(data), "🧠 深度分析"
            else:
                result = call_ai(f"请对{stock['name']}进行快速分析。数据：{data['tech_summary']}, {data['money_summary']}"), "🤖 快速分析"
            with ai_lock:
                ai_done[0] += 1
                print(f"  [✓ 完成 {ai_done[0]}/{ai_total}] {stock['name']} ({time.time()-t0:.1f}s)")
            return result
        finally:
            ai_semaphore.release()

    with ThreadPoolExecutor(max_workers=3) as ai_executor:
        future_map = {}
        for idx, (code, stock, data, use_deep, triggers, score) in enumerate(analysis_tasks):
            if use_deep:
                deep_count += 1
            if idx > 0:
                time.sleep(2)  # 限流：每次提交间隔 2 秒，避免触发 API QPM 限制
            future = ai_executor.submit(analyze_one, code, stock, data, use_deep)
            future_map[future] = (code, stock, data)
            print(f"  [→ 提交 {idx+1}/{ai_total}] {stock['name']}")

        for future in as_completed(future_map):
            code, stock, data = future_map[future]
            try:
                summary, label = future.result()
                ai_results[code] = (stock, data, summary, label)
            except Exception as e:
                logging.error(f"❌ AI分析失败: {stock['name']}: {e}")
                ai_results[code] = (stock, data, f"⚠️ 分析失败: {e}", "❌ 失败")

    ai_elapsed = time.time() - ai_start
    print(f"🧠 AI分析完成 ({len(ai_results)}/{ai_total}), 耗时 {ai_elapsed:.1f}s\n")

    # 按原始顺序组装报告
    for code, stock, data, use_deep, triggers, score in analysis_tasks:
        if code in ai_results:
            stock, data, summary, label = ai_results[code]
            print(f"\n[{label}] {stock['name']} ({code})")
            report_content += f"## {stock['name']} ({code})\n\n**分析模式**: {label}\n- **趋势**: {data['tech_summary']}\n- **资金**: {data['money_summary']}\n- **舆情**: {data['news_summary']}\n\n**AI点评**:\n\n{summary}\n\n---\n\n"

    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Report", now.strftime('%y%m%d'))
    os.makedirs(report_dir, exist_ok=True)
    filename = os.path.join(report_dir, f"{now.strftime('%H%M%S')}_{watchlist_name}_{analysis_mode}.md")

    with open(filename, "w", encoding="utf-8") as f: f.write(report_content)
    print(f"\n✅ Markdown报告已生成: {filename}")
    pdf_path = filename.replace('.md', '.pdf')
    if md_to_pdf(filename, pdf_path):
        print(f"✅ PDF报告已生成: {pdf_path}")

# ============================================================
# 批量估值分析
# ============================================================
_batch_logger = logging.getLogger('batch_valuation')


class StockListParser:
    """股票清单解析器，支持多种格式"""

    def __init__(self):
        self.finder = StockFinder()

    def parse_text(self, text: str) -> List[Tuple[str, str]]:
        """
        解析包含股票信息的文本，提取股票代码和名称

        支持格式：
        - 600519 贵州茅台
        - 贵州茅台 (600519)
        - 贵州茅台
        - 600519
        """
        stocks = []
        seen = set()

        for line in text.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            code_candidates = re.findall(r'\b\d{6}\b', line)
            name_candidates = re.findall(r'[\u4e00-\u9fa5]{2,}', line)

            if code_candidates:
                for code in code_candidates:
                    if code not in seen:
                        result = self.finder.find(code)
                        if result and isinstance(result, dict):
                            stock_code = result['code']
                            stock_name = result['name']
                            stocks.append((stock_code, stock_name))
                            seen.add(stock_code)
                            _batch_logger.info(f"✓ 解析: {stock_name} ({stock_code})")

            if name_candidates and not code_candidates:
                for name in name_candidates:
                    if len(name) < 2:
                        continue
                    result = self.finder.find(name)
                    if result and isinstance(result, dict):
                        stock_code = result['code']
                        stock_name = result['name']
                        if stock_code not in seen:
                            stocks.append((stock_code, stock_name))
                            seen.add(stock_code)
                            _batch_logger.info(f"✓ 解析: {stock_name} ({stock_code})")
                    elif result and isinstance(result, list):
                        match_names = ', '.join([f"{s['name']}({s['code']})" for s in result[:3]])
                        _batch_logger.warning(f"⚠️ '{name}' 匹配到多只股票，已跳过: {match_names}")

        return stocks

    def parse_file(self, file_path: str) -> List[Tuple[str, str]]:
        """从文件解析股票清单"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            return self.parse_text(text)
        except Exception as e:
            _batch_logger.error(f"❌ 读取文件失败: {e}")
            return []


class BatchValuationAnalyzer:
    """批量估值分析器"""

    def __init__(self, call_ai_func, model: str = None):
        self.analyzer = ValuationAnalyzer()
        self.call_ai = call_ai_func
        self.model = model or ai_config.get_primary_model_name()

    def analyze_batch(self, stocks: List[Tuple[str, str]], output_dir: Optional[str] = None, delay: float = 2.0) -> dict:
        """批量分析股票列表"""
        if output_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            date_folder = datetime.now().strftime('%y%m%d')
            output_dir = os.path.join(script_dir, "Report", date_folder)
        os.makedirs(output_dir, exist_ok=True)

        stats = {'total': len(stocks), 'success': 0, 'failed': 0, 'failed_list': []}

        print(f"\n{'='*60}")
        print(f"📊 批量估值分析模式")
        print(f"📅 日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📝 任务数: {len(stocks)} 只股票")
        print(f"📁 输出目录: {output_dir}")
        print(f"{'='*60}\n")

        for idx, (stock_code, stock_name) in enumerate(stocks, 1):
            print(f"\n[{idx}/{len(stocks)}] 正在分析: {stock_name} ({stock_code})")
            print("-" * 60)

            try:
                print(f"📊 获取估值数据...")
                metrics, summary = self.analyzer.analyze(stock_code, stock_name)

                print(f"🧠 调用 {self.model} 进行深度分析...")
                prompt = self.analyzer.generate_llm_prompt(metrics)
                analysis = self.call_ai(prompt, model=self.model)

                filename = os.path.join(output_dir, f"{datetime.now().strftime('%H%M%S')}_{stock_name}_估值分析.md")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(f"# {stock_name}（{stock_code}）快速估值分析\n\n")
                    f.write(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write(summary)
                    f.write("\n\n---\n\n")
                    f.write("## AI 深度分析\n\n")
                    f.write(analysis)

                print(f"✅ 报告已保存: {filename}")
                pdf_path = filename.replace('.md', '.pdf')
                if md_to_pdf(filename, pdf_path):
                    print(f"✅ PDF报告已生成: {pdf_path}")
                stats['success'] += 1

                if idx < len(stocks):
                    print(f"⏳ 等待 {delay} 秒...")
                    time.sleep(delay)

            except Exception as e:
                _batch_logger.error(f"❌ 分析失败: {e}")
                stats['failed'] += 1
                stats['failed_list'].append((stock_code, stock_name, str(e)))
                print(f"❌ 分析失败: {e}")

        print(f"\n{'='*60}")
        print(f"📊 批量分析完成")
        print(f"{'='*60}")
        print(f"✅ 成功: {stats['success']}/{stats['total']}")
        print(f"❌ 失败: {stats['failed']}/{stats['total']}")

        if stats['failed_list']:
            print(f"\n失败列表:")
            for code, name, error in stats['failed_list']:
                print(f"  - {name} ({code}): {error[:50]}")

        print(f"\n📁 报告目录: {output_dir}")
        print(f"{'='*60}\n")

        return stats


def run_batch_valuation(input_source: str, call_ai_func, model: str = None, delay: float = 2.0, auto_confirm: bool = False):
    """运行批量估值分析"""
    parser = StockListParser()

    if os.path.isfile(input_source):
        print(f"📄 从文件解析股票清单: {input_source}")
        stocks = parser.parse_file(input_source)
    else:
        print(f"📝 从文本解析股票清单")
        stocks = parser.parse_text(input_source)

    if not stocks:
        print("❌ 未解析到任何股票，请检查输入格式")
        return

    print(f"\n解析结果: 共 {len(stocks)} 只股票")
    print("-" * 60)
    for idx, (code, name) in enumerate(stocks, 1):
        print(f"{idx}. {name} ({code})")
    print("-" * 60)

    if not auto_confirm:
        confirm = input("\n是否开始批量分析？[Y/n]: ").strip().lower()
        if confirm and confirm != 'y':
            print("已取消")
            return
    else:
        print("\n⚡ 自动确认模式：直接开始批量分析")

    analyzer = BatchValuationAnalyzer(call_ai_func=call_ai_func, model=model)
    return analyzer.analyze_batch(stocks, delay=delay)


# ============================================================
# 缓存预热
# ============================================================
def run_warm_cache(list_name: str = "my"):
    """预热自选股缓存"""
    from analyst_cache import warm_up_cache, get_cache_info

    lists = {
        "my": ("My Watchlist", MY_WATCHLIST),
        "dad": ("Dad's Watchlist", DAD_WATCHLIST),
        "erin": ("Erin's Watchlist", ERIN_WATCHLIST),
        "all": ("全部自选股", MY_WATCHLIST + DAD_WATCHLIST + ERIN_WATCHLIST),
    }

    if list_name not in lists:
        print(f"❌ 未知列表: {list_name}，可选: my/dad/erin/all")
        return

    label, watchlist = lists[list_name]
    print("=" * 70)
    print("📦 自选股缓存预热工具")
    print("=" * 70)
    print(f"\n✅ 预热列表: {label} ({len(watchlist)} 只)")
    print("\n包含标的:")
    for stock in watchlist:
        print(f"  - {stock['name']} ({stock['code']})")

    print("\n" + "=" * 70)
    warm_up_cache(watchlist)

    print("\n" + "=" * 70)
    print("📊 缓存统计")
    print("=" * 70)
    get_cache_info()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Quant Lab - AI量化分析系统')
    parser.add_argument('--list', choices=['my', 'dad', 'erin'], help='指定 watchlist')
    parser.add_argument('--stock', help='单股查询模式 CODE[:NAME]')
    parser.add_argument('--no-interaction', action='store_true', help='非交互模式')
    parser.add_argument('--analysis-mode', choices=['fast', 'deep', 'auto'], default='fast')
    parser.add_argument('--prompt-version', choices=['professional', 'value_first', 'quant_hybrid'], default='professional', help='Prompt风格')
    parser.add_argument('--valuation', help='快速估值模式')
    parser.add_argument('--batch-valuation', help='批量估值模式')
    parser.add_argument('--warm-cache', choices=['my', 'dad', 'erin', 'all'], help='缓存预热')
    parser.add_argument('--global', dest='global_stock', help='全球股票分析模式 (如 TSLA, AAPL, MSFT)')
    parser.add_argument('--delay', type=float, default=2.0)
    parser.add_argument('--yes', '-y', action='store_true')

    args = parser.parse_args()

    if args.warm_cache:
        run_warm_cache(args.warm_cache)
        sys.exit(0)

    if args.batch_valuation:
        run_batch_valuation(args.batch_valuation, call_ai, ai_config.get_primary_model_name(), args.delay, args.yes)
        sys.exit(0)

    if args.valuation:
        code, name, market = smart_stock_query(args.valuation)
        if code:
            va = ValuationAnalyzer()
            metrics, summary = va.analyze(code, name, market=market)
            print(summary)

            # 保存估值摘要报告
            now = datetime.now()
            report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Report", now.strftime('%y%m%d'))
            os.makedirs(report_dir, exist_ok=True)
            filename = os.path.join(report_dir, f"{now.strftime('%H%M%S')}_{name}_估值分析.md")
            ai_section = ""

            # 修改为9秒超时，默认自动开始 (y)
            prompt_msg = "\n🤔 是否启动AI深度分析？(9秒内未响应将自动开始) [Y/n]: "
            if ask_user_with_timeout(prompt_msg, 9, default='y') in ['y', 'yes']:
                ai_result = call_ai(va.generate_llm_prompt(metrics))
                print(ai_result)
                ai_section = f"\n## AI深度分析\n\n{ai_result}\n"

            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# {name}（{code}）估值分析\n\n> 生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n{summary}\n{ai_section}")
            print(f"\n✅ 报告已保存: {filename}")
            pdf_path = filename.replace('.md', '.pdf')
            if md_to_pdf(filename, pdf_path):
                print(f"✅ PDF报告已生成: {pdf_path}")
        sys.exit(0)

    if args.global_stock:
        run_global_stock_mode(args.global_stock)
        sys.exit(0)

    if args.stock:
        code, name = args.stock.split(':', 1) if ':' in args.stock else (args.stock, None)
        run_single_stock_mode(code.strip(), name.strip() if name else None, args.analysis_mode, args.prompt_version)
        sys.exit(0)

    selected = args.list or (args.no_interaction and 'my') or get_user_choice_with_timeout()
    run_monitor_mode(selected, args.analysis_mode, args.prompt_version)
