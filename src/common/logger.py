"""공통 로깅 설정. INFO/WARNING/ERROR를 콘솔 + output/logs/app.log에 기록한다.

담당: D 신규/확정. 전원이 `from src.common.logger import get_logger` 로 사용.
"""

import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_LOG_FILE = BASE_DIR / "output" / "logs" / "app.log"

_configured = False


def setup_logging(level: str = "INFO", log_file: str | None = None) -> None:
    """앱 시작 시 한 번 호출한다 (main.py에서 호출)."""
    global _configured
    if _configured:
        return

    log_path = Path(log_file) if log_file else DEFAULT_LOG_FILE
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """모듈별 로거. 사용 예: logger = get_logger(__name__)"""
    return logging.getLogger(name)
