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

## 낙하/충격 리포트
SmartTwin 파이프라인이 만든 deep(단건 심층)·sphere(전각도 낙하)·impact(전위치 부분충격) 리포트 HTML 인제스트·분석.
| 도구 | 인자 | REST | 설명 |
|---|---|---|---|
| `ingest_report` | session_id, filename, html_content, kind?, label?, base64_encoded? | POST /sessions/{id}/reports | 리포트 HTML 인제스트(kind 자동판별) → report_id |
| `list_reports` | session_id | GET /sessions/{id}/reports | 세션의 리포트 목록 |
| `report_summary` | report_id | GET /reports/{id} | kind·프로젝트·sim_params·parts·findings·전역 최악 롤업 |
| `report_worst_cases` | report_id, metric?, top_n? | GET /reports/{id}/cases | 최악 케이스 랭킹(sphere=방향, impact=위치, deep=단건) |
| `report_part_risk` | report_id, part_id? | GET /reports/{id}/parts | 파트별 최악값·발생 케이스·최소 안전율 |
| `report_case` | report_id, case_key | GET /reports/{id}/cases/{key} | 한 케이스 상세(파트별 메트릭) |
| `report_directional` | report_id, part_id? | GET /reports/{id}/directional | 방향 범주(sphere 면/엣지/코너, impact F1~F6)별 최악 응력·G |
| `report_scatter` | report_id, metric?, part_id? | GET /reports/{id}/scatter | 방향 섭동 산포(sphere) — 26방향별 mean/std/CoV/최악 + 민감도 |
| `report_energy_flow` | report_id, case_key? | GET /reports/{id}/energy | deep=에너지밸런스·접촉력·Newton-3, sphere/impact=하중경로 그래프 |
| `report_part_series` | report_id, case_key, part_id | GET /reports/{id}/cases/{key}/series | 케이스·파트 시계열(응력/변형률/G/변위, 다운샘플) |
| `report_findings` | report_id, severity? | GET /reports/{id}/findings | 위험 소견(CRITICAL/WARNING/INFO) |
| `compare_reports` | report_ids[], part_id? | (다중 GET) | 리비전/조건 간 파트별 최악값 비교(federate 식) |
| `publish_report_to_datahub` | report_id, project, stage, variation?, doe?, unit?, title? | POST /reports/{id}/publish-datahub | AI Data Hub 에 범용 sim_report 레코드로 등재(eng_meta 연계) |
| `delete_report` | report_id | DELETE /reports/{id} | 리포트 삭제(원본 HTML 포함) |

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
- `mcp_server/smoke.py` — 22개 도구 노출 + 전체 op 파이프라인 + 신규 2개(`list_session_jobs`,
  `system_capabilities`) + 에러 전파를 러닝 스택에 대고 확인(스택 없으면 자동 skip).
- `backend/tests/test_parity.py` — 광고 카운트(`mcp_tools`)와 실제 `@mcp.tool` 수 일치 강제.
