"""Tests for quant_lab.core.llm.factory."""

from __future__ import annotations

from unittest.mock import patch

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
