# cae00 · icn401 · stcx 점검 — 2026-10-30 반영분(DynaForge 후처리 반입 · 낙하 트윈 P1 · P2 · P3 받는 쪽)

**누가 · 어디서** 사람이 cae00(실사용 서버)·icn401(KooSlurm 운영)·stcx 에서 돌리는 확인이다. 포털 `docs/cae00-deploy-guide.md` 의 「2026-10-30 반영분」 절로 옮긴다(포털 세션).
**정본** DynaForge 쪽 결정 · 계약은 KooRemapper `platform/docs/REQUEST-postprocess-operation.md` §10, `docs/01-plan/features/{postprocess-reservation-1028,sphere-risk-map-1029}.plan.md`, 총괄 `drop-twin-1028.checklist.md`. KooSlurm 쪽은 KooSlurm `docs/sso_enable_20261029/{icn401_apply_check,sso_enable_procedure}.md`(origin `46c647e4`).

## 0. 순서 — 한 줄씩
1. **cae00** — `git pull && update-all`(kooremapper 가 Drive 판 `dist-20261029-221150Z` 를 받는다) → §1 확인.
2. **icn401** — `git pull && sudo ./dashboard/start_production.sh` → §3 확인(KooSlurm 문서 §2).
3. **비밀 하나를 두 곳에** — icn401 `HEAX_GATEWAY_SECRET`(backend_5010/.env) = cae00 `KOORM_KOOSLURM_SSO_SECRET`(KooRemapper platform/.env) → §2 · §3-3.
4. **cae00** — `KOORM_STCX_BACKEND_URL` 확인 → DynaForge 재기동 → §2 확인.
5. 운영의 **첫 실제 전각도 잡** 뒤 → §4.
6. (사람 · 읽기만) stcx viz 노드 · 게이트웨이 감사 → §5 · §6.
SSO 켜기는 **이번에 하지 않는다**(§7 — 조건이 안 섰다).

## 1. cae00 — DynaForge 받기(update-all 뒤)
이번 판에 든 것 — 반입 속도(raw_decode `288afb7` · sphere 블록 분리 `c7970dc`) · 후처리 예약 `postprocess`(`4ff9a79` → 위임 창구 `e62f601` · rc 3 경고) · 구면 위험도 맵(3D · 허용비 · 상위 N, `f366816`) · 렌더 결과 반입 C-11(`85ba2f0`). **마이그레이션 둘**(0015 · 0016 — null 허용 칸 · 유일 제약, 옛 코드에 영향 없음). 바이너리는 그대로(`8c7c4f87`).

| 확인 | 명령 | 기대값 |
|---|---|---|
| 판 | `curl -s http://127.0.0.1:8700/api/health` | `"status":"ok"` · `revision` 이 이번 게시 BUILD_INFO 의 커밋(`c9bc426`) |
| 마이그레이션 | KooRemapper 리포 루트에서 `bash platform/infra/scripts/migrate.sh` | 「Running upgrade」 줄 없이 「✓ migrations applied」 = 이미 0016 까지 올라 있다(빠졌으면 이 명령이 그 자리에서 올린다 — 0015 · 0016) |
| MCP 도구 | 게이트웨이 tools/list 에서 kooremapper 도구 수, 또는 `platform/mcp_server/venv/bin/python platform/mcp_server/smoke.py` | 81개(`attach_render` 가 새로 있다) · `MCP SMOKE: PASS` |
| 화면 | 세션 → 전각도 리포트 펼치기 → 「부품 위치·방향 시각화」 → 보기 「구(3D)」 | 3D 구가 뜬다(three.js 는 묶음 안에 있다 — 망 밖에 안 나간다) · 허용값을 넣으면 「초과 · 경고」 수가 보인다 |

⚠ 화면이 옛것이면 — dist 는 받았는데 API 가 옛 index 를 내는 것이다. `update-all` 이 재기동을 건너뛰었는지(§2 지문) 보고, 아니면 KooRemapper `platform/infra/scripts/restart-api-only.sh`(도는 잡 0 확인 뒤).

## 2. cae00 — 후처리 예약(7-1) 설정
`platform/.env`(KooRemapper)에 둘. **값은 화면 · 로그 · 채팅에 붙이지 않는다.**
```
KOORM_STCX_BACKEND_URL=<cae00 에서 닿는 stcx 대시보드 주소 — 덱 업로드에 쓰는 것과 같은 값>
KOORM_KOOSLURM_SSO_SECRET=<icn401 backend_5010/.env 의 HEAX_GATEWAY_SECRET 과 같은 값>
```
선택 — `KOORM_POSTPROCESS_WAIT_DAYS`(기본 7) · `KOORM_KOOSLURM_TIMEOUT_SEC`(기본 30). 넣은 뒤 재기동(도는 잡 0 확인 → `restart-api-only.sh`, 또는 다음 `update-all` 이 .env 지문으로 재기동).

**확인 — 없는 잡으로 예약해 본다**(운영 잡을 건드리지 않는다). 콘솔에서 세션 하나 → 오퍼레이션 `postprocess` → `job_key=stcx:0`, `sim_type=fullangle_drop` → 실행. 또는 `platform/mcp_server/venv/bin/python platform/mcp_server/allops_smoke.py` 의 postprocess 줄.
| 잡의 오류 문구 | 뜻 |
|---|---|
| 「구성 안 됨 — KOORM_… 이(가) 비었다」 | 설정이 아직 안 들어갔다(또는 재기동 전) |
| 「위임 창구가 잡 소유자의 토큰을 내주지 않았다(sso_401)」 | 비밀이 icn401 과 다르다 |
| 「…(sso_404)」 | icn401 에 비밀이 아직 없다(§3-3) — 창구가 닫혀 있다 |
| 「…(sso_400)」 | 이메일이 사용자 이름 규칙에 안 맞는다(`@` 앞이 `[a-z0-9._-]` 1~32 · admin · root · anonymous 거절) |
| 1~2분 뒤 「클러스터가 이 잡을 모른다(`/info` 404 …)」 | **정상** — 설정 · 위임 · 대시보드 REST 가 다 닿았다(잡 0 은 없다) |

## 3. icn401 — KooSlurm 반영(사람)
KooSlurm `docs/sso_enable_20261029/icn401_apply_check.md` 그대로. 요점 —
1. 반영 `git pull && sudo ./dashboard/start_production.sh`(로그를 /tmp 에 tee). 결과 귀환(`7c280000` 까지) · 위임 창구(`3f72f4c6`) · 문서(`46c647e4`)가 한 번에 들어간다.
2. 확인 10개 — 코드 판 · 템플릿 동기화 줄 · 드라이버 템플릿 `grep -c write_return_manifest` = 3 · LSTC 플레이스홀더 0 · 「→ SSO=false → 정본 conf: hpc-portal.conf」 · frontend_3010 재빌드 · 백엔드 active · C 라우트(새 코드면 400 · error_code 9001) · 다운로드 티켓 · 위임 창구 비밀 전 404.
3. `HEAX_GATEWAY_SECRET` 넣기(backend_5010/.env · chmod 600 · 재시작) → `curl -s -o /dev/null -w '%{http_code}' -X POST -H "X-Heax-Gateway-Secret: <비밀>" https://<대시보드>/api/auth/sso/verify` → **204**(틀리면 401). 같은 값을 cae00 §2 에.

## 4. 운영 첫 실제 전각도 잡 뒤 — 끝까지 한 번
1. **B(드라이버 매니페스트)** — KooSlurm 문서 §4: `sacct` · 드라이버 로그 끝 「=== 귀환 매니페스트 ===」 · `<RESULT_DIR>/output/return_manifest.json`. 정상이면 `COMPLETED 0:0` · `ok: true` · 리포트 sha256 이 파일과 같다. 없으면 `FAILED 3:0` · `reason` · `log_tail` — 그 줄을 KooSlurm 에 넘긴다(없으면 C 로 다시 거는 curl 이 문서에 있다).
2. **DynaForge 예약** — 그 잡을 제출한 절차(포털 R2a, `9ce09b6`)가 걸어 둔 `postprocess` 잡이 `succeeded` 가 되고 `resolved_cmd.report_ids` 에 리포트 id 가 생긴다. 리포트가 예약자 명의 · 과제 메타로 들어왔는지, 리포트 상세의 `external_job_key` = `stcx:<잡 id>` 인지 본다.
3. 실패면 잡의 `error_summary` 가 매니페스트 까닭을 그대로 싣는다 — 그 문구를 DynaForge 에 넘긴다.

## 5. stcx viz 노드 — 읽기만(SceneForge · S1)
GPU 는 노드마다 챗 LLM 과 함께 쓴다 — **읽기만**. MIG · 렌더 시험은 챗 LLM 운영과 시간을 잡고 나서.
```
ssh stcx sinfo -s
ssh stcx scontrol show node <viz 노드>                # gres · 메모리 · 상태
ssh stcx srun -p <viz 파티션> -w <viz 노드> ls <운영 전각도 잡의 output_dir>   # S1 이 그 자리에서 읽히나(⑥)
```
결과는 SceneForge 세션에 넘긴다(그쪽이 렌더 잡 규율 — gres 로 GPU · `--mem` 필수 · 노드 하나씩).

## 6. 게이트웨이 — 게이트웨이를 거친 stcx 제출이 지금 되는가(선택)
```
tail -3000 ~/Projects/HWAXMcpGateway/audit.jsonl | grep -a '"backend": "smart-twin' | tail -5
```
`ok` · `error` 칸만 본다. 게이트웨이는 smart-twin 백엔드에 Authorization 을 싣지 않아(사람별 위임은 미룸 — 사용자 「나로 일단」), smarttwin_mcp 가 서버 env `STMC_CLUSTER_TOKEN` 으로 넘어간다. 그것도 없으면 거부다.

## 7. SSO 켜기 — 이번엔 하지 않는다(조건)
KooSlurm `docs/sso_enable_20261029/sso_enable_procedure.md`. 켜기 전에 설 것 —
- **IdP 주소** — 저장소의 운영 YAML 사본은 `sso.saml.idp.sso_url` 이 비었다. 비었으면 켜는 순간 아무도 로그인 못 한다(icn401 실제 YAML 확인).
- **SSO 꺼진 동안 발급한 kst_ 는 전부 admin 으로 저장됐다** — 켠 뒤 그대로 두면 관리자 토큰이다. 절차서 §2 대로 지우고 다시 발급(`~/.claude.json` 의 smarttwin kst_ 포함).
- **DynaForge 덱 업로드의 신원** — 업로드 PAT = 제출 PAT 여야 smarttwin_mcp 가 받는다. 제출은 지금 게이트웨이 단일 신원(「나로」)이라, 업로드만 잡 소유자로 바꾸면 켜는 순간 제출이 거절된다. 켤 때 신원 방식(사람별 위임 · 단일)과 함께 정한다.
- 걸린 예약이 없을 때 켠다 — 켜는 순간 신원이 admin → 실제 사용자로 바뀌어 켜기 전 예약은 403 으로 닫힌다.

## 8. 되돌리기
- **DynaForge** — 아티팩트: `rclone copy ApptainerImages:KooRemapper/dist/dist-<이전 판>/ ApptainerImages:KooRemapper/dist/latest/` 뒤 `update-all`(또는 `dist-from-drive.sh --restart`). 코드: 이전 커밋으로. 마이그레이션 0015 · 0016 은 null 허용 칸 · 유일 제약이라 옛 코드가 그대로 돈다 — 되돌리지 않아도 된다.
- **KooSlurm** — 그쪽 문서의 되돌리기 절.

## 9. 남은 사람 결정(참고)
옛 결과 리포트 셸 다시 만들기 `--regen-sh`(pyKooCAE — 옛 부분충격 결과는 이것 없이 7-1 로 못 받는다) · SSO 켤 시각(§7) · 렌더 결과를 붙이는 명의(소유자만 / 같은 소속) · 보고 영상 「접촉 앞」 해석 밖 구간 · 과제 키 검증(7-4) · pyKooCAE F 예제.
