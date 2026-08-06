# [Project B] AI 뉴스 트렌드 및 종합 분석 리포트

뉴스 수집 → 정제 → AI 요약 → AI 인사이트 분석 → 시각화/리포트 → 내보내기를
수행하는 CLI 기반 Python 애플리케이션.

## 팀 구성 (4인)

| 담당 | 역할 | 모듈 | 서브커맨드 |
|---|---|---|---|
| A | 뉴스 수집·정제 | `src/collector/` | `fetch`, `clean` |
| B | AI 요약·분석 | `src/ai/` | `summarize`, `analyze` |
| C | 시각화·리포트 | `src/report/` | `report`, `export` |
| D | 데이터 정책·문서 | `docs/`, `config.json` | (보너스 `list`/`show` 겸임) |

역할 분담, 디렉토리 구조, 모듈 간 의존성 규칙은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 참고.

## 시작하기

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env         # AI_API_KEY 채우기
# config.json은 이미 있음 — 소스 조사 후 TODO 항목 채우기
```

### 한글 폰트 (차트용)

`report` 명령의 차트에 한글을 표시하려면 시스템에 한글 폰트가 있어야 한다.
없으면 차트의 한글이 전부 `□□□`(두부)로 깨진다.

- **Windows / macOS**: 맑은 고딕 / AppleGothic이 기본 설치돼 있어 보통 그대로 동작한다.
- **Linux (Ubuntu)**: 직접 설치해야 한다.

```bash
sudo apt-get install -y fonts-nanum
rm -rf ~/.cache/matplotlib   # matplotlib이 예전 폰트 목록을 캐시하고 있어 지워줘야 인식된다
```

폰트를 찾지 못하면 `report` 실행 시 경고 로그가 뜨고, 차트는 한글이 깨진 채로 생성된다.

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

# AI 요약 (--all / --id / --unsummarized 중 하나 필수)
python main.py summarize --unsummarized --limit 10
python main.py summarize --id 3
python main.py summarize --all --limit 20 --force   # 이미 요약된 것도 다시 요약

# AI 인사이트 분석 (옵션 생략 시 전체 대상)
python main.py analyze --date-from 2026-08-01 --date-to 2026-08-06 --category IT

# 저장된 분석 결과 조회 (--list: 목록, --show: 상세)
python main.py analyze --list
python main.py analyze --list --category IT          # 카테고리 필터
python main.py analyze --list --keyword 반도체        # 트렌드/키워드 검색
python main.py analyze --list --limit 5 --page 2     # 페이지네이션
python main.py analyze --show 4                      # id로 상세 조회
# 주의: 조회 모드의 --date-from/--date-to는 '분석 실행 시각' 기준이다
#       (새 분석 실행 시에는 '뉴스 발행일' 기준이라 의미가 다르다).

# 차트(PNG) 생성 + 종합 리포트 (콘솔 출력 + output/reports/에 저장)
python main.py report --format md
python main.py report --format txt --top 5      # TOP 키워드 5개까지만
python main.py report --no-chart                # 차트 없이 리포트만
python main.py report --no-save                 # 콘솔에만 출력

# 데이터 내보내기 (output/exports/에 저장)
python main.py export --format csv --status summarized
python main.py export --format jsonl
python main.py export --format excel --category IT

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
- [x] B: `src/ai/` — AI API 연동, summarize, analyze(분석 실행 + `--list`/`--show` 조회) 구현
- [x] C: `src/report/` — matplotlib 시각화, report, export(CSV/JSONL/Excel) 구현
- [ ] D: 뉴스 소스/크롤링 정책 조사 후 `config.json` TODO 값 채우기, 여유 시 `src/query/`(list/show) 구현

## 요구사항 원문

[docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)
