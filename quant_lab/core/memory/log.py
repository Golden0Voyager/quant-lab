"""Analysis memory log — T+1 continuous learning loop.

Stores every analysis decision as a ``pending`` record.  After the market
closes the next day, ``resolve_with_outcome`` updates the record with the
actual return and an LLM-generated reflection.  Historical entries are
injected into subsequent prompts via ``get_past_context``.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any

from quant_lab.core.memory.path import safe_ticker_component

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = os.path.expanduser("~/Code/data/quant_data/quant_cache.db")

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS memory_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    stock_name TEXT,
    date TEXT NOT NULL,
    rating TEXT,
    confidence REAL,
    triggers TEXT,
    analysis_mode TEXT,
    report_path TEXT,
    raw_data_summary TEXT,
    status TEXT DEFAULT 'pending',
    raw_return REAL,
    alpha_return REAL,
    reflection TEXT,
    resolved_at TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_memory_symbol_date
ON memory_log(symbol, date)
"""

_CREATE_STATUS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_memory_status
ON memory_log(status)
"""


class AnalysisMemoryLog:
    """Append-only memory log with pending/resolved state machine."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or _DEFAULT_DB_PATH
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(_CREATE_TABLE_SQL)
            conn.execute(_CREATE_INDEX_SQL)
            conn.execute(_CREATE_STATUS_INDEX_SQL)
            conn.commit()
        finally:
            conn.close()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _summarise_raw_data(raw_data: dict[str, Any]) -> dict[str, Any]:
        """Extract a small, stable subset of raw data for the log."""
        keys = [
            "tech_summary",
            "money_summary",
            "valuation_summary",
            "performance_summary",
            "news_summary",
            "market_env_summary",
            "pe_ttm",
            "pb",
            "dividend_yield",
        ]
        return {k: raw_data.get(k, "N/A") for k in keys if k in raw_data}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store_decision(
        self,
        symbol: str,
        stock_name: str,
        date: str,
        rating: str | None = None,
        confidence: float | None = None,
        triggers: list[str] | None = None,
        analysis_mode: str = "auto",
        report_path: str | None = None,
        raw_data: dict[str, Any] | None = None,
    ) -> str:
        """Store a new ``pending`` analysis decision.

        Returns:
            The auto-generated ``entry_id`` (row id as string).
        """
        conn = self._conn()
        try:
            summary_json = json.dumps(
                self._summarise_raw_data(raw_data or {}),
                ensure_ascii=False,
                default=str,
            )
            cursor = conn.execute(
                """
                INSERT INTO memory_log
                (symbol, stock_name, date, rating, confidence, triggers,
                 analysis_mode, report_path, raw_data_summary, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    symbol,
                    stock_name,
                    date,
                    rating,
                    confidence,
                    json.dumps(triggers, ensure_ascii=False),
                    analysis_mode,
                    report_path,
                    summary_json,
                ),
            )
            conn.commit()
            entry_id = str(cursor.lastrowid)
            logger.info("💾 Memory stored: %s (%s) → id=%s", symbol, date, entry_id)
            return entry_id
        finally:
            conn.close()

    def get_pending_entries(
        self,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return all (or symbol-filtered) pending entries."""
        conn = self._conn()
        try:
            if symbol:
                rows = conn.execute(
                    """
                    SELECT id, symbol, stock_name, date, rating, confidence,
                           triggers, analysis_mode, report_path, raw_data_summary,
                           status, created_at
                    FROM memory_log
                    WHERE status = 'pending' AND symbol = ?
                    ORDER BY date DESC
                    LIMIT ?
                    """,
                    (symbol, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, symbol, stock_name, date, rating, confidence,
                           triggers, analysis_mode, report_path, raw_data_summary,
                           status, created_at
                    FROM memory_log
                    WHERE status = 'pending'
                    ORDER BY date DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            columns = [
                "id", "symbol", "stock_name", "date", "rating", "confidence",
                "triggers", "analysis_mode", "report_path", "raw_data_summary",
                "status", "created_at",
            ]
            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()

    def resolve_with_outcome(
        self,
        entry_id: str,
        raw_return: float,
        alpha_return: float,
        reflection: str | None = None,
    ) -> dict[str, Any] | None:
        """Mark a pending entry as resolved with its T+1 outcome.

        Returns:
            The updated record, or *None* if the entry was not found.
        """
        conn = self._conn()
        try:
            cursor = conn.execute(
                """
                UPDATE memory_log
                SET status = 'resolved',
                    raw_return = ?,
                    alpha_return = ?,
                    reflection = ?,
                    resolved_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (raw_return, alpha_return, reflection, self._now(), entry_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                logger.warning("No pending entry found with id=%s", entry_id)
                return None

            cursor = conn.execute(
                "SELECT * FROM memory_log WHERE id = ?", (entry_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [d[0] for d in cursor.description]
            record = dict(zip(columns, row))
            logger.info(
                "✅ Memory resolved: id=%s raw=%.2f%% alpha=%.2f%%",
                entry_id,
                raw_return * 100,
                alpha_return * 100,
            )
            return record
        finally:
            conn.close()

    def get_past_context(
        self,
        symbol: str,
        n_same: int = 5,
        n_cross: int = 3,
    ) -> str:
        """Generate a past-context string for prompt injection.

        Combines the most recent *n_same* resolved entries for the same
        ticker with *n_cross* resolved entries for other tickers.

        Returns:
            Markdown-formatted context string (empty if no history).
        """
        conn = self._conn()
        try:
            # Same-symbol history
            same_rows = conn.execute(
                """
                SELECT date, rating, confidence, raw_return, alpha_return,
                       reflection, triggers
                FROM memory_log
                WHERE symbol = ? AND status = 'resolved'
                ORDER BY date DESC
                LIMIT ?
                """,
                (symbol, n_same),
            ).fetchall()

            # Cross-symbol history (exclude current symbol)
            cross_rows = conn.execute(
                """
                SELECT symbol, date, rating, confidence, raw_return, alpha_return,
                       reflection
                FROM memory_log
                WHERE symbol != ? AND status = 'resolved'
                ORDER BY date DESC
                LIMIT ?
                """,
                (symbol, n_cross),
            ).fetchall()

            if not same_rows and not cross_rows:
                return ""

            lines: list[str] = []
            if same_rows:
                lines.append(f"### {symbol} 历史决策")
                for row in same_rows:
                    date, rating, confidence, raw_ret, alpha_ret, reflection, triggers = row
                    lines.append(f"- **{date}** | 评级: {rating} | 置信度: {confidence}")
                    if raw_ret is not None:
                        lines.append(f"  - 实际收益: {raw_ret * 100:.1f}% | Alpha: {alpha_ret * 100:.1f}%")
                    if reflection:
                        lines.append(f"  - 反思: {reflection}")

            if cross_rows:
                lines.append("### 跨标的参考")
                for row in cross_rows:
                    sym, date, rating, confidence, raw_ret, alpha_ret, reflection = row
                    lines.append(f"- **{sym} ({date})** | 评级: {rating}")
                    if raw_ret is not None:
                        lines.append(f"  - 实际收益: {raw_ret * 100:.1f}% | Alpha: {alpha_ret * 100:.1f}%")
                    if reflection:
                        lines.append(f"  - 反思: {reflection}")

            return "\n".join(lines)
        finally:
            conn.close()

    def get_stats(self) -> dict[str, Any]:
        """Return high-level memory statistics."""
        conn = self._conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM memory_log"
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM memory_log WHERE status = 'pending'"
            ).fetchone()[0]
            resolved = conn.execute(
                "SELECT COUNT(*) FROM memory_log WHERE status = 'resolved'"
            ).fetchone()[0]
            symbols = conn.execute(
                "SELECT COUNT(DISTINCT symbol) FROM memory_log"
            ).fetchone()[0]
            avg_alpha = conn.execute(
                "SELECT AVG(alpha_return) FROM memory_log WHERE status = 'resolved'"
            ).fetchone()[0]
            return {
                "total": total,
                "pending": pending,
                "resolved": resolved,
                "symbols": symbols,
                "avg_alpha": avg_alpha,
            }
        finally:
            conn.close()
