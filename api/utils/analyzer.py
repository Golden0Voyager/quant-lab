"""
股票分析器
封装现有的分析功能，提供统一的API接口
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 导入现有的分析模块
from analyst_brain import AnalystBrain
from analyst_integration import build_enhanced_prompt, fetch_stock_data
from stock_finder import smart_stock_query
from valuation_analyzer import ValuationAnalyzer

logger = logging.getLogger(__name__)


class StockAnalyzer:
    """股票分析器类"""

    def __init__(self):
        """初始化分析器"""
        # 初始化AI分析引擎
        api_key = os.getenv('DASHSCOPE_API_KEY', '')
        if not api_key:
            logger.warning("未配置DASHSCOPE_API_KEY，AI分析功能可能不可用")

        self.brain = AnalystBrain(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen-flash"
        )

        # 初始化估值分析器
        self.valuation_analyzer = ValuationAnalyzer()

        logger.info("股票分析器初始化完成")

    def _get_prompt(self, mode: str, data: dict, prompt_version: str = "professional") -> str:
        """
        获取分析提示词

        Args:
            mode: 分析模式 (fast/deep)
            data: 股票数据
            prompt_version: 提示词版本

        Returns:
            提示词字符串
        """
        if mode == "fast":
            # 快速分析使用worker模式
            return build_enhanced_prompt(data, analysis_type="worker", prompt_version=prompt_version)
        else:
            # 深度分析使用brain模式
            return build_enhanced_prompt(data, analysis_type="brain", prompt_version=prompt_version)

    def _resolve_stock_code(self, code: str, name: str = "") -> tuple:
        """
        解析股票代码，如果提供名称则尝试查询

        Args:
            code: 股票代码
            name: 股票名称（可选）

        Returns:
            (股票代码, 股票名称, 市场)
        """
        if name:
            return code, name, 'A'

        # 尝试通过代码查询名称
        try:
            resolved_code, resolved_name, market, asset_type = smart_stock_query(code)
            if resolved_code:
                return resolved_code, resolved_name, market or 'A'
        except Exception as e:
            logger.warning(f"查询股票名称失败: {e}")

        return code, code, 'A'

    def analyze_fast(self, stock_code: str, stock_name: str = "") -> dict[str, Any]:
        """
        快速分析（Fast模式）

        Args:
            stock_code: 股票代码
            stock_name: 股票名称（可选）

        Returns:
            分析结果字典
        """
        try:
            # 解析股票代码
            code, name, market = self._resolve_stock_code(stock_code, stock_name)
            logger.info(f"开始快速分析: {code} {name}")

            # 获取数据
            data = fetch_stock_data(code)
            if not data:
                raise ValueError(f"无法获取股票数据: {code}")

            # 快速分析模式：只做基础点评
            prompt = self._get_prompt("fast", data)
            summary = self.brain.analyze_with_prompt(prompt)

            # 生成报告ID
            report_id = f"{code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_fast"

            return {
                "stock_code": code,
                "stock_name": name,
                "summary": summary,
                "report_id": report_id,
                "mode": "fast",
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"快速分析失败: {e}", exc_info=True)
            raise

    def analyze_deep(self, stock_code: str, stock_name: str = "",
                     prompt_version: str = "professional") -> dict[str, Any]:
        """
        深度分析（Deep模式）

        Args:
            stock_code: 股票代码
            stock_name: 股票名称（可选）
            prompt_version: 分析策略版本

        Returns:
            分析结果字典
        """
        try:
            # 解析股票代码
            code, name, market = self._resolve_stock_code(stock_code, stock_name)
            logger.info(f"开始深度分析: {code} {name}, 策略={prompt_version}")

            # 获取数据
            data = fetch_stock_data(code)
            if not data:
                raise ValueError(f"无法获取股票数据: {code}")

            # 深度分析
            prompt = self._get_prompt("deep", data, prompt_version)
            analysis = self.brain.analyze_with_prompt(prompt)

            # 生成报告markdown
            report_markdown = self._format_deep_report(code, name, analysis, prompt_version)

            # 生成报告ID
            report_id = f"{code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{prompt_version}"

            return {
                "stock_code": code,
                "stock_name": name,
                "report_markdown": report_markdown,
                "analysis": analysis,
                "strategy": prompt_version,
                "report_id": report_id,
                "mode": "deep",
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"深度分析失败: {e}", exc_info=True)
            raise

    def analyze_multi_strategy(self, stock_code: str, stock_name: str = "") -> dict[str, Any]:
        """
        多策略对比分析（MVP核心功能）

        Args:
            stock_code: 股票代码
            stock_name: 股票名称（可选）

        Returns:
            分析结果字典
        """
        try:
            # 解析股票代码
            code, name, market = self._resolve_stock_code(stock_code, stock_name)
            logger.info(f"开始多策略分析: {code} {name}")

            # 获取数据
            data = fetch_stock_data(code)
            if not data:
                raise ValueError(f"无法获取股票数据: {code}")

            # 三种策略分析
            strategies = ["professional", "value_first", "quant_hybrid"]
            results = {}

            for strategy in strategies:
                logger.info(f"  执行策略: {strategy}")
                prompt = self._get_prompt("deep", data, strategy)
                analysis = self.brain.analyze_with_prompt(prompt)
                results[strategy] = analysis

            # 生成对比报告
            comparison_report = self._format_comparison_report(code, name, results)

            # 生成报告ID
            report_id = f"{code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_multi"

            return {
                "stock_code": code,
                "stock_name": name,
                "comparison_report": comparison_report,
                "strategies": results,
                "report_id": report_id,
                "mode": "multi_strategy",
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"多策略分析失败: {e}", exc_info=True)
            raise

    def analyze_watchlist(self, stocks: list[dict], mode: str = "daily") -> dict[str, Any]:
        """
        自选股监控分析

        Args:
            stocks: 股票列表 [{"code": "600519", "name": "贵州茅台"}, ...]
            mode: 监控模式 (daily/weekly)

        Returns:
            分析结果字典
        """
        try:
            logger.info(f"开始自选股分析: {len(stocks)}只股票, 模式={mode}")

            all_results = []
            highlights = []  # 异动股票

            for stock in stocks:
                code = stock.get('code', '')
                name = stock.get('name', code)

                try:
                    # 获取数据
                    data = fetch_stock_data(code)
                    if not data:
                        logger.warning(f"跳过 {code}: 无法获取数据")
                        continue

                    # 根据模式选择分析深度
                    if mode == "daily":
                        # 日报：快速扫描，识别异动
                        prompt = self._get_prompt("fast", data)
                        analysis = self.brain.analyze_with_prompt(prompt)

                        # 简单的异动判断（可以后续优化）
                        is_highlight = self._check_if_highlight(data)
                        if is_highlight:
                            highlights.append({
                                "code": code,
                                "name": name,
                                "reason": "异动检测"
                            })

                    else:  # weekly
                        # 周报：深度分析
                        prompt = self._get_prompt("deep", data, "professional")
                        analysis = self.brain.analyze_with_prompt(prompt)

                    all_results.append({
                        "code": code,
                        "name": name,
                        "analysis": analysis
                    })

                except Exception as e:
                    logger.error(f"分析 {code} 失败: {e}")
                    continue

            # 生成监控报告
            report = self._format_watchlist_report(all_results, highlights, mode)

            return {
                "report": report,
                "highlights": highlights,
                "total_stocks": len(stocks),
                "analyzed_stocks": len(all_results),
                "mode": mode,
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"自选股分析失败: {e}", exc_info=True)
            raise

    def analyze_valuation(self, stock_code: str, stock_name: str = "") -> dict[str, Any]:
        """
        估值分析

        Args:
            stock_code: 股票代码
            stock_name: 股票名称（可选）

        Returns:
            估值分析结果
        """
        try:
            # 解析股票代码
            code, name, market = self._resolve_stock_code(stock_code, stock_name)
            logger.info(f"开始估值分析: {code} {name}")

            # 获取估值数据
            metrics = self.valuation_analyzer.analyze(code)

            # 生成估值报告
            summary = self.valuation_analyzer.format_report(metrics)

            return {
                "stock_code": code,
                "stock_name": name,
                "metrics": metrics.__dict__,
                "summary": summary,
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"估值分析失败: {e}", exc_info=True)
            raise

    def _format_deep_report(self, code: str, name: str, analysis: str, strategy: str) -> str:
        """格式化深度报告"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        strategy_name_map = {
            "professional": "专业投资者视角",
            "value_first": "价值投资视角",
            "quant_hybrid": "量化混合策略"
        }

        return f"""# {name}（{code}）深度分析报告

> 生成时间: {timestamp}
> 分析策略: {strategy_name_map.get(strategy, strategy)}

---

{analysis}

---

**免责声明**: 本报告由AI生成，仅供参考，不构成投资建议。
"""

    def _format_comparison_report(self, code: str, name: str, results: dict[str, str]) -> str:
        """格式化多策略对比报告"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        report = f"""# {name}（{code}）多策略对比分析

> 生成时间: {timestamp}
> 分析策略: 3种策略对比

---

## 📊 策略一：专业投资者视角

{results.get('professional', 'N/A')}

---

## 💰 策略二：价值投资视角

{results.get('value_first', 'N/A')}

---

## 🔢 策略三：量化混合策略

{results.get('quant_hybrid', 'N/A')}

---

**免责声明**: 本报告由AI生成，仅供参考，不构成投资建议。
"""
        return report

    def _format_watchlist_report(self, results: list[dict], highlights: list[dict], mode: str) -> str:
        """格式化自选股监控报告"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        mode_name = "日报" if mode == "daily" else "周报"

        report = f"""# 自选股监控{mode_name}

> 生成时间: {timestamp}
> 分析数量: {len(results)}只

---

"""

        # 异动提醒
        if highlights:
            report += "## ⚠️ 异动提醒\n\n"
            for h in highlights:
                report += f"- **{h['name']}（{h['code']}）**: {h['reason']}\n"
            report += "\n---\n\n"

        # 个股分析
        report += "## 📈 个股分析\n\n"
        for r in results:
            report += f"### {r['name']}（{r['code']}）\n\n"
            report += f"{r['analysis']}\n\n"
            report += "---\n\n"

        report += "**免责声明**: 本报告由AI生成，仅供参考，不构成投资建议。\n"

        return report

    def _check_if_highlight(self, data: dict) -> bool:
        """
        简单的异动判断逻辑

        Args:
            data: 股票数据

        Returns:
            是否异动
        """
        try:
            # 示例：涨跌幅超过5%视为异动
            change_pct = data.get('行情数据', {}).get('涨跌幅', 0)
            if abs(change_pct) > 5:
                return True

            # TODO: 可以添加更多异动判断逻辑
            # - 成交量放大
            # - 突破关键价位
            # - 重大新闻

            return False

        except Exception:
            return False
