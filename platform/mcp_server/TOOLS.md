# KooRemapper MCP 도구 레퍼런스 (22개)

MCP 서버는 streamable-http로 뜨고, 들어온 `Authorization: Bearer kr_...`(PAT)를
백엔드 REST에 그대로 전달해 **그 사용자 권한**으로 동작한다. 모든 도구는 백엔드
응답 봉투 `{success,data,message,errors}`를 벗겨 반환하며, 백엔드 오류 시 **예외를
던져** Claude가 툴 에러(isError)로 인식한다.

연결: `claude mcp add --transport http kooremapper http://<host>:8701/mcp --header "Authorization: Bearer kr_..."`

## 카탈로그 (2)
| 도구 | 인자 | REST | 설명 |
|---|---|---|---|
| `list_operations` | — | GET /operations | 45개 오퍼레이션 요약 목록 |
| `describe_operation` | operation | GET /operations/{op} | 한 op의 인자 JSON Schema·예제·매뉴얼 |

## 세션 (5)
| 도구 | 인자 | REST | 설명 |
|---|---|---|---|
| `list_sessions` | — | GET /sessions | 내 세션(프로젝트) 목록 |
| `create_session` | name, description? | POST /sessions | 새 세션 생성 |
| `get_session` | session_id | GET /sessions/{id} | 세션 상세 + 파일 목록 |
| `update_session` | session_id, name?, description? | PATCH /sessions/{id} | 세션 이름/설명 수정 |
| `delete_session` | session_id | DELETE /sessions/{id} | 세션 + 전체 파일 삭제 |

## 파일 (6)
| 도구 | 인자 | REST | 설명 |
|---|---|---|---|
| `upload_kfile` | session_id, filename, content, base64_encoded? | POST /sessions/{id}/files | 내용(텍스트/base64)으로 업로드 |
| `upload_local_path` | session_id, path, filename? | POST /sessions/{id}/files | 로컬 디스크 파일 업로드(대형 메쉬, 같은 머신) |
| `list_session_files` | session_id | GET /sessions/{id}/files | 파일 목록 + meta(노드/요소/bbox/*INCLUDE) |
| `inspect_file` | session_id, file_id | GET …/files/{id}/inspect | 단일 파일 상세 메타 |
| `delete_file` | session_id, file_id | DELETE …/files/{id} | 파일 1건 삭제 |
| `download_result` | session_id, file_id, as_base64? | GET …/files/{id}/download | 파일 내용 회수(5MB 상한, base64/미리보기) |
| `save_result_to_path` | session_id, file_id, dest_path | GET …/files/{id}/download | 산출물을 로컬 경로로 저장(대형, 같은 머신) |

## 실행 / Job (5)
| 도구 | 인자 | REST | 설명 |
|---|---|---|---|
| `run_operation` | session_id, operation, args | POST /sessions/{id}/jobs | 오퍼레이션 실행(비동기 Job) → job_id |
| `get_job` | job_id, include_logs? | GET /jobs/{id} (+/logs) | Job 상태/exit_code/산출, 옵션으로 로그 |
| `list_session_jobs` | session_id | GET /sessions/{id}/jobs | 세션의 Job 이력 |
| `cancel_job` | job_id | POST /jobs/{id}/cancel | 대기/실행 중 Job 취소 |
| `get_job_outputs` | job_id | GET /jobs/{id}/outputs | Job이 만든 산출 파일 목록 |

## 시스템 / 신원 (4)
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
