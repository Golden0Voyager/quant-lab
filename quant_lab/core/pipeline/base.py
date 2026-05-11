"""Pipeline base classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field

from quant_lab.core.pipeline.state import AnalysisState


class PipelineStep(ABC):
    """Abstract base class for a single pipeline step.

    Each step receives the current :class:`AnalysisState`, performs its work,
    and returns a (possibly updated) state.  Steps should be stateless — all
    mutable data lives in ``AnalysisState``.
    """

    name: str = ""

    @abstractmethod
    def run(self, state: AnalysisState) -> AnalysisState:
        """Execute the step.

        Args:
            state: Current pipeline state.

        Returns:
            Updated state.  The runner treats the returned object as the new
            canonical state.
        """

    def _stamp(self, state: AnalysisState, stage: str) -> AnalysisState:
        """Convenience helper: update ``stage`` and record a timestamp."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamps = {**state.timestamps, stage: now}
        return state.model_copy(update={"stage": stage, "timestamps": timestamps})


class PipelineResult(BaseModel):
    """Result of a :class:`PipelineRunner` execution."""

    state: AnalysisState
    completed_steps: list[str] = Field(default_factory=list)
    failed_steps: list[tuple[str, str]] = Field(default_factory=list)
