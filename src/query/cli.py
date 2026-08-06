"""query 모듈 서브커맨드: list, show (보너스 과제).

뉴스 목록 조회(list)와 상세 조회(show)를 제공한다.
조건 필터링(카테고리/날짜/키워드)과 페이지네이션을 지원한다.
"""

import argparse
import unicodedata

from src.common.db import (
    count_news,
    fetch_news_detail,
    fetch_news_list,
    get_connection,
    init_db,
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
    # python main.py list --category IT --page 1
    list_parser = subparsers.add_parser("list", help="뉴스 목록 조회")
    list_parser.add_argument("--category", default=None, help="카테고리 필터")
    list_parser.add_argument("--date-from", default=None, help="시작일 (YYYY-MM-DD)")
    list_parser.add_argument("--date-to", default=None, help="종료일 (YYYY-MM-DD)")
    list_parser.add_argument("--keyword", default=None, help="제목/본문/요약 검색어")
    list_parser.add_argument(
        "--status", choices=["clean", "summarized"], default=None, help="상태 필터"
    )
    list_parser.add_argument("--limit", type=_limit_type, default=10, metavar="{1..100}")
    list_parser.add_argument("--page", type=_page_type, default=1, metavar="N")
    list_parser.set_defaults(func=_run_list)

    # python main.py show --id 1
    show_parser = subparsers.add_parser("show", help="뉴스 상세 조회")
    # 요구사항 예시가 `show --id 1` 형태라 옵션으로 받되, `show 1`도 되도록 위치 인자를 함께 둔다.
    show_parser.add_argument("news_id", type=int, nargs="?", help="뉴스 id (예: show 1)")
    show_parser.add_argument("--id", type=int, dest="id_opt", help="뉴스 id (예: show --id 1)")
    show_parser.add_argument("--full", action="store_true", help="본문 전체 출력 (기본은 일부만)")
    show_parser.set_defaults(func=_run_show)


def _run_list(args: argparse.Namespace) -> None:
    conn = get_connection()
    init_db(conn)
    try:
        filters = {
            "category": args.category,
            "date_from": args.date_from,
            "date_to": args.date_to,
            "keyword": args.keyword,
            "status": args.status,
        }
        total = count_news(conn, **filters)
        offset = (args.page - 1) * args.limit
        rows = fetch_news_list(conn, **filters, limit=args.limit, offset=offset)

        if total == 0:
            if any(filters.values()):
                print("조건에 맞는 뉴스가 없습니다.")
            else:
                print("저장된 뉴스가 없습니다. 먼저 python main.py fetch 를 실행하세요.")
            return
        if not rows:
            print(f"{args.page}페이지에는 결과가 없습니다. (전체 {total}건)")
            return

        last_page = (total + args.limit - 1) // args.limit
        print(f"=== 뉴스 {total}건 (페이지 {args.page}/{last_page}) ===")
        print(f"{'ID':>4}  {'발행일':<10}  {'카테고리':<8}  {'상태':<10}  제목")
        for row in rows:
            published = (row.get("published_at") or row.get("collected_at") or "")[:10]
            print(
                f"{row['id']:>4}  {published:<10}  "
                f"{_pad(row.get('category') or '미분류', 8)}  "
                f"{(row.get('status') or ''):<10}  "
                f"{_truncate(row.get('title') or '', 50)}"
            )

        if args.page < last_page:
            print(f"\n다음 페이지: --page {args.page + 1}")
        print("상세 조회: python main.py show --id <ID>")
    finally:
        conn.close()


def _run_show(args: argparse.Namespace) -> None:
    # 위치 인자와 --id 중 주어진 쪽을 쓴다.
    news_id = args.id_opt if args.id_opt is not None else args.news_id
    if news_id is None:
        logger.error("뉴스 id가 필요합니다. 예: python main.py show --id 1")
        return

    conn = get_connection()
    init_db(conn)
    try:
        row = fetch_news_detail(conn, news_id)
        if row is None:
            logger.error("id=%d 인 뉴스가 없습니다.", news_id)
            return

        print(f"=== 뉴스 상세 (id={row['id']}) ===")
        print(f"제목    : {row.get('title') or '-'}")
        print(f"카테고리: {row.get('category') or '미분류'}")
        print(f"발행일  : {row.get('published_at') or '-'}")
        print(f"수집일  : {row.get('collected_at') or '-'}")
        print(f"출처    : {row.get('source_name') or '-'} ({row.get('collect_method') or '-'})")
        print(f"URL     : {row.get('source_url') or '-'}")
        print(f"상태    : {row.get('status') or '-'}")

        if row.get("summary"):
            print(f"\n[AI 요약] (감성: {row.get('sentiment') or '-'})")
            print(row["summary"])
        else:
            print("\n[AI 요약] 아직 요약되지 않았습니다. `python main.py summarize --id "
                  f"{row['id']}` 로 요약할 수 있습니다.")

        content = row.get("content") or ""
        print("\n[본문]")
        if not content:
            print("-")
        elif args.full:
            print(content)
        else:
            # 기본은 앞부분만 보여준다 (본문이 길어 터미널을 덮는 것을 막는다).
            print(_truncate(content, 500))
            if len(content) > 500:
                print(f"\n... (전체 {len(content)}자, 전체 보기: --full)")
    finally:
        conn.close()


def _width(text: str) -> int:
    """터미널에서 차지하는 칸 수. 한글·전각 문자는 2칸으로 센다."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _truncate(text: str, max_width: int) -> str:
    """표시 폭 기준으로 자르고 넘치면 '...'을 붙인다."""
    text = text.replace("\n", " ").strip()
    if _width(text) <= max_width:
        return text

    out, used = [], 0
    for ch in text:
        w = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        if used + w > max_width - 3:
            break
        out.append(ch)
        used += w
    return "".join(out) + "..."


def _pad(text: str, width: int) -> str:
    """표시 폭 기준으로 오른쪽을 공백 채움 (한글이 섞여도 열이 밀리지 않게)."""
    return text + " " * max(0, width - _width(text))
