# Context Notes — stcx 전각도 낙하를 SmartTwinMCP 로

설계 `stcx-smarttwin.plan.md` · 체크리스트 `stcx-smarttwin.checklist.md`
작업 중 내린 결정과 그 근거를 **계속 덧붙인다**.

---

## 2026-10-14 · 요청서를 먼저 전수 대조했다

요청서가 운영 헤드노드 실측이라고 명시했으므로 dev 상태로 판정하지 않았다. 대신 **줄번호로
동일성을 확인**했다 — `file_upload_api.py` 의 `:43`(50GB)·`:77`(init)·`:187`(chunk)·`:304`
(complete)가 이 박스 사본과 정확히 일치한다. 그래서 이 사본을 읽어 얻은 사실(청크 필드 이름 등)을
운영에도 적용되는 것으로 다룬다.

주장 8건이 **전부 사실**이었다. 특히 "인증 필요 없다" 는 데코레이터가 없다는 뜻이 아니라
`jwt_required` 가 `SSO_ENABLED` 가 꺼졌을 때 `FULL_ACCESS_USER`(admin)로 **통과시킨다**는 뜻이었다
(`jwt_middleware.py:118-120`). 겉으로 `@jwt_required` 가 붙어 있는 것만 보고 "요청서가 틀렸다" 고
말할 뻔했다 — 데코레이터의 **본문**을 읽어야 했다.

## 결정 1 — 반입 코드를 `stcx_client.py` 에 둔다

요청서의 「고칠 곳」 표가 그 파일을 지목했다. 그대로 따른다.

다만 그 파일 머리말이 **「파일을 나르지 않는다」**고 못박고 있다 — 이번 변경이 그 문장을 정면으로
뒤집는다. 그래서 머리말을 고치고 **왜 뒤집혔는지**를 같이 적는다. 이유는 하나다 — cae00 `/data` 와
stcx `/data` 가 **다른 저장소**라 같은 경로를 보지 않는다. 예전 전제("두 쪽이 같은 경로를 본다")가
사실이 아니었다.

머리말의 다른 금지(컨테이너에 ssh·키·클러스터 자격을 들이지 않는다)는 **그대로 살아 있다.**
반입은 HTTP 이고 인증이 없으므로 자격증명이 들어오지 않는다.

## 결정 2 — 업로드 `init` 에 `job_id` 를 싣는다 (요청서에 없음)

요청서 §1 표는 `{filename, file_size}` 만 적었다. 그대로 하면 저장 경로가
`/shared/uploads/users/admin/data/` 하나로 모인다 — SSO 가 꺼져 **모든 사용자가 `admin`** 이기
때문이다(`file_classifier.py:302`). 그리고 `complete` 는 `storage_path/filename` 에 그냥 쓴다
(`:368`). 즉 **같은 이름의 덱을 올린 두 잡이 서로를 덮는다.**

`init` 이 `job_id` 를 선택 필드로 이미 받고, 주면 `/shared/uploads/jobs/{job_id}/data/` 로 갈린다
(`:297-299`). **API 변경 없이** 충돌이 사라지므로 싣는다.

## 결정 3 — `model_file` 은 보내지 않는다 (확인 대기)

`script.sh:46-52` 가 `work_dir/{model_file}` 로 복사하는데 기본값이 `MinimumModel.k` 다. 즉 올린
덱이 그 이름으로 복사된다. 시나리오도 같은 이름을 가리키므로 **동작에는 문제없다.**

요청서가 「보낼 인자 — 이것만」 이라 했으므로 추가하지 않는다. 이름을 살리고 싶으면
`model_file` 을 함께 보내면 된다 — 확인 사항으로 올렸다.

★ 더 중요한 것은 같은 줄의 **`if not os.path.exists(model_target)`** 이다. 그 파일이 이미 있으면
`model_file_path` 를 **조용히 무시**한다. 그래서 요청서 §3 의 "시간 초과에 다시 제출하지 않는다" 는
단순한 중복 방지가 아니라 **묵은 덱으로 도는 것을 막는 규칙**이다. 반드시 지킨다.

## 결정 4 — 폴링에 `get_job_details` 를 추가한다 (요청서에 없음)

요청서 §4 가 정한 잠정 규칙(「`slurm_job_ids` 가 squeue 에서 모두 사라지면 끝」)을 `job_status`
응답만으로는 **구현할 수 없다.** 그 응답에 `slurm_job_ids` 가 없기 때문이다
(`job_status/latest/script.sh:16-22`). 있는 것은 `squeue` 뿐인데, `slurm_queue_for` 는 예외가
나도 `{}` 를 돌려주므로(`job_helpers.py:197-198`) 빈 `{}` 가 세 가지를 뜻한다 — 다 끝났다 ·
아직 큐에 안 올랐다 · squeue 가 실패했다.

빈 것을 무조건 성공으로 접으면 **제출 직후에 바로 성공으로 끝난다.** 그래서 레지스트리 행 전체를
주는 `get_job_details`(`script.sh:84`, `registry.py:38`·`:77`)를 함께 부른다. 둘 다
`expose: direct` 라 게이트웨이로 바로 닿는다. 폴링 1회당 호출이 2번이 되는 것이 대가다 —
확인 사항으로 올렸다.

⚠ 이름 함정 — `job_status` 응답의 `job_id` 는 **레지스트리 행 id**, 제출 응답의 `job_id` 는
**slurm job id** 다. 같은 키 이름이 다른 것을 가리킨다. 지목은 `registry_id` 로만 한다.

## 관찰 — 받는 쪽이 `additionalProperties: False` 라 다행이다

모르는 인자를 보내면 **거절**된다(`server.py:223-225` 가 호출 전에 검증한다). 조용히 버려지는
모양이 아니다. 그래서 인자 매핑이 틀리면 몇 시간 뒤가 아니라 **제출 즉시** 안다.

이것은 예전 `scenario_overrides` 경로와 정반대다 — 그쪽은 모르는 키를 그냥 병합해 두고 지나가서
"화면에서 고른 값이 아무 영향을 안 주는데 잡은 성공" 하는 자리였다(`stcx_client.py:128-133` 주석).
이번 판에서 `extra_scenario_overrides` 를 안 쓰는 이유가 하나 더 있는 셈이다.

---

## 구현 중에 더 알게 된 것 (2026-10-14)

### 게이트웨이 별칭은 **호출 전용**이다 — 목록에 없어도 있는 이름이다

`/tools-map` 을 재서 `smarttwinmcp_fullangle_drop_simulation` 이 **안 보였다.** 요청서의
도구 이름이 틀렸나 싶었는데, 게이트웨이 코드를 읽으니 아니었다(`gateway.py:717-742`) —

- `alias_route[f"{키에서 하이픈 뺀 것}_{도구이름}"]` 은 **충돌과 무관하게 항상** 등록된다
- `exposed_tools`/`route` 는 이름이 **유일할 때만 맨이름**, 겹치면 접두사
- `tools/call` 은 `route.get(name) or alias_route.get(name)` 로 푼다(`:3419`)
- `/tools-map`·`tools/list` 는 **`route` 만** 싣는다

그래서 `fullangle_drop_simulation`(맨이름)과 `smarttwinmcp_job_status`(겹쳐서 접두사)가
목록에 보이고 나머지 별칭은 안 보인다. **보이는 것으로 판단하면 틀린다.** 기존 머리말의
조언(별칭을 쓰라)이 맞았고, 거기에 "목록에는 안 보인다" 는 사실을 더 적었다.

### `meta["includes"]` 를 쓰지 않았다 — 앞 8MB 만 본다

`*INCLUDE` 검사에 세션 메타를 쓰려다 `kfile_inspect.py:86` 의 `max_bytes=8_000_000` 을
봤다. 2GB 덱의 뒤쪽 인클루드는 **메타에 안 나온다.** 그 거짓 음성이 곧 반쪽 모델 업로드다.
그래서 덱을 전수 훑는 `_deck_has_include` 를 썼다 — 제출 한 번에 GB 를 나르는 길이므로
훑는 값은 싸다. 청크 경계에서는 **막는 쪽으로** 틀리게 만들었다.

### 카탈로그도 `additionalProperties: False` 였다

`catalog.validate_args` 가 모르는 키를 이미 거절한다. 그래서 params 를 12칸으로 줄이면
미지원 옵션은 **카탈로그가 먼저** 막는다. 내가 넣은 런타임 `extra` 검사는 그 뒤의
**드리프트 관문**이다 — 칸이 다시 생기고 매핑을 잊는 경우를 잡는다. 두 경로를 시험으로
각각 고정했다(`..._by_the_catalog` / `..._by_the_drift_guard`).

### `_SCENARIO_MAP` 을 지우지 않고 **이름으로 파킹**했다

80개 매핑이 §5(다음 판)를 위해 필요하다. 그러나 남겨만 두면 다음 사람이 살아 있는 경로로
착각한다. 그래서 (a) 코드에 날짜와 이유를 박고, (b) 시험에
`PARKED_FOR_NEXT_ROUND` 를 **이름으로** 두었다. 목록이 현실과 어긋나면 빨개진다 —
칸이 다시 열렸는데 목록에 남아 있거나, 매핑이 없어졌는데 목록에 있으면.

이것은 이 리포에서 이미 쓰는 방식이다(`test_report_blocks.py` 의 `EXPECTED_UNREAD`).

### 아직 라이브로 안 돌았다

PAT·터널·stcx 등재가 서버 쪽에서 끝나야 한다. 그때까지 이 변경은 **시험으로만 녹색**이다.
[[kooremapper-green-gates-lie]] 가 말하는 바로 그 상태다 — "관문이 초록인 것과 플랫폼에서
도는 것은 다른 사실이다".

### ★A 를 `job_id` 대신 **파일 이름**으로 가른다 (2026-10-14)

받는 쪽(`fullangle_drop_simulation` 1.1.2)이 `model_file_path` 를 호출자 영역 안에서만
읽게 됐다(`stmc_exec.py:76` `DEFAULT_INPUT_ROOTS`, `:204` `check_under`). `job_id` 로 올린
`/shared/uploads/jobs/<id>/` 는 그 안에 없다 — 올린 사람과 묶이지 않은 경로라 받는 쪽이 일부러
열지 않았다(열면 남의 잡 덱을 자기 잡으로 가져갈 수 있다). 양쪽 코드에서 직접 확인했다.

덮어쓰기(★A)는 그대로 남는 문제라 이름에 잡 id(ULID)를 붙였다. 받는 쪽 안(案) 그대로다.
`model_file` 은 보내지 않으므로(기본 `MinimumModel.k`) 업로드 이름이 받는 쪽의
`_NAME_RE`(영문·숫자·`._-`)에 걸릴 일은 없다 — 이름은 `model_file_path` 로만 쓰인다.

남은 함정 — 업로드는 지금 **인증 없이** 간다. SSO 가 꺼져 업로드도 MCP `/api/me` 도 `admin`
이라 맞물리지만, SSO 가 켜지면 업로드 사용자와 PAT 사용자가 갈려 이 경로도 거절된다
(요청서 §3). 그때 업로드에 같은 PAT 를 실어야 한다.

### 제출이 성공하면 업로드를 지운다 — 근거는 `registry_id` (요청서 §7)

§1 이후 업로드는 잡마다 따로 쌓인다. 잡이 그 원본을 다시 읽지 않는다는 것을 받는 쪽 코드에서
직접 확인했다. `script.sh` 는 `prepare_model_workdir` 로 스테이징에 복사한 뒤 `backend_submit` 에
**그 사본(`model_target`)** 을 파일로 보낸다. backend 는 그것을 `slurm_uploads/` 에 두고
잡 스크립트가 거기서 `input/` 으로 `cp` 한다(`job_submit_api.py:151`·`:856-867`). `registry_id` 는
`backend_submit` **뒤에** 생긴다. 그래서 그것을 받았다는 것이 "원본이 더는 필요 없다" 의 근거다.
`recovered_by_work_dir` 도 registry 행이 있어야 찾히므로 같다.

순서는 **커밋 → 지우기** 다. 지우기를 먼저 하면 그것이 걸린 동안 잡의 제출 기록이 DB 에 없다.
그 사이 워커가 죽으면 stcx 에서는 돌고 DynaForge 에는 흔적이 없는 잡이 된다.
삭제 API 는 init·chunk·complete 와 같은 데코레이터(`jwt_required`·`permission_required('dashboard')`)
라 업로드가 되는 신원이면 지우기도 된다. 이미 지운 것을 다시 지워도 200 이다(상태만 `cancelled`).

### §5 반영 — ★C 는 받기만 하고 판정은 안 바꿨다 (2026-10-15)

받는 쪽이 ★B·★C 를 넣었다(SmartTwinCluster `bffd4e50`). `result_dir` 기록은 사용자 결정이다.
이 결정은 pykoocae-53 세션을 거쳐 전해 받았다.

★C 를 쓰면 폴링 한 번에 `get_job_details` 호출 하나를 덜 수 있다. 그래도 지금은 떼지 않았다.
새 칸은 **dev 에만** 반영됐다. 운영이 옛 `job_status` 인 채로 우리가 그 칸에 기대면 id 목록이
비어 보이고, 잡은 `no_slurm_ids_yet` 로 영영 "active" 에 머문다.
같이 불러도 깨지지 않는다고 받는 쪽이 말했으니 두 번 부르는 값이 더 싸다.

복구 경로(`recovered_by_work_dir`)에는 제출 응답이 없으므로 `result_dir` 을 **상태 응답의
`work_dir`** 에서 얻는다. 그 칸은 우리가 준 스테이징이 아니라 registry 의 결과 폴더다(받는 쪽 `b1274d04`
이후). 이름이 같아 헷갈리기 쉬운 자리라 시험 픽스처도 그 값으로 바꿨다.
