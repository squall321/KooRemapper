# 체크리스트 — 10-16 마무리

- [x] C++ 문구·주석 — `section` 안내 · `info` 「읽지 못해」 · 그림 셋이 요소가 없을 때 리더의 닫힘 안내를 찍는다 · stackdiagram `*MAT` 힌트 · 주석 넷 · 도움말(그림 셋 · 재결속 v2) → 빌드 · 관련 회귀 6파일 FAIL 0 · 전체 회귀 97/97 · 단위 rc 0 · 도움말 ALL PASS
- [x] 카탈로그 — rebind(바꾸는 칸 · 재검사) · 그림 셋 `model` · stackdiagram `*MAT` · modelmeta(닫힘 · 2차 null) · info(닫힘 · 참조 · 2차) · hfdamp(닫힘 · 실측 rc 255) · ale(인클루드 한계 · 실측 rc 1) · id_floor(`check` 값) → 패리티 ALL PASS · 백엔드 562
- [x] ★(점검 중 발견) gmsh 게이트가 meshfix `preview: true` 도 막았다 — gmsh 가 없는 서버에서 「gmsh 없이」 약속이 깨진다 → 예외 한 줄 · 시험(돌연변이 FAIL 확인)
- [x] `server.py` 도구 설명 — 업로드(★인클루드를 먼저 — 실측: 마스터를 먼저 올리면 meta 절점 0 으로 남는다) · `session_includes`(고쳐 쓰는 op 만 주 덱 · 넘김값은 REST 만) · `get_job`(`warnings` — 절점 참조도 실린다, 실측) → 백엔드 562 · 패리티
- [x] 백엔드 주석·API 설명 — `sessions/routes.py` · `jobs/routes.py`(422 문구에 「REST 전용」) · `jobs/schemas.py`
- [x] SKILL.md — 조각 넣기 흐름 · 재결속 · 멈추는 자리(meshfix · hfdamp · ale) · 인클루드 순서 · 2차 null · `warnings` · 모르는 키 422 · 자주 쓰는 op
- [x] TOOLS.md — 도구 수 54 → 72 · 검증에 그림·덱 op 스모크 · 패리티 ALL PASS
- [x] 매뉴얼(§50 재결속 두 줄 · §45.4 `*MAT` 닫힘 덧말 · §35 ale 인클루드 마스터 소절) · platform README(op 수 · meshfix preview)
- [x] API · MCP 재기동(API 는 stop 만 — 감독자가 띄움) → 살아 있는 MCP 가 고친 설명을 낸다 **11/11**(`describe_operation` 8 · 도구 설명 3)
- [x] 보고서 `docs/04-report/deck-contract-1016.report.md` — 다시 잰 수치와 커밋 기록 수치를 갈라 적었다 · 결함 수를 다시 세어 31 → 34 로 고쳤다
- [x] 관문 — 회귀 97/97 · 단위 104 · 도움말 ALL PASS · 백엔드 562 · 패리티 ALL PASS · smoke PASS · 그림 20/20 · 덱 op 21/21

## 2차 — 사용자 「그것도 다 갱신해야하고 업데이트 되었으면 당연히 빌드도 다 해야한다」
- [x] pyKooCAE 매뉴얼 `docs/manual/04_KooRemapper` — 새 항목 15 · info 다시 씀 · 기존 18개에 「2026-10 정본 대조」 · README(63 op · 색인 · REMAP 판정 표) · 곁 문서 넷 · COVERAGE §8 → pyKooCAE `6879624`(63/63 op 항목 · 낡은 말 0)
      → 쓰다 찾아 고친 것 — applyfold·stackwrap `.k.k`(`7a13f72`) · 모르는 키 말없음 셋(`888f578`) · 재결속 도움말 v1 요약 · section 카탈로그 겹친 구절(`e0e2b3f`) · info 사용법 `[--strict]`(`36ded26`) · offset 카탈로그 「TSHELL NO czm」(`d8ed0d9`) · 매뉴얼(`110327d`)
- [x] 릴리스 빌드 `e37fdf4f`(888f578 · GLIBC_2.35) → 회귀 97/97 · 단위 104/104 · 도움말 · 패리티 ALL PASS · 백엔드 562 · 42 op 지문 = 게시본 `43aa5d5c` 와 덱 바이트 동일(늘 달라지는 리포트 JSON 둘만)
- [x] 프런트 · `cli.sif` `13d9c3b4` → Drive `dist-20261016-222746Z` → API · MCP 재기동(health `e37fdf4f` 일치) → smoke · 그림 20/20 · 덱 op 21/21 · 설명 11/11 · 새 op 경유
- [x] 스테이징 → SmartTwinPreprocessor.sif 굽기(tar v115 · 메일) → `/opt/apptainers` → 세 사본 바이트 동일 · SIF 안 실행 · 배포 SIF 로 REMAP 배선 재실측
- [x] 장부(2차 배포 칸) · 보고서(2차 절 · 결함 38 · 결정 셋 갱신) · 메모리

## 3차 — 사용자 「다 권장대로 해」(2026-10-17)
- [x] ③ offset 셸 + czm 거절 · 기본 tied 경고(`de2a798`) — 회귀 E 절 셋(옛 바이너리 FAIL 둘) · 카탈로그 · 매뉴얼 · 도움말
- [x] ① 인클루드가 들어오면 가리키는 덱 meta 를 다시 잰다 — 시험(돌연변이 FAIL 확인) · 백엔드 563 · MCP 설명 · SKILL.md
- [x] ② `allow_missing_includes` 는 MCP 에 열지 않는다 — 결정 기록(코드 변경 없음)
- [x] 다시 빌드 `2ddc2e44` → 관문 → `dist-20261017-031631Z` → API · MCP → 스모크 · 업로드 순서 198/198 → 스테이징 → SIF(v116 · 세 사본) → 장부 · 보고서 · 메모리 · pyKooCAE(`0b59d2d`)

## 4차 — 사용자 「다 만들고 배포해서 테스트할거야」(2026-10-17)
- [x] 셸 층 묶기 — `tied`(기본)면 `*SET_SEGMENT` 둘 + `*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET`(restack 셸 계면과 같은 꼴) · both 는 경고 ·
      회귀 E 절(묶음 하나 · slave/master 절점 · sstyp/mstyp) · 단독 offset 경로도 같다 · 산출 `info --strict` OK ·
      커밋된 셸 결과 셋 다시 구움(지운 줄 0 · 묶음 블록만 +1,175) · 그 덱을 읽는 시험 넷 FAIL 0
- [x] 다시 빌드 `1164d8ed` → 관문 → `dist-20261017-035440Z` → API · MCP → 스모크 · 플랫폼 경유 셸 묶음 → 스테이징 → SIF(v117) → 장부 · 보고서 · 메모리 · pyKooCAE(`2680a22`)
