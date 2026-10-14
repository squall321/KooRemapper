# 설계 — stcx 전각도 낙하를 SmartTwinMCP(:5013)로

요청서 `DynaForge 변경 요청서 — stcx 전각도 낙하를 SmartTwinMCP 로 돌게 하기`(2026-10-14, koo.park)
· 기준 `ba9e16e` · 작업 HEAD `cbe71c6`
체크리스트 `stcx-smarttwin.checklist.md` · 맥락 `stcx-smarttwin.context-notes.md`

**목표는 하나 — 일단 돈다.** `stcx_fullangle_drop` 을 제출하면 stcx 에서 실제로 돌고 DynaForge 가
상태를 따라간다. 옵션 전부·결과 회수·세부 각도는 다음 판이다.

## 0. 요청서 주장을 전수 확인했다 — 전부 사실이다

운영 헤드노드에서 읽으신 `file:line` 을 이 박스의 사본으로 대조했다. 줄번호 `:43`·`:77`·`:187`·`:304`
가 **정확히 일치**하므로 같은 파일로 본다.

| 요청서 주장 | 실측 |
|---|---|
| 직접 노출 도구는 `args` 하나를 받는다 | ✓ `server.py:218-219` `def _direct(args: dict \| None = None)` |
| `dry_run` 기본값 **false** | ✓ 스키마 `default=False` |
| 필수는 `work_dir`·`lstc_license_ip` | ✓ |
| `model_file_path` 패턴 `^/.+\.k$` | ✓ |
| 응답이 JSON 봉투 | ✓ `runner.py:40-49` `{ok, exit_code, stdout, stderr, result, transport, command}` |
| 리스트는 통째 교체 | ✓ `scenario_builder.py:88-89` "Lists in overrides REPLACE base lists" |
| 업로드 3단계 · 50GB | ✓ `file_upload_api.py:43`·`:77`·`:187`·`:304` |
| 인증 필요 없다 | ✓ `jwt_middleware.py:118-120` — `SSO_ENABLED` 가 꺼지면 `FULL_ACCESS_USER`(admin)로 **그냥 통과** |

추가로 잰 것 — `.k` 는 분류 `data`, 보안검사 `safe`(실제로 돌려 봤다). 올라간다.
그리고 **`additionalProperties: False`** 다 — 모르는 인자는 조용히 버려지지 않고 **거절**된다.

## 1. 요청서에 없던 함정 셋

### ★A. 업로드가 **덮어쓴다** — `job_id` 를 줘야 갈린다

`complete` 의 `final_path = storage_path/filename`(`:368`)이고 `storage_path` 는
`get_storage_path(type, user_id, job_id)` 다(`file_classifier.py:295-304`).

- `job_id` 없음 → `/shared/uploads/users/admin/data/<filename>`
- `job_id` 있음 → `/shared/uploads/jobs/<job_id>/data/<filename>`

SSO 가 꺼져 있어 **모든 DynaForge 사용자가 `admin`** 이다. 따라서 `job_id` 를 안 주면 서로 다른
잡이 올린 같은 이름의 덱이 **한 자리에 겹쳐 덮인다** — 먼저 올린 잡이 남의 덱으로 돈다.

→ **`init` 에 `job_id = DynaForge job id` 를 싣는다.** API 가 이미 받는 선택 필드다.

⚠ **2026-10-14 에 뒤집혔다** — fullangle 1.1.2 가 `model_file_path` 를 호출자 영역
(`/shared/uploads/users/<user>` 등) 안에서만 읽어, jobs/ 경로는 제출이 거절된다
(`docs/requests/smarttwinmcp-contract-request-2026-10-14.md` §1). 이제 `job_id` 는 싣지 않고
**이름 앞에 잡 id 를 붙여** `users/<user>/data/<job.id>_<이름>.k` 로 가른다(`upload_name`).

### ★B. `model_file` 이 이미 있으면 올린 덱이 **조용히 무시된다**

`fullangle_drop_simulation/latest/script.sh:46-52` —

```python
model_target = os.path.join(work_dir, model_file)   # model_file 기본 "MinimumModel.k"
if not os.path.exists(model_target):
    if model_file_path and os.path.exists(model_file_path):
        shutil.copy(model_file_path, model_target)
    else:
        fail(f"Model file missing: {model_target}")
```

`work_dir` 가 잡마다 고유하면 처음엔 비어 있으니 괜찮다. 그러나 **재제출·재시도로 같은 `work_dir`
를 다시 쓰면 묵은 덱으로 돈다.** 요청서 §3 의 "시간 초과에 다시 제출하지 않는다" 가 이것을
우연히 막아 준다 — 그래서 그 규칙을 **반드시** 지킨다.

올린 덱의 이름은 `work_dir` 안에서 `MinimumModel.k` 가 된다(시나리오도 같은 이름을 가리키므로
동작에는 문제없다). 이름을 살리려면 `model_file` 도 함께 보내야 하는데, 요청서가 "이것만" 이라
했으므로 **이번 판에서는 안 보낸다.** 확인 사항으로 올린다.

### ★C. 종료 판정의 근거가 응답에 **없다**

요청서 §4 는 「`slurm_job_ids` 가 squeue 에서 모두 사라지면 끝」으로 두라고 했다. 그런데
`job_status` 응답에는 `slurm_job_ids` 가 **없다**(`job_status/latest/script.sh:16-22`).
있는 것은 `squeue` 뿐이고, `slurm_queue_for` 는 **예외가 나도 `{}`** 를 돌려준다
(`job_helpers.py:197-198`). 그래서 빈 `{}` 하나가 세 가지를 뜻한다.

1. 다 끝났다  2. 애초에 slurm id 가 없다(제출 직후)  3. squeue 호출이 실패했다

→ **`get_job_details` 를 함께 부른다.** 그 도구는 레지스트리 행 전체를 주고 거기에
`slurm_job_ids` 가 있다(`registry.py:38`·`:77`, `get_job_details/latest/script.sh:84`).
둘 다 `expose: direct` 라 오늘 게이트웨이로 부를 수 있다. 판정은 —

| `slurm_job_ids` | `squeue` | 판정 |
|---|---|---|
| 비어 있음 | — | **active** (아직 큐에 안 올랐다) |
| 있음 | 하나라도 ACTIVE 상태 | **active** |
| 있음 | 하나라도 BAD 상태 | **failed** |
| 있음 | 전부 없음 | **succeeded** (요청서가 정한 잠정 규칙) |
| 도구 실패 | — | **unknown** — 접지 않고 다음에 다시 본다 |

⚠ 덧 — `job_status` 응답의 `job_id` 는 **레지스트리 행 id** 이고, 제출 응답의 `job_id` 는
**slurm job id** 다. **같은 이름, 다른 것**이다. `registry_id` 로만 지목한다.

## 2. 흐름

```
_submit_external
  ├─ include 있으면 즉시 실패 ("INCLUDE 가 있는 덱은 아직 stcx 로 못 보낸다")
  ├─ 미지원 옵션 들어왔으면 즉시 실패 (조용히 버리지 않는다)
  ├─ 반입  init(job_id=DynaForge job id) → chunk ×N → complete  ⇒ file_path
  ├─ 제출  smarttwinmcp_fullangle_drop_simulation {"args": {...}}
  │         work_dir = {WORK_ROOT}/{DynaForge job id}
  └─ external_ref ← registry_id · job_id · work_dir · output_dir · sphere_report_path

시간 초과 → 재제출하지 않는다. job_status({"work_dir": …}) 로 먼저 찾는다.

_poll_external_once
  ├─ get_job_details({"registry_id": N})  → slurm_job_ids
  ├─ job_status({"registry_id": N})       → squeue
  └─ 위 표로 판정. 모르면 접지 않는다.
```

## 3. 설정 (새 3 · 기존 1)

| 키 | 뜻 | 비면 |
|---|---|---|
| `KOORM_GATEWAY_PAT` (기존) | 게이트웨이 호출 | 작업 꺼짐 |
| `KOORM_STCX_BACKEND_URL` | 반입 API 터널 주소 | 작업 꺼짐 |
| `KOORM_STCX_WORK_ROOT` | 헤드노드 작업 루트 | 작업 꺼짐 |
| `KOORM_STCX_LSTC_IP` | 라이선스 서버 IPv4 | 작업 꺼짐 |

**코드에 기본값을 박지 않는다**(`config.py:86` 의 규약 그대로).

## 4. 이번 판에 안 하는 것

요청서 §5 그대로 — 피보나치 외 각도 방식·공차·DR·접촉·연속 낙하 · 결과 회수 · 잡 소유자 ·
`*INCLUDE` 덱. 추가로 `model_file` 이름 보존(★B)도 다음 판으로 둔다.
