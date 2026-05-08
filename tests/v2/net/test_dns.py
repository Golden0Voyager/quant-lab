"""Tests for quant_lab.core.net.dns."""

from __future__ import annotations

import socket

import pytest

from quant_lab.core.net.dns import force_ipv4_eastmoney, prefer_ipv4_for_host


class TestPreferIpv4ForHost:
    """Tests for the context-manager variant."""

    def test_restores_original_getaddrinfo(self) -> None:
        original = socket.getaddrinfo
        with prefer_ipv4_for_host("example.com"):
            pass
        assert socket.getaddrinfo is original

    def test_changes_getaddrinfo_inside_context(self) -> None:
        original = socket.getaddrinfo
        with prefer_ipv4_for_host("example.com"):
            assert socket.getaddrinfo is not original
        assert socket.getaddrinfo is original

    def test_restores_on_exception(self) -> None:
        original = socket.getaddrinfo
        with pytest.raises(RuntimeError), prefer_ipv4_for_host("example.com"):
            assert socket.getaddrinfo is not original
            raise RuntimeError("boom")
        assert socket.getaddrinfo is original


class TestForceIpv4Eastmoney:
    """Tests for the permanent-patch compatibility helper."""

    def test_patches_getaddrinfo(self) -> None:
        original = socket.getaddrinfo
        force_ipv4_eastmoney()
        try:
            assert socket.getaddrinfo is not original
        finally:
            # Restore to avoid polluting other tests
            socket.getaddrinfo = original
