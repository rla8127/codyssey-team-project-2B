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


# --- 담당 B (AI): summarize / analyze 용 ---


def fetch_clean_news(
    conn: sqlite3.Connection,
    only_unsummarized: bool = False,
    news_id: int | None = None,
    limit: int | None = None,
) -> list[dict]:
    """요약 대상 news_clean 행을 조회한다.

    only_unsummarized=True면 summary가 아직 없는 행만 반환한다 (--unsummarized).
    news_id를 주면 해당 id 1건만 반환한다 (--id).
    """
    sql = "SELECT * FROM news_clean"
    params: list = []
    where: list[str] = []

    if news_id is not None:
        where.append("id = ?")
        params.append(news_id)
    if only_unsummarized:
        where.append("(summary IS NULL OR summary = '')")

    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def update_news_summary(
    conn: sqlite3.Connection, news_id: int, summary: str, sentiment: str | None = None
) -> None:
    """요약 결과를 news_clean에 반영하고 status를 'summarized'로 올린다."""
    conn.execute(
        """UPDATE news_clean
           SET summary = ?, sentiment = ?, status = 'summarized', updated_at = ?
           WHERE id = ?""",
        (summary, sentiment, _now(), news_id),
    )
    conn.commit()


def fetch_news_for_analysis(
    conn: sqlite3.Connection,
    date_from: str | None = None,
    date_to: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """인사이트 분석 대상을 기간/카테고리로 필터링해 조회한다.

    published_at이 없는 기사를 버리지 않도록 collected_at으로 대체 비교한다.
    """
    sql = "SELECT * FROM news_clean"
    where: list[str] = []
    params: list = []

    if date_from:
        where.append("COALESCE(published_at, collected_at) >= ?")
        params.append(date_from)
    if date_to:
        # date_to를 포함하도록 날짜 끝까지 비교한다 (YYYY-MM-DD -> 그날 23:59:59).
        where.append("COALESCE(published_at, collected_at) <= ?")
        params.append(date_to + "T23:59:59")
    if category:
        where.append("category = ?")
        params.append(category)

    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY COALESCE(published_at, collected_at)"

    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def insert_insight(conn: sqlite3.Connection, insight: dict) -> int:
    """AI 인사이트 분석 결과를 insights 테이블에 저장하고 id를 반환한다."""
    cur = conn.execute(
        """INSERT INTO insights
           (date_from, date_to, category, news_count, trends, keywords, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            insight.get("date_from"),
            insight.get("date_to"),
            insight.get("category"),
            insight.get("news_count"),
            insight.get("trends"),
            insight.get("keywords"),
            _now(),
        ),
    )
    conn.commit()
    return cur.lastrowid


def fetch_insights(
    conn: sqlite3.Connection,
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    keyword: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """저장된 인사이트 목록을 최신순으로 조회한다 (analyze --list).

    date_from/date_to는 분석을 실행한 시각(created_at) 기준으로 거른다.
    keyword는 trends/keywords 본문에 대한 부분 일치 검색이다.
    """
    sql = "SELECT * FROM insights"
    where: list[str] = []
    params: list = []

    if category:
        where.append("category = ?")
        params.append(category)
    if date_from:
        where.append("created_at >= ?")
        params.append(date_from)
    if date_to:
        where.append("created_at <= ?")
        params.append(date_to + "T23:59:59")
    if keyword:
        where.append("(trends LIKE ? OR keywords LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def count_insights(
    conn: sqlite3.Connection,
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    keyword: str | None = None,
) -> int:
    """fetch_insights와 같은 조건의 전체 건수 (페이지네이션 표시용)."""
    sql = "SELECT COUNT(*) AS cnt FROM insights"
    where: list[str] = []
    params: list = []

    if category:
        where.append("category = ?")
        params.append(category)
    if date_from:
        where.append("created_at >= ?")
        params.append(date_from)
    if date_to:
        where.append("created_at <= ?")
        params.append(date_to + "T23:59:59")
    if keyword:
        where.append("(trends LIKE ? OR keywords LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if where:
        sql += " WHERE " + " AND ".join(where)

    return conn.execute(sql, params).fetchone()["cnt"]


def fetch_insight(conn: sqlite3.Connection, insight_id: int) -> dict | None:
    """인사이트 1건을 id로 조회한다 (analyze --show ID). 없으면 None."""
    row = conn.execute("SELECT * FROM insights WHERE id = ?", (insight_id,)).fetchone()
    return dict(row) if row else None


def fetch_latest_insight(
    conn: sqlite3.Connection, category: str | None = None
) -> dict | None:
    """가장 최근 인사이트 1건을 조회한다 (report에서 활용). 없으면 None."""
    sql = "SELECT * FROM insights"
    params: list = []
    if category:
        sql += " WHERE category = ?"
        params.append(category)
    sql += " ORDER BY id DESC LIMIT 1"

    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# report(C) 전용 — 집계/시각화/내보내기
# ---------------------------------------------------------------------------


def count_by_category(conn: sqlite3.Connection) -> dict[str, int]:
    """카테고리별 뉴스 수 (차트 1: 막대그래프용).

    category가 NULL이거나 빈 문자열인 행은 '미분류'로 묶는다.
    """
    rows = conn.execute(
        """SELECT COALESCE(NULLIF(category, ''), '미분류') AS name, COUNT(*) AS cnt
           FROM news_clean GROUP BY name ORDER BY cnt DESC"""
    ).fetchall()
    return {r["name"]: r["cnt"] for r in rows}


def count_by_date(conn: sqlite3.Connection) -> dict[str, int]:
    """일자별 수집 추이 (차트 2: 선그래프용).

    발행일이 없는 기사도 빠지지 않도록 collected_at으로 대체해 앞 10자(YYYY-MM-DD)만 자른다.
    """
    rows = conn.execute(
        """SELECT substr(COALESCE(published_at, collected_at), 1, 10) AS day,
                  COUNT(*) AS cnt
           FROM news_clean
           WHERE COALESCE(published_at, collected_at) IS NOT NULL
           GROUP BY day ORDER BY day"""
    ).fetchall()
    return {r["day"]: r["cnt"] for r in rows}


def count_by_sentiment(conn: sqlite3.Connection) -> dict[str, int]:
    """감성별 뉴스 수 (보너스 차트: 파이그래프용). 아직 요약 전인 행은 제외한다."""
    rows = conn.execute(
        """SELECT sentiment AS name, COUNT(*) AS cnt
           FROM news_clean
           WHERE sentiment IS NOT NULL AND sentiment != ''
           GROUP BY name ORDER BY cnt DESC"""
    ).fetchall()
    return {r["name"]: r["cnt"] for r in rows}


def quality_metrics(conn: sqlite3.Connection) -> dict:
    """리포트용 품질 지표.

    수집 대비 정제 성공률, 요약 완료율, 필수 필드 결측률을 한 번에 계산한다.
    """
    raw_total = conn.execute("SELECT COUNT(*) AS c FROM news_raw").fetchone()["c"]
    row = conn.execute(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN status = 'summarized' THEN 1 ELSE 0 END) AS summarized,
                  SUM(CASE WHEN content IS NULL OR content = '' THEN 1 ELSE 0 END) AS no_content,
                  SUM(CASE WHEN category IS NULL OR category = '' THEN 1 ELSE 0 END) AS no_category,
                  SUM(CASE WHEN published_at IS NULL OR published_at = '' THEN 1 ELSE 0 END) AS no_date
           FROM news_clean"""
    ).fetchone()

    clean_total = row["total"] or 0
    return {
        "raw_total": raw_total,
        "clean_total": clean_total,
        # 0으로 나누는 것을 막기 위해 분모가 0이면 0.0을 쓴다.
        "clean_rate": round(clean_total / raw_total * 100, 1) if raw_total else 0.0,
        "summarized_total": row["summarized"] or 0,
        "summarized_rate": (
            round((row["summarized"] or 0) / clean_total * 100, 1) if clean_total else 0.0
        ),
        "missing_content": row["no_content"] or 0,
        "missing_category": row["no_category"] or 0,
        "missing_date": row["no_date"] or 0,
    }


def top_keywords(conn: sqlite3.Connection, limit: int = 10) -> list[tuple[str, int]]:
    """저장된 인사이트의 keywords를 모두 펼쳐 빈도 TOP N을 만든다.

    keywords는 JSON 문자열이라 파이썬에서 파싱해 센다.
    """
    import json as _json
    from collections import Counter

    counter: Counter = Counter()
    for row in conn.execute("SELECT keywords FROM insights").fetchall():
        if not row["keywords"]:
            continue
        try:
            parsed = _json.loads(row["keywords"])
        except _json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            counter.update(str(k).strip() for k in parsed if str(k).strip())

    return counter.most_common(limit)


def fetch_news_for_export(
    conn: sqlite3.Connection,
    status: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """내보내기 대상 조회 (--status summarized 등 필터 지원)."""
    sql = "SELECT * FROM news_clean"
    where: list[str] = []
    params: list = []

    if status:
        where.append("status = ?")
        params.append(status)
    if category:
        where.append("category = ?")
        params.append(category)

    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id"

    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ---------------------------------------------------------------------------
# query(D, 보너스) 전용 — list / show
# ---------------------------------------------------------------------------


def _news_filter_clause(
    category: str | None,
    date_from: str | None,
    date_to: str | None,
    keyword: str | None,
    status: str | None,
) -> tuple[str, list]:
    """list/count가 같은 조건을 쓰도록 WHERE 절과 파라미터를 함께 만든다.

    날짜는 발행일 기준이되, 발행일이 없는 기사가 빠지지 않도록 collected_at으로 대체한다.
    keyword는 제목/본문/요약을 함께 검색한다.
    """
    where: list[str] = []
    params: list = []

    if category:
        where.append("category = ?")
        params.append(category)
    if date_from:
        where.append("COALESCE(published_at, collected_at) >= ?")
        params.append(date_from)
    if date_to:
        where.append("COALESCE(published_at, collected_at) <= ?")
        params.append(date_to + "T23:59:59")
    if keyword:
        where.append("(title LIKE ? OR content LIKE ? OR summary LIKE ?)")
        params.extend([f"%{keyword}%"] * 3)
    if status:
        where.append("status = ?")
        params.append(status)

    return (" WHERE " + " AND ".join(where) if where else ""), params


def fetch_news_list(
    conn: sqlite3.Connection,
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    keyword: str | None = None,
    status: str | None = None,
    limit: int = 10,
    offset: int = 0,
) -> list[dict]:
    """뉴스 목록을 조건 필터링 + 페이지네이션으로 조회한다 (list 서브커맨드)."""
    clause, params = _news_filter_clause(category, date_from, date_to, keyword, status)
    sql = (
        "SELECT * FROM news_clean"
        + clause
        + " ORDER BY COALESCE(published_at, collected_at) DESC, id DESC LIMIT ? OFFSET ?"
    )
    return [dict(r) for r in conn.execute(sql, params + [limit, offset]).fetchall()]


def count_news(
    conn: sqlite3.Connection,
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    keyword: str | None = None,
    status: str | None = None,
) -> int:
    """fetch_news_list와 같은 조건의 전체 건수 (페이지 수 계산용)."""
    clause, params = _news_filter_clause(category, date_from, date_to, keyword, status)
    return conn.execute("SELECT COUNT(*) AS cnt FROM news_clean" + clause, params).fetchone()["cnt"]


def fetch_news_detail(conn: sqlite3.Connection, news_id: int) -> dict | None:
    """뉴스 1건 상세 조회 (show 서브커맨드). 없으면 None."""
    row = conn.execute("SELECT * FROM news_clean WHERE id = ?", (news_id,)).fetchone()
    return dict(row) if row else None


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
