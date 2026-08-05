# 프로젝트 구조

## 팀 분담 (4인)

| 담당 | 역할 | 모듈 | 서브커맨드 |
|---|---|---|---|
| A | Collector Engineer | `src/collector/` | `fetch`, `clean` |
| B | AI Engineer | `src/ai/` | `summarize`, `analyze` |
| C | Visualization Engineer | `src/report/` | `report`, `export` |
| D | Data & Compliance Lead | 소스/정책 조사, `config.json` | (보너스 `list`/`show` 겸임) |

A/B/C는 서로의 모듈을 import하지 않는다. 데이터는 오직 `src/common/db.py`를
통해 SQLite로 주고받는다. raw/clean은 테이블로 분리되어 있다 (`news_raw`: 수집
원본, 불변 / `news_clean`: 정제 결과, `raw_id`로 원본 추적). 파이프라인 단계는
`news_clean.status` 필드로 판별한다 (`clean` → `summarized`).

`src/collector/`, `src/ai/`, `src/report/`, `src/query/`는 `__init__.py`만 있는
빈 폴더다. 담당자가 폴더 안 파일명과 구조를 자유롭게 정해 구현하되, `main.py`가
서브커맨드를 등록할 수 있도록 `register_subparser(subparsers)` 함수를 노출하는
진입 파일을 하나 만들고 `main.py`에 import를 추가한다.

## 디렉토리 구조

```
codyssey-team-project-2B/
├── main.py                  # 진입점: argparse 서브커맨드 라우팅만 담당
├── config.json               # D가 채움 (API 키는 .env로 분리)
├── .env.example
├── requirements.txt
├── README.md
├── docs/
│   ├── REQUIREMENTS.md
│   └── ARCHITECTURE.md       # 본 문서
├── src/
│   ├── common/                # 공통 기반 (완성됨, 수정 시 팀 공유 후)
│   │   ├── config.py          # config.json + 환경변수 로더
│   │   ├── db.py               # SQLite 스키마 + CRUD 함수
│   │   └── logger.py          # 공통 로깅 설정
│   ├── collector/              # 담당 A — fetch/clean (빈 폴더, 자유 구성)
│   ├── ai/                     # 담당 B — summarize/analyze (빈 폴더, 자유 구성)
│   ├── report/                  # 담당 C — report/export (빈 폴더, 자유 구성)
│   └── query/                   # 보너스: list/show (빈 폴더, 자유 구성)
├── output/                    # 실행 산출물 (전부 gitignore, .gitkeep으로 폴더만 유지)
│   ├── data/
│   │   └── news.db              # SQLite (news_raw, news_clean, insights 테이블)
│   ├── logs/                   # 로그 파일
│   ├── charts/                 # PNG 출력
│   ├── exports/                # CSV/JSONL/Excel 출력
│   └── reports/                # TXT/MD 리포트 출력
└── tests/
```

## 개발 순서

1. D가 뉴스 소스 조사(API/RSS + 크롤링 대상, robots.txt 확인) 후 `config.json`을 확정한다.
2. A/B/C는 `src/common/db.py`의 함수만 보고 병렬로 각자 모듈을 구현한다.
3. 통합 후 `fetch → clean → summarize → analyze → report → export` 전체 파이프라인을 실행해 검증한다.
