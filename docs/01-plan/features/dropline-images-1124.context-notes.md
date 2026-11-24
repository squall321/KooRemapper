# 낙하 파이프라인 ⑥ 맥락 — 귀환 매니페스트의 이미지 출처 받기

계획 `dropline-images-1124.plan.md` · 체크리스트 `dropline-images-1124.checklist.md`.

## 1. 받음(2026-11-24)
- hwaxportal-87 — 사용자 지시로 ⑥ 을 연다. 꼴은 KooSlurm(-35)이 정한다. 5차 동결 중이라 가지에서만.
- KooSlurm 리포(읽기만)의 `dashboard/backend_5010/return_manifest.py` 에는 아직 이미지 칸이 없다(11-24).
- API 셋은 kooremapper-fd 의 `dropline-1112` 갈래다 — 겹치는지 물었다.
- 꼴이 오기 전에 짓는 것은 꼴에 기대지 않는 (가) 뿐이다 — 칸 이름을 짐작해 집계를 짓지 않는다(지어내지 않는다).

## 2. 꼴 받음 · 맡음(2026-11-24)
- kooremapper-fd — 「⑥ 은 받지도 시작하지도 않았습니다. 그쪽이 맡아 주세요.」 `dropline-1112` 문서는 그쪽 것이라 이 문서에만 적는다.
- KooSlurm -35 이 알린 꼴을 그쪽 가지 `016a6109` 소스로 맞춰 봤다 — 알린 것과 같다. 소스에서 더 본 것 — `report_node` 는 sacct NodeList 라 여러
  노드면 `icn[1-2]` 같은 글이 올 수 있다 · `error` 는 `예외이름: 글` 이라 경로가 들 수 있다 · 곁 파일은 64 KB 이하 아무 사전이라 칸마다 꼴을
  본다.
- pre · post 를 나눠 고른 까닭 — KooSlurm 의 고르는 순서는 「리포트를 만든 노드」 의 이미지를 고르는 것이다. 리포트를 만든 것은 후처리 SIF 다.
  전처리 SIF 는 드라이버 잡에서 돌았으니 매니페스트 노드 것이 관측이다(리포트 노드 곁 파일의 pre 는 리포트와 상관없다). 이 읽기는 KooSlurm 에
  알려 바로잡을 수 있게 한다. → **절반이 틀렸다 — 4절**(「드라이버 잡에서 돌았다」 는 아니다).
- find_reports 를 뺀 까닭 — 목록 항목(`ReportListItem`)은 reservation 을 싣지 않는다. 잡 키로 찾은 뒤 get_report 로 열면 다 보인다. 목록에
  넣으면 칸 하나를 위해 목록 응답 꼴이 바뀐다 — 포털이 바라면 그때 더한다.
- 저장 때 칸마다 꼴을 걸러 두므로 system_status 의 집계는 접은 뒤 합치기가 필요 없다(저장된 값이 이미 한 줄 · hex 다). 그래도 낼 때 한 번 더
  접는다.

## 3. 짓기(2026-11-24)
- 픽스처는 KooSlurm `016a6109` 작성기를 그쪽 시험과 같은 대역(가짜 apptainer · sacct)으로 scratch 에서 돌려 얻었다 — a(드라이버 같은 노드) ·
  b(pre 없음 · 후처리 꺼짐) · c(리포트 잡 곁 파일) · c2(리포트 잡 다른 노드 · 곁 파일 없음). 노드 이름 · SIF 경로만 바꿨다(이 박스 호스트 이름 ·
  scratch 경로 · 그쪽 시험의 노드 이름을 리포에 두지 않는다). 실물에서 본 것 — 후처리가 꺼진 b 는 `ok: true` 인데 리포트가 없다(지금 판정이
  `present` 를 먼저 보는 까닭 그대로).
- 꼴 거르기에서 `re.match` + `$` 는 끝 줄바꿈 앞에서도 맞는다 — sha256 · 커밋 · 종류 열쇠는 `fullmatch` 로 본다(변이로 확인).
- `size` 는 `type(...) is int` — `True` 가 정수로 통과하지 않게.
- get_job `external.images` 는 관측이 있을 때만 칸이 있다 — 기존 시험(`{kind, cluster_state, ontology}` 와 정확히 같음)을 바꾸지 않고, 모르는
  것을 null 로 말하지 않는다. 문자열은 `_redact_deep`(진단 번들과 같은 접기)을 거친다.
- system_status `observed_images` 의 집계는 JSONB 경로를 `substr` 로 앞부분만 가져와 묶는다 — `postprocess_versions` 와 같은 꼴 · 같은 기간 ·
  역할마다 10줄 · 못 세면 None.
- 변이 15 / 15 빨강. 처음 돌린 것은 0 / 14 「살아남음」 이었는데 실행기(`pt.py`)가 pytest 의 rc 를 찍기만 하고 0 으로 끝나서였다 — 찍힌 `rc N`
  을 읽게 고쳤다. 고친 뒤 살아남은 하나(종류 열쇠 거르기)는 이상한 열쇠가 좋은 열쇠 넷 뒤에 있어 상한이 가린 것이었다 — 시험에서 앞으로 옮겼다.
- cae00 점검 문서는 운영에 깔린 판을 적는 문서라 이 판이 올라갈 때(동결 해제 뒤) 고친다 — 지금 고치면 운영에 없는 칸을 점검하라고 하게 된다.

## 4. KooSlurm 답 — pre 는 배포 상태(2026-11-24)
- post 순서 · 곁 파일의 pre 를 버리는 것 · 리포트 노드와 pre 를 묶지 않는 것 · images 가 없을 때 칸째 없음은 맞다.
- 틀린 것 — 「전처리는 드라이버 잡에서 돌았다」. 전처리(Pre SIF 안 KooMeshModifier · KooRemapper)는 KooChainRun 이 띄운 자식 런 잡들이 여러
  노드에서 매니페스트보다 먼저 돌렸다. 드라이버 노드는 KooChainRun prepare · submit 만 하고 그것도 NFS 의 KooChainRun 으로 한다. 그래서
  `manifest_node.pre` 는 매니페스트를 쓴 노드(드라이버 노드, C 면 후처리 잡 노드)에 그 시각 깔려 있던 Pre 판 — 배포 스냅숏이다. 런마다 실제로 쓴
  SIF · 덱은 KC-01 의 런별 provenance.json(pyKooCAE RunProvenance)이 정본이다.
- 그 권고(「Pre(매니페스트 노드 배포 상태)」 로 이름 붙이기)를 받아 관측 칸 이름을 `pre` → `manifest_node_pre` 로 바꿨다 — get_job
  `external.images` · system_status `observed_images` · 원장 `images_observed` 셋. 받은 원본 칸(`images.manifest_node.pre`)은 KooSlurm 이름
  그대로 둔다. 아직 올리지 않은 가지라 바꾸는 값이 싸고, 설명 글만 고치면 날 JSON 을 읽는 쪽은 여전히 `pre` 를 「전처리가 쓴 판」 으로 읽는다.
  MCP 설명 · TOOLS.md · 계획도 같은 커밋에서 쓸었다. 변이 16 / 16.
- 전처리가 실제로 쓴 판(provenance.json)을 읽는 것은 이번 요청 밖이다 — 필요하면 포털 · 사용자가 정한다.
- report_node 압축 목록 — 리포트 잡은 ntasks=1 이라 한 노드다. 글자 그대로 비교로 된다(여러 노드면 「출처 없음」 이 안전한 쪽이라는 답).
- KooSlurm `016a6109` 는 5차 동결로 아직 안 밀었다 — 해제 뒤 알린다고 했다.
