# 후처리 예약 연산(7-1) — KooSlurm 귀환 매니페스트를 기다려 리포트를 예약자 명의로 반입 (2026-10-28)

근거 — `platform/docs/REQUEST-postprocess-operation.md` §7(W-93: 클러스터에 후처리를 걸고 리포트 HTML 만 받는다 · 예약자 명의 반입 · 잡 하나에 리포트 하나) · KooSlurm `docs/REQUEST-result-return.md` §6(A·B·C·D, `c41d927e`) · 총괄 `drop-twin-1028.plan.md` P1.
사용자 결정(10-28 밤) — **DynaForge 가 예약한 사용자의 kst_ PAT 를 맡는다**(암호화해 두었다가 끝나면 지운다) · KooSlurm 운영 반영은 dev 노드 실제 잡 검증 뒤.

## 무엇
`run_operation(operation="postprocess", args={…})` — 포털이 제출 직후 게이트웨이 위임으로 부른다. 즉시 job_id 를 돌려주고, 잡은 외부 잡(`external_kind="kooslurm_return"`)으로 KooSlurm 의 `output/return_manifest.json` 을 기다린다. 끝나면 있는 리포트를 내려받아 sha256 을 맞추고 **잡 소유자(예약자) 명의**로 반입한다. 결과는 잡 상태(성공 · report_id / 실패 · 까닭)로 낸다.

## 인자 (catalog `postprocess`, invocation external)
- `job_key` — `stcx:<slurm_job_id>`(필수). 잡 하나에 리포트 하나 — 같은 키가 이미 반입됐으면 새로 받지 않고 그 리포트를 알린다.
- `kst_token` — 예약한 사용자 본인의 KooSlurm PAT(필수, **쓰기 전용**). 잡을 만들 때 인자에서 떼어 암호화해 `external_ref` 에만 두고, 잡 인자 · 응답 · 로그 · 진단 번들 어디에도 평문으로 남기지 않는다. 끝나면(성공 · 실패 · 취소 · 기한) 지운다.
- `sim_type` — `fullangle_drop | partial_impact`(필수). 기대하는 리포트 종류(sphere · impact)를 정한다.
- 선택 — `job_name` · `label` · 과제 메타(`project` · `dev_rev` · `variation` · `doe`) · 해석 조건(`height` · `floor` · `preset` · `position_doe`).

## 흐름
1. 잡 생성(라우트 · MCP 공통) — 인자 검증 → `kst_token` 을 떼어 암호화 → `external_ref.token_enc`. 소속도 이때 검증해 얼린다(반입 때는 요청이 없다).
2. 워커 시작 — KooSlurm 주소가 없으면 「구성 안 됨」 으로 실패(값을 지어내지 않는다). 같은 `job_key` 의 리포트가 이미 있으면 그 리포트로 끝낸다(7-2). 아니면 외부 잡(`kooslurm_return`)으로 걸어 두고 다음 스캔(≤15초)에 첫 확인을 한다.
3. 폴링(외부 잡 루프, stcx 폴링과 실패 영역을 가른다) — 401 · 403 은 토큰 · 소유 문제로 바로 실패, 시간 초과 · 5xx 는 다시 본다, 200 은 판정. 404 는 아직인데 ⚠ **없는 잡도 404** 라 `/info` 로 상태를 따로 본다.
   - 잡이 끝난 상태(COMPLETED · FAILED · TIMEOUT …)인데 매니페스트가 없으면 — `.prev.json` 이 있으면 C 가 도는 중이라 기다린다. 없으면 처음 본 뒤 **2분**(NFS 지연, KooSlurm 「1분 이상」) 지나 실패로 닫는다(드라이버가 EXIT trap 전에 죽었거나 매니페스트 전 판의 드라이버 — C 로 다시 걸 수 있다고 적는다).
   - `/info` 404 는 sacct 5초 상한에도 나므로 **세 번 연달아**일 때만 「클러스터가 이 잡을 모른다」.
4. 판정 — schema · version(v1) · sim_type 이 다르면 실패. `stage=early_exit` 면 실패. 기대 종류의 항목이 없거나 `present=false` 면 실패(`reason` · `log_tail` 을 그대로). ⚠ `ok` 보다 **`present` 를 먼저** 본다 — 후처리가 꺼진 잡은 `ok: true` 인데 리포트가 없다. 기대 종류가 있는데 `ok=false` 면(다른 종류가 없음) 반입하고 경고로 남긴다. 경로가 절대 · `..` 면(결과 폴더 밖) 실패. 있으면 `reports[].path` 를 `files/download?path=` 로 받아 크기 · sha256 을 맞추고 반입.
5. 반입 — 잡 세션 · 잡 소유자 명의 · 과제 메타 · 예약 때 얼린 소속으로 `ingest_report`. 리포트에 `external_job_key`(유일, 7-2) · `reservation`(잡 이름 · sim_type · 해석 조건 · 매니페스트 요지, 7-5)을 싣고, 리포트에 낙하 높이가 없을 때만 예약 `height` 로 채운다. 잡은 성공, `resolved_cmd.report_ids`(JobRead 로 보인다) · `output_file_ids`.
6. 기한 — 예약 뒤 N일(설정, 기본 7일)이 지나도 매니페스트가 없으면 실패. 토큰은 끝나는 모든 길에서 지운다.
7. 취소 — 이 종류는 클러스터에 손대지 않으므로 사용자가 취소할 수 있다(기다림만 멈춘다, queued · running 모두).

## 지키는 것
- 지어내지 않는다 — 매니페스트가 말하는 대로만 성공 · 실패한다. 까닭은 원문 그대로.
- 토큰 — 저장은 암호문만(키는 `KOORM_TOKEN_KEY`, 없으면 `jwt_secret` 에서 HKDF 로 끌어낸다). 진단 번들의 가리기에 `kst_` 를 더하고 `token_enc` 는 아예 뺀다. 비밀 칸(`secret`)의 인자 검증 오류는 값을 싣지 않는다. 콘솔은 가린 칸으로 그린다.
- 호출 상한 — 연결 · 전체 시간 상한(설정).
- 큰 리포트 — 내려받기는 파일로 흘려 쓰고, 반입은 기존 경로(sphere 는 곁파일)를 탄다.

## 설정
주소는 **`KOORM_STCX_BACKEND_URL` 을 같이 쓴다**(덱 업로드와 잡 REST 가 같은 backend_5010 — 비면 「구성 안 됨」). `KOORM_TOKEN_KEY`(선택) · `KOORM_POSTPROCESS_WAIT_DAYS`(기본 7) · `KOORM_KOOSLURM_TIMEOUT_SEC`(기본 30).

## 검증
- 시험(가짜 KooSlurm — httpx MockTransport) — 404 → 200 ok → 반입(예약자 명의 · 메타) · ok=false 까닭 · 401 · sha 불일치 · early_exit · 기한 · 같은 job_key · 토큰이 인자 · DB 평문에 없다 · 끝나면 토큰이 지워진다 · 취소.
- 플랫폼 — allops_smoke 에 넣는다. 성공이 아니라 **까닭이 분명한 실패**(「구성 안 됨」·「이 잡을 모른다」·「토큰을 거절했다」)와 잡 인자에 토큰이 없는지를 값으로 본다. 잡 키는 예제(123456) 대신 **`stcx:0`** — 예제 번호는 운영에 실제로 있을 수 있고 대시보드가 SSO 꺼짐이면 남의 잡도 열린다. 실제 귀환은 운영 반영 뒤 첫 실제 잡으로 잰다.

## 체크리스트
- [x] 카탈로그 `postprocess` · 설정 · 토큰 상자 · KooSlurm 클라이언트
- [x] 잡 생성(토큰 떼기) · 워커 시작 · 폴링 분기 · 반입 · 취소 · 진단 가리기
- [x] 리포트 `external_job_key`(유일) · `reservation` — 마이그레이션 `0015_report_reservation`(dev DB 적용)
- [x] 시험 26(가짜 KooSlurm) · 백엔드 전체 703 · 줄바꿈 회귀 64 · 카탈로그 일치 — 라우트 토큰 떼기 · 번들 암호문 빼기는 일부러 깨 시험이 잡는 것까지 확인
- [ ] dev 반영 · allops_smoke · reports_smoke
- [ ] 요청서 §10 회신 · 포털에 호출 꼴 알림 · 총괄 체크리스트 · 기억

## 결정 기록 (10-29)
- **주소 설정을 새로 두지 않았다.** 처음엔 `KOORM_KOOSLURM_URL` 을 두려 했는데, backend_5010 `app.py` 가 업로드(`/api/v2/files/upload/*`)와 잡 REST(`/api/jobs`)를 함께 싣는다(KooSlurm 확인 — nginx `/api/` 도 같은 곳). 같은 서버를 가리키는 값이 둘이면 어긋난다(두 번째 소비자).
- **404 하나로 실패를 정하지 않는다.** `_resolve_job_file` 은 결과 폴더를 못 찾아도 404 다. KooSlurm 이 「드라이버가 SIGKILL · 시간 초과로 죽으면 EXIT trap 이 못 돌아 매니페스트가 영영 안 생긴다 — `/info` 를 보라」고 했다(10-28). `/info` 는 sacct 5초 상한이라 404 가 흔들릴 수 있어 세 번을 본다. 「두 번 연달아」 는 처음 두 확인이 30초 간격이라 NFS 지연(1분 이상)을 못 넘는다 — 시각(2분)으로 바꿨다. `.prev` 가정(C 가 끝나도 지우지 않는다)은 KooSlurm 이 확인했다. C 가 시작도 못 하고 죽으면 `.prev` 만 남아 기한까지 기다린다(우리가 C 를 걸지 않으니 그 잡 id 를 모른다).
- **인클루드 검사를 이 연산만 건너뛴다.** 파일 인자가 없으면 `or inc` 가 세션의 모든 덱을 봐서, 상관없는 덱 하나 때문에 예약이 막힌다. MCP 에는 넘기는 길도 없다. 덱을 받지 않는 다른 일곱 연산(generate 등)은 손대지 않았다.
- **결과는 `resolved_cmd.report_ids` 로 보인다.** JobRead 에 `external_ref` 가 없다(토큰 원장이 있으니 내보내지 않는다). 외부 잡은 이미 `resolved_cmd` 에 걸어 둔 것을 적는다.
- **반입이 워커 스캔 안에서 돈다.** 1,000각도(484 MB) 리포트는 받기 + 반입에 수십 초 — 그동안 로컬 잡 집기가 늦는다. 흔한 리포트(10 MB 안팎)는 1–2초다. 문제가 되면 반입을 따로 띄운다.
- **소속은 예약 시점 값이다.** 반입 때는 요청이 없어 다른 길이 없다 — §9 「확인 부탁 2」(예약 시점 vs 반입 시점)의 답이 여기서 정해진다.
- 남은 것(이 일 밖) — 운영 SSO 는 꺼져 있다(모든 요청 admin, 사용자 결정 10-29 「켜기 전에 영향부터 조사」). 켜면 DynaForge 덱 업로드(`StcxUploader`, 인증 없음)가 401 이 된다 — KooSlurm 제안은 예약자 본인의 kst_ PAT. 켜기 전 예약은 켜는 순간 403 이 될 수 있다(신원이 admin → 실제 사용자).
