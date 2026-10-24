# 결정 권장안 · contact 카드 결함 전부 · map 직렬 전처리 — 완료 보고서

> 사용자 요청 — 「권장재로 진행을 해줘」(10-23 저녁, 결정 아홉 묶음) → 「결함은 다 고쳐야지 그건 최우선이야. 그리고 c++작업이라도
> 고쳐야할건 고쳐야하고」 · 상시 지시 「업데이트 되었으면 당연히 빌드도 다 해야한다」
>
> 작성일: 2026-10-24
> 상태: 플랫폼과 SIF 사본 셋(빌드 · compute-node-images · `/opt`)까지 배포했다(바이너리 `0e7db58c` · `dist-20261024-000227Z` · 소스 `2e8b9e4`).
> **계산 노드 node001 · node002 는 VM 이 꺼져 있어 깔지 못했다**(10-19 부터 · 켜는 것은 사용자 결정).
>
> ⚠ 수치는 이 라운드에서 직접 잰 값이다. 솔버로는 하나도 못 쟀다(LS-DYNA 라이선스 10-16 만료).

---

## Executive Summary

### 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **기능명** | 결정 권장안(카탈로그 · CPU · HWAX · 요청서 · SIF) · contact 카드 결함 D1–D24 · map 직렬 전처리 |
| **기간** | 2026-10-23 저녁 ~ 10-24 |
| **커밋 수** | 결정 라운드 **7**(`6c20e57` · `ae8e94f` · `47a10e6` · `841065c` · `74aa501` · `cd3823c` · `e356154`) · 결함과 성능 **10**(`e7a2bed` · `b20d1ad` · `cd3891b` · `c1067b8` · `00693be` · `2cbfef0` · `2d801d9` · `9f80bf1` · `2e8b9e4` · `cb8a9ae`) + 이 문서 |
| **변경 규모** | 결정 라운드 15 파일 +500/−67 · 결함과 성능 47 파일 +2,248/−1,379 — contact 정본과 op `e7a2bed` 31 파일 +1,624/−1,174 · 소비자 셋 `b20d1ad` 7 파일 +142/−34 · map 다섯 6 파일 +281/−152 · YAML 키 순서 `2e8b9e4` 5 파일 +68/−19 · 나머지는 문서 |
| **장부** | `docs/01-plan/features/decisions-1023b.*` · `contact-cards-1023.{plan,checklist,context-notes}.md` · 결함 기록 `contact-card-defects-1023.findings.md` |

### 결과 요약

| 지표 | 결과 |
|------|------|
| **고친 결함** | **24** — 카탈로그 대조에서 기록한 11 · 코드를 읽다 더 나온 10(D12–D21) · 접촉 카드를 따로 세던 소비자 셋(D22) · 배포 뒤 살아 있는 잡에서 찾은 플랫폼 경로 둘(D23 · D24) |
| **빨라진 것** | map 매핑 단계 6.1–6.7 → **1.3–1.4 초**(20만 HEX8 · 최대 메모리 421 → 284 MB) · 산출 sha 그대로 |
| **엄격해진 것** | tiebreak 은 `option` 필수(option ≠ 1 이면 `nfls` · `sfls` 도) · assemble 의 contact 는 THERMAL · TIEBREAK · ERODING 거절 · 못 쓰는 Card 4 형 거절 · 못 읽는 숫자 · 모르는 · 빠진 action 은 rc 1 |
| **결정 권장안** | 3B 카탈로그 설명 54 고침 · 4A map 확장성 측정 · 4B 잡마다 `OMP_NUM_THREADS` · 8 HWAX `host.job_node` · `.nfs*` 제외 · 6B 요청서 초안(안 보냄) · SIF v121 · 5B 보류(메모리) |
| **신규 시험** | 단위 **128 → 140** · 회귀 파일 **100 → 101**(`test_contact_cards` 61항, A–T) · 기존 회귀에 단언 15(참조 검사 E 6 · cnrb2spring 2 · pidref B2 7) · 덱 op 스모크 **21 → 25**(contact) · 백엔드 **619 → 628**(실행기 · OMP 9) |
| **관문(릴리스 바이너리)** | 단위 140 · 회귀 101/101(개발 · compat 둘 다) · 도움말 사례 · 카탈로그 대조 · 백엔드 628 · 덱 지문(contact 만 의도대로 다름) · **플랫폼 키 순서 탐침 48 op 동일** · GLIBC_2.35 |
| **배포** | Drive `dist-20261024-000227Z` · health `2e8b9e4` 일치 · 스모크 넷(도구 73 · 리포트 35/35 · 그림 20/20 · 덱 op 25/25) · SIF v122 · **노드 대기** |

### Value Delivered

| 관점 | 내용 |
|------|------|
| **Problem** | contact op 과 그 카드를 고치는 op 들이 매뉴얼 카드 순서를 몰라 **덱을 조용히 틀리게** 썼다 — TIEBREAK 은 몰래 파손 없는 OPTION 1, Card C 는 한 칸 밀림, 값 반올림, 없는 키워드. 같은 꼴의 사본 셋이 `_MPP` 덱을 잘못 읽었고, 플랫폼에서는 `type` 을 준 contact create 가 **늘** 실패했다(카탈로그 예제는 create 를 버리고 rc 0). map 은 스레드를 늘려도 빨라지지 않았다 |
| **Solution** | 카드 자리 정본 하나(`ct_parseContacts`)를 모든 소비자가 쓴다 · 매뉴얼 순서로 쓴다 · 못 쓰는 형과 빠진 required 값은 조용히 채우지 않고 거절한다 · YAML 항목은 키 순서와 상관없이 읽는다 · map 은 두 번 돌던 직렬 전처리를 한 번으로 |
| **Function UX Effect** | 실패한 잡이 까닭을 그대로 보여 준다(「option 을 주어야 한다 … 1 = 영구 접착 · 2 = 파손 때까지 …」) · 플랫폼에서 contact create 가 돈다 · map 잡이 4.5배 빨리 끝나고 메모리를 덜 쓴다 |
| **Core Value** | 「조용히 틀린 덱을 내지 않는다」 — 모르면 거절하고, 바꾼 거동은 시험이 옛 바이너리에서 실패하는 것으로 못 박았다 |

---

## 1 — 결정 권장안 (10-23 저녁)

| # | 무엇 | 한 것 | 커밋 |
|---|---|---|---|
| 3B | 카탈로그 설명 | `contact` 키 112개를 Vol_I(R16)와 대조 — 틀린 54 고침(BT 는 「Bias tangential friction」 이 아니라 접촉 시작 시각 · SFSA 는 마찰이 아니라 강성 배율 등) · stabilize · stcx 자원 칸. 설명으로 못 고치는 코드 결함 11개를 따로 기록 | `841065c` · `74aa501` |
| 4A | map CPU 확장성 | 1–32 스레드가 모두 6.1–6.4 초 · CPU 110% — gdb 표본 여섯이 전부 직렬 전처리 안. 이것이 §3 으로 이어졌다 | (측정) |
| 4B | 잡마다 스레드 | 실행기가 없으면 `OMP_NUM_THREADS = 코어 ÷ 동시 슬롯`(이 박스 8, 이미 있으면 존중) · `env_snapshot.omp_num_threads` · 살아 있는 잡에서 8 확인 | `6c20e57` |
| 8 | HWAX 실행기 | 잡이 돈 노드를 `host.job_node` 로(`.job_<id>.node`, 글자 검사) · `.nfs*` 를 출력에서 뺀다 · 답신 6장 덧붙임(4B 는 V1 「설정이 비면 지금과 똑같다」의 예외 — **아직 안 전함**) | `ae8e94f` |
| 6B | stcx 결과 자동 반입 | SmartTwinMCP · stcx 대시보드에 결과 리포트 내려받기를 청하는 요청서 **초안**(안 보냄) | `47a10e6` |
| 1 | SIF | 카탈로그를 먼저 커밋한 뒤 v121 굽기(`252bd444` · 소스 `74aa501`) · `/opt` 사본 | `e356154` |
| 5B | 다각도 새 판 sphere | 조리법은 확인했다. 런마다 상태 4,952 개 · 약 35 GB 가 드는데 쓸 수 있는 메모리 12 GB · 스왑 39/39 GB 라 **보류** | `cd3823c` |

## 2 — contact 카드 결함 D1–D24

매뉴얼(Vol_I R16 *CONTACT 「Cards must appear in the exact order」)은 ID → MPP 1(→ `&` MPP 2) → Card 1·2·3 → 형이 요구하는 Card 4 →
THRM 1 → ORFR → 선택 카드 A–G 다. 빈 줄도 카드다.

| 묶음 | 결함 | 고침 | 커밋 |
|---|---|---|---|
| 카드 자리(파서) | 빈 줄을 건너뜀(D8) · `_MPP` 의 MPP 1 을 Card 1 로(D9) · 쉼표 자유 형식을 10칸으로 자름(D19) · Card C 를 6·7열로(D1) · 선택 카드 modify 가 Card 4 · THRM 을 지움(D7) | 파서가 카드 줄 자리를 든다(idLine · mppLines · cardLine · card4Lines · thrmLines · optLines) · 형마다 필수 카드 수 · 자리를 모르는 형은 `layoutKnown=false` 로 선택 카드를 읽지도 고치지도 않는다 | `e7a2bed` |
| 쓰기 | Card 4 · THRM 을 선택 카드 뒤에(D2) · FTOSA 생략 시 1.0(D3) · ERODING Card 4 없음(D6) · Card A 의 MAXPAR 1.025 · DEPTH 2 를 늘 씀(D10) · 값 반올림(D15 — 0.125 → 0.13) · tied_mortar 가 없는 키워드(D5) | 매뉴얼 순서 · FTOSA 0(= 0.5) · ERODING `0 1 0` · 안 준 칸은 0(= 형의 기본) · 옛 형식 글자가 같은 값이면 그 글자(골든 바이트 그대로), 아니면 10칸 안의 가장 정밀한 표기 · `AUTOMATIC_SURFACE_TO_SURFACE_MORTAR_TIED` | `e7a2bed` |
| contact op | TIEBREAK OPTION 생략 시 1 = 파손 없음(D4) · 뜻 있는 음수를 버림(D11) · 못 읽는 숫자를 조용히 버림(D16) · modify 가 Card 1 확장 칸 무시(D17) · remove 뒤 액션이 줄을 밀면 다른 접촉을 지움(D21) · detect 가 THRM · Card 4 를 안 씀(D12) · skip/subtract_existing 이 SET_SEGMENT 접촉을 못 알아봄(D13) · notes 13(D14) | option 필수(13/14 · DAMPING ±9/±11 · SOFT 2 · SINGLE/GENERAL 의 6 이상은 거절 — Remark 2) · 칸은 `std::optional` · rc 1 · 지울 번호를 모았다가 맨 끝에 다시 읽은 자리로 · detect 도 create 와 같은 카드 조립 · 세그먼트를 파트로 풀어 비교 · notes 13 은 코드대로(auto_create 와 상관없이 뺀다) 고쳐 적었다 | `e7a2bed` |
| 같은 정본을 쓰는 op | optimize 가 카드를 직접 셈 · stabilize 가 SOFT 2 와 MAXPAR 1.15(D18) · stabilize 가 목록을 돌며 다시 파싱(반복자 무효 — 미정의 동작) · TIEBREAK 에 SOFT 2(D20) · assemble 이 Card 1-3 만 쓰며 필수 카드 형을 냄 | 파서 자리로 고친다 · MAXPAR 안 씀 · 번호로 돈다 · TIEBREAK 는 SOFT 그대로 · assemble 은 THERMAL · TIEBREAK · ERODING 을 [ERROR] rc 1 | `e7a2bed` |
| 소비자 셋(D22) | `info` 참조 검사가 MPP 1 의 IGNORE 2 를 「세트 2 이 정의되지 않았습니다」로(`--strict` rc 1) · restack/merge 가 `_MPP` 접촉의 죽은 PID 를 놓치고 MPP 1 줄을 고쳐 씀(NS2TRK 3→2) · cnrb2spring 이 [manual] 을 [maybe] 로 낮춰 rc 0 · modelmeta 는 「SET_SEGMENT 200 이 덱에 없다」 | 셋 다 `ct_parseContacts` 의 카드 자리를 쓴다(modelmeta 는 이미 정본을 써서 `e7a2bed` 로 함께 고쳐졌다 — 옛 바이너리 실측) | `b20d1ad` |
| 플랫폼 경로(D23 · D24) | 파서가 `- action` 으로 시작하는 항목만 알아봄 — argbuild 는 JSONB 가 순서를 잃어 `type` 부터 써서 **플랫폼에서 type 을 준 create 가 늘 실패**, 카탈로그 예제는 create 를 앞 analyze 에 섞어 **버리고 rc 0** · 모르는 action 은 경고만 하고 rc 0 | `- ` 면 첫 키가 무엇이든 새 항목 · `action` 은 어디에 와도 된다 · 모르는 · 빠진 action 은 덱을 건드리기 전에 rc 1 | `2e8b9e4` |

D23 은 이번 고침 전부터 있었다 — 옛 배포본(`252bd444`)에 같은 YAML 을 줘도 같다. assemble 의 contact 와 다른 op 의 목록 파서는 `- ` 만 보고
항목을 가르므로 이 문제가 없었다(argbuild 꼴 YAML 로 확인).

**플랫폼 키 순서 탐침(10-24)** — 덱을 쓰는 48 op 의 카탈로그 예제를 「사람이 쓴 순서(argbuild 우선 키를 끈 판)」와 「플랫폼 순서(JSONB +
우선 키)」로 각각 돌려 산출을 대조했다. 새 바이너리는 **48 op 모두 같다.** 옛 바이너리는 contact 하나가 다르다(탐침이 D23 을 잡는다).
덱을 쓰지 않는 15 op(generate · battery · modelmeta · info · section …)은 이 탐침 밖이다.

## 3 — map 직렬 전처리

| 커밋 | 무엇 |
|---|---|
| `c1067b8` | step2 가 step1 의 색인 결과를 이어 쓴다 — 같은 입력으로 연결성 · 색인 · 절점 재정렬 · 경계 추출을 두 번 돌렸다 |
| `00693be` | 연결성 면 묶기에서 문자열 키(`"a_b_c_d"` → `std::map<string>` → 다시 `stoi`)를 뺀다 — 이웃 순서는 옛 키 문자열의 사전순 그대로 |
| `2cbfef0` | 색인 BFS 와 절점 재정렬이 요소 중심을 한 번만 잰다 |
| `2d801d9` | 경계 격자 만들기가 칸마다 `std::set` 을 만들던 것을 작은 정렬 배열과 `set_intersection` 으로 |
| `9f80bf1` | 평판 bbox 를 step3 에서 한 번만 잰다(같은 메시로 세 번 쟀다) |

이 세션에서 다시 잰 값(20만 HEX8 큰 arc · 32코어 · 옛 = 배포본 `252bd444`, 산출 sha 는 `$ Date` 줄을 뺐다):

| | 옛 | 새 | sha |
|---|---|---|---|
| map 평판 — 매핑 단계(3회) | 6.09 / 6.66 / 6.32 초 | 1.42 / 1.33 / 1.31 초 | `39a6a2af43c731d4` 같음 |
| map 평판 — 총 시간 | 7.29 / 7.94 / 7.54 초 | 2.69 / 2.58 / 2.53 초 | |
| 최대 메모리 | 421 MB | 284 MB | |
| map TET 100만 — 매핑 단계 | 7.06 초 | 1.78 초 | `64c63de199b5e6ed` 같음 |
| unfold — 벽시계 | 4.45 초 | 2.01 초 | `858a8d9361984df3` 같음 · 로그도 같음 |

바이트 대조는 하위 에이전트가 더 넓게 했다 — 모양 97건(성공 70 은 산출과 로그, 실패 27 은 rc 와 오류 문구) · 옵션 36건 · 옛/새 grid 소스를
나란히 빌드한 합성 메시 106종의 덤프(3.6 MB, 축 방향은 16진 부동소수까지)가 모두 같다. 세밀한 평판(160만 HEX8)은 11.98 → 5.98 초(1회).

## 배포

| 자리 | 상태 |
|---|---|
| compat 빌드 | `0e7db58c` · GLIBC_2.35 · `cli.sif` 안의 바이너리도 같다 |
| Drive | `dist-20261024-000227Z`(소스 `2e8b9e4`) — 그 전 게시 `dist-20261023-234230Z` 는 D23 을 고치기 전이라 이 판이 대신한다 |
| API · MCP | 살아 있는 잡이 0 인 것을 본 **결과에 걸어** 재기동 · health ok · `revision_matches_binary=True` |
| 스모크 | smoke(op 63 · 도구 73) · reports 35/35 · figures 20/20 · deckops **25/25**(contact 줄을 더했다 — 그 전 배포본에서 23/25 로 빨개지는 것을 봤다) |
| 살아 있는 잡 | option 없는 tiebreak → failed, `error_summary` 에 까닭 · option 2 → succeeded · MCP `describe_operation` 이 새 문장(option 필수 · ftosa · assemble 거절)을 낸다 |
| SmartTwinPreprocessor.sif | v122 굽기 rc 0 · 구운 sha = 스테이징 sha `0e7db58c` · BUILD_INFO 소스 `2e8b9e4` · Drive 업로드 · 메일 sent OK |
| compute-node-images · `/opt/apptainers` | 둘 다 `0e7db58c` · `/opt` 는 임시 이름으로 복사한 뒤 `mv` · 빌드본과 바이트가 같다 |
| 계산 노드 node001 · node002 | VM shut off(10-19 부터) — **못 깔았다** |

## 한계 (정직한 명시)

- **솔버로 안 쟀다.** 카드 고침은 매뉴얼 카드 순서와 칸 자리로 확인했다. LS-DYNA 가 고친 덱을 어떻게 읽는지는 미루어 본 것이다.
- **계산 노드에 안 깔았다.** VM 이 켜지면 노드에서 도는 잡은 옛 판 바이너리를 쓴다 — 켜면 잡보다 노드 배포가 먼저다.
- **assemble 은 필수 카드 형을 만들지 않는다**(거절한다). 단독 contact 의 카드 조립을 옮기는 일은 따로 정할 수 있다.
- 못 쓰는 형은 거절한다 — TIEBREAK_USER · `TIEBREAK_NODES/SURFACE_…` · THERMAL_FRICTION · ORTHO_FRICTION · DRAWBEAD · CONSTRAINT · RIGID · INTERFERENCE ·
  COMPOSITE/LUBRICATION · TIED_WELD · AUTOMATIC_SINGLE_SURFACE_TIED · CONTRACTION_JOINT · TIEBREAK OPTION 13/14 · DAMPING ±9/±11.
- 플랫폼 키 순서 탐침은 덱을 쓰는 48 op 만 봤다 — 덱을 안 쓰는 15 op 은 안 봤다. 탐침은 아직 관문이 아니다(스크래치).
- 덱 지문 관문의 `cleanup_report.json` · `extract_report.json` 은 **같은 바이너리로도 매번 다르다** — 고치지 않았다.
- map 의 다음 병목(세밀한 평판 쪽 직렬 일)과 step2 뒤 풀린 임시 메시를 가리키는 포인터(예전부터 · 지금은 아무도 안 읽는다)는 손대지 않았다.
- IdRefs 는 접촉 머리 카드를 따로 센다(바르게 센다 — 그대로 뒀다).
- 5B 다각도 새 판 sphere 는 여전히 안 쟀다.

## 교훈

- **시험이 결함 거동을 기대값으로 적고 있었다**(catalog_binary_parity · remaining_surfaces H6 · yaml_common_rules). 고친 뒤 빨개진 시험은 낡은
  기대값일 수 있다 — 바꾼 단언마다 옛 바이너리에서 FAIL, 새 바이너리에서 PASS 를 봤다.
- **같은 카드를 직접 세는 사본은 같은 결함을 갖는다.** 파서를 고치면 그 카드를 읽는 다른 자리를 다 찾는다 — 셋(D22)이 그렇게 나왔다.
- **관문이 전부 초록이어도 플랫폼 경로는 깨져 있을 수 있다.** D23 은 재기동 뒤 살아 있는 잡으로 찾았다. 스모크가 부르지 않는 op 은 플랫폼에서
  안 잰 것이다. 바이너리 회귀는 사람이 쓴 YAML 만 써서 못 봤다 — 플랫폼이 만드는 YAML(`argbuild._dump_yaml`)로도 잰다.
- **덱 지문은 다른 op 의 수가 아니라 다른 파일을 본다** — 매번 다른 보고 둘이 늘 「다른 op 2」를 만든다.
- **스레드를 늘리기 전에 시간이 어디서 가는지 본다** — map 은 같은 일을 두 번 하고 있었다(gdb 표본).

## 다음 할 일

### A. 결정이 필요한 것

1. **계산 노드 node001 · node002 를 켤지** — 켜면 잡보다 먼저 `deploy_apptainers.sh --image SmartTwinPreprocessor.sif` → 노드에서 sha(`0e7db58c`) →
   SmartTwinMCP 에 알림. 켜지 않으면 지금 그대로다(노드에서 도는 잡이 없다).
2. **HWAX 답신 6장을 보낼지** — ③ A · `.nfs*` · ⚠ 4B 가 V1 「설정이 비면 지금과 똑같다」의 예외라는 것(실행기 없는 prod 의 스레드 수가 바뀐다).
3. **SmartTwinMCP 결과 내려받기 요청서(`47a10e6`)를 보낼지.**
4. **5B 다각도 새 판 sphere** — 런마다 약 35 GB. 10-24 실측 이 박스 available 43 GB(free 12 · 캐시 34) · 스왑 38/39 GB 사용 중이라
   런 하나는 여유 8 GB 안팎으로 빠듯하다. 지금 돌릴지 · 메모리를 비우고 돌릴지 · 다른 박스에서 돌릴지 · 미룰지.
5. **assemble 이 THERMAL · TIEBREAK · ERODING 을 만들게 할지** — 지금은 거절하고 단독 contact 로 보낸다.
6. **못 쓰는 접촉 형을 지원할지**(쓸 일이 있는 형만) — THERMAL_FRICTION · ORTHO_FRICTION · TIEBREAK_USER · OPTION 13/14 등.
7. 앞서 미룬 것 — 선택지 4(stcx 결과 자동 반입) · 5(DataHub 핫스팟 칸) · 결정 7(DataHub 칸) · 9(작은 것 둘).

### B. 다른 쪽을 기다리는 것

8. HWAX NFS 판정 — HWAXProd 측정(H5).
9. stcx-smarttwin — 요청자의 답이 필요한 확인 사항 4건(I-3 — 도구 실명 · `model_file` · `get_job_details` 를 같이 부를지 · 첫 제출 응답 원문).
   체크리스트에 열려 있고, 요청자에게 전해졌는지는 장부에 없다 · 운영 반영 확인 뒤 `get_job_details` 호출을 뗄지 · 라이브 제출은 아직 한 번도 안 돌았다.
10. StepForge Q13 — TIM 대기.
11. 온톨로지 이식 — 실제 허브에서 한 번 받기(S1-6) · 붙은 수 · 못 붙은 수 실측 보고(S4-3) · `dev_revision` 을 허브에(S6-1).
12. 셸 층 묶기(`5a0fbd6`) — 사용자 솔버 시험.

### C. 지금 할 수 있는 개발 일 (권장 순서)

13. **플랫폼 키 순서 탐침을 상시 관문으로** — 오늘 쓴 탐침(48 op · 옛 바이너리에서 contact 를 잡는다)을 회귀에 넣고, 덱을 안 쓰는 15 op 은
    산출(JSON · CSV · SVG)로 잰다. 작고 D23 같은 결함이 돌아오는 것을 막는다.
14. **덱 지문의 보고 JSON 잡음 가리기** — 두 파일이 매번 다른 까닭(임시 경로 · 시각)을 보고 가린다. 진짜 차이를 숨기지 않게.
15. **map 다음 병목** — 세밀한 평판(160만 HEX8) 매핑 5.98 초 중 `analyzeSourceMesh` 약 1.0 · step4 준비 약 1.9 · `reorientMappedElements` 약 2.1 초
    (`std::map` 찾기). 같은 규율(산출 바이트 동일)로.
16. **map 의 풀린 포인터** — step2 뒤 `indexer_.indexedElements_` · `boundary_` 면 목록이 풀린 임시 메시를 가리킨다. 지금은 아무도 안 읽지만 덫이다 — 비워 둔다.
17. **플랫폼 op 스모크 범위** — 덱 op 스모크는 6 op 만 부른다. 63 op 을 플랫폼에서 한 번씩 부르는 스모크를 둘지(13 은 바이너리 · argbuild 만 본다).
18. (작음) IdRefs 의 접촉 머리 카드 세기를 정본(`ct_parseContacts`)으로.

### D. 라이선스가 돌아오면

19. 솔버로 잰다 — contact 카드 고침(Card 4 · THRM 순서 · Card C 열 · FTOSA · tiebreak OPTION) · optimize Card 3 고침 · 셸 층 묶기 · stcx `ncpu` 기본값.
