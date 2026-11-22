# DF 2차 ⑥ — 핫스팟 묶음(DF-07) · 덱 세션 관리 나머지(DF-15) 계획

DynaForge 개발 요청서 v1.0(11-17)의 DF-07 · DF-15 나머지이고 설계안 `df-request-1117.design.md` 의 ⑥(마지막) 단계다. 체크리스트
`df-hotspot-session-1122.checklist.md` · 맥락 `df-hotspot-session-1122.context-notes.md`. 요청서의 검증 사례(T4 재집계 · 모델 이름 · 판 이름)는
옮기지 않는다 — 같은 꼴의 합성 사례로 잰다. 대조는 사용자가 cae00 에서 한다.

## 0. 받은 결정(사용자 11-21 · 11-22)
- 이름표 — 설계안 3절 그대로(11-21 「표 그대로 승인」): MCP `campaign_hotspot_sites` · REST `GET /campaigns/{id}/hotspot-sites`, DF-15 는 새
  도구 · 경로 없이 `get_session` 응답에 칸 · `rename_session_part`(`PATCH /sessions/{id}/parts/{pid}`). 표에 없던 쓰기 길 하나는 7절.
- 차례 · 확인(11-22 「계획한건 전부 만들고, 다 만들면 검증런을 cae00에서 돌릴게」) — 멈춰 확인받지 않고 짓는다. 고른 읽기는 7절에 모아 보고에서
  알린다.

## 1. 짓는 것(MCP 117 → 120 · 마이그레이션 `0026_hotspot_session` 하나)
| 겉 | 이름 | 하는 일 |
|---|---|---|
| 쓰기 | `PUT /campaigns/{id}/frame-offset` · `set_campaign_frame_offset`(새 이름) | 결과 틀 → 덱 틀 이동값 `{dx, dy, dz, source}` 을 캠페인에 둔다(null 이면 지운다) |
| 읽기 | `GET /campaigns/{id}/hotspot-sites` · `campaign_hotspot_sites` | 넣은 런의 핫스팟 군집(파트 · 기준)을 덱 틀로 옮겨 반경 안에서 묶는다 — 자리마다 덱 중심 · 되풀이 각도 수 · 최대 응력 분포 · 대표 각도 · bbox 포함률 |
| 읽기(고침) | `GET /sessions/{id}` · `get_session` | `environment` · `deck_revision_label` · `linked_cad` · 판이 다르면 `revision_warning` |
| 쓰기(고침) | `PATCH /sessions/{id}` | `deck_revision_label` · `linked_cad`(`{project_id, revision}`)를 더 받는다 |
| 쓰기 | `PATCH /sessions/{id}/parts/{pid}` · `rename_session_part` | 세션 덱 파일의 `*PART` 제목 줄 하나를 바꾼다(제자리 · 지문과 메타 갱신) |

## 2. 표(`0026_hotspot_session`)
- `campaigns` 칸 하나 — `frame_offset`(JSONB). `sessions` 칸 둘 — `deck_revision_label`(글 64) · `linked_cad`(JSONB). 모두 null 허용.

## 3. 핫스팟 자리(DF-07)
- 넣는 런은 ⑤ 와 같은 규칙. 런마다 리포트의 핫스팟 군집(`hotspot_clusters` — deep 은 최상위 레코드, 전각도 리포트는 각도마다)을 고른 파트 · 판정
  기준으로 읽는다(기준을 안 주면 그 파트의 기준이 하나일 때만 — 여럿이면 422 로 고르라고 한다).
- 덱 틀 중심 = 결과 틀 중심 + 이동값. 이동값은 인자(dx · dy · dz) → 캠페인의 `frame_offset` → 0(이때 「이동값 없음」 경고).
- 묶기 — 군집을 최대 응력(절댓값)이 큰 것부터 보며 반경(`radius_mm` · 기본 군집 반경의 2 배 가운데값, 그것도 없으면 5 mm) 안의 첫 자리에 넣고
  없으면 새 자리. 자리 중심은 들어온 군집 중심의 평균. 자리마다 되풀이 각도 수(서로 다른 각도) · 최대 응력 분포(각도마다 그 자리의 최댓값) ·
  대표 각도 (최댓값의 각도) · 군집 수.
- bbox 포함률 — 리포트의 원본 K 파일 메타(modelmeta 의 파트 bbox · 덱 틀)가 있으면 옮긴 군집 중심이 그 bbox(허용 1 mm) 안에 드는 비율. 없으면
  null 과 까닭. 99 % 아래면 경고(이동값이 틀렸을 수 있다).
- 합친 파트 — 면적으로 거르지 않으므로 빠지는 파트가 없다. 덱 메타에서 합친 파트를 가릴 칸이 없어 `merged_part` 는 null(모른다)이다.

## 4. 덱 세션 관리(DF-15 나머지)
- 세션 응답(`GET` · `PATCH`)에 `environment`(dev · prod · unknown) · `deck_revision_label` · `linked_cad` · `revision_warning`(둘 다 있고 앞뒤
  공백 · 대소문자를 빼고 다르면 「덱 판 … 과 CAD 판 … 이 다르다」).
- 파트 이름 바꾸기 — 세션의 K 파일(`file_id`) 주 덱에서 `*PART` 블록의 「제목 줄 + PID 가 맞는 Card 1」 을 찾아 제목 줄만 바꾼다(줄 끝 꼴 · 다른
  바이트 그대로). 맞는 자리가 없거나(인클루드 안이면 그렇게 말한다) 둘 이상이면 거절. 새 제목은 70 자까지 · 줄바꿈 없음 · `*` · `$` 로 시작하지
  않음. 파일의 sha256 · 메타의 파트 제목을 고친다. 세션 주인만.

## 5. 시험
- 새 `tests/test_hotspot_session.py` — 순수 함수(묶기 · 이동값 · bbox 포함률) · 앱(받는 꼴 422 · 주인 404 · 합성 캠페인 핫스팟 · 세션 칸 · 판
  경고 · 파트 이름 바꾸기 — 바이트 대조 · CRLF · 쌓인 *PART · 인클루드 안 · 겹침). MCP 계약(117 → 120) · 선언 시험 · 변이.

## 6. 차례
- 마이그레이션 → 모델 → 묶기(순수 함수 `campaigns/hotspots.py`) → 서비스 · REST → 세션 칸 · 파트 이름 → MCP · 글 → 시험 · 변이 → ⑤ 와 한 판으로
  올리기.

## 7. 고른 읽기(묻지 않았다 — 보고에서 알린다)
- 1 — 이동값 쓰기 길 `set_campaign_frame_offset` · `PUT /campaigns/{id}/frame-offset` 은 설계안 표에 없던 이름이다(요청서 데이터 모델의
  `campaign.frame_offset` 을 둘 길이 없었다). 조회 인자로도 준다.
- 2 — 묶음 반경 기본값은 군집 반경 가운데값의 2 배(없으면 5 mm). 자리 중심은 군집 중심의 단순 평균.
- 3 — 합친 파트는 가릴 칸이 없어 `merged_part: null` — 면적 필터를 두지 않아 빠지는 파트는 없다.
- 4 — 판 라벨 · CAD 연결을 쓰는 MCP 도구는 두지 않는다(REST PATCH 만) — 리스크 앱은 읽기만 한다.
- 5 — 파트 이름 바꾸기는 제자리 편집이다(새 파일을 만들지 않는다 — 리포트가 원본 K 파일을 가리킨다).
