# Shell Forming Strain (formstrain)

## 1. 개요

판금 부품(실드캔, 브라켓 등)은 평판에서 절곡/스탬핑으로 성형된다.
성형 과정에서 굴곡부에는 소성 변형이 발생하고, 재료가 경화(strain hardening)된다.
이 이력을 반영하지 않으면 후속 해석(드롭, 충격, 크리프)에서 굴곡부 거동이 부정확해진다.

**핵심 아이디어**: 최종 메쉬의 기하학적 곡률로부터 성형 시 굽힘 변형률을 역산하고,
항복점을 초과하는 부분을 유효소성변형률(EPS)로 부여한다.

```text
[평판 원자재] ─── 절곡/스탬핑 ───> [굴곡부에 소성변형] ─── 경화된 상태
                                          ↑
                           메쉬 곡률에서 역산 가능
```

---

## 2. 이론

### 2.1 판 굽힘의 변형률 분포

두께 `t`인 평판이 곡률 `κ`로 굽혀질 때, 중립면에서 거리 `d`인 위치의 굽힘 변형률:

```text
ε(d) = κ · d
```

중립면(`d = 0`)에서 변형률은 0이고, 표면(`d = ±t/2`)에서 최대:

```text
ε_surface = κ · t/2
```

### 2.2 이면각 곡률 (Dihedral Angle Curvature)

연속체의 곡률 `κ = dθ/ds`를 이산 쉘 메쉬에서 근사하는 방법이다.

인접한 두 QUAD4 요소가 공유 엣지를 사이에 두고 이루는 이면각 `θ`로부터:

```text
θ = arccos(n_A · n_B)

κ = θ / L
```

여기서:

- `n_A`, `n_B` : 각 요소의 단위 법선벡터 (대각선 외적으로 계산)
- `L` : 두 요소 중심(centroid)간 거리

```text
      n_A ↗         ↖ n_B
       /               \
 [elem A]────edge────[elem B]
    ●─────── L ────────●
 centroid_A         centroid_B
```

**L의 선택 근거**: 곡률의 정의 `κ = dθ/ds`에서 `ds`는 곡선 위의 미소 호 길이이다.
중심간 거리가 호 길이 `ds`에 대한 가장 자연스러운 이산 근사이다.
엣지 길이는 접선 방향이므로 `ds`의 좋은 근사가 아니다.

**요소별 곡률**: 한 요소는 최대 4개의 엣지를 가지며, 각 엣지의 `κ` 중 최대값을 해당 요소의 곡률로 취한다.

**경계 처리**: 이웃이 없는 자유 경계 엣지는 건너뛴다 (곡률 기여 없음).

### 2.3 법선 일관성 검사

QUAD4 법선은 노드 순서에 의존한다 (반시계 → 상면 법선).
인접 요소의 법선이 뒤집혀 있으면 평면인데도 `θ ≈ π`로 잘못 계산된다.

대응: `n_A · n_B < -0.5`인 엣지는 건너뛰고 경고 카운터를 증가시킨다.
CAD 생성 메쉬는 일반적으로 법선 일관성이 보장되므로, 별도의 법선 재계산은 수행하지 않는다.

### 2.4 소성 변형률 판정

표면 굽힘 변형률이 탄성 한계를 초과하면 소성 변형이 발생한다:

```text
ε_bending = κ · t/2               (표면 굽힘 변형률)
ε_yield   = σ_y / E               (탄성 한계 변형률)
ε_plastic = max(0, ε_bending - ε_yield)
```

이것은 탄성-완전소성(elastic-perfectly plastic) 모델의 단순화이다.
실제 경화 곡선이 있는 재료에서는 보수적인 추정값이 된다.

### 2.5 EPS의 물리적 의미

`ε_plastic`을 LS-DYNA `*INITIAL_STRESS_SHELL`의 EPS 필드에 부여한다.

- **응력 = 0**: 스프링백 후 이완 상태 가정 (잔류응력 없음)
- **EPS > 0**: 등방 경화(isotropic hardening)에 의한 항복면 확장
- **상면/하면 동일 EPS**: 순수 굽힘의 대칭성 (`|d| = t/2` 동일)

결과적으로 굴곡부의 재료는 `σ_y + H·ε_plastic`만큼 강화된 상태로 해석에 투입된다
(H = 경화 계수, MAT_024의 ETAN 또는 곡선 기반).

---

## 3. LS-DYNA 키워드 포맷

### 3.1 입력: `*MAT_PIECEWISE_LINEAR_PLASTICITY` (MAT_024)

```text
*MAT_PIECEWISE_LINEAR_PLASTICITY
$#     mid        ro         e        pr      sigy      etan      fail      tdel
         1  7.93E-09    193000      0.29       215       0.0       0.0       0.0
```

- 10-char 고정폭 필드
- SIGY = Card 1, Field 5 (항복응력)
- SIGY > 0인 경우만 formstrain 대상

### 3.2 출력: `*INITIAL_STRESS_SHELL`

```text
*INITIAL_STRESS_SHELL
$#    eid  nplane  nthick   nhisv  ntensr   large  nthint  nthhsv
        42       1       2       0       0       0       0       0
$#       T     sigxx     sigyy     sigzz     sigxy     sigyz     sigzx       eps
-1.000e+00 0.000e+00 0.000e+00 0.000e+00 0.000e+00 0.000e+00 0.000e+00 2.500e-02
 1.000e+00 0.000e+00 0.000e+00 0.000e+00 0.000e+00 0.000e+00 0.000e+00 2.500e-02
```

| 필드 | 값 | 의미 |
| --- | --- | --- |
| NPLANE | 1 | 면내 적분점 1개 |
| NTHICK | 2 | 두께 방향 적분점 2개 (상면/하면) |
| T = -1 | 하면 | EPS = `ε_plastic` |
| T = +1 | 상면 | EPS = `ε_plastic` (동일) |
| sigxx~sigzx | 0 | 잔류응력 없음 |

---

## 4. 자동 대상 판별

파트가 formstrain 대상이 되려면 다음 조건을 모두 만족해야 한다:

1. `*ELEMENT_SHELL` (QUAD4) 요소를 포함
2. `*SECTION_SHELL` 연결 → T1 두께 > 0
3. `*MAT_024` 연결 → SIGY > 0

조건 불만족 파트는 자동으로 건너뛰며 에러가 아닌 로그를 출력한다.

---

## 5. YAML 설정

### 5.1 기본 (자동 감지)

```yaml
base_model: model.k
output: result
dynain_embed: true

operations:
  - type: formstrain
```

`target_pid` 생략 시 위 조건을 만족하는 모든 쉘 파트를 자동 처리한다.

### 5.2 옵션

```yaml
operations:
  - type: formstrain
    target_pid: 3           # 특정 파트만 지정 (0 또는 생략 = 전체)
    shell_thickness: 0.8    # 두께 오버라이드 (0 = *SECTION_SHELL 자동)
    min_curvature: 0.1      # 노이즈 필터 임계값 (기본 = 0)
```

### 5.3 indent + formstrain 조합

```yaml
operations:
  - type: indent
    target_pid: 3
    depth: 0.05
    # ...

  - type: formstrain
```

같은 요소에 두 오퍼레이션이 적용될 때의 병합 규칙:

| 항목 | indent | formstrain | 병합 결과 |
| --- | --- | --- | --- |
| stress | σ_indent | 0 | σ_indent (합산) |
| EPS | 0 | ε_plastic | ε_plastic (max) |

EPS는 `max(a, b)` 사용 (소성변형률은 합산이 아닌 최대값 채택).

---

## 6. 구현 구조

### 6.1 `ShellCurvature` 클래스 (신규)

`include/assembly/ShellCurvature.h` + `src/assembly/ShellCurvature.cpp`

```cpp
struct ShellCurvatureResult {
    int elementId;
    double maxCurvature;      // max κ across all edges
    double maxBendingStrain;  // κ · t/2
    double plasticStrain;     // max(0, ε_bending - σ_y/E)
};

class ShellCurvature {
public:
    std::vector<ShellCurvatureResult> compute(
        const Mesh& mesh, int targetPid, double thickness,
        double sigy, double E, double minCurvature = 0.0);
    int getNormalWarnings() const;
};
```

알고리즘:

1. 대상 파트의 QUAD4 요소 ID 수집
2. 엣지맵 구축: `sorted(nodeA, nodeB) → {elemA, elemB}`
3. 요소별 법선/중심 사전 계산
4. 엣지 순회: `θ = arccos(n_A · n_B)`, `L = dist(c_A, c_B)`, `κ = θ/L`
5. 요소별 max κ → `ε_bending` → `ε_plastic`

### 6.2 수정 파일 요약

| 파일 | 변경 |
| --- | --- |
| `Mesh.h` | `MaterialData.sigy` 추가 |
| `KFileReader.cpp` | MAT_024 SIGY 파싱 |
| `ElementAnalyzer.h` | `ElementResult.epsTop/epsBottom` 추가 |
| `AssemblyConfig.h` | `FormStrainOperation` + `FORMSTRAIN` enum |
| `AssemblyConfigReader.cpp` | YAML 파싱 |
| `ModelAssembler.cpp` | `applyFormStrain()` + EPS 출력/병합 |
| `main.cpp` | dispatch |
| `CMakeLists.txt` | 소스 추가 |

---

## 7. 검증

### 7.1 검증 1 - L-shape 90도 절곡

**입력**: `examples/formstrain/bent_shell.k`

```text
5×5 평판 (z=0) + 5×5 수직벽 (y=5, z=0~5)
50개 QUAD4 요소, 1개 파트
E = 210000, σ_y = 200, t = 1.0
```

```text
     z
     │  wall (25 elems)
     │  ___________
     │ │           │
     └─┴───────────── y
     flat plate (25 elems)
```

**수동 계산**:

```text
θ       = π/2                                     (90도)
L       = √(0.5² + 0.5²)           = 0.7071      (centroid 간 거리)
κ       = (π/2) / 0.7071            = 2.2214      (곡률)
ε_bend  = 2.2214 × 1.0/2            = 1.1107      (표면 변형률)
ε_yield = 200 / 210000               = 0.000952    (탄성 한계)
ε_plastic = 1.1107 − 0.000952        = 1.110       (소성 변형률)
```

**프로그램 출력**: 절곡부 10개 요소 (EID 21-30) → **EPS = 1.110** (일치)

### 7.2 검증 2 - PBA 실드캔

**입력**: `examples/formstrain/shield_can.k`

```text
20×15mm 바닥판 + 3mm 높이 4면 벽
510개 QUAD4 요소, SUS304
E = 193000, ν = 0.29, σ_y = 215, t = 0.2
```

```text
       -X wall (45)
      ┌────────────────┐
      │                │
-Y    │  bottom (300)  │  +Y
wall  │                │  wall
(60)  │                │  (60)
      └────────────────┘
       +X wall (45)
```

**수동 계산** (바닥-벽 90도 엣지):

```text
θ       = π/2                                     (90도)
L       = √(0.5² + 0.5²)           = 0.7071
κ       = (π/2) / 0.7071            = 2.2214
ε_bend  = 2.2214 × 0.2/2            = 0.2221      (t/2 = 0.1)
ε_yield = 215 / 193000               = 0.001114
ε_plastic = 0.2221 − 0.001114        = 0.221
```

**프로그램 출력**: 152/510 요소에 EPS 부여

| 영역 | EPS가 있는 요소 수 | EPS 값 | 설명 |
| --- | --- | --- | --- |
| 바닥 내부 | 0 | - | 평면, 곡률 없음 |
| 바닥 가장자리 | 66 | 0.221 | 벽과의 90도 절곡 |
| 벽 최하단 행 | 70 | 0.221 | 바닥과의 90도 절곡 |
| 벽-벽 코너 | 16 | 0.221 | 벽 간 90도 접합 |
| 벽 중간/상단 | 0 | - | 평면, 곡률 없음 |

모든 EPS 값이 수동 계산 **0.221**과 정확히 일치.

### 7.3 참고 - 곡률 반경별 EPS

| 조건 | κ | ε_bend | ε_yield | ε_plastic |
| --- | --- | --- | --- | --- |
| t=1.0, R=1mm 급절곡 | 1.0 | 0.500 | 0.00095 | 0.499 |
| t=0.3, R=50mm 완만곡 | 0.02 | 0.003 | 0.00095 | 0.002 |
| 평면 (R→∞) | ≈0 | ≈0 | - | 0 |

---

## 8. 예제 파일

`examples/formstrain/` 디렉토리:

| 파일 | 설명 |
| --- | --- |
| `bent_shell.k` | L-shape 90도 절곡 메쉬 (50 요소) |
| `formstrain_test.yaml` | bent_shell 테스트 설정 |
| `formstrain_result.k` | 결과: 절곡부 EPS = 1.110 |
| `gen_shield_can.ps1` | 실드캔 메쉬 생성 PowerShell 스크립트 |
| `shield_can.k` | 생성된 실드캔 메쉬 (510 요소) |
| `shield_can_test.yaml` | 실드캔 테스트 설정 |
| `shield_can_result.k` | 결과: 152 요소 EPS = 0.221 |
| `analyze_result.ps1` | 결과 분석 (영역별 EPS 분포 출력) |

실행:

```bash
# L-shape 테스트
KooRemapper assemble examples/formstrain/formstrain_test.yaml

# 실드캔 생성 + 테스트
powershell -ExecutionPolicy Bypass -File examples/formstrain/gen_shield_can.ps1
KooRemapper assemble examples/formstrain/shield_can_test.yaml

# 결과 분석
powershell -ExecutionPolicy Bypass -File examples/formstrain/analyze_result.ps1
```

---

## 9. 제약사항

1. **순수 굽힘 가정** - 인장/압축 성분 무시 (딥드로잉 같은 복합 변형에는 부정확)
2. **스프링백 미고려** - 잔류응력 없이 EPS만 부여 (보수적 추정)
3. **경로 독립** - 최종 형상의 곡률만 사용 (중간 공정 이력 무시)
4. **MAT_024 전용** - SIGY 필드가 있는 재료만 지원 (LCSS 테이블 미지원)
5. **메쉬 의존** - 이면각 곡률은 요소 크기에 의존 (거친 메쉬 → 곡률 과소평가)
6. **법선 일관성 전제** - 뒤집힌 법선은 skip + 경고 (자동 보정 없음)
7. **QUAD4 전용** - TRIA3 요소 미지원
