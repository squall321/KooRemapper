# 덱 편집 계약 요청서 — 조용히 틀리는 것을 도구가 막게

**보내는 쪽**: LS-DYNA 낙하해석 캠페인 운영(2026-07~09, T1~T4 · A27 · M1/M3 · TN · ON1/ON4 · Cross_AX-TF)
**받는 쪽**: DynaForge / KooRemapper — k파일 레벨(`platform/core` 오퍼레이션 + `src/parser` 계층)
**작성일**: 2026-09-24
**한 줄**: 덱을 텍스트로 고치는 일에 **계약이 없어서** 3개월간 잃은 계산을, 그 계약을 도구가 강제하는 기능으로 옮긴다.
**성격**: 기능 요청이다. 우선순위와 설계는 이 리포가 정한다 — 아래는 근거와 우리가 먹는 모양이다.

---

## 1. 왜 — 잃은 것의 대부분은 에러가 아니었다

에러가 났으면 그 자리에서 알았다. 실제로 비쌌던 것은 **에러 없이 조용히 틀린 것**이다.

| 사건 | 원인 | 손실 |
|---|---|---|
| A27 요소 소실 | `*ELEMENT_SOLID` 2줄 포맷을 1줄로 읽음 | 솔리드 922만 → 434만. **에러 없이 완주** |
| CRLF 소실 | 텍스트 모드 I/O 가 700MB 덱을 LF 로 변환 | 바이트 −12MB · diff 2,433만 줄. 구조 카운트는 **전부 정상** |
| TN1 hang | `*KEYWORD` 의 `I10=Y LONG=S` 가 왕복에서 소실 | 10칸 데이터를 8칸으로 오독 |
| TN4 전멸 | `*DATABASE_HISTORY_SOLID_SET` 이 없는 set 참조 | Error 10144, 키워드 단계 즉사 |
| RBE3 480런 정지 | CNRB→`*CONSTRAINED_INTERPOLATION` 이 dt 를 303배 붕괴 | 350노드를 하루 넘게 점유. `energy ratio = 1.00000` 이라 **건강해 보였다** |
| 유격 캠페인 무효 | CNRB 21개만 유격화, TIED 225개를 강체로 남김 | 1,464런. 갭 10배에도 변화 0.18% |
| restack 무증상 붕괴 | 층분할 덱을 전처리기가 조용히 망가뜨림 | 485런이 AP 없는 모델로 "정상 완료" |
| 낙하판 66mm 밖 | 더미 노드가 모델 bbox 를 부풀림 | 실패 0건인데 **충돌 자체가 없었다** |
| TIM 압착 부재 | TIM 윗면이 0.15~0.30mm 떠서 하중을 안 받음 | 도포 DOE 400런이 **null 변수**를 측정 |

공통 원인은 하나다. **필드폭·개행·참조 무결성·편집 범위를 매번 사람이 기억해서 맞춘다.**
손으로 짠 스크립트 500여 개가 같은 8줄을 복붙하고 있고, 한 곳만 틀리면 덱이 망가진다.

---

## 2. 지금 있는 것으로 어디까지 되나 — 실측

게이트웨이 `tools/list` 와 소스를 직접 봤다(오퍼레이션 49개 · MCP 도구 50개).
**인접한 것이 많고, 일부는 이미 요청 항목 그 자체다.** 아래는 정직한 판정이다.

### 이미 있는 것 — 요청에서 뺀다

| 요청 항목 | 이미 있는 것 | 비고 |
|---|---|---|
| DF-47 유격 조인트(`split_cnrb_to_freeplay`) | **`cnrb2spring`** — CNRB 체결점을 두 강체 + 유격 discrete beam 으로 분할 | 요청 항목과 같다. 확장만 필요(§3.4) |
| DF-40 두께방향 N분할 | **`refine`**(1:2·1:3), **`restack`**(층별 두께·재질 재분할) | 세트 전파만 결손(§3.3) |
| DF-42 부피·질량 | **`info`**, **`modelmeta`**(파트별 면적·부피·투영) | 충분하다 |
| DF-43~45 재질·전역카드 | **`matdb`**, **`matswap`**, **`optimize`**, **`stabilize`**, **`hfdamp`**, **`database`** | 적용은 된다. 타당성 검사만 결손 |
| DF-50 자세 DOE | **`stcx_fullangle_drop`** — 피보나치 구면 전각도 | 역검증만 결손 |
| DF-53/54 결과 판정·수집 | **`report_*` 20여 개**, `report_worst_cases`, `report_energy_flow`, `compare_reports`, `job_diagnose` | 수집·분석은 강하다 |
| DF-35 압착 기하(일부) | **`squeeze`** — 간섭 압착 + 초기응력/변형 생성 | 갭 측정 기반 목표 클리어런스 입력만 결손 |
| 접촉 조작 | **`contact`** — 분석·생성·수정·변환·제거·자동탐지 | 재료가 충분하다 |

### 부품은 있는데 **계약이 아니다** — 이것이 요청의 핵심

| 요청 | 있는 부품 | 왜 답이 아닌가 |
|---|---|---|
| DF-02 방언 판별 | `ElementCardLayout::optValue("I10")`, `keywordCardDeckWidth`, `deckFieldWidth`, `keywordFieldWidth` | **요소 카드에 국한**된다. `*PART`/`*SET_*`/`*MAT_*`/`*CONTACT_*`/`*CONTROL_*` 은 I10 과 무관하게 항상 10칸인데 그 표가 없다. 그리고 "판별 후 스캔 0건이면 **실패**" 규약이 없어, 오프셋을 틀리면 오염 덱을 CLEAN 으로 오판한다(실측: bbox 세 축이 똑같이 99.000mm 로 떨어지는데 통과했다) |
| DF-03 필드폭 표 | `ElementCardLayout`, `realFieldWidth(intFw)` | 요소용이다. 넘칠 때 **자르지 말고 raise** 하는 규약이 없다 — 7자리 EID `9900061` 이 `99000` 으로 잘려 PID 가 199/299 로 읽힌 적이 있다 |
| DF-04 1줄/2줄 솔리드 | `solidCardLines()`, `solidNodesFromElform()` + `cnrb2spring.cpp:284~344` · `ModelAssembler.cpp:4955` 가 **각자** 처리 | 공용 계층이 아니라 **명령마다 재구현**이다. `(ten nodes format)` 을 **섹션 헤더마다 개별 판정**해야 하는데(T4 덱은 5섹션 중 3개가 2줄) 그 규약과 섹션별 총수 리포트가 공용에 없다 |

### 없는 것

| 없는 것 | 확인 방법 |
|---|---|
| **DF-01 바이트 보존 I/O** | `KFileWriter.cpp:111,229` 가 `std::ofstream out(filename)` — **텍스트 모드**다. 개행 감지·보존 계약이 없고, 편집 0회 round-trip 바이트 동일 단언도 없다 |
| **DF-06 참조 무결성** | `include/validation/` 에 `ElementQualityChecker`·`IntersectionDetector`·`MaterialCardValidator` 뿐 — SET/DATABASE_HISTORY/CONTACT ssid·msid/CNRB NSID/PART→SECID·MID 의 dangling 검사가 없다 |
| **DF-07 ID 발행** | 예약 대역 레지스트리가 없다. `max+1` 은 하위 전처리기 관례 번호와 충돌한다(KMM 낙하판 PID 500323, `sid 9000001` 은 감쇠용으로 이미 점유) |
| **DF-20/21 편집 게이트·범위 단언** | 없다 |
| **DF-25~30 영역·이미지 마스킹 일체** | 없다 |
| **DF-32~34 갭 분포·유효면·결합 분류** | 없다 |
| **DF-46/49 체결 그래프·dt 가드** | 없다 |
| **DF-52 제출 게이트** | 없다 |

---

## 3. 요청

### 3.1 1차 — 기반 계약 (이것만 있어도 위 사건표 절반이 사라진다)

이 계층은 **나머지 전부의 전제**다. 개별 기능보다 이것이 먼저다.

#### DF-01 `deck_open` / `deck_save` — 바이트 보존 I/O **(치명)**
- `path → DeckBuffer{lines[], newline, n_bytes, n_crlf, n_lines, sha256}` / `buffer → file + EditReport{Δbytes, Δlines, Δcrlf, changed_line_ranges}`
- `encoding=latin-1` 고정(`errors='ignore'` 금지) · `newline=auto|force_crlf|force_lf` · 700MB~1GB 덱용 mmap 임계
- **받아들일 조건**: 편집 0회 round-trip 에서 바이트·줄·CRLF 수가 **완전 일치**(assert). 개행 판정은 `count(b"\r\n")*2 > count(b"\n")`.
- **모든 편집의 유일한 I/O 진입점으로 강제할 것.** 지금 `KFileWriter` 가 텍스트 모드인 채로 남으면 나머지 기능이 전부 그 위에 쌓인다.

#### DF-02 `detect_deck_schema` — 방언 판별 **(치명)**
- `DeckBuffer → Schema{id_width(8|10), node_coord_offsets, per_keyword_width_map, keyword_options}`
- **`I10=Y`/`LONG=S` 는 `*NODE`/`*ELEMENT_*` 에만 적용된다.** 나머지는 항상 10칸.
- **판별 후 스캔 결과가 0건이면 성공이 아니라 실패로 raise.**
- 있는 `ElementCardLayout` 을 전 카드로 **넓히는 일**이다. 새로 짜는 것이 아니다.

#### DF-03 `card_layout` — 필드폭 표 (부록 A)
- `(keyword) → Layout{fields[(name,width)], n_title_lines, n_data_lines}`
- **폭을 넘치면 잘라내지 말고 raise.** "공백 1칸 보장" 용 폭 확대(`rjust(max(9,W))`)도 금지 — 고정포맷은 컬럼으로 자른다.

#### DF-04 `iter_solid_elements` — 1줄/2줄을 **공용 계층으로**
- `DeckBuffer+Schema → Element{eid,pid,nodes[],line_index,line_span,section_id}` 스트림 + `SectionStat{format, n_elem}`
- `(ten nodes format)` 을 **섹션 헤더마다 개별 판정**. 섹션별·전체 총수를 **반드시 출력**하고 0이면 "포맷 확인!" 에러.
- `cnrb2spring`·`ModelAssembler` 의 사본을 이것으로 **모으는 일**이 포함된다.

#### DF-05 `iter_cards` — `_TITLE` / `_ID` 추가 줄
- `_TITLE` 은 제목줄 1개. **`_ID` 접미사도 cid+title 카드가 1줄 더** 있다(`*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET_ID`).
- 이걸 놓쳐 TIED 225개를 **0개로 오판**했다. 판정식: `has_id = kw.endswith("_ID") or "_ID_" in kw`

#### DF-06 `check_reference_integrity` — 참조 무결성 **(치명)**
- 대상: `SET_SOLID/NODE/PART/SEGMENT` · `DATABASE_HISTORY_*` · `CONTACT` ssid/msid + sstyp/mstyp 해석 · `CNRB` NSID · `BOUNDARY_SPC` · `DAMPING_PART_SET` · `PART→SECID/MID` · `ELEMENT→PID/NID`
- 미정의 SET 참조가 0건이 아니면 **제출 금지**. 요소 삭제 전/후 dangling **증가량**을 대조.

#### DF-07 `reserve_id_range` — ID 발행
- `max+1` 금지. **외부 예약 대역 등록표를 도구가 보유**할 것. 발행 후 전역 exact-match 재검사 0건.
- 세트 ID 도 같다.

#### DF-08 `element_inventory` / `assert_counts` — 요소 수 원장
- `{pid: {n_elem, n_node, bbox, volume, mass}}` + **원본/템플릿/per-run 3자 대조**
- `info`·`modelmeta` 가 재료다. 필요한 것은 **3자 대조**와 실패 판정이다. 전처리 도구를 거친 덱은 이 한 줄 대조가 유일한 방어선이다.

#### DF-20 `verify_edit` — 편집 게이트 **(모든 편집 함수의 종료 직전 필수)**
① Δbytes 가 의도한 변화량(줄당 필드폭 계산치)과 일치 ② 변경 줄 범위가 의도 범위 안 ③ CRLF 수 보존
④ 키워드별 카드 수 증감이 선언과 일치 ⑤ DF-06 dangling 0 ⑥ DF-08 요소 수 증감 일치
- **구조 카운트만으로 절대 통과시키지 않는다.** CRLF 사건은 요소·파트 카운트가 전부 정상이었다.

#### DF-21 `assert_edit_scope` — 편집 범위 단언
- 선언 범위 밖에서 **1바이트라도** 바뀌면 실패.

#### SYS-02 `roundtrip_noop_corpus` — 도구 회귀 CI **(치명)**
- 실 운영 덱 코퍼스(6face 19개 + A27·M1/M3·TN·Cross 계열)에 **편집 0회** 읽기→쓰기 바이트 동일 검사.
- **이게 없으면 도구 자체가 조용히 덱을 망가뜨린다.** 코퍼스는 우리가 제공한다.

### 3.2 2차 — 지금 손으로 하고 있는 일

#### 영역·도포 마스킹 (DF-25~30) — **전무, 신규**
- `part_plane_frame` — 파트 평면 확정(최소 관성축/최단 bbox 축 법선 또는 명시 3점). **나머지 전부의 전제**
- `element_column_map` — 두께방향 열 접기. **도포율은 반드시 열(column) 단위**로 계산한다(2층 파트를 요소 단위로 세면 층수만큼 왜곡). 면적은 아랫면 4절점 슈레이스 — 요소 bbox 근사는 **117%** 가 나온다(실측)
- `pattern_region` + `coverage_solve` — `FULL/CENTER/RING/V1/Vn/H1/Hn/Dn/X/GRID/RANDOM_VOID/POLYGON`. **설계 변수는 패턴 파라미터가 아니라 도포율(면적%)** 이다 → 목표 도포율을 주면 면적 기준 이분법으로 파라미터를 자동 보정. 받아들일 조건: `|실도포율 − 목표| < 0.1%p`
- `image_register` + `image_to_region_mask` — 도면/사진 → 마스크. **이미지에 축척이 없으므로 여기가 단일 실패점**이다. 모드 셋 필수: `bbox_fit`(거칠다, 미리보기 필수) · `anchor_2pt`(축척+회전 확정) · `fiducial`. 사진은 `image_rectify_and_scale` 로 기울기·원근 먼저 보정
  - **필수 산출물 넷**: ① 이미지 픽셀 커버리지 vs 요소 면적 커버리지 나란히(크게 다르면 정합 실패) ② 원 이미지 위 **오버레이 PNG** ③ 최소 피처 폭이 요소 크기의 2배 미만이면 **"표현 불가" 경고** 후 CAD 갈래 유도 ④ 경계 요소 비율(계단 오차)
- `part_region_export_image` — 역방향. 현 파트 평면을 PNG/SVG 로 내보내 사람이 칠하고 되먹인다. **도면이 없을 때 제일 빠른 루프다**
- `apply_mask` — `delete`(공극) / `split_part` / `swap_material`
  - 삭제는 **`line_span` 단위**로. 2줄 포맷에서 `eid pid` 줄만 지우고 노드줄을 남기면 그 뒤 **전체 위상이 반전**된다(고아 노드줄 14,840개가 남은 적이 있다)
  - 후처리 필수: `orphan_node_sweep` · DF-06 · **`contact_gap_guard`**(생긴 공극에 관통 방지 접촉이 실제로 있나 — 전역 `*CONTACT_AUTOMATIC_GENERAL`(SSTYP=5)이 없으면 파트끼리 통과한다) · `mass_volume_delta`(도포율 DOE 의 교란 변수)

#### 압착·갭·계면 (DF-31~39) — **`squeeze` 가 있으니 그 앞단이 필요하다**
- `resolve_effective_surface` — 솔리드는 절점면, **셸은 중립면에서 t/2 바깥**. 두께는 `*PART → *SECTION_SHELL` 에서 읽는다(하드코딩 금지). 실드캔(t=0.15)이 절점 기준 0.126mm 였는데 반두께를 빼니 0.051mm 로 테이프 두께와 정확히 일치했다 — 보정 없이는 "떠 있다"로 오판한다
- `measure_interface_gap` — 절점별 수직 간격 + `{상대 PID: (개수, min, p10, 중앙, p90, max)}` + **밀착 비율(<1µm)**. 격자 해시로 근접 후보만(XY 반경 기본 0.3mm). **min 이 아니라 분포**를 낸다 — min 만 보면 가장자리 한 점에 속는다. TIM 윗면 3,823절점 밀착 비율 **0.0%**, 중앙값 0.300mm 로 "이 모델에 압착이 없다"가 확정됐다
- `audit_contact_thickness` — 기하 간격에서 컨택이 더해 주는 두께를 뺀 **실효 간격**. `SLDTHK`/`SHLTHK`/`SST`/`MST` + `*CONTROL_CONTACT` 의 `SHLTHK`/`SSTHK`
- `classify_interface_bond` — `절점공유` / `TIED(_OFFSET 구분)` / `접촉만` / `무연결`
- `close_gap_by_node_shift` — 자유면 절점을 상대면까지, **내부 층은 비례 이동**. 좌표 필드가 16칸 고정이라 바이트 폭은 자동 보존된다. 검증 필수: 야코비안 음수 0 · 초기관통 0 · dt 예측 · 질량 변화
- `check_jacobian_winding` / `fix_winding` — 음수면 `n1 n2 n3 n4|n5 n6 n7 n8` → `n1 n4 n3 n2|n5 n8 n7 n6` **필드 문자열 교환**(자릿수·바이트 불변). **모든 절점 이동/분할 함수의 종료 검사로 강제**
- `equivalent_blt_stiffness` — 메시 안 바꾸고 `E_eq = E × (t_model/t_target)`. 한계 명시: 질량·관성·횡거동은 보정 안 된다
- `build_interface_ladder_doe` — `P0` 갭 유지 / `P1` 밀착+접촉만 / `P2` 밀착+TIED / (옵션) `P3` 압축커브 스프링. 도포율 축과 요인설계로 조합
  - **동반 `map_press_force_to_blt`**: 압착력(N)/토크/스페이서 두께 → BLT → 클리어런스·등가강성·결합레벨. **DOE 축을 물리 단위로 묶는 유일한 다리다.** 현장에서 "압착력을 낮췄더니 불량이 늘었다"는데 모델에 그 변수가 아예 없었다
- `check_initial_penetration` — `IGNORE=1` 이면 LS-DYNA 가 조용히 흡수하므로 솔버 로그로는 알 수 없다

#### 제출·판정 (DF-49, 51~52) — **수집은 강하니 제출 앞단이 필요하다**
- `guard_constraint_change_dt` — 구속 변경 전후 임계 dt 예측, **50% 이하로 떨어지면 대량 제출 차단**. RBE3 가 dt 를 303배 눌렀고 `energy ratio = 1.00000` · 128랭크 99.8% CPU 라 고장처럼 보이지 않았다
- `estimate_dt` / `attribute_dt_governor_to_parts` — 사전 `Lc=V/A_max`, `c=sqrt(E(1−ν)/((1+ν)(1−2ν)ρ))` / 사후 `d3hsp` 의 `100 smallest timesteps` 를 **파트·재질별 집계**
  - **dt 붕괴 판정은 `glstat` 의 `time step` 한 줄만 유효하다.** stdout·d3hsp·Slurm 상태는 전부 정상으로 보인다
- `preflight_submit` — DF-06/08/20/22/39/49/51 + `audit_output_requests` + `check_units_and_global_mass` 한 번에
  - `estimate_campaign_cost` — **런 1개당 51GB** 실측(d3plot 36.8 · dynain 1.9 · d3hsp 2.1 · 기타 ~10). 1,000런 = **51TB**. 임계 초과면 제출 차단
  - `submit_contract_guard` — 제출 시점에 **동결**되는 것(배치 스크립트 사본·환경변수)과 **런타임**에 읽히는 것(runner_config·덱)을 구분해 알린다. 제출 후 스크립트 패치는 무효다

### 3.3 3차 — 있는 것의 결손 메우기

- **`propagate_sets_on_refine`** — `refine`/`restack` 이 요소를 나눌 때 그것을 참조하던 `SET_SOLID`/`DATABASE_HISTORY` 를 자식으로 확장. 안 하면 elout 이 최하단 1/N 만 본다(**T4 에 실제로 남은 부채**). die 0.19mm 를 요소 2개로 나눈 것이 진짜 병목이었고 6층으로 늘리니 die 인장이 +37% 올라갔다
- `orphan_node_sweep` / `check_stray_nodes_bbox` + **`drop_plate_bbox_policy`** — 하위 전처리기가 낙하판을 `*NODE` **전체** bbox 로 만든다. 더미 절점 하나가 낙하판을 66mm 밖에 만들어 **충돌 없는 해석**이 됐다. bbox 기준을 "요소가 참조하는 절점"으로 한정하는 옵션은 하위 도구 결함에 대한 우리 측 방어다
- `check_material_plausibility` — 재질군별 허용 범위로 E·ρ·ν 자동 점검. 잡을 것: 자릿수 누락(zRO2 의 E 가 1000배 작음), 사출 광학플라스틱에 130GPa, ρ 가 강철의 1000배, ν≥0.5, 같은 이름 다른 값. **판정은 경고로 끝내고 사람에게 넘긴다** — 운영 덱 22개가 전부 같은 이상값이면 그건 규약일 수 있다
- `extract_material_table` / 제목 정규화 — 같은 재질이 `ZNDC`/`ZNDC_1`/`ZNDC_19G`, `Cu`/`Cu-Alloy`/`Cu_Alloy` 로 흩어져 있다. **미매칭 목록을 반드시 출력**할 것(Q8 덱의 ZNDC·PI·Cu·SUZY 가 이름 불일치로 누락될 뻔했다)
- `*MAT_ELASTIC_TITLE → *MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE` 변환은 **4장 카드 필수**(앞 40바이트 보존 + sigy/etan + eps1~8/es1~8 2장). 3장이면 IndexError rc=120
- `extract_fastening_graph` / `trace_load_path` — 노드=파트, 엣지=CNRB/TIED/스프링/절점공유. **dead end 검출**(TIED 이웃 1개뿐인 체결부) — T4 는 나사 보스 4개가 전부 dead end, PBA 는 FPC·PORON 7홉으로만 섀시에 매달려 있었다. **캠페인을 만들기 전에 "이 변경이 대상에 도달하는가"를 보여 줘야 한다**
- `add_tied_interface` — TIED 는 **조용히 안 붙을 수 있다.** 타이 형성 개수를 솔버 메시지에서 확인하고, 타이 전/후 결과가 bit-identical 이면 **실패로 판정**
- `verify_drop_attitude` — `stcx_fullangle_drop` 이 생성한 (roll,pitch)가 실제로 의도한 면/모서리/코너에 닿는지 덱 기하로 역검증하고 면 라벨을 실측 기준으로 다시 붙인다. 규약: `d=(cos r·sin p, −sin r, −cos r·cos p)`, 접촉점 = `d·X` 최대점. **Z 의 음부호가 필수** — 틀려서 면 배정이 어긋난 적이 있다
- `establish_noise_baseline` — 효과를 주장하기 전에 **같은 덱을 다시 돌려** 잡음 하한을 잡는다. (실측: LS-DYNA MPP 는 bit-deterministic 이라 101상태 전부 상대차 0.000e+00 — 즉 덱 간 차이는 전부 모델 차이다)
- 성공 판정 — `.done` 파일이나 diagnose 로그는 **오답이다**. 결과 산출물(`report/analysis_result.json` 등)의 존재와 크기로 판정한다
- `classify_run_outcome` — 키워드 즉사 / dt 붕괴 / NaN·음의체적 / **미충돌** / 침식 과다 / 전처리기 사망 / 정상. **"실패 0건"은 성공의 증거가 아니다** — glstat 운동에너지 감소로 충돌 발생을 별도 판정
- `deck_manifest` — 덱마다 `원본 sha256 + 편집 체인 + 파라미터 + 표시된 가정 + 도구 버전` 을 사이드카 JSON 과 덱 머리 `$` 주석에 각인. 3개월 뒤 "이 덱이 뭐였더라"에 매번 반나절이 든다
- `plan_edit` / `deck_checkpoint_rollback` / `apply_across_decks` — dry-run 은 apply 와 **동일 코드경로**(출력만 계획). 700MB 원자적 쓰기·백업·롤백·잠금. 팬아웃은 덱마다 방언을 독립 판정하고 **"해당 없음"과 "읽기 실패"를 구분**한다
- `render_deck_preview` — 덱 자체를 단면·평면으로 렌더. **후처리기 렌더에 의존하지 않는다**(2시간 타임아웃·137GB SIGBUS 전례). 원격 SSH 고려해 **PNG 와 ASCII 둘 다**
- `ascii_safe_stdout` / `emit_for_consumer` — 진단 출력이 상위 파이프라인(ascii 로케일)에서 죽지 않게. 출력 덱의 소비자(LS-DYNA raw / KooMeshModifier / KooRemapper / HyperMesh)를 **선언**하면 그 방언 제약을 적용하고 어느 쪽도 못 맞추면 **사전 거부**
  - 근거: 전처리기의 한글 진단 출력에 상위 파이프라인이 ascii 로 죽었고, Slurm 이 제출 시점 env 를 동결해 **제출 후 패치가 무효**였다
- `preflight_solver_check` — raw LS-DYNA(`endtim=1e-8`)와 하위 전처리기 왕복을 **둘 다**, 원본도 같이 돌려 기준선. 왕복 후 `*KEYWORD` 옵션 보존 재검사. **LS-DYNA 통과 ≠ 전처리기 통과**

### 3.4 있는 것의 확장

- `cnrb2spring`(=DF-47) — **유격은 면내에 있다**(홀이 나사보다 큰 것이지 위아래로 뜨는 게 아니다). 그리고 TIED 체결부도 같은 축으로 유격화해야 한다. CNRB 21개만 유격화하고 TIED 225개를 강체로 남겨 1,464런이 무효가 됐다
  - 함정: 블록을 이어붙일 때 빈 줄이 들어가면 `*ELEMENT_DISCRETE` 가 그걸 요소로 읽어 `discrete element id 0 is invalid`. `*SECTION_DISCRETE` 는 **2줄 필수**, `*ELEMENT_DISCRETE` 는 **8칸 고정폭**
- `squeeze` — 입력을 "변형 조건"이 아니라 **`measure_interface_gap` 이 낸 목표 클리어런스**로도 받게
- `contact` — `resolve_contact_targets`(SET 을 풀어 실제 파트쌍 확정) 추가. **컨택 제목·이름으로 고르는 것을 금지**하기 위한 기반이다. `find_duplicate_joints`: 한쪽 덱에만 중복 TIED 가 있으면 컨택당 계측값이 절반으로 깎여 **가짜 역전**이 생긴다

---

## 4. 경계 — StepForge 와의 인계

**판단 규칙: 노드 ID 가 바뀌면 StepForge, 안 바뀌면 DynaForge.**

같은 일을 두 갈래로 할 수 있으면 **둘 다 제공하고 한계를 명시**한다. 도포 영역 반영은 k파일 요소 삭제(계단 오차 = 요소 크기)로도, CAD 트림(정확)으로도 된다.

- **`check_mask_resolution_feasibility`** — 요구 형상의 최소 피처 폭·모서리 반경·이격을 현재 메시로 표현할 수 있나. **불가하면 k파일 마스킹을 거부하고 CAD 갈래로 유도한다.** 요소 0.5mm 메시로 폭 0.6mm 줄무늬를 표현하려는 시도를 도구가 막아야 한다
- **`rebind_entities_after_remesh`** — StepForge 가 재메시해 노드 ID 가 통째로 바뀐 뒤 노드세트·CNRB·SPC·DATABASE_HISTORY·TIED 슬레이브를 **위치 기준**으로 재결속. 재메시 **전에** "무엇이 깨지는지" 미리 조회하는 `assess_edit_impact` 가 반드시 같이 있어야 한다
- **`align_image_to_geometry`** — 이미지 정합 모듈은 DF-28(k파일)과 SF-04(CAD)가 **같은 변환**을 써야 한다. 같은 이미지가 두 갈래에서 같은 물리 좌표로 떨어져야 한다. 어느 리포가 소유할지는 두 리포가 정한다
- **`cad_solid_merge_to_deck`** — CAD 메시를 기존 덱에 파트로 삽입. **가장 사고가 잦은 지점**이다. ID 대역 예약(DF-07)·단위 변환·좌표 정렬 후 DF-06/08/20 전부 통과

**정의는 한 곳에만 둔다.** 평면 프레임·이미지 정합·도포율 계산은 공통 모듈이고 두 레이어가 같은 결과를 내야 한다.

---

## 5. 받아들일 때의 계약

기능이 들어왔다고 판정하는 기준이다. 이것 없이는 "됐다"를 말할 수 없다.

1. **요소 수 3자 대조** — 원본/템플릿/per-run, 파트별
2. **바이트 증감 대조** — 의도한 변화량과 일치. 구조 카운트만으로는 부족하다
3. **참조 무결성 0건** — 삭제·재번호 후 필수
4. **dt 사전 예측 + `glstat` 실측** — 기준 대비 절반 이하면 중단
5. **하중 경로 도달 확인** — 변경이 대상에 실제로 닿는가
6. **bbox 출처 확인** — 요소가 참조하는 절점만인가
7. **물성 타당성 + 과제 간 일관성**
8. **위치 기반 매칭** — ID·이름으로 매칭 금지
9. **DOE 교집합** — 부분 데이터 결론 금지
10. **소비자 방언 계약** — LS-DYNA 통과 ≠ 전처리기 통과
11. **계면 밀착 비율** — 갭 분포를 재기 전에는 "이 부품이 하중을 받는다"고 가정하지 않는다
12. **잡음 하한 확립** — 효과 주장 전에 같은 덱 재실행

---

## 부록 A. 필드폭·포맷 규약 (도구가 표로 보유할 것)

| 카드 | 필드폭 | 비고 |
|---|---|---|
| `*NODE` | nid 8 + x/y/z 각 16 + tc 8 + rc 8 | `I10=Y` 면 nid 10, 좌표 오프셋 11/27/43 |
| `*ELEMENT_SOLID` | 8칸 | `(ten nodes format)` = **요소당 2줄**. 섹션마다 개별 판정 |
| `*ELEMENT_SHELL/_DISCRETE/_MASS/_BEAM` | 8칸 | 각자 줄 수 다름 |
| `*PART` | 10칸 | 제목줄 1 + 데이터줄 1 |
| `*SET_*_LIST` | 10칸 | `_TITLE` 이면 제목줄 +1. 일부 덱은 `solver`(MECH) 필드가 6번째 — **해당 덱의 지배적 형식을 따를 것** |
| `*MAT_*` | 10칸 | `_TITLE` 이면 제목줄 +1. PIECEWISE_LINEAR_PLASTICITY 는 **카드 4장** |
| `*CONTACT_*` | 10칸 | `_ID` 접미사면 cid+title 카드 **1줄 더** |
| `*CONSTRAINED_*`, `*CONTROL_*`, `*DEFINE_*`, `*DAMPING_*` | 10칸 | |
| 개행 | 감지 후 보존 | `count(b"\r\n")*2 > count(b"\n")` |
| 인코딩 | latin-1 (1:1) | `errors='ignore'` 금지 |

---

## 부록 B. 우리가 제공할 것

- **운영 덱 코퍼스** — SYS-02 회귀 CI 용(6face 19개 + A27·M1/M3·TN·Cross 계열). 2줄 포맷 혼재 덱, `I10=Y LONG=S` 덱, `_ID` 접미사 TIED 덱 포함
- **실측 기준값** — TIM 갭 분포(3,823절점), 셸 반두께 보정 전후(0.126 → 0.051mm), die 층수 대 인장(+37%), 런당 디스크 51GB, MPP bit-determinism 확인(101상태 상대차 0)
- **재현 사례** — 위 사건 14건의 덱과 로그
