# KooD3plotReader 에 드리는 결함 보고 — 단면 영상 · 상태 읽기 (2026-10-28)

**보내는 곳** DynaForge(KooRemapper) — 낙하 트윈 P0 실측 중에 발견했습니다.
**받는 곳** KooD3plotReader — 운영 이미지 `SmartTwinPostprocessor.sif` 의 `koo_deep_report` · `unified_analyzer`(이미지 VERSION `282630b`, 아래 인용 파일은 HEAD `176857e` 와 같습니다).
**성격** 결함 보고와 개선 제안입니다. 고치는 방법과 순서는 KooD3plotReader 가 정합니다.
**증거** `/data/koopark/drop_twin_p0/sv_proto/` — 런별 meta · time · log · watch.json, 운영과 바이트 단위로 같은 cfile, 비교 프레임. 측정 전체는 KooRemapper `docs/04-report/drop-twin-p0-1028.report.md` §5 입니다.

## 1. 한 줄
운영 단면 영상과 상태 읽기가 **오류 없이 틀린 결과**를 냅니다. 영상 24개 중 7개가 어느 프레임부터 응력 0 으로 그려졌고, d3plot 상태 4,952개 중 1,546개만 읽고 rc 0 으로 끝난 경우가 있었습니다.

## 2. 결함
### K-1 (높음) LS-PrePost 배치가 응력 0 프레임을 낸다 — 비결정
- 재현 조건 — `Test_005_Fibonacci_100` 의 `Run_20260602_093237_801e2b`(4,952 상태), `lspp412_mesa` · Xvfb · 1280×720, 운영 cfile 그대로.
- 24개 중 7개 영상이 어느 프레임(예 1518, 4697)부터 끝까지 「min = 0, max = 0, at node# 0」 이고 색 막대도 전부 0 입니다. 같은 cfile 을 다시 돌리면 정상입니다.
- 확인 — `sv_proto/last_frame_B1_zero_stress.png` 대 `sv_proto/last_frame_N3za_normal.png`(같은 시각 정상 영상은 max 131.1).
- 상한 탓은 아닙니다 — LS-PrePost VmPeak 4.6–5.2 GiB(상한 12 GiB). 시작 시점이 MemFree 약 1.0–1.3 GB 와 겹친 일이 셋, 반례(0.8 GB 에서 정상)가 하나라 원인은 모릅니다.
- 지금 아무도 못 잡습니다 — 렌더 뒤 0 프린지 검사가 없습니다. `UnifiedAnalyzerRender.cpp:605-616` 은 렌더 전 상태 5개 표본으로 범위만 잡고 max ≤ 0 이면 자동 범위로 조용히 넘어가고, `detectFringePixelBBox`(230-318)는 자르기에만 쓰입니다.
- 제안 — 영상마다 마지막(또는 표본) 프레임의 max 를 검사해 0 이면 다시 그리거나 실패로 표시. 원인 조사.

### K-2 (높음) 상태 읽기 예외를 삼키고 성공으로 끝낸다
- `src/parsers/StateDataParser.cpp:54-74` — catch 가 로그 없이 `done = true` 로 그때까지 읽은 상태를 돌려줍니다. 43-52 의 크기 검사도 말없이 멈춥니다.
- 호출 쪽이 `result.success = true` 로 둡니다(`src/D3plotReader.cpp:217-219`). 그래서 316-320 의 경고는 뜨지 않고, 마지막 「Completed: N total states loaded」(325)에는 견줄 기대값이 없습니다.
- 실측 — software 백엔드가 상태 4,952개 중 1,546개만 싣고 rc 0(186.5 초)으로 끝났습니다.
- 제안 — 예외를 로그하고 실패로 올리기. 기대 상태 수(헤더 · 가족 파일 크기)와 읽은 수를 견줘 다르면 실패.

### K-3 (중간) 가족 파일마다 스레드 — 상한이 없다
- `src/D3plotReader.cpp:161-168, 274-280` — `std::async(std::launch::async, …)` 를 가족 파일마다(이 덱은 249개) 한꺼번에 띄웁니다. `hardware_concurrency()` 는 찍기만 합니다.
- `std::system_error: Resource temporarily unavailable` 를 아무도 잡지 않아 SIGABRT(rc −6)로 끝납니다(`UnifiedAnalyzer.cpp:72` → `examples/unified_analyzer.cpp:1368`). 12 GiB 주소 공간 상한 아래 `koo_deep_report` 분석 단계에서 실측했습니다.
- 제안 — 코어 수를 상한으로 하는 스레드 풀과 예외 처리.

### K-4 (중간) 렌더가 실패해도 rc 0
- `examples/unified_analyzer.cpp:1471` 은 렌더 잡 · 파트별 렌더가 실패해도(1409-1413, 1434-1438) 0 을 돌려줍니다. `koo_deep_report` 의 2차 패스도 RuntimeError 를 무시합니다(`core/d3plot_reader.py:172-175`).

## 3. 느린 까닭 — 개선 제안(결함 아님)
측정 — 영상 하나(4,952 프레임)가 NVMe 사본에서 약 100 초, `/data` HDD 에서 157–312 초입니다. 프레임당 20 ms 중 래스터가 약 10 ms 입니다.
- **P-1 개관 영상 중복** — `core/d3plot_reader.py` `_build_yaml`(223~)의 개관 render_jobs(324-335)에 render_only 검사가 없어, 2차 패스(154-163)에서 개관 3개를 또 만듭니다(각도당 6개).
- **P-2 세션 폭증** — `scripts/post_analyze.sh:77 · 869-886` 이 per-part · x y z · von_mises 를 켜고, iso_clip 은 기본으로 켜져 있으며(`__main__.py:189` · `render/job_builder.py:45`), per-part 는 대상이 없으면 저절로 켜집니다(`__main__.py:1009-1013`). 23파트 × 3축 × (단면 + iso_clip) 138개 + 개관 6개 = **각도당 LS-PrePost 세션 144개**입니다. 영상마다 Xvfb 와 lsprepost 를 새로 띄우고(`LSPrePostRenderer.cpp:560-563 · 664 · 723 · 373-378`) 세션마다 d3plot 18 GB 를 다 읽습니다.
- **P-3 모든 상태가 프레임** — movie 명령(`LSPrePostRenderer.cpp:303-325 · 657-659 · 716-718`)에 상태 건너뛰기가 없습니다. `RenderOptions` 의 start_state · end_state · state_step(`LSPrePostRenderer.h:198-200`)과 YAML `states:`(`UnifiedConfigParser.cpp:886-890`)는 읽히지만 렌더에 쓰이지 않습니다. 4,952 프레임이 24 fps 로 206 초짜리 영상이 됩니다.
- **P-4 한 세션 여러 단면** — x · y · z 를 한 세션에 그리면 NVMe 에서 7–10% 빠릅니다. HDD 에서는 열기를 아껴 더 큽니다.
- 관찰 — GPU 는 래스터(약 절반)만 줄입니다. 세션 수와 프레임 수를 줄이는 쪽이 훨씬 큽니다.

## 4. 우리 쪽 맥락
낙하 트윈(KooRemapper `docs/01-plan/features/drop-twin-1028.plan.md`)에서 단면 영상은 유지하기로 했습니다(D-8). 위 개선은 S1 경량 추출본 · 요청 때 렌더와 맞물립니다. 순서는 KooD3plotReader 가 정하시되, K-1 · K-2 는 운영 리포트가 조용히 틀리는 문제라 먼저 봐 주시기를 부탁드립니다.

## 5. 여쭐 것
1. K-1 을 재현하실 수 있는지 — 같은 덱과 cfile 이 `sv_proto/runs/B2_ua_render_vm_z/captured_cfiles/` 에 있습니다.
2. 이미 나간 운영 영상 중 0 프레임이 섞인 것을 일괄 점검할지 — 마지막 프레임의 max = 0 과 파일 크기로 찾을 수 있습니다.
