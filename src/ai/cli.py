"""ai 모듈 서브커맨드: summarize, analyze."""

import argparse
import json

from src.ai.analyze import analyze_news
from src.ai.summarize import summarize_news_item
from src.common.config import load_config
from src.common.db import (
    fetch_clean_news,
    fetch_news_for_analysis,
    get_connection,
    init_db,
    insert_insight,
    update_news_summary,
)
from src.common.logger import get_logger

logger = get_logger(__name__)


def _limit_type(value: str) -> int:
    n = int(value)
    if not 1 <= n <= 100:
        raise argparse.ArgumentTypeError("--limit은 1~100 범위여야 합니다.")
    return n


def register_subparser(subparsers: argparse._SubParsersAction) -> None:
    # python main.py summarize --unsummarized --limit 10
    summarize_parser = subparsers.add_parser("summarize", help="뉴스 AI 요약")
    # --all / --id / --unsummarized는 동시에 쓰면 의미가 충돌하므로 배타 그룹으로 묶는다.
    target = summarize_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--all", action="store_true", help="clean 뉴스 전체 요약")
    target.add_argument("--id", type=int, help="특정 news_clean id만 요약")
    target.add_argument(
        "--unsummarized", action="store_true", help="아직 요약되지 않은 뉴스만 요약"
    )
    summarize_parser.add_argument("--limit", type=_limit_type, default=20, metavar="{1..100}")
    # 이미 요약된 뉴스는 기본 스킵. 다시 요약하려면 --force.
    summarize_parser.add_argument(
        "--force", action="store_true", help="이미 요약된 뉴스도 다시 요약"
    )
    summarize_parser.set_defaults(func=_run_summarize)

    # python main.py analyze --date-from 2026-01-01 --date-to 2026-01-10 --category IT
    analyze_parser = subparsers.add_parser("analyze", help="AI 인사이트 분석")
    analyze_parser.add_argument("--date-from", default=None, help="시작일 (YYYY-MM-DD)")
    analyze_parser.add_argument("--date-to", default=None, help="종료일 (YYYY-MM-DD)")
    analyze_parser.add_argument("--category", default=None, help="카테고리 필터")
    analyze_parser.set_defaults(func=_run_analyze)


def _run_summarize(args: argparse.Namespace) -> None:
    config = load_config()
    conn = get_connection()
    init_db(conn)

    rows = fetch_clean_news(
        conn,
        only_unsummarized=args.unsummarized,
        news_id=args.id,
        limit=None if args.id else args.limit,
    )
    logger.info("요약 대상: %d건", len(rows))

    success, skipped, failed = 0, 0, 0
    for row in rows:
        # 이미 요약된 뉴스는 기본 스킵 (--unsummarized는 조회 단계에서 이미 걸러짐).
        if row.get("summary") and not args.force:
            logger.info("이미 요약됨, 스킵: id=%s", row["id"])
            skipped += 1
            continue

        result = summarize_news_item(config, row)
        if result is None:
            # API 실패/본문 없음은 이미 하위 함수에서 로깅했다.
            failed += 1
            continue

        update_news_summary(conn, row["id"], result["summary"], result["sentiment"])
        success += 1

    conn.close()
    logger.info("요약 완료: %d건 성공, %d건 skip, %d건 실패", success, skipped, failed)


def _run_analyze(args: argparse.Namespace) -> None:
    config = load_config()
    conn = get_connection()
    init_db(conn)

    rows = fetch_news_for_analysis(
        conn, date_from=args.date_from, date_to=args.date_to, category=args.category
    )
    logger.info(
        "분석 대상: %d건 (기간=%s~%s, 카테고리=%s)",
        len(rows),
        args.date_from or "전체",
        args.date_to or "전체",
        args.category or "전체",
    )

    insight = analyze_news(config, rows, args.date_from, args.date_to, args.category)
    if insight is None:
        logger.error("인사이트 분석 실패")
        conn.close()
        return

    insight_id = insert_insight(conn, insight)
    conn.close()

    logger.info("인사이트 저장 완료: id=%d", insight_id)
    logger.info("주요 트렌드: %s", insight["trends"])
    logger.info("핵심 키워드: %s", ", ".join(json.loads(insight["keywords"])))
