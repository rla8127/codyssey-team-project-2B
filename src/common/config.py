"""공통 설정 로더.

config.json(비민감 설정)과 환경변수/.env(민감 정보: API 키)를 병합해서
하나의 dict로 반환한다. 모든 모듈(A/B/C/D)은 이 함수를 통해서만 설정을 읽는다.

담당: D (Data & Compliance Lead) 신규/확정. A/B/C는 read-only로 사용.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
ENV_PATH = BASE_DIR / ".env"

_cached_config = None


def load_config(force_reload: bool = False) -> dict:
    """config.json + 환경변수를 병합한 설정 dict를 반환한다."""
    global _cached_config
    if _cached_config is not None and not force_reload:
        return _cached_config

    # API KEY를 포함한 민감정보 .env에서 불러오기
    load_dotenv(ENV_PATH)

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"config.json이 없습니다: {CONFIG_PATH}. config.json.example을 복사해서 만드세요."
        )

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    config["ai"]["api_key"] = os.environ.get("AI_API_KEY", "")
    config["news_sources"]["api"]["client_id"] = os.environ.get("NAVER_CLIENT_ID", "")
    config["news_sources"]["api"]["client_secret"] = os.environ.get("NAVER_CLIENT_SECRET", "")

    _cached_config = config
    return config
