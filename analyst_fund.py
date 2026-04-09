import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from analyst_base import BaseAnalyst, retry_on_failure, _to_xq_symbol
import os

class FundAnalyst(BaseAnalyst):
    """
    专业基金分析器 (Pro Edition)
    核心功能：风险调整收益计算、底层持仓穿透、风格归因
    """

    def __init__(self):
        self.risk_free_rate = 0.02  # 默认无风险利率 2%

    @retry_on_failure(max_retries=3)
    def fetch_data(self, symbol: str, name: str):
        """抓取基金全维度数据"""
        print(f"📊 [FUND] 深度研判: {name} ({symbol})...")
        data = {
            'type': 'fund',
            'name': name,
            'code': symbol,
            'metrics': {},
            'portfolio': [],
            'performance': {}
        }

        # 1. 基础信息抓取
        try:
            # 尝试通过东财获取基础排名和基本信息
            fund_info = ak.fund_open_fund_info_em(symbol=symbol, indicator="单位净值走势")
            if not fund_info.empty:
                data['basic'] = {"info": "开放式基金"}
        except:
            data['basic'] = {"info": "基础信息暂不可用"}

        # 2. 历史净值获取 (雪球通用接口 + 东财备用)
        nav_df = self._fetch_nav_history(symbol)
        if nav_df is not None and not nav_df.empty:
            data['metrics'] = self._calculate_pro_metrics(nav_df)
            data['nav_data'] = nav_df.tail(20).to_dict('records')
        
        # 3. 持仓穿透 (核心竞争力)
        data['portfolio'] = self._fetch_portfolio_penetration(symbol)
        
        # 4. 阶段表现
        data['performance'] = self._fetch_stage_performance(symbol)

        return data

    def _fetch_nav_history(self, symbol: str):
        """获取历史净值/价格数据 (多源容错)"""
        # 方案A: 雪球 (高效，支持前复权价格)
        try:
            xq_symbol = _to_xq_symbol(symbol)
            df = ak.stock_zh_a_hist_xq(symbol=xq_symbol, period="daily", adjust="qfq")
            if df is not None and not df.empty:
                col_date = '时间' if '时间' in df.columns else ('日期' if '日期' in df.columns else None)
                if col_date:
                    df['date'] = pd.to_datetime(df[col_date])
                    df = df.sort_values('date')
                    return df
        except Exception as e:
            logging.debug(f"雪球源尝试失败: {e}")

        # 方案B: 东财 (保底，纯净值)
        try:
            df = ak.fund_open_fund_info_em(symbol=symbol, indicator="单位净值走势")
            if df is not None and not df.empty:
                df = df.rename(columns={'净值日期': 'date', '单位净值': '收盘'})
                df['date'] = pd.to_datetime(df['date'])
                return df
        except:
            pass
        return None

    def _calculate_pro_metrics(self, df: pd.DataFrame):
        """计算专家级量化指标"""
        try:
            returns = df['收盘'].pct_change().dropna()
            if len(returns) < 10: return {}

            # 年化收益率
            total_return = (df['收盘'].iloc[-1] / df['收盘'].iloc[0]) - 1
            days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
            annual_return = (1 + total_return) ** (365 / max(days, 1)) - 1
            
            # 年化波动率
            annual_vol = returns.std() * np.sqrt(252)
            
            # 夏普比率
            sharpe = (annual_return - self.risk_free_rate) / annual_vol if annual_vol > 0 else 0
            
            # 最大回撤
            cumulative_returns = (1 + returns).cumprod()
            peak = cumulative_returns.cummax()
            drawdown = (cumulative_returns - peak) / peak
            max_dd = drawdown.min()
            
            # 卡玛比率
            calmar = annual_return / abs(max_dd) if max_dd != 0 else 0

            return {
                'annual_return': round(annual_return * 100, 2),
                'annual_vol': round(annual_vol * 100, 2),
                'sharpe_ratio': round(sharpe, 2),
                'max_drawdown': round(max_dd * 100, 2),
                'calmar_ratio': round(calmar, 2),
                'status': 'Normal'
            }
        except:
            return {'status': 'Calculation Failed'}

    def _fetch_portfolio_penetration(self, symbol: str):
        """持仓穿透逻辑"""
        try:
            df_portfolio = ak.fund_portfolio_hold_em(symbol=symbol)
            if df_portfolio is not None and not df_portfolio.empty:
                code_col = '股票代码' if '股票代码' in df_portfolio.columns else '代码'
                name_col = '股票名称' if '股票名称' in df_portfolio.columns else '名称'
                
                top_10 = df_portfolio.head(10).copy()
                holdings = []
                for _, row in top_10.iterrows():
                    ratio_val = row.get('占净值比例', row.get('持仓比例', row.get('持股比例', 0)))
                    try:
                        ratio_val = float(ratio_val)
                    except:
                        ratio_val = 0.0

                    holdings.append({
                        'code': str(row[code_col]),
                        'name': str(row[name_col]),
                        'ratio': ratio_val,
                        'change': row.get('持股变动', '持平')
                    })
                return holdings
        except:
            pass
        return []

    def _fetch_stage_performance(self, symbol: str):
        """获取阶段性涨跌幅排名"""
        try:
            df = ak.fund_open_fund_info_em(symbol=symbol, indicator="阶段涨跌幅")
            if df is not None and not df.empty:
                periods = ['近1周', '近1月', '近3月', '近6月', '近1年', '今年来']
                perf = {}
                for p in periods:
                    row = df[df['周期'] == p]
                    if not row.empty:
                        perf[p] = {
                            'return': row['涨跌幅'].values[0],
                            'rank': f"{row['同类排名'].values[0]}"
                        }
                return perf
        except:
            pass
        return {}

    def get_report_context(self, data: dict) -> str:
        """为 AI 提供格式化上下文"""
        metrics = data.get('metrics', {})
        perf = data.get('performance', {})
        portfolio = data.get('portfolio', [])
        
        port_str = ""
        for p in portfolio:
            port_str += f"- {p['name']} ({p['code']}): 占比 {p['ratio']}% | 变动: {p['change']}\n"

        perf_str = ""
        for k, v in perf.items():
            perf_str += f"- {k}: 收益 {v['return']}% | 排名 {v['rank']}\n"

        context = f"""
### 基金量化体检报告: {data['name']} ({data['code']})

#### 1. 核心风险收益指标 (Risk-Adjusted)
- **年化收益率**: {metrics.get('annual_return', 'N/A')}%
- **最大回撤 (MaxDrawdown)**: {metrics.get('max_drawdown', 'N/A')}% (风险压测指标)
- **夏普比率 (Sharpe)**: {metrics.get('sharpe_ratio', 'N/A')} (每承担一单位风险获得的超额收益)
- **卡玛比率 (Calmar)**: {metrics.get('calmar_ratio', 'N/A')} (收益与最大回撤的性价比)

#### 2. 阶段业绩表现
{perf_str if perf_str else "数据暂缺"}

#### 3. 前十大重仓股穿透 (Look-through)
{port_str if port_str else "持仓数据未公开或暂不可用"}

#### 4. 专家研判逻辑引导
- 如果 **夏普比率 > 1.0**，说明经理风险控制极佳。
- 如果 **最大回撤 > 30%**，说明该基金波动剧烈，不适合稳健投资者。
- 观察重仓股：如果重仓股近期集体处于“均线空头排列”，基金净值短期面临探底压力。
"""
        return context
