# Plan — Q8 전각도 낙하 준비 3종 (`extract-parts` · `cleanup-nodes` · `info` 보강)

> 요청: koo.park (CAE그룹) — "KooRemapper 기능 요청 v1.0 · 2026-10-10"
> 회신·설계: 2026-10-10
>
> **읽는 분께** — §1 에 요청서 전제를 코드로 확인한 결과가 있습니다. **④는 전제가 반대이고
> 절반은 이미 됩니다.** 그 절은 먼저 읽어 주십시오. ①②③ 은 요청대로 타당합니다.

## Executive Summary

| 관점 | 내용 |
|------|------|
| **Problem** | Q8 접힘 전각도 낙하 준비가 두 군데서 끊긴다 — ① 2.32GB 덱에서 디스플레이 적층 9파트만 자립형 `.k` 로 떼어낼 수단이 없어 `unfold`→`prestress` 에 진입하지 못하고, ② 고아 절점 118,568개가 bbox 를 53mm 부풀려 낙하판이 기기 밖에 생성된다(충돌 자체가 없다). |
| **Solution** | `extract-parts`(파트 선택 추출, ID·고정폭·CRLF 보존) + `cleanup-nodes`(키워드별 참조 추적 기반 안전 삭제 + 세트 멤버 정리) 두 op 신설. 둘 다 **맨땅이 아니다** — `DeckWriter`(CRLF 보존)·`formatNodeLine`(칸폭 추종)·`ReferenceIntegrity`(329줄, 키워드별 필드 파싱)를 재사용한다. |
| **Function/UX Effect** | `extract-parts` → `unfold` → `prestress` → `relax` 가 한 줄로 이어지고, `cleanup-nodes` 가 bbox 전후를 찍어 낙하판 오배치를 **사전에** 드러낸다. Q8 Close 전각도 낙하 준비 전 구간이 KooRemapper 안에서 돈다. |
| **Core Value** | 두 사고(연결성 뒤섞임·충돌 없는 낙하)는 **에러 없이 조용히 틀린** 종류다. 요청서 §6 의 함정 표를 그대로 **되읽기 검증 기준**으로 채택해, 두 op 이 스스로 "미정의 0" 을 증명하게 한다. |

---

## 1. 요청서 전제 확인 — 코드로 재서

### ①②③ — 요청대로 없다 (타당)

| 요청 전제 | 확인 |
|---|---|
| `strip` 은 키워드 단위라 파트 선택이 안 됨 | ✅ 카탈로그: "Remove specified LS-DYNA keyword blocks … prefix-based" |
| `extract-surface` 는 셸만 뽑음 | ✅ "Extracts the free (outer) surface … **as shell QUAD4**". `pid` 필터는 있으나 산출은 셸 |
| `merge` 는 적층을 합치는 쪽 | ✅ "Merges stacked solid elements … into homogenized layers" |
| `prestress`·`strain` 은 같은 토폴로지 전용 | ✅ "Computes strain tensor between two K-files with **identical topology**" |
| 고아 절점 정리 수단 없음 | ✅ 58 op 전수 · `src/`·`include/` 전수 grep 에서 해당 op 0건 |
| §7 `relax` 가 `*SET_PART_LIST` 를 자동 생성하지 않음 | ✅ `*INTERFACE_SPRINGBACK_LSDYNA` 를 내는 곳은 `cclip` 뿐(`psid 3` 하드코딩). `relax` 는 내지 않는다 |

### ④ — ★전제가 반대이고, 절반은 이미 됩니다

요청서는 "현재 `info` 는 bbox 를 하나만 내고 그것이 `*NODE` 전체 기준" 이라고 적었습니다.
**`info` 의 bbox 는 이미 요소 사용 절점 기준입니다.** `Mesh::calculateBoundingBox()`
(`include/core/Mesh.h:258-268`)이 고아 절점을 **일부러 뺍니다**. 주석에 이유까지 적혀 있습니다 —

> "요소가 참조하는 절점만 본다. 바깥에 떨어진 고아 참조 절점(`*CONSTRAINED_RIGID_BODIES`,
> `*BOUNDARY_PRESCRIBED_*`, `*ELEMENT_MASS` 의 더미 절점)이 bbox 를 부풀리면 `map`·`shellmap`
> 의 **모든 파라메트릭 비율**이 하류에서 왜곡된다."

Q8 상황을 그대로 재현한 픽스처로 쟀습니다 — 요소 사용 절점 x 0~10, 고아를 x=−40 과 x=28 에.

| | 값 | 기준 |
|---|---|---|
| `info` `Size` | 폭 **10** | **요소 사용 절점** (고아 제외) |
| `modelmeta` `model.bbox` | 폭 **68** | `*NODE` 전체 |
| `modelmeta` `parts[].bbox` 합집합 | 폭 **10** | **요소 사용 절점** |

그리고 **`modelmeta` 는 파트별 bbox 를 이미 줍니다**(`parts[].bbox_min`/`bbox_max`,
`src/commands/modelmeta.cpp:642-659` 가 요소를 순회합니다). 요청서 §5 에서 찾으신
`pid 100213 GF30#05_PROTECT_CAP_2 폭 19.52 mm` 같은 진단은 **오늘 `modelmeta` 로 바로 나옵니다.**

**따라서 67.50 mm 를 낸 것은 KooRemapper 가 아닙니다.** DropSet 쪽이 `*NODE` 에서 직접 뽑은
값으로 보입니다. KooRemapper 는 내부적으로 함정을 피하는데 **그 사실을 말하지 않아서**, 자기
bbox 를 따로 계산하는 하류 도구는 그대로 빠집니다.

→ ④의 실제 수선은 요청보다 **작고 더 정확합니다**: "두 값을 나란히 찍고 고아 수를 말한다".
그 한 줄이 요청하신 경고이고, 동시에 하류 도구가 `*NODE` 로 재면 안 된다는 신호가 됩니다.

---

## 2. 설계

### ④ `info` 보강 + `modelmeta` 기준 명시 — 우선 (소규모)

```
Nodes:                   13,366,933
Elements:                ...
bbox (요소 사용 절점)     X  -4.5500 ~  10.0006   폭  14.5506   ← 기기 실제 치수
bbox (*NODE 전체)        X -39.3601 ~  28.1444   폭  67.5046
[WARN] 고아 절점 118,568개 (0.89%) — 두 bbox 가 52.95mm 다르다.
       낙하판·접촉면을 bbox 로 놓는 도구는 **요소 사용 절점 기준**을 쓰라.
```

- 요소 사용 bbox 는 `calculateBoundingBox()` 를 그대로 쓴다(이미 그 값이다 — 라벨만 붙인다).
- 전체 절점 bbox 를 **추가로** 계산해 나란히 찍는다. 두 값의 차가 임계(예: 어느 축에서 전체
  폭의 5% 이상)를 넘으면 `[WARN]`.
- `modelmeta` 는 `model.bbox_*` 의 **기준을 JSON 에 명시**하고(`"bbox_basis": "all_nodes"`),
  요소 기준 값을 `model.bbox_used_*` 로 **함께** 낸다 + `model.orphan_nodes`.
  `conventions` 블록에 한 줄 추가(그 블록이 이미 기준 설명을 담는다).
- 파트별 bbox 는 **손대지 않는다** — 이미 요소 기준이고 맞다.

### ② `cleanup-nodes` — `ReferenceIntegrity` 에 **절점 축**을 더한다

재사용 자산: `src/validation/ReferenceIntegrity.cpp`(329줄)가 이미 키워드별 필드 형식으로
`*SET_*` · `*CONSTRAINED_NODAL_RIGID_BODY` · `*BOUNDARY_SPC_SET` · `*DATABASE_HISTORY_*` ·
`*LOAD_NODE_SET` · `*LOAD_SEGMENT_SET` · `*CONTACT_*` · `*MAT_*` · `*SECTION_*` 를 파싱합니다.
다만 추적 축이 **세트·파트·섹션·재질 ID** 이고 **절점이 아닙니다.**

> 요청서의 진단이 정확합니다 — "비-`*NODE`/`*ELEMENT_` 줄에서 8칸·10칸·공백 분리로 숫자를
> 전부 긁었더니 118,568개 전부가 참조됨으로 나왔다". 그래서 **키워드별 필드 형식**이 필요하고,
> 그 지식이 이미 이 파일에 있습니다. 이 기능이 KooRemapper 에 있어야 하는 이유도 그것입니다.

요청서의 `keep_referenced_by` 다섯 중 **셋은 이미 알고 둘은 새로 넣어야** 합니다 — 작업량의
실제 모양입니다.

| keep 키워드 | `ReferenceIntegrity` 가 아는가 |
|---|---|
| `CONSTRAINED_NODAL_RIGID_BODY` | ✅ (요청서의 71건이 여기서 걸린다) |
| `BOUNDARY_SPC_NODE` | ✅ (`*BOUNDARY_SPC_SET` 을 안다 — `_NODE` 변종 확인 필요) |
| `DATABASE_HISTORY_NODE` | ✅ |
| `CONSTRAINED_EXTRA_NODES` | ❌ 새로 |
| `INITIAL_VELOCITY_NODE` | ❌ 새로 |

인터페이스는 요청서 그대로 받습니다(`mode` · `keep_referenced_by` · `prune_sets` · `report`).
`mode: report` 를 **기본**으로 둘 것을 제안합니다 — 지우는 쪽이 기본이면 사고가 조용합니다.

산출 JSON 은 요청서 양식을 그대로 쓰고 `bbox_before`/`bbox_after` 를 반드시 넣습니다.

★추가 제안 — **`keep_referenced_by` 를 비워도 안전해야 합니다.** 요청서의 다섯 키워드는
좋은 기본값이지만, 그 목록에 없는 키워드가 절점을 참조하면 조용히 깨집니다. 그래서
`mode: safe` 는 **알고 있는 키워드로 참조를 찾고, 모르는 키워드가 숫자처럼 보이는 필드를 가진
경우 그 절점을 남기고 `unknown_keyword_kept` 에 적습니다**(거절이 아니라 보고). 즉
"안전" 의 뜻을 "내가 이해한 것만 지운다" 로 둡니다.

### ① `extract-parts` — ID·고정폭·CRLF 보존이 전부다

재사용 자산:
- `DeckWriter`/`NewlineStreambuf`(`include/parser/DeckWriter.h`) — 덱 쓰기의 **단일 진입점**이고
  원본 개행을 되붙입니다. 700MB~1GB 를 전제로 **스트리밍**이며 상수 메모리입니다. 홀로 선 `\n`
  앞에만 CR 을 넣으므로 `\r\r\n` 이 생기지 않습니다.
- `formatNodeLine(id,x,y,z,fw)`(`ModelAssembler`) — 그 덱의 **칸폭을 따라갑니다**.
- `ReferenceIntegrity` — `sets: referenced` 판정(뽑은 파트를 가리키는 세트만)에 그대로 씁니다.

인터페이스는 요청서 그대로(`parts` / `part_titles` 와일드카드 / `include.{nodes,sets,materials,
sections}` / `renumber: false` 기본).

★설계 판단 둘:
1. **`renumber: false` 가 기본**이고, `true` 는 **매핑 표를 함께 내도록** 합니다
   (`renumber_map.json`). 안 그러면 되돌릴 수 없습니다.
2. **잘라낸 쪽이 아니라 남긴 쪽을 검증합니다** — 산출 덱의 요소가 참조하는 절점이 전부 그 덱
   안에 있을 것(미정의 0). op 이 스스로 찍습니다(요청서 §2 의 3번).

### ③ `map-state` — 보류

요청서도 "①②가 되면 불필요" 로 적었습니다. ①②④ 를 먼저 내고, 그 뒤에도 필요하면 별건으로
설계합니다. 지금 짜면 ①②가 만들 경로와 겹칠 위험이 큽니다.

---

## 3. 검증 기준 — 요청서 §6 을 그대로 채택

요청서가 적어 주신 함정 표는 **전부 에러 없이 조용히 틀린** 사례입니다. 되읽기 검증으로
그대로 넣습니다. 아래가 회귀 체크리스트가 됩니다.

- [ ] `*ELEMENT_SOLID` 8칸 고정폭 — 절점 ID 8자리로 공백이 사라진 덱을 픽스처로 넣고,
      **요소 참조 절점 중 미정의 0** 을 확인한다. (요청서: `split()` 오판으로 총 요소 수가
      10.2M vs 15.9M 로 틀렸다)
- [ ] `*NODE` 8+16×3 · `*PART`/`*MAT`/`*SET` 10칸 — 쓴 뒤 **되읽어 값 보존** 확인
      (고정폭 지수 잘림: `E-09` → `E-0` 로 밀도 10억 배)
- [ ] **CRLF 보존** — CRLF 덱을 넣어 산출에 **LF 단독 줄 0**
- [ ] `*SECTION_*_TITLE` 제목줄 — 섹션 수 ↔ 참조 secid 수 대조(섹션이 통째로 사라지지 않는다)
- [ ] `*SET_PART_LIST` SID 줄 위치 — 멤버 수 ↔ 기대값 대조
- [ ] `cleanup-nodes` — 요청서 분류를 재현: CNRB 참조 71 · 다른 세트 3 · 삭제 가능 118,529.
      삭제한 절점이 `*SET_NODE_*` 멤버에서도 빠졌는지(LS-DYNA `Error 10233` 재현 금지)
- [ ] `cleanup-nodes` — **bbox 전후**가 리포트에 있고 콘솔에도 찍힌다
- [ ] `extract-parts` — `renumber: false` 에서 요소·절점 ID 가 **바이트까지 동일**
- [ ] `info` — 두 bbox 와 고아 수가 찍히고, 차가 크면 `[WARN]`
- [ ] 기존 44 op 의 **덱 바이트 불변**(`tools/deck_manifest.py`) — 신설 op 이므로 0건이어야 한다

★요청서 §6 의 dynain 함정 둘(`NINT` 적분점 · 응력줄 고정폭)은 `prestress` 쪽이고 이번 범위
밖입니다. 다만 "고아 값줄 0" · "레코드 수 ↔ 요소 수" 는 좋은 기준이라 `prestress` 회귀에
별건으로 추가할 것을 제안합니다.

---

## 4. 규모와 순서

| # | 기능 | 규모 | 근거 |
|---|---|---|---|
| ④ | `info` + `modelmeta` 기준 명시 | **작다** | 요소 기준 bbox 는 이미 있다 — 라벨·전체 절점 값·고아 수만 더한다 |
| ② | `cleanup-nodes` | **중간** | `ReferenceIntegrity` 에 절점 축 추가 + 세트 멤버 정리 + 리포트 |
| ① | `extract-parts` | **크다** | ID·고정폭·CRLF·세트·재질·섹션 선별 + 되읽기 검증. 2.32GB 를 스트리밍으로 |

순서는 **④ → ② → ①** 을 제안합니다. ④가 먼저면 ②의 사고를 그날 바로 볼 수 있고, ②의 산출이
①의 입력 품질을 보장합니다.

---

## 5. 요청자께 확인이 필요한 것

1. **`extract-parts` 의 `include.sets: referenced` 범위** — "뽑은 파트를 가리키는 세트" 에
   `*SET_NODE_*` 도 포함합니까? 뽑은 파트의 절점만 걸러 **잘라낸 세트**를 낼지, 아니면 그
   세트는 **빼버릴지**가 갈립니다. 접촉·경계조건을 이어 쓰려면 잘라내는 쪽이 맞는데, 잘라낸
   세트는 원본과 ID 가 같으면서 내용이 다릅니다 — 그 혼동이 더 위험할 수도 있습니다.
2. **`cleanup-nodes` 의 기본 `mode`** — `report` 를 기본으로 둘까요(제안), `safe` 를 둘까요?
3. **2.32GB 덱을 이쪽에서 받을 수 있습니까?** 지금 이 호스트에 없습니다(`stc` 실측이라 하셨으니
   당연합니다). 요청서 수치를 **재현해서** 회귀 픽스처를 만들려면 덱이나, 최소한 같은 포맷의
   축소본이 필요합니다. 없으면 합성 픽스처로 짜고 "실제 덱 미검증" 으로 적습니다.
4. **③ `map-state` 를 정말 보류해도 됩니까?** ①②가 들어간 뒤 다시 보시는 것으로 이해했습니다.
