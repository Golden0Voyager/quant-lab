"""v2 CLI entry point — wraps the v2 pipeline in user-facing commands.

This module is intentionally separate from ``main.py`` so that the legacy
CLI can remain untouched while v2 matures.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from quant_lab.core.pipeline.builders import (
    build_auto_pipeline,
    build_deep_pipeline,
    build_fast_pipeline,
)
from quant_lab.core.pipeline.runner import PipelineRunner
from quant_lab.core.pipeline.state import AnalysisState

logger = logging.getLogger(__name__)

_DEFAULT_WATCHLISTS: dict[str, list[dict]] = {
    "my": [
        {"code": "002683", "name": "广东宏大"},
        {"code": "002179", "name": "中航光电"},
        {"code": "002049", "name": "紫光国微"},
        {"code": "688122", "name": "西部超导"},
        {"code": "603508", "name": "思维列控"},
        {"code": "600150", "name": "中国船舶"},
        {"code": "002267", "name": "陕天然气"},
        {"code": "002056", "name": "横店东磁"},
        {"code": "399050", "name": "中证互联网"},
        {"code": "399441", "name": "国证生物医药"},
        {"code": "399971", "name": "中证光伏"},
        {"code": "399976", "name": "中证新能源汽车"},
        {"code": "000932", "name": "中证消费"},
    ],
    "dad": [
        {"code": "000988", "name": "华工科技"},
        {"code": "600990", "name": "四创电子"},
        {"code": "300348", "name": "长亮科技"},
        {"code": "000063", "name": "中兴通讯"},
        {"code": "601727", "name": "上海电气"},
        {"code": "600729", "name": "重庆百货"},
        {"code": "300753", "name": "爱朋医疗"},
        {"code": "002838", "name": "道恩股份"},
        {"code": "002086", "name": "东方海洋"},
        {"code": "002647", "name": "ST仁东"},
    ],
    "erin": [
        {"code": "300059", "name": "东方财富"},
        {"code": "601088", "name": "中国神华"},
        {"code": "600901", "name": "江苏金租"},
        {"code": "600690", "name": "海尔智家"},
        {"code": "002475", "name": "立讯精密"},
        {"code": "688122", "name": "西部超导"},
    ],
}


def _load_watchlist(name: str) -> list[dict]:
    """Load a watchlist from ``watchlists.json`` (or fall back to built-ins)."""
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_file = os.path.join(script_dir, "watchlists.json")

    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            if name in config and "stocks" in config[name]:
                return [
                    {"code": s["code"], "name": s["name"], "tags": s.get("tags", [])}
                    for s in config[name]["stocks"]
                ]
        except Exception as exc:
            logger.warning("Failed to load watchlists.json: %s", exc)

    return [
        {"code": s["code"], "name": s["name"], "tags": []}
        for s in _DEFAULT_WATCHLISTS.get(name, [])
    ]


def _infer_asset_type(item: dict) -> str | None:
    """Infer asset type from tags (fund / etf / stock)."""
    tags = [t.lower() for t in item.get("tags", [])]
    if "基金" in tags or "fund" in tags:
        return "fund"
    if "etf" in tags:
        return "etf"
    return None  # let caller detect


def _select_builder(analysis_mode: str):
    """Return the appropriate builder for *analysis_mode*."""
    if analysis_mode == "deep":
        return build_deep_pipeline
    if analysis_mode == "fast":
        return build_fast_pipeline
    return build_auto_pipeline


def _report_dir() -> str:
    """Return the default report directory ``Report/YYMMDD``."""
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(script_dir, "Report", datetime.now().strftime("%y%m%d"))


def run_v2_single_stock(
    symbol: str,
    stock_name: str | None = None,
    analysis_mode: str = "auto",
    prompt_version: str = "professional",
    provider: str = "modelscope",
    model: str | None = None,
    deep_model: str | None = None,
    use_cache: bool = True,
) -> None:
    """Run the v2 pipeline for a single stock and print / save the report.

    Args:
        symbol: Stock / ETF / index code.
        stock_name: Human-readable name (optional, falls back to *symbol*).
        analysis_mode: ``fast`` | ``deep`` | ``auto``.
        prompt_version: Brain prompt style.
        provider: LLM provider.
        model: Default model ID.
        deep_model: Model used when deep analysis is triggered.
        use_cache: Whether to use the data cache.
    """
    stock_name = stock_name or symbol

    print(
        f"\n{'='*60}\n"
        f"🔍 v2 单股分析模式\n"
        f"📅 日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🎯 标的: {stock_name} ({symbol})\n"
        f"⚙️  分析模式: {analysis_mode.upper()}\n"
        f"{'='*60}\n"
    )

    builder = _select_builder(analysis_mode)
    steps = builder(
        provider=provider,
        model=model,
        deep_model=deep_model,
        prompt_version=prompt_version,
        use_cache=use_cache,
    )

    initial_state = AnalysisState(symbol=symbol, stock_name=stock_name)
    runner = PipelineRunner(steps, abort_on_error=False)
    result = runner.run(initial_state)

    state = result.state
    _print_result(state, result.failed_steps)
    _save_single_report(state)


def run_v2_monitor_mode(
    watchlist_name: str = "my",
    analysis_mode: str = "auto",
    prompt_version: str = "professional",
    provider: str = "modelscope",
    model: str | None = None,
    deep_model: str | None = None,
    use_cache: bool = True,
    max_workers: int = 3,
) -> None:
    """Run the v2 pipeline for every stock in a watchlist.

    Data fetching and AI analysis are parallelised with
    ``ThreadPoolExecutor(max_workers=max_workers)`` to mirror legacy
    behaviour.
    """
    watchlist = _load_watchlist(watchlist_name)
    total = len(watchlist)

    print(
        f"\n🛡️  启动【v2 多策略监控模式】…\n"
        f"📅 日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⚙️  分析模式: {analysis_mode}\n"
        f"📊 监控标的: {total} 只\n"
    )

    # ------------------------------------------------------------------
    # Phase 1 — fetch data for all items (parallel, max 3 workers)
    # ------------------------------------------------------------------
    print(f"📊 数据获取中 (共{total}只)…")
    fetch_start = time.time()
    fetched_map: dict[str, tuple[dict, dict[str, Any]]] = {}
    fetch_lock = threading.Lock()
    fetch_done = [0]

    builder = _select_builder(analysis_mode)
    # Create steps once; each task gets its own runner but shares nothing
    base_steps = builder(
        provider=provider,
        model=model,
        deep_model=deep_model,
        prompt_version=prompt_version,
        use_cache=use_cache,
    )

    def _fetch_one(item: dict) -> tuple[str, dict, dict[str, Any]]:
        """Return (code, item, raw_data)."""
        from quant_lab.core.data.aggregator import aggregate

        code = item["code"]
        name = item["name"]
        asset_type = _infer_asset_type(item) or "stock"
        data = aggregate(code, name, asset_type=asset_type)
        return code, item, data

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, s): s for s in watchlist}
        for future in as_completed(futures):
            stock = futures[future]
            try:
                code, item, data = future.result()
                with fetch_lock:
                    fetched_map[code] = (item, data)
                    fetch_done[0] += 1
                    elapsed = time.time() - fetch_start
                    print(
                        f"  [{fetch_done[0]}/{total}] ✓ {item['name']}({code}) "
                        f"就绪 ({elapsed:.1f}s)"
                    )
            except Exception as exc:
                with fetch_lock:
                    fetch_done[0] += 1
                    print(
                        f"  [{fetch_done[0]}/{total}] ✗ {stock['name']}({stock['code']}) "
                        f"失败: {exc}"
                    )

    fetch_elapsed = time.time() - fetch_start
    print(
        f"📊 数据获取完成 ({len(fetched_map)}/{total}), "
        f"耗时 {fetch_elapsed:.1f}s\n"
    )

    if not fetched_map:
        print("❌ 没有成功获取任何数据，监控模式结束。")
        return

    # ------------------------------------------------------------------
    # Phase 2 — run AI analysis (parallel, max 3 concurrent LLM calls)
    # ------------------------------------------------------------------
    ai_results: dict[str, tuple[dict, dict[str, Any], str, bool]] = {}
    ai_lock = threading.Lock()
    ai_done = [0]
    ai_start = time.time()
    ai_total = len(fetched_map)
    ai_semaphore = threading.Semaphore(max_workers)

    print(f"🧠 AI 分析中 (共{ai_total}只)…")

    def _analyze_one(code: str, item: dict, data: dict[str, Any]) -> tuple[dict, dict[str, Any], str, bool]:
        ai_semaphore.acquire()
        try:
            t0 = time.time()
            state = AnalysisState(
                symbol=code,
                stock_name=item["name"],
                raw_data=data,
            )
            runner = PipelineRunner(base_steps, abort_on_error=False)
            result = runner.run(state)

            final = result.state
            is_deep = final.need_deep_analysis
            response = final.response or "⚠️ 无 AI 输出"

            with ai_lock:
                ai_done[0] += 1
                label = "🧠 深度" if is_deep else "🤖 快速"
                print(
                    f"  [✓ 完成 {ai_done[0]}/{ai_total}] {item['name']} "
                    f"({label}, {time.time()-t0:.1f}s)"
                )
            return item, data, response, is_deep
        finally:
            ai_semaphore.release()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {}
        for idx, (code, (item, data)) in enumerate(fetched_map.items()):
            if idx > 0:
                time.sleep(2)  # rate-limit submissions
            future = executor.submit(_analyze_one, code, item, data)
            future_map[future] = code
            print(f"  [→ 提交 {idx+1}/{ai_total}] {item['name']}")

        for future in as_completed(future_map):
            code = future_map[future]
            try:
                item, data, response, is_deep = future.result()
                ai_results[code] = (item, data, response, is_deep)
            except Exception as exc:
                logger.error("AI 分析失败 %s: %s", code, exc)
                item, data = fetched_map[code]
                ai_results[code] = (item, data, f"⚠️ 分析失败: {exc}", False)

    ai_elapsed = time.time() - ai_start
    print(f"🧠 AI 分析完成 ({len(ai_results)}/{ai_total}), 耗时 {ai_elapsed:.1f}s\n")

    # ------------------------------------------------------------------
    # Phase 3 — assemble aggregate report
    # ------------------------------------------------------------------
    now = datetime.now()
    report_dir = _report_dir()
    os.makedirs(report_dir, exist_ok=True)
    filename = os.path.join(
        report_dir,
        f"{now.strftime('%H%M%S')}_{watchlist_name}_{analysis_mode}.md",
    )

    lines = [
        f"# 每日投资报告（{now.strftime('%Y-%m-%d')}）",
        "",
        "> 本报告由 v2 AI 自动生成，仅供参考。",
        "",
    ]

    deep_count = 0
    for stock in watchlist:
        code = stock["code"]
        if code not in ai_results:
            continue
        item, data, response, is_deep = ai_results[code]
        if is_deep:
            deep_count += 1

        label = "🧠 Brain 深度分析" if is_deep else "🤖 Worker 快速分析"
        lines.extend(
            [
                f"## {item['name']} ({code})",
                "",
                f"**分析模式**: {label}",
                f"- **趋势**: {data.get('tech_summary', 'N/A')}",
                f"- **资金**: {data.get('money_summary', 'N/A')}",
                f"- **舆情**: {data.get('news_summary', 'N/A')}",
                "",
                "**AI点评**:",
                "",
                response,
                "",
                "---",
                "",
            ]
        )

    content = "\n".join(lines)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n✅ Markdown 汇总报告已生成: {filename}")

    # Attempt PDF
    try:
        from md2pdf_tool import md_to_pdf

        pdf_path = filename.replace(".md", ".pdf")
        if md_to_pdf(filename, pdf_path):
            print(f"✅ PDF 报告已生成: {pdf_path}")
    except Exception as exc:
        logger.warning("PDF 生成失败: %s", exc)

    print(
        f"\n{'='*60}\n"
        f"📊 监控模式完成\n"
        f"{'='*60}\n"
        f"✅ 成功: {len(ai_results)}/{total}\n"
        f"🧠 深度分析: {deep_count} 只\n"
        f"📁 报告目录: {report_dir}\n"
        f"{'='*60}\n"
    )


def _print_result(state: Any, failed_steps: list[tuple[str, str]]) -> None:
    """Pretty-print a single-stock pipeline result to the terminal."""
    print(
        f"\n{'='*60}\n"
        f"{'🧠 Brain 深度分析' if state.need_deep_analysis else '🤖 Worker 快速分析'}:\n"
        f"{'='*60}\n"
        f"**资金面**: {state.raw_data.get('money_summary', 'N/A')}\n"
        f"**技术面**: {state.raw_data.get('tech_summary', 'N/A')}\n"
        f"**舆情**: {state.raw_data.get('news_summary', 'N/A')}\n"
        f"\n{state.response}\n"
        f"{'='*60}\n"
    )
    if state.structured_output:
        so = state.structured_output
        print(
            f"📊 结构化输出:\n"
            f"  评级: {getattr(so, 'rating', 'N/A')}\n"
            f"  置信度: {getattr(so, 'confidence', 'N/A')}\n"
            f"  目标价: {getattr(so, 'target_price', 'N/A')}\n"
        )
    if failed_steps:
        print("⚠️ 以下步骤执行失败:")
        for name, msg in failed_steps:
            print(f"  - {name}: {msg}")


def run_memory_migration(dry_run: bool = False) -> None:
    """Run the one-off migration of historical reports into memory log."""
    from quant_lab.core.memory.migration import run_migration

    stats = run_migration(dry_run=dry_run)
    print(f"\n{'='*60}")
    print("📊 Memory Migration Summary")
    print(f"{'='*60}")
    print(f"Total scanned: {stats['total']}")
    print(f"Imported: {stats['imported']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Errors: {stats['errors']}")


def run_memory_stats() -> None:
    """Print memory log statistics."""
    from quant_lab.core.memory.log import AnalysisMemoryLog

    log = AnalysisMemoryLog()
    stats = log.get_stats()
    print(f"\n{'='*60}")
    print("🧠 Memory Log Statistics")
    print(f"{'='*60}")
    print(f"Total entries: {stats['total']}")
    print(f"Pending: {stats['pending']}")
    print(f"Resolved: {stats['resolved']}")
    print(f"Unique symbols: {stats['symbols']}")
    if stats['avg_alpha'] is not None:
        print(f"Average alpha: {stats['avg_alpha'] * 100:.2f}%")


def _save_single_report(state: Any) -> None:
    """Save a single-stock report (Markdown + optional PDF)."""
    report_dir = _report_dir()
    os.makedirs(report_dir, exist_ok=True)

    now = datetime.now()
    mode = "deep" if state.need_deep_analysis else "fast"
    filename = os.path.join(
        report_dir,
        f"{now.strftime('%H%M%S')}_{state.stock_name}_{mode}.md",
    )

    lines = [
        f"# {state.stock_name}（{state.symbol}）投资分析",
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

    if state.structured_output:
        from quant_lab.core.schemas.render import render_stock_analysis

        lines.extend(
            [
                "## 结构化分析",
                "",
                render_stock_analysis(state.structured_output),
                "",
            ]
        )

    lines.extend(["## AI分析", "", state.response, ""])

    content = "\n".join(lines)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ Markdown 报告已保存: {filename}")

    try:
        from md2pdf_tool import md_to_pdf

        pdf_path = filename.replace(".md", ".pdf")
        if md_to_pdf(filename, pdf_path):
            print(f"✅ PDF 报告已生成: {pdf_path}")
    except Exception as exc:
        logger.warning("PDF 生成失败: %s", exc)
