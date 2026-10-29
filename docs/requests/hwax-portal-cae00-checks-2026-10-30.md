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
7. (운영 측) stcx 후처리 이미지 **Post v42** 설치 — 단면 영상 응력 0 프레임 고침 → §5-1.
SSO 켜기는 **이번에 하지 않는다**(§7 — 조건이 안 섰다).

## 1. cae00 — DynaForge 받기(update-all 뒤)
이번 판에 든 것 — 반입 속도(raw_decode `288afb7` · sphere 블록 분리 `c7970dc`) · 후처리 예약 `postprocess`(`4ff9a79` → 위임 창구 `e62f601` · rc 3 경고) · 구면 위험도 맵(3D · 허용비 · 상위 N, `f366816`) · 렌더 결과 반입 C-11(`85ba2f0`) · postprocess 의 비운 선택 칸 null 을 없는 칸으로(`07679d7`) · `dev_rev` 를 예약 때 반입 규칙으로(`3574342`) — 둘 다 파이썬만, git 으로 온다. **마이그레이션 둘**(0015 · 0016 — null 허용 칸 · 유일 제약, 옛 코드에 영향 없음). 바이너리는 그대로(`8c7c4f87`).

| 확인 | 명령 | 기대값 |
|---|---|---|
| 판 | `curl -s http://127.0.0.1:8700/api/health` | `"status":"ok"` · `revision` 이 이번 게시 BUILD_INFO 의 커밋(`c9bc426`) |
| 소스 | KooRemapper 리포 루트에서 `git log -1 --oneline` | `3574342` 이거나 그 뒤 — 위 `revision` 은 Drive 판의 커밋이라 파이썬만 바뀐 커밋은 여기서만 보인다. 앞이면 null 을 보내는 손님(MCP 직접 호출 — Claude 등)이 비운 선택 칸에서 422 를 받고(포털 R2a 는 칸째 빼고 보내 영향 없음), 틀린 `dev_rev` 가 예약은 되고 잡이 끝난 뒤 반입에서야 실패한다 |
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
2. **DynaForge 예약** — 그 잡을 제출한 절차(포털 R2a, `9ce09b6`)가 걸어 둔 `postprocess` 잡이 `succeeded` 가 되고 `resolved_cmd.report_ids` 에 리포트 id 가 생긴다. 리포트가 예약자 명의로 들어왔는지(제출 때 과제 메타 — `project` · `dev_rev` · `variation` · `doe` — 를 채웠으면 그 값도), 리포트 상세의 `external_job_key` = `stcx:<잡 id>` 인지 본다.
3. 실패면 잡의 `error_summary` 가 매니페스트 까닭을 그대로 싣는다 — 그 문구를 DynaForge 에 넘긴다.

## 5. stcx viz 노드 — 읽기만(SceneForge · S1)
GPU 는 노드마다 챗 LLM 과 함께 쓴다 — **읽기만**(MIG 전환 · GPU 재설정 · 설치 · 렌더 없음). 명령의 정본은 SceneForge `scripts/stcx_viz_readcheck.sh`(f46e835) — 결과를 텍스트 파일 하나로 모은다. 그 파일을 SceneForge 세션에 넘긴다.
```
bash stcx_viz_readcheck.sh                                    # 1단계 — 로그인 노드만, 노드에 잡을 걸지 않는다
bash stcx_viz_readcheck.sh <viz 파티션> <노드> <S1 결과 폴더>    # 2단계 — 고른 노드에 CPU 1 · 512M · 5분 · GPU 요청 없는 잡 하나
```
- 2단계 앞뒤로 cae00 에서 `~/stcx-llm/llmctl.sh status`(챗 LLM 이 그대로인지).
- **<S1 결과 폴더>** — S1 은 아직 나오지 않았다(KooD3plotReader 추출기 계약 대기). 둘 자리는 추출기 쪽(KooD3plotReader)이 정한다 — 후보는 각도 run 폴더 안 `Output/s1.h5` 와 결과 옆 `<RESULT_DIR>/output/s1/` 둘이고, 둘 다 `<RESULT_DIR>/output` 아래다. 그러니 지금은 운영 전각도 잡 하나의 `<RESULT_DIR>/output`(sphere_report.html 이 있는 곳 — 귀환 매니페스트의 `job.result_dir`)로 마운트를 본다.
- 스크립트를 못 옮기면 한 줄씩 — SceneForge `docs/requests/dynaforge-sceneforge-tasks-reply-2026-10-29.md` 「cae00 명령」 절(sinfo · squeue · 챗 LLM sbatch gres · scontrol config · `nvidia-smi` · `ldconfig -p` 로 GL/EGL/NVENC/Vulkan 라이브러리 · `apptainer --version` · `ls -la <폴더>`).
- 제어면 준비로 둘 더 — SceneForge 를 돌릴 cae00 계정에서 `ssh -o BatchMode=yes stcx true && echo ok`(sbatch 낼 길이 비밀번호 없이 열리나, C-13) · `ssh stcx df -h /data2`(렌더 작업자 SIF · 결과 자리 여유 — 자리는 노드 관리자와 정한다).
- GPU 를 쓰는 시험(T1 · T2)은 SceneForge `docs/research/stcx-gpu-test-plan-2026-10-29.md` — 읽기 점검 결과가 나온 뒤 챗 LLM 운영과 시간을 잡고.

## 5-1. stcx — 후처리 이미지 Post v42(운영 측 설치)
단면 영상 **응력 0 프레임**(K-1 — 운영 영상 24개 중 7개가 오류 없이 응력 0) 고침이 든 판이다(KooD3plotReader `5abbc76`). pyKooCAE 가 Drive `ApptainerImages:SmartTwinPreprocessor/` 에 올렸다 — `SmartTwinPostprocessor_20261029_v42.tar.gz`, sha256 헤드리스 `1a6e0933…` · GUI `4536ea72…`. 이 박스에서 stcx 로 밀어 넣는 절차는 없고 **설치는 운영 측 몫**이다.
- 설치 뒤 — `apptainer exec <설치한 SmartTwinPostprocessor.sif> head -3 /opt/kood3plot/VERSION` → `Version: 5abbc76`.
- 고침 자체는 dev 헤드에서 확인했다 — 결함을 매번 일으키는 설정(LS-PrePost 예산 20M)을 심어도 정상이고, 옛 판(Post v41 `282630b`)은 같은 설정에서 0 을 내며 rc 0 으로 끝났다(KooRemapper `7818cbc`). 운영에서는 설치 뒤 전각도 잡 하나의 단면 영상 마지막 프레임 범례가 `max = 0, at node# 0` 이 아닌지만 본다.

## 6. 게이트웨이 — 게이트웨이를 거친 stcx 제출이 지금 되는가(선택)
```
tail -3000 ~/Projects/HWAXMcpGateway/audit.jsonl | grep -a '"backend": "smart-twin' | tail -5
```
`ok` · `error` 칸만 본다. 게이트웨이는 smart-twin 백엔드에 Authorization 을 싣지 않아(사람별 위임은 미룸 — 사용자 「나로 일단」), smarttwin_mcp 가 서버 env `STMC_CLUSTER_TOKEN` 으로 넘어간다. 그것도 없으면 거부다.

## 7. SSO 켜기 — 이번엔 하지 않는다(조건)
KooSlurm `docs/sso_enable_20261029/sso_enable_procedure.md`. 켜기 전에 설 것 —
- **IdP 주소** — 저장소의 운영 YAML 사본은 `sso.saml.idp.sso_url` 이 비었다. 비었으면 켜는 순간 아무도 로그인 못 한다(icn401 실제 YAML 확인).
- **SSO 꺼진 동안 발급한 kst_ 는 전부 admin 으로 저장됐다** — 켠 뒤 그대로 두면 관리자 토큰이다. 절차서 §2 대로 지우고 다시 발급(`~/.claude.json` 의 smarttwin kst_ 포함). **smarttwin-mcp 유닛 env 의 `STMC_CLUSTER_TOKEN` 도** — 그대로 두면 게이트웨이 경유 제출이 전부 관리자 권한으로 간다. 다시 발급한 토큰의 주인이 그 뒤 제출 · 업로드의 명의가 된다(KooSlurm `a4734e7a`).
- **DynaForge 덱 업로드의 신원 = 제출 신원**(절차서 §0 조건 5) — 게이트웨이 경유 단일 신원이면 업로드도 그 토큰(`STMC_CLUSTER_TOKEN`), 사람별 위임이면 업로드도 위임 창구 토큰. 어긋나면 켜는 순간 거절된다. 어느 쪽인지는 켤 때 사용자 결정이고, DynaForge 업로더는 그 결정에 맞춰 짓는다(지금은 보류).
- 걸린 예약이 없을 때 켠다 — 켜는 순간 신원이 admin → 실제 사용자로 바뀌어 켜기 전 예약은 403 으로 닫힌다.

## 8. 되돌리기
- **DynaForge** — 아티팩트: `rclone copy ApptainerImages:KooRemapper/dist/dist-<이전 판>/ ApptainerImages:KooRemapper/dist/latest/` 뒤 `update-all`(또는 `dist-from-drive.sh --restart`). 코드: 이전 커밋으로. 마이그레이션 0015 · 0016 은 null 허용 칸 · 유일 제약이라 옛 코드가 그대로 돈다 — 되돌리지 않아도 된다.
- **KooSlurm** — 그쪽 문서의 되돌리기 절.

## 9. 남은 사람 결정(참고)
옛 결과 리포트 셸 다시 만들기 `--regen-sh`(pyKooCAE — 옛 부분충격 결과는 이것 없이 7-1 로 못 받는다) · SSO 켤 시각(§7) · 렌더 결과를 붙이는 명의(소유자만 / 같은 소속) · 보고 영상 「접촉 앞」 해석 밖 구간 · 과제 키 검증(7-4) · pyKooCAE F 예제.
