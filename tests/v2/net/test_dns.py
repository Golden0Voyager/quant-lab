"""Tests for quant_lab.core.net.dns."""

from __future__ import annotations

import socket
from unittest.mock import patch

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

    def test_matched_host_uses_ipv4(self) -> None:
        original = socket.getaddrinfo
        mock_result = [("AF_INET",)]
        with prefer_ipv4_for_host("push2his.eastmoney.com"):
            with patch("quant_lab.core.net.dns._original_getaddrinfo") as mock_orig:
                mock_orig.return_value = mock_result
                socket.getaddrinfo("push2his.eastmoney.com", 443)
                call_args = mock_orig.call_args
                assert call_args[0][2] == socket.AF_INET
        assert socket.getaddrinfo is original

    def test_unmatched_host_passes_through(self) -> None:
        original = socket.getaddrinfo
        mock_result = [("AF_UNSPEC",)]
        with prefer_ipv4_for_host("push2his.eastmoney.com"):
            with patch("quant_lab.core.net.dns._original_getaddrinfo") as mock_orig:
                mock_orig.return_value = mock_result
                socket.getaddrinfo("other.com", 443)
                call_args = mock_orig.call_args
                assert call_args[0][2] == 0
        assert socket.getaddrinfo is original


class TestForceIpv4Eastmoney:
    """Tests for the permanent-patch compatibility helper."""

    def test_patches_getaddrinfo(self) -> None:
        original = socket.getaddrinfo
        force_ipv4_eastmoney()
        try:
            assert socket.getaddrinfo is not original
        finally:
            socket.getaddrinfo = original

    def test_force_patches_getaddrinfo(self) -> None:
        original = socket.getaddrinfo
        force_ipv4_eastmoney()
        try:
            assert socket.getaddrinfo is not original
        finally:
            socket.getaddrinfo = original

    def test_eastmoney_host_uses_ipv4(self) -> None:
        original = socket.getaddrinfo
        force_ipv4_eastmoney()
        try:
            mock_result = [("AF_INET",)]
            with patch.object(socket, "getaddrinfo", wraps=socket.getaddrinfo) as mock_gai:
                mock_gai.return_value = mock_result
                with patch("quant_lab.core.net.dns._original_getaddrinfo", wraps=original) as mock_orig:
                    mock_orig.return_value = mock_result
                    result = socket.getaddrinfo("push2his.eastmoney.com", 443)
                    assert result == mock_result
        finally:
            socket.getaddrinfo = original

    def test_other_host_passes_through(self) -> None:
        original = socket.getaddrinfo
        force_ipv4_eastmoney()
        try:
            mock_result = [("AF_UNSPEC",)]
            with patch("quant_lab.core.net.dns._original_getaddrinfo") as mock_orig:
                mock_orig.return_value = mock_result
                socket.getaddrinfo("example.com", 443)
                call_args = mock_orig.call_args
                assert call_args[0][2] == 0
        finally:
            socket.getaddrinfo = original
