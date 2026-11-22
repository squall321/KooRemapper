# DF 2차 ⑥ 맥락 노트 — 핫스팟 묶음 · 덱 세션 관리 나머지

계획 `df-hotspot-session-1122.plan.md` · 체크리스트 `df-hotspot-session-1122.checklist.md`.

## 1. 시작(2026-11-22)
- ⑤ 를 커밋한 뒤 바로 열었다. 요청서 원문(DF-07 · DF-15)은 스크래치에만 있다.
- 핫스팟 군집은 리포트 상세 자료에서 읽는다(`parser.hotspot_clusters` — deep 최상위 레코드 · 전각도 각도마다 압축 꼴). 군집 중심은 결과 틀이다.
  덱 틀 bbox 는 원본 K 파일 메타(modelmeta 의 파트 bbox)에만 있다.
- DF-15 의 11-17 몫(리포트 응답 `environment` · inspect `sha256`)은 올렸다. 세션 응답의 칸과 파트 이름 바꾸기가 남았다.

## 2. 지은 것 · 잰 것(2026-11-22)
- **지은 것** — 마이그레이션 0026(캠페인 `frame_offset` · 세션 `deck_revision_label` · `linked_cad`) · 순수 함수 `campaigns/hotspots.py`(묶기 ·
  기본 반경 · bbox 포함률) · `sessions/part_title.py`(제목 줄 바꾸기 — 1열 규칙 · Card 1 PID 10 · 20 칸 · 콤마 · `*END` 에서 멈춤 · 겹침 거절) ·
  REST — `PUT /campaigns/{id}/frame-offset` · `GET /campaigns/{id}/hotspot-sites` · 세션 응답의 칸 넷 · `PATCH /sessions/{id}` 의 칸 둘 · `PATCH
  /sessions/{id}/parts/{pid}` · MCP 셋(117 → 120) · `get_session` 설명 · capabilities 경로 셋과 표 두 줄 · 글.
- **핫스팟 군집 읽기** — 리포트 서비스의 `hotspots()`(deep 최상위 레코드 · 전각도 각도마다)를 그대로 부른다(같은 계산을 두 번 짓지 않는다). 앱
  시험은 그 함수를 갈아 끼운 합성 군집으로 잰다 — 이 박스의 전각도 표본에는 핫스팟 군집이 없다.
- **잰 것** — 시험 `test_hotspot_session.py` 6 항(순수 셋 · 앱 셋 — 이동값 79.6 · −6.24 의 합성 사례 · bbox 포함률 2 / 3 경고 · 판 경고 · 제목
  바꾸기 바이트 대조 · CRLF) · 선언 · MCP 계약 13 / 13 · 변이 18 / 18(1차 16 — 자리 차례 · 들여 쓴 `*` 제목 두 자리에 사례를 더했다) · scratch
  DB 0026 · 작업 트리 백엔드 1118 통과 · 4 실패(`.env` 없는 supervisor_log).

## 3. 올리기(2026-11-22)
- **올리기** — ⑤ 와 한 판으로 올렸다(⑤ 맥락 노트 3절 — 코드 `4cca82a` · dev DB 0026 · 탐침 14 / 14 · 백엔드 1134).
