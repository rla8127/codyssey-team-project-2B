"""리포트 본문 생성.

요구사항 7번: 품질 지표 2개 이상, TOP N 집계 1개 이상, AI 인사이트 결과를 포함한다.
콘솔 출력과 파일(TXT/MD) 저장에 같은 본문을 쓰기 위해 문자열을 만들어 반환한다.
"""

import json
from datetime import datetime
from pathlib import Path

from src.common.logger import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPORT_DIR = BASE_DIR / "output" / "reports"


def build_report(
    metrics: dict,
    by_category: dict[str, int],
    by_date: dict[str, int],
    top_keywords: list[tuple[str, int]],
    insight: dict | None,
    chart_paths: list[Path],
    fmt: str = "md",
) -> str:
    """리포트 전체 본문을 문자열로 만든다.

    fmt이 'md'면 마크다운 헤딩을, 'txt'면 평문 구분선을 쓴다.
    """
    md = fmt == "md"
    lines: list[str] = []

    def heading(text: str, level: int = 2) -> None:
        """포맷에 맞춰 제목을 추가한다 (md는 '##', txt는 밑줄)."""
        if md:
            lines.append(f"\n{'#' * level} {text}\n")
        else:
            lines.append(f"\n[{text}]")

    # --- 머리말 ---
    title = "AI 뉴스 트렌드 및 종합 분석 리포트"
    if md:
        lines.append(f"# {title}")
    else:
        lines.append("=" * 60)
        lines.append(title)
        lines.append("=" * 60)
    lines.append(f"생성 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # --- 품질 지표 (요구사항: 2개 이상) ---
    heading("품질 지표")
    lines.append(f"- 수집(raw) 건수      : {metrics['raw_total']}건")
    lines.append(f"- 정제(clean) 건수    : {metrics['clean_total']}건")
    lines.append(f"- 정제 성공률         : {metrics['clean_rate']}%")
    lines.append(
        f"- 요약 완료율         : {metrics['summarized_rate']}% "
        f"({metrics['summarized_total']}/{metrics['clean_total']}건)"
    )
    lines.append(f"- 본문 결측          : {metrics['missing_content']}건")
    lines.append(f"- 카테고리 결측       : {metrics['missing_category']}건")
    lines.append(f"- 발행일 결측         : {metrics['missing_date']}건")

    # --- TOP N 집계 (요구사항: 1개 이상) ---
    heading("TOP 카테고리")
    if by_category:
        total = sum(by_category.values())
        for rank, (name, cnt) in enumerate(list(by_category.items())[:5], start=1):
            share = round(cnt / total * 100, 1) if total else 0.0
            lines.append(f"{rank}. {name} — {cnt}건 ({share}%)")
    else:
        lines.append("- 데이터 없음")

    heading("TOP 키워드 (AI 인사이트 기준)")
    if top_keywords:
        for rank, (word, cnt) in enumerate(top_keywords, start=1):
            lines.append(f"{rank}. {word} ({cnt}회)")
    else:
        lines.append("- 아직 분석된 인사이트가 없습니다. `python main.py analyze` 실행 후 다시 시도하세요.")

    # --- 일자별 추이 ---
    heading("일자별 수집 추이")
    if by_date:
        for day, cnt in by_date.items():
            # 막대를 문자로 그려 콘솔에서도 추이가 눈에 들어오게 한다.
            lines.append(f"- {day}: {'█' * min(cnt, 40)} {cnt}건")
    else:
        lines.append("- 데이터 없음")

    # --- AI 인사이트 ---
    heading("AI 인사이트 분석")
    if insight:
        period = f"{insight.get('date_from') or '전체'} ~ {insight.get('date_to') or '전체'}"
        lines.append(f"- 분석 id   : {insight['id']}")
        lines.append(f"- 대상 기간 : {period}")
        lines.append(f"- 카테고리  : {insight.get('category') or '전체'}")
        lines.append(f"- 분석 건수 : {insight.get('news_count') or 0}건")
        lines.append("")
        lines.append("주요 트렌드:")
        lines.append(insight.get("trends") or "-")
        lines.append("")
        lines.append(f"핵심 키워드: {_format_keywords(insight.get('keywords'))}")
    else:
        lines.append("- 저장된 인사이트가 없습니다. `python main.py analyze` 를 먼저 실행하세요.")

    # --- 차트 ---
    heading("차트")
    if chart_paths:
        for path in chart_paths:
            # 마크다운은 이미지로 삽입해 뷰어에서 바로 보이게 한다.
            if md:
                lines.append(f"![{path.stem}]({path.relative_to(BASE_DIR)})")
            else:
                lines.append(f"- {path.relative_to(BASE_DIR)}")
    else:
        lines.append("- 생성된 차트가 없습니다.")

    return "\n".join(lines)


def save_report(content: str, fmt: str = "md") -> Path:
    """리포트를 output/reports/에 저장하고 경로를 반환한다.

    파일명에 생성 시각을 넣어 실행할 때마다 이전 리포트가 덮이지 않게 한다.
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"report_{stamp}.{fmt}"

    path.write_text(content, encoding="utf-8")
    logger.info("리포트 저장: %s", path)
    return path


def _format_keywords(raw: str | None) -> str:
    """JSON 문자열로 저장된 keywords를 '가, 나, 다' 형태로 되돌린다."""
    if not raw:
        return "-"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    return ", ".join(str(k) for k in parsed) if isinstance(parsed, list) else str(parsed)
