"""ai 모듈 서브커맨드: summarize, analyze."""

import argparse
import json

from src.ai.analyze import analyze_news
from src.ai.summarize import summarize_news_item
from src.common.config import load_config
from src.common.db import (
    count_insights,
    fetch_clean_news,
    fetch_insight,
    fetch_insights,
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


def _page_type(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("--page는 1 이상이어야 합니다.")
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

    # 새 분석 실행:   python main.py analyze --date-from 2026-01-01 --date-to 2026-01-10 --category IT
    # 저장된 결과 조회: python main.py analyze --list --category IT
    #                  python main.py analyze --show 3
    analyze_parser = subparsers.add_parser("analyze", help="AI 인사이트 분석 / 결과 조회")
    # --list와 --show는 조회 모드끼리 충돌하므로 배타 그룹으로 묶는다.
    # 둘 다 없으면 기존처럼 새 분석을 실행한다.
    mode = analyze_parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="저장된 분석 결과 목록 조회")
    mode.add_argument("--show", type=int, metavar="ID", help="분석 결과 상세 조회")
    analyze_parser.add_argument("--date-from", default=None, help="시작일 (YYYY-MM-DD)")
    analyze_parser.add_argument("--date-to", default=None, help="종료일 (YYYY-MM-DD)")
    analyze_parser.add_argument("--category", default=None, help="카테고리 필터")
    # 아래 3개는 --list 전용 옵션이다.
    analyze_parser.add_argument("--keyword", default=None, help="[--list] 트렌드/키워드 검색어")
    analyze_parser.add_argument(
        "--limit", type=_limit_type, default=10, metavar="{1..100}", help="[--list] 페이지당 건수"
    )
    analyze_parser.add_argument(
        "--page", type=_page_type, default=1, metavar="N", help="[--list] 페이지 번호 (1부터)"
    )
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
    """--list면 목록 조회, --show면 상세 조회, 둘 다 없으면 새 분석을 실행한다."""
    conn = get_connection()
    init_db(conn)
    try:
        if args.list:
            _show_insight_list(conn, args)
        elif args.show is not None:
            _show_insight_detail(conn, args.show)
        else:
            _create_insight(conn, args)
    finally:
        conn.close()


def _show_insight_list(conn, args: argparse.Namespace) -> None:
    """저장된 인사이트를 최신순으로 페이지 단위 출력한다."""
    filters = {
        "category": args.category,
        "date_from": args.date_from,
        "date_to": args.date_to,
        "keyword": args.keyword,
    }
    total = count_insights(conn, **filters)
    offset = (args.page - 1) * args.limit
    rows = fetch_insights(conn, **filters, limit=args.limit, offset=offset)

    if total == 0:
        # 필터를 하나라도 걸었다면 '아직 분석한 적 없음'과 구분해서 안내한다.
        if any(filters.values()):
            print("조건에 맞는 분석 결과가 없습니다.")
        else:
            print("저장된 분석 결과가 없습니다. 먼저 python main.py analyze 를 실행하세요.")
        return
    if not rows:
        print(f"{args.page}페이지에는 결과가 없습니다. (전체 {total}건)")
        return

    # 전체 페이지 수 = 올림(total / limit).
    last_page = (total + args.limit - 1) // args.limit
    print(f"=== 저장된 인사이트 {total}건 (페이지 {args.page}/{last_page}) ===")
    print(f"{'ID':>4}  {'분석일시':<19}  {'카테고리':<8}  {'건수':>4}  키워드")
    for row in rows:
        print(
            f"{row['id']:>4}  {_format_datetime(row['created_at']):<19}  "
            f"{(row['category'] or '전체'):<8}  {row['news_count'] or 0:>4}  "
            f"{_format_keywords(row['keywords'])}"
        )
    print("\n상세 조회: python main.py analyze --show <ID>")


def _show_insight_detail(conn, insight_id: int) -> None:
    """인사이트 1건의 전체 내용을 출력한다."""
    row = fetch_insight(conn, insight_id)
    if row is None:
        logger.error("id=%d 인 분석 결과가 없습니다.", insight_id)
        return

    period = f"{row['date_from'] or '전체'} ~ {row['date_to'] or '전체'}"
    print(f"=== AI 인사이트 분석 결과 (id={row['id']}) ===")
    print(f"분석 일시: {_format_datetime(row['created_at'])}")
    print(f"대상 기간: {period}")
    print(f"카테고리 : {row['category'] or '전체'}")
    print(f"분석 건수: {row['news_count'] or 0}건")
    print("\n[주요 트렌드]")
    print(row["trends"] or "-")
    print("\n[핵심 키워드]")
    print(_format_keywords(row["keywords"]) or "-")


def _format_keywords(raw: str | None) -> str:
    """DB에 JSON 문자열로 저장된 keywords를 '가, 나, 다' 형태로 되돌린다.

    과거 데이터나 AI 응답 형태가 달라 JSON이 아닐 수도 있어 그대로 반환한다.
    """
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    return ", ".join(str(k) for k in parsed) if isinstance(parsed, list) else str(parsed)


def _format_datetime(raw: str | None) -> str:
    """created_at(ISO UTC)을 'YYYY-MM-DD HH:MM:SS'로 짧게 보여준다."""
    if not raw:
        return "-"
    return raw.replace("T", " ")[:19]


def _create_insight(conn, args: argparse.Namespace) -> None:
    config = load_config()

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
        return

    insight_id = insert_insight(conn, insight)
    logger.info("인사이트 저장 완료: id=%d", insight_id)

    # 방금 저장한 결과를 상세 조회와 같은 형식으로 그대로 보여준다.
    _show_insight_detail(conn, insight_id)
