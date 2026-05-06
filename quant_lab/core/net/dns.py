"""DNS helpers: force IPv4 for unstable IPv6 endpoints."""

from __future__ import annotations

import socket
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

_original_getaddrinfo = socket.getaddrinfo


def force_ipv4_eastmoney() -> None:
    """Permanently patch ``socket.getaddrinfo`` to prefer IPv4 for eastmoney.com.

    This is a compatibility shim for legacy code paths that rely on the
    global monkey-patch. New code should use :func:`prefer_ipv4_for_host`
    as a context manager instead.
    """

    def _prefer_ipv4(
        host: bytes | str | None,
        port: bytes | str | int | None,
        family: int = 0,
        type: int = 0,  # noqa: A002
        proto: int = 0,
        flags: int = 0,
    ) -> Any:
        if host and isinstance(host, str) and "eastmoney.com" in host:
            return _original_getaddrinfo(
                host, port, socket.AF_INET, type, proto, flags
            )
        return _original_getaddrinfo(
            host, port, family, type, proto, flags
        )

    socket.getaddrinfo = _prefer_ipv4  # type: ignore[assignment]


@contextmanager
def prefer_ipv4_for_host(*hosts: str) -> Generator[None, None, None]:
    """Temporarily force IPv4 for the given hostnames.

    Example::

        with prefer_ipv4_for_host("push2his.eastmoney.com"):
            requests.get("https://push2his.eastmoney.com/api/...")

    Args:
        hosts: Hostnames that should be resolved via IPv4 only.
    """
    target_hosts = frozenset(hosts)

    def _prefer_ipv4(
        host: bytes | str | None,
        port: bytes | str | int | None,
        family: int = 0,
        type: int = 0,  # noqa: A002
        proto: int = 0,
        flags: int = 0,
    ) -> Any:
        if host and isinstance(host, str) and host in target_hosts:
            return _original_getaddrinfo(
                host, port, socket.AF_INET, type, proto, flags
            )
        return _original_getaddrinfo(
            host, port, family, type, proto, flags
        )

    socket.getaddrinfo = _prefer_ipv4  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.getaddrinfo = _original_getaddrinfo
