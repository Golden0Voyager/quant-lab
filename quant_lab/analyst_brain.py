"""
决策层 (Brain Layer) - 深度分析与策略决策

使用强推理模型进行复杂的金融分析和决策
"""

import os
import time
import logging
from openai import OpenAI

# 配置日志
logger = logging.getLogger(__name__)


class AnalystBrain:
    """决策层分析器 - 使用强推理模型进行深度分析"""

    def __init__(self, model="deepseek-v3.2", api_key=None, base_url=None):
        """
        初始化决策层

        Args:
            model: 使用的模型（默认 deepseek-v3.2）
            api_key: API密钥
            base_url: API端点
        """
        self.model = model
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=90.0)

    def deep_analyze_stock(self, stock_data):
        """
        对单只股票进行深度分析

        Args:
            stock_data: 从 Worker 层获取的结构化数据

        Returns:
            深度分析报告
        """
        # 构建深度分析 prompt
        prompt = self._build_deep_analysis_prompt(stock_data)

        # 调用强推理模型
        logger.info(f"🧠 Brain 深度分析: {stock_data['name']} (模型: {self.model})")

        for attempt in range(3):
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一位资深的量化分析师，擅长深度挖掘市场信号，识别投资机会和风险。"
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3  # 降低温度，提高分析的稳定性
                )
                return completion.choices[0].message.content
            except Exception as e:
                logger.warning(f"Brain 分析失败 (尝试 {attempt + 1}/3): {type(e).__name__}")
                if attempt < 2:
                    time.sleep(2)

        return "深度分析超时，请稍后重试"

    def _build_deep_analysis_prompt(self, data):
        """构建深度分析的 prompt"""

        asset_type = data.get('type', 'stock')

        if asset_type == 'stock':
            # 个股深度分析
            prompt = f"""
请对个股【{data['name']}】进行深度量化分析。

## 一、核心数据
**资金流向**：{data['money_summary']}
**技术形态**：{data['tech_summary']}
**舆情信息**：
{data['news_context']}

## 二、分析要求

### 1. 多维度信号解读
- **资金面**：分析主力资金行为背后的逻辑（建仓/出货/洗盘/观望）
- **技术面**：识别关键支撑位、压力位，判断趋势强度
- **基本面**：从公告中提取业绩、治理、事件驱动等信号
- **情绪面**：评估市场对该股的关注度和情绪偏向

### 2. 风险收益评估
- 当前位置的赔率（潜在涨幅 vs 回调空间）
- 关键风险点识别（技术破位点、基本面隐患）
- 时间窗口判断（短线/中线/长线）

### 3. 策略建议
- **评级**：看多/中性/看空，并给出置信度（0-100%）
- **操作建议**：具体的买卖点位、仓位建议、止损位
- **监控指标**：需要持续关注的关键指标

### 4. 输出格式要求
请用结构化markdown格式输出，包含：
- **综合评级**：看多/中性/看空 + 置信度
- **核心逻辑**：2-3句话说明主要理由
- **关键信号**：列出3个最重要的信号
- **操作策略**：分短线/中线分别给出建议
- **风险提示**：列出主要风险点

注意：✅表示资金流入（利好），❌表示资金流出（利空）
"""
        elif asset_type == 'etf':
            # ETF/行业分析
            prompt = f"""
请对行业ETF【{data['name']}】进行深度分析，重点关注：

**赛道趋势**：{data['tech_summary']}
**资金动向**：ETF份额变化、资金流向
**行业催化**：当前行业的政策、事件驱动

分析要点：
1. 行业景气度判断
2. 板块轮动位置
3. 配置时机建议
"""
        else:
            # 指数分析
            prompt = f"""
请对大盘指数【{data['name']}】进行宏观分析：

**趋势位置**：{data['tech_summary']}

分析要点：
1. 大盘环境判断（牛市/熊市/震荡市）
2. 系统性风险评估
3. 仓位管理建议
"""

        return prompt

    def evaluate_signal_strength(self, data):
        """
        评估信号强度，判断是否需要深度分析

        Args:
            data: 股票数据

        Returns:
            (需要深度分析, 触发原因列表)
        """
        triggers = []

        # 1. 资金异动检测
        money_summary = data.get('money_summary', '')
        if '亿' in money_summary:
            # 提取金额
            import re
            match = re.search(r'([\d.]+)亿', money_summary)
            if match:
                amount = float(match.group(1))
                if abs(amount) >= 5:  # 5亿以上异动
                    triggers.append(f"资金异动大: {amount}亿")

        # 2. 技术突破检测
        tech_summary = data.get('tech_summary', '')
        if '年线上方' in tech_summary or '年线下方' in tech_summary:
            triggers.append("价格位于年线关键位置")

        # 3. 重大公告检测
        news_context = data.get('news_context', '')
        critical_keywords = ['回购', '重组', '并购', '业绩', '中标', '分红', '增持', '减持']
        for keyword in critical_keywords:
            if keyword in news_context:
                triggers.append(f"重大事件: {keyword}")
                break

        # 4. 新闻来源评估
        news_source = data.get('news_source', '')
        if news_source == '东财公告' and len(triggers) == 0:
            # 有官方公告但无其他触发条件，判断公告重要性
            important_patterns = ['股东大会', '董事会', '审计', '法律意见']
            for pattern in important_patterns:
                if pattern in news_context:
                    triggers.append(f"重要公告: {pattern}")
                    break

        # 判断是否需要深度分析
        need_deep = len(triggers) >= 2  # 2个及以上信号触发

        return need_deep, triggers


def test_brain():
    """测试决策层功能"""
    brain = AnalystBrain(model="deepseek-v3.2")

    # 模拟测试数据
    test_data = {
        'name': '思源电气',
        'code': '002028',
        'type': 'stock',
        'money_summary': '3日主力✅流入 5.24亿',
        'tech_summary': '现价 148.50 | MA20 147.84 | 年线上方(强势)',
        'news_context': '- 发布股份回购方案\n- 2025年第三季度业绩超预期\n- 董事会战略升级',
        'news_source': '东财公告'
    }

    # 测试信号评估
    need_deep, triggers = brain.evaluate_signal_strength(test_data)
    print(f"需要深度分析: {need_deep}")
    print(f"触发原因: {triggers}")

    # 如果需要，进行深度分析
    if need_deep:
        analysis = brain.deep_analyze_stock(test_data)
        print("\n深度分析结果:")
        print(analysis)


if __name__ == "__main__":
    test_brain()
