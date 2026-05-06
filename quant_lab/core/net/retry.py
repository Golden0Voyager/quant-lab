"""Unified retry strategy for HTTP clients."""

from __future__ import annotations

from urllib3.util.retry import Retry


def make_retry_strategy(
    total: int = 2,
    backoff_factor: float = 1.0,
    status_forcelist: tuple[int, ...] = (429, 500, 502, 503, 504),
    connect: int = 1,
    read: int = 1,
) -> Retry:
    """Return a urllib3 Retry instance suitable for requests.Session.

    Args:
        total: Max retry attempts across all error categories.
        backoff_factor: Sleep between retries = backoff_factor * (2 ** (retry - 1)).
        status_forcelist: HTTP status codes that trigger a retry.
        connect: Max retries for connection errors.
        read: Max retries for read errors.
    """
    return Retry(
        total=total,
        backoff_factor=backoff_factor,
        status_forcelist=list(status_forcelist),
        connect=connect,
        read=read,
    )
