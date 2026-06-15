"""Tests for evaluate_signals — covering all signal branches."""

from __future__ import annotations

from quant_lab.core.pipeline.steps.evaluate_signals import (
    EvaluateSignalsStep,
    _evaluate_signals,
    _extract_amount,
)
from quant_lab.core.pipeline.state import AnalysisState


class TestExtractAmount:
    def test_valid_amount(self) -> None:
        assert _extract_amount("净流入 5.3亿") == 5.3

    def test_negative_amount(self) -> None:
        assert _extract_amount("净流出 -12亿") == 12.0

    def test_no_amount(self) -> None:
        assert _extract_amount("正常") is None

    def test_empty_string(self) -> None:
        assert _extract_amount("") is None


class TestMoneyFlowSignals:
    def test_huge_inflow_with_market_cap(self) -> None:
        data = {
            "money_summary": "✅ 主力净流入 15亿",
            "market_cap_yi": 200,
        }
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 3
        assert any("巨额资金异动" in t for t in triggers)

    def test_large_inflow_with_market_cap(self) -> None:
        data = {
            "money_summary": "✅ 主力净流入 10亿",
            "market_cap_yi": 400,
        }
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 2
        assert any("大额资金异动" in t for t in triggers)

    def test_small_inflow_with_market_cap(self) -> None:
        data = {
            "money_summary": "✅ 主力净流入 3亿",
            "market_cap_yi": 300,
        }
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 1
        assert any("资金异动" in t for t in triggers)

    def test_huge_inflow_no_market_cap(self) -> None:
        data = {"money_summary": "✅ 主力净流入 15亿"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 3
        assert any("巨额资金流入" in t for t in triggers)

    def test_large_inflow_no_market_cap(self) -> None:
        data = {"money_summary": "✅ 主力净流入 8亿"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 2
        assert any("大额资金流入" in t for t in triggers)

    def test_outflow_no_market_cap(self) -> None:
        data = {"money_summary": "主力净流出 12亿"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 3
        assert any("巨额资金流出" in t for t in triggers)

    def test_small_outflow_no_market_cap(self) -> None:
        data = {"money_summary": "主力净流出 6亿"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 2
        assert any("大额资金流出" in t for t in triggers)

    def test_no_money_summary(self) -> None:
        data = {}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score == 0


class TestValuationSignals:
    def test_valuation_mismatch(self) -> None:
        data = {
            "pe_ttm": "10",
            "pb": "3",
            "pe_percentile": "25%",
            "pb_percentile": "75%",
        }
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 3
        assert any("估值错位" in t for t in triggers)

    def test_extreme低估(self) -> None:
        data = {
            "pe_ttm": "8",
            "pb": "0.8",
            "pe_percentile": "15%",
            "pb_percentile": "18%",
        }
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 3
        assert any("极度低估" in t for t in triggers)

    def test_high估_warning(self) -> None:
        data = {
            "pe_ttm": "80",
            "pb": "12",
            "pe_percentile": "85%",
            "pb_percentile": "82%",
        }
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 2
        assert any("高估预警" in t for t in triggers)

    def test_valuation_na(self) -> None:
        data = {"pe_ttm": "N/A", "pb": "N/A"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score == 0

    def test_valuation_parse_error(self) -> None:
        data = {
            "pe_ttm": "10",
            "pb": "3",
            "pe_percentile": "abc%",
            "pb_percentile": "75%",
        }
        need_deep, triggers, score = _evaluate_signals(data)
        assert score == 0


class TestDividendSignals:
    def test_high_dividend(self) -> None:
        data = {"dividend_yield": "5.2%"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 2
        assert any("高股息" in t for t in triggers)

    def test_stable_dividend(self) -> None:
        data = {"dividend_yield": "3.5%"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 1
        assert any("稳定股息" in t for t in triggers)

    def test_no_dividend(self) -> None:
        data = {"dividend_yield": "N/A"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score == 0

    def test_no_dividend_text(self) -> None:
        data = {"dividend_yield": "无分红"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score == 0

    def test_dividend_parse_error(self) -> None:
        data = {"dividend_yield": "abc%"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score == 0


class TestProfitGrowthSignals:
    def test_profit_crash(self) -> None:
        data = {"profit_yoy": "-45%"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 3
        assert any("业绩爆雷" in t for t in triggers)

    def test_profit_double(self) -> None:
        data = {"profit_yoy": "150%"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 3
        assert any("业绩翻倍" in t for t in triggers)

    def test_profit_high_growth(self) -> None:
        data = {"profit_yoy": "45%"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 2
        assert any("业绩高增长" in t for t in triggers)

    def test_profit_na(self) -> None:
        data = {"profit_yoy": "N/A"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score == 0

    def test_profit_parse_error(self) -> None:
        data = {"profit_yoy": "abc"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score == 0


class TestCashFlowQuality:
    def test_cf_warning(self) -> None:
        data = {"cf_quality": "⚠️ 含金量较低，净利润与经营现金流不匹配"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 2
        assert any("现金流预警" in t for t in triggers)

    def test_cf_quality_ok(self) -> None:
        data = {"cf_quality": "现金流质量良好"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score == 0


class TestGrossMargin:
    def test_low_margin(self) -> None:
        data = {"gross_margin": "12%"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 1
        assert any("毛利率偏低" in t for t in triggers)

    def test_margin_na(self) -> None:
        data = {"gross_margin": "N/A"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score == 0

    def test_margin_parse_error(self) -> None:
        data = {"gross_margin": "abc"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score == 0


class TestVolumeAndChip:
    def test_volume_alert(self) -> None:
        data = {"volume_alert": "量比异动 2.5"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 2

    def test_chip_concentration(self) -> None:
        data = {"holder_trend": "筹码集中，大户吸筹"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 2
        assert any("💎" in t for t in triggers)

    def test_chip_dispersion(self) -> None:
        data = {"holder_trend": "筹码分散，散户接盘"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 1
        assert any("⚠️" in t for t in triggers)


class TestNorthFlow:
    def test_north_flow_with_market_cap(self) -> None:
        data = {
            "north_flow_3d": "北向资金 10亿",
            "market_cap_yi": 400,
        }
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 2

    def test_north_flow_small_ratio(self) -> None:
        data = {
            "north_flow_3d": "北向资金 3亿",
            "market_cap_yi": 600,
        }
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 1

    def test_north_flow_no_market_cap_large(self) -> None:
        data = {"north_flow_3d": "北向资金流入 8亿"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 2

    def test_north_flow_na(self) -> None:
        data = {"north_flow_3d": "N/A"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score == 0


class TestETFSignals:
    def test_etf_discount(self) -> None:
        data = {"premium_alert": "折价超过1%", "etf_premium": "-1.5%"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 2
        assert any("ETF折价套利" in t for t in triggers)

    def test_etf_premium(self) -> None:
        data = {"premium_alert": "溢价超过1%", "etf_premium": "2.1%"}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score >= 1
        assert any("ETF溢价风险" in t for t in triggers)

    def test_etf_no_alert(self) -> None:
        data = {"premium_alert": ""}
        need_deep, triggers, score = _evaluate_signals(data)
        assert score == 0


class TestEvaluateSignalsStepIntegration:
    def test_step_sets_state(self) -> None:
        step = EvaluateSignalsStep()
        state = AnalysisState(
            symbol="000001",
            stock_name="平安银行",
            raw_data={"volume_alert": "量比异动"},
        )
        result = step.run(state)
        assert result.signal_score == 2
        assert result.need_deep_analysis is False
        assert result.stage == "evaluate_signals"

    def test_step_deep_analysis(self) -> None:
        step = EvaluateSignalsStep()
        state = AnalysisState(
            symbol="000001",
            stock_name="平安银行",
            raw_data={
                "volume_alert": "量比异动",
                "holder_trend": "筹码集中，大户吸筹",
                "money_summary": "✅ 主力净流入 15亿",
                "market_cap_yi": 100,
            },
        )
        result = step.run(state)
        assert result.need_deep_analysis is True
        assert result.signal_score >= 3
