"""SaveReportStep — 保存 Markdown / PDF 报告."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from quant_lab.core.pipeline.base import PipelineStep
from quant_lab.core.pipeline.state import AnalysisState
from quant_lab.core.schemas import StockAnalysis
from quant_lab.core.schemas.render import render_stock_analysis

try:
    from md2pdf_tool import md_to_pdf as _md_to_pdf
except Exception:  # pragma: no cover
    _md_to_pdf = None  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)


class SaveReportStep(PipelineStep):
    """将分析结果保存为 Markdown 报告，并尝试生成 PDF.

    Args:
        report_dir: 报告保存目录；*None* 时使用 ``./Report/YYMMDD``.
    """

    name = "save_report"

    def __init__(self, report_dir: str | None = None) -> None:
        self._report_dir = report_dir

    def _get_report_dir(self) -> str:
        if self._report_dir:
            return self._report_dir
        base = os.path.dirname(os.path.abspath(__file__))
        # Walk up to project root (assuming core/pipeline/steps/)
        project_root = os.path.abspath(os.path.join(base, "..", "..", "..", ".."))
        return os.path.join(project_root, "Report", datetime.now().strftime("%y%m%d"))

    def run(self, state: AnalysisState) -> AnalysisState:
        symbol = state.symbol
        stock_name = state.stock_name
        response = state.response
        analysis_mode = "deep" if state.need_deep_analysis else "fast"

        report_dir = self._get_report_dir()
        os.makedirs(report_dir, exist_ok=True)

        now = datetime.now()
        filename = os.path.join(
            report_dir,
            f"{now.strftime('%H%M%S')}_{stock_name}_{analysis_mode}.md",
        )

        # Build report content
        lines: list[str] = [
            f"# {stock_name}（{symbol}）投资分析",
            "",
            f"> 生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"> 分析模式: {'🧠 Brain 深度分析' if state.need_deep_analysis else '🤖 Worker 快速分析'}",
            "",
            "## 数据概览",
            "",
            f"- **资金面**: {state.raw_data.get('money_summary', 'N/A')}",
            f"- **技术面**: {state.raw_data.get('tech_summary', 'N/A')}",
            f"- **舆情**: {state.raw_data.get('news_summary', 'N/A')}",
            "",
        ]

        # If structured output exists, render it
        if state.structured_output and isinstance(state.structured_output, StockAnalysis):
            lines.append("## 结构化分析")
            lines.append("")
            lines.append(render_stock_analysis(state.structured_output))
            lines.append("")

        lines.extend(["## AI分析", "", response, ""])

        content = "\n".join(lines)

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("✅ Markdown 报告已保存: %s", filename)
        except Exception as exc:
            logger.error("❌ 保存报告失败: %s", exc)
            return self._stamp(
                state.model_copy(update={"error": f"save_report: {exc}"}),
                "save_report",
            )

        # Attempt PDF conversion
        pdf_path = filename.replace(".md", ".pdf")
        try:
            if _md_to_pdf is not None and _md_to_pdf(filename, pdf_path):
                logger.info("✅ PDF 报告已生成: %s", pdf_path)
        except Exception as exc:
            logger.warning("⚠️ PDF 生成失败: %s", exc)

        return self._stamp(
            state.model_copy(update={"report_path": filename}),
            "save_report",
        )
