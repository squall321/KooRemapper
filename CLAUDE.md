# KooRemapper(DynaForge) — 이 리포에서 일할 때의 규칙

## SP(StandardPlatform) 키트는 늘 최신판을 받는다
작업을 시작할 때 SP main HEAD 와 키트 판(`KIT_VERSION`) · `CHANGES.md` 를 확인하고, 바뀌었으면 맞춘다(사용자 지시 2026-10-31).

- **확인** — `git -C external/StandardPlatform fetch -q origin && git -C external/StandardPlatform log --oneline HEAD..origin/main` 이 비었는지,
  `external/StandardPlatform/backend/app/modules/coreapi/kit/sp_core_pull.py` 의 `KIT_VERSION` 과 `kit/CHANGES.md` 맨 위 판이 우리 수신부
  (`platform/backend/app/runner/sp_core.py` 의 `KIT_VERSION`)와 같은지 본다.
- **바뀌었으면** — 서브모듈을 올리고(경계 시험 `platform/backend/tests/test_external_boundary.py` 의 고정 커밋도 같이), 키트 지시서
  `01-AI-GUIDE.md` · `UPGRADE.md` 대로 받는 쪽(층 1 `sp_core.py` · 층 2 `app/modules/ontology/services.py`)을 맞춘 뒤 시험장 8단계
  (`tests/test_sp_testbed.py`)와 규칙 시험(`tests/test_sp_core_rules.py` · `tests/test_sp_layer2.py`)을 돌린다. 키트가 그대로여도
  `coreapi` 가 바뀌었으면 받는 쪽에 닿는지 본다(응답 칸 · 오류 코드).
- 같은 SP 를 받는 StepForge 와 **같은 커밋**에 둔다 — 올릴 때 그쪽에 알린다.
- 기록 — 2026-10-30 키트 2026-10-21 판으로 다시 지은 것은 `docs/01-plan/features/sp-receive-1030.plan.md`.
