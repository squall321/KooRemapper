# 컨택 그래프 · 전각도 핫스팟 · 세트 합치기 — 1·2·3 완료 보고서

> 사용자 요청 — 「파트간의 컨택 관계로 그래프를 그리는게 가능한지와 전각도 낙하 데이터가 핫스팟 클러스터 기능까지도 다 올라오고
> 조회도 되는지」 → 조사 답의 선택지 1·2·3 을 **「꼼꼼히」** → 「ㄱㄱ」 · 상시 지시 「업데이트 되었으면 당연히 빌드도 다 해야한다」
>
> 작성일: 2026-10-23
> 상태: 플랫폼까지 배포했다(`252bd444` · `dist-20261023-115800Z` · 스모크 4종 통과). **SmartTwinPreprocessor.sif 굽기는 자동 모드 분류기가
> 막아 사용자 실행 대기**다 — 그 전까지 pyKooCAE REMAP 체인은 10-17 바이너리(`cd07c327`)로 돈다. 계산노드 둘은 지금 응답이 없다(§배포).
>
> ⚠ 수치는 이 라운드에서 직접 잰 값이다.

---

## Executive Summary

### 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **기능명** | 파트 접촉 그래프(결과 · 덱) · 전각도 낙하 핫스팟 일급 조회 · `*SET_…_ADD` 세트 해석 |
| **기간** | 2026-10-23 (하루) |
| **커밋 수** | **6개**(`234ad04` · `f1520ba` · `fe82dd3` · `d70ccc7` · `9e8999f` · `ab19ef9`) + 이 문서 |
| **변경 규모** | 기능 다섯 커밋 33 파일 **+2,703 / −262** — C++(생성 도움말 포함) 10 파일 +542/−176 · C++ 시험·회귀 4 파일 +470/−6 · 백엔드 3 파일 +470/−35 · 백엔드 시험 2 파일 +350/−4 · 프런트 5 파일 +777/−19 · MCP·카탈로그·문서 나머지. 관문 `ab19ef9` 1 파일 +60/−6 |
| **장부** | 계획 `docs/01-plan/features/contact-hotspot-1023.{plan,checklist,context-notes}.md` |

### 결과 요약

| 지표 | 결과 |
|------|------|
| **고친 것** | 조용히 틀린 값 셋(하중경로 값이 전부 null · 없는 각도를 물으면 다른 각도의 그래프 · 세트 합치기 0쌍/틀린 쌍) + 짓다가 돌려 보고 찾은 결함 **다섯**(§결함) |
| **새로 조회되는 것** | sphere 핫스팟(각도별 · 포락) · 파트쌍 × 각도(위치) 접촉 프로파일 · 하중경로 그래프 · 새로 읽는 최상위 키 **열**(`PARSER_READS`) |
| **새로 보이는 것** | 하중경로 층 그래프 · 「접촉 전개」 히트맵(칸 → 그 각도의 그래프) · sphere 핫스팟 포락 표 · 덱 연결도 인접 행렬 · 미해석 접촉 목록 |
| **정본으로 모은 것** | 세트 해석 `src/commands/set_members.h`(`ct_setMembers` · `ct_setHas`) — modelmeta · contact · optimize 셋이 쓴다 |
| **신규 시험** | 단위 **112 → 128** · 회귀 파일 **99 → 100**(`test_set_add_resolution`) · 백엔드 `test_report_contact_hotspot` 18항 + `test_report_blocks` 에 새 판 sphere · `reports_smoke` **24 → 35** |
| **관문(릴리스 바이너리)** | 단위 128/128 · 회귀 100/100 · 도움말 예제 · 카탈로그 대조 · 백엔드 619 passed · 덱 바이트 같음(다른 것 둘은 리포트 JSON 의 임시 폴더 경로뿐) · GLIBC_2.35 |
| **배포** | Drive `dist-20261023-115800Z`(소스 `9e8999f`) · health `revision_matches_binary=True` · smoke(op 63 · 도구 73) · reports 35/35 · figures 20/20 · deckops 21/21 · **SIF 대기** |

### Value Delivered

| 관점 | 내용 |
|------|------|
| **Problem** | 전각도 낙하 리포트는 반입되는데 핫스팟 · 파트쌍 접촉을 조회할 수 없었고, 하중경로는 값이 **전부 null** 이었다. 없는 각도를 물으면 **다른 각도의 그래프를 그 각도 이름으로** 돌려줬다. `*SET_PART_ADD` 로 묶은 접촉은 연결도에서 0쌍으로 사라졌고, `*SET_SEGMENT_ADD` 는 엉뚱한 파트쌍을 냈다 |
| **Solution** | 생성기의 압축 꼴을 읽는다(sphere · impact 이름이 또 다르다) · 없는 값은 지어내지 않고 null + 까닭 · LS-DYNA 규칙대로 푸는 세트 해석 정본 하나 · 화면 넷 |
| **Function UX Effect** | 각도별 핫스팟과 「파트 × 기준마다 가장 센 각도」 포락 · 히트맵 칸을 누르면 그 각도의 접촉 그래프 · 786쌍 덱은 행렬로 · 풀지 못한 세트는 접촉 · CID · 까닭과 함께 목록 |
| **Core Value** | 「조용히 틀린 값을 내지 않는다」 — 못 푸는 세트와 압축본에 없는 값은 **못 풀었다 · 없다고 말한다** |

---

## 1 — 조용히 틀린 값

| | 무엇 | 실측(고치기 전) | 고침 | 커밋 |
|---|---|---|---|---|
| 1-A | 하중경로 읽기 | HTML 은 압축 꼴(sphere `pf`·`tw`·`ti` · impact `peak_f`·`total_w`·`total_imp`·`conf` · 흐름 `ke_init` · 노드 `id`)인데 중립 이름만 읽어 **값이 전부 null** · 요청한 각도에 상세가 없으면 **첫 흐름을 그 각도 이름으로** | 세 꼴을 다 읽는다 · 없으면 `energy_flow: null` + `available_case_keys` · 실제로 쓴 케이스 `flow_case_key` · 압축본에 없는 칸만 `form_note` 에 | `f1520ba` |
| 1-B | 세트 합치기(C++ 공용 파서) | `*SET_PART_ADD` → **0쌍 · 미해석 0** · `*SET_SEGMENT_ADD` → 멤버 세트 ID 를 절점으로 읽어 (1,3) 대신 **(2,3)** · contact · optimize 도 같은 조회 | 정본 해석기 — `_ADD` 합집합 · PSID 음수 범위(PART) · 없는 세트는 빼고 `note` · 재귀 · 순환 · `_INTERSECT` · `_COLLECT`(모든 정의가 COLLECT 일 때만) · `_GENERAL`/`_ADVANCED`/`_COLUMN` 은 미해석(`unresolved_detail`) | `234ad04` |
| 1-C | 회귀 고정본 | 이 박스의 sphere 고정본은 전부 옛 판(12키)이라 관문이 초록 — 새 판은 23키 중 **9개를 안 읽었다** | 운영 이미지로 만든 새 판 고정본 `/data/koopark/report_fixtures/sphere_hotspot_v1018`(README 에 출처) · 안 읽는 것 9 → 2(`device_mesh` · `set_report` — 화면 전용) | `f1520ba` |

살아 있는 플랫폼에서 — `*SET_PART_ADD` 덱의 연결도가 (1,3) · (2,3) · (3,4) 를 내고, `_GENERAL` 세트를 가리키는 접촉은 까닭과 함께 미해석으로 나온다.

## 2 — sphere 핫스팟 · 접촉 프로파일 일급 조회

- **`/hotspots`(sphere)** — 각도 런마다 실린 압축 꼴(`results[i].hotspot`)을 deep 과 같은 평탄 목록으로. 새 판 고정본에서 13항목 · 58군집 ·
  포락 13(파트 × 기준마다 가장 센 각도 · 그 값 · 군집이 난 각도 수) · `case_key` 로 한 각도만 · 생성기 상한 문구(`cap_note`).
  압축본에 없는 값(부피 · 평균응력 · 피크요소)은 null 이다.
- **`/contact_profile`(sphere · impact 같은 꼴)** — 쌍마다 최대 |값| 과 그 각도 · 축 요약(MCP 기본 세기 순 10) · `case_key` 를 주면 그 각도의
  파트쌍 엣지 전부 · 히트맵 행렬(상한 120,000칸). impact 실리포트 23쌍 × 25위치 · 새 판 sphere 22쌍.
- 새 키 읽기 — `unit_system` · `tool_builds` · `contact_trust` · `hotspot_parts` · `hotspot_mesh(_note)` · `hotspot_cap_note` · `energy_flows_note` · `positions`.
- MCP — `report_contact_profile`(73번째) · `report_hotspots` 에 `case_key` · `report_energy_flow` 설명 · TOOLS.md · SKILL.md · README · CLAUDE_DESKTOP.

## 3 — 그림

- 「에너지·접촉」 탭 — 하중경로 층 그래프(충격체에서 너비 우선으로 층을 매기고 엣지 굵기 = 피크 접촉력).
- 「접촉 전개」 탭(새) — 파트쌍 × 각도(위치) 히트맵(pf · ti · tw). 빈 칸은 「그 각도에 그 접촉이 없다」(0 이 아니다). 칸을 누르면 그 각도의 그래프.
- 「핫스팟」 탭이 sphere 를 그린다 — 포락 표 + 각도 칸.
- 덱 연결도 — 그래프/행렬 전환(엣지가 150 을 넘으면 행렬이 기본) · 미해석 접촉 목록과 CID.

Playwright 로 네 화면을 봤다 — 새 판 sphere(핫스팟 · 접촉 전개 · 각도 그래프 · 하중경로) · impact 히트맵(23×25) · 61파트 덱 786쌍 행렬 ·
ADD 세트 덱의 미해석 목록.

## 결함 — 짓다가 돌려 보고 찾은 것 5건

| # | 무엇 | 어떻게 나왔나 | 커밋 |
|---|---|---|---|
| 1 | ★optimize 가 `*CONTACT_…_ID` 접촉의 **Card 3 SFSA 칸(슬레이브 강성 배율)에 SOFT=0** 을 썼다 — 보고는 「SOFT=1->0」 | 시험 덱을 `_TITLE`(접촉에는 없다 — `info --strict` 가 잡았다)에서 `_ID` 로 바꾸다 | `fe82dd3` |
| 2 | modelmeta 연결도 제목에 CID(1–10열)가 붙었다 | 같은 때 | `fe82dd3` |
| 3 | impact 압축본의 엣지 이름이 sphere 와 또 다르다 — sphere 꼴만 맞췄다면 impact 하중경로는 여전히 null | impact 실리포트로 돌려서 | `f1520ba` |
| 4 | MCP 문서의 도구 수가 72 로 낡았다 | 카탈로그 대조 관문 | `d70ccc7` |
| 5 | `reports_smoke` 24/24 의 어느 항도 새 도구를 부르지 않았다 — 도구 수만 셌다 | 배포 뒤 관문이 무엇을 부르는지 봤다 | `ab19ef9` |

## 배포

| 자리 | 상태 |
|---|---|
| compat 빌드 | `252bd444` · GLIBC_2.35 |
| Drive | `dist-20261023-115800Z` · 소스 `9e8999f` · 옛 묶음 `dist-20261016-222746Z` 정리(보존 4) |
| API · MCP · 프런트 | health ok · `revision_matches_binary=True` · 도구 73 · dist 재빌드 |
| 스모크 | smoke(op 63 · 도구 73) · reports 35/35 · figures 20/20 · deckops 21/21 |
| SmartTwinPreprocessor.sif(빌드 폴더 · compute-node-images) | 10-23 11:19(UTC)에 다시 구워졌지만 안의 바이너리는 10-17 의 `cd07c327` — **굽기 대기** |
| `/opt/apptainers` | `cd07c327` |
| 계산노드 node001 · node002 | Slurm `down*`(Not responding) · ssh 도 닿지 않는다 — 지금은 깔 수 없다 |

굽기는 root 로 돌고 Drive 업로드와 메일까지 하므로 자동 모드 분류기가 「Production Deploy」로 막았다(10-16 과 같다). 우회하지 않았다.
굽기 앞에 다른 굽기 프로세스와 Slurm 잡이 없음을 봤고, 굽기 스크립트의 스테이징 자동 갱신 · sha 검증 훅이 그대로 있음을 봤다.

## 한계 (정직한 명시)

- **실제 다각도 새 판 sphere 리포트로는 안 쟀다.** 고정본은 런 하나로 만들어 각도가 하나다. 여러 각도는 합성 시험(생성기 압축 함수의 꼴)과
  impact 25위치로만 쟀다.
- 압축본에 없는 값은 null 이다 — sphere 군집의 부피 · 평균응력 · 피크요소, 원해상도 피크 · confidence · first_engage_t, 전파 순서.
  솎은 시계열에서 피크를 다시 재지 않는다(생성기 규칙).
- 하중경로 상세는 생성기가 상위 60 각도에만 싣는다 — 나머지 각도는 null + 까닭이고, 그 각도의 파트쌍 접촉은 `contact_profile` 에 있다.
- 세트 — `_GENERAL` · `_ADVANCED` · `_COLUMN` 은 풀지 않고 미해석으로 센다 · `_ADD` 의 음수 범위는 PART 만 · 범위는 덱에 정의된 세트만 고른다.
- 솔버로는 안 쟀다(LS-DYNA 라이선스가 10-16 에 만료) — optimize Card 3 고침은 카드 칸 위치로 확인했다.
- 덱 바이트 대조 관문은 리포트 JSON 의 임시 폴더 경로를 「다름」으로 센다(고치지 않았다).
- 61파트 덱의 기하 탐지는 gap 0.05 에서 **786쌍**(0.1 에서 1134)이다 — 조사 답에서 말한 700 은 DB 에 남은 더 옛 판의 값이었다.
- API 를 재기동할 때 「살아 있는 잡이 없다」 확인의 결과에 묶지 않았다. 그때 running 행이 하나 있었고, 「worker restarted」로 닫힌 잡은 없었다.

## 교훈

- 생성기가 플랫폼보다 앞서면 관문은 옛 고정본으로 초록이다 — 고정본은 **운영 이미지로** 만든다.
- 시험이 두 관심사를 섞으면(쌍을 제목으로 찾기) 옛 바이너리에서 엉뚱한 이유로 빨개진다 — 쌍은 접촉 순번으로 고른다.
- 세는 관문은 안 부른 도구도 초록이다 — 새 도구는 **값으로** 재는 항을 같이 넣는다.
- 고치기 전에 층마다 넘기는 값을 본다 — 파서를 `axis_top` 없이 불러 버그처럼 보였던 축 요약은 MCP 경로에서 맞았다.

## 남은 것

- SmartTwinPreprocessor.sif 굽기(사용자) → `/opt/apptainers` 사본 → 계산노드가 살아나면 `deploy_apptainers.sh --image` · 노드에서 sha → SmartTwinMCP 알림.
- 조사 답의 선택지 4(stcx 자동 반입) · 5(DataHub 핫스팟 칸)는 이번 범위 밖이다.
