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

## ② `cleanup-nodes` — 설계 확정 대기

- [ ] **B-0 ★요청자 확인**: 기본 `mode` (제안: `report`)
- [ ] B-1 `ReferenceIntegrity` 에 **절점 축** 추가 (지금은 세트·파트·섹션·재질 ID 만)
- [ ] B-2 keep 키워드 — 셋은 이미 안다. **둘을 새로**:
      `CONSTRAINED_EXTRA_NODES` · `INITIAL_VELOCITY_NODE`
      (`BOUNDARY_SPC_NODE` 는 `_SET` 변종만 아는지 확인 필요)
- [ ] B-3 `prune_sets` — 삭제 절점을 `*SET_NODE_*` 멤버에서도 뺀다(LS-DYNA `Error 10233`)
- [ ] B-4 리포트 JSON — 요청서 양식 + **`bbox_before`/`bbox_after` 필수**
- [ ] B-5 ★`mode: safe` 의 뜻을 "내가 이해한 것만 지운다" 로 — 모르는 키워드가 절점처럼
      보이는 필드를 가지면 **남기고 `unknown_keyword_kept` 에 적는다**
- [ ] B-6 회귀 — 요청서 분류 재현(CNRB 71 · 세트 3 · 삭제 가능 118,529)은 **덱이 있어야** 한다

## ① `extract-parts` — 설계 확정 대기

- [ ] **C-0 ★요청자 확인**: `include.sets: referenced` 가 `*SET_NODE_*` 를 **잘라낼지 뺄지**
- [ ] C-1 `DeckWriter`(CRLF·스트리밍) + `formatNodeLine`(칸폭) 재사용
- [ ] C-2 `renumber: false` 기본 · `true` 면 **매핑 표**를 함께 낸다
- [ ] C-3 되읽기 검증 — 산출 덱의 **미정의 참조 0** 을 op 이 스스로 찍는다
- [ ] C-4 2.32GB 스트리밍 — 문자열로 모으지 않는다

## 요청서 §6 함정 — 되읽기 검증 기준 (①② 공통)

- [ ] `*ELEMENT_SOLID` 8칸에서 절점 ID 8자리로 공백 소실 → **미정의 0**
- [ ] 고정폭 지수 잘림(`E-09`→`E-0`, 밀도 10억 배) → **쓴 뒤 되읽어 값 보존**
- [ ] CRLF → 산출에 **LF 단독 줄 0**
- [ ] `*SECTION_*_TITLE` 제목줄 → 섹션 수 ↔ 참조 secid 수
- [ ] `*SET_PART_LIST` SID 줄 위치 → 멤버 수 ↔ 기대값
