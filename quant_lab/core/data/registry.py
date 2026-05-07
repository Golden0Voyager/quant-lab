"""Dimension registry for quant_lab.

Maps human-readable dimension names (e.g. ``"valuation"``) to
``DimensionFetcher`` implementations and optionally auto-manages the
cache layer.
"""

from __future__ import annotations

import logging
from typing import Any

from quant_lab.core.data.cache import DataCacheFacade
from quant_lab.core.data.dimensions.base import DimensionFetcher

logger = logging.getLogger(__name__)


class DimensionRegistry:
    """Registry that binds dimension names to fetcher objects.

    When ``cache`` is supplied, ``fetch`` will:
    1. Attempt a cache hit.
    2. On miss, run the registered fetcher.
    3. Write the result back to the cache.
    """

    def __init__(self, cache: DataCacheFacade | None = None) -> None:
        self._fetchers: dict[str, DimensionFetcher] = {}
        self._cache = cache

    def register(self, name: str, fetcher: DimensionFetcher) -> None:
        """Bind *name* to *fetcher*."""
        if name in self._fetchers:
            logger.warning("Overwriting existing dimension %r", name)
        self._fetchers[name] = fetcher
        logger.debug("Registered dimension %r → %s", name, type(fetcher).__name__)

    def get(self, name: str) -> DimensionFetcher | None:
        """Return the fetcher registered under *name*, or *None*."""
        return self._fetchers.get(name)

    def fetch(
        self,
        name: str,
        symbol: str,
        stock_name: str,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Fetch a single dimension by *name*.

        The result is always a flat ``dict``.  On failure the dict
        contains ``_error`` and ``_dimension`` keys.
        """
        fetcher = self._fetchers.get(name)
        if fetcher is None:
            return {
                "_error": f"Dimension {name!r} is not registered",
                "_dimension": name,
            }

        # 1. Cache read
        if use_cache and self._cache is not None:
            cached: dict[str, Any] | None = self._cache.get(name, symbol)
            if cached is not None:
                logger.debug("Cache hit for %s × %s", name, symbol)
                return cached

        # 2. Execute fetcher
        result: dict[str, Any] = fetcher.fetch(symbol, stock_name)

        # 3. Cache write
        if use_cache and self._cache is not None and "_error" not in result:
            self._cache.set(name, symbol, result)

        return result

    def fetch_all(
        self,
        symbol: str,
        stock_name: str,
        names: list[str] | None = None,
        *,
        use_cache: bool = True,
    ) -> dict[str, dict[str, Any]]:
        """Fetch multiple dimensions and return a nested dict.

        The top-level keys are dimension names; values are the flat
        result dicts from each fetcher.
        """
        if names is None:
            names = list(self._fetchers.keys())

        return {
            name: self.fetch(name, symbol, stock_name, use_cache=use_cache)
            for name in names
        }

    def list_dimensions(self) -> list[str]:
        """Return all registered dimension names."""
        return list(self._fetchers.keys())
