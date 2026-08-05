"""SQLite 접근 계층.

A(collector)/B(ai)/C(report)는 서로의 모듈을 import하지 않고 이 파일을 통해서만
데이터를 주고받는다. 함수 시그니처를 바꿀 때는 팀에 먼저 공지한다.
새 함수 추가는 자유롭게 해도 된다.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "output" / "data" / "news.db"

# news_raw 테이블 - 수집 원본 (불변, fetch만 씀)
# news_clean 테이블 - 정제 결과 (clean이 news_raw를 읽어 새로 insert, status: 'clean' | 'summarized')
# insights 테이블 - AI가 생성한 종합 분석 결과를 저장하기 위해 선언
SCHEMA = """
CREATE TABLE IF NOT EXISTS news_raw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT UNIQUE NOT NULL,
    source_name TEXT,
    collect_method TEXT,
    category TEXT,
    title TEXT,
    content TEXT,
    published_at TEXT,
    collected_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS news_clean (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id INTEGER NOT NULL REFERENCES news_raw(id),
    source_url TEXT UNIQUE NOT NULL,
    source_name TEXT,
    collect_method TEXT,
    category TEXT,
    title TEXT,
    content TEXT,
    published_at TEXT,
    collected_at TEXT,
    status TEXT NOT NULL DEFAULT 'clean',
    summary TEXT,
    sentiment TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_from TEXT,
    date_to TEXT,
    category TEXT,
    news_count INTEGER,
    trends TEXT,
    keywords TEXT,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# DB 생성하기
def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


# ---------------------------------------------------------------------------
# collector(A) 전용
# ---------------------------------------------------------------------------

def insert_news_raw(conn: sqlite3.Connection, item: dict, duplicate_policy: str = "skip") -> bool:
    """raw 뉴스 1건을 news_raw에 삽입한다 (title/content는 수집 원문 그대로).
    성공(신규 삽입 또는 upsert 갱신) 시 True, skip된 경우 False.

    INSERT 전에 source_url 존재 여부를 먼저 확인한다 (INSERT OR IGNORE로 시도 후
    무시하면, 위반 여부와 무관하게 AUTOINCREMENT 시퀀스가 먼저 소비되어 skip된
    건도 id가 하나씩 건너뛰게 되기 때문)."""
    now = _now()
    existing = conn.execute(
        "SELECT id FROM news_raw WHERE source_url = ?", (item["source_url"],)
    ).fetchone()

    if existing:
        if duplicate_policy != "upsert":
            return False
        conn.execute(
            """UPDATE news_raw SET source_name=?, collect_method=?, category=?,
               title=?, content=?, published_at=?, collected_at=?
               WHERE id=?""",
            (
                item.get("source_name"),
                item.get("collect_method"),
                item.get("category"),
                item.get("title"),
                item.get("content"),
                item.get("published_at"),
                item.get("collected_at", now),
                existing["id"],
            ),
        )
        conn.commit()
        return True

    conn.execute(
        """INSERT INTO news_raw
           (source_url, source_name, collect_method, category, title, content,
            published_at, collected_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            item["source_url"],
            item.get("source_name"),
            item.get("collect_method"),
            item.get("category"),
            item.get("title"),
            item.get("content"),
            item.get("published_at"),
            item.get("collected_at", now),
            now,
        ),
    )
    conn.commit()
    return True


def fetch_raw_news(conn: sqlite3.Connection) -> list[dict]:
    """news_clean에 아직 없는 news_raw 전체 조회 (clean 대상)."""
    rows = conn.execute(
        """SELECT * FROM news_raw
           WHERE id NOT IN (SELECT raw_id FROM news_clean)"""
    ).fetchall()
    return [dict(r) for r in rows]


def update_news_clean(conn: sqlite3.Connection, raw_id: int, cleaned_fields: dict) -> None:
    """정제 결과를 news_clean에 새로 삽입한다 (status='clean')."""
    raw = conn.execute("SELECT * FROM news_raw WHERE id = ?", (raw_id,)).fetchone()
    now = _now()
    fields = {**dict(raw), **cleaned_fields}
    conn.execute(
        """INSERT INTO news_clean
           (raw_id, source_url, source_name, collect_method, category, title, content,
            published_at, collected_at, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'clean', ?, ?)""",
        (
            raw_id,
            fields.get("source_url"),
            fields.get("source_name"),
            fields.get("collect_method"),
            fields.get("category"),
            fields.get("title"),
            fields.get("content"),
            fields.get("published_at"),
            fields.get("collected_at"),
            now,
            now,
        ),
    )
    conn.commit()

"""
각자 여기에서 DB 접근 함수를 추가해서 사용하면 됩니다.
"""
# # ---------------------------------------------------------------------------
# # ai(B) 전용
# # ---------------------------------------------------------------------------

# def fetch_news_for_summary(
#     conn: sqlite3.Connection, mode: str, limit: int | None = None, ids: list[int] | None = None
# ) -> list[dict]:
#     """mode: 'all' | 'id' | 'unsummarized' (news_clean 대상)"""
#     if mode == "id":
#         if not ids:
#             return []
#         placeholders = ",".join("?" for _ in ids)
#         rows = conn.execute(
#             f"SELECT * FROM news_clean WHERE id IN ({placeholders})", ids
#         ).fetchall()
#     elif mode == "unsummarized":
#         query = "SELECT * FROM news_clean WHERE status = 'clean' AND summary IS NULL"
#         query += " LIMIT ?" if limit else ""
#         rows = conn.execute(query, (limit,) if limit else ()).fetchall()
#     else:  # all
#         query = "SELECT * FROM news_clean WHERE status IN ('clean', 'summarized')"
#         query += " LIMIT ?" if limit else ""
#         rows = conn.execute(query, (limit,) if limit else ()).fetchall()
#     return [dict(r) for r in rows]


# def save_summary(conn: sqlite3.Connection, news_id: int, summary: str) -> None:
#     conn.execute(
#         "UPDATE news_clean SET summary = ?, status = 'summarized', updated_at = ? WHERE id = ?",
#         (summary, _now(), news_id),
#     )
#     conn.commit()


# def fetch_news_for_analysis(
#     conn: sqlite3.Connection,
#     date_from: str | None = None,
#     date_to: str | None = None,
#     category: str | None = None,
# ) -> list[dict]:
#     query = "SELECT * FROM news_clean WHERE 1=1"
#     params: list = []
#     if date_from:
#         query += " AND published_at >= ?"
#         params.append(date_from)
#     if date_to:
#         query += " AND published_at <= ?"
#         params.append(date_to)
#     if category:
#         query += " AND category = ?"
#         params.append(category)
#     rows = conn.execute(query, params).fetchall()
#     return [dict(r) for r in rows]


# def save_insight(conn: sqlite3.Connection, insight: dict) -> int:
#     cur = conn.execute(
#         """INSERT INTO insights
#            (date_from, date_to, category, news_count, trends, keywords, created_at)
#            VALUES (?, ?, ?, ?, ?, ?, ?)""",
#         (
#             insight.get("date_from"),
#             insight.get("date_to"),
#             insight.get("category"),
#             insight.get("news_count", 0),
#             insight.get("trends"),
#             insight.get("keywords"),
#             _now(),
#         ),
#     )
#     conn.commit()
#     return cur.lastrowid


# # ---------------------------------------------------------------------------
# # report(C) 전용
# # ---------------------------------------------------------------------------

# def fetch_news_for_report(conn: sqlite3.Connection, filters: dict | None = None) -> list[dict]:
#     filters = filters or {}
#     query = "SELECT * FROM news_clean WHERE 1=1"
#     params: list = []
#     if filters.get("category"):
#         query += " AND category = ?"
#         params.append(filters["category"])
#     if filters.get("date_from"):
#         query += " AND published_at >= ?"
#         params.append(filters["date_from"])
#     if filters.get("date_to"):
#         query += " AND published_at <= ?"
#         params.append(filters["date_to"])
#     if filters.get("status"):
#         query += " AND status = ?"
#         params.append(filters["status"])
#     rows = conn.execute(query, params).fetchall()
#     return [dict(r) for r in rows]


# def fetch_latest_insight(conn: sqlite3.Connection, filters: dict | None = None) -> dict | None:
#     filters = filters or {}
#     query = "SELECT * FROM insights WHERE 1=1"
#     params: list = []
#     if filters.get("category"):
#         query += " AND category = ?"
#         params.append(filters["category"])
#     query += " ORDER BY created_at DESC LIMIT 1"
#     row = conn.execute(query, params).fetchone()
#     return dict(row) if row else None


# def count_by_category(conn: sqlite3.Connection) -> dict:
#     rows = conn.execute(
#         "SELECT category, COUNT(*) as cnt FROM news_clean GROUP BY category"
#     ).fetchall()
#     return {r["category"] or "미분류": r["cnt"] for r in rows}


# def count_by_date(conn: sqlite3.Connection) -> dict:
#     rows = conn.execute(
#         "SELECT substr(collected_at, 1, 10) as day, COUNT(*) as cnt FROM news_raw GROUP BY day ORDER BY day"
#     ).fetchall()
#     return {r["day"]: r["cnt"] for r in rows}
