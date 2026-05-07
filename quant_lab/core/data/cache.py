"""Cache facade for the quant_lab data layer.

Wraps the existing ``DataCache`` from ``data_cache`` with a cleaner
interface keyed by *(dimension, symbol)* pairs.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DataCacheFacade:
    """Thin wrapper around ``data_cache.DataCache``.

    The underlying cache uses *(symbol, category)* as its key.
    This facade exposes *(dimension, symbol)* to match the data-layer
    vocabulary, and auto-selects sensible TTLs.
    """

    # Default TTLs (seconds) when the caller does not supply one.
    _DEFAULT_TTLS: dict[str, int] = {
        "valuation": 24 * 60 * 60,
        "performance": 7 * 24 * 60 * 60,
        "sentiment": 24 * 60 * 60,
        "consensus": 7 * 24 * 60 * 60,
        "macro": 60 * 60,
        "market_env": 24 * 60 * 60,
        "lockup": 7 * 24 * 60 * 60,
        "chip": 24 * 60 * 60,
        "institution": 30 * 24 * 60 * 60,
        "competitor": 7 * 24 * 60 * 60,
        "smart_money": 24 * 60 * 60,
        "theme": 24 * 60 * 60,
        "support_resist": 24 * 60 * 60,
        "news": 60 * 60,
        "extended": 24 * 60 * 60,
    }

    def __init__(self, cache: Any | None = None) -> None:
        """*cache* may be an existing ``DataCache`` instance or *None*."""
        if cache is not None:
            self._cache = cache
            return

        # Lazy import so that the module can be imported without
        # creating a SQLite connection.
        from data_cache import DataCache

        self._cache = DataCache()

    def get(self, dimension: str, symbol: str) -> Any | None:
        """Return cached data for *dimension* × *symbol* or *None*."""
        return self._cache.get(symbol, dimension)

    def set(
        self,
        dimension: str,
        symbol: str,
        data: Any,
        ttl: int | None = None,
    ) -> None:
        """Store *data* under *dimension* × *symbol* with optional *ttl*."""
        if ttl is None:
            ttl = self._DEFAULT_TTLS.get(dimension, 24 * 60 * 60)
        self._cache.set(symbol, dimension, data, ttl)

    def invalidate(self, dimension: str, symbol: str) -> None:
        """Remove the entry for *dimension* × *symbol*."""
        # DataCache does not expose a direct delete; overwrite with None
        # and a very short TTL.
        self._cache.set(symbol, dimension, None, 1)
