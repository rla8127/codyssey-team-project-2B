# [Project B] AI 뉴스 트렌드 및 종합 분석 리포트

뉴스 수집 → 정제 → AI 요약 → AI 인사이트 분석 → 시각화/리포트 → 내보내기를
수행하는 CLI 기반 Python 애플리케이션.

## 팀 구성 (4인)

| 담당 | 역할 | 모듈 | 서브커맨드 |
|---|---|---|---|
| A | Collector Engineer | `src/collector/` | `fetch`, `clean` |
| B | AI Engineer | `src/ai/` | `summarize`, `analyze` |
| C | Visualization Engineer | `src/report/` | `report`, `export` |
| D | Data & Compliance Lead | `docs/`, `config.json` | (보너스 `list`/`show` 겸임) |

역할 분담, 디렉토리 구조, 모듈 간 의존성 규칙은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 참고.

## 시작하기

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env         # AI_API_KEY 채우기
# config.json은 이미 있음 — 소스 조사 후 TODO 항목 채우기
```

## 실행 예시

```bash
# 방법 1: 네이버 뉴스 API
python main.py fetch --source naver --limit 20
python main.py fetch --source naver --query IT --category IT --limit 3
python main.py fetch --source naver --query 반도체 --category tech --limit 3

# 방법 2: 전자신문(etnews.com) AI·SW 섹션 크롤링
# --query는 사용되지 않는다 (섹션 페이지 고정이라 검색 개념이 없음).
python main.py fetch --source crawl --limit 5
python main.py fetch --source crawl --category AI --limit 5

python main.py clean --all
# 아직 미 개발
# python main.py summarize --unsummarized --limit 10
# python main.py analyze --date-from 2026-01-01 --date-to 2026-01-10 --category IT
# python main.py report --format md
# python main.py export --format csv --status summarized

# 보너스
python main.py list --category IT --page 1
python main.py show --id 1
```

## 현재 상태

`src/common/`(DB, config, logger)만 구현되어 있다. `src/collector/`, `src/ai/`,
`src/report/`, `src/query/`는 빈 폴더 상태이며, 각 담당자가 폴더 안에서
파일명과 내부 구조를 자유롭게 정해 구현한다. 단, `main.py`가 서브커맨드를
등록할 수 있도록 각 모듈은 `register_subparser(subparsers)` 함수를 노출하는
진입 파일을 만들고 `main.py`에 import를 추가해야 한다 (자세한 내용은 main.py 상단 주석 참고).

- [ ] A: `src/collector/` — fetch(API/RSS + 크롤링), clean 구현
- [ ] B: `src/ai/` — AI API 연동, summarize, analyze 구현
- [ ] C: `src/report/` — matplotlib 시각화, report, export(CSV/JSONL/Excel) 구현
- [ ] D: 뉴스 소스/크롤링 정책 조사 후 `config.json` TODO 값 채우기, 여유 시 `src/query/`(list/show) 구현

## 요구사항 원문

[docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)
