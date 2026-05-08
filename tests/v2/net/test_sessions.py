"""Tests for quant_lab.core.net.sessions."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx

from quant_lab.core.net.sessions import (
    make_china_session,
    make_llm_session,
    make_yahoo_session,
)


class TestMakeChinaSession:
    """Tests for make_china_session."""

    def test_trust_env_false(self) -> None:
        session = make_china_session()
        assert session.trust_env is False

    def test_user_agent_set(self) -> None:
        session = make_china_session()
        assert "Mozilla/5.0" in session.headers.get("User-Agent", "")

    def test_no_proxy_by_default(self) -> None:
        session = make_china_session()
        assert session.proxies == {}

    def test_custom_headers(self) -> None:
        session = make_china_session(headers={"X-Custom": "val"})
        assert session.headers["X-Custom"] == "val"

    def test_retry_adapter_mounted(self) -> None:
        session = make_china_session()
        adapter = session.get_adapter("https://example.com")
        assert adapter is not None


class TestMakeYahooSession:
    """Tests for make_yahoo_session."""

    def test_proxy_from_argument(self) -> None:
        session = make_yahoo_session(proxy_url="http://proxy:8080")
        assert session.proxies["http"] == "http://proxy:8080"
        assert session.proxies["https"] == "http://proxy:8080"

    def test_proxy_from_env(self) -> None:
        with patch.dict(os.environ, {"YAHOO_PROXY": "http://env-proxy:9090"}):
            session = make_yahoo_session()
        assert session.proxies["http"] == "http://env-proxy:9090"

    def test_fallback_default_proxy(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            session = make_yahoo_session()
        assert "127.0.0.1:7897" in session.proxies.get("http", "")

    def test_trust_env_false(self) -> None:
        session = make_yahoo_session()
        assert session.trust_env is False


class TestMakeLlmSession:
    """Tests for make_llm_session."""

    def test_returns_httpx_client(self) -> None:
        client = make_llm_session()
        assert isinstance(client, httpx.Client)

    def test_default_no_proxy(self) -> None:
        with patch("quant_lab.core.net.sessions.httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            make_llm_session()
            mock_client.assert_called_once_with(
                timeout=180.0,
                proxy=None,
                trust_env=False,
            )

    def test_explicit_proxy(self) -> None:
        with patch("quant_lab.core.net.sessions.httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            make_llm_session(proxy="http://proxy:8080")
            mock_client.assert_called_once_with(
                timeout=180.0,
                proxy="http://proxy:8080",
                trust_env=False,
            )

    def test_trust_env_false(self) -> None:
        with patch("quant_lab.core.net.sessions.httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            make_llm_session()
            assert mock_client.call_args.kwargs["trust_env"] is False

    def test_trust_env_true(self) -> None:
        with patch("quant_lab.core.net.sessions.httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            make_llm_session(trust_env=True)
            assert mock_client.call_args.kwargs["trust_env"] is True

    def test_timeout(self) -> None:
        with patch("quant_lab.core.net.sessions.httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            make_llm_session(timeout=60.0)
            assert mock_client.call_args.kwargs["timeout"] == 60.0
