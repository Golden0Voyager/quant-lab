"""Tests for quant_lab.core.memory.reflection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quant_lab.core.memory.reflection import Reflector


class TestReflector:
    """Tests for ``Reflector.reflect_on_decision``."""

    @patch("quant_lab.core.memory.reflection.create_client")
    def test_reflect_generates_text(self, mock_create_client: MagicMock) -> None:
        client = MagicMock()
        client.chat.return_value = "  判断正确，资金持续流入，下次可加大仓位。  "
        mock_create_client.return_value = client

        reflector = Reflector(provider="modelscope", model="deepseek-v3")
        decision = {
            "symbol": "000001",
            "date": "2026-05-27",
            "rating": "买入",
            "confidence": 0.85,
            "triggers": '["资金异动"]',
        }
        result = reflector.reflect_on_decision(decision, raw_return=0.05, alpha_return=0.02)

        assert "判断正确" in result
        client.chat.assert_called_once()
        args, _ = client.chat.call_args
        assert "000001" in args[0]
        assert "5.00%" in args[0]

    @patch("quant_lab.core.memory.reflection.create_client")
    def test_reflect_handles_failure(self, mock_create_client: MagicMock) -> None:
        client = MagicMock()
        client.chat.side_effect = Exception("API error")
        mock_create_client.return_value = client

        reflector = Reflector()
        decision = {"symbol": "000001", "date": "2026-05-27"}
        result = reflector.reflect_on_decision(decision, 0.0, 0.0)

        assert result == ""
