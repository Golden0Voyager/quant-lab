"""Migration script — bulk-import historical reports into memory log.

Usage::

    uv run python -m quant_lab.core.memory.migration [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from datetime import datetime
from typing import Any

from quant_lab.core.memory.log import AnalysisMemoryLog

logger = logging.getLogger(__name__)

REPORT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "Report",
)

# Filename pattern: HHMMSS_股票名_模式.md
_FILENAME_RE = re.compile(r"^\d{6}_(.+?)_(fast|deep|auto|估值分析|global|fund)\.md$")

# Try to extract rating from common patterns in report text
_RATING_PATTERNS = [
    re.compile(r"评级[：:]\s*(强烈买入|买入|持有|减持|卖出)"),
    re.compile(r"投资评级[：:]\s*(强烈买入|买入|持有|减持|卖出)"),
    re.compile(r"rating[：:]\s*(STRONG_BUY|BUY|HOLD|REDUCE|SELL)"),
]


def _parse_report_file(path: str) -> dict[str, Any] | None:
    """Parse a single markdown report and return metadata dict."""
    basename = os.path.basename(path)
    match = _FILENAME_RE.match(basename)
    if not match:
        return None

    stock_name = match.group(1)
    analysis_mode = match.group(2)

    # Date from directory name (YYMMDD) or file mtime
    dir_name = os.path.basename(os.path.dirname(path))
    try:
        report_date = datetime.strptime(dir_name, "%y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        # Fallback to file modification time
        mtime = os.path.getmtime(path)
        report_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")

    # Read content
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return None

    # Extract symbol from first heading: # 股票名（代码）
    symbol = None
    title_match = re.search(r"#\s*[^（]+[（(](\d{6})[）)]", content)
    if title_match:
        symbol = title_match.group(1)
    else:
        # Fallback: try to find any 6-digit code
        codes = re.findall(r"\b\d{6}\b", content)
        if codes:
            symbol = codes[0]

    if not symbol:
        logger.warning("Cannot extract symbol from %s", path)
        return None

    # Extract rating
    rating = None
    for pat in _RATING_PATTERNS:
        m = pat.search(content)
        if m:
            rating = m.group(1)
            break

    # Extract confidence if present
    confidence = None
    conf_match = re.search(r"置信度[：:]\s*([\d.]+)", content)
    if conf_match:
        try:
            confidence = float(conf_match.group(1))
        except ValueError:
            pass

    return {
        "symbol": symbol,
        "stock_name": stock_name,
        "date": report_date,
        "rating": rating,
        "confidence": confidence,
        "triggers": [],
        "analysis_mode": analysis_mode,
        "report_path": path,
        "raw_data": {},
    }


def run_migration(dry_run: bool = False) -> dict[str, Any]:
    """Scan ``Report/`` and import all historical reports into memory log.

    Returns:
        Statistics dict with ``total``, ``imported``, ``skipped``, ``errors``.
    """
    log = AnalysisMemoryLog()
    stats = {"total": 0, "imported": 0, "skipped": 0, "errors": 0, "details": []}

    if not os.path.isdir(REPORT_ROOT):
        logger.warning("Report directory not found: %s", REPORT_ROOT)
        return stats

    for dir_name in sorted(os.listdir(REPORT_ROOT)):
        dir_path = os.path.join(REPORT_ROOT, dir_name)
        if not os.path.isdir(dir_path):
            continue
        if not re.match(r"^\d{6}$", dir_name):
            continue

        for filename in sorted(os.listdir(dir_path)):
            if not filename.endswith(".md"):
                continue
            stats["total"] += 1
            file_path = os.path.join(dir_path, filename)

            parsed = _parse_report_file(file_path)
            if parsed is None:
                stats["skipped"] += 1
                continue

            if dry_run:
                logger.info("[DRY-RUN] Would import: %s", filename)
                stats["imported"] += 1
                stats["details"].append({"status": "dry-run", **parsed})
                continue

            try:
                entry_id = log.store_decision(
                    symbol=parsed["symbol"],
                    stock_name=parsed["stock_name"],
                    date=parsed["date"],
                    rating=parsed.get("rating"),
                    confidence=parsed.get("confidence"),
                    triggers=parsed["triggers"],
                    analysis_mode=parsed["analysis_mode"],
                    report_path=parsed["report_path"],
                )
                stats["imported"] += 1
                stats["details"].append({"status": "imported", "id": entry_id, **parsed})
                logger.info("Imported %s → id=%s", filename, entry_id)
            except Exception as exc:
                stats["errors"] += 1
                stats["details"].append({"status": "error", "error": str(exc), **parsed})
                logger.error("Failed to import %s: %s", filename, exc)

    return stats


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    parser = argparse.ArgumentParser(description="Import historical reports into memory log")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be imported without writing")
    args = parser.parse_args()

    stats = run_migration(dry_run=args.dry_run)
    print(f"\n{'='*60}")
    print("📊 Migration Summary")
    print(f"{'='*60}")
    print(f"Total reports scanned: {stats['total']}")
    print(f"Imported: {stats['imported']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Errors: {stats['errors']}")

    output_path = os.path.join(REPORT_ROOT, "migration_report.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"\n📁 Detail report saved: {output_path}")


if __name__ == "__main__":
    main()
