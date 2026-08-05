"""collector 모듈 서브커맨드: fetch, clean."""

import argparse

from src.collector import naver
from src.common.config import load_config
from src.common.db import fetch_raw_news, get_connection, init_db, insert_news_raw, update_news_clean
from src.common.logger import get_logger
from src.collector.clean import clean_news_item
from src.collector.crawl import fetch_crawled_news
from src.collector.naver import fetch_naver_news

logger = get_logger(__name__)


def _limit_type(value: str) -> int:
    n = int(value)
    if not 1 <= n <= 100:
        raise argparse.ArgumentTypeError("--limit은 1~100 범위여야 합니다.")
    return n


def register_subparser(subparsers: argparse._SubParsersAction) -> None:
    # collector(A) 전용 서브커맨드 등록
    # python main.py fetch --source naver
    # 다중 인자 호출할 경우 args.query, args.category, args.limit 등으로 전달
    fetch_parser = subparsers.add_parser("fetch", help="뉴스 수집")
    fetch_parser.add_argument("--source", default="naver", choices=["naver", "crawl"])
    # 네이버 검색창에 IT라고 치는것과 비슷한 개념, API 측에서 색인해서 조회함.
    # --source crawl에서는 사용되지 않음 (전자신문 AI·SW 섹션 고정).
    fetch_parser.add_argument("--query", default="IT")
    # category는 DB에 저장되는 값이므로, API 호출 시에는 사용되지 않음.
    fetch_parser.add_argument("--category", default=None)
    # argparse가 자동으로 변수를 type에 선언된 함수에 전달
    fetch_parser.add_argument("--limit", type=_limit_type, default=20, metavar="{1..100}")
    fetch_parser.set_defaults(func=_run_fetch)

    # python main.py clean --all
    clean_parser = subparsers.add_parser("clean", help="raw 뉴스 정제")
    # store_true는 옵션이 없어도 True로 설정되므로 실행되고, 함수 로직에서 에러 로그 뱉도록 구현하였음.
    clean_parser.add_argument("--all", action="store_true", help="raw 상태 뉴스를 모두 정제")
    clean_parser.set_defaults(func=_run_clean)

# fetch 명령어
# 다중 인자 호출할 경우 args.query, args.category, args.limit 등으로 전달
def _run_fetch(args: argparse.Namespace) -> None:
    config = load_config()
    logger.info("뉴스 수집 시작: source=%s, limit=%d", args.source, args.limit)

    if args.source == "crawl":
        raw_items = fetch_crawled_news(config, limit=args.limit)
        source_name, collect_method = "etnews", "crawl"
    else:
        raw_items = fetch_naver_news(config, query=args.query, limit=args.limit)
        source_name, collect_method = "naver", "api"

    # DB 연결
    conn = get_connection()
    init_db(conn)

    # 내가 디버깅하려고 만듬. 없어도 됨.
    success, skipped, failed = 0, 0, 0

    # 중복 시 skip(default), upsert 옵션 설정 가져오기
    duplicate_policy = config.get("duplicate_policy", "skip")

    for raw_item in raw_items:
        try:
            news_item = {
                "source_url": raw_item.get("originallink") or raw_item.get("link"),
                "source_name": source_name,
                "collect_method": collect_method,
                "category": args.category,
                "title": raw_item.get("title"),
                "content": raw_item.get("description"),
                "published_at": raw_item.get("pubDate"),
            }
            # source_url이 news_raw에 이미 있으면 중복으로 판단 (UNIQUE 제약).
            # skip 정책이면 insert_news_raw가 INSERT OR IGNORE로 조용히 무시하고 False 반환.
            if insert_news_raw(conn, news_item, duplicate_policy=duplicate_policy):
                success += 1
            else:
                logger.info("중복 뉴스 skip: %s", news_item["source_url"])
                skipped += 1
        except Exception:
            logger.exception("뉴스 저장 실패: %s", raw_item.get("link"))
            failed += 1

    conn.close()
    logger.info("수집 완료: %d건 성공, %d건 skip, %d건 실패", success, skipped, failed)
    logger.info("raw 저장소에 저장 완료")


def _run_clean(args: argparse.Namespace) -> None:
    if not args.all:
        logger.error("clean은 현재 --all 옵션만 지원합니다.")
        return

    conn = get_connection()
    init_db(conn)

    raw_rows = fetch_raw_news(conn)
    logger.info("정제 대상: %d건", len(raw_rows))

    success, skipped = 0, 0
    for row in raw_rows:
        cleaned = clean_news_item(row)
        if cleaned is None:
            skipped += 1
            continue
        update_news_clean(conn, row["id"], cleaned)
        success += 1

    conn.close()
    logger.info("정제 완료: %d건 성공, %d건 스킵", success, skipped)
