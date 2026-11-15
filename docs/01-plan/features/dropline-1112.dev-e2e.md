# dev E2E — 해석기 없는 후처리 예약 · 반입 차례 (2026-11-12)

사용자 결정 11-12: KooSlurm 세션이 C 길 후처리 잡을 짜고, 포털이 노드 VM 을 켠다. DynaForge 쪽은 이 문서대로 예약 ·
반입을 돌린다. **값은 dev 박스의 `platform/.env` 에만 둔다 — 이 리포 · 챗 · 잡 인자에 적지 않는다.**
누가 어떤 값을 주는지는 포털이 사용자에게 묻고 알린다(같은 물음이 두 번 가지 않게 이쪽은 묻지 않는다).

## 0. 어느 칸이 드나

| 칸 | 후처리 예약 · 반입 | stcx 제출(전각도) | 값의 짝 |
|---|---|---|---|
| `KOORM_STCX_BACKEND_URL` | **필요** | 필요 | KooSlurm 대시보드(backend_5010) 주소 — 덱 업로드 · 잡 REST · 위임 창구가 같은 곳 |
| `KOORM_KOOSLURM_SSO_SECRET` | **필요** | — | KooSlurm 쪽 `HEAX_GATEWAY_SECRET` 과 **같은 값** |
| `KOORM_GATEWAY_PAT` | — | 필요 | 게이트웨이(:9110) PAT — 제출 도구를 부르는 신원 |
| `KOORM_STCX_WORK_ROOT` · `KOORM_STCX_LSTC_IP` | — | 필요 | 헤드노드 작업 루트 · 라이선스 IPv4 |

해석기 없는 E2E(C 길 후처리 잡만)는 **위 두 칸**이면 된다. 예약 신원은 토큰을 나르지 않고 확인할 때마다 위임 창구
(`<URL>/api/auth/sso`)에서 **잡 소유자 이메일**로 kst_ 를 받는다 — 그 사람이 KooSlurm 에서 잡을 볼 수 있어야 한다.

## 1. 반영

1. 값을 `platform/.env` 에 넣는다(위 칸 이름 그대로).
2. `bash platform/infra/scripts/restart-api-only.sh` — 워커가 API 프로세스 안에서 돌아 이것 하나로 설정이 들어간다.

## 2. 점검 — 값은 출력하지 않는다

```
python3 platform/infra/scripts/check-postprocess.py                        # 칸 · 위임 창구가 살아 있나
python3 platform/infra/scripts/check-postprocess.py --email <예약자 이메일>   # + 그 사람 명의 토큰을 실제로 받아 본다
```

- `후처리 예약 · 반입: 설정 칸과 위임 창구가 갖춰졌다` 가 나와야 다음으로 간다.
- 위임 창구가 `HTTP 200`(비밀 없이 토큰을 줌)이면 멈추고 KooSlurm 쪽에 알린다.
- `--email` 은 토큰을 **발급**한다 — 예약할 그 사람으로만 한 번.

## 3. 예약

KooSlurm 세션이 C 길 후처리 잡의 Slurm 잡 id 를 알려 주면 —

```
run_operation(session_id, operation="postprocess",
              args={"job_key": "stcx:<Slurm 잡 id>", "sim_type": "fullangle_drop", ...})
```

(`sim_type` 은 `fullangle_drop` → sphere · `partial_impact` → impact. 나머지 인자는 `describe_operation("postprocess")`.)

## 4. 확인 차례

1. `get_job(job_id)` — `status` 와 **`external`**:
   - `external.cluster_state` — KooSlurm 이 말하는 클러스터 잡 상태(RUNNING · COMPLETED · FAILED …)
   - `external.ontology.state` — 해석 온톨로지 꾸러미: `loaded` · `absent`(이번 잡에 꾸러미 없음) · `no_field`(옛 매니페스트) ·
     `failed`(+ `why`, 리포트는 반입됐다)
   - `status=failed` 이고 `error_summary` 가 「구성 안 됨 — …」 이면 1 · 2 로 돌아간다.
2. `find_reports(external_job_key="stcx:<Slurm 잡 id>")` — 반입된 리포트 하나가 나와야 한다(잡 하나에 리포트 하나).
3. `report_summary(report_id)` — 케이스 수 · 최악 응력/가속 · 파트.
4. `report_cae(report_id)` — 꾸러미가 실렸으면 파트 판정 · 하중 경로.
5. (덤) `system_status()` 의 `postprocess_versions` — 방금 리포트의 후처리 판이 맨 앞에 보인다.
