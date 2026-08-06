# BeatufulSoup4 이용해서 크롤링함.
# 크롤링은 API 정의서가 없어서 말그대로 사이트 주소에서 어떻게 HTML 구조 뿌려주는지 인지한 뒤,
# 코드를 짜야함. 그래서 불편하고 코드를 보면 별에별 방법으로 HTML 구조를 탐색하고 있음.
# 전자뉴스를 크롤링했으며, 전자뉴스에서 응답하는 HTML 구조에 맞게 코드를 작성함.

import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.common.logger import get_logger

logger = get_logger(__name__)

# 기본 UA로 요청하면 차단하는 사이트가 있어 브라우저 UA를 사용한다.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}


def fetch_crawled_news(config: dict, limit: int) -> list[dict]:
    """전자신문 AI·SW 섹션을 크롤링해 기사 리스트를 반환한다.

    limit은 1~100 범위로 제한된다 (naver.py와 동일한 제약).
    """
    # 하드코딩 대신 config.json에서 읽어 코드 수정 없이 대상/간격을 바꿀 수 있게 한다.
    crawl_config = config["news_sources"]["crawl"]
    base_url = crawl_config["base_url"]
    list_path = crawl_config["list_path"]
    interval_sec = crawl_config.get("request_interval_sec", 1.0)
    timeout_sec = config.get("http", {}).get("timeout_sec", 10)
    max_retries = config.get("http", {}).get("max_retries", 2)

    # 1단계: 목록 페이지들을 돌며 기사 상세 URL만 먼저 모은다.
    links = _collect_article_links(
        base_url, list_path, limit, interval_sec, timeout_sec, max_retries
    )

    # 2단계: 수집한 URL을 하나씩 방문해 본문을 추출한다.
    items: list[dict] = []
    for link in links:
        time.sleep(interval_sec)
        item = _fetch_article(link, timeout_sec, max_retries)
        if item is not None:
            items.append(item)

    return items


def _collect_article_links(
    base_url: str,
    list_path: str,
    limit: int,
    interval_sec: float,
    timeout_sec: float,
    max_retries: int,
) -> list[str]:
    """목록 페이지를 페이지네이션(&page=N)하며 기사 상세 링크를 limit개 모은다."""
    links: list[str] = []
    page = 1
    # 종료 조건 ①: limit개를 다 모으면 멈춘다.
    while len(links) < limit:
        # 목록 URL 예시: https://www.etnews.com/news/section.html?id1=04&page=1
        url = f"{base_url}{list_path}&page={page}"
        html = _request_with_retry(url, timeout_sec, max_retries)
        # 종료 조건 ②: 요청이 최종 실패하면 지금까지 모은 것만 반환한다.
        if html is None:
            break

        # HTML 문자열을 탐색 가능한 트리 구조로 파싱한다.
        soup = BeautifulSoup(html, "html.parser")
        # select()는 CSS 선택자로 매칭되는 태그를 "전부" 리스트로 준다.
        # "div.text > strong > a" = class가 text인 div의 직계 자식 strong, 그 직계 자식 a
        # href는 상대 경로(/20260806000072)로 오므로 절대 URL로 변환한다.
        page_links = [
            urljoin(base_url, a["href"]) # 이렇게 합침 "https://www.etnews.com/20260806000072"
            for a in soup.select("div.text > strong > a")
            if a.get("href")  # href 속성이 없는 <a>는 건너뛴다
        ]
        # 종료 조건 ③: 기사가 하나도 없으면 마지막 페이지를 지난 것이다.
        if not page_links:
            break

        links.extend(page_links)
        page += 1
        # 사이트가 빈 페이지에도 200을 주는 경우를 대비한 무한루프 방지
        if page > 20:
            break

        time.sleep(interval_sec)

    # 마지막 페이지에서 limit을 넘겨 모았을 수 있으므로 잘라낸다.
    return links[:limit]


def _fetch_article(url: str, timeout_sec: float, max_retries: int) -> dict | None:
    """기사 상세 페이지에서 title/description/pubDate를 추출한다."""
    html = _request_with_retry(url, timeout_sec, max_retries)
    if html is None:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # select_one()은 첫 번째 매칭 태그 "하나"만 준다. 없으면 예외 대신 None.
    body_tag = soup.select_one("#articleBody")  # id가 articleBody인 태그
    # <meta>는 화면에 안 보이는 태그다. 화면의 "2026.08.06" 같은 표시 텍스트 대신
    # 메타태그를 쓰는 이유는 ISO 8601 표준 형식이라 파싱이 안정적이기 때문.
    date_tag = soup.select_one('meta[property="article:published_time"]')
    # 셋 중 하나라도 없으면 페이지 구조가 예상과 다른 것이므로 이 기사는 건너뛴다.
    if soup.title is None or body_tag is None or date_tag is None:
        logger.warning("기사 파싱 실패, 스킵: url=%s", url)
        return None

    # <title>은 "기사 제목 - 전자신문" 형태라 뒤쪽 매체명만 떼어낸다.
    # 제목 자체에 " - "가 있을 수 있어 rsplit으로 마지막 구분자만 자른다.
    title = soup.title.get_text().rsplit(" - ", 1)[0].strip()

    # naver.py의 반환 형태와 키를 맞춰 cli.py가 두 소스를 동일하게 처리하게 한다.
    return {
        "title": title,
        "link": url,
        # get_text()는 태그를 걷어내고 사람이 읽는 텍스트만 남긴다.
        # separator="\n"으로 문단 구분을 줄바꿈으로 살린다.
        "description": body_tag.get_text(separator="\n", strip=True),
        # <meta>는 눈에 보이는 텍스트가 없으므로 content 속성값을 꺼내야 한다.
        "pubDate": date_tag.get("content"),
    }


# naver.py의 _request_with_retry와 동일한 재시도 정책을 크롤링에도 적용한다.
def _request_with_retry(url: str, timeout_sec: float, max_retries: int) -> str | None:
    """HTTP 요청 실패 시 재시도하고, 최종 실패하면 None을 반환한다."""
    for attempt in range(1, max_retries + 2):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout_sec)
            resp.raise_for_status()
            # 응답 헤더에 charset이 없으면 requests가 latin-1로 추측해 한글이 깨진다.
            # 본문 바이트를 보고 실제 인코딩(UTF-8)을 추론하게 한다.
            resp.encoding = resp.apparent_encoding
            return resp.text
        except requests.exceptions.RequestException as e:
            logger.warning(
                "크롤링 요청 실패 (%d/%d): url=%s, error=%s", attempt, max_retries + 1, url, e
            )
    logger.error("크롤링 요청 최종 실패: url=%s", url)
    return None
