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

뉴스 수집을 매일 자동으로 돌리려면 OS 스케줄러에 등록한다.

### 핵심 주의사항

스케줄러는 터미널과 **환경이 달라서** 그냥 등록하면 대부분 실패한다. 세 가지를 지켜야 한다.

1. **절대 경로를 쓴다.** cron은 홈 디렉토리에서 실행되므로 `python main.py`는 파일을 못 찾는다.
2. **가상환경의 python을 직접 지정한다.** `source .venv/bin/activate` 없이 `.venv/bin/python`을 쓰면 된다.
3. **작업 디렉토리를 옮긴다.** `config.json`과 `.env`를 프로젝트 루트 기준으로 읽기 때문에 `cd`가 필요하다.

### Linux / macOS (cron)

```bash
crontab -e
```

아래 내용을 추가한다 (경로 본인에 맞게 변경).

```cron
# 매일 오전 8시에 뉴스 수집 → 정제 → 요약까지 실행
0 8 * * * cd /home/ubuntu/codyssey-team-project-2B && .venv/bin/python main.py fetch --source naver --limit 20 >> logs/cron.log 2>&1
5 8 * * * cd /home/ubuntu/codyssey-team-project-2B && .venv/bin/python main.py clean --all >> logs/cron.log 2>&1
10 8 * * * cd /home/ubuntu/codyssey-team-project-2B && .venv/bin/python main.py summarize --unsummarized --limit 20 >> logs/cron.log 2>&1

# 매주 월요일 오전 9시에 분석 + 리포트 생성
0 9 * * 1 cd /home/ubuntu/codyssey-team-project-2B && .venv/bin/python main.py analyze >> logs/cron.log 2>&1
10 9 * * 1 cd /home/ubuntu/codyssey-team-project-2B && .venv/bin/python main.py report --format md >> logs/cron.log 2>&1
```

수집과 요약 사이에 5분 간격을 둔 이유는, 앞 단계가 끝나기 전에 다음 단계가 시작되면
아직 정제되지 않은 데이터를 대상으로 돌게 되기 때문이다. 한 줄로 묶어 순차 실행해도 된다.

```cron
# && 로 묶으면 앞 명령이 성공했을 때만 다음이 실행된다
0 8 * * * cd /home/ubuntu/codyssey-team-project-2B && .venv/bin/python main.py fetch --source naver --limit 20 && .venv/bin/python main.py clean --all && .venv/bin/python main.py summarize --unsummarized --limit 20 >> logs/cron.log 2>&1
```

등록 확인과 삭제:

```bash
crontab -l          # 등록된 목록 확인
crontab -r          # 전체 삭제 (주의)
tail -f logs/cron.log   # 실행 로그 확인
```


## 현재 상태

필수 서브커맨드 6개(`fetch`, `clean`, `summarize`, `analyze`, `report`, `export`)와
보너스 2개(`list`, `show`)가 모두 동작한다. 각 모듈은 `register_subparser(subparsers)`
함수를 노출하고 `main.py`가 이를 import해 등록한다.

- [x] A: `src/collector/` — fetch(네이버 API + bs4 크롤링), clean 구현
- [x] B: `src/ai/` — AI API 연동, summarize, analyze(분석 실행 + `--list`/`--show` 조회) 구현
- [x] C: `src/report/` — matplotlib 시각화, report, export(CSV/JSONL/Excel) 구현
- [x] D: `src/query/` — 보너스 list/show(필터 + 페이지네이션) 구현
- [ ] D: 뉴스 소스/크롤링 정책 조사 후 `config.json` TODO 값 확정

## 요구사항 원문

[docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)
