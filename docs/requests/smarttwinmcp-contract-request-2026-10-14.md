# SmartTwinMCP 연동 변경 요청서 — 개통 전 접근 통제가 DynaForge 제출 경로에 걸리는 곳

**보내는 쪽**: SmartTwinMCP(:5013) 개발 — `KooSlurmInstallAutomationRefactory/dashboard/smarttwin_mcp`
**받는 쪽**: DynaForge — `platform/backend/app/runner/stcx_client.py` · `app/worker/runner_loop.py` (92cb157 기준)
**작성일**: 2026-10-14
**한 줄**: stcx 운영 배포 요청(koo.park, 2026-10-14)을 반영하면서 HWAX 개통 범위(plat:smarttwin 전원)에 맞춰
접근 통제를 넣었다(SmartTwinCluster `5aa61b67`, 푸시됨). 그중 **업로드 `job_id`** 는 지금 DynaForge 제출을
막는다. 그 밖에 DynaForge 복구 경로를 무력하게 만들던 우리 쪽 결함은 고쳤다(`b1274d04`, 푸시됨).
**성격**: 맞춰 달라는 요청 둘(§1·§2), 우리 제안(§5)에 대한 답, 나머지는 알림이다.

| § | 무엇 | 누가 | 급함 |
|---|---|---|---|
| 1 | 업로드 init 에 `job_id` 를 싣지 말고 **파일 이름**으로 가르기 | DynaForge | 🔴 개통 전 필수 |
| 2 | `KOORM_STCX_WORK_ROOT` 를 허용 루트와 맞추기 | DynaForge + 운영 | 🔴 개통 전 필수 |
| 3 | 제출·조회에 PAT 신원이 붙는다 | 알림 | — |
| 4 | 제출 응답의 `work_dir` 이 registry 와 달라 `job_status(work_dir=…)` 복구가 늘 실패 | **우리 결함 — 고침** | 알림 |
| 5 | `job_status` 에 `slurm_job_ids` 추가(★C) · 모델 재사용을 응답에 표시(★B) | **우리 — 반영함** | 알림 |
| 6 | 버전·도구 목록 변화, SSO 꺼짐 환경의 의미 | 알림 | — |
| 7 | 제출이 성공하면 업로드를 지운다 (§1 회신 뒤 추가) | DynaForge | 개통 전 권장 |

---

## 1. 🔴 업로드 `job_id` → `model_file_path` 거절

`fullangle_drop_simulation` 1.1.2(latest)는 `model_file_path` 를 **호출자 영역 안**에서만 읽는다.

- 근거 — `smarttwin_mcp/tools/_shared/stmc_exec.py:76`
  `DEFAULT_INPUT_ROOTS = "/data/single/{user}:/shared/uploads/users/{user}:/data/scenario"`,
  `:204` 에서 그 안인지 확인한 뒤 복사한다. `{user}` 는 요청 PAT 로 backend `/api/me` 가 돌려준 이름이다.
- DynaForge 는 `StcxUploader.upload(..., job_id=str(job.id))`(`runner_loop.py:337`)로 올리므로 파일이
  `/shared/uploads/jobs/<job.id>/data/<이름>.k` 에 저장되고, 제출은
  `허용 범위 밖의 경로다: /shared/uploads/jobs/…` 로 **실패한다**.

`/shared/uploads/jobs/` 를 허용 루트에 넣지 않은 이유 — 그 경로는 올린 사람과 묶여 있지 않다. 넣으면 어떤
호출자든 남의 잡이 올린 덱 경로를 `model_file_path` 로 줘서 자기 잡으로 가져갈 수 있다.

**요청** — init 에서 `job_id` 를 빼고, ★A(같은 이름이 서로 덮임)는 **파일 이름에 잡 id 를 넣어** 가른다.

```python
# stcx_client.py — upload_name 이 잡 id 를 받는다(원본 파일은 그대로)
def upload_name(name: str, job_id: str) -> str:
    base = Path(name).name
    stem = base[:-2] if base.endswith(".k") else Path(base).stem
    return f"{job_id}_{stem}.k"          # → /shared/uploads/users/<사용자>/data/<job.id>_<이름>.k
```

API 변경은 양쪽 다 없다. `^/.+\.k$` 패턴도 그대로 맞는다.
`job_id` 디렉터리를 꼭 써야 하면 알려 달라 — 그때는 우리가 backend 업로드 기록(`/api/v2/files/uploads`,
호출자 범위)에서 그 경로가 호출자의 것인지 확인하는 쪽으로 열겠다(작업량이 더 크다).

## 2. 🔴 `KOORM_STCX_WORK_ROOT` = 허용 루트

`work_dir` 도 호출자 영역(`/data/single/<사용자>/`) 또는 서버 env `STMC_WORK_ROOTS` 아래만 받는다
(`stmc_exec.py:180`). 밖이면 `허용 범위 밖의 경로다` 로 실패하고 폴더도 만들지 않는다.

stcx 운영에는 `STMC_WORK_ROOTS=/data/koopark/dynaforge` 를 넣어 달라고 회신했다(요청서 1-5 의 작업 루트 그대로).
따라서 **DynaForge 쪽 값은 지금 그대로** `KOORM_STCX_WORK_ROOT=/data/koopark/dynaforge` 면 된다 —
`work_dir=/data/koopark/dynaforge/<job.id>`(`runner_loop.py:265`).

- 운영이 env 를 아직 안 넣었으면 제출이 위 메시지로 실패한다. 개통 확인 때 이 메시지가 보이면 운영 쪽 설정이다.
- env 없이 가려면 `KOORM_STCX_WORK_ROOT=/data/single/<PAT 사용자>/dynaforge` 도 된다(§3 의 사용자 이름).

## 3. 알림 — 제출·조회에 PAT 신원이 붙는다

| 도구 | 바뀐 점 |
|---|---|
| `fullangle_drop_simulation` (드라이런 포함) | `Authorization` 이 `/api/me` 에서 사용자로 풀려야 한다. 없으면 `요청에 PAT … 가 없다` |
| `job_status` · `get_job_details` (모든 job_*) | 그 사용자의 잡만 — registry 행의 잡 폴더가 `/data/single/<사용자>/` 안이어야 한다(`job_helpers.is_owner`·`resolve_job`) |

DynaForge 는 게이트웨이 PAT 하나(`KOORM_GATEWAY_PAT`)로 제출하고 조회하므로 **같은 사용자**로 맞물린다.
제출한 잡의 registry 행은 `/data/single/<그 사용자>/<정규화된 project_name>_<slurm id>` 로 기록된다(`job_helpers.backend_result_dir`).

⚠ 그 PAT 뒤의 사용자가 바뀌면(예: stcx 가 SSO 를 켜서 `admin` → 실제 사용자) **이미 낸 잡이 안 보이게 된다**.
진행 중인 잡이 있을 때 바꾸지 말 것. 같은 이유로 업로드(§1)도 지금은 인증 헤더 없이 가는데, SSO 가 켜지면
업로드에도 같은 PAT 를 실어야 업로드 사용자와 MCP 호출자가 같아진다.

## 4. 우리 결함 — 고침 (`b1274d04`)

**무엇이었나** — 제출 응답의 `work_dir`·`output_dir`·`sphere_report_path` 는 **스테이징 폴더**
(`/data/koopark/dynaforge/<job.id>`)를 가리켰고, registry 에는 backend 결과 폴더가 기록됐다. 그래서
DynaForge 의 복구(`runner_loop.py:355`, 제출 응답이 끊기면 `job_status(work_dir=<스테이징>)` 로 찾기)가 **늘
"Job not found"** 였고, 잡은 stcx 에서 돌고 있는데 DynaForge 에서는 실패로 남았다(재제출은 안 하니 이중 실행은 없었다).
고치면서 같은 자리의 결함 둘을 더 찾았다.

- registry 경로를 잡 이름 그대로 만들었다 — `project_name` 에 한글·공백이 있으면 backend 가 두 번 정규화한
  RESULT_DIR(`job_submit_api.py:1115`·`:1269`)과 달랐다.
- `runner_config_path` 를 `<결과>/output/runner_config.json` 으로 적었는데 템플릿은 결과 폴더 **최상위**에 쓴다
  (dev 실측) — `job_status` 가 KooChainRun 진행 상황을 조용히 빠뜨렸다.

**지금** — fullangle·single 1.1.2 응답(인자 스키마는 그대로)

| 칸 | 값 |
|---|---|
| `work_dir` | 준 값 그대로(스테이징). **`job_status(work_dir=…)` 로 찾힌다** — registry 에 `extra.staging_dir` 로 적는다 |
| `result_dir` (새 칸) | 실제 결과 폴더 `/data/single/<사용자>/<정규화된 project_name>_<slurm id>` = registry `work_dir` |
| `output_dir` · `sphere_report_path` | `result_dir/output`·`result_dir/output/sphere_report.html` (예전엔 스테이징 쪽) |

DynaForge 는 `output_dir`·`sphere_report_path` 를 `external_ref` 에 기록만 하므로(`runner_loop.py:381-382`) 바꿀 코드는
없다. `result_dir` 을 `external_ref` 에 같이 남겨 두면 나중에 결과를 가져올 때 기준이 된다(선택).
복구 조회는 소유 검사를 그대로 지난다 — 같은 게이트웨이 PAT 로 부르면 찾히고 다른 사용자에게는 거절된다.

## 5. 우리 제안 — ★B·★C → 반영함 (`bffd4e50`, 사용자 결정 2026-10-15)

응답에 칸만 더했다. 기존 칸은 그대로라 DynaForge 코드가 깨지지 않는다.

- **★C** — `job_status` 응답 최상위에 `slurm_job_ids`(문자열 목록)와 `sphere_job_id`(없으면 `null`).
  squeue 결과가 비어도(끝났거나 조회 실패) 무엇을 물었는지 남으므로, 종료 판정에 `get_job_details` 를 따로
  부르지 않아도 된다(같이 불러도 된다).
- **★B** — fullangle·single 1.1.2 응답(드라이런 포함)에 `model_source` — `"copied"` 면 `model_file_path` 에서
  복사했고, `"existing"` 이면 작업 폴더에 이미 있던 모델을 그대로 써서 `model_file_path` 를 읽지 않았다
  (묵은 덱 신호). DynaForge 는 잡마다 `work_dir` 이 고유하므로 늘 `"copied"` 여야 한다 — `"existing"` 이 오면
  경고로 남길 것을 권한다.

`result_dir` 을 `external_ref` 에 남기는 것은 **남기기로 했다**(사용자 결정 2026-10-15).

## 6. 알림

- **버전** — `fullangle_drop_simulation` latest 는 1.1.2(인자 스키마 1.1.1 과 같다). 옛 버전(1.0.0·1.1.0·1.1.1)을
  `version` 으로 고정해 부르면 1.1.2 가 돈다. DynaForge 는 고정하지 않으니 영향 없다.
- **도구 목록** — 직접 노출이 둘 늘었다(`tool_result`·`smarttwin_capabilities`). 게이트웨이 별칭 목록이 바뀔 수 있다.
- **SSO 꺼짐 환경** — `/api/me` 가 아무 토큰(토큰이 없어도)에 `admin` 을 돌려준다(이 서버 dev 에서 실측).
  그런 환경에서는 사용자 간 격리가 의미가 없고, 경로 허용 루트만 실제로 범위를 좁힌다.
- 회신 문서(운영용)는 `SmartTwinCluster: dashboard/smarttwin_mcp/deploy/STCX_DYNAFORGE_REPLY.md`.

## 7. 추가 (2026-10-14, §1 회신 뒤) — 제출이 성공하면 업로드를 지운다

**왜** — §1 이후 업로드는 `<ULID>_<이름>.k` 로 잡마다 따로 저장되고 덮이지 않으므로 stcx 의
`/shared/uploads/users/<사용자>/data/` 에 **계속 쌓인다.** 그런데 잡은 업로드 원본을 다시 보지 않는다.

- fullangle 도구가 제출 전에 원본을 스테이징 폴더로 복사한다(`stmc_exec.prepare_model_workdir`).
- backend 는 받은 파일을 자기 임시 폴더 `$SHARED_BASE/slurm_uploads/` 에 두고(`job_submit_api.py:151`),
  잡이 시작할 때 그것을 잡의 `input/` 으로 복사한다(`:856-867`).

그래서 큰 덱이면 같은 덱이 stcx 에 적어도 네 벌 남는다(업로드·스테이징·backend 임시·잡 폴더). 그중 업로드는
**DynaForge 만 지울 수 있다**(올린 사람 소유).

**요청** — 제출에서 `registry_id` 를 받으면(응답이든 `recovered_by_work_dir` 복구든) 그 자리에서 업로드를 지운다.

```
DELETE {KOORM_STCX_BACKEND_URL}/api/v2/files/uploads/<upload_id>
→ 200 {"message": "Upload cancelled successfully", "upload_id": "…"}     (없으면 404)
```

- `upload_id` 는 `StcxUploader.upload()` 가 성공 반환에 이미 싣는다. runner_loop 는 지금 `external_ref` 에
  `uploaded_path`·`uploaded_bytes` 만 남기므로, 지우기를 나중으로 미루려면 `upload_id` 도 남길 것.
- 완료된 파일과 청크 폴더를 지우고 상태를 `cancelled` 로 바꾼다(`file_upload_api.py` `cancel_upload`).
  **본인 업로드만** 지울 수 있다(관리자 그룹 `HPC-Admins` 예외). SSO 가 꺼진 지금은 올린 쪽과 지우는 쪽이 같은
  `admin` 이라 맞고, SSO 를 켜면 §3 처럼 업로드·삭제에도 같은 PAT 를 실어야 한다.
- **`registry_id` 를 못 받았으면 지우지 않는다.** 응답만 끊겼을 뿐 서버의 도구가 아직 복사 전일 수 있다.
  그런 업로드는 드물므로 사람이 정리하거나, 오래된 실패 잡의 것을 주기적으로 지운다.
- 지우기가 실패해도 잡에는 영향이 없다 — 경고만 남기고 넘어가면 된다.

나머지 사본(스테이징 `/data/koopark/dynaforge/<job.id>/`, backend 임시, 잡 폴더)은 우리·운영 쪽에서 따로 정리한다.

