"""전자신문(etnews.com) AI·SW 섹션 Selenium 크롤러.

목록 페이지(news/section.html?id1=04)에서 기사 링크를 모은 뒤, 각 상세 페이지를
방문해 제목/본문/발행일을 추출한다. naver.py의 fetch_naver_news와 동일하게
{"title", "link", "description", "pubDate"} 형태의 dict 리스트를 반환해서
cli.py에서 두 수집 방법을 동일하게 다룰 수 있게 한다.
"""

import time

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from src.common.logger import get_logger

logger = get_logger(__name__)


def _build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)


def fetch_crawled_news(config: dict, limit: int) -> list[dict]:
    """전자신문 AI·SW 섹션을 크롤링해 기사 리스트를 반환한다.

    limit은 1~100 범위로 제한된다 (naver.py와 동일한 제약).
    """
    crawl_config = config["news_sources"]["crawl"]
    base_url = crawl_config["base_url"]
    list_path = crawl_config["list_path"]
    interval_sec = crawl_config.get("request_interval_sec", 1.0)

    driver = _build_driver()
    items: list[dict] = []
    try:
        links = _collect_article_links(driver, base_url, list_path, limit)
        for link in links:
            time.sleep(interval_sec)
            item = _fetch_article(driver, link)
            if item is not None:
                items.append(item)
    finally:
        driver.quit()

    return items


def _collect_article_links(
    driver: webdriver.Chrome, base_url: str, list_path: str, limit: int
) -> list[str]:
    """목록 페이지를 페이지네이션(&page=N)하며 기사 상세 링크를 limit개 모은다."""
    links: list[str] = []
    page = 1
    while len(links) < limit:
        url = f"{base_url}{list_path}&page={page}"
        try:
            driver.get(url)
        except WebDriverException as e:
            logger.warning("목록 페이지 요청 실패: url=%s, error=%s", url, e)
            break

        anchors = driver.find_elements(By.CSS_SELECTOR, "div.text > strong > a")
        page_links = [a.get_attribute("href") for a in anchors if a.get_attribute("href")]
        if not page_links:
            break

        links.extend(page_links)
        page += 1
        if page > 20:  # 안전장치: 과도한 페이지 순회 방지
            break

    return links[:limit]


def _fetch_article(driver: webdriver.Chrome, url: str) -> dict | None:
    """기사 상세 페이지에서 title/description/pubDate를 추출한다."""
    try:
        driver.get(url)
    except WebDriverException as e:
        logger.warning("기사 페이지 요청 실패: url=%s, error=%s", url, e)
        return None

    try:
        title = driver.title.rsplit(" - ", 1)[0].strip()
        body = driver.find_element(By.ID, "articleBody").text.strip()
        pub_date = driver.find_element(
            By.CSS_SELECTOR, 'meta[property="article:published_time"]'
        ).get_attribute("content")
    except Exception as e:
        logger.warning("기사 파싱 실패, 스킵: url=%s, error=%s", url, e)
        return None

    return {
        "title": title,
        "link": url,
        "description": body,
        "pubDate": pub_date,
    }
