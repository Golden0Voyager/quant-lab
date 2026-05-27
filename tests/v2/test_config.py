"""Tests for quant_lab.core.config."""

from __future__ import annotations

import warnings

import pytest

from quant_lab.core.config import QuantLabSettings, get_settings
from quant_lab.core.llm.catalog import ModelCatalog


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Ensure each test starts with a fresh settings cache."""
    get_settings.cache_clear()


class TestQuantLabSettings:
    """Tests for ``QuantLabSettings``."""

    def test_default_provider(self) -> None:
        s = QuantLabSettings()
        assert s.llm_provider == "modelscope"

    def test_default_model_fallback(self) -> None:
        s = QuantLabSettings(llm_model=None)
        assert s.default_model == ModelCatalog.default_model_for_provider("modelscope")

    def test_explicit_model_override(self) -> None:
        s = QuantLabSettings(llm_model="glm-4.7")
        assert s.default_model == "glm-4.7"

    def test_deep_model_fallback(self) -> None:
        s = QuantLabSettings(llm_model="deepseek-v3", llm_deep_model=None)
        assert s.effective_deep_model == "deepseek-v3"

    def test_deep_model_explicit(self) -> None:
        s = QuantLabSettings(llm_model="deepseek-v3", llm_deep_model="deepseek-r1")
        assert s.effective_deep_model == "deepseek-r1"

    def test_yahoo_proxy_default(self) -> None:
        s = QuantLabSettings()
        assert s.yahoo_proxy_url == "http://127.0.0.1:7897"

    def test_memory_enabled_default(self) -> None:
        s = QuantLabSettings()
        assert s.memory_enabled is True

    def test_model_dump_legacy_shape(self) -> None:
        s = QuantLabSettings()
        legacy = s.model_dump_legacy()
        assert "api_key_env" in legacy
        assert "base_url" in legacy
        assert "model" in legacy

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("QUANT_LAB_LLM_PROVIDER", "dashscope")
        monkeypatch.setenv("QUANT_LAB_LLM_MODEL", "glm-4.7")
        # Clear cache so the new env vars are picked up
        get_settings.cache_clear()
        s = get_settings()
        assert s.llm_provider == "dashscope"
        assert s.llm_model == "glm-4.7"
        assert s.default_model == "glm-4.7"


class TestGetSettingsSingleton:
    """Tests for ``get_settings()`` singleton behaviour."""

    def test_returns_same_instance(self) -> None:
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_cache_clear_creates_new(self, monkeypatch: pytest.MonkeyPatch) -> None:
        get_settings.cache_clear()
        s1 = get_settings()
        monkeypatch.setenv("QUANT_LAB_LLM_PROVIDER", "anthropic")
        get_settings.cache_clear()
        s2 = get_settings()
        assert s1 is not s2
        assert s2.llm_provider == "anthropic"


class TestAiConfigBackwardCompatibility:
    """Legacy ``ai_config`` functions still work but emit DeprecationWarning."""

    def test_get_primary_model_name(self) -> None:
        import ai_config

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            model = ai_config.get_primary_model_name()
            assert model == "deepseek-ai/DeepSeek-V3.2"
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)

    def test_get_backup_model_name(self) -> None:
        import ai_config

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            model = ai_config.get_backup_model_name()
            assert model == "Qwen/Qwen3.5-397B-A17B"
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)

    def test_get_current_config(self) -> None:
        import ai_config

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            cfg = ai_config.get_current_config()
            assert "api_key_env" in cfg
            assert "base_url" in cfg
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
