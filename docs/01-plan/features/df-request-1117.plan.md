# DynaForge 개발 요청서 v1.0(11-17) — 확인 · 1차 범위

요청서 원문은 사용자가 붙여 넣은 요청서(리포에 두지 않는다 — 미출시 과제 이름 · PC 경로가 들어 있다, 포털이 전한 부탁 11-17) · 체크리스트 `df-request-1117.checklist.md` · 맥락
`df-request-1117.context-notes.md`. 조정 세션 kooremapper-4a 가 2026-11-17 에 소스와 대조했다.

## 사용자 결정(2026-11-17)
- 이번 범위 — 「결함 · 틈 먼저」. DF-14 를 막고 DF-01 의 작은 틈(401 갈래를 가르는 글 · `.env.example` 의 `KOORM_PUBLIC_BASE`)을
  고친다. 나머지 13건은 설계서(개체 · 이름표 · 다른 플랫폼에 기대는 것)를 먼저 써서 확인받는다.
- DF-14 — 「감지 · 경고 · 쓰기 거절」. modelmeta 응답에 겹친 번호 수 · 빠진 파트 수 · 고아 절점 수를 싣고, 덱을 다시 쓰는
  op(map · shellmap 등)은 겹친 덱이면 거절한다. C++ 약 100 ~ 200줄 · compat 빌드와 Drive 게시가 따른다.
- D1 — 해석 결과 원본과 캠페인 조회 함수는 DynaForge 에 둔다(요청서 권고). ReportArchive 는 묶음(DF-13)을 인용한다.
- 이름 — 요청서 제안을 바탕으로 우리 꼴(경로 kebab · 기존 칸과 겹침)에 맞춘 이름표를 설계서에 올려 한 번에 확인받는다.

## 소스 대조(11-17)
| ID | 요청서의 주장 | 소스 | 판정 |
|---|---|---|---|
| DF-01 | intake 폼 칸 | `reports/routes.py:185~201` | 같다 |
| DF-01 | 같은 내용 재적재 건너뜀 없음 | 파일 sha256 은 기록용 · 같은 서명 건너뜀은 7-1 귀환(`services.py:1351~1353`)뿐 | 맞다 |
| DF-01 | 포털 토큰이 `/apps/kooremapper_api/...` 에서 401 | API 는 `Bearer kr_…` 를 같은 인스턴스 DB 와 대조하고, 아니면 우리 JWT 로 읽는다(`shared/auth.py:78~100`). 게이트웨이 매니페스트(HEAXHub 로컬 `118059b`)는 portal_auth 없음 | 401 글로 갈래가 갈린다(아래) |
| DF-01 | `KOORM_PUBLIC_BASE` 빈 값 | MCP 가 프로세스 env 로 읽는다(`mcp_server/server.py:919`) · `.env` 는 `set -a` 로 넘어간다 · `.env.example` 에 그 키가 없다 | 문서 틈 |
| DF-08 | 기본 항복 350 | 안전율 · 항복값은 생성기가 낸 값(`reports/parser.py:202 · 237 · 353 · 472`) | 생성기 몫 · 우리는 싣기만 |
| DF-10 | footprint 합성 | `footprints_are_measured` 는 생성기가 합성한 수가 0 일 때(`parser.py:762`) | 생성기 몫(덱으로 재는 것은 새 기능) |
| DF-06 | `peak_time` 이 초 | 리포트 값 그대로(`parser.py:1135 · 1274`) | 생성기 단위 |
| DF-14 | 겹친 요소 번호로 파트가 조용히 빠진다 | 요소 한 표(`Mesh.h:107`) · 뒤 정의가 덮는다(`Mesh.h:175`) · modelmeta 는 남은 요소로 파트를 센다(`modelmeta.cpp:605~615`) · 쓰기도 잃는다(`KFileWriter.cpp:174~192`) · `info` 만 11-08(`59b6960`)부터 알린다(`core_ops.cpp:1600 · 1712~1728`) | 맞다 — 예전부터 있던 결함 |
| DF-15 | 환경 칸 없음 | `system_status` 에 `env` 는 있다(`system/routes.py:127`) · 세션 · 리포트 응답에는 없다 | 일부 있다 |

401 의 세 갈래(응답 `detail` 글로 가린다) — 「인증 토큰이 필요합니다.」 면 Authorization 헤더가 API 에 닿지 않았다(게이트웨이가 뗐다) ·
「토큰이 유효하지 않거나 취소·만료되었습니다.」 면 kr_ 토큰인데 그 인스턴스 DB 에 없다(예: dev 에서 받은 토큰을 운영에) · 「토큰이 유효하지
않거나 만료되었습니다.」(「취소」 없음 — `auth.py:62~65`)면 kr_ 가 아닌 토큰(포털 자체 토큰)을 우리 JWT 로 읽다 실패했다 · detail 이 없는
401(우리 JSON 꼴이 아니다)이면 게이트웨이가 앞에서 막았다. 운영 게이트웨이에 실제로 깔린 설정은 이 세션이 보지 못했다.

## 1차 — DF-14 감지 · 경고 · 쓰기 거절
- 리더(`KFileReader.cpp` 의 요소 추가 넷 — 솔리드 · 티쉘 629 · 2차 솔리드 266 · 셸 1048 · 1074)가 앞 정의를 덮을 때 잃은 요소를
  파트별로 센다(`Mesh` 의 새 표 — 잃은 정의의 PID → 수). 덮인 요소의 곁표(2차 솔리드 전체 절점 · 두께 셸 번호)도 같이 지운다.
  `Mesh::addElement` 에서 세지 않는다 — op 이 요소를 바꿔 끼울 때도 부른다(리더 밖 13곳).
- modelmeta — `model` 에 덮인 요소 수 · 요소가 하나도 남지 않은 파트 수를 싣는다(이름은 확인받는다). 고아 절점은 있는 칸
  (`orphan_nodes`)이다. 0 이 아니면 콘솔에 경고 한 줄.
- 쓰기 거절 — `KFileWriter::writeFile` · `writeFileWithSource` 맨 앞, 이미 있는 `secondOrderWritable` 곁에 관문 하나. 메시를 새로
  짓는 자리(`MeshRemapper.cpp:332 · 446`, shellmap 결과 메시)는 표를 옮겨 준다. 거절은 op 마다 돌려 재본다(`tools/regress`).
- 플랫폼 — `runner/kfile_modelmeta.py` 가 새 칸을 통과시킨다 · 콘솔 파일 패널이 고아 절점 경고 곁에 보인다.
- 덮지 않는 것 — 족마다 번호를 따로 두는 읽기(선택지 「족마다 번호 따로」 — 고르지 않음) · 셸 번호를 바꾼 사본(고르지 않음) ·
  contact detect · surfview · dynain 쓰기의 경고(결정 문장 밖 — 끝 보고에 올린다).

## 1차 — DF-01 의 틈
- `.env.example` 에 `KOORM_PUBLIC_BASE=` 와 뜻 한 줄.
- MCP `upload_instructions` 의 대용량 칸 곁에 401 의 세 갈래를 가르는 글.

## 1차 — 포털이 옮긴 결정 문서 · 리스크 앱 요청에서 더한 것(사용자 결정 11-17)
- D4 적재 공식 답 — `/system/capabilities` 에 `intake` 묶음(`method` · `path` · `public_url` · `mcp_url` · `token` ·
  `portal_auth_required` · `max_upload_mb` · `max_report_mb` · `batch`). `public_url` 은 `KOORM_PUBLIC_BASE` 로 짓고 비면 null.
- D5 environment — 리포트 응답(`ReportRead` · `ReportListItem` 계산 칸)과 원샷 intake 응답에 `environment`(dev · prod · unknown).
- RK-06 — inspect 응답에 파일 행의 `sha256`.
- DF-14 칸 이름 확인 — 「낱칸 — 우리 꼴」(`element_id_collisions` · `parts_missing`).

## 2차 — 나머지 13건 설계서
- 캠페인 개체 · 런 칸(출처 · 유효성 · 추출) · 캠페인 집계 도구의 이름표를 요청서 제안 바탕으로 쓰고 확인받는다.
- 다른 플랫폼에 기대는 것 — KooChainRun KC-01 · KC-02 · KC-05(이 박스에 리포 없음 — 꼴을 못 봤다) · MatNexus MN-01 · ReportArchive
  RA-02.
