import sqlite3
import json
import math
import os
from datetime import datetime
from config import get_logger

log = get_logger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "history.db")

def _connect() -> sqlite3.Connection:
    """Return a WAL-mode connection with a busy timeout for concurrent access."""
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")      # allows concurrent readers + 1 writer
    conn.execute("PRAGMA busy_timeout=5000")      # wait up to 5s instead of failing immediately
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT NOT NULL,
                jd_text     TEXT NOT NULL,
                parsed_jd   TEXT NOT NULL,
                candidates  TEXT NOT NULL,
                bias_report TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'recruiter',
                created_at    TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER REFERENCES users(id),
                analysis_id    INTEGER REFERENCES analyses(id),
                candidate_name TEXT NOT NULL,
                action         TEXT NOT NULL CHECK(action IN ('shortlist','reject','hire')),
                created_at     TEXT NOT NULL
            )
        """)
        # Safe migrations for existing DBs
        for migration in [
            "ALTER TABLE analyses ADD COLUMN bias_report TEXT NOT NULL DEFAULT '{}'",
        ]:
            try:
                conn.execute(migration)
                log.info("database.migration", extra={"sql": migration[:60]})
            except sqlite3.OperationalError:
                pass
        conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at  ON analyses(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_uid ON feedback(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_aid ON feedback(analysis_id)")
    log.info("database.initialized", extra={"path": DB_PATH})

def save_analysis(jd_text: str, parsed_jd: dict, candidates: list, bias_report: dict = None) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO analyses (created_at, jd_text, parsed_jd, candidates, bias_report) VALUES (?, ?, ?, ?, ?)",
            (
                datetime.utcnow().isoformat(),
                jd_text,
                json.dumps(parsed_jd),
                json.dumps(candidates),
                json.dumps(bias_report or {}),
            ),
        )
        row_id = cursor.lastrowid
        log.info("database.saved", extra={"analysis_id": row_id})
        return row_id

def get_history(page: int = 1, limit: int = 20) -> dict:
    """Paginated history. Returns history list + pagination metadata."""
    page  = max(1, page)
    limit = min(100, max(1, limit))
    offset = (page - 1) * limit

    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        rows  = conn.execute(
            "SELECT id, created_at, jd_text, parsed_jd FROM analyses ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            d["parsed_jd"] = json.loads(d["parsed_jd"])
            result.append(d)

    return {
        "history": result,
        "total":   total,
        "page":    page,
        "pages":   math.ceil(total / limit) if total else 1,
        "limit":   limit,
    }

def get_analysis(analysis_id: int) -> dict | None:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        if row:
            d = dict(row)
            d["parsed_jd"]   = json.loads(d["parsed_jd"])
            d["candidates"]  = json.loads(d["candidates"])
            d["bias_report"] = json.loads(d.get("bias_report") or "{}")
            return d
        return None

def delete_analysis(analysis_id: int) -> bool:
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        deleted = cursor.rowcount > 0
        if deleted:
            log.info("database.deleted", extra={"analysis_id": analysis_id})
        return deleted


# ── Feedback ─────────────────────────────────────────────────────────────────────

def save_feedback(analysis_id: int, candidate_name: str,
                  action: str, user_id: str | None = None) -> int:
    from datetime import datetime
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO feedback (user_id, analysis_id, candidate_name, action, created_at) "
            "VALUES (?,?,?,?,?)",
            (user_id, analysis_id, candidate_name, action, datetime.utcnow().isoformat()),
        )
        log.info("feedback.saved",
                 extra={"action": action, "candidate": candidate_name})
        return cur.lastrowid


def get_feedback_stats(analysis_id: int | None = None) -> dict:
    """Returns action counts. When analysis_id is given, scoped to that analysis."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        where = "WHERE analysis_id = ?" if analysis_id else ""
        params = (analysis_id,) if analysis_id else ()
        rows = conn.execute(
            f"SELECT action, COUNT(*) as cnt FROM feedback {where} GROUP BY action",
            params,
        ).fetchall()
    counts = {r["action"]: r["cnt"] for r in rows}
    total      = sum(counts.values())
    shortlisted = counts.get("shortlist", 0)
    return {
        "shortlisted":  shortlisted,
        "rejected":     counts.get("reject", 0),
        "hired":        counts.get("hire",   0),
        "total":        total,
        "precision_at_k": round(shortlisted / total, 3) if total else None,
    }
