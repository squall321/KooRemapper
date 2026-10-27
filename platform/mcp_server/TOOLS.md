# KooRemapper MCP 도구 레퍼런스

MCP 서버는 streamable-http로 뜨고, 들어온 `Authorization: Bearer kr_...`(PAT)를
백엔드 REST에 그대로 전달해 **그 사용자 권한**으로 동작한다. 모든 도구는 백엔드
응답 봉투 `{success,data,message,errors}`를 벗겨 반환하며, 백엔드 오류 시 **예외를
던져** Claude가 툴 에러(isError)로 인식한다.

연결: `claude mcp add --transport http kooremapper http://<host>:8701/mcp --header "Authorization: Bearer kr_..."`

## 카탈로그
| 도구 | 인자 | REST | 설명 |
|---|---|---|---|
| `list_operations` | — | GET /operations | 전체 오퍼레이션 요약 목록 |
| `describe_operation` | operation | GET /operations/{op} | 한 op의 인자 JSON Schema·예제·매뉴얼 |

## 세션
| 도구 | 인자 | REST | 설명 |
|---|---|---|---|
| `list_sessions` | — | GET /sessions | 내 세션(프로젝트) 목록 |
| `create_session` | name, description? | POST /sessions | 새 세션 생성 |
| `get_session` | session_id | GET /sessions/{id} | 세션 상세 + 파일 목록 |
| `update_session` | session_id, name?, description? | PATCH /sessions/{id} | 세션 이름/설명 수정 |
| `delete_session` | session_id | DELETE /sessions/{id} | 세션 + 전체 파일 삭제 |

## 파일
| 도구 | 인자 | REST | 설명 |
|---|---|---|---|
| `upload_kfile` | session_id, filename, content, base64_encoded? | POST /sessions/{id}/files | 내용(텍스트/base64)으로 업로드 |
| `upload_local_path` | session_id, path, filename? | POST /sessions/{id}/files | 로컬 디스크 파일 업로드(대형 메쉬, 같은 머신) |
| `list_session_files` | session_id | GET /sessions/{id}/files | 파일 목록 + meta(노드/요소/bbox/*INCLUDE) |
| `session_includes` | session_id | GET /sessions/{id}/includes | 참조된 *INCLUDE 가 세션에 다 있나 — **op 전에 확인**(빠지면 산출물이 LS-DYNA 에서 깨진다) |
| `inspect_file` | session_id, file_id | GET …/files/{id}/inspect | 단일 파일 상세 메타 |
| `delete_file` | session_id, file_id | DELETE …/files/{id} | 파일 1건 삭제 |
| `download_result` | session_id, file_id, as_base64? | GET …/files/{id}/download | 파일 내용 회수(5MB 상한, base64/미리보기) |
| `save_result_to_path` | session_id, file_id, dest_path | GET …/files/{id}/download | 산출물을 로컬 경로로 저장(대형, 같은 머신) |

## 실행 / Job
| 도구 | 인자 | REST | 설명 |
|---|---|---|---|
| `run_operation` | session_id, operation, args | POST /sessions/{id}/jobs | 오퍼레이션 실행(비동기 Job) → job_id |
| `get_job` | job_id, include_logs? | GET /jobs/{id} (+/logs) | Job 상태/exit_code/산출, 옵션으로 로그 |
| `list_session_jobs` | session_id | GET /sessions/{id}/jobs | 세션의 Job 이력 |
| `cancel_job` | job_id | POST /jobs/{id}/cancel | 대기/실행 중 Job 취소 |
| `get_job_outputs` | job_id | GET /jobs/{id}/outputs | Job이 만든 산출 파일 목록 |
| `mesh_section_figure` | session_id, file_id, axis?, at?, compare_file_id?, mode?, isotropic?, width?, height? | POST /sessions/{id}/jobs (section) + 폴링 + 매니페스트 | 격자를 평면으로 잘라 **단면 SVG** 와 그 매니페스트를 한 번에. ⚠ 응답에 픽셀은 없다 — 그림의 요지를 **숫자로** 함께 준다(축과 고른 까닭·맞은 파트 수·ε 비킴·확대 배율·최소피처와 px·파트별 두께와 출처). 다각형은 **돌려주지 않는다**(286k 요소 덱의 단면 JSON 이 455KB 다) |
| `mesh_surface_figure` | session_id, file_id, azimuth?, elevation?, wire?, width?, height? | POST /sessions/{id}/jobs (surfview) + 폴링 + 로그 | 자유면만 뽑아 직교투영·깊이정렬로 그린 **겉모습 SVG**. 매니페스트가 없으므로 요지 숫자는 `report`(콘솔)로 온다 — 자유면 비율·**등진 삼각형 수**·ink_ratio. ⚠ **등축**이다(3D 를 늘이면 모양이 거짓이다) — 층 두께는 `mesh_section_figure`. ⚠ 큰 덱은 SVG 가 5MB 상한을 넘어 `download_result` 가 거절한다(실측 12.2MB) → `svg_bytes`·`download_warning` 을 보고 `save_result_to_path` |
| `mesh_stack_diagram` | session_id, file_id, axis?, force?, width?, height? | POST /sessions/{id}/jobs (stackdiagram) + 폴링 + 로그 | 적층을 **층 모식도 SVG** 로 그리고 **중립축·기하 중심면·굽힘강성을 같은 그림에** 긋는다. 평면을 고를 필요가 없다. ⚠ **감긴 적층은 거절한다** — 솔리드 축 범위가 포개지면 층 순서가 없고, 포갠 것을 층처럼 쌓은 그림은 완전히 그럴듯해 보인다(그때는 `mesh_section_figure`). `*MAT` 이 없으면 층은 그리고 중립축만 생략한다 |

## 전사 코퍼스 (조직 전체 통계)
개별 모델이 아니라 조직이 쌓아온 K파일·잡·리포트 전체를 집계한다(개인 식별 없음).
| 도구 | 인자 | REST | 설명 |
|---|---|---|---|
| `corpus_summary` | — | GET /corpus/summary | 전사 모델 규모 — 세션·파일·잡 수와 메시 규모 분포 |
| `material_usage` | limit? | GET /corpus/materials | 물성 카드별 사용 모델 수 — 어떤 `*MAT_` 가 몇 개 K파일에 실제로 쓰였나 |
| `operation_usage` | — | GET /corpus/operations | 오퍼레이션 실행 이력 집계 — 실제 전처리 관행과 성공률 |
| `section_contact_usage` | limit? | GET /corpus/sections-contacts | `*SECTION_`(요소 정식)·`*CONTACT_` 카드 사용 분포 |
| `report_corpus` | — | GET /corpus/reports | 해석 결과 분포 — 리포트 종류·케이스 수·반복되는 findings |

## 낙하/충격 리포트
SmartTwin 파이프라인이 만든 deep(단건 심층)·sphere(전각도 낙하)·impact(전위치 부분충격) 리포트 HTML 인제스트·분석.
| 도구 | 인자 | REST | 설명 |
|---|---|---|---|
| `ingest_report` | session_id, filename, html_content, kind?, label?, scenario_content?, kfile_id?, project?, dev_rev?, variation?, doe?, focus?, base64_encoded? | POST /sessions/{id}/reports | 리포트 HTML 인제스트(문자열 — 소용량). 대용량은 REST intake |
| `report_upload_instructions` | project?, filename? | (안내 전용) | 로컬 리포트+K파일 업로드용 REST intake 명령(kr_ PAT curl)을 준다 — MCP 로 GB 못 나름 |
| — (REST 전용) | file, kfile?, scenario?, session_id?/session_name?, kind?, project?, … (multipart, .gz 가능) | POST /reports/intake | **원샷 반입** — (세션 생성/지정)+K파일+리포트+scenario 를 한 호출로. 대용량은 여기로 |
| `list_reports` | session_id, kfile_id? | GET /sessions/{id}/reports | 세션의 리포트 목록(kfile_id=그 K에 매달린 것만) |
| `report_facets` | — | GET /reports/facets | 검색 facet — 어떤 kind·과제·rev·방향컨셉·초점·심각도·높이가 있나 + 건수(먼저 '뭐가 있나') |
| `find_reports` | kind?·project?·dev_rev?·variation?·doe?·focus?·doe_strategy?·scenario_type?·drop_height?·severity?·min_worst_stress?·min_worst_g?·has_part?·q?·since/until?·session_id?·kfile_id?·sort·order·limit | GET /reports | 조건으로 리포트 검색(전 세션, 서버 다축 필터). 목표→리포트 특정 |
| `report_query` | report_id, part_id?·category?·angle_name?·near_roll/pitch+angle_tol_deg?(yaw 무시)·metric?·min/max_value?·sort·limit | GET /reports/{id}/query | 리포트 내부 fact 드릴다운(부품×각도×물리량×값, 서버 필터) |
| `report_blocks` | report_id | GET /reports/{id}/blocks | 임베드 블록 **전수** 목록 — 이름·형태·크기·`read_by_parser`(정규화가 아직 해석 안 하는 것도 다 보인다) |
| `report_block` | report_id, name, path?·limit?·max_bytes? | GET /reports/{id}/blocks/{name} | 블록 하나(또는 `a.b.0.c` 하위) — 무엇이든 끝까지 되짚는다. 크면 잘라서 **잘랐다고 말한다** |
| `report_hotspots` | report_id, criterion?·part_id?·top·order·case_key? | GET /reports/{id}/hotspots | ★핫스팟 군집(deep · sphere) — **어디가 뜨거운가**. 중심·반경·요소수·피크시각(deep 은 부피·피크요소까지). sphere 는 각도마다 + `envelope`(파트 × 기준마다 전 각도 최강) · `case_key` 로 한 각도. 정렬은 **절대값** |
| `report_contact_profile` | report_id, metric?(pf·ti·tw)·top·case_key?·axis_top | GET /reports/{id}/contact_profile | ★파트쌍 × 각도(위치) 접촉 스칼라(sphere · impact) — 쌍마다 최대와 그 각도 · 가장 센 각도 상위 · `case_key` 면 그 각도의 엣지(접촉 그래프). **전 각도**가 실린다. None = 접촉 없음(0 이 아니다) |
| `report_behavior_clusters` | report_id | GET /reports/{id}/clusters | 거동 아키타입 군집(impact). `degenerate`(선언≠사용)·`is_mock` 를 숨기지 않는다 |
| `report_analytics` | report_id, block? | GET /reports/{id}/analytics | 큰 분석 블록 요약(doe_analysis·deep_analytics·insights·physics…). 생성기 `summary` **그대로** |
| `report_media` | report_id, case_key?·kind?·role?·images_only? | GET /reports/{id}/media | 결과 이미지·영상 **목록**. `can_llm_view` 가 모델이 볼 수 있는지를 가른다(mp4 는 못 본다) |
| `report_image` | report_id, case_key?·path?·role | (media + 파일 다운로드) | ★결과 이미지를 **그림으로** 돌려준다 — 모델이 실제로 보고 판단한다 |
| `report_compare` | report_id, case_keys[], metrics?·max_images? | (cases + media) | ★케이스 여러 개를 **지표 표 + 이미지**로 한 번에 비교 — 리포트 쓸 때 쓴다. 장수 상한, 넘으면 **뺀 수를 말한다** |
| `report_angle_stats` | report_id, metric?·part_id?·category?/angle_name?/near_lon+near_lat+tol_deg?·top_parts? | GET /reports/{id}/angle-stats | 특정 각도군 표준 통계(분포 n/mean/std/CoV/백분위/IQR/최악 + 부품별 위험·민감도). available_metrics 자동 감지 |
| `update_report_meta` | report_id, label?·project?·dev_rev?·variation?·doe?·focus?·kfile_id? | PATCH /reports/{id} | 과제명·rev·초점·K파일 링크 수동 설정(""=삭제) |
| `attach_report_scenario` | report_id, scenario_content | POST /reports/{id}/scenario | 시뮬 조건 scenario.json 첨부 — 요약 캐시 + K파일 자동매칭 |
| `report_summary` | report_id | GET /reports/{id} | kind·과제메타·scenario·sim_params·parts·findings·전역 최악·검색축 |
| `report_worst_cases` | report_id, metric?, top_n? | GET /reports/{id}/cases | 최악 케이스 랭킹(sphere=방향, impact=위치, deep=단건) |
| `report_part_risk` | report_id, part_id? | GET /reports/{id}/parts | 파트별 최악값·발생 케이스·최소 안전율 |
| `report_case` | report_id, case_key | GET /reports/{id}/cases/{key} | 한 케이스 상세(파트별 메트릭) |
| `report_directional` | report_id, part_id? | GET /reports/{id}/directional | 방향 범주(sphere 면/엣지/코너, impact F1~F6)별 최악 응력·G |
| `report_scatter` | report_id, metric?, part_id? | GET /reports/{id}/scatter | 방향 섭동 산포(sphere) — 26방향별 mean/std/CoV/최악 + 민감도 |
| `report_energy_flow` | report_id, case_key? | GET /reports/{id}/energy | deep=에너지밸런스·접촉력·Newton-3, sphere/impact=하중경로 그래프(엣지 peak_force·total_work·total_impulse). 상세는 **상위 각도에만** — 없는 케이스는 null + 까닭(다른 각도로 안 떨어진다) · `flow_case_key` |
| `report_part_energy` | report_id, part_id? | GET /reports/{id}/part-energy | 파트별 에너지(내부 IE·운동 KE) 시계열(deep matsum, 있을 때) |
| `report_part_series` | report_id, case_key, part_id | GET /reports/{id}/cases/{key}/series | 케이스·파트 시계열(응력/변형률/G/변위, 다운샘플) |
| `report_geometry` | report_id | GET /reports/{id}/geometry | impact 디바이스 외곽선+파트 footprint(XY)+z범위 — 부품 위치 시각화 |
| `report_findings` | report_id, severity? | GET /reports/{id}/findings | 위험 소견(CRITICAL/WARNING/INFO) |
| `compare_reports` | report_ids[], part_id? | (다중 GET) | 리비전/조건 간 파트별 최악값 비교(federate 식) |
| `publish_report_to_datahub` | report_id, project, stage, variation?, doe?, unit?, title? | POST /reports/{id}/publish-datahub | AI Data Hub 에 범용 sim_report 레코드로 등재(eng_meta 연계) |
| `delete_report` | report_id | DELETE /reports/{id} | 리포트 삭제(원본 HTML 포함) |

## 과제 · 개발 개정 (온톨로지)

과제의 정본은 **SP 허브**다 — 여기에 과제를 만들거나 고치는 도구는 **없다**(있으면 다음
받기가 덮어쓰고 그 사실이 고친 사람에게 안 보인다). 쓰는 것은 **우리 것**(개정 · 별칭)뿐이다.
기능이 꺼져 있으면 모든 도구가 **꺼졌다고 사유와 함께** 거절한다(409).

| 도구 | 인자 | REST | 메모 |
| --- | --- | --- | --- |
| `list_tasks` | q?·limit? | GET /ontology/tasks | 허브 과제 목록. `q` 는 key(과제명)·task_code(과제코드)·label 을 본다 · 항목마다 `matched_by`. ★비면 `reason`(「꺼졌다」≠「없다」) |
| `task_revisions` | task_key | GET /ontology/tasks/{k}/revisions | 개정 줄 — `rev_seq` 순, 각 판의 리포트와 앞 판 |
| `compare_task_revisions` | task_key | GET /ontology/tasks/{k}/compare | ★판끼리 **견준다** — 최악응력·최악G·심각도·케이스와 **앞 판 대비 변화**. 안 잰 것은 `null` 이고 0 이 아니다 |
| `report_revision` | report_id, task_key? | GET /reports/{id}/revision | 이어진 개정 + **어긋남** + 후보와 근거. `mismatch` 가 있으면 수동 메타와 다르다는 뜻이다 |
| `set_report_revision` | report_id, task_key, code, model_key?·supersedes?·note? | PUT /reports/{id}/revision | ★사람의 확정으로 기록된다(재인제스트에 안 지워진다) — **짐작으로 부르지 마라** |
| `unlink_report_revision` | report_id | DELETE /reports/{id}/revision | 연결을 끊는다. **개정 객체는 남는다**(다른 리포트가 달려 있거나 줄의 가운데일 수 있다) |
| `confirm_task_alias` | alias, task_key, note? | POST /ontology/aliases | 자유 문자열을 정본 과제에 붙인다(관리자). 한 문자열은 **한 과제만** 가리킨다 |
| `remove_task_alias` | alias | DELETE /ontology/aliases | 별칭을 뗀다(관리자). **이미 이어 둔 개정은 안 건드린다** |
| `plan_task_links` | limit? | GET /ontology/task-links | 과거 붙이기 **계획**(관리자) — 아무것도 쓰지 않는다. 붙는 것·후보·못 붙인 것을 가른다 |
| `ontology_sync_state` | — | GET /ontology/sync | 허브 수신 상태(읽기는 로그인한 사용자 누구나 — KR-17). `stopped` 는 **공개 안 된 타입**이라 멈춘 것 |

## 레시피 — 빌드 없이 쌓이는 분석 함수

C++·백엔드에 박아 **빌드·배포**하는 대신, 분석 함수 하나를 격리 샌드박스에서 돌리고 효과가
있으면 등록해 쌓는다. ★규칙 둘 — 새 분석 코드를 쓰기 전에 `recipe_search` 로 먼저 보고,
즉석 분석이 효과를 봤으면 `recipe_propose` 로 올린다.

| 도구 | 인자 | REST | 메모 |
| --- | --- | --- | --- |
| `recipe_search` | q?·kind?·tag?·limit? | GET /recipes | ★**먼저** 여기. 등록된(내 초안·후보 포함) 레시피를 '쓸모' 순으로 |
| `recipe_get` | name | GET /recipes/{name} | 판 목록·상태·메타·관문·코드 |
| `recipe_run` | name, session_id, report_ids, params?·version?·wait_sec? | POST /recipes/{name}/run | 실데이터로 돌려 **결과까지** 기다린다(샌드박스·플랫폼 잡). 큰 결과는 산출 파일로 |
| `recipe_propose` | name, code, meta? | POST /recipes/propose | `run(reports,params)`+`test_*`. 정적 검사→자기 시험→후보. 허용 import 는 stdlib 일부·numpy·scipy·recipe_kit 뿐 |
| `recipe_evaluate` | run_id, useful, note | POST /recipes/runs/{id}/evaluate | useful=true+글(20자↑)이 등록 근거 |
| `recipe_register` | name, version? | POST /recipes/{name}/register | 자동 관문 통과 시 등록+파일 내보내기(커밋·푸시는 사람이) |
| `recipe_deprecate` | name, reason | POST /recipes/{name}/deprecate | 내린다(올린 사람·관리자). 판 기록은 남는다 |

## 시스템 / 신원
| 도구 | 인자 | REST | 설명 |
|---|---|---|---|
| `whoami` | — | GET /me | 현재 토큰의 사용자 정보 |
| `system_status` | — | GET /system/status | 플랫폼 헬스(api/db/worker/gmsh/op수) |
| `system_capabilities` | — | GET /system/capabilities | 기능 카탈로그 + 웹/MCP 패리티 + 연결 힌트 |

> 표준 워크플로: `create_session` → `upload_*` → `describe_operation` → `run_operation`
> → `get_job` 폴링 → `get_job_outputs`/`download_result`(또는 `save_result_to_path`).

## MCP에서 제외 — 보안상 웹 전용
아래는 **의도적으로 MCP에 없다**(발급된 PAT로만 동작하는 설계):
- 로그인 / 회원가입 / `/auth/config`
- 비밀번호 변경 (`/me/password`)
- **PAT 발급·조회·폐기** (`/me/tokens`) — 토큰은 웹 대시보드에서 발급
- **관리자 사용자 관리** (`/admin/*`)

## 검증
- `mcp_server/smoke.py` — 도구 노출 수 + 전체 op 파이프라인 + 에러 전파를 러닝 스택에 대고
  확인(스택 없으면 자동 skip). 기대 도구 수는 하드코딩하지 않고 `server.py` 의 `@mcp.tool(`
  수에서 뽑는다 — 위 표의 도구 수(현재 72개)와 같아야 한다.
- `mcp_server/figures_smoke.py` · `mcp_server/deckops_smoke.py` — 그림 도구와 **덱을 쓰는 op**(새 op 은 `CASES` 에
  한 줄 더한다)을 살아 있는 스택에서 끝까지 부른다. 게시 바이너리·API·MCP 가 하나라도 낡으면 빨개진다.
- `backend/tests/test_parity.py` — 광고 카운트(`mcp_tools`)와 실제 `@mcp.tool` 수 일치 강제.
