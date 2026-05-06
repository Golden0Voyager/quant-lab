"""Network layer: explicit session factories for China APIs / Yahoo / LLM endpoints."""

from __future__ import annotations

from .dns import force_ipv4_eastmoney, prefer_ipv4_for_host
from .retry import make_retry_strategy
from .sessions import make_china_session, make_llm_session, make_yahoo_session

__all__ = [
    "force_ipv4_eastmoney",
    "make_china_session",
    "make_llm_session",
    "make_retry_strategy",
    "make_yahoo_session",
    "prefer_ipv4_for_host",
]
