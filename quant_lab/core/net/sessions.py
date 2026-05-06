"""Explicit HTTP session factories to replace global monkey-patching."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from requests.adapters import HTTPAdapter  # type: ignore[import-untyped]

from .retry import make_retry_strategy

logger = logging.getLogger(__name__)

_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def make_china_session(
    *,
    timeout: float = 30.0,
    retries: int = 2,
    headers: dict[str, str] | None = None,
) -> Any:
    """Create a ``requests.Session`` tuned for China APIs.

    - ``trust_env=False`` to avoid system proxy mis-routing.
    - Real browser User-Agent.
    - Retry adapter for transient HTTP errors.
    - No proxy by default.

    Args:
        timeout: Request timeout in seconds (used by callers, not set on session).
        retries: Max retry attempts for the HTTP adapter.
        headers: Additional headers merged into the session.

    Returns:
        A configured ``requests.Session`` instance.
    """
    import requests  # type: ignore[import-untyped]

    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": _DEFAULT_UA})
    if headers:
        session.headers.update(headers)

    retry_strategy = make_retry_strategy(total=retries)
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def make_yahoo_session(
    *,
    proxy_url: str | None = None,
    timeout: float = 30.0,
    retries: int = 2,
) -> Any:
    """Create a ``requests.Session`` for Yahoo Finance (proxy-injected).

    Args:
        proxy_url: Explicit proxy URL; falls back to ``YAHOO_PROXY`` env var
            then ``http://127.0.0.1:7897``.
        timeout: Request timeout in seconds (used by callers).
        retries: Max retry attempts for the HTTP adapter.

    Returns:
        A configured ``requests.Session`` instance with proxies set.
    """
    import requests  # type: ignore[import-untyped]

    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": _DEFAULT_UA})

    _proxy = proxy_url or os.getenv("YAHOO_PROXY", "http://127.0.0.1:7897")
    if _proxy:
        session.proxies = {"http": _proxy, "https": _proxy}

    retry_strategy = make_retry_strategy(total=retries)
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def make_llm_session(
    *,
    proxy: str | None = None,
    timeout: float = 180.0,
    trust_env: bool = False,
) -> httpx.Client:
    """Create an ``httpx.Client`` for LLM API calls.

    Args:
        proxy: Explicit proxy URL (e.g. ``"http://127.0.0.1:7897"``).
        timeout: Request timeout in seconds.
        trust_env: Whether to read proxy settings from environment variables.

    Returns:
        A configured ``httpx.Client`` instance.
    """
    return httpx.Client(
        timeout=timeout,
        proxy=proxy,  # type: ignore[arg-type]
        trust_env=trust_env,
    )


def _install_patched_session_init() -> None:
    """Install the legacy monkey-patch for ``requests.Session.__init__``.

    This is a private compatibility helper kept for ``ai_config.init_global_network()``.
    New code should use :func:`make_china_session` or :func:`make_yahoo_session` directly.
    """
    import ai_config  # type: ignore[import-not-found]
    import requests  # type: ignore[import-untyped]
    from requests.adapters import HTTPAdapter  # type: ignore[import-untyped]

    _original_session_init = requests.Session.__init__

    def _patched_session_init(self: Any, *args: Any, **kwargs: Any) -> None:
        _original_session_init(self, *args, **kwargs)
        self.trust_env = False
        self.headers.update({"User-Agent": _DEFAULT_UA})

        if getattr(ai_config._yahoo_proxy, "active", False):
            proxy_url = getattr(ai_config._yahoo_proxy, "proxy_url", ai_config.YAHOO_PROXY_URL)
            if proxy_url:
                self.proxies = {"http": proxy_url, "https": proxy_url}

        retry_strategy = make_retry_strategy(total=2)
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.mount("http://", adapter)
        self.mount("https://", adapter)

    requests.Session.__init__ = _patched_session_init  # type: ignore[method-assign]
    logger.debug("Legacy monkey-patch installed for requests.Session.__init__")
