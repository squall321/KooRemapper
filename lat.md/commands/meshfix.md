# meshfix — TET4 Gmsh-based remesh (§40)

Source: [meshfix.cpp](../../src/commands/meshfix.cpp), [[modules/remesh#Module: src/remesh/]]
Manual: [`KooRemapper_Manual.md`#40-meshfix--tet4-재메시-gmsh-기반](../../docs/KooRemapper_Manual.md#40-meshfix--tet4-재메시-gmsh-기반)


## Synopsis

```
KooRemapper meshfix <args>
```

## What it does

Gmsh-driven adaptive TET4 remesh with scaled-Jacobian quality, patch polishing, thin-solid handling. Per-component bad-element patch remesh (commit `04a97dd`); pure-Gmsh geomThin field optimal (commit `f7036a6`).

## Key references

- [[modules/remesh#Module: src/remesh/]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §40. meshfix — TET4 재메시 (Gmsh 기반)._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
기존 TET4 파트를 Gmsh를 통해 **완전 재메시**하여 요소 품질을 개선하는 명령.
STL 경계 추출 → Gmsh 실행 → MSH2 파싱 → 원본 K파일에 스플라이스하는 파이프라인으로 동작하며,
Gmsh 실행 파일(`gmsh.exe`)이 `dist/gmsh/` 또는 `dist/gmsh-<ver>/` 디렉터리에 있어야 한다.

### 사용법

```bash
KooRemapper.exe meshfix <config.yaml>
```

### YAML 설정 전체

```yaml
model:   input.k      # 입력 K파일
output:  output.k     # 출력 K파일
pid:     1            # 재메시할 파트 ID (TET4)

# ─── 요소 크기 제어 ────────────────────────────────────────────────────────
lc_target:    5.0     # 목표 평균 요소 크기 (기본: 1.0, 단위: 모델 단위)
lc_min:      -1.0     # 최소 요소 크기 (-1 = 자동: edge_min×0.8 또는 dt 기반)
lc_max:      -1.0     # 최대 요소 크기 (-1 = lc_target × 2)

# ─── dt 기반 lc_min (lc_min 대신 사용 가능) ───────────────────────────────
min_dt:       1.0e-6  # LS-DYNA explicit 시간 증분 하한 (초)
density:      2.7e-9  # 밀도 (t/mm³)
E:            70000.0 # 탄성계수 (MPa)
nu:           0.33    # 포아송 비

# ─── 얇은 형상 처리 ────────────────────────────────────────────────────────
min_layers_thin: 2    # 얇은 방향 최소 요소 레이어 수 (기본: 2)

# ─── 적응형 사이즈 필드 ────────────────────────────────────────────────────
adaptive:     true    # bbox 코너 거리 기반 MathEval 필드 활성화 (기본: true)
decay_factor: 8.0     # 코너 세밀 영역 크기 = lc_min × decay_factor

# ─── Gmsh 메셔 설정 ────────────────────────────────────────────────────────
algorithm:       hxt  # 3D 메셔: hxt (병렬, 기본) | frontal3d | del3d
optimize_netgen: true # Gmsh 내장 Netgen 최적화 활성화
optimize_passes: 3    # Mesh 3 이후 추가 OptimizeMesh "Netgen" 호출 횟수

# ─── 표면 STL 전처리 ───────────────────────────────────────────────────────
refine_surface:  auto # auto | 0(off) | 1~3 (conforming feature-edge 세분화)
smooth_surface:  0    # feature-edge Laplacian 스무딩 스텝 수 (0=off)

# ─── 경계 노드 처리 ────────────────────────────────────────────────────────
boundary_nodes: free  # free | fixed | snap
snap_tolerance: 0.001 # snap 모드 탐색 반경

# ─── 품질 보고 ─────────────────────────────────────────────────────────────
quality_check:  true  # 재메시 후 스케일드 자코비안 보고 활성화
warn_min_jac:   0.15  # 이 값 미만 요소에 경고 출력

# ─── 패치 폴리싱 (실험적) ─────────────────────────────────────────────────
polish:          false # 나쁜 요소 클러스터 로컬 재메시 (기본: off)
polish_jac:      0.10  # polish 대상 임계값 (J < polish_jac)
polish_max_iter: 2     # 최대 반복 횟수
```

**표 40-1. meshfix YAML 옵션 요약**

| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `lc_target` | 1.0 | 목표 평균 요소 크기 |
| `lc_min` | auto | 최솟값 (-1=자동, dt 기반 또는 edge_min×0.8) |
| `lc_max` | auto | 최댓값 (-1=lc_target×2) |
| `adaptive` | true | MathEval bbox 코너 거리 필드 |
| `algorithm` | hxt | Gmsh 3D 메셔 선택 |
| `optimize_passes` | 3 | 추가 Netgen 최적화 횟수 |
| `refine_surface` | auto | STL feature-edge 세분화 레벨 |
| `warn_min_jac` | 0.15 | 품질 경고 임계값 |
| `polish` | false | 나쁜 요소 로컬 재메시 |

### 동작 파이프라인

```
[1] K파일 로드 → TET4 파트 추출
        ↓
[2] 메시 분석
    - lc_min/max 자동 계산
    - geomThin 감지 (min_bbox < avg_bbox × 0.3)
    - autoRefineSurface 레벨 결정
        ↓
[3] 경계 STL 추출
    - 비다양체 에지 필터 (Stage 1: 점수 기반)
    - bbox 표면 노드 필터 (Stage 2: 레이캐스팅)
    - 최대 연결 컴포넌트만 유지
        ↓
[4] STL 전처리
    - refine_surface: conforming feature-edge 세분화 (dihedral > 40°)
    - smooth_surface: feature-edge Laplacian 스무딩
        ↓
[5] Gmsh .geo 스크립트 생성
    - ClassifySurfaces{40°} → CreateGeometry → Volume
    - MathEval 적응형 사이즈 필드 (또는 인플레인 4코너 필드)
        ↓
[6] Gmsh 실행 (HXT 알고리즘)
    Mesh 2 → Mesh 3 → OptimizeMesh "Netgen" × N
        ↓
[7] MSH2 파싱 → 스케일드 자코비안 품질 검사
        ↓
[8] (polish=true) 나쁜 클러스터 로컬 재메시
        ↓
[9] K파일 스플라이스 (기존 노드/요소 교체, 다른 파트 보존)
```

> **그림 40-1. meshfix 처리 파이프라인 — 입력 K파일에서 재메시된 출력 K파일까지의 전체 데이터 흐름을 단계별로 나타낸다. [2]~[4]는 전처리, [5]~[6]은 Gmsh 처리, [7]~[9]는 후처리에 해당한다.**

### 적응형 사이즈 필드

MathEval 거리 필드: Gmsh 임베디드 Point 엔티티 없이 순수 수식으로 구현 (HXT 호환).

```
Field[1] = MathEval;
Field[1].F = "Sqrt(Min(Min(d000,d001),Min(...,d111)))";
    ← bbox 8개 코너까지의 최솟값 거리 (수식)

Field[2] = Threshold;
    SizeMin = lc_min     ← 코너 근처: 세밀
    SizeMax = lc_max     ← 내부: 큰 요소

Field[3] = MathEval; F = "lc_target";
    ← 균일 배경 필드

Background Field = Min(Field[2], Field[3]);
```

> **그림 40-2. MathEval 적응형 사이즈 필드 구성 — 8개 bbox 코너까지의 최솟값 거리를 기준으로 코너 근처에서는 lc_min, 내부에서는 lc_target의 요소 크기를 유도한다.**

**얇은 형상 (geomThin) 처리:**
min_bbox < avg_bbox × 0.3인 경우 자동 감지하여 다음을 전환한다.

**표 40-2. geomThin 감지 시 동작 변경**

| 항목 | 일반 형상 | 얇은 형상 (geomThin) |
|---|---|---|
| Mesh 2 (표면 메시) | 실행 | **스킵** |
| 사이즈 필드 | 8코너 3D 필드 | **4코너 인플레인 필드** |
| Netgen OptimizePasses | 실행 | **스킵** |
| autoRefineSurface | 0 (Mesh 2가 대신함) | 1 (필요 시) |

### 스케일드 자코비안 (Scaled Jacobian)

TET4 요소의 형상 품질을 나타내는 무차원 지표.

$$J_s = \frac{6\sqrt{2} \cdot V}{L_{max}^3}$$

여기서 V = TET4 체적, $L_{max}$ = 가장 긴 엣지 길이. 정규 TET4에서 $J_s = 1.0$.

**표 40-3. 스케일드 자코비안 판정 기준**

| 범위 | 판정 | 설명 |
|---|---|---|
| $J_s \geq 0.5$ | **우수** | LS-DYNA 권장 범위 |
| $0.2 \leq J_s < 0.5$ | 양호 | 실용적으로 허용 |
| $0.15 \leq J_s < 0.2$ | 주의 | warn_min_jac 경고 기준 |
| $0.0 < J_s < 0.15$ | **불량** | 재메시 또는 개선 필요 |
| $J_s \leq 0$ | 역전 | 음의 체적 — 해석 불가 |

### 기하학적 품질 한계

90° 직각 코너에 인접한 TET4는 기하 구속으로 인해 이론적 최솟값이 존재한다.

$$J_{s,min}^{corner} \approx 0.03 \sim 0.07 \quad \text{(기하 구속, 요소 크기와 무관)}$$

이 한계는 기하학 수정(코너 라운딩, 필렛 추가) 없이는 개선할 수 없다.

### 패치 폴리싱 (polish)

`polish: true` 설정 시 재메시 후 추가 국소 개선을 시도한다.

**표 40-4. 패치 폴리싱 이중 품질 게이트**

| 조건 | 식 | 의미 |
|---|---|---|
| 최솟값 Jac 유지 | $J_{min,new} \geq J_{min,orig} \times 0.95$ | 최솟값 5% 이상 회귀 시 거부 |
| 불량 수 감소 | $N_{bad,new} < N_{bad,orig}$ | 불량 요소 수가 줄어야 수락 |

두 조건을 모두 만족한 패치만 메시에 머지한다. 하나라도 불만족이면 해당 클러스터는 원본 유지.

### 경계 노드 처리 모드

**표 40-5. boundary_nodes 모드별 동작**

| 모드 | 동작 | 사용 예 |
|---|---|---|
| `free` (기본) | 모든 Gmsh 노드에 새 ID 부여 | 독립 파트 재메시 |
| `fixed` | 경계 노드를 원본 ID에 고정 (좌표 매칭) | 인접 파트와 공유 노드 |
| `snap` | 인접 파트 노드에 snap_tolerance 이내이면 병합 | 파트 간 접합 재메시 |

### 실행 예시

```yaml
# 예시: arc30 평면 TET4 메시 재메시
model:      examples/arc30/arc30_flat_tet.k
output:     output/remeshed.k
pid:        1
lc_target:  5.0
adaptive:   true
warn_min_jac: 0.15
```

실행 출력:
```
PID 1 TET4:              3000
  lc_min=1  lc_max=10
Gmsh TET4:               34695
Min scaled Jacobian:     0.0675
Avg scaled Jacobian:     0.405
[WARN] 847 elements below warn_min_jac=0.15
Total time: 13.6 s
```

> **그림 40-3. meshfix 실행 출력 예 — 입력 3,000개 TET4가 34,695개로 재메시됨. 스케일드 자코비안 통계와 품질 경고가 출력된다. 847개 불량 요소는 박스 90° 코너의 기하 구속에 의한 것으로, 기하학 수정 없이는 개선 불가하다.**

### 주의사항

- **Gmsh 필수**: `dist/gmsh/gmsh.exe` 또는 `dist/gmsh-<ver>/gmsh.exe` 위치에 배치 필요
- **TET4 전용**: 입력 파트는 TET4 (또는 퇴화 HEX8) 형식이어야 함
- **처리 시간**: 10만 요소 이상에서 수 분 소요 가능
- **polish 제한**: `polish: true`는 실험적 기능. 90° 코너 구속 형상에서는 불량 수 감소 불가로 자동 스킵

---

<!-- END MANUAL EXCERPT -->
