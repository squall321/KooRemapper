# Restack Operation Guide

## Overview

`restack`은 단일 균질 솔리드 파트를 다층 재료 스택으로 교체하는 오퍼레이션입니다.
원본 파트의 노드를 압출 방향으로 재배열하여 새로운 레이어를 생성하며,
각 레이어는 독립적인 파트(PID), 단면(SECID), 재료(MID)를 갖습니다.

### 지원 레이어 타입

| 타입 | LS-DYNA 요소 | 특징 |
|------|-------------|------|
| `solid` | ELEMENT_SOLID (ELFORM=1) | 완전 연속체, 인접 레이어와 노드 공유 |
| `tshell` | ELEMENT_TSHELL | 두께 방향 적분점 지원 솔리드쉘 |
| `shell` | ELEMENT_SHELL (ELFORM=2) | 독립 mid-plane 노드, 접촉으로 연결 |

---

## YAML 문법

### 최상위 필드

```yaml
- type: restack
  target_pid: 1              # 교체 대상 파트 ID (필수)
  direction: z               # 압출 방향: x | y | z | auto (기본: auto)
  element_type: solid        # 기본 레이어 타입: solid | tshell | shell (기본: solid)
  element_size: 0.0          # 레이어당 요소 목표 크기 [mm] (0=비활성)

  # 계면 접촉 설정
  interface_contact: tied    # tied | czm | czm_auto (기본: tied)
  czm_normal: 50.0           # [MPa] CZM 법선 파손 응력 (czm/czm_auto 시 필요)
  czm_shear:  30.0           # [MPa] CZM 전단 파손 응력 (czm/czm_auto 시 필요)
  drop_height: 1000.0        # [mm] 낙하 높이 (czm_auto 전용)

  layers:
    - ...
```

### 레이어 필드

```yaml
layers:
  - title: Layer_Name        # *PART 제목 (미지정 시 "Restack Layer N")
    thickness: 0.050         # 레이어 총 두께 [mm] (필수)
    num_elements: 2          # 두께 방향 요소 수 (0=element_size로 자동 계산)
    element_type: solid      # 레이어별 타입 override (미지정 시 상위 기본값)
    czm_normal: 40.0         # 이 레이어 인터페이스 법선 파손 응력 override
    czm_shear:  20.0         # 이 레이어 인터페이스 전단 파손 응력 override
    material_card: |
      *MAT_ELASTIC_TITLE
      ...
```

---

## 계면 접촉 모드

### `tied` (기본)

Shell 레이어가 있는 인터페이스에 `*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET` 자동 생성.
Solid-Solid 인터페이스는 노드 공유(conformal)로 접촉 불필요.

```
*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET
Card 1: SSID  MSID  SSTYP=0  MSTYP=0  ...  SPR=1  MPR=1
Card 2: FS=0  FD=0  DC=0  VC=0  ...  DT=1e20
Card 3: SFSA=1  SFSB=1  ...
```

### `czm`

`*CONTACT_TIED_SURFACE_TO_SURFACE_FAILURE`로 변경.
`czm_normal`(FS), `czm_shear`(FD)로 파손 응력 지정.

```
*CONTACT_TIED_SURFACE_TO_SURFACE_FAILURE
Card 2: FS=czm_normal  FD=czm_shear  DC=0  VC=0  ...
```

### `czm_auto`

`czm`와 동일하되 VC(점성 감쇠)를 Prony 급수에서 자동 계산.

**계산 체인:**
```
낙하 높이 h [mm]
  → 충격속도 v = √(2 × 9810 × h)  [mm/s]
  → 지배 각주파수 ω = 2π × v / t_layer  [rad/s]
  → G''(ω) = Σ gᵢ × ωτᵢ / (1 + ω²τᵢ²)  [MPa]
  → VC = G''(ω) / (ω × t_layer)  [MPa·s/mm]
```

지원 재료:
- `*MAT_GENERAL_VISCOELASTIC` — Prony 급수 (복수 항 모두 반영)
- `*MAT_VISCOELASTIC` — 단일 Maxwell 요소 (G0, Gi, BETA)

`czm_normal`/`czm_shear`는 여전히 수동 입력 필요.

---

## Shell 레이어 동작

Shell 레이어는 인접 Solid와 **노드를 공유하지 않습니다** (독립 mid-plane 노드).
이를 통해 양쪽 Solid가 각각 별도의 tied/CZM 접촉으로 연결됩니다.

```
[Solid A top face]        → SET_SEGMENT (master)
      ↕  CONTACT_TIED
[Shell mid-plane nodes]   → SET_SEGMENT (slave)  NLOC=0
      ↕  CONTACT_TIED
[Solid B bottom face]     → SET_SEGMENT (master)
```

### Shell 단면 설정

```
*SECTION_SHELL
  ELFORM=2, NIP=2, SHRF=1.0
  T1=T2=T3=T4=thickness, NLOC=0   (mid-plane 기준)
```

---

## 자동 생성 카드 요약

| 카드 | 조건 |
|------|------|
| `*PART` + `*SECTION_SOLID` + `*MAT_*` | 모든 레이어 |
| `*SECTION_SHELL` (NLOC=0) | shell 레이어 |
| `*SET_SEGMENT` × 2 | shell-solid 계면마다 |
| `*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET` | tied 모드 |
| `*CONTACT_TIED_SURFACE_TO_SURFACE_FAILURE` | czm / czm_auto 모드 |
| `*INITIAL_STRAIN_SOLID` | 총 두께 불일치 시 (solid 요소만) |

---

## 두께 불일치 처리

레이어 총 두께 합이 원본 파트 두께와 다를 경우:

1. **노드 강제 스케일링**: `planeFrac × originalThickness`로 노드 배치
   → 모든 레이어가 원본 범위에 비례하여 압축/인장
2. **`*INITIAL_STRAIN_SOLID` 자동 삽입**: 변형률 `eps = (original/sum) - 1.0`을
   솔리드 요소에 적용. LS-DYNA가 각 재료 모델로 응력을 자동 계산.
   - Shell 레이어는 skip (기하학적으로 두께 점유가 없음)
   - E/nu 불필요 — 이종 재료 스택에도 정확

> **권장**: 총 두께를 정확히 맞추면 prestress 없이 가장 깔끔한 초기 상태를 얻습니다.

---

## 예제 파일

| 파일 | 설명 |
|------|------|
| `simplebox.yaml` | 알루미늄 박스 생성 (generate only) → `simplebox.k` |
| `b7_allsolid.yaml` | 전 11층 solid (conformal, 접촉 없음) |
| `b7_mixed.yaml` | solid + shell 혼합, tied contact (현재 권장 구조) |
| `b7_czm.yaml` | solid + shell 혼합, czm_auto contact (Prony 자동 감쇠) |
| `b7_psa_solid.yaml` | PSA4/5/6/7 solid, BarrierPI shell + tied |
| `gen_al_box.yaml` | generate + restack 일체형 원본 |

### 실행 순서

```bash
# 1. 베이스 박스 생성
KooRemapper assemble examples/assemble_display/simplebox.yaml

# 2. 원하는 스택 구성 실행
KooRemapper assemble examples/assemble_display/b7_mixed.yaml
KooRemapper assemble examples/assemble_display/b7_czm.yaml
# 또는
KooRemapper assemble examples/assemble_display/b7_allsolid.yaml
KooRemapper assemble examples/assemble_display/b7_psa_solid.yaml
```

---

## B7_PV1 디스플레이 스택 레이어 구성

**박스**: 67.0 × 145.0 × 0.395 mm, 134 × 290 × 1 요소

| # | 레이어 | 두께 [mm] | 밀도 [t/mm³] | 재료 | 요소 타입 |
|---|--------|-----------|-------------|------|-----------|
| 1 | PL_ADV (Polarizer Film) | 0.054 | 1.35e-9 | MAT_GENERAL_VISCOELASTIC | solid 2ea |
| 2 | PSA0_ADV | 0.035 | 1.10e-9 | MAT_GENERAL_VISCOELASTIC | solid 2ea |
| 3 | FTG_F (Flexible Thin Glass) | 0.050 | 1.35e-9 | MAT_ELASTIC (E=3000, ν=0.34) | solid 2ea |
| 4 | PSA1_ADV | 0.075 | 1.10e-9 | MAT_GENERAL_VISCOELASTIC | solid 2ea |
| 5 | Panel-F | 0.030 | 1.42e-9 | MAT_ELASTIC (E=3300, ν=0.25) | solid 2ea |
| 6 | PSA4_ADV | 0.025 | 1.10e-9 | MAT_GENERAL_VISCOELASTIC | **shell 1ea** |
| 7 | P-film_ADV | 0.050 | 1.39e-9 | MAT_GENERAL_VISCOELASTIC | solid 2ea |
| 8 | PSA5_ADV | 0.015 | 1.10e-9 | MAT_GENERAL_VISCOELASTIC | **shell 1ea** |
| 9 | BarrierPI | 0.025 | 1.40e-9 | MAT_ELASTIC (E=3000, ν=0.34) | **shell 1ea** |
| 10 | PSA6_ADV | 0.016 | 1.10e-9 | MAT_GENERAL_VISCOELASTIC | **shell 1ea** |
| 11 | PSA7_ADV | 0.020 | 1.10e-9 | MAT_GENERAL_VISCOELASTIC | **shell 1ea** |

**합계**: 0.395 mm (박스 두께와 일치 → prestress 없음)

### PSA Prony 급수 (MAT_GENERAL_VISCOELASTIC, MID=14)

| 항 | gᵢ [MPa] | βᵢ [1/s] | τᵢ [s] |
|----|----------|----------|--------|
| G∞ | 0.3 | 0 | ∞ |
| 1 | 2.0 | 1 | 1 |
| 2 | 5.0 | 10 | 0.1 |
| 3 | 15.0 | 100 | 10ms |
| 4 | 40.0 | 1,000 | 1ms |
| 5 | 100.0 | 10,000 | 0.1ms |

**1m 낙하 기준** (v=4429 mm/s, PSA4 t=0.025mm):
- ω ≈ 1.1 × 10⁶ rad/s
- G''(ω) ≈ 0.95 MPa (고주파 동결 상태 — PSA 순간 강성 지배)
- VC ≈ 3.5 × 10⁻⁸ MPa·s/mm

### 계면 접촉 (mixed/czm 구조)

총 6개 계면 접촉 (shell이 있는 인터페이스):

| 계면 | Slave | Master |
|------|-------|--------|
| Panel-F ↔ PSA4 | PSA4 shell mid | Panel-F top face |
| PSA4 ↔ P-film | PSA4 shell mid | P-film bottom face |
| P-film ↔ PSA5 | PSA5 shell mid | P-film top face |
| PSA5 ↔ BarrierPI | PSA5 shell mid | BarrierPI shell mid |
| BarrierPI ↔ PSA6 | PSA6 shell mid | BarrierPI shell mid |
| PSA6 ↔ PSA7 | PSA6 shell mid | PSA7 shell mid |

---

## 변경 이력

| 버전 | 변경 내용 |
|------|-----------|
| v1.2.0 | restack 기본 기능 (solid/tshell 레이어) |
| v1.2.x | shell 레이어 지원, independent mid-plane 노드 |
| v1.2.x | `title` 필드 — *PART 제목 per-layer 지정 |
| v1.2.x | SET_SEGMENT 기반 tied contact (PID 방식→세그먼트 방식) |
| v1.2.x | `interface_contact: czm` — CONTACT_TIED_*_FAILURE |
| v1.2.x | `interface_contact: czm_auto` — Prony 자동 VC 계산 |
| v1.2.x | per-layer `czm_normal`/`czm_shear` override |
| v1.2.x | 두께 불일치 처리: `*INITIAL_STRESS_SOLID` → `*INITIAL_STRAIN_SOLID` |
