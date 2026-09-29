# DynaForge 진단 체계 — 체크리스트

계획은 [diagnostics-plan-2026-09-29.md](diagnostics-plan-2026-09-29.md). 결정 근거는
`platform/context-notes.md` 28번.

성공 기준 — **재현 없이 고칠 수 있는가.** 번들 하나에 "어느 빌드가 · 어떤 덱에 · 어떤 argv 로 ·
무엇을 출력하고 · 어디서 멈췄는지" 가 다 있어야 한다.

## 1단계 — 기록 (잡에 환경을 붙인다)

- [ ] `Job.env_snapshot` JSONB 한 칸 추가 + alembic 마이그레이션.
      → 확인: 마이그레이션을 올렸다 내려도 기존 잡 조회가 깨지지 않는다(nullable).
- [ ] 잡 시작 시 `buildinfo` + `gmsh_probe` 결과를 그 칸에 쓴다. **새로 계산하지 않고 기존 함수를 쓴다.**
      모듈 경로는 `app/shared/buildinfo.py` 다(`app/runner/` 아니다).
      → 확인: 잡 하나 돌린 뒤 `env_snapshot.binary.sha256` 이 `/api/health` 의 `binary_sha256` 과 같다.
      → ⚠ gmsh 는 **이미 잡 stdout 에 찍힌다** — `meshfix.cpp:2137` 이 `Gmsh: <경로> (v4.14.1)` 을
        낸다(실사용 잡 파일에서 확인). 그러니 이 칸의 가치는 "없던 정보를 만든다" 가 아니라
        **구조화와 meshfix 아닌 op 에도 남긴다** 는 것이다. 과장하지 말 것.
      → ⚠ 반대로 **바이너리 리비전은 어디에도 없다.** 배너는 상수 `Version 1.8.0` 이다
        (`src/main.cpp:92`). 그것이 이 칸의 진짜 이유다.
- [ ] 사전 점검 결과(dangling 등급·인클루드 정합·개행)가 이미 `warnings` 에 남는지 **먼저 확인**한다.
      남으면 새 칸을 만들지 않는다.
      → 확인: 미정의 참조가 있는 덱으로 잡을 돌려 `warnings` 를 읽는다.

## 2단계 — 상관자 (사용자가 본 것과 서버 줄을 잇는다)

- [ ] 로그 포맷에 시각 + 상관자. contextvar 를 읽는 `logging.Filter`, 없으면 `-`.
      → 확인: 기동 직후 `koorm_api.err` 첫 줄에 시각이 있다.
- [ ] 미들웨어 — `X-Request-Id` 를 받으면 쓰고 없으면 만든다. 응답 헤더 + 에러 본문에 싣는다.
      → 확인: 일부러 422 를 낸 응답의 헤더 id 로 로그를 grep 해 줄이 나온다.
- [ ] 워커가 잡 구간에서 상관자를 **job id** 로 둔다.
      → 확인: 잡 id 로 grep 하면 그 잡의 워커 줄만 나온다.
- [ ] `/api/health` 접근 로그를 접는다 — `koorm_api.out` 의 health 줄이 1,461개다.
      → ⚠ 이것은 **요청 갈래**를 읽기 위한 것이다. 앱·워커 줄은 stderr 로 가서 `koorm_api.err` 에
        따로 쌓이므로(`grep -c koorm.worker koorm_api.out` = 0) 잡 진단의 전제는 아니다.
      → 확인: 5분 기다린 뒤 `koorm_api.out` 에 health 줄이 없고 다른 요청 줄은 있다.

## 3단계 — 번들 (내보내는 자리)

- [ ] `GET /jobs/{job_id}/diagnostics` → JSON. 잡 기록 + `env_snapshot` + 로그 꼬리 + 요약.
- [ ] `?deck_lines=1` 로 문제 줄 전후 몇 줄 **opt-in**. 기본은 담지 않는다.
- [ ] `GET /jobs/{job_id}/diagnostics.zip` → `diagnostic.json` · `stdout.log` · `stderr.log` ·
      `resolved_cmd.yaml` · `server.log`(상관자 일치 줄만).
- [ ] 레다ct — 절대 경로를 `<storage>/…` 로 접고, 이메일·토큰을 지우고, 타 사용자 줄을 넣지 않는다.
- [ ] 권한은 기존 잡 소유권 검사를 그대로 쓴다. 새 권한 개념을 만들지 않는다.

## 4단계 — 화면

- [ ] 실패한 잡 자리에 `[진단 정보 복사]` — 짧은 요약을 클립보드로. 기존 `TokensPage.tsx` 선례를 따른다.
- [ ] `[진단 파일 받기]` — `.zip` 다운로드. 기존 `endpoints.ts` 의 Blob 선례를 따른다.
- [ ] 복사 실패(클립보드 거부) 시 텍스트를 선택 가능한 형태로 보여 준다.
      → 확인: `navigator.clipboard` 를 막고도 사용자가 내용을 가져갈 수 있다.

## 5단계 — 시험

- [ ] 번들에 비밀이 없다(설정 env 값·토큰).
- [ ] 번들에 타 사용자 로그 줄이 없다.
- [ ] 번들에 호스트 절대 경로가 없다.
- [ ] `deck_lines` 없이는 덱 본문 줄이 하나도 없다.
- [ ] 남의 잡 진단은 403.
- [ ] 로그 한 줄에 시각과 상관자가 있다.
- [ ] 회귀 전체 초록 + **덱 바이트 42 op 불변**(이 일은 덱 편집 경로를 건드리지 않는다).

## 0단계 — 잡이 흔적 없이 사라지는 것을 먼저 막는다

정독이 실사용 로그에서 찾았고 실측으로 확인했다. `ERROR:koorm.worker:job … crashed` 4건이
`StaleDataError: UPDATE statement on table 'jobs' expected to update 1 row(s); 0 were matched.` 로
끝나고, **그 4건은 DB 에 한 건도 없다.** 복구 경로(`runner_loop.py:536-542`)가
`if j and j.status == "running"` 이라 행이 사라지면 아무것도 쓰지 못한다 —
`error_summary = 'worker exception'` 인 잡은 전체에서 **0건**이고, 복구가 한 번도 성공한 적이 없다.

이것을 먼저 하는 이유는, **진단 체계가 설명해야 하는 가장 어려운 부류**가 바로 이것이기 때문이다.
여기를 두고 번들을 만들면 정작 필요한 실패에서 번들이 비어 있다.

- [ ] `StaleDataError` 를 그 자리에서 잡아 "도는 중에 잡 행이 지워졌다" 로 해석한다.
      불투명한 `crashed` 로 끝내지 않는다.
      → 확인: 잡이 도는 중에 세션을 지우고, 잡의 stderr 파일 끝에 그 사실이 적히는지 본다.
- [ ] 크래시 기록을 **행이 없어도 남는 자리**(잡의 stderr 파일)에 쓴다. 파일은 세션 삭제와 별개로 남는다.
- [ ] 번들 조립이 **잡 id + 파일**만으로도 동작한다. 행이 없을 때 404 로 끝내지 않는다.
      → 확인: 행을 지운 뒤에도 번들이 나오고, 그 안에 "행이 없다" 가 사실로 적혀 있다.

## 미결 — 확인된 것과 남은 것

- [x] 로그 보존 기간 — **일별 14세대**다(관측: `koorm_api.{out,err}` 09-15 … 09-28, 최신 회전본은
      압축 전). 번들은 약 2주 전 실패까지 담을 수 있다.
- [x] DB 쪽 보존 — `backup-db.sh:59` 가 일별 덤프 **14개**를 남긴다(`tail -n +15 | xargs rm`).
      세션을 지워 잡 행이 사라져도 최대 14일치 덤프에는 남아 있다.
- [ ] 회전이 누구 손인지는 아직 모른다(apptainer 자체인지 시스템 logrotate 인지). 보존 세대 수를
      우리가 조절할 수 있는지가 여기서 갈린다.
