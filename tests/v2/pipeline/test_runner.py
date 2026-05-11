"""Tests for PipelineRunner."""

from __future__ import annotations

from quant_lab.core.pipeline.base import PipelineStep
from quant_lab.core.pipeline.runner import PipelineRunner
from quant_lab.core.pipeline.state import AnalysisState


class AddTriggerStep(PipelineStep):
    name = "add_trigger"

    def __init__(self, trigger: str) -> None:
        self.trigger = trigger

    def run(self, state: AnalysisState) -> AnalysisState:
        triggers = [*state.triggers, self.trigger]
        return self._stamp(state.model_copy(update={"triggers": triggers}), "add_trigger")


class FailStep(PipelineStep):
    name = "fail"

    def run(self, state: AnalysisState) -> AnalysisState:
        raise RuntimeError("boom")


class TestPipelineRunner:
    def test_sequential_execution(self) -> None:
        runner = PipelineRunner(
            [AddTriggerStep("a"), AddTriggerStep("b")],
        )
        state = AnalysisState(symbol="000001", stock_name="平安银行")
        result = runner.run(state)

        assert result.state.triggers == ["a", "b"]
        assert result.completed_steps == ["add_trigger", "add_trigger"]
        assert result.failed_steps == []

    def test_continue_on_error(self) -> None:
        runner = PipelineRunner(
            [AddTriggerStep("a"), FailStep(), AddTriggerStep("c")],
            abort_on_error=False,
        )
        state = AnalysisState(symbol="000001", stock_name="平安银行")
        result = runner.run(state)

        assert result.state.triggers == ["a", "c"]
        assert result.completed_steps == ["add_trigger", "add_trigger"]
        assert len(result.failed_steps) == 1
        assert result.failed_steps[0][0] == "fail"
        assert "boom" in result.failed_steps[0][1]

    def test_abort_on_error(self) -> None:
        runner = PipelineRunner(
            [AddTriggerStep("a"), FailStep(), AddTriggerStep("c")],
            abort_on_error=True,
        )
        state = AnalysisState(symbol="000001", stock_name="平安银行")
        result = runner.run(state)

        assert result.state.triggers == ["a"]
        assert result.completed_steps == ["add_trigger"]
        assert len(result.failed_steps) == 1

    def test_timestamps_recorded(self) -> None:
        step = AddTriggerStep("x")
        runner = PipelineRunner([step])
        state = AnalysisState(symbol="000001", stock_name="平安银行")
        result = runner.run(state)

        assert "add_trigger" in result.state.timestamps
