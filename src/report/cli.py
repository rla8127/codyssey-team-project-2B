"""report 모듈 서브커맨드: report, export."""

import argparse

from src.common.db import (
    count_by_category,
    count_by_date,
    count_by_sentiment,
    fetch_latest_insight,
    fetch_news_for_export,
    get_connection,
    init_db,
    quality_metrics,
    top_keywords,
)
from src.common.logger import get_logger
from src.report.charts import (
    plot_category_counts,
    plot_daily_counts,
    plot_sentiment,
    setup_korean_font,
)
from src.report.export import export_rows
from src.report.summary import build_report, save_report

logger = get_logger(__name__)


def register_subparser(subparsers: argparse._SubParsersAction) -> None:
    # python main.py report --format md
    report_parser = subparsers.add_parser("report", help="차트 생성 + 종합 리포트")
    report_parser.add_argument(
        "--format", choices=["md", "txt"], default="md", help="리포트 파일 형식 (기본 md)"
    )
    report_parser.add_argument("--category", default=None, help="인사이트 카테고리 필터")
    report_parser.add_argument("--top", type=int, default=10, help="TOP 키워드 개수 (기본 10)")
    report_parser.add_argument(
        "--no-chart", action="store_true", help="차트 생성을 건너뛰고 리포트만 만든다"
    )
    report_parser.add_argument(
        "--no-save", action="store_true", help="파일로 저장하지 않고 콘솔에만 출력한다"
    )
    report_parser.set_defaults(func=_run_report)

    # python main.py export --format csv --status summarized
    export_parser = subparsers.add_parser("export", help="뉴스 데이터 내보내기")
    export_parser.add_argument(
        "--format", choices=["csv", "jsonl", "excel"], default="csv", help="내보내기 형식"
    )
    export_parser.add_argument(
        "--status", choices=["clean", "summarized"], default=None, help="상태 필터"
    )
    export_parser.add_argument("--category", default=None, help="카테고리 필터")
    export_parser.set_defaults(func=_run_export)


def _run_report(args: argparse.Namespace) -> None:
    conn = get_connection()
    init_db(conn)
    try:
        by_category = count_by_category(conn)
        by_date = count_by_date(conn)
        metrics = quality_metrics(conn)
        keywords = top_keywords(conn, limit=args.top)
        insight = fetch_latest_insight(conn, category=args.category)

        chart_paths = []
        if not args.no_chart:
            # 차트를 그리기 전에 반드시 한글 폰트를 먼저 설정한다.
            setup_korean_font()
            candidates = [
                plot_category_counts(by_category),
                plot_daily_counts(by_date),
                plot_sentiment(count_by_sentiment(conn)),
            ]
            # 데이터가 없어 건너뛴 차트는 None이 반환되므로 걸러낸다.
            chart_paths = [p for p in candidates if p is not None]
            logger.info("차트 %d개 생성 완료", len(chart_paths))

        content = build_report(
            metrics=metrics,
            by_category=by_category,
            by_date=by_date,
            top_keywords=keywords,
            insight=insight,
            chart_paths=chart_paths,
            fmt=args.format,
        )

        # 요구사항: 콘솔 출력 및 파일 저장을 모두 지원한다.
        print(content)
        if not args.no_save:
            save_report(content, fmt=args.format)
    finally:
        conn.close()


def _run_export(args: argparse.Namespace) -> None:
    conn = get_connection()
    init_db(conn)
    try:
        rows = fetch_news_for_export(conn, status=args.status, category=args.category)
        logger.info(
            "내보내기 대상: %d건 (status=%s, category=%s)",
            len(rows),
            args.status or "전체",
            args.category or "전체",
        )
        export_rows(rows, args.format)
    finally:
        conn.close()
