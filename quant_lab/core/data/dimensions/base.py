"""Dimension fetcher abstractions for quant_lab."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class DimensionFetcher(Protocol):
    """Protocol for a business-dimension data fetcher.

    Each dimension (valuation, performance, sentiment, …) implements
    this protocol so that the registry and aggregator can treat them
    uniformly.
    """

    name: str

    def fetch(
        self, symbol: str, stock_name: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Return a flat dict of data fields for *symbol*.

        On failure the dict should contain ``_error`` and ``_dimension``
        keys rather than raising.

        ``**kwargs`` allows the aggregator to inject upstream context
        (e.g. prices, moving averages) when a dimension depends on it.
        """
        ...


def safe_fetch(
    func: Callable[..., dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    """Decorator that catches *all* exceptions and returns an error dict.

    The returned dict contains ``_error`` (exception message) and
    ``_dimension`` (fetcher name when available) so that the aggregator
    can continue with other dimensions instead of crashing the whole
    pipeline.
    """

    @functools.wraps(func)
    def wrapper(
        self: Any, symbol: str, stock_name: str, **kwargs: Any
    ) -> dict[str, Any]:
        dim_name = getattr(self, "name", func.__name__)
        try:
            return func(self, symbol, stock_name, **kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dimension %s failed for %s: %s", dim_name, symbol, exc)
            return {"_error": str(exc), "_dimension": dim_name}

    return wrapper
