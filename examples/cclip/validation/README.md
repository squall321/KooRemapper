# cclip LS-DYNA 실솔버 검증 (2026-07)

`tools/cclip_check.py`(솔버 없는 자기일관성 검사)에 더해, 실제 LS-DYNA로 두 가지
핵심 주장을 검증한 기록이다. 환경: LS-DYNA **MPP double R16.1.1** (Apptainer
`LSDynaBasic_aocc420_ompi4.0.5_mpp_d.sif`), Slurm 단일 노드, implicit statics.

## Test 1 — 압축덱 F-δ (강성 캘리브레이션 재현)

deck 모드 산출물(`cclip_deck.yaml` → `*_cclip_deck_2.k`: 자유 클립 + 강체판
변위제어 압축)을 그대로 풀고 rcforc/nodout에서 F-δ를 추출했다.

| 항목 | 해석 캘리브(빔이론) | LS-DYNA 쉘 FE | 차이 |
|---|---|---|---|
| 압축량 δ (tip, nodout) | 0.15 (설계) | 0.14992 | 정확 |
| 작동력 F @ δ_op | 1.200 N | 1.374 N | +14.5% |
| 강성 k | 8.000 N/mm | 9.166 N/mm | +14.6% |

- 정상 종료(97 cycles). FE F-δ 전 구간 선형(k=9.14~9.46) → **선형 캘리브 가정 타당**.
- 접촉두께 갭 보정 정확: 판 이동 0.16 − 갭 0.01 → tip z 0.65→0.50 (설치높이).
- FE가 +15% 강성이 높은 것은 Euler-Bernoulli 빔이론이 곡선 C-clip의 곡률강성·
  고정발 강성을 무시해 과소평가하는 계통오차 — 부호·크기 모두 물리적으로 타당.
  정밀 매칭이 필요하면 실측/FE F-δ 곡선을 `calibration.curve`로 주면 된다
  (캘리브 대상 자체가 FE 강성이 되므로 이 오차는 상쇄).

## Test 2 — 선응력 스프링백 (*INITIAL_STRESS_SHELL 부호·크기)

analytic 산출물(눌린 형상 + 초기응력)에서 클립만 추출(`make_springback.py`),
발 고정 + 외력 0 + 초기응력만으로 implicit 평형을 풀었다. 응력이 올바르면
클립이 스스로 자유높이로 복원되어야 한다.

| 항목 | 기대 | LS-DYNA | 판정 |
|---|---|---|---|
| 복원 방향 | +z (위로) | +z | PASS |
| 스프링백 Δz | +0.150 | +0.1616 | PASS (+7.8%) |
| 최종 팁 높이 | 0.650 (자유높이) | 0.6616 | — |

- 정상 종료(46 cycles), t=0.1에 평형 도달 후 불변(깨끗한 정적 해).
- **초기응력의 부호와 크기가 눌림량 δ_op를 정확히 인코딩** → DR/조립 해석 시
  클립이 상대면을 F_work 수준으로 미는 평형이 실솔버에서 성립함을 확인.

## 재현 방법

```bash
# Test 1: deck 산출물 생성 후 제출
KooRemapper cclip examples/cclip/cclip_deck.yaml
sbatch run_stiffness.sbatch          # 내부 경로(VD)를 배치 위치로 수정
# 완료 후: python3 parse_fd.py       (rcforc SURFA + nodout 변위블록 파싱, ±20% 판정)

# Test 2: analytic 산출물 → 스프링백 덱 생성 후 제출
KooRemapper cclip examples/cclip/cclip.yaml
python3 make_springback.py clip_board_cclip.k springback.k
sbatch run_springback.sbatch
# 완료 후: python3 parse_sb.py       (팁 복원 부호/크기, ±15% 판정)
```

주의: sbatch 스크립트의 SIF/라이선스 env는 이 클러스터 전용이다
(`LSTC_LICENSE_SERVER=192.168.122.1`, 컨테이너 내부 `/opt/ls-dyna/lsdyna_R16.1.1`).
nodout 파서는 시간당 변위/회전 두 블록 중 변위 블록만 읽는다(회전 블록 오독 주의).
rcforc는 R16 MPP 포맷(`SURFA`/`SURFB` 행) 기준이다.
