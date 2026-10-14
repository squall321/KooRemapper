# Checklist — stcx 전각도 낙하를 SmartTwinMCP(:5013)로

설계 `stcx-smarttwin.plan.md` · 맥락 `stcx-smarttwin.context-notes.md`
요청서 2026-10-14 koo.park · 운영 헤드노드 실측 기준

## A. 실측·기준 (선행)
- [x] **A-1 요청서 주장 전수 대조** — 8건 전부 사실. 줄번호 `:43`·`:77`·`:187`·`:304` 가
      사본과 정확히 일치해 같은 파일로 본다
- [x] **A-2 청크 필드 이름 실측** — multipart `upload_id`·`chunk_index`(0부터)·파일 `chunk`·
      선택 `checksum`(MD5). 요청서가 "주석만 봤다" 고 한 자리다
- [x] **A-3 `.k` 가 통과하는지 실제로 돌림** — 분류 `data` · 보안검사 `safe`
- [x] **A-4 함정 셋 발견** — ★A 덮어쓰기 · ★B 묵은 덱 · ★C 종료 근거 없음(설계서 §1)

## B. 설정
- [x] **B-1 `config.py` 3개** `stcx_backend_url`·`stcx_work_root`·`stcx_lstc_ip` — 기본값 빈 문자열
- [x] **B-2 꺼짐 규약** 넷 중 하나라도 비면 제출을 **명시적으로 실패**시킨다(조용히 성공 금지)
      → verify: 시험이 네 경우를 각각 빨갛게 만든다

## C. 반입 (`stcx_client.py`)
- [x] **C-1 `StcxUploader`** init → chunk ×N → complete, 5MB 기본 청크
- [x] **C-2 ★`job_id` 를 싣는다** — 안 싣으면 모든 잡이 `/shared/uploads/users/admin/data/`
      한 자리를 공유해 **서로 덮는다**(SSO off → 전원 `admin`)
      → verify: 시험이 init 본문에 `job_id` 가 있는지 본다
- [x] **C-3 `.k` 로 개명** 받는 쪽 패턴이 `^/.+\.k$` 다. `.key`·`.dyn` 은 올릴 때 이름만 바꾼다
      (원본 파일은 안 건드린다)
- [x] **C-4 `*INCLUDE` 거절** 세션 메타 `includes` 가 비지 않으면 **반입 전에** 실패
      → verify: 바깥으로 HTTP 를 한 번도 안 낸다
- [x] **C-5 실패를 예외로 올리지 않는다** `{"ok": False, "error": …}` — 이 파일의 기존 규약
- [x] **C-6 청크 재전송은 안전하다** `complete` 가 인덱스별 파일 존재를 다시 보므로
      카운터가 부풀어도 병합은 맞다(`file_upload_api.py:371-381`). 주석으로 남긴다

## D. 제출
- [x] **D-1 도구 이름** `smarttwinmcp_fullangle_drop_simulation` · `smarttwinmcp_job_status`
      · `smarttwinmcp_get_job_details`. ★`gateway.py:717-742` 를 읽어 **별칭은 충돌과
      무관하게 항상 등록되고 호출 때 `route`→`alias_route` 순으로 풀린다**는 것을 확인했다
      (`:3419`). `/tools-map` 에 안 보이는 것은 목록이 `route` 만 싣기 때문이다.
      ⚠ 라이브 `tools/call` 확인은 PAT 가 있어야 한다 — 서버 쪽 몫으로 남는다
- [x] **D-2 `{"args": {...}}` 한 겹** — 직접 노출 도구의 모양
- [x] **D-3 인자 매핑 12개** 요청서 §2 표 그대로. `work_dir = {WORK_ROOT}/{job.id}`
- [x] **D-4 `extra_scenario_overrides` 를 보내지 않는다** — 리스트 통째 교체라 기본 시나리오가
      지워진다. `build_scenario_overrides` 는 이번 판에서 **호출하지 않는다**
- [x] **D-5 미지원 옵션은 거절** 조용히 버리지 않는다 — 들어오면 이름을 적어 실패
      → verify: 각도 프리셋·육면체·스윕·공차·DR·접촉·연속낙하·`scenario_overrides`
- [x] **D-6 `dry_run: False` 를 명시** 기본값이 바뀌어도 우리 뜻이 남는다

## E. 응답 해석
- [x] **E-1 `parse_submit_json`** 성공 = 바깥 `ok` **그리고** `result.ok` **그리고** `registry_id`
- [x] **E-2 실패 사유 순서** `result.reason` → `error`(검증 실패 모양) → `stderr` 꼬리
- [x] **E-3 `external_ref`** `registry_id`·`job_id`·`work_dir`·`output_dir`·`sphere_report_path`
- [x] **E-4 ★시간 초과에 재제출 금지** — `job_status({"work_dir": …})` 로 먼저 찾는다.
      ★B(묵은 덱) 때문에 이것은 선택이 아니다
      → verify: 시험이 제출 호출 횟수가 **1** 임을 본다

## F. 폴링
- [x] **F-1 `get_job_details` + `job_status` 두 번** — 종료 근거(`slurm_job_ids`)가 `job_status`
      응답에 없다(★C)
- [x] **F-2 판정표** 설계서 §1-★C 표 그대로. 빈 `squeue` 를 무조건 성공으로 접지 않는다
- [x] **F-3 모르면 접지 않는다** 기존 `last_unknown`·`unknown_count` 규약 유지
- [x] **F-4 `registry_id` 로만 지목** `job_status` 의 `job_id` 는 레지스트리 행 id 라 제출 응답의
      `job_id`(slurm)와 **다르다**

## G. 카탈로그·문서
- [x] **G-1 `catalog_data.json`** `stcx_fullangle_drop` 의 params 98개 → 지원 12개만 남기거나
      나머지를 「미지원」으로 표시
- [x] **G-2 설명 고침** 「모델·각도 파일은 전송하지 않는다」가 이제 거짓이다
- [x] **G-3 `GET /api/v1/stcx/options`** 빈 목록 + 사유(부를 곳이 없어졌다)
- [x] **G-4 `stcx_client.py` 머리말** 「파일을 나르지 않는다」를 고친다 — 이제 나른다. 왜
      바뀌었는지(두 `/data` 가 다른 저장소다)를 적는다

## H. 시험
- [x] **H-1 `test_external_submit_poll.py` 손봄** 14항 중 응답 모양에 묶인 것들을 JSON 으로
      (`test_a_dry_run_reply_fails_the_job` 등)
- [x] **H-2 반입 3단계** MockTransport — init·chunk×N·complete 순서와 **제출 인자에 반입 경로가
      실리는가**
- [x] **H-3 JSON 성공/실패 4형태** 성공 · `result.ok=false` · 검증 실패(`error`만) · 스크립트 실패
- [x] **H-4 시간 초과 재제출 0회**
- [x] **H-5 include 덱 거절** — 바깥 호출 0회
- [x] **H-6 미지원 옵션 거절**
- [x] **H-7 폴링 판정표 전수** 5경우
- [x] **H-8 `test_stcx_option_coverage.py`** 옵션을 줄이면 같이 고친다
- [x] **H-9 backend 전체 녹색** `python -m pytest tests/ -q`

## I. 마감
- [x] **I-1 의미 단위 커밋** 설정 · 반입 · 제출/해석 · 폴링 · 카탈로그 · 시험
- [x] **I-2 커밋 즉시 푸시** (재부팅이 개발 트리를 `reset --hard origin/main` 한다)
- [ ] **I-3 확인 사항을 요청자에게** 아래 4건 (답을 기다린다)

## 확인 사항 (요청자)
1. **도구 실명** — 등재 뒤 `tools/list` 의 `smarttwinmcp_*` 실제 이름
2. **★B** `model_file` 을 함께 보내 올린 덱 이름을 살릴까요, 아니면 `MinimumModel.k` 로 둘까요
3. **★C** `get_job_details` 를 같이 부르는 것으로 가도 됩니까(폴링 1회당 호출 2번)
4. **첫 실제 제출의 `job_status` 응답 원문** — 종료 판정을 그것으로 고정합니다

---

## 마감 (2026-10-14)

커밋 `92cb157`(코드·시험) · `aee2056`(카탈로그·옵션) — 둘 다 푸시했다.

**시험 99항 새로 썼다** — `test_stcx_parse.py` 38 · `test_stcx_client.py` 31 ·
`test_external_submit_poll.py` 30. `test_stcx_option_coverage.py` 10.
**backend 전체 389 녹색.**

세 함정에 각각 관문을 달았다.

| 함정 | 관문 |
|---|---|
| ★A 업로드 덮어쓰기 | `test_the_job_id_is_sent_so_two_jobs_do_not_overwrite_each_other` |
| ★B 묵은 덱 | `test_a_timeout_does_not_resubmit_and_recovers_the_registry_id` |
| ★C 종료 근거 없음 | `test_an_empty_squeue_right_after_submit_is_not_done` · `({}, [], "running")` |

그리고 요청서에 없던 것 둘을 더 막았다.

- `*INCLUDE` 를 **덱 전수**로 본다 — `meta["includes"]` 는 앞 8MB 만 본다
  (`test_an_include_deck_is_refused_before_uploading` · `$` 주석 오탐 시험까지)
- 받는 쪽 패턴 `^/.+\.k$` 를 **반입 단계에서** 확인한다(제출 거절을 되짚는 것보다 싸다)

★ 아직 **안 돈 것** — 라이브 제출. PAT·터널·stcx 등재가 서버 쪽에서 끝나야 한다.
그때까지 이 변경은 "시험으로만 녹색" 이다([[kooremapper-green-gates-lie]] 의 교훈 그대로).

## SmartTwinMCP 요청서 반영 (2026-10-14)

`docs/requests/smarttwinmcp-contract-request-2026-10-14.md` — 받는 쪽이 접근 통제를 넣었다(`5aa61b67`).

- [x] §1 업로드 init 에서 `job_id` 를 뺀다 — 1.1.2 가 jobs/ 경로를 "허용 범위 밖" 으로 거절한다
- [x] §1 ★A 는 **이름**으로 가른다 — `upload_name(name, job_id)` → `<job.id>_<이름>.k`
- [x] 관문 — `test_the_job_id_goes_into_the_name_not_the_init_so_the_path_stays_readable` ·
      `test_two_jobs_with_the_same_deck_name_land_on_different_paths`. **backend 전체 491 녹색**
- [x] §2 `KOORM_STCX_WORK_ROOT=/data/koopark/dynaforge` 그대로 — 코드 변경 없음
      (받는 쪽 운영에 `STMC_WORK_ROOTS` 가 들어가야 한다. 안 들어가면 제출이 "허용 범위 밖의 경로다")
- [x] §7 제출이 `registry_id` 를 받으면(응답·`recovered_by_work_dir` 둘 다) 업로드를 지운다
      — `StcxUploader.delete` → `DELETE /api/v2/files/uploads/<upload_id>`. 잡을 **먼저 커밋**하고
      지우며, 실패는 경고뿐. `external_ref.upload_id` 를 남긴다. 시험 6항, **backend 전체 542 녹색**
- [ ] §5 ★B(`model_source`)·★C(`job_status` 에 `slurm_job_ids`) — 받을지 사용자 답 대기
- [ ] §4 `result_dir` 을 `external_ref` 에 남길지 — 사용자 답 대기
- [ ] 라이브 제출 — 여전히 안 돌았다
