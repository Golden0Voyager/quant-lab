"""Data source abstractions for quant_lab."""

from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable


class SourceResult(TypedDict, total=False):
    """Result wrapper for a data source fetch operation."""

    data: dict[str, Any]
    source_name: str
    confidence: float
    timestamp: str
    error: str


@runtime_checkable
class DataSource(Protocol):
    """Protocol for a data source adapter."""

    name: str

    def fetch(self, symbol: str) -> SourceResult:
        """Fetch raw data for *symbol* from this source.

        Returns a ``SourceResult`` dict.  On failure the ``error`` key
        should be populated and ``data`` may be omitted.
        """
        ...
