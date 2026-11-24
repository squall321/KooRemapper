# 낙하 파이프라인 ⑥ — 귀환 매니페스트의 이미지 출처 받기 (2026-11-24)

체크리스트 `dropline-images-1124.checklist.md` · 맥락 `dropline-images-1124.context-notes.md`. API 셋(a · b · c)은
`dropline-1112.plan.md`(kooremapper-fd 갈래)다 — 이 문서는 그 옆에 덧붙이고 그 문서는 손대지 않는다.

## 0. 요청과 조건
- 포털 hwaxportal-87(11-24 · 사용자 지시) — 귀환 매니페스트에 이미지 출처 `images{}`(노드 · SIF sha256 · VERSION · KooRemapper 판)가 실린다.
  DynaForge 반입이 그 칸을 읽어 리포트의 「관측된 후처리 판」(get_job · find_reports 에 더한 API 셋 옆)에 함께 보이게 준비한다.
- 꼴은 KooSlurm(-35)이 정했다 — 가지 `feat/images-manifest-mcp` 의 `016a6109`(아직 밀지 않았다 · 소스로 읽었다). `version` 은 1 그대로라 받는
  쪽은 모르는 칸을 건너뛰어야 한다 — 지금 `judge` 는 맨 위 칸을 고르지 않는다(소스 확인).
- kooremapper-fd — ⑥ 은 받지도 시작하지도 않았으니 이쪽이 맡는다(11-24).
- 5차 동결 — 가지 `corelink-int` 에서만. main push · Drive 는 hwaxportal-87 의 해제 알림 뒤.

## 1. 받은 꼴(KooSlurm `dashboard/backend_5010/return_manifest.py` 의 `collect_images` · `build`)
- `images.manifest_node` = `{node, pre: {path, present, size, sha256, version, kooremapper_commit}, post: {path, present, size, sha256,
  version}}` — 매니페스트를 쓴 노드(드라이버 노드, C 면 후처리 잡 노드)에 있는 `/opt/apptainers` 의 SIF. SIF 가 없으면 `{path, present: false}`,
  apptainer 가 없으면 판 글자가 null, 수집이 깨지면 `{node, error}`.
- `images.report_node` — 리포트 잡이면 sacct NodeList, 드라이버 · C 가 직접 만들었으면 매니페스트 노드, 그 밖에는 null.
- `images.report_images` — 리포트 노드가 곁에 쓴 `<kind>_report.images.json`(같은 꼴 · 선택 · 64 KB 이하의 아무 사전). 없으면 null.
- 고르는 순서(KooSlurm) — ① `report_images.<kind>` 가 있으면 그것 ② 없고 `report_node == manifest_node.node` 면 `manifest_node` ③ 다르면
  「리포트 노드 출처 없음」.

## 2. 설계
- (가) 원장 — `_digest(manifest, kind)` 가 `images` 를 아는 칸만 골라 싣는다(남이 쓴 글이고 곁 파일은 아무 사전이다). sha256 은 64자 소문자 hex
  만 · `kooremapper_commit` 은 7 ~ 40자 hex 만 · `size` 는 0 이상 정수 · `present` 는 참거짓 · `node` · `version` 은 찍히는 글자 한 줄 80자 ·
  `path` · `error` 는 한 줄 160자 · `report_images` 의 종류 열쇠는 소문자 낱말 넷까지. 꼴이 틀린 값은 null 이다(지어내지 않는다). `images` 가
  없거나 사전이 아니면 칸째 뺀다(모르는 것을 없다고 하지 않는다).
- (가) 관측 — 같은 자리에서 `images_observed` 를 셈한다. `post`(리포트를 만든 노드의 후처리 SIF)는 KooSlurm 의 고르는 순서대로 `{from:
  report_images | manifest_node, node, present, size, sha256, version}` 이고, 고를 것이 없으면 `{from: null, node: report_node, why: "리포트
  노드 출처 없음"}` 이다. `manifest_node_pre` 는 매니페스트를 쓴 노드(드라이버 노드, C 면 후처리 잡 노드)에 그 시각 깔려 있던 전처리 SIF `{node,
  present, size, sha256, version, kooremapper_commit}` 이다(수집이 깨졌으면 `{node, error}`) — **배포 상태**이고 전처리가 실제로 쓴 판의 증거가
  아니다. 전처리는 KooChainRun 의 자식 런 잡들이 여러 노드에서 먼저 돌렸고, 런마다 쓴 판은 런별 provenance.json 이 정본이다(KooSlurm 11-24 —
  맥락 4절). 그래서 `pre` 라 부르지 않는다. 둘 다 잡 원장(`external_ref.manifest`)과 리포트 `reservation.manifest`(report_summary 가 내보낸다)에
  남는다.
- (나) API 셋 옆 — get_job `external.images` 는 `images_observed`(문자열은 같은 `redact`) · system_status `observed_images` 는 `{post: […],
  manifest_node_pre: […]}` — 최근 90일 7-1 반입 리포트의 `images_observed` 에서 서로 다른 `{sha256, version(, kooremapper_commit)}` · 리포트 수
  · 노드 수 · 마지막 시각이다. 칸마다 10줄 · 못 세면 None(`postprocess_versions` 와 같은 기간 · 상한).
- find_reports 항목에는 싣지 않는다 — 목록은 가벼운 칸만 내고, `external_job_key` 로 찾은 리포트를 get_report 로 열면 `reservation.manifest` 에
  다 있다. 목록에도 필요하면 포털이 말한다(알림에 적는다).
- (다) MCP 설명(get_job · report_summary · system_status) · `TOOLS.md` — 같은 커밋. cae00 점검 문서는 운영에 깔린 판을 적으니 올릴 때(동결 해제
  뒤) 고친다.
- 지키는 것 — 덧붙이기만(기존 칸 · 인자 · 판정 그대로) · 이미지 칸은 판정 · `ok` 에 닿지 않는다(KooSlurm 시험 (d) 와 같은 뜻).
- 한 줄 접기 `_one_line` 은 system 라우트와 반입이 같이 쓴다 — 두 번째 소비자가 생겼으니 `app/shared/text.py` 로 옮기고 라우트는 그것을 가져다
  쓴다.

## 3. 시험
- KooSlurm `ImagesProvenanceTest` 의 꼴 넷(a 같은 노드 · b pre 없음 · c 리포트 잡 곁 파일 · d 판정 그대로) + 수집 실패 + 꼴이 틀린 값(긴 글 ·
  줄바꿈 · 대문자 sha · 정수 아닌 size · 이상한 종류 열쇠 · 사전 아님) + `images` 없음.
- get_job `external.images` · system_status `observed_images`(시험 DB) · 기존 dropline 시험 그대로 · 백엔드 전체 · MCP 계약.

## 4. 올리기
- 가지 `corelink-int` 에 커밋 · push. main · Drive 는 5차 동결 해제 알림 뒤.
- 알림 — KooSlurm -35(꼴을 받았고 이렇게 읽는다 — post 순서는 맞고 pre 는 배포 상태라는 답, 맥락 4절) · hwaxportal-87(가지 끝 · 칸 이름 ·
  find_reports 는 뺐다 · pre 칸 이름 바꿈).
