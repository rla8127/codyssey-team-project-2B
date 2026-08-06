"""OpenAI API 클라이언트 래퍼.

config.json의 ai 설정(provider/model/timeout_sec)과 .env의 AI_API_KEY를 사용한다.
naver.py의 _request_with_retry와 동일하게 실패 시 재시도하고, 최종 실패하면
None을 반환해서 호출부가 로깅 후 스킵할 수 있게 한다.
"""

from openai import OpenAI, OpenAIError

from src.common.logger import get_logger

logger = get_logger(__name__)

_client: OpenAI | None = None


def get_client(config: dict) -> OpenAI:
    """OpenAI 클라이언트를 생성한다 (모듈 내 1회 캐싱)."""
    global _client
    if _client is not None:
        return _client

    ai_config = config["ai"]
    api_key = ai_config.get("api_key", "")
    if not api_key:
        raise RuntimeError("AI_API_KEY가 설정되지 않았습니다. .env를 확인하세요.")

    _client = OpenAI(api_key=api_key, timeout=ai_config.get("timeout_sec", 30))
    return _client


def ask(config: dict, system_prompt: str, user_prompt: str) -> str | None:
    """AI API를 호출해 응답 텍스트를 반환한다. 최종 실패 시 None.

    요구사항 "API 실패 시 로깅 후 스킵"을 위해 예외를 던지지 않는다.
    """
    ai_config = config["ai"]
    model = ai_config["model"]
    max_retries = config.get("http", {}).get("max_retries", 2)

    client = get_client(config)

    # max_retries=2면 최초 1회 + 재시도 2회 = 총 3번 시도한다.
    for attempt in range(1, max_retries + 2):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = resp.choices[0].message.content
            if content:
                return content.strip()
            logger.warning("AI 응답이 비어 있습니다 (%d/%d)", attempt, max_retries + 1)
        except OpenAIError as e:
            logger.warning("AI API 요청 실패 (%d/%d): %s", attempt, max_retries + 1, e)

    logger.error("AI API 요청 최종 실패: model=%s", model)
    return None
