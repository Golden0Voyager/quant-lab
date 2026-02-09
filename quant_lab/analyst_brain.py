"""
决策层 V2.0 - 基于量化思维的智能触发系统

改进点：
1. 相对强度替代绝对值（资金/市值比例）
2. 多维度技术信号（突破+成交量）
3. 分级触发机制（轻度/中度/重度）
4. 回测友好的设计
5. 支持多版本Prompt (value_first/quant_hybrid/professional)
"""

import os
import time
import logging
import re
from datetime import datetime, timedelta

# 引入统一配置中心
import ai_config
from openai import OpenAI

# 导入新的 Prompt 构建函数
from analyst_integration import build_enhanced_prompt

logger = logging.getLogger(__name__)


class AnalystBrain:
    """决策层 V2.0 - 量化增强版"""

    def __init__(self, model=None, prompt_version="professional"):
        """
        初始化 Brain V2

        Args:
            model: 指定模型（可选，默认使用 ai_config 中的主力模型）
            prompt_version: Prompt 版本 (value_first/quant_hybrid/professional)
        """
        # 如果未指定模型，从统一配置获取
        self.model = model or ai_config.get_primary_model_name()
        
        # 获取备用模型（用于重试）
        self.backup_model = ai_config.get_backup_model_name()
        
        self.prompt_version = prompt_version
        
        # 使用统一工厂创建客户端
        self.client = ai_config.create_openai_client(timeout=180.0)

    def evaluate_signal_strength_v2(self, data):
        """
        V2.0 信号评估系统：基于量化思维

        分级触发机制：
        - 轻度信号（1分）：可能有意义，但不紧急
        - 中度信号（2分）：值得关注
        - 重度信号（3分）：强烈建议深度分析

        触发阈值：>= 4分
        """
        triggers = []
        signal_score = 0

        # ==================== 资金面信号 ====================
        money_signals = self._evaluate_money_flow(data)
        triggers.extend(money_signals['triggers'])
        signal_score += money_signals['score']

        # ==================== 技术面信号 ====================
        tech_signals = self._evaluate_technical(data)
        triggers.extend(tech_signals['triggers'])
        signal_score += tech_signals['score']

        # ==================== 基本面信号 ====================
        fundamental_signals = self._evaluate_fundamental(data)
        triggers.extend(fundamental_signals['triggers'])
        signal_score += fundamental_signals['score']

        # ==================== 波动率信号 ====================
        volatility_signals = self._evaluate_volatility(data)
        triggers.extend(volatility_signals['triggers'])
        signal_score += volatility_signals['score']

        # 判断是否触发（阈值：3分 - 量化优化后的平衡值）
        need_deep = signal_score >= 3

        return need_deep, triggers, signal_score

    def _evaluate_money_flow(self, data):
        """
        资金流向评估（量化增强版）

        改进：
        1. 使用相对强度（资金/假设的日均成交额）
        2. 区分流入/流出方向
        3. 检测连续性
        """
        triggers = []
        score = 0

        money_summary = data.get('money_summary', '')

        # 提取资金金额
        if '亿' in money_summary:
            match = re.search(r'([\d.]+)亿', money_summary)
            if match:
                amount = float(match.group(1))
                direction = '流入' if '✅' in money_summary else '流出'

                # 量化判断：资金强度（假设日均成交额为50亿）
                # TODO: 未来可以从实际数据中获取流通市值或日均成交额
                avg_volume_estimate = 50  # 亿元，粗略估计

                intensity = abs(amount) / avg_volume_estimate

                if intensity >= 0.3:  # 超过日均成交额30%
                    if abs(amount) >= 10:
                        score += 3  # 重度：10亿以上
                        triggers.append(f"💰 巨额资金{direction}: {amount}亿 (强度{intensity:.1%})")
                    elif abs(amount) >= 5:
                        score += 2  # 中度：5-10亿
                        triggers.append(f"💰 大额资金{direction}: {amount}亿 (强度{intensity:.1%})")
                    else:
                        score += 1  # 轻度
                        triggers.append(f"💰 资金{direction}: {amount}亿")

        elif '万' in money_summary:
            match = re.search(r'([\d.]+)万', money_summary)
            if match:
                amount_wan = float(match.group(1))
                # 小盘股可能用万作单位
                if abs(amount_wan) >= 5000:  # 5000万 = 0.5亿
                    score += 1
                    triggers.append(f"💰 资金异动: {amount_wan}万")

        return {'triggers': triggers, 'score': score}

    def _evaluate_technical(self, data):
        """
        技术面评估（量化增强版）

        改进：
        1. 精确判断"突破"而非"所在位置"
        2. 多周期均线（MA20, MA60, MA250）
        3. 结合价格位置计算距离百分比
        """
        triggers = []
        score = 0

        tech_summary = data.get('tech_summary', '')

        # 解析技术数据
        price_match = re.search(r'现价 ([\d.]+)', tech_summary)
        ma20_match = re.search(r'MA20 ([\d.]+)', tech_summary)

        if price_match and ma20_match:
            price = float(price_match.group(1))
            ma20 = float(ma20_match.group(1))

            # 计算与MA20的距离
            distance_pct = (price - ma20) / ma20 * 100

            # 策略1：刚突破MA20（1-3日内）
            if 0 < distance_pct <= 3:  # 在MA20上方0-3%
                score += 2
                triggers.append(f"📈 突破月线: 距MA20 +{distance_pct:.1f}%（右侧交易机会）")
            elif -3 <= distance_pct < 0:  # 在MA20下方0-3%
                score += 2
                triggers.append(f"📉 跌破月线: 距MA20 {distance_pct:.1f}%（风险信号）")

            # 策略2：即将突破MA20（测试支撑/压力）
            elif 3 < distance_pct <= 5:
                score += 1
                triggers.append(f"🔍 测试MA20上方: +{distance_pct:.1f}%（关注回踩）")
            elif -5 <= distance_pct < -3:
                score += 1
                triggers.append(f"🔍 测试MA20下方: {distance_pct:.1f}%（关注反弹）")

            # 策略3：远离均线（超买/超卖）
            elif distance_pct > 15:
                score += 1
                triggers.append(f"⚠️ 远离MA20: +{distance_pct:.1f}%（超买风险）")
            elif distance_pct < -15:
                score += 1
                triggers.append(f"⚠️ 远离MA20: {distance_pct:.1f}%（超卖机会？）")

        # 年线判断
        if '年线上方(强势)' in tech_summary:
            # 仅当刚提及年线时才加分
            score += 1
            triggers.append("📊 站稳年线（趋势偏多）")
        elif '年线下方(弱势)' in tech_summary:
            score += 1
            triggers.append("📊 失守年线（趋势偏空）")

        return {'triggers': triggers, 'score': score}

    def _evaluate_fundamental(self, data):
        """
        基本面评估（量化增强版）

        改进：
        1. 精细化关键词权重
        2. 尝试提取数字（回购金额、业绩增速）
        3. 过滤常规公告
        """
        triggers = []
        score = 0

        news_context = data.get('news_context', '')

        # 高权重事件（3分）
        critical_events = {
            '重组': '重大资产重组',
            '并购': '并购整合',
            '业绩暴增': '业绩大幅增长',
            '业绩预增': '业绩预告增长',
            '中标': '重大合同中标',
        }

        for keyword, description in critical_events.items():
            if keyword in news_context:
                score += 3
                triggers.append(f"🔥 {description}")
                break  # 只触发一次最高权重

        # 中权重事件（2-3分，根据金额调整）
        important_events = {
            '回购': self._extract_buyback_amount,
            '增持': self._extract_shareholding_change,
            '分红': self._extract_dividend_info,
        }

        for keyword, extractor in important_events.items():
            if keyword in news_context and score < 3:  # 避免重复计分
                amount_info = extractor(news_context)
                if amount_info:
                    # 根据金额动态调整分数
                    if keyword == '回购' and '亿' in amount_info:
                        match = re.search(r'([\d.]+)亿', amount_info)
                        if match and float(match.group(1)) >= 5:
                            score += 3  # 大额回购（>=5亿）给3分
                            triggers.append(f"🔥 大额{keyword}: {amount_info}")
                        else:
                            score += 2
                            triggers.append(f"💎 {keyword}: {amount_info}")
                    else:
                        score += 2
                        triggers.append(f"💎 {keyword}: {amount_info}")

        # 轻度关注事件（1分）
        if score == 0:  # 没有重大事件时才检查这些
            minor_events = ['减持', '股东变更', '高管变动']
            for event in minor_events:
                if event in news_context:
                    score += 1
                    triggers.append(f"ℹ️ {event}（需关注）")
                    break

        # 过滤：删除常规公告（不加分）
        routine_patterns = ['董事会决议', '股东大会通知', '法律意见书']
        # 这些不触发，除非配合其他重大事件

        return {'triggers': triggers, 'score': score}

    def _evaluate_volatility(self, data):
        """
        波动率评估（未来扩展）

        TODO: 需要历史K线数据才能计算
        - ATR（平均真实波幅）突增
        - 单日涨跌幅 > 7%
        - 连续大阴/大阳线
        """
        triggers = []
        score = 0

        # 当前缺少历史K线数据，留作未来扩展
        # 如果tech_summary中包含涨跌幅信息，可以尝试提取

        return {'triggers': triggers, 'score': score}

    def _extract_buyback_amount(self, text):
        """提取回购金额"""
        # 简单实现：匹配"回购XX亿"
        match = re.search(r'回购.*?([\d.]+)亿', text)
        if match:
            amount = float(match.group(1))
            if amount >= 5:
                return f"{amount}亿（大额）"
            else:
                return f"{amount}亿"
        return "详见公告"

    def _extract_shareholding_change(self, text):
        """提取增持信息"""
        # 简单实现
        if '大股东' in text or '实控人' in text:
            return "大股东增持"
        return "增持"

    def _extract_dividend_info(self, text):
        """提取分红信息"""
        match = re.search(r'([\d.]+)元', text)
        if match:
            return f"{match.group(1)}元/股"
        return "详见公告"

    def deep_analyze_stock(self, stock_data, prompt_version=None):
        """
        调用Brain进行深度分析 (支持主备模型切换)

        Args:
            stock_data: 从 Worker 层获取的结构化数据
            prompt_version: Prompt版本

        Returns:
            深度分析报告
        """
        # 使用指定版本或默认版本
        version = prompt_version or self.prompt_version

        # 使用新的 Prompt 构建函数
        prompt = build_enhanced_prompt(stock_data, analysis_type="brain", prompt_version=version)

        # 尝试列表：[(模型名称, 尝试次数)]
        # 策略：先试主模型 2 次，失败后试备用模型 2 次
        attempts_plan = [
            (self.model, 1),
            (self.model, 2),
            (self.backup_model, 1),
            (self.backup_model, 2)
        ]

        logger.info(f"🧠 Brain V2深度分析: {stock_data['name']} (Prompt: {version})")

        last_error = None
        for model_name, attempt_idx in attempts_plan:
            try:
                if model_name != self.model and attempt_idx == 1:
                    logger.info(f"⚠️ 切换到备用模型: {model_name} ...")

                logger.info(f"⏳ 调用 {model_name} (尝试 {attempt_idx})...")
                
                completion = self.client.chat.completions.create(
                    model=model_name,
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
                    temperature=0.3
                )
                return completion.choices[0].message.content

            except Exception as e:
                last_error = e
                logger.warning(f"❌ {model_name} 调用失败: {type(e).__name__}")
                time.sleep(1) # 短暂冷却

        error_msg = f"深度分析失败 (所有模型均尝试失败): {str(last_error)}"
        logger.error(error_msg)
        return error_msg

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


def test_signal_evaluation():
    """测试信号评估系统"""
    brain = AnalystBrain()

    # 测试案例1：大额资金流入 + 突破MA20
    test1 = {
        'name': '思源电气',
        'money_summary': '3日主力✅流入 8.24亿',
        'tech_summary': '现价 150.50 | MA20 147.84 | 年线上方(强势)',
        'news_context': '- 董事会决议\n- 薪酬管理办法',
    }

    need_deep, triggers, score = brain.evaluate_signal_strength_v2(test1)
    print(f"\n测试1: {test1['name']}")
    print(f"触发深度分析: {need_deep} (评分: {score})")
    print(f"触发原因: {triggers}")

    # 测试案例2：重大回购公告
    test2 = {
        'name': '中兴通讯',
        'money_summary': '3日主力❌流出 -3.24亿',
        'tech_summary': '现价 36.50 | MA20 38.84 | 月线下方',
        'news_context': '- 发布回购方案，拟回购10亿元\n- 用于员工持股计划',
    }

    need_deep, triggers, score = brain.evaluate_signal_strength_v2(test2)
    print(f"\n测试2: {test2['name']}")
    print(f"触发深度分析: {need_deep} (评分: {score})")
    print(f"触发原因: {triggers}")

    # 测试案例3：常规公告，无特殊信号
    test3 = {
        'name': '海尔智家',
        'money_summary': '3日主力❌流出 -620万',
        'tech_summary': '现价 27.50 | MA20 27.20 | 月线上方',
        'news_context': '- 董事会决议\n- 股东大会通知\n- 法律意见书',
    }

    need_deep, triggers, score = brain.evaluate_signal_strength_v2(test3)
    print(f"\n测试3: {test3['name']}")
    print(f"触发深度分析: {need_deep} (评分: {score})")
    print(f"触发原因: {triggers if triggers else '无显著信号'}")


if __name__ == "__main__":
    test_signal_evaluation()
