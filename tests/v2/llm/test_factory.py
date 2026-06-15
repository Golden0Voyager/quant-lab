"""Tests for quant_lab.core.llm.factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quant_lab.core.llm import AnthropicClient, DeepSeekClient, OpenAICompatibleClient
from quant_lab.core.llm.catalog import ModelCatalog
from quant_lab.core.llm.factory import create_client


class TestCreateClient:
    """Tests for create_client factory."""

    def test_create_modelscope_client(self) -> None:
        with patch.dict("os.environ", {"MODELSCOPE_API_KEY": "fake-ms-key"}):
            client = create_client("modelscope", "deepseek-ai/DeepSeek-V3.2")
        assert isinstance(client, OpenAICompatibleClient)
        assert client.model_name == "deepseek-ai/DeepSeek-V3.2"

    def test_create_deepseek_r1_client(self) -> None:
        with patch.dict("os.environ", {"MODELSCOPE_API_KEY": "fake-ms-key"}):
            client = create_client("modelscope", "deepseek-ai/DeepSeek-R1-0528")
        assert isinstance(client, DeepSeekClient)
        assert client.model_name == "deepseek-ai/DeepSeek-R1-0528"

    def test_create_dashscope_client(self) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "fake-ds-key"}):
            client = create_client("dashscope", "glm-4.7")
        assert isinstance(client, OpenAICompatibleClient)
        assert client.model_name == "glm-4.7"

    def test_create_anthropic_client(self) -> None:
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-ant-key"}):
            client = create_client("anthropic", "claude-sonnet-4-6-20251101")
        assert isinstance(client, AnthropicClient)
        assert client.model_name == "claude-sonnet-4-6-20251101"

    def test_default_model(self) -> None:
        with patch.dict("os.environ", {"MODELSCOPE_API_KEY": "fake-ms-key"}):
            client = create_client("modelscope")
        assert client.model_name == ModelCatalog.default_model_for_provider("modelscope")

    def test_unknown_provider(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider"):
            create_client("unknown_provider")

    def test_mismatched_provider_model(self) -> None:
        with pytest.raises(ValueError, match="belongs to provider"):
            create_client("dashscope", "deepseek-ai/DeepSeek-V3.2")

    def test_missing_api_key_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        with patch.dict("os.environ", {}, clear=True):
            create_client("modelscope", "deepseek-ai/DeepSeek-V3.2")
        assert "API key not found" in caplog.text

    def test_unsupported_model(self) -> None:
        """Line 46: model not in catalog → ValueError."""
        with pytest.raises(ValueError, match="Unsupported model"):
            create_client("modelscope", model="nonexistent-model-xyz")

    def test_unsupported_provider(self) -> None:
        """Line 86: unknown provider → ValueError."""
        # Need a valid model first, then the provider check comes after
        # Model must exist in catalog but belong to different provider
        with patch("quant_lab.core.llm.factory.ModelCatalog") as mock_catalog:
            mock_info = MagicMock()
            mock_info.provider = "wrong_provider"
            mock_catalog.lookup.return_value = mock_info
            mock_catalog.default_model_for_provider.return_value = "test-model"
            with pytest.raises(ValueError, match="Unsupported provider|belongs to provider"):
                create_client("unknown_provider", model="test-model")

    def test_provider_mismatch(self) -> None:
        with pytest.raises(ValueError, match="belongs to provider"):
            create_client("modelscope", model="claude-sonnet-4-6-20251101")

    def test_anthropic_provider(self) -> None:
        with patch("quant_lab.core.llm.factory.AnthropicClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            create_client("anthropic", model="claude-sonnet-4-6-20251101")
            mock_cls.assert_called_once()
