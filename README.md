# [Project B] AI 뉴스 트렌드 및 종합 분석 리포트

뉴스 수집 → 정제 → AI 요약 → AI 인사이트 분석 → 시각화/리포트 → 내보내기를
수행하는 CLI 기반 Python 애플리케이션.

## 팀 구성 (4인)

| 담당 | 역할 | 모듈 | 서브커맨드 |
|---|---|---|---|
| A | 뉴스 수집·정제 | `src/collector/` | `fetch`, `clean` |
| B | AI 요약·분석 | `src/ai/` | `summarize`, `analyze` |
| C | 시각화·리포트 | `src/report/` | `report`, `export` |
| D | 데이터 정책·문서 | `docs/`, `config.json` | 보너스 `list`, `show` |

각 모듈은 서로를 import하지 않고 `src/common/db.py`(SQLite)를 통해서만 데이터를 주고받는다.
raw/clean은 `news_raw`(수집 원본, 불변) / `news_clean`(정제 결과, `raw_id`로 원본 추적)
테이블로 분리되어 있고, 파이프라인 단계는 `news_clean.status`(`clean` → `summarized`)로 판별한다.

## 시작하기

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env         # AI_API_KEY 채우기
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

# 보너스: 뉴스 목록/상세 조회
python main.py list                                  # 최신순 10건
python main.py list --category IT --page 1           # 카테고리 필터
python main.py list --keyword 반도체                  # 제목/본문/요약 검색
python main.py list --date-from 2026-08-05 --date-to 2026-08-06
python main.py list --status summarized --limit 20   # 요약된 뉴스만
python main.py show --id 1                           # 상세 조회 (show 1 도 가능)
python main.py show --id 1 --full                    # 본문 전체 출력
```

## 정기 실행 스케줄링

cron은 터미널과 환경이 달라서, 다음 세 가지를 지키지 않으면 실패한다.

1. `cd`로 프로젝트 루트 이동 — `config.json`/`.env`를 루트 기준으로 읽는다.
2. `.venv/bin/python`을 직접 지정 — cron의 PATH에는 가상환경이 없다 (`activate` 불필요).
3. 경로는 절대 경로로 — cron은 홈 디렉토리에서 실행된다.

`crontab -e`로 아래를 추가한다 (경로는 본인에 맞게 변경).

```cron
# 매일 08:00 수집 → 정제 → 요약 (&&로 묶어 앞 단계 성공 시에만 다음 실행)
0 8 * * * cd /home/ubuntu/codyssey-team-project-2B && .venv/bin/python main.py fetch --source naver --limit 20 && .venv/bin/python main.py clean --all && .venv/bin/python main.py summarize --unsummarized --limit 20 >> logs/cron.log 2>&1

# 매주 월요일 09:00 분석 → 리포트
0 9 * * 1 cd /home/ubuntu/codyssey-team-project-2B && .venv/bin/python main.py analyze && .venv/bin/python main.py report --format md >> logs/cron.log 2>&1
```

시간 형식은 `분 시 일 월 요일`. 확인은 `crontab -l`, 로그는 `tail -f logs/cron.log`.

Windows는 작업 스케줄러에서 프로그램에 `.venv\Scripts\python.exe`, 인수에 `main.py fetch ...`,
**시작 위치에 프로젝트 폴더 경로**를 넣는다 (시작 위치를 비우면 config.json을 못 찾는다).

크롤링 대상 사이트에 부담을 주지 않도록 수집은 하루 1~2회로 제한한다.


## 현재 상태

필수 서브커맨드 6개(`fetch`, `clean`, `summarize`, `analyze`, `report`, `export`)와
보너스 2개(`list`, `show`)가 모두 동작한다. 각 모듈은 `register_subparser(subparsers)`
함수를 노출하고 `main.py`가 이를 import해 등록한다.

- [x] A: `src/collector/` — fetch(네이버 API + bs4 크롤링), clean
- [x] B: `src/ai/` — AI API 연동, summarize, analyze(분석 실행 + `--list`/`--show` 조회)
- [x] C: `src/report/` — matplotlib 시각화, report, export(CSV/JSONL/Excel)
- [x] D: `src/query/` — 보너스 list/show(필터 + 페이지네이션)

## 요구사항 원문

[docs/요구사항.md](docs/요구사항.md)
