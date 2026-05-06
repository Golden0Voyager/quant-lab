"""Tests for quant_lab.core.llm.openai_compat clients."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quant_lab.core.llm.openai_compat import DeepSeekClient, OpenAICompatibleClient
from quant_lab.core.schemas import StockAnalysis, StockRating


class TestOpenAICompatibleClient:
    """Tests for OpenAICompatibleClient."""

    @pytest.fixture
    def client(self) -> OpenAICompatibleClient:
        return OpenAICompatibleClient(
            model="deepseek-ai/DeepSeek-V3.2",
            api_key="fake-key",
            base_url="https://api.example.com/v1",
        )

    def test_model_name(self, client: OpenAICompatibleClient) -> None:
        assert client.model_name == "deepseek-ai/DeepSeek-V3.2"

    def test_chat_free_text(self, client: OpenAICompatibleClient) -> None:
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "持有。估值合理。"

        with patch.object(
            client._client.chat.completions,
            "create",
            return_value=mock_completion,
        ):
            result = client.chat("分析平安银行")

        assert result == "持有。估值合理。"

    def test_chat_structured(self, client: OpenAICompatibleClient) -> None:
        expected = StockAnalysis(
            ticker="000001.SZ",
            name="平安银行",
            rating=StockRating.HOLD,
            confidence=0.72,
        )
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.parsed = expected

        with patch.object(
            client._client.beta.chat.completions,
            "parse",
            return_value=mock_completion,
        ):
            result = client.chat("分析平安银行", schema=StockAnalysis)

        assert isinstance(result, StockAnalysis)
        assert result.rating == StockRating.HOLD

    def test_chat_structured_fallback(self, client: OpenAICompatibleClient) -> None:
        with patch.object(
            client._client.beta.chat.completions,
            "parse",
            side_effect=RuntimeError("parse failed"),
        ):
            mock_completion = MagicMock()
            mock_completion.choices = [MagicMock()]
            mock_completion.choices[0].message.content = "自由文本 fallback"

            with patch.object(
                client._client.chat.completions,
                "create",
                return_value=mock_completion,
            ):
                result = client.chat("分析平安银行", schema=StockAnalysis)

        assert result == "自由文本 fallback"


class TestDeepSeekClient:
    """Tests for DeepSeekClient reasoning_content handling."""

    def test_reasoning_content_logged(self) -> None:
        client = DeepSeekClient(
            model="deepseek-ai/DeepSeek-R1-0528",
            api_key="fake-key",
            base_url="https://api.example.com/v1",
        )

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        msg = MagicMock()
        msg.content = "最终结论"
        msg.reasoning_content = " lengthy reasoning chain " * 10
        mock_completion.choices[0].message = msg

        with patch.object(
            client._client.chat.completions,
            "create",
            return_value=mock_completion,
        ), patch("quant_lab.core.llm.openai_compat.logger") as mock_logger:
            result = client.chat("分析")
            assert result == "最终结论"
            mock_logger.debug.assert_called_once()
