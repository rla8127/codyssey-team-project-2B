"""matplotlib 시각화.

요구사항 6번: 카테고리별 뉴스 수, 일자별 수집 추이를 PNG로 저장한다.
한글 폰트를 잡지 않으면 축/제목의 한글이 전부 □□□(두부)로 깨지므로
차트를 그리기 전에 반드시 setup_korean_font()를 먼저 호출한다.
"""

import matplotlib

# Agg는 화면 없는 환경(서버/CI)에서도 PNG를 저장할 수 있는 백엔드다.
# pyplot을 import하기 '전에' 지정해야 효과가 있다.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from pathlib import Path  # noqa: E402

from src.common.logger import get_logger  # noqa: E402

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CHART_DIR = BASE_DIR / "output" / "charts"

# OS마다 들어있는 한글 폰트가 다르므로 후보를 순서대로 찾아 처음 발견된 것을 쓴다.
# (Windows: 맑은 고딕 / macOS: AppleGothic / Linux: 나눔고딕·Noto)
KOREAN_FONT_CANDIDATES = [
    "Malgun Gothic",
    "AppleGothic",
    "NanumGothic",
    "NanumBarunGothic",
    "Noto Sans CJK KR",
    "Noto Sans KR",
]


def setup_korean_font() -> str | None:
    """설치된 한글 폰트를 찾아 matplotlib 기본 폰트로 지정한다.

    찾은 폰트 이름을 반환하고, 하나도 없으면 경고 로그 후 None을 반환한다
    (차트는 그려지지만 한글이 깨진다).
    """
    found = _find_font(KOREAN_FONT_CANDIDATES)

    # 폰트를 방금 설치한 경우 matplotlib이 예전 목록을 캐시하고 있어 새 폰트를
    # 못 찾는다. 이때 캐시를 무시하고 한 번 다시 스캔하면 인식된다.
    if found is None:
        font_manager._load_fontmanager(try_read_cache=False)
        found = _find_font(KOREAN_FONT_CANDIDATES)

    if found is None:
        logger.warning(
            "한글 폰트를 찾지 못했습니다. 차트의 한글이 깨집니다(□□□). "
            "설치: Ubuntu `sudo apt-get install fonts-nanum` / "
            "Windows·macOS는 기본 폰트(맑은 고딕/AppleGothic)가 있어 보통 자동 인식된다."
        )
        return None

    plt.rcParams["font.family"] = found
    # 한글 폰트를 쓰면 음수 축 라벨의 마이너스 기호가 깨지는 알려진 이슈가 있어 함께 끈다.
    plt.rcParams["axes.unicode_minus"] = False
    logger.info("한글 폰트 적용: %s", found)
    return found


def _find_font(candidates: list[str]) -> str | None:
    """설치된 폰트 목록에서 후보를 순서대로 찾아 처음 일치한 이름을 반환한다."""
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in installed:
            return name
    return None


def plot_category_counts(data: dict[str, int], filename: str = "category_counts.png") -> Path | None:
    """카테고리별 뉴스 수 막대그래프를 PNG로 저장하고 경로를 반환한다."""
    if not data:
        logger.warning("카테고리 데이터가 없어 차트를 건너뜁니다.")
        return None

    categories = list(data.keys())
    counts = list(data.values())

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(categories, counts, color="#4C72B0")

    # 막대 위에 실제 건수를 적어 값을 바로 읽을 수 있게 한다.
    for bar, count in zip(bars, counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            str(count),
            ha="center",
            va="bottom",
        )

    ax.set_title("카테고리별 뉴스 수")
    ax.set_xlabel("카테고리")
    ax.set_ylabel("뉴스 수(건)")
    # y축은 정수 건수이므로 눈금도 정수로 맞춘다.
    ax.set_yticks(range(0, max(counts) + 2))
    ax.grid(axis="y", alpha=0.3)

    return _save(fig, filename)


def plot_daily_counts(data: dict[str, int], filename: str = "daily_counts.png") -> Path | None:
    """일자별 수집 추이 선그래프를 PNG로 저장하고 경로를 반환한다."""
    if not data:
        logger.warning("일자별 데이터가 없어 차트를 건너뜁니다.")
        return None

    days = list(data.keys())
    counts = list(data.values())

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(days, counts, marker="o", color="#DD8452")

    for day, count in zip(days, counts):
        ax.annotate(str(count), (day, count), textcoords="offset points", xytext=(0, 8), ha="center")

    ax.set_title("일자별 뉴스 수집 추이")
    ax.set_xlabel("날짜")
    ax.set_ylabel("수집 건수(건)")
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3)
    # 날짜가 많아지면 라벨이 겹치므로 기울여 표시한다.
    fig.autofmt_xdate(rotation=45)

    return _save(fig, filename)


def plot_sentiment(data: dict[str, int], filename: str = "sentiment.png") -> Path | None:
    """감성 분포 파이차트 (보너스 과제). 요약된 뉴스가 없으면 건너뛴다."""
    if not data:
        logger.warning("감성 데이터가 없어 차트를 건너뜁니다.")
        return None

    # 감성별로 의미가 통하는 색을 고정한다 (긍정=녹색, 부정=빨강, 중립=회색).
    color_map = {"긍정": "#55A868", "부정": "#C44E52", "중립": "#8C8C8C"}
    labels = list(data.keys())
    colors = [color_map.get(label, "#4C72B0") for label in labels]

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(
        list(data.values()),
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        startangle=90,
    )
    ax.set_title("뉴스 감성 분포")
    # 파이를 정원으로 그린다.
    ax.axis("equal")

    return _save(fig, filename)


def _save(fig, filename: str) -> Path:
    """공통 저장 처리: 폴더 생성 → 여백 정리 → PNG 저장 → figure 해제."""
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    path = CHART_DIR / filename

    fig.tight_layout()
    fig.savefig(path, dpi=120)
    # 저장 후 닫지 않으면 figure가 메모리에 계속 쌓인다.
    plt.close(fig)

    logger.info("차트 저장: %s", path)
    return path
