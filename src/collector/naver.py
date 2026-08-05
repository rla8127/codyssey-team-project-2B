"""네이버 뉴스 검색 API 클라이언트.

https://naverapihub.apigw.ntruss.com/search/v1/news 를 호출해서 원본 응답 item을 그대로 반환한다.
HTML 태그/엔티티 정제는 clean 단계(clean.py)에서 처리한다.
"""

import requests

from src.common.logger import get_logger

logger = get_logger(__name__)


def fetch_naver_news(config: dict, query: str, limit: int) -> list[dict]:
    """네이버 뉴스 검색 API로 뉴스를 수집해 원본 item 리스트를 반환한다.

    limit은 1~100 범위로 제한되며, API를 한 번만 호출한다.
    """
    api_config = config["news_sources"]["api"]
    client_id = api_config.get("client_id", "")
    client_secret = api_config.get("client_secret", "")
    if not client_id or not client_secret:
        raise RuntimeError(
            "NAVER_CLIENT_ID/NAVER_CLIENT_SECRET이 설정되지 않았습니다. .env를 확인하세요."
        )

    base_url = api_config["base_url"]
    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret,
    }
    timeout_sec = config.get("http", {}).get("timeout_sec", 10)
    max_retries = config.get("http", {}).get("max_retries", 2)

    params = {"query": query, "display": limit, "start": 1, "sort": "date"}
    response = _request_with_retry(base_url, headers, params, timeout_sec, max_retries)
    if response is None:
        return []

    return response.get("items", [])

# 과제 의도가 HTTP Retry 정책도 따로 만들라는거 같아서 걍 만듬.
# 말그대로 HTTP 요청 실패 시 재시도하는 함수
def _request_with_retry(
    base_url: str, headers: dict, params: dict, timeout_sec: float, max_retries: int
) -> dict | None:
    for attempt in range(1, max_retries + 2):
        try:
            resp = requests.get(base_url, headers=headers, params=params, timeout=timeout_sec)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            logger.warning("네이버 API 요청 실패 (%d/%d): %s", attempt, max_retries + 1, e)
    logger.error("네이버 API 요청 최종 실패: params=%s", params)
    return None

# https://api.ncloud-docs.com/docs/naver-api-hub-search-news
# 네이버 뉴스 API 응답 예시 (raw item):
# {
#     "lastBuildDate": "Thu, 11 Jun 2026 19:03:00 +0900",
#     "total": 2388472,
#     "start": 1,
#     "display": 2,
#     "items": [
#         {
#             "title": "네이버, '로컬 그라운드' 캠페인 추진 … AI 기반 지역상권 지원 확대",
#             "originallink": "http://www.worktoday.co.kr/news/articleView.html?idxno=85535",
#             "link": "http://www.worktoday.co.kr/news/articleView.html?idxno=85535",
#             "description": "네이버는 부산 지역과의 협력 사례로 로컬 브랜드 '모모스 <b>커피</b>'를 소개하며, 플랫폼을 통한 지역 브랜드의 전국 확산 가능성을 강조했다. 이번 캠페인은 로컬 상권의 디지털 전환과 관광·소비 활성화를 동시에 겨냥한... ",
#             "pubDate": "Thu, 11 Jun 2026 18:34:00 +0900"
#         },
#         {
#             "title": "인천시, 송도 아파트서 '마을기업 연계축제' 개최",
#             "originallink": "https://www.gukjenews.com/news/articleView.html?idxno=3606281",
#             "link": "https://www.gukjenews.com/news/articleView.html?idxno=3606281",
#             "description": "행사장에서는 천연버물리, <b>커피</b>드립백, 나전칠기 키링 만들기 등 온 가족이 즐길 수 있는 무료 문화 체험 프로그램도 운영된다. 마을기업 연계축제는 주민 생활공간인 아파트 단지에서 열려, 마을기업의 가치와 제품을... ",
#             "pubDate": "Thu, 11 Jun 2026 18:30:00 +0900"
#         }
#     ]
# }