"""Centralised configuration for quant_lab v2.

Replaces the legacy ``ai_config`` global variables with a
``pydantic-settings``-based ``QuantLabSettings`` class that can be
driven by environment variables and/or an ``.env`` file.

Usage::

    from quant_lab.core.config import get_settings

    settings = get_settings()
    print(settings.llm_provider)      # "modelscope"
    print(settings.default_model)     # "deepseek-ai/DeepSeek-V3.2"
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from quant_lab.core.llm.catalog import ModelCatalog


class QuantLabSettings(BaseSettings):
    """All quant_lab configuration in one typed, testable place.

    Values are read from (in order of precedence):

    1. Environment variables (``QUANT_LAB_*`` prefix)
    2. ``.env`` file in the project root
    3. The defaults declared below
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="QUANT_LAB_",
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------
    llm_provider: str = Field(default="modelscope", description="Default LLM provider")
    llm_model: str | None = Field(default=None, description="Default model ID; None → provider default")
    llm_deep_model: str | None = Field(default=None, description="Model used for deep analysis")
    llm_timeout: float = Field(default=180.0, description="LLM API timeout in seconds")

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------
    yahoo_proxy_url: str = Field(
        default="http://127.0.0.1:7897",
        description="Proxy for Yahoo Finance / OpenBB calls",
    )
    network_retry_attempts: int = Field(default=3, description="HTTP retry attempts")
    network_timeout: float = Field(default=30.0, description="HTTP timeout for data sources")

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------
    memory_enabled: bool = Field(default=True, description="Enable T+1 memory loop")
    memory_db_path: str | None = Field(
        default=None,
        description="SQLite path for memory log; None → shared cache DB",
    )

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------
    pipeline_default_mode: str = Field(default="auto", description="Default analysis mode: fast/auto/deep")
    pipeline_prompt_version: str = Field(default="professional", description="Brain prompt style")

    # ------------------------------------------------------------------
    # Report / Output
    # ------------------------------------------------------------------
    report_dir: str | None = Field(
        default=None,
        description="Report output directory; None → ./Report",
    )

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------
    @property
    def default_model(self) -> str:
        """Return the effective default model ID.

        If ``llm_model`` is explicitly set, use it; otherwise ask the
        :class:`ModelCatalog` for the provider default.
        """
        if self.llm_model:
            return self.llm_model
        return ModelCatalog.default_model_for_provider(self.llm_provider)

    @property
    def effective_deep_model(self) -> str:
        """Return the model used for deep analysis.

        Falls back to :attr:`default_model` when ``llm_deep_model`` is
        not configured.
        """
        return self.llm_deep_model or self.default_model

    def model_dump_legacy(self) -> dict[str, Any]:
        """Return a dict shaped like the old ``ai_config.MODEL_CONFIGS`` entry.

        This is a compatibility helper for legacy code that expects the
        ``{"api_key_env", "base_url", "model", ...}`` shape.
        """
        info = ModelCatalog.lookup(self.default_model)
        if info is None:
            return {}
        return {
            "api_key_env": info.api_key_env,
            "base_url": info.base_url,
            "model": info.model_id,
            "description": info.description,
        }


@lru_cache(maxsize=1)
def get_settings() -> QuantLabSettings:
    """Return the singleton ``QuantLabSettings`` instance.

    The result is cached so that repeated calls are cheap.  In tests
    you can clear the cache with::

        get_settings.cache_clear()
        # or monkeypatch environment variables before calling get_settings()
    """
    return QuantLabSettings()
