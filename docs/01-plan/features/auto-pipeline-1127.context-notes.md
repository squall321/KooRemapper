# 자동 파이프라인 맥락 — DynaForge 원천 + 전각도 낙하 해석

계획 `auto-pipeline-1127.plan.md` · 체크리스트 `auto-pipeline-1127.checklist.md`.

## 1. 사용자 결정(2026-11-27) — 고른 선택지의 설명 문장이 규격이다
- 세션 잇기 「세션에 과제 · 개발 단계 칸」 — 세션에 허브 과제(과제명)와 개발 단계 칸을 새로 둔다. 사람이 콘솔 · MCP 로 넣고, 과제는 판 확정과
  같은 규칙(과제명 · 과제코드 · 옛 과제명 · 별칭 → 과제 하나, 못 풀면 거절)으로, 개발 단계는 dev_rev 꼴로 검사한다. 비어 있으면 auto_changes 가
  null 로 싣고 refs 에 세션 id 와 linked_cad 의 StepForge 과제 id 를 함께 싣는다.
- 판정 「기준 없이 수치만」 — profile 둘(전각도 Fibonacci 162 · 26 방향 — 높이 · 바닥 · 시간은 stcx 제출 op 의 기본값, 바꾸려면 profile 을
  고친다). verdict 는 늘 unknown 이고 metrics 에 최대 응력 · 최대 가속도 · 소성 핫스팟 수 등을 단위와 함께 싣는다(limit 없음). 기준과 출처가
  정해지면 그때 더한다.
- 신원 「auto_* 만 모두 읽기」 — 설정에 적은 게이트웨이 서비스 계정으로 부를 때 auto_* 도구에서만 모든 세션 · 리포트를 읽게 연다(다른 도구 ·
  사람 신원은 그대로). 제출 계정은 운영 답 전까지 auto_profiles 의 service_identity 를 false 로 두고 auto_submit 은 permission 으로 막는다.

## 2. 대 본 것(11-27)
- 세션 칸 · 파일 sha256 · `updated_at` 의 움직임 · 낙하 사슬의 op 인자 · 리포트의 단위계 · MCP 오류 꼴 · 신원 전달은 계획 1절.
- 덱 하나를 고르는 규칙은 계약에 없다 — v1 은 「세션 입력 파일 가운데 덱 꼴이 하나」 일 때만 준비로 본다(둘 이상이면 무엇을 낼지 모른다 —
  missing input 에 목록). 포털에 알린다.
- sphere 리포트의 수치 단위는 생성기가 검출한 단위계에서 읽는다. 단위계를 모르면(검출 안 됨) 그 수치는 싣지 않고 notes 에 까닭 — 계약 §4-4
  「단위가 비지 않는다」 와 「지어내지 않는다」 를 함께 지킨다.

## 3. 포털과 맞춘 것 · refs 결정(2026-11-27)
- hwaxportal-71 — 포털 검증기(contract.py)에 대 봤고 꼴이 맞다. 맞출 것 셋 — ① ready 키는 `deck_ready`(포털 규칙 `kooremapper_mcp.deck_ready`) ②
  inputs 의 sha256 은 채운다(포털 입력 지문은 원천 · kind · ref · sha256 — at 은 안 쓴다, sha 가 null 이면 같은 ref 의 새 덱이 새 실행이 안
  된다) ③ 같은 세션이면 refs 를 늘 같은 꼴로.
- ③ 은 고른 선택지 문장(「refs 에 세션 id 와 linked_cad 의 StepForge 과제 id 를 함께」)과 부딪혀 다시 물었다 — 사용자 「refs 는 세션 id 만」:
  refs 는 {dynaforge: 세션 id} 하나로 고정하고 StepForge 과제 id 는 refs 밖 `links.step_forge`(없으면 빠짐)로 따로 싣는다. 같은 세션은 칸을
  채우거나 CAD 를 잇거나 refs 가 같아 포털이 막힘 줄을 걷는다.
- 세션 파일의 sha256 은 올릴 때 채운다(`sessions/services.py`). 빈 옛 행은 auto_changes 가 처음 볼 때 한 번 재서 남긴다.
