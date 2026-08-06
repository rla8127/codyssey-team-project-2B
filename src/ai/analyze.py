"""AI 인사이트 분석.

기간/카테고리로 필터링한 뉴스를 묶어서 AI에 넘기고, 주요 트렌드와 핵심 키워드를
받아 insights 테이블에 저장할 dict를 만든다.
"""

import json

from src.ai.client import ask
from src.common.logger import get_logger

logger = get_logger(__name__)

# 한 번에 분석에 넣을 기사 수 상한 (프롬프트가 과도하게 길어지는 것을 방지).
MAX_ITEMS = 50
# 기사당 프롬프트에 넣을 본문 길이 (요약이 있으면 요약을 우선 사용한다).
MAX_SNIPPET_CHARS = 300

SYSTEM_PROMPT = (
    "너는 IT 뉴스 트렌드 분석가다. 주어진 뉴스 목록을 종합 분석한다. "
    "반드시 아래 JSON 형식으로만 답한다. 다른 설명은 붙이지 않는다.\n"
    '{"trends": "주요 트렌드를 한국어 3~5문장으로", '
    '"keywords": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"]}'
)


def analyze_news(
    config: dict,
    items: list[dict],
    date_from: str | None,
    date_to: str | None,
    category: str | None,
) -> dict | None:
    """뉴스 묶음을 분석해 insights 테이블에 넣을 dict를 반환한다.

    분석 대상이 없거나 AI 호출이 최종 실패하면 None을 반환한다.
    """
    if not items:
        logger.warning("분석 대상 뉴스가 없습니다.")
        return None

    user_prompt = _build_prompt(items[:MAX_ITEMS])
    answer = ask(config, SYSTEM_PROMPT, user_prompt)
    if answer is None:
        return None

    parsed = _parse_answer(answer)
    if parsed is None:
        return None

    return {
        "date_from": date_from,
        "date_to": date_to,
        "category": category,
        "news_count": len(items),
        "trends": parsed["trends"],
        # keywords는 리스트라 TEXT 컬럼에 저장하기 위해 JSON 문자열로 직렬화한다.
        "keywords": json.dumps(parsed["keywords"], ensure_ascii=False),
    }


def _build_prompt(items: list[dict]) -> str:
    """기사 목록을 '번호. [카테고리] 제목 - 요약' 형태의 텍스트로 만든다."""
    lines = []
    for i, item in enumerate(items, start=1):
        # 요약이 이미 있으면 요약을, 없으면 본문 앞부분을 쓴다.
        snippet = (item.get("summary") or item.get("content") or "").strip()
        snippet = snippet.replace("\n", " ")[:MAX_SNIPPET_CHARS]
        category = item.get("category") or "미분류"
        lines.append(f"{i}. [{category}] {item.get('title')} - {snippet}")
    return "다음 뉴스들을 분석해줘.\n\n" + "\n".join(lines)


def _parse_answer(answer: str) -> dict | None:
    """AI 응답에서 JSON을 추출해 파싱한다.

    모델이 ```json 코드블록으로 감싸는 경우가 있어 중괄호 범위만 잘라 파싱한다.
    """
    start = answer.find("{")
    end = answer.rfind("}")
    if start == -1 or end == -1:
        logger.error("AI 응답에서 JSON을 찾지 못했습니다: %s", answer[:200])
        return None

    try:
        data = json.loads(answer[start : end + 1])
    except json.JSONDecodeError as e:
        logger.error("AI 응답 JSON 파싱 실패: %s", e)
        return None

    trends = data.get("trends")
    keywords = data.get("keywords")
    if not trends or not isinstance(keywords, list):
        logger.error("AI 응답에 trends/keywords가 없습니다: %s", answer[:200])
        return None

    return {"trends": trends, "keywords": keywords}
