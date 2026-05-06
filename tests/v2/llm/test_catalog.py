"""Tests for quant_lab.core.llm.catalog."""

from __future__ import annotations

import pytest

from quant_lab.core.llm.catalog import ModelCatalog


class TestModelCatalog:
    """Tests for ModelCatalog."""

    def test_lookup_existing(self) -> None:
        info = ModelCatalog.lookup("deepseek-ai/DeepSeek-V3.2")
        assert info is not None
        assert info.provider == "modelscope"
        assert info.supports_structured is True

    def test_lookup_nonexistent(self) -> None:
        assert ModelCatalog.lookup("nonexistent-model") is None

    def test_list_models_all(self) -> None:
        models = ModelCatalog.list_models()
        assert len(models) >= 6

    def test_list_models_by_provider(self) -> None:
        models = ModelCatalog.list_models(provider="modelscope")
        assert all(m.provider == "modelscope" for m in models)
        assert len(models) == 4

    def test_list_providers(self) -> None:
        providers = ModelCatalog.list_providers()
        assert "modelscope" in providers
        assert "dashscope" in providers
        assert "anthropic" in providers

    def test_default_model_for_provider(self) -> None:
        model = ModelCatalog.default_model_for_provider("dashscope")
        assert model == "glm-4.7"

    def test_default_model_for_unknown_provider(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider"):
            ModelCatalog.default_model_for_provider("unknown")
