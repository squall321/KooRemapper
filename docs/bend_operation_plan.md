# `bend` 오퍼레이션: 파트 휨 변형 + 초기 굽힘 응력

## Context

### 문제
기존 `squeeze`는 x,y,z 방향 균일 변형률만 적용 가능하다.
실제 제품에서는 **굽힘(warpage/bending)** 변형이 필요하다:
- 몰딩 후 뒤틀림 (측정 데이터 기반)
- 배터리 스웰링 (상/하면 다른 변형)
- DOE용 파라메트릭 휨 (sin 함수)

### 해결
`assemble` 명령에 `bend` 오퍼레이션 추가:
- 3가지 휨 소스: dat 파일 / 상하면 dat 쌍 / formula 수식
- 2가지 모드: deform (좌표 이동) / stress (초기응력만)
- 기존 squeeze, restack와 순차 적용 가능

```
[평면 파트]  ──── bend ────>  [굽힌 파트] + 초기응력(dynain)
                 │
    source: ┌────┼────────────────┐
            │    │                │
          dat  dat_pair        formula
       (중립면) (상/하면)    (자유 수식)
```

---

## YAML Config

```yaml
operations:
  # 소스 1: dat 파일 (중립면 처짐 그리드)
  - type: bend
    target_pid: 3
    plane: xy              # xy | yz | zx (면내 방향)
    mode: deform           # deform | stress
    source: dat
    dat_file: warpage.dat  # 스페이스 구분 그리드 (첫 줄=ymax)

  # 소스 2: 상/하면 dat 쌍 (배터리 스웰링)
  - type: bend
    target_pid: 3
    plane: xy
    mode: deform
    source: dat_pair
    dat_top: top.dat
    dat_bottom: bottom.dat

  # 소스 3: 수식 (formula) - DOE용 자유 수식
  - type: bend
    target_pid: 3
    plane: xy
    mode: stress           # 평면 유지 + 응력으로 DR 시 굽힘
    source: formula
    expression: "0.5 * sin(pi*x1/L1) * sin(pi*x2/L2)"
    # 변수: x1,x2 (면내좌표, BB min 기준), L1,L2 (BB 크기), pi
    # 함수: sin,cos,tan,exp,log,sqrt,abs,pow
    # 2차 모드 예: "0.3*sin(2*pi*x1/L1)*sin(pi*x2/L2)"
    # 복합 예: "0.5*sin(pi*x1/L1)*sin(pi*x2/L2) + 0.1*cos(2*pi*x1/L1)"
```

---

## 면 방향(plane) 매핑

| plane | 면내 축1 (x₁) | 면내 축2 (x₂) | 법선 축 (처짐 방향) |
|-------|-------------|-------------|----------------|
| xy    | x (idx 0)  | y (idx 1)   | z (idx 2)      |
| yz    | y (idx 1)  | z (idx 2)   | x (idx 0)      |
| zx    | z (idx 2)  | x (idx 0)   | y (idx 1)      |

---

## 핵심 알고리즘

### 1. dat 파일 포맷

```
0.00  0.10  0.25  0.30     ← row 0 = y_max 줄
0.05  0.20  0.40  0.35     ← ...
0.00  0.10  0.20  0.25     ← row N-1 = y_min 줄
```

- 열(column) = x₁ 방향 (x₁_min → x₁_max)
- 행(row) = x₂ 방향 (x₂_max → x₂_min, 위→아래)
- 값 = 법선 방향 처짐량 w
- 그리드 범위를 파트 바운딩박스에 자동 매핑

### 2. 곡률 계산 (유한차분)

그리드 간격 dx₁, dx₂에 대해:
```
κ₁₁ = -d2w/dx1^2   (중앙차분)
κ₂₂ = -d2w/dx2^2
κ₁₂ = -d2w/(dx1·dx2)
```
경계에서는 편측 차분 사용. 그리드 노드에서 미리 계산 후 bilinear 보간.
부호 규약: κ = -∂²w/∂x² (양수 = concave up)

### 3. formula 소스 (자유 수식)

수식을 파싱하여 그리드에 평가 → DeflectionGrid로 변환:

```
1. FormulaEvaluator로 expression 파싱
2. 101×101 그리드에 수식 평가 (x1,x2,L1,L2,pi 변수 바인딩)
3. 결과를 DeflectionGrid.data_에 저장
4. setRange() → computeDerivatives() → 곡률/기울기 자동 계산
```

수식 파서 지원: `+`, `-`, `*`, `/`, `^`, 괄호, `sin`, `cos`, `tan`, `exp`, `log`, `sqrt`, `abs`, `pow`
예: `"0.5*sin(2*pi*x1/L1)*sin(pi*x2/L2) + 0.1*cos(3*pi*x1/L1)"`

### 4. 굽힘 변형률 (판 이론)

중립면에서 거리 d인 점의 변형률:
```
ε₁₁ = -d · κ₁₁
ε₂₂ = -d · κ₂₂
γ₁₂ = -2d · κ₁₂
```
여기서 d = n_coord - n_mid (법선 축 좌표 - 중립면 좌표)

### 5. 노드 변위 (deform 모드)

각 노드에 대해:
```
Δn = w(x₁, x₂)                    ← 법선 방향 처짐
Δx₁ = -d · ∂w/∂x₁                 ← Kirchhoff 면내 보정
Δx₂ = -d · ∂w/∂x₂                 ← Kirchhoff 면내 보정
```
면내 보정은 두꺼운 파트에서 정확한 굽힘 형상을 위해 필요.

### 6. dat_pair 모드 (상/하면)

```
t_frac = (n - n_min) / (n_max - n_min)    // 0=하면, 1=상면
w_node = w_bottom·(1-t_frac) + w_top·t_frac
```
곡률 계산은 중면(midplane) 기준:
```
w_mid = (w_top + w_bottom) / 2
κ from w_mid grid
```

### 7. 응력 부호 규약

| 모드 | 기하 | 응력 | DR 결과 |
|------|------|------|---------|
| deform | 굽힌 형상 | 역방향 응력 (-ε) | 굽힌 상태 유지 |
| stress | 평면 유지 | 순방향 응력 (+ε) | 평면→굽힘 변형 |

```cpp
// deform 모드: 역방향 (squeeze와 동일 패턴)
StrainTensor reverseStrain = strain * (-1.0);
stress = StressTensor::fromStrain(reverseStrain, E, nu);

// stress 모드: 순방향
stress = StressTensor::fromStrain(strain, E, nu);
```

### 8. 응력 병합 (squeeze + bend 동일 파트)

같은 요소에 squeeze + bend가 적용되면 응력이 중복됨.
`writeOutput()`에서 출력 전 element ID별로 응력 합산:

```cpp
std::map<int, ElementResult> merged;
for (const auto& er : accumulatedResults_) {
    auto it = merged.find(er.elementId);
    if (it != merged.end()) {
        it->second.stress += er.stress;
        it->second.strain += er.strain;
    } else {
        merged[er.elementId] = er;
    }
}
```

---

## 구현 파일

### 새 파일 (4개)
1. `include/assembly/FormulaEvaluator.h` + `src/assembly/FormulaEvaluator.cpp`
2. `include/assembly/DeflectionGrid.h` + `src/assembly/DeflectionGrid.cpp`

### 수정 파일 (5개)
1. `include/assembly/AssemblyConfig.h` - BendOperation 구조체
2. `src/assembly/AssemblyConfigReader.cpp` - bend YAML 파싱
3. `include/assembly/ModelAssembler.h` + `src/assembly/ModelAssembler.cpp` - applyBend()
4. `src/main.cpp` - CLI dispatch
5. `CMakeLists.txt` - 소스 추가

---

## 검증

1. **formula 모드 검증**: amplitude=1.0, sin(pi*x1/L1)*sin(pi*x2/L2)
   - 중심 요소 곡률: κ = (π/λ)² · A
   - 상면 요소 응력: σ = E · d · κ (계산값과 비교)

2. **deform 모드 확인**: 출력 .k 파일에서 노드 좌표가 sin 형태로 변형되었는지 확인

3. **stress 모드 확인**: 노드 좌표 원래대로 + dynain에 굽힘 응력 존재

4. **squeeze + bend 조합**: 같은 파트에 두 오퍼레이션 → dynain에 요소별 1개 항목 (합산된 응력)

5. **dat 파일 테스트**: 포물선 w = ax² → κ₁₁ = 2a (상수) 확인
