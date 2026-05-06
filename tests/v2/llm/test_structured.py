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
        client._model = "deepseek-chat"
        return client

    def test_structured_success(self) -> None:
        client = self._make_mock_client()
        expected = StockAnalysis(
            ticker="000001.SZ",
            name="平安银行",
            rating=StockRating.BUY,
            confidence=0.85,
        )

        # Mock parse API success
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.parsed = expected
        client.beta.chat.completions.parse.return_value = mock_completion

        result = invoke_structured_or_freetext(
            client,
            prompt="分析平安银行",
            schema=StockAnalysis,
        )

        assert isinstance(result, StockAnalysis)
        assert result.rating == StockRating.BUY
        client.beta.chat.completions.parse.assert_called_once()

    def test_fallback_to_freetext(self) -> None:
        client = self._make_mock_client()

        # Mock parse API failure
        client.beta.chat.completions.parse.side_effect = RuntimeError("parse error")

        # Mock create API success
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "持有。市场震荡，估值合理。"
        client.chat.completions.create.return_value = mock_completion

        result = invoke_structured_or_freetext(
            client,
            prompt="分析平安银行",
            schema=StockAnalysis,
            max_retries=1,
        )

        assert isinstance(result, str)
        assert "持有" in result
        client.beta.chat.completions.parse.assert_called_once()
        client.chat.completions.create.assert_called_once()

    def test_retry_then_fallback(self) -> None:
        client = self._make_mock_client()
        client.beta.chat.completions.parse.side_effect = RuntimeError("parse error")

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "买入"
        client.chat.completions.create.return_value = mock_completion

        result = invoke_structured_or_freetext(
            client,
            prompt="分析",
            schema=StockAnalysis,
            max_retries=2,
        )

        assert result == "买入"
        assert client.beta.chat.completions.parse.call_count == 2

    def test_total_failure_raises(self) -> None:
        client = self._make_mock_client()
        client.beta.chat.completions.parse.side_effect = RuntimeError("parse error")
        client.chat.completions.create.side_effect = RuntimeError("create error")

        with pytest.raises(RuntimeError, match="create error"):
            invoke_structured_or_freetext(
                client,
                prompt="分析",
                schema=StockAnalysis,
                max_retries=1,
            )
