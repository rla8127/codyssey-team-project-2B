"""CLI 진입점. 서브커맨드 라우팅만 담당하고 실제 로직은 각 모듈에 위임한다.

담당자별로 자기 모듈(src/collector, src/ai, src/report, src/query) 안에
파일을 자유롭게 구성하고, subparsers를 등록하는 함수 하나를 여기서 import해서
아래 register 호출부에 추가한다.

예시 (파일명/함수명은 각자 자유롭게):
    from src.collector.cli import register_subparser as register_collector
    ...
    register_collector(subparsers)  # fetch, clean

사용 예:
    python main.py fetch --source naver --limit 20
    python main.py clean --all
    python main.py summarize --unsummarized --limit 3
    python main.py analyze --date-from 2026-01-01 --date-to 2026-01-10 --category IT
    python main.py report --format md
    python main.py export --format csv --status summarized
"""

import argparse
import sys

from src.common.config import load_config
from src.common.logger import get_logger, setup_logging

from src.collector.cli import register_subparser as register_collector  # A: fetch, clean
from src.ai.cli import register_subparser as register_ai  # B: summarize, analyze
from src.report.cli import register_subparser as register_report  # C: report, export
from src.query.cli import register_subparser as register_query  # D(보너스): list, show


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py", description="AI 뉴스 트렌드 및 종합 분석 리포트 CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_collector(subparsers)
    register_ai(subparsers)
    register_report(subparsers)
    register_query(subparsers)

    return parser


def main() -> None:
    config = load_config()
    setup_logging(
        level=config.get("logging", {}).get("level", "INFO"),
        log_file=config.get("logging", {}).get("file"),
    )
    logger = get_logger(__name__)

    parser = build_parser()
    args = parser.parse_args()

    try:
        args.func(args)
    except NotImplementedError as e:
        logger.error("미구현 기능: %s", e)
        sys.exit(1)
    except Exception:
        logger.exception("실행 중 오류 발생")
        sys.exit(1)


if __name__ == "__main__":
    main()
