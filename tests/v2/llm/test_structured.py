"""Tests for quant_lab.core.llm.structured.invoke_structured_or_freetext."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quant_lab.core.llm.structured import invoke_structured_or_freetext
from quant_lab.core.schemas import StockAnalysis, StockRating


class TestInvokeStructuredOrFreetext:
    """Tests for structured-output with graceful fallback."""

    def _make_mock_client(self) -> MagicMock:
        client = MagicMock()
        client.model_name = "deepseek-chat"
        return client

    def test_structured_success(self) -> None:
        client = self._make_mock_client()
        expected = StockAnalysis(
            ticker="000001.SZ",
            name="平安银行",
            rating=StockRating.BUY,
            confidence=0.85,
        )
        client.chat.return_value = expected

        result = invoke_structured_or_freetext(
            client,
            prompt="分析平安银行",
            schema=StockAnalysis,
        )

        assert isinstance(result, StockAnalysis)
        assert result.rating == StockRating.BUY
        client.chat.assert_called_once_with(
            "分析平安银行",
            schema=StockAnalysis,
            temperature=0.3,
        )

    def test_fallback_to_freetext(self) -> None:
        client = self._make_mock_client()

        # 第一次 structured 失败，第二次 free text 成功
        def _chat_side_effect(prompt: str, *, schema=None, temperature=0.3):
            if schema is not None:
                raise RuntimeError("structured failed")
            return "持有。市场震荡，估值合理。"

        client.chat.side_effect = _chat_side_effect

        result = invoke_structured_or_freetext(
            client,
            prompt="分析平安银行",
            schema=StockAnalysis,
            max_retries=1,
        )

        assert isinstance(result, str)
        assert "持有" in result
        assert client.chat.call_count == 2

    def test_retry_then_fallback(self) -> None:
        client = self._make_mock_client()
        call_count = 0

        def _chat_side_effect(prompt: str, *, schema=None, temperature=0.3):
            nonlocal call_count
            call_count += 1
            if schema is not None:
                raise RuntimeError("structured failed")
            return "买入"

        client.chat.side_effect = _chat_side_effect

        result = invoke_structured_or_freetext(
            client,
            prompt="分析",
            schema=StockAnalysis,
            max_retries=2,
        )

        assert result == "买入"
        assert call_count == 3  # 2 次 structured + 1 次 free text

    def test_total_failure_raises(self) -> None:
        client = self._make_mock_client()
        client.chat.side_effect = RuntimeError("total failure")

        with pytest.raises(RuntimeError, match="total failure"):
            invoke_structured_or_freetext(
                client,
                prompt="分析",
                schema=StockAnalysis,
                max_retries=1,
            )
