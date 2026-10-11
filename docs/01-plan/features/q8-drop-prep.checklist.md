# Checklist — Q8 전각도 낙하 준비 3종

설계: `q8-drop-prep.plan.md` · 맥락: `q8-drop-prep.context-notes.md`
순서는 **④ → ② → ①**. ③ 은 보류(요청서 합의).

---

## ④ `info` 보강 + `modelmeta` 기준 명시 — 진행 중

**전제 확인(완료)** — 요청서 전제가 반대였다. `info` 의 bbox 는 **이미 요소 사용 절점 기준**이고
`modelmeta` 는 **파트별 bbox 를 이미** 준다. 없는 것은 "둘을 나란히 + 고아 수" 다.

- [x] **A-1 소비자 전수 확인 — 라벨을 바꾸면 깨지는 곳** 
      `platform/backend/app/runner/kfile_inspect.py:22-24` 가 `^Min bound:`·`^Max bound:`·
      `^Size:` 를 **정규식으로 파싱**하고, `tools/regress/test_packed_node.py:51` 도 같다.
      → **세 라벨은 그대로 두고 추가만 한다.**
- [x] **A-2 플랫폼이 쓰는 기준 확인** — `FileMeta.bbox_min/max`(프런트 `ComparePanel`·
      `FilePanel`)는 `info` 에서 온다 = **이미 요소 기준이라 안전**하다. 고칠 필요 없다.
- [x] **A-3 `modelmeta` 안의 이름 충돌 확인** — 한 JSON 안에서 `model.bbox_min`(전체 절점)과
      `parts[].bbox_min`(요소 기준)이 **같은 이름으로 다른 기준**이다. 라벨링이 필요하다.
      (프런트 `ModelMeta` 타입은 `model` 을 선언조차 하지 않아 지금 소비자는 없다.)
- [x] **A-4 `info` 에 기준 라벨 + 전체 절점 bbox + 고아 수**
      · `bbox basis` 는 **항상** 찍는다(한 줄, 그게 핵심 신호다)
      · 전체 절점 bbox·고아 수는 **고아가 있을 때만** 찍는다(정상 덱 출력을 더럽히지 않는다)
      · 어느 축이든 차이가 `0.01 × 최대 요소 범위` 를 넘으면 `[WARN]` + 축과 수치
      · ⚠ 축 범위가 0 인 평면 메시에서 0 으로 나누지 않는다
- [x] **A-5 `modelmeta` 에 기준 명시 + 요소 기준 값 추가** (추가만 — 이름 변경 금지)
      `model.bbox_basis` · `model.bbox_used_min/max` · `model.bbox_used_basis` ·
      `model.orphan_nodes` + `conventions` 한 줄
- [x] **A-6 회귀** `tools/regress/test_orphan_bbox.py` — **25항**, 게시본에서 **12건 실패**
      · 고아 있는 덱: 두 bbox 가 **다르게** 찍히고 고아 수·WARN 이 나온다
      · 고아 없는 덱: 전체 절점 블록·WARN 이 **안** 나온다(거짓 경보 금지)
      · ★`Min bound`·`Max bound`·`Size` 라벨이 **그대로**다(플랫폼 정규식이 계속 맞는다)
      · `modelmeta` 가 두 기준을 다 내고 고아 수가 맞는다
      · **옛 바이너리에서 실패**하는지 확인한다
- [x] **A-7 관문** 도움말 예제 전수 · 패리티 전수 · **덱 바이트 불변**(게시본 대비 44 op 0건) ·
      backend 315 (전수 재확인 진행 중)
- [x] **A-9 ★예정에 없던 것 — 신호가 플랫폼까지 끊겨 있었다**
      `kfile_modelmeta.run_modelmeta` 가 `model` 블록을 통째로 버렸다("카운트는 info 와
      중복" — 그땐 맞았지만 지금은 **고아 수가 info 에 없는 신호**다). 세 자리를 이었다 —
      래퍼 통과 · 프런트 타입 선언(선언이 없으면 조용히 사라진다) · `FilePanel` 이 고아를
      빨간 줄로 표시. 회귀 `backend/tests/test_orphan_node_signal.py` 2항.
      ⚠ 그 회귀가 **게시본 바이너리에서 빨갛다** — 그게 의도다(플랫폼이 구본이면 잡는다).
      compat 빌드로 교체해 통과시켰다(`cd8ab1fb`).
- [x] **A-10 ★`modelmeta` 의 `conventions.bbox` 가 거짓이었다**
      "model.bbox_* 는 같은 기준의 합집합이라 덱의 고립 절점은 들어오지 않는다" 고 적혀
      있었는데 실측으로 들어온다(고아를 x=-40 에 둔 덱에서 `bbox_min.x = -40`). 그 자리를
      고쳤다 — 중복 키를 만들지 않고 기존 문구를 바로잡았다.
- [x] **A-8 문서** 매뉴얼 §11 경고 블록 + 표 항목 4개 · `ops_help` info·modelmeta notes

## ④ 뒤에 알게 된 것 — 게시가 필요하다

- [x] **A-11 ★로컬 바이너리 슬롯은 내구성이 없다** — 10-10 23:41 재부팅으로 `build/linux/bin` 과
      `platform/backend/bin` 이 **게시본 `43084d35` 로 되돌아왔다**(게시 아티팩트 복원).
      `test_orphan_node_signal.py` 가 그것을 잡았다(2항 빨강).
      → **④·② 를 게시해야** 플랫폼에 남는다. 게시는 마무리가 아니라 **그 기능의 일부**다.
- [x] **A-12 게시 완료** — `dist-20261011-124511Z` · 커밋 `4551ba1` · 바이너리 `e9ec35bf`
      (GLIBC_2.35 ✓, 상한 2.35). compat 빌드 → 듀얼 프런트 → cli.sif → publish.
      API·MCP 재시작 뒤 **라이브 스택**에서 `ops=60` · `mcp_tools=54` 확인.
- [x] **A-13 ★덱 op 플랫폼 관문을 남겼다** `platform/mcp_server/deckops_smoke.py` (9항).
      그림 op 은 `figures_smoke.py` 가 지켰지만 **덱을 쓰는 op 은 지키는 것이 없었다** —
      10-02 의 '게시본이 낡아 op 이 하나도 안 돌던' 사고와 10-10 재부팅 되돌림이 같은 자리다.
      바이너리·카탈로그·API·MCP 넷 중 하나만 낡아도 빨개진다. 실측 PASS 9/9.
- [x] **A-14 보고서** `docs/04-report/q8-drop-prep.report.md` — 요청자용(확인 없이 정한 둘과
      **실제 덱 미검증**을 명시).

## ② `cleanup-nodes` — 진행 중 (기본 `mode: report` 로 정함)

> 요청자 확인 없이 진행한 가정 — **기본 `mode` 는 `report`** 다. 지우는 쪽이 기본이면 사고가
> 조용하고, 한 줄로 바꿀 수 있다. 요청자가 `safe` 를 원하면 그 줄만 고친다.

- [x] **B-1a 파싱 보조를 공용 헤더로** — `include/parser/CardFields.h`.
      `ReferenceIntegrity.cpp` 의 익명 네임스페이스에만 있어서 베껴야 했다(7번째 사본이 될
      자리였다). 순수 이동임을 확인했다 — 참조 무결성 관련 회귀 15개 통과 · **덱 바이트 0건**.
      `fieldsFixed(line, fw)` 를 새로 넣었다(⚠ 공백으로 되돌리지 **않는다** — 절점 ID 8자리가
      칸을 꽉 채우면 `split()` 이 2토큰으로 읽어 연결성이 뒤섞인 사고가 요청서 §6 에 있다).

- [x] **B-0 기본 `mode` = `report`** (요청자 확인 없이 진행한 가정 — 한 줄로 바뀐다)
- [x] **B-1 절점 축** — `cleanup-nodes` 안에 키워드별 훑기로 넣었다. `ReferenceIntegrity` 를
      고치지 않았다: 그쪽은 **세트·파트 ID 무결성**을 한 번에 보는 도구이고, 이쪽은 2.32GB 를
      **스트리밍**해야 해서 전제가 다르다. 공유한 것은 `CardFields.h`(칸 읽기)와
      `elementCardSpan`(카드 줄 수)이다 — 사본이 생길 자리는 둘 다 막았다.
- [x] **B-2 keep 키워드 다섯** — 기본값으로 넣었다. ★다만 **목록이 안전을 만들지 않는다**:
      모르는 키워드도 전수 훑어 남기므로, 목록은 **귀속**과 `mode: force` 분기만 바꾼다
      (회귀 J-2 가 '목록을 바꿔도 삭제 수가 같다' 를 못 박는다).
- [x] **B-3 `prune_sets`** — `_LIST` 는 다시 포장, `_COLUMN` 은 줄 제거,
      `_GENERATE`/`_GENERAL`/`_ADD`/`_INTERSECT` 는 **정리하지 않고 전부 남긴다**
      (범위를 끝점만 보면 안쪽이 지워져 세트가 조용히 빈다 — G-1).
- [x] **B-4 리포트 JSON** — `bbox_before`/`bbox_after` 필수(A-8·A-9), `kept_by` ·
      `unknown_keyword_kept` · `sets_pruned` · `verify` · `element_keywords_opaque`.
- [x] **B-5 `mode: safe` = '이해한 것만 지운다'** + `force` 가 그 반대편.
- [x] **B-6 회귀 57항** — 요청서 §6 함정 전부. ★**두 번 일부러 깨서** 판별력을 확인했다:
      고정폭→공백 분해로 바꾸면 `used_by_elements` 8→**0**(C 절 빨강), `*SET_NODE` 를 보통
      키워드로 두면 `deletable` 3→**0**(요청자의 결과, 18항 빨강).
      ⚠ 요청서 실측(118,568 / 71 / 118,529)은 2.32GB 덱이 없어 **재현 못 했다 — 실제 덱 미검증**.
- [x] **B-7 ★예정에 없던 것** — 요소 카드 줄 수 사다리가 `ModelAssembler::ecBuildIndex`
      **안에만** 있었다. `elementCardSpan` 으로 올렸다(순수 이동, 덱 바이트 0건).
- [x] **B-8 등록·문서** — 카탈로그 59 op · `ops_help` · `HelpCatalogData.inc` ·
      CRLF 매트릭스(제외 아님, 보존 45) · `ofstream` 선언 · 매뉴얼 §47 · 예제 폴더.
      커밋 `794d5ed`(공용 판정기) · `7032d6b`(op). 푸시 완료.

## ① `extract-parts` — 완료

- [x] **C-0 요청자 확인 대기였던 것을 결정했다** — `include.sets: referenced` 는 **자른다**
      (빼지 않는다). 빼면 그 세트를 가리키는 접촉·경계 카드가 미정의 참조가 되어 **덱이 안
      돈다**. 자르면 같은 SID 로 유효한 덱이 된다. `sets: none` 으로 전부 뺄 수도 있지만
      그때는 검증이 그 손실을 잡는다. ⚠ 요청자 확인 없이 진행한 결정이다.
- [x] **C-1 `DeckWriter` + 고정폭** — ★줄을 **다시 쓰지 않는다.** 고른 줄을 글자 그대로
      흘리므로 지수 잘림·꼬리 공백 손실이 애초에 없다. `renumber` 만 칸을 제자리에서
      갈아 끼운다(`putField`) — 좌표 글자 바이트 동일(회귀 D-6).
- [x] **C-2 `renumber: false` 기본 · `true` 면 매핑 표** `<output>_renumber_map.json`.
      종류가 다른 요소가 같은 EID 를 쓰면 거절한다(전역 1부터 매기면 분간이 안 된다).
- [x] **C-3 되읽기 검증** — 절점·파트·섹션·재질 **네 축** 미정의 수를 op 이 스스로 찍고
      0 이 아니면 rc≠0. 검증이 장식이 아님을 E-3 이 증명한다(`materials: false` 로 깨면 잡는다).
- [x] **C-4 스트리밍** — 덱 전문을 메모리에 들지 않는다. 블록 하나만 버퍼한다
      (`*PART`·ID 블록·세트). `*NODE`·`*ELEMENT_*` 는 흘린다.
- [x] **C-5 ★예정에 없던 것 — `*INCLUDE` 를 펼친다.** 처음 설계에 없었고, 그대로 뒀으면
      요청자의 덱에서 **요소가 하나도 없는 덱**이 조용히 나왔다(2.32GB 급은 거의 늘
      인클루드로 쪼개져 있다). 인클루드 재귀를 끈 바이너리로 재서 확인했다 — B절 3항 빨강,
      인클루드 안의 파트만 고르면 rc=1. 못 읽는 인클루드는 **거절**한다.
- [x] **C-6 ★모르는 것을 조용히 버리지 않는다** — 줄 수를 모르는 `*ELEMENT_*` 변형이
      **고른 파트의** 요소를 담으면 거절(J-2), 안 고른 파트의 것이면 버리고 수로 적는다(J-3).
      버린 모든 키워드를 `dropped_keywords` 에 센다.
- [x] **C-7 회귀 57항** `tools/regress/test_extract_parts.py` — §6 함정 전부 + 거절 7종.
      ★인클루드 재귀를 끊어 **판별력을 확인**했다.
- [x] **C-8 공용 헤더로 또 하나 막았다** — `parser/DeckScan.h`(덱을 블록으로 걸어가는 규칙).
      ② 안에만 있던 것을 ① 이 전부 필요로 해서 올렸다(순수 이동, 덱 바이트 45변형 0건).
- [x] **C-9 등록·문서** — 카탈로그 60 op · `ops_help` · `.inc` · CRLF 매트릭스(보존 46) ·
      `ofstream` 선언 · 매뉴얼 §48 · 예제 폴더 2덱 2설정.
      MCP 는 `run_operation` 이 카탈로그를 받아 일반 실행하므로 **도구 수는 그대로(54)** 다.

## 요청서 §6 함정 — 되읽기 검증 기준 (①② 공통)

- [x] `*ELEMENT_SOLID` 8칸에서 절점 ID 8자리로 공백 소실 → **미정의 0**
      ②C-1·C-2 · ①I-1~I-3. ★②에서 고정폭을 공백 분해로 바꿔 재서 확인했다:
      `used_by_elements` 8→**0**(쓰이는 절점을 전부 지운다).
- [x] 고정폭 지수 잘림 → **애초에 다시 쓰지 않는다.** ①은 줄을 글자 그대로 흘리고
      `renumber` 도 칸만 제자리에서 갈아 끼운다(좌표 바이트 동일 — ①D-6).
- [x] CRLF → 산출에 **LF 단독 줄 0** (②D-2 · ①G-2 · CRLF 매트릭스 60 op)
- [x] `*SECTION_*_TITLE`·`*SET_*_TITLE` 제목줄 → ②H-1(제목줄을 세어 SID 를 제 줄에서 읽는다;
      못 읽으면 CNRB 전이가 끊긴다) · ①은 `*PART` 제목 쌍을 빈 줄까지 세어 읽는다
- [x] `*SET_PART_LIST` SID 줄 위치 → ①F-2·F-3(자른 뒤 안 고른 PID 가 빠졌다)

## 추가 지시 (2026-10-11, 사용자 선택)

- [x] **D-1 `build/koorm-work` 삭제** — 16G → 0(여유 346G → 361G). worktree 31개를
      `git worktree remove` 로 정식 제거(커밋·브랜치는 남는다. `integ` 의 `3501c6a` 는 이미
      main 조상). git 밖 인수인계 메모 4개(280K)는 유일본이라 `build/koorm-notes/` 로 옮겼다.
- [x] **D-2 보 족 5종을 공용 판정기에** — `auxElementCard`(`ElementCardLayout`).
      ★`ElemFamily` 를 **넓히지 않고 축을 갈랐다** — 넓히면 `ecBuildIndex` 의 `famOf`(`else` 가
      티쉘이다)·`countByPid`, `KFileReader`, `cnrb2spring` 이 조용히 바뀐다.
      덱 바이트 불변 46/46 으로 무영향 확인. 회귀 `extract-parts` L·M 19항 ·
      `cleanup-nodes` L 8항. 회귀가 내 버그를 **두 번** 잡았다(맥락 노트 참조).
- [x] **D-3 `info` 안내 한 줄** — `--strict` 가 **이미** rc=1 을 냈다(앞선 보고를 정정했다).
      기본 rc=0 은 계약이라 두고, 사유가 있을 때만 "스크립트로 거르려면 `--strict`" 를
      한 줄 안내한다. 정상 덱에서는 조용하다. 회귀 `test_strict_gate.py` D절 13항.
