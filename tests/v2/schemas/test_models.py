"""Tests for quant_lab.core.schemas models and render functions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from quant_lab.core.schemas import (
    BatchValuationResult,
    FundAnalysis,
    FundRating,
    IndexAnalysis,
    MarketAssessment,
    StockAnalysis,
    StockRating,
    render_batch_result,
    render_fund_analysis,
    render_index_analysis,
    render_stock_analysis,
)


class TestStockAnalysis:
    """Tests for StockAnalysis schema."""

    def test_basic_creation(self) -> None:
        analysis = StockAnalysis(
            ticker="000001.SZ",
            name="平安银行",
            rating=StockRating.BUY,
            confidence=0.85,
            key_signals=["估值低", "资金流入"],
            risk_alerts=["宏观风险"],
            target_price=15.0,
            time_horizon="中线",
            core_logic="低估值叠加资金流入",
            strategy_short_term="逢低吸纳",
            strategy_mid_term="持有待涨",
        )
        assert analysis.rating == StockRating.BUY
        assert analysis.confidence == 0.85
        assert analysis.target_price == 15.0

    def test_confidence_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            StockAnalysis(
                ticker="000001.SZ",
                name="平安银行",
                rating=StockRating.HOLD,
                confidence=1.5,
            )

        with pytest.raises(ValidationError):
            StockAnalysis(
                ticker="000001.SZ",
                name="平安银行",
                rating=StockRating.HOLD,
                confidence=-0.3,
            )

    def test_confidence_rounding(self) -> None:
        analysis = StockAnalysis(
            ticker="000001.SZ",
            name="平安银行",
            rating=StockRating.HOLD,
            confidence=0.755,
        )
        assert analysis.confidence == 0.76

    def test_invalid_rating(self) -> None:
        with pytest.raises(ValidationError):
            StockAnalysis(
                ticker="000001.SZ",
                name="平安银行",
                rating="INVALID",  # type: ignore[arg-type]
                confidence=0.5,
            )

    def test_render(self) -> None:
        analysis = StockAnalysis(
            ticker="000001.SZ",
            name="平安银行",
            rating=StockRating.BUY,
            confidence=0.85,
            key_signals=["信号1", "信号2"],
            risk_alerts=["风险1"],
            target_price=15.0,
            time_horizon="中线",
            core_logic="核心逻辑",
            strategy_short_term="短线策略",
            strategy_mid_term="中线策略",
        )
        md = render_stock_analysis(analysis)
        assert "平安银行" in md
        assert "买入" in md
        assert "85%" in md
        assert "信号1" in md
        assert "风险1" in md
        assert "¥15.00" in md
        assert "短线策略" in md
        assert "中线策略" in md


class TestRenderStockAnalysisExtended:
    def test_with_strategies(self) -> None:
        a = StockAnalysis(
            ticker="000001",
            name="平安银行",
            rating=StockRating.HOLD,
            confidence=0.7,
            strategy_short_term="短线观望",
            strategy_mid_term="中线持有",
        )
        result = render_stock_analysis(a)
        assert "短线" in result
        assert "中线" in result

    def test_without_strategies(self) -> None:
        a = StockAnalysis(
            ticker="000001",
            name="平安银行",
            rating=StockRating.HOLD,
            confidence=0.7,
        )
        result = render_stock_analysis(a)
        assert "操作策略" not in result


class TestFundAnalysis:
    """Tests for FundAnalysis schema."""

    def test_basic_creation(self) -> None:
        analysis = FundAnalysis(
            ticker="510300.SH",
            name="沪深300ETF",
            rating=FundRating.HOLD,
            confidence=0.6,
            holdings_penetration_summary="重仓金融、消费",
            target_nav=4.5,
        )
        assert analysis.rating == FundRating.HOLD
        assert analysis.target_nav == 4.5

    def test_render(self) -> None:
        analysis = FundAnalysis(
            ticker="510300.SH",
            name="沪深300ETF",
            rating=FundRating.HOLD,
            confidence=0.6,
            key_signals=["信号A"],
            risk_alerts=["风险A"],
            holdings_penetration_summary="前十大重仓：茅台、平安...",
        )
        md = render_fund_analysis(analysis)
        assert "沪深300ETF" in md
        assert "持仓穿透" in md
        assert "茅台、平安" in md


class TestRenderFundAnalysisExtended:
    def test_with_target_nav(self) -> None:
        a = FundAnalysis(
            ticker="399050",
            name="中证互联网",
            rating=FundRating.BUY,
            confidence=0.8,
            target_nav=1.2345,
            time_horizon="6个月",
        )
        result = render_fund_analysis(a)
        assert "1.2345" in result
        assert "6个月" in result

    def test_with_holdings_penetration(self) -> None:
        a = FundAnalysis(
            ticker="399050",
            name="中证互联网",
            rating=FundRating.HOLD,
            confidence=0.7,
            holdings_penetration_summary="前十大重仓占比60%",
        )
        result = render_fund_analysis(a)
        assert "持仓穿透" in result


class TestIndexAnalysis:
    """Tests for IndexAnalysis schema."""

    def test_basic_creation(self) -> None:
        analysis = IndexAnalysis(
            ticker="000300.SH",
            name="沪深300",
            market_assessment=MarketAssessment.CONSOLIDATION,
            confidence=0.7,
            risk_level=3,
            suggested_position="半仓",
        )
        assert analysis.market_assessment == MarketAssessment.CONSOLIDATION
        assert analysis.risk_level == 3

    def test_invalid_risk_level(self) -> None:
        with pytest.raises(ValidationError):
            IndexAnalysis(
                ticker="000300.SH",
                name="沪深300",
                market_assessment=MarketAssessment.BULL,
                confidence=0.5,
                risk_level=6,
                suggested_position="满仓",
            )

    def test_render(self) -> None:
        analysis = IndexAnalysis(
            ticker="000300.SH",
            name="沪深300",
            market_assessment=MarketAssessment.BULL,
            confidence=0.8,
            risk_level=2,
            key_signals=["信号X"],
            risk_alerts=["风险X"],
            suggested_position="满仓",
            core_logic="牛市格局未变",
        )
        md = render_index_analysis(analysis)
        assert "沪深300" in md
        assert "牛市" in md
        assert "满仓" in md
        assert "80%" in md


class TestRenderIndexAnalysisExtended:
    def test_basic(self) -> None:
        a = IndexAnalysis(
            ticker="000300",
            name="沪深300",
            market_assessment=MarketAssessment.CONSOLIDATION,
            confidence=0.7,
            risk_level=3,
            suggested_position="半仓",
        )
        result = render_index_analysis(a)
        assert "震荡市" in result
        assert "半仓" in result


class TestBatchValuationResult:
    """Tests for BatchValuationResult schema."""

    def test_creation_with_stock_analysis(self) -> None:
        stock = StockAnalysis(
            ticker="000001.SZ",
            name="平安银行",
            rating=StockRating.BUY,
            confidence=0.85,
        )
        result = BatchValuationResult(
            ticker="000001.SZ",
            name="平安银行",
            analysis=stock,
            metrics_digest="PE 5.2 | PB 0.8",
        )
        assert result.analysis.confidence == 0.85
        assert "PE 5.2" in result.metrics_digest

    def test_render(self) -> None:
        stock = StockAnalysis(
            ticker="000001.SZ",
            name="平安银行",
            rating=StockRating.BUY,
            confidence=0.85,
        )
        result = BatchValuationResult(
            ticker="000001.SZ",
            name="平安银行",
            analysis=stock,
            metrics_digest="**PE**: 5.2",
        )
        md = render_batch_result(result)
        assert "平安银行" in md
        assert "**PE**: 5.2" in md


class TestRenderBatchResultExtended:
    def test_basic(self) -> None:
        analysis = StockAnalysis(
            ticker="000001",
            name="平安银行",
            rating=StockRating.HOLD,
            confidence=0.7,
        )
        result = BatchValuationResult(
            ticker="000001",
            name="平安银行",
            analysis=analysis,
            metrics_digest="PE=5.2",
        )
        rendered = render_batch_result(result)
        assert "PE=5.2" in rendered
