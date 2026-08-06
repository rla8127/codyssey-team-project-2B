"""뉴스 본문 AI 요약.

news_clean의 content를 AI로 요약해 summary/sentiment 컬럼을 채운다.
본문이 길 수 있으므로 프롬프트에 넣기 전에 잘라서 토큰 낭비를 막는다.
"""

from src.ai.client import ask
from src.common.logger import get_logger

logger = get_logger(__name__)

# 기사 본문이 매우 길 경우 요약에 필요한 앞부분만 사용한다.
MAX_CONTENT_CHARS = 4000

SYSTEM_PROMPT = (
    "너는 IT 뉴스 요약 전문가다. 기사를 한국어 3문장 이내로 요약한다. "
    "사실만 쓰고 추측은 하지 않는다. "
    "마지막 줄에 반드시 '감정: 긍정' 또는 '감정: 부정' 또는 '감정: 중립' 형식으로 "
    "기사 논조를 한 줄 덧붙인다."
)


def summarize_news_item(config: dict, item: dict) -> dict | None:
    """기사 1건을 요약해 {"summary", "sentiment"}를 반환한다.

    본문이 없거나 AI 호출이 최종 실패하면 None을 반환한다 (호출부에서 스킵).
    """
    content = (item.get("content") or "").strip()
    if not content:
        logger.warning("본문이 없어 요약 스킵: id=%s", item.get("id"))
        return None

    title = item.get("title") or ""
    user_prompt = f"제목: {title}\n\n본문:\n{content[:MAX_CONTENT_CHARS]}"

    answer = ask(config, SYSTEM_PROMPT, user_prompt)
    if answer is None:
        return None

    summary, sentiment = _split_sentiment(answer)
    return {"summary": summary, "sentiment": sentiment}


def _split_sentiment(answer: str) -> tuple[str, str | None]:
    """응답 마지막 줄의 '감정: X'를 분리해 (요약본문, 감정)으로 나눈다.

    모델이 형식을 지키지 않을 수 있으므로 못 찾으면 감정을 None으로 둔다.
    """
    lines = [line.strip() for line in answer.splitlines() if line.strip()]
    if lines and lines[-1].startswith("감정:"):
        sentiment = lines[-1].removeprefix("감정:").strip()
        return "\n".join(lines[:-1]).strip(), sentiment or None
    return answer, None
