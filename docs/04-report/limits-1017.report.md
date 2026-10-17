# 한계 여섯 — 작은 셋 · 큰 셋 완료 보고서 (5차 배포)

> 사용자 요청 — 「말고 또 할거 남았나」 → **「셋다 고치는게.낫겠는데」** · 결정 넷은 권장안(AskUserQuestion) ·
> 상시 지시 「업데이트 되었으면 당연히 빌드도 다 해야한다」
>
> 작성일: 2026-10-17
> 상태: 완료 — 여섯 모두 지어 5차로 배포했다(네 자리 `cd07c327` · SIF 세 사본 동일). 남은 것은 셸 층 묶기의 솔버 시험(4차 · 사용자 몫)과 바깥 대기 항목이다.
>
> ⚠ 수치는 이 라운드에서 직접 잰 값이다(커밋 메시지와 장부에 같은 값을 적었다).

---

## Executive Summary

### 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **기능명** | 4차 배포 뒤 남긴 한계 여섯 — 작은 셋(정본을 두 번째 소비자에게) · 큰 셋(거절·null 로 막아 둔 자리를 실제로 푼다) |
| **기간** | 2026-10-17 (하루) |
| **커밋 수** | **11개**(`fe37b04..44f16c9`) + pyKooCAE **1개**(`15e5e8f`) |
| **변경 규모** | 65 파일 · **+3,141 / −627** — C++ 43 파일 +1,608/−451 · 시험 10 파일 +920/−63 |
| **장부** | `docs/requests/deck-contract-checklist.md` 「5차」 · 계획 `docs/01-plan/features/limits-1017.{plan,checklist,context-notes}.md` |

### 결과 요약

| 지표 | 결과 |
|------|------|
| **고친 것** | 작은 셋 3 · 큰 셋 3 — 그리고 짓다가 돌려 보고 찾은 결함 **9건**(아래 §결함) |
| **정본으로 모은 것** | 목록 카드 표 `noderefs::listCardOf`(세 장치) · 흘려 읽기 닫힘 `include_closure::readPaths` · 홀로 서는 펼치기 `include_closure::inlined`·`FlatDeck` · 재질 정의 훑기 `cur_scanMaterialIds` · 모서리 표(modelmeta 가 `topo::edgesOf` 로) |
| **사용자 결정** | 넷 — 범위 여섯 · 2차는 코너 값 + `geometry_basis` · 인클루드는 `flatten_includes: true` 일 때만 · 재결속 공차는 줄 때만 |
| **신규 시험** | 회귀 파일 **97 → 99**(`test_dead_node_list_cards` · `test_flatten_includes`) + 기존 넷 확장(cleanup-nodes F-10~14 · 2차 솔리드 다시 씀 · 재결속 D–G · hfdamp C-1b) · 단위 **104 → 112** · 백엔드 **563 → 564** |
| **관문(릴리스 바이너리)** | 회귀 **99/99** · 단위 112/112 · 도움말 예제 ALL PASS · 패리티 ALL PASS · 백엔드 564 · 42 op 덱 바이트 = 4차 게시본(리포트 JSON 둘만) · GLIBC_2.35 |
| **배포** | 5차 `dist-20261017-082514Z`(`cd07c327`) · `cli.sif` `d8213999` · API·MCP health 일치 · 스모크(op 63 · 도구 72) · 그림 20/20 · 덱 op 21/21 · MCP 설명 14/14 · 플랫폼 경유 새 동작 3/3 · 스테이징 `1164d8ed → cd07c327` · SmartTwinPreprocessor.sif 재bake(§배포) |

### Value Delivered

| 관점 | 내용 |
|------|------|
| **Problem** | 2차 솔리드(TET10)는 그림이 거절되고 메타가 null 이었다 · 고쳐 쓰는 op 은 인클루드 덱에서 rc 0 으로 **아무것도 안 바꾼 덱**을 냈다(tetremesh 는 빈 덱) · 재결속은 한 파일·정확 일치·좁은 카드만 받았다 · 정본 밖 사본 셋이 조용히 틀렸다 |
| **Solution** | 리더가 절점 칸을 다 읽고 코너를 제자리에 놓는다 · `flatten_includes` 와 「대상이 인클루드 안이면 멈춤」 · 재결속 공차·인클루드·카드 · 사본을 정본으로 |
| **Function UX Effect** | TET10 단면이 1차와 같다(0.665 · 예전 0.19) · 쪼갠 덱의 27 op 이 안내와 함께 멈추고, 옵션을 주면 안 쪼갠 덱과 **같은 산출** · 공차는 쓴 곳과 거리를 말한다 |
| **Core Value** | 「조용히 틀린 산출을 내지 않는다」를 두 큰 자리(2차 기하 · 인클루드 덱)로 넓혔다 — 막던 것을 푸는 대신 **값이 맞는 것을 시험으로 지킨다** |

---

## 작은 셋

| | 무엇 | 실측(돌려서) | 커밋 |
|---|---|---|---|
| S1 | hfdamp 거절 종료 코드 255 → 1 | 선택형 닫힘 불완전 · 값 검사(cdamp) 거절이 둘 다 255 | `19c265d` |
| S3 | 지운 절점 정리 — 목록 카드를 정본 표로 | ★`*SET_NODE_INTERSECT`·`*SET_SEGMENT_INTERSECT` 의 **세트 ID** 를 절점으로 읽어 교집합을 비웠다 · ★맨 `*SET_NODE` 는 옮기지 않고 지웠다(같은 세트가 `_LIST` 면 67·68 → 199·200) · 보고 장치도 세 번째 사본 | `f7ad8c0` |
| S2 | cleanup-nodes 인클루드 → 정본 닫힘(흘려 읽기 판) | ★9단째 인클루드를 「read: 9」로 세고 **훑지 않아** 거기 요소가 쓰는 절점을 지웠다(safe · rc 0 · 되읽기도 같은 길이라 0) · `␣+` 이름 못 찾음 | `5871e5d` |

## 큰 셋

### B1 2차 솔리드 리더 (`0193459`)
- 덱 순서 전체 절점을 `Mesh::solidAllNodes`(2차 요소만)에 두고 코너를 위상 표 자리에 — TET10 은 N1..N4(매뉴얼 Fig 19-31) → TET4 꼴 + 종류 TET10 · 육면체 23·24·29 는 앞 8칸.
- 매뉴얼 본문에 코너 차례가 없는 ELFORM 25·26·27·28 과 칸이 모자란 카드(8+2 · 옛 한 줄 꼴)는 **그대로 거절·null** — 짐작하지 않는다.
- 매뉴얼 꼴 TET10 둘로 다시 잰 값 — 단면 0.665(1차와 같다) · 자유면 삼각형 6 · 부피 0.5 · n_node 14 · 고아 0 · 야코비안 1 · 2.
- 소비자 — 그림 셋 · modelmeta(`geometry_basis` · `second_order` 는 2차 파트 전부) · info · 재결속(소속) · `KFileWriter`(두 카드 꼴 · 전체 절점 없는 TET10 은 안 쓴다) · 프런트(⚠ 는 geometry_basis null 만).
- ★같이 고친 것 — modelmeta `edge_len` 이 육면체 12모서리 사본을 사면체에도 써 n1–n3 을 빠뜨렸다(max 9.055 · 참 10.0). 1차 TET4 값도 바뀐다 → StepForge 답신 §0-1 에 알렸다.

### B2 재결속 (`ea3e994`)
- `tolerance`(줄 때만) — 같은 파트 제목 안 거리 안 새 절점이 하나일 때만 · 둘이 하나로 몰리면 거절 · 몇 곳·최대 거리를 [WARN].
- 인클루드로 쪼갠 두 덱 — 닫힘을 다 읽어야 받는다 · 한 파일 덱과 산출이 **바이트로 같다**.
- `*DAMPING_PART_MASS/STIFFNESS`(PID · MASS FLAG=1 Card 2) · `*INITIAL_STRESS_SOLID/SHELL`(카드 세트 길이를 NINT·NHISV·LARGE… 로).

### B3 `flatten_includes` (`0b7daf8`)
- 실측 — 모든 op 사례를 주 덱 + `*INCLUDE` 로 쪼개 다시 돌렸더니 14개 rc 1 · 10여 개 rc 0 인데 아무것도 안 바꾼 덱(convert·refine·elform·update·load·boundary·rbe·matdb · tetremesh 빈 덱 · explicit 은 인클루드의 *CONTROL_IMPLICIT_* 를 남김).
- 지금 — 27 op 이 쪼갠 덱에서 rc 1 + 안내 · 옵션을 주면 안 쪼갠 덱과 같은 산출 · 임시 파일 안 남김(회귀 114항).
- 「모든 파트」 op 은 주 덱에 요소가 없을 때만 멈추고, 있으면 고치되 인클루드 파트는 안 고쳤다고 [WARN](처음 판은 이 꼴도 멈춰 `test_assembler_include_ids` 의 czm·tetremesh 두 항을 깼다 — 회귀가 잡았다).

## 결함 — 짓다가 돌려 보고 찾은 것 9건
1. restack 정리가 교집합 세트의 세트 ID 를 절점으로 읽어 세트를 비웠다(S3).
2. 맨 `*SET_NODE` 의 절점을 옮기지 않고 지웠다(S3).
3. 보고 장치가 교집합을 「지운 중간면 노드」로 적었다(S3).
4. cleanup-nodes 가 9단째 인클루드를 훑지 않고 그 절점을 지웠다(S2 · rc 0).
5. modelmeta 사면체 `edge_len` 이 n1–n3 을 빠뜨렸다(B1 · 1차 TET4 도).
6. tetremesh 가 쪼갠 덱에서 빈 덱을 rc 0 으로 냈다(B3).
7. explicit 이 인클루드의 implicit 제어 카드를 남겼다(B3).
8. convert·refine·elform·update·load·boundary·rbe·matdb 가 쪼갠 덱에서 아무것도 안 바꾼 덱을 rc 0 으로 냈다(B3).
9. 백엔드 관문이 옛 바이너리를 재고 있었다 — `platform/backend/bin` 은 compat 빌드만 채운다(그 전 563 은 4차 바이너리 기준이었다).

## 배포 (5차)
- 릴리스 `cd07c327`(0b7daf8 · GLIBC_2.35) → 관문 전부 → 프런트(FilePanel) · `cli.sif` `d8213999` → Drive `dist-20261017-082514Z`(보관 4) →
  API · MCP 재기동(health `cd07c327` · `revision_matches_binary: true`) → smoke(op 63 · 도구 72) · 그림 20/20 · 덱 op 21/21 · 설명 14/14 ·
  플랫폼 경유 — TET10 업로드 meta `geometry_basis: corners` · 고아 0 / 쪼갠 덱 ale 옵션 없음 failed · `flatten_includes` succeeded(산출에 `*INCLUDE` 없음) /
  재결속 `tolerance` 가 구조화 검증을 지난다.
- 스테이징 `1164d8ed → cd07c327` · `cli.sif` → SmartTwinPreprocessor.sif 재bake(`bake rc=0` · tar v119 · Drive 업로드 둘 · 메일) →
  `/opt/apptainers` → **세 사본 바이트 동일**(`eddd5783`) · 안의 바이너리 `cd07c327` — **네 자리(게시본 · API · 스테이징 · SIF)가 같다.**
  그 SIF 안에서 TET10 코너 · 쪼갠 덱 ale(옵션 없음 rc 1 · 있으면 rc 0) · REMAP 배선 5/5.

## 한계 (정직한 명시)
- ELFORM 25·26·27·28 의 코너 차례는 매뉴얼 **본문**에 없다(그림뿐) — 그 파트는 계속 거절·null 이다. 그림의 차례를 확인할 길(LS-PrePost · 실물 덱)이 생기면 푼다.
- 2차 요소의 값은 **코너로 잰 값**이다 — 휜 모서리(곡면 TET10)는 곧게 본다(`geometry_basis` 가 그렇게 말한다).
- REMAP 체인은 입력 덱 하나만 복사하므로 인클루드 덱을 펼칠 수 없다 — 체인에는 미리 펼친 한 파일을 준다(pyKooCAE 매뉴얼에 적었다 · 러너 코드는 손대지 않았다).
- extract-parts 의 인클루드 펼치기는 포함하는 파일의 폴더 기준이다(정본은 주 덱 폴더) — 이번 범위 밖이라 알리기만 한다.

## 교훈
- **「막아 둔 자리」를 풀면 그 막음을 지키던 시험과 문장이 거꾸로 선다.** 2차 솔리드 시험 40항 · 백엔드 시험 하나 · 카탈로그 5 · 도움말 5 · SKILL 2 · 매뉴얼 · pyKooCAE · StepForge 답신을 같이 뒤집었다(전제를 뒤집을 때 그 전제를 단정한 문장을 쓸어라 — 메모리).
- **관문의 바이너리를 확인하라.** 백엔드 pytest 는 `platform/backend/bin` 을 재므로 dev 빌드 관문만으로는 새 동작을 한 번도 안 쟀다 — 릴리스 빌드 뒤에야 빨개졌다.
- **조용한 실패는 돌려야 보인다.** 쪼갠 덱 실측이 없었다면 「옵션을 줄 때만 펼친다」는 결정만 짓고 rc 0 무편집 여덟과 빈 덱 하나를 그대로 두었을 것이다.
