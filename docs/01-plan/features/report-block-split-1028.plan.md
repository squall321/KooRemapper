# 반입 블록 분리 — sphere 리포트 상세 질의가 원본을 다시 읽지 않게 (2026-10-28)

총괄 `drop-twin-1028.plan.md` P1 · 측정 `docs/04-report/drop-twin-p0-1028.report.md` §1

## 문제
1,000각도 sphere 리포트는 484 MB 다. 상세 질의마다 원본 HTML 을 다시 읽고 임베드 JSON 을 통째로 푼다. raw_decode(`288afb7`) 뒤에도 1회 6.7초 · 3.1 GB 이고, 질의 자체는 0.13초다.

## 무엇이 무거운가
각도마다 `results[i].parts[pid]` 의 시계열(`*_ts`)이다 — 각도당 약 0.47 MB, 전체의 95% 남짓. 상세 질의 가운데 시계열을 쓰는 것은 sphere `part_series` 하나다. `case_energy` 는 최상위 `energy_flows`, `hotspots` 는 `results[i].hotspot`, `scatter` 는 스칼라를 쓴다. 범용 `get_block` 은 경로에 따라 쓸 수 있다.

## 설계
- 반입 때(예전 리포트는 첫 상세 질의 때 한 번) 원본 옆에 곁파일 폴더 `.<원본 이름>.blocks/` 를 둔다.
  - `meta.json` — 꼴 판 · 원본 sha256(SessionFile 의 값) · case_key → 순번 · `list_blocks` 결과(전체 기준 크기).
  - `slim.json.gz` — 전체에서 `results[i].parts[pid]` 의 `*_ts` 만 뺀 것.
  - `cases/<순번>.json.gz` — 그 각도의 `*_ts`.
- 상세 질의는 slim 만 읽는다. `part_series` 는 그 각도 파일 하나를 합친다. `blocks` 는 meta 의 목록을 쓴다. `get_block` 은 `results.<순번>…` 이면 그 각도를 합치고, `results` 통째면 원본을 읽는다 — 시계열이 조용히 빠지지 않게.
- 원본 sha256 이 다르면 다시 만든다. 만들기는 한 번에 하나(전역 잠금 — 메모리 보호).
- 곁파일을 못 쓰거나 못 읽으면 반입은 그대로 성공하고 경고만 남긴다. 상세 질의는 원본 읽기로 떨어진다.
- 리포트를 지우면 곁파일도 지운다(세션 삭제는 폴더째 지워진다).
- sphere 만 한다. deep · impact 는 지금처럼 둔다(크기가 작다).

## 검증
- 시험 — 나눴다 합치면 원본과 같다 · slim 위 상세 함수 결과가 전체 위 결과와 같다(hotspots · contact_profile · scatter · case_energy · geometry · analytics) · 합친 각도의 part_series 가 같다 · meta 의 블록 목록 · 반입이 곁파일을 만든다 · sha 가 다르면 다시 만든다 · 리포트 삭제가 곁파일을 지운다.
- 측정 — 합성 1,000각도에서 곁파일 크기 · 만드는 시간 · 상세 질의 1회 시간과 메모리(6.7초 · 3.1 GB 대비).

## 체크리스트
- [x] `app/reports/blockstore.py` · 단위 시험 4
- [x] 반입 · 상세 질의 · 삭제 배선 · DB 시험(반입이 곁파일을 쓴다 · part_series 같다 · 블록 목록 · 지우면 다시 만든다 · results.<순번> · 삭제)
- [x] 합성 1,000각도 측정 — 아래 「결과」
- [x] 백엔드 전체 시험 677 통과 · dev 반영(`c7970dc`, 잡 0 확인 뒤 API 재기동) · 리포트 스모크 35/35 · 스모크 뒤 저장소에 남은 곁파일 0
- [x] 총괄 체크리스트 · 결정 노트 · 기억

## 결과 (10-28 실측, 합성 1,000각도 · 484 MB · `prlimit --as` 8 GiB)
| | 상세 질의 1회 | 최대 메모리 |
|---|---|---|
| 처음(파이썬 괄호 맞추기) | 22.4 s | 4.0 GB |
| raw_decode(`288afb7`) | 6.7 s | 3.1 GB |
| **곁파일(slim + 그 각도)** | **0.34 s** | **174 MB** |
- 곁파일 145 MB(원본의 30%) — slim 3.7 MB · 각도 파일 1,000개(gzip 3). 만드는 데 10.6초(반입에 더해진다, 그 전에 임베드 풀기 6.3초는 반입이 이미 한다).
- 상세 질의 0.34초의 내역 — slim 읽기 0.22 · 그 각도 읽기 0.004 · 질의 셋 0.11.
- 측정 스크립트는 스크래치(`bench_blocks.py`)였다 — 다시 잴 일이 생기면 `scripts/bench_sphere_scale.py` 에 모드를 더한다.
