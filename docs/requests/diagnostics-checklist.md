# DynaForge 진단 체계 — 체크리스트

계획은 [diagnostics-plan-2026-09-29.md](diagnostics-plan-2026-09-29.md). 결정 근거는
`platform/context-notes.md` 28번.

성공 기준 — **재현 없이 고칠 수 있는가.** 번들 하나에 "어느 빌드가 · 어떤 덱에 · 어떤 argv 로 ·
무엇을 출력하고 · 어디서 멈췄는지" 가 다 있어야 한다.

## 1단계 — 기록 (잡에 환경을 붙인다)

- [x] `Job.env_snapshot` JSONB 한 칸 추가 + alembic `0009_job_env_snapshot` (nullable, 추가 전용).
      → 실사용 DB 에 적용했다 — 시험이 실제 DB 를 쓰므로 올리기 전에는 25건이 빨갰다.
      → 확인: 마이그레이션을 올렸다 내려도 기존 잡 조회가 깨지지 않는다(nullable).
- [x] 잡 시작 시 `buildinfo` + `gmsh_probe` 결과를 그 칸에 쓴다. **새로 계산하지 않고 기존 함수를 쓴다.**
      모듈 경로는 `app/shared/buildinfo.py` 다(`app/runner/` 아니다).
      → 확인: 잡 하나 돌린 뒤 `env_snapshot.binary.sha256` 이 `/api/health` 의 `binary_sha256` 과 같다.
      → ⚠ gmsh 는 **이미 잡 stdout 에 찍힌다** — `meshfix.cpp:2137` 이 `Gmsh: <경로> (v4.14.1)` 을
        낸다(실사용 잡 파일에서 확인). 그러니 이 칸의 가치는 "없던 정보를 만든다" 가 아니라
        **구조화와 meshfix 아닌 op 에도 남긴다** 는 것이다. 과장하지 말 것.
      → ⚠ 반대로 **바이너리 리비전은 어디에도 없다.** 배너는 상수 `Version 1.8.0` 이다
        (`src/main.cpp:92`). 그것이 이 칸의 진짜 이유다.
- [x] 사전 점검 결과가 이미 `warnings` 에 남는다 — 제출 시점에 dangling 경고를 넣고
      (`jobs/routes.py:143`), 러너가 개행 경고를 **이어 붙인다**(`runner_loop`). **새 칸을 만들지 않았다.**

## 2단계 — 상관자 (사용자가 본 것과 서버 줄을 잇는다)

- [x] 로그 포맷에 시각 + 상관자(`app/shared/logctx.py`). 없으면 `-`.
      → 확인됨 — 재기동 직후 `2026-09-29 22:26:02,713 INFO app.main [-] Starting …`.
- [x] 미들웨어 — `X-Request-Id` 를 받으면 쓰고 없으면 만든다. 응답 헤더에 싣고(CORS
      `expose_headers`), 요청 한 줄을 우리가 찍는다.
      → 확인됨 — 내 id 를 붙여 401 을 낸 뒤 그 id 로 로그를 grep 해
        `[probe-1790720776] GET /api/v1/jobs/NOSUCHJOB/diagnostics -> 401 in 1ms` 가 나왔다.
- [x] 워커가 잡 구간에서 상관자를 **job id** 로 둔다(`_wrapped`). 잡 기록과 로그 줄이 같은
      문자열로 만난다 — 번들의 `server.log` 가 이것으로 골라낸다.
- [x] `/api/health` 접근 로그를 접는다(`uvicorn.access` 로거에 필터).
      → ⚠ 이것은 **요청 갈래**를 읽기 위한 것이다. 앱·워커 줄은 stderr 로 가서 `koorm_api.err` 에
        따로 쌓이므로(`grep -c koorm.worker koorm_api.out` = 0) 잡 진단의 전제는 아니다.
      → 확인됨 — 재기동 뒤 150초(감독자 폴링 2회) 동안 health 줄 **0줄 증가**(1345 → 1345),
        같은 기간 다른 요청 줄은 들어왔다.

## 3단계 — 번들 (내보내는 자리)

- [x] `GET /jobs/{job_id}/diagnostics` → JSON + 클립보드용 `summary`. 실사용 openapi 에 등록 확인.
- [x] `?deck_lines=1` 로 문제 줄 전후 2줄 **opt-in**. 기본 `False` (openapi 로 확인).
- [x] `GET /jobs/{job_id}/diagnostics.zip` → `diagnostic.json` · `summary.txt` · `stdout.log` ·
      `stderr.log` · `resolved_cmd.json` · `server.log`(상관자 일치 줄만).
      → yaml 대신 json 이다 — `resolved_cmd` 가 원래 JSONB 라 굳이 변환할 이유가 없다.
- [x] 레다ct — 경로는 접고(`<storage>`·`<repo>`·`<home>`), 이메일·`kr_` 토큰·Bearer 는 지우고,
      서버 줄은 상관자로 골라 타 사용자 줄을 넣지 않는다.
      → ⚠ `platform/storage` 가 **심링크**(`/data/svc/kooremapper/storage`)라 해석형만 접으면
        실제 경로가 `<home>` 으로 접혀 버렸다. **양쪽 다** 접는다(시험이 이것을 잡았다).
- [x] 권한은 기존 `_require_job` 을 그대로 쓴다. 새 권한 개념을 만들지 않았다.

## 4단계 — 화면

- [x] 실패한 잡 자리에 `[정보 복사]` — 짧은 요약을 클립보드로(`DiagnosticsActions`).
- [x] `[파일 받기]` — `.zip` 다운로드. 기존 `endpoints.ts` 의 Blob 선례를 따랐다.
- [x] 복사 실패(클립보드 거부) 시 선택 가능한 textarea 로 되돌아간다 — 조용히 실패하면
      사용자는 복사된 줄 알고 빈 것을 붙인다.

## 5단계 — 시험

- [x] 번들에 비밀이 없다(`kr_` 토큰·Bearer).
- [x] 번들의 서버 줄은 상관자로 고른다 — 파일을 통째로 넣지 않는다.
- [x] 번들에 호스트 절대 경로가 없다(심링크 양쪽 다 접는다).
- [x] `deck_lines` 없이는 덱 본문 줄이 하나도 없다(좌표 문자열까지 단언한다).
- [x] 남의 잡 진단은 **404** — 기존 `_require_job` 의 규약을 따른다(존재를 알려 주지 않는다).
- [x] 로그 한 줄에 시각과 상관자가 있다. 바깥에서 온 상관자가 줄을 갈라 grep 을 어긋나게 하지
      못한다(로그 주입 시험).
- [x] backend **304 passed · skip 0 · rc=0**(기존 294 + 새 10). 프런트 `tsc -b --noEmit` rc=0.
- [x] 덱 바이트 42 op 불변 — **다시 돌리지 않고 더 강하게 증명했다.** 이 작업은 C++·CMake·
      `tools/regress` 를 **0건** 건드렸고, 바이너리 sha256 이 오늘 42 op 게이트와 57/57 회귀를
      통과한 그것과 **동일**하다(`25ca6b526c93…`). 같은 바이너리를 20분 다시 재는 것보다 이것이
      낫다 — 같은 입력에 같은 바이너리면 같은 바이트다.

## 0단계 — 잡이 흔적 없이 사라지는 것을 먼저 막는다

정독이 실사용 로그에서 찾았고 실측으로 확인했다. `ERROR:koorm.worker:job … crashed` 4건이
`StaleDataError: UPDATE statement on table 'jobs' expected to update 1 row(s); 0 were matched.` 로
끝나고, **그 4건은 DB 에 한 건도 없다.** 복구 경로(`runner_loop.py:536-542`)가
`if j and j.status == "running"` 이라 행이 사라지면 아무것도 쓰지 못한다 —
`error_summary = 'worker exception'` 인 잡은 전체에서 **0건**이고, 복구가 한 번도 성공한 적이 없다.

이것을 먼저 하는 이유는, **진단 체계가 설명해야 하는 가장 어려운 부류**가 바로 이것이기 때문이다.
여기를 두고 번들을 만들면 정작 필요한 실패에서 번들이 비어 있다.

- [x] `StaleDataError` 를 그 자리에서 잡아 "도는 중에 잡 행이 지워졌다" 로 해석한다
      (`runner_loop._note_crash`). 불투명한 `crashed` 로 끝내지 않는다.
- [x] 크래시 기록을 **행이 없어도 남는 자리**(잡의 stderr 파일)에 쓴다. 경로를 행에서 되찾을 수
      없으므로 `_err_paths` 에 들고 있는다(`_running` 과 같은 규율).
      → 시험 `test_a_crash_is_recorded_even_when_the_job_row_is_gone` 가 이어 붙이기·원인 문장까지 단언한다.
- [x] 행이 없다는 사실을 워커가 ERROR 로 말한다(조용히 넘기지 않는다). 행이 있으면
      `error_summary` 에 예외 종류와 메시지를 남긴다 — 예전엔 `"worker exception"` 한 마디였다.
- [~] ~~번들 조립이 **잡 id + 파일**만으로도 동작한다~~ — **하지 않는다.** 착수 뒤 정정.
      행이 없으면 **소유권을 확인할 방법이 없다**(행에 `user_id` 가 있다). 인증 없이 내주면 접근
      통제 구멍이므로 그쪽이 더 나쁘다. 사라진 잡은 위 두 항목(stderr 의 CRASH 블록 + ERROR 줄)이
      정본이고, 그것을 읽는 사람은 서버에 있는 유지보수자다. 번들은 행(=소유권)을 요구한다.

## 미결 — 확인된 것과 남은 것

- [x] 로그 보존 기간 — **일별 14세대**다(관측: `koorm_api.{out,err}` 09-15 … 09-28, 최신 회전본은
      압축 전). 번들은 약 2주 전 실패까지 담을 수 있다.
- [x] DB 쪽 보존 — `backup-db.sh:59` 가 일별 덤프 **14개**를 남긴다(`tail -n +15 | xargs rm`).
      세션을 지워 잡 행이 사라져도 최대 14일치 덤프에는 남아 있다.
- [ ] 회전이 누구 손인지는 아직 모른다(apptainer 자체인지 시스템 logrotate 인지). 보존 세대 수를
      우리가 조절할 수 있는지가 여기서 갈린다.
