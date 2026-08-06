"""raw 뉴스 정제: HTML 태그/엔티티 제거, 날짜 형식 통일, 필수 필드 검증."""

import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from src.common.logger import get_logger

logger = get_logger(__name__)

# 태그같은거 삭제하기 위함
_TAG_RE = re.compile(r"<[^>]+>")

REQUIRED_FIELDS = ("title", "content", "source_url")


def normalize_text(raw: str | None) -> str:
    """HTML 태그 제거 + 엔티티 디코딩 + 공백 정규화."""
    if not raw:
        return ""
    text = _TAG_RE.sub("", raw)
    text = html.unescape(text) # html 엔티티는 일반 문자로 변환
    return " ".join(text.split()) # 빈 문자열 자동으로 버리기

# 네이버는 "Thu, 11 Jun 2026 18:34:00 +0900"(RFC 2822), 전자신문 크롤링은
# "2026-08-05T19:08:41+09:00"(ISO 8601)로 줘서, DB에 사용하기 편하도록 UTC로 변환
def normalize_pub_date(raw: str | None) -> str | None:
    """수집처별 pubDate(RFC 2822 / ISO 8601)를 ISO 8601(UTC)로 통일한다. 파싱 실패 시 None."""
    if not raw:
        return None
    for parse in (parsedate_to_datetime, datetime.fromisoformat):
        try:
            dt = parse(raw)
        except (TypeError, ValueError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()

    logger.warning("날짜 형식 파싱 실패, 결측값 처리: %r", raw)
    return None


def clean_news_item(raw_row: dict) -> dict | None:
    """news 테이블의 raw 1행을 정제된 필드 dict로 변환한다. 필수 필드 누락 시 None."""
    cleaned = {
        "title": normalize_text(raw_row.get("title")),
        "content": normalize_text(raw_row.get("content")),
        "published_at": normalize_pub_date(raw_row.get("published_at")),
        "source_url": raw_row.get("source_url"),
    }

    missing = [f for f in REQUIRED_FIELDS if not cleaned.get(f)]
    if missing:
        logger.warning(
            "필수 필드 누락으로 clean 스킵: id=%s, missing=%s", raw_row.get("id"), missing
        )
        return None

    cleaned.pop("source_url")  # source_url은 변경 대상이 아니므로 UPDATE 필드에서 제외
    return cleaned
