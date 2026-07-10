# cclip — C-clip(스프링 접점) 치환 예제

스마트폰 PBA의 C-clip(Spring Contact/Ground Spring/C-Clip)은 조립 시 상대 부품에 눌리며
전기 접촉하는 탄성 부품이다. CAE 모델에서 흔히 **육면체 블록**으로 단순화되는데, 이 op는
그 블록을 **F-δ 데이터로 강성 캘리브레이션된 C형 쉘 스트립**으로 치환하고, 자유높이 >
설치높이의 오버랩을 **눌린 상태 + *INITIAL_STRESS_SHELL(잔류 굽힘 응력)**로 반영한다.

## 실행

```bash
bash run.sh
# 또는 수동:
KooRemapper generate box gen_board.yaml     # 입력 박스(clip_board.k) 생성
KooRemapper cclip cclip.yaml                # 치환 + 캘리브레이션 + 선응력
python3 ../../tools/cclip_check.py clip_board_cclip.k clip_board_cclip_cclip_report.json
```

## 입력 / 출력

| 파일 | 설명 |
|------|------|
| `gen_board.yaml` | 입력 박스 생성 설정 (3.0×1.5×0.5mm, PID 2, BeCu) |
| `cclip.yaml` | analytic 모드 + 작동점(0.15mm, 1.2N) 캘리브레이션 |
| `cclip_deck.yaml` | deck 모드 + F-δ 곡선 캘리브레이션 |
| → `clip_board_cclip.k` | 눌린 클립 (원 PID 유지, *SECTION_SHELL T=보정 두께, 초기응력 embed) |
| → `clip_board_cclip_cclip_report.json` | 목표/달성 강성·두께·오차·작동력·σ_max·질량 리포트 |
| → `clip_board_deck_cclip_deck_2.k` | (deck 모드) 강체판 압축덱 — LS-DYNA 실행용 |

## 내부 동작

1. **박스 프레임 추출** — 대상 파트 bbox에서 압축축(최단축)·길이·폭·설치높이 도출.
2. **C 프로파일** — 발 평탄부 → 반원(또는 1/4원+수직다리) → 경사 접촉 암(팁이 정점,
   팁 라이즈 ≥ 작동변위라 눌린 후 어깨가 상대면 아래에 위치).
3. **캘리브레이션** — Castigliano 단위하중법 `J=∫m²ds` → `k(t)=E·W·t³/(12·J)` 닫힌형
   해로 두께 결정(곡선 입력은 작동점 시컨트, v1은 선형 매칭 — 리포트에 명시).
4. **눌린 형상** — 곡률변화 `Δκ=c·m/(EI)`를 코드(현) 회전으로 적분(대변형 보정 c는
   이분법으로 max높이=설치높이). **응력장은 실측 작동력 F_work 기준**으로 기입되어
   DR/해석 시 클립이 상대면을 F_work로 미는 평형이 구성상 보장된다.
5. **치환** — 원 PID 유지(*PART의 SECID/MID만 교체 → 기존 SET/CONTACT 참조 보존),
   대상 솔리드 요소 삭제, 구 SECTION/MAT은 비공유 시만 제거, 박스 노드는 보존(고아
   수 리포트).

## 검증 (LS-DYNA 없이)

`tools/cclip_check.py`가 산출물만으로 4가지를 검사한다.

1. 눌린 최대높이 == 설치높이
2. 강성 상대오차 ≤ 5%
3. 상/하면 응력 부호 반전(순수 굽힘 패턴)
4. 응력 적분→모멘트→팁 접촉력 환산 vs 리포트 작동력 (≤10%)

LS-DYNA가 있으면: deck 모드 덱을 실행해 rcforc의 반력-변위를 입력 F-δ와 대조하고,
analytic 산출물은 `KooRemapper relax`로 DR 덱을 구성해 접촉력 재현을 확인할 수 있다.

## Variants

- **여러 클립 일괄**: `clips: [- match_part: "CCLIP_*"]` — 파트 타이틀 글롭, 매치마다 클립 1개.
- **바닥 부착**: `attach: cnrb` — 발 노드 + attach_tol 내 주변(보드) 노드를 *CONSTRAINED_NODAL_RIGID_BODY로 묶음.
- **초기응력 별도 파일**: `stress_output: include` — `<output>.dynain` + *INCLUDE.
- **재료/캘리브레이션 클립별 오버라이드**: clips 항목 안에 `material:`/`calibration:` 지정.

## v1 한계 (리포트에도 출력됨)

선형(시컨트) 강성 매칭 · 탄성 굽힘 선응력만(소성 없음, σ_max>0.8σy 경고) ·
축정렬 박스 전제 · 쉘 접촉두께 t/2에 의한 갭 미보정.
