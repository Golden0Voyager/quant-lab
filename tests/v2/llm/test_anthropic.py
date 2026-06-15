"""Tests for quant_lab.core.llm.anthropic."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from quant_lab.core.schemas import StockAnalysis, StockRating


class TestAnthropicClient:
    @pytest.fixture
    def client(self) -> MagicMock:
        with patch("quant_lab.core.llm.anthropic.Anthropic") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            from quant_lab.core.llm.anthropic import AnthropicClient

            c = AnthropicClient(model="claude-sonnet-4-6-20251101", api_key="fake-key")
            return c

    def test_model_name(self, client: MagicMock) -> None:
        assert client.model_name == "claude-sonnet-4-6-20251101"

    def test_chat_free_text(self, client: MagicMock) -> None:
        mock_block = MagicMock()
        mock_block.text = "持有。估值合理。"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        client._client.messages.create.return_value = mock_response

        result = client.chat("分析平安银行")
        assert result == "持有。估值合理。"
        client._client.messages.create.assert_called_once()

    def test_chat_structured_success(self, client: MagicMock) -> None:
        expected = StockAnalysis(
            ticker="000001.SZ",
            name="平安银行",
            rating=StockRating.HOLD,
            confidence=0.72,
        )
        mock_block = MagicMock()
        mock_block.text = json.dumps(expected.model_dump(mode="json"))
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        client._client.messages.create.return_value = mock_response

        result = client.chat("分析平安银行", schema=StockAnalysis)
        assert isinstance(result, StockAnalysis)
        assert result.rating == StockRating.HOLD

    def test_chat_structured_fallback(self, client: MagicMock) -> None:
        call_count = 0

        def _create_side_effect(**kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            mock_block = MagicMock()
            if kwargs.get("system"):
                mock_block.text = "not json"
            else:
                mock_block.text = "自由文本 fallback"
            mock_response = MagicMock()
            mock_response.content = [mock_block]
            return mock_response

        client._client.messages.create.side_effect = _create_side_effect

        result = client.chat("分析平安银行", schema=StockAnalysis)
        assert result == "自由文本 fallback"
        assert call_count == 2

    def test_chat_no_schema(self, client: MagicMock) -> None:
        mock_block = MagicMock()
        mock_block.text = "分析结果"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        client._client.messages.create.return_value = mock_response

        result = client.chat("分析", schema=None)
        assert result == "分析结果"

    def test_chat_with_base_url(self) -> None:
        with patch("quant_lab.core.llm.anthropic.Anthropic") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            from quant_lab.core.llm.anthropic import AnthropicClient

            AnthropicClient(
                model="claude-sonnet-4-6-20251101",
                api_key="fake-key",
                base_url="https://custom.api.com",
            )
            call_kwargs = mock_cls.call_args.kwargs
            assert call_kwargs["base_url"] == "https://custom.api.com"

    def test_chat_with_temperature(self, client: MagicMock) -> None:
        mock_block = MagicMock()
        mock_block.text = "分析结果"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        client._client.messages.create.return_value = mock_response

        client.chat("分析", temperature=0.5)
        call_kwargs = client._client.messages.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.5


class TestExtractText:
    def test_extract_text_success(self) -> None:
        from quant_lab.core.llm.anthropic import AnthropicClient

        mock_block = MagicMock()
        mock_block.text = "Hello"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        result = AnthropicClient._extract_text(mock_response)
        assert result == "Hello"

    def test_extract_text_no_text_block(self) -> None:
        from quant_lab.core.llm.anthropic import AnthropicClient

        mock_block = MagicMock()
        mock_block.text = ""
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        with pytest.raises(RuntimeError, match="No text block"):
            AnthropicClient._extract_text(mock_response)

    def test_extract_text_empty_content(self) -> None:
        from quant_lab.core.llm.anthropic import AnthropicClient

        mock_response = MagicMock()
        mock_response.content = []
        with pytest.raises(RuntimeError, match="No text block"):
            AnthropicClient._extract_text(mock_response)


class TestAnthropicImportError:
    def test_runtime_error_when_anthropic_not_installed(self) -> None:
        """Lines 13-15, 38: ImportError → RuntimeError on init."""
        import quant_lab.core.llm.anthropic as mod

        original = mod.Anthropic
        original_import_error = getattr(mod, "_IMPORT_ERROR", None)
        mod.Anthropic = None
        mod._IMPORT_ERROR = ImportError("no anthropic")
        try:
            with pytest.raises(RuntimeError, match="anthropic SDK is not installed"):
                mod.AnthropicClient(model="claude-sonnet-4-6-20251101", api_key="fake")
        finally:
            mod.Anthropic = original
            if original_import_error is not None:
                mod._IMPORT_ERROR = original_import_error
            elif hasattr(mod, "_IMPORT_ERROR") and original_import_error is None:
                del mod._IMPORT_ERROR
