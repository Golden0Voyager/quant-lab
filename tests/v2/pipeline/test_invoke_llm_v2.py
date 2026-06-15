"""Extended tests for InvokeLLMStep — covering uncovered branches."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quant_lab.core.pipeline.steps.invoke_llm import InvokeLLMStep
from tests.v2.helpers import make_analysis_state, make_stock_analysis


class TestInvokeLLMStepV2:
    def test_model_not_supports_structured(self) -> None:
        """Lines 65-66: model doesn't support structured → fallback to free text."""
        step = InvokeLLMStep(provider="modelscope", model="deepseek-r1")
        state = make_analysis_state(prompt="分析平安银行")
        mock_info = MagicMock()
        mock_info.supports_structured = False
        with patch("quant_lab.core.pipeline.steps.invoke_llm.create_client") as mock_create, \
             patch("quant_lab.core.pipeline.steps.invoke_llm.ModelCatalog") as mock_catalog:
            mock_catalog.lookup.return_value = mock_info
            mock_client = MagicMock()
            mock_client.chat.return_value = "自由文本结果"
            mock_create.return_value = mock_client
            result = step.run(state)
        assert result.response == "自由文本结果"
        assert result.structured_output is None

    def test_structured_output_as_basemodel(self) -> None:
        """Line 77: result is BaseModel → store structured_output."""
        step = InvokeLLMStep(provider="modelscope", model="test-model")
        state = make_analysis_state(prompt="分析")
        expected = make_stock_analysis()
        with patch("quant_lab.core.pipeline.steps.invoke_llm.create_client") as mock_create, \
             patch("quant_lab.core.pipeline.steps.invoke_llm.invoke_structured_or_freetext") as mock_invoke:
            mock_client = MagicMock()
            mock_create.return_value = mock_client
            mock_invoke.return_value = expected
            result = step.run(state)
        assert result.structured_output == expected

    def test_structured_output_as_string(self) -> None:
        """Line 88: result is string → store as response."""
        step = InvokeLLMStep(provider="modelscope", model="test-model")
        state = make_analysis_state(prompt="分析")
        with patch("quant_lab.core.pipeline.steps.invoke_llm.create_client") as mock_create, \
             patch("quant_lab.core.pipeline.steps.invoke_llm.invoke_structured_or_freetext") as mock_invoke:
            mock_client = MagicMock()
            mock_create.return_value = mock_client
            mock_invoke.return_value = "自由文本结果"
            result = step.run(state)
        assert result.response == "自由文本结果"
        assert result.structured_output is None
