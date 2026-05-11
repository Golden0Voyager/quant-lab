"""Pipeline runner — sequential execution with error handling."""

from __future__ import annotations

import logging

from quant_lab.core.pipeline.base import PipelineResult, PipelineStep
from quant_lab.core.pipeline.state import AnalysisState

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Execute a list of :class:`PipelineStep` instances in order.

    Args:
        steps: Ordered list of steps to run.
        abort_on_error: If ``True``, stop at the first failing step and
            return immediately.  If ``False``, log the error and continue.
    """

    def __init__(
        self,
        steps: list[PipelineStep],
        *,
        abort_on_error: bool = False,
    ) -> None:
        self.steps = steps
        self.abort_on_error = abort_on_error

    def run(self, state: AnalysisState) -> PipelineResult:
        """Execute all steps sequentially.

        Args:
            state: Initial pipeline state (usually created from symbol/name).

        Returns:
            A :class:`PipelineResult` containing the final state and
            execution bookkeeping.
        """
        completed: list[str] = []
        failed: list[tuple[str, str]] = []

        current = state
        for step in self.steps:
            step_name = step.name or step.__class__.__name__
            try:
                current = step.run(current)
                completed.append(step_name)
                logger.debug("✅ Step '%s' completed (stage=%s)", step_name, current.stage)
            except Exception as exc:  # noqa: BLE001
                msg = f"{type(exc).__name__}: {exc}"
                logger.warning("❌ Step '%s' failed: %s", step_name, msg)
                failed.append((step_name, msg))
                if self.abort_on_error:
                    break

        return PipelineResult(
            state=current,
            completed_steps=completed,
            failed_steps=failed,
        )
