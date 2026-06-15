"""Extended tests for BuildPromptStep — covering uncovered branches."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quant_lab.core.pipeline.steps.build_prompt import BuildPromptStep
from tests.v2.helpers import make_analysis_state


class TestBuildPromptStepV2:
    def test_worker_prompt_with_valuation(self) -> None:
        """Worker prompt with valuation_summary (line 43)."""
        step = BuildPromptStep()
        state = make_analysis_state(
            raw_data={
                "name": "平安银行",
                "code": "000001",
                "type": "stock",
                "valuation_summary": "PE 15倍",
                "valuation_data_date": "2025-09-30",
                "dividend_yield": "3.5%",
                "dividend_percentile": "60%",
                "peg": "1.2",
                "peg_signal": "合理",
            },
            need_deep_analysis=False,
        )
        result = step.run(state)
        assert "估值维度" in result.prompt
        assert "PE 15倍" in result.prompt

    def test_worker_prompt_with_performance(self) -> None:
        """Worker prompt with performance_summary (line 50)."""
        step = BuildPromptStep()
        state = make_analysis_state(
            raw_data={
                "name": "平安银行",
                "code": "000001",
                "type": "stock",
                "performance_summary": "营收增长15%",
                "performance_data_date": "2025-09-30",
                "revenue_qoq": "5%",
                "profit_qoq": "8%",
                "cf_quality": "优质",
            },
            need_deep_analysis=False,
        )
        result = step.run(state)
        assert "业绩维度" in result.prompt
        assert "营收增长15%" in result.prompt

    def test_worker_prompt_with_consensus(self) -> None:
        """Worker prompt with consensus_summary (line 58)."""
        step = BuildPromptStep()
        state = make_analysis_state(
            raw_data={
                "name": "平安银行",
                "code": "000001",
                "type": "stock",
                "consensus_summary": "一致预期买入",
                "consensus_data_date": "2025-09-30",
            },
            need_deep_analysis=False,
        )
        result = step.run(state)
        assert "分析师预期" in result.prompt
        assert "一致预期买入" in result.prompt

    def test_worker_prompt_with_market_env(self) -> None:
        """Worker prompt with market_env_summary (lines 76-99)."""
        step = BuildPromptStep()
        state = make_analysis_state(
            raw_data={
                "name": "平安银行",
                "code": "000001",
                "type": "stock",
                "market_env_summary": "大盘偏暖",
                "market_env_data_date": "2025-09-30",
                "indices_overview": "沪深300 +1.2%",
                "market_total_volume": "8000亿",
                "market_volume_vs_5d": "+10%",
                "market_volume_signal": "放量",
                "market_up_count": "3000",
                "market_down_count": "1500",
                "market_flat_count": "200",
                "market_limit_up": "80",
                "market_limit_down": "20",
                "north_total_net_flow": "已停止实时披露",
                "south_total_net_flow": "+30亿",
                "south_flow_direction": "净流入港股",
                "shibor_overnight": "1.5%",
                "shibor_overnight_change": "+2bp",
                "shibor_1w": "1.8%",
                "monetary_signal": "平稳",
                "hot_sectors_top3": ["银行", "白酒"],
            },
            need_deep_analysis=False,
        )
        result = step.run(state)
        assert "大盘环境" in result.prompt
        assert "沪深300" in result.prompt

    def test_worker_prompt_with_global_macro(self) -> None:
        """Worker prompt with global_macro_summary (lines 87-92)."""
        step = BuildPromptStep()
        state = make_analysis_state(
            raw_data={
                "name": "平安银行",
                "code": "000001",
                "type": "stock",
                "market_env_summary": "大盘偏暖",
                "global_macro_summary": "美联储降息预期",
                "global_macro_update": "2025-09-30",
            },
            need_deep_analysis=False,
        )
        result = step.run(state)
        assert "全球宏观背景" in result.prompt
        assert "美联储降息预期" in result.prompt

    def test_worker_prompt_with_lockup(self) -> None:
        """Worker prompt with lockup_summary (lines 93-97)."""
        step = BuildPromptStep()
        state = make_analysis_state(
            raw_data={
                "name": "平安银行",
                "code": "000001",
                "type": "stock",
                "market_env_summary": "大盘偏暖",
                "lockup_summary": "低风险",
                "lockup_data_date": "2025-09-30",
            },
            need_deep_analysis=False,
        )
        result = step.run(state)
        assert "解禁风险" in result.prompt

    def test_worker_prompt_with_chip(self) -> None:
        """Worker prompt with chip_summary (lines 98-102)."""
        step = BuildPromptStep()
        state = make_analysis_state(
            raw_data={
                "name": "平安银行",
                "code": "000001",
                "type": "stock",
                "market_env_summary": "大盘偏暖",
                "chip_summary": "筹码集中",
                "chip_data_date": "2025-09-30",
            },
            need_deep_analysis=False,
        )
        result = step.run(state)
        assert "筹码分布" in result.prompt

    @patch("quant_lab.core.pipeline.steps.build_prompt.AnalysisMemoryLog")
    def test_memory_context_injection(self, mock_log_cls: MagicMock) -> None:
        """Memory context injection (lines 205-207)."""
        mock_log = MagicMock()
        mock_log.get_past_context.return_value = "历史决策：买入"
        mock_log_cls.return_value = mock_log

        step = BuildPromptStep(include_memory=True)
        state = make_analysis_state(
            raw_data={"name": "平安银行", "code": "000001"},
            need_deep_analysis=False,
        )
        result = step.run(state)
        assert "历史决策参考" in result.prompt
        assert "历史决策：买入" in result.prompt

    @patch("quant_lab.core.pipeline.steps.build_prompt.AnalysisMemoryLog")
    def test_memory_context_exception(self, mock_log_cls: MagicMock) -> None:
        """Memory context exception → skipped (lines 205-207)."""
        mock_log_cls.side_effect = Exception("memory fail")

        step = BuildPromptStep(include_memory=True)
        state = make_analysis_state(
            raw_data={"name": "平安银行", "code": "000001"},
            need_deep_analysis=False,
        )
        result = step.run(state)
        assert "_error" not in result.to_dict()
