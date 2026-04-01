# CNRB to Solid Conversion (cnrb2solid)

## 1. 개요

FE 모델에서 볼트 연결부를 `*CONSTRAINED_NODAL_RIGID_BODY` (CNRB)로 모델링하는 것이 일반적이다.
CNRB는 정적 해석에서는 충분하지만, 명시적 동역학 해석(낙하, 충격)에서는 실제 솔리드 요소로 대체해야
현실적인 변형 거동을 포착할 수 있다.

**핵심 아이디어**: CNRB에 속한 볼트홀 노드들로부터 실린더 형상을 자동 추론하고,
O-grid(butterfly) 토폴로지의 HEX8 메쉬를 생성하여 CNRB를 대체한다.
추가로 볼트 헤드(플랜지)를 자동 생성하여 실제 볼트 형상을 재현한다.

```text
[CNRB 볼트 모델링] ──── cnrb2solid ────> [O-grid HEX8 볼트 + Tied Contact]
   (강체 구속)                                (샤프트 + 헤드 솔리드)
        ↑                                          ↑
  노드셋 기하학에서                        PCA 축 자동감지
  실린더 파라미터 역산                     볼트 헤드 자동 생성

  단면도 (축 방향 절단):

       ┌─────────────┐  ← head_thickness
       │  Bolt Head  │  ← R_shaft + head_offset_r
       ├───┐     ┌───┤
           │     │
           │Shaft│      ← R_shaft (CNRB 노드에서 감지)
           │     │
           └─────┘
```

---

## 2. 레퍼런스 알고리즘 분석

`references/CNRB/` 디렉토리의 pyKooCAE 구현을 분석한 결과:

### 2.1 입력/출력

| 구분 | 내용 |
|------|------|
| **입력** | K-file 내 `*CONSTRAINED_NODAL_RIGID_BODY`, `*SET_NODE_LIST`, 노드 좌표 |
| **출력** | CNRB 제거 + HEX8 실린더 메쉬 + `*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET` |
| **파라미터** | E, PR, RHO, RadiusScale, NumCircumNodes, InnerRadiusRatio, AxisDirection, ZTolerance, RTolerance |

### 2.2 알고리즘 10단계

1. **축 방향 감지 (PCA)**: 노드 공분산 행렬 고유값분해 → 최대 분산 방향 = 실린더 축
2. **원통좌표 변환**: (x,y,z) → (R, θ, Z_local)
3. **Z-Level 그룹핑**: ZTolerance 기반 높이별 노드 분류
4. **R-Value 클러스터링**: 다중 반경 지원 (좁은 샤프트 + 넓은 헤드)
5. **Conformal 메쉬 전략**: R_max 기준 전체 그리드 생성, 로컬 R 초과 요소만 생략
6. **O-Grid 단면 생성**: Core 정사각 격자 + 외곽 원형 링 (butterfly mesh)
7. **HEX8 노드 순서**: LS-DYNA 규칙 (바닥면 반시계, 오른손 법칙)
8. **R-기반 요소 필터링**: Z 레이어별 로컬 R에 따라 외곽 링 요소 생략/포함
9. **Tied Contact 생성**: 원본 노드 ↔ 신규 솔리드 파트 간 힘 전달
10. **정리**: CNRB 삭제, 중심노드(PNODE) 제거, ID 동기화

### 2.3 두 가지 테스트 케이스

| 케이스 | 특징 | 노드 수 | 결과 |
|--------|------|---------|------|
| **Uniform** | 단일 R=3.0, 균일 Z간격, 3개 Z-level | 24 | 깔끔한 균일 실린더 |
| **NonUniform** | 이중 R(샤프트+헤드), 불균일 Z, 가변 θ분포 | 61 | 단계형 실린더 (R 전환) |

---

## 3. KooRemapper 구현 설계

### 3.1 커맨드 인터페이스

**Standalone 커맨드:**
```bash
KooRemapper cnrb2solid config.yaml
```

**Assemble operation:**
```yaml
operations:
  - type: cnrb2solid
    target: all          # all / pid_list / nsid_list
    E: 200000.0          # MPa (t/mm/s 단위계)
    PR: 0.3
    RHO: 7.85e-9
    radius_scale: 0.999
    num_circum_nodes: 0  # 0=auto
    inner_radius_ratio: 0.3
    axis_direction: auto # auto/x/y/z
    z_tolerance: 0.1
    r_tolerance: 0.5
    # --- 볼트 헤드 파라미터 ---
    head_offset_r: 1.5   # 헤드 반경 = R_shaft + head_offset_r (mm)
    head_thickness: 2.0   # 헤드 축방향 두께 (mm)
    head_position: auto   # auto(큰R 쪽)/top/bottom/none
```

**YAML 설정 (standalone):**
```yaml
model: input_model.k
output: output_model.k

cnrb2solid:
  target: all           # all | [200, 300, 400]
  E: 200000.0
  PR: 0.3
  RHO: 7.85e-9
  radius_scale: 0.999
  num_circum_nodes: 0
  inner_radius_ratio: 0.3
  axis_direction: auto
  z_tolerance: 0.1
  r_tolerance: 0.5
  # --- 볼트 헤드 파라미터 ---
  head_offset_r: 1.5     # 헤드 반경 = R_shaft + head_offset_r (mm)
  head_thickness: 2.0     # 헤드 축방향 두께 (mm)
  head_position: auto     # auto | top | bottom | none
```

#### 볼트 헤드 파라미터 상세

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `head_offset_r` | 0.0 (헤드 없음) | 샤프트 R에 더할 헤드 반경 오프셋 (mm). 0이면 헤드 미생성 |
| `head_thickness` | 2.0 | 볼트 헤드의 축방향 두께 (mm). 헤드 Z-layer 수 = 1 (단일 레이어) |
| `head_position` | auto | `auto`: 상/하단 중 큰 R 쪽에 배치. `top`: Z_max 쪽. `bottom`: Z_min 쪽. `none`: 헤드 미생성 |

```text
예시: R_shaft=3.0, head_offset_r=1.5, head_thickness=2.0

        R_head = 4.5
    ┌───────────────┐  Z=12 (head_thickness=2)
    │   Bolt Head   │
    ├────┐     ┌────┤  Z=10 (원래 CNRB Z_max)
         │     │
         │     │       R_shaft=3.0
         │     │
         └─────┘       Z=0  (원래 CNRB Z_min)
```

### 3.2 파서 확장 (KFileReader)

현재 `KFileReader`는 `*CONSTRAINED_NODAL_RIGID_BODY`를 파싱하지 않는다. 추가 필요:

```cpp
// 새로운 데이터 구조
struct CNRBDefinition {
    int pid;          // CNRB PID
    int nsid;         // Node Set ID
    int pnode;        // Pilot/Center node
    std::string title;
};

// KFileReader에 추가
std::vector<CNRBDefinition> cnrbDefinitions_;

// *SET_NODE_LIST 파싱도 필요
std::map<int, std::vector<int>> nodeSetMap_;  // NSID → [node IDs]
```

### 3.3 핵심 알고리즘 구현

#### 3.3.1 PCA 축 감지

```cpp
// 3x3 공분산 행렬 → 고유값 분해 (Jacobi rotation 또는 직접 해법)
// 가장 큰 고유값의 고유벡터 = 실린더 축
Vector3D detectCylinderAxis(const std::vector<Vector3D>& nodes, Vector3D center) {
    // 1. 중심 빼기
    // 2. 공분산 행렬 계산 (대칭 3x3)
    // 3. 고유값 분해 (analytic formula for 3x3 symmetric)
    // 4. 최대 고유값 → 해당 고유벡터 반환
}
```

**3x3 대칭 행렬 고유값 분해**: 외부 라이브러리 없이 Cardano's formula 또는 Jacobi rotation으로 구현 가능. 기존 코드에 행렬 연산이 없으므로 analytic 해법 채택.

#### 3.3.2 O-Grid 메쉬 생성

```
         ○─○─○─○─○
        /           \
       ○  □─□─□─□  ○
       |  | | | |  |     □ = core (정사각 격자)
       ○  □─□─□─□  ○     ○ = ring (원형)
       |  | | | |  |
       ○  □─□─□─□  ○
        \           /
         ○─○─○─○─○
```

- N = 원주 노드 수 (4의 배수)
- m = N/4 (사분면당 세그먼트)
- Core: (m+1)×(m+1) 격자, 변 = 2·R·ratio
- Ring: N개 노드를 원형 배치
- Shell 요소: Core 경계 ↔ Ring 연결

#### 3.3.3 다중 반경 처리

```text
Chain 1 (R~1.5): Z=0, Z=2, Z=4       ← 좁은 샤프트
Chain 2 (R~3.0): Z=4, Z=6, Z=8       ← 넓은 헤드

→ R_max 기준으로 전체 노드 생성
→ Z-layer별 로컬 R 초과 요소만 생략
→ 공유 노드 보장 (conformal mesh)
```

#### 3.3.4 볼트 헤드 생성

CNRB 노드로부터 샤프트를 생성한 후, 한쪽 끝에 헤드(플랜지)를 추가 생성한다.

**헤드 위치 결정 (auto 모드):**

CNRB 노드에서 다중 R이 감지된 경우, 큰 R 쪽이 이미 헤드에 해당하므로
자연스럽게 해당 방향에 헤드를 배치한다.
단일 R인 경우, Z_max 쪽을 기본 헤드 위치로 사용한다.

```text
auto 판별 로직:
  1. Z-level별 R_avg 계산
  2. R_max가 위치한 Z 끝단 결정 (Z_min 쪽 vs Z_max 쪽)
  3. R_max 쪽에 헤드 배치
  4. 단일 R (모든 Z-level에서 R 동일) → Z_max 쪽에 배치
```

**헤드 메쉬 생성 (R_max 필터링 방식):**

레퍼런스 알고리즘의 "R_max 기준 전체 생성 → 로컬 R 초과 요소 삭제" 패턴을 그대로 확장한다.

```text
R_head = R_shaft + head_offset_r
R_shaft = CNRB 노드에서 감지된 샤프트 반경

핵심 원리:
  1. 헤드 Z-level 추가: Z_head_top = Z_head_base ± head_thickness
  2. R_head 기준으로 전체 O-grid 실린더를 모든 Z-level에 생성
     (Core + 샤프트 ring + 헤드 ring, 모든 Z에 동일한 노드 그리드)
  3. Z-level별 로컬 R로 요소 필터링:
     - 헤드 구간 (Z_head_base ~ Z_head_top): R_local = R_head → 전체 ring 유지
     - 샤프트 구간 (나머지 Z):              R_local = R_shaft → 외곽 ring 삭제

단면도 (head_position=top, 필터링 후):

                   ← 삭제됨 →      ← 삭제됨 →
  Z_head_top ─→ ┌───┬─────────┬───┐  R_head    ← 헤드: 전체 유지
                 │   │  Head   │   │
  Z_head_base ─→ ├───┼────┬────┼───┤
                 :삭제│    │삭제:            ← 샤프트: 외곽 ring 삭제
                      │    │
                      │Shaft│    R_shaft
                      │    │
  Z_min ────────→    └────┘

  → 노드는 모든 Z-level에 R_head까지 생성 (orphan 노드 허용)
  → 요소만 R_local 기준으로 생성/생략
  → 헤드-샤프트 경계(Z_head_base)는 노드 공유 → conformal 보장
```

이 방식의 장점:
- 레퍼런스의 다중 R 필터링 로직을 **그대로 재사용**
- 헤드 Z-level을 추가하고 R_local 맵에 R_head를 등록하면 끝
- 별도의 헤드 생성 로직이 필요 없음 (기존 필터링이 알아서 처리)

```text
R_local 맵 구성 예시 (head_position=top):

  Z-level   R_local
  ───────   ───────
  Z=0       R_shaft (3.0)    ← 샤프트 구간
  Z=5       R_shaft (3.0)
  Z=10      R_shaft (3.0)    ← Z_head_base
  Z=12      R_head  (4.5)    ← 추가된 헤드 Z-level

Head ring 수 결정:
  K = max(1, round(head_offset_r / (R_shaft / num_shaft_rings)))
  → 샤프트 ring 간격과 비슷한 크기로 head ring 분할
```

### 3.4 구현 파일 구조

기존 KooRemapper 아키텍처(v1.4.0 모듈 구조)를 따라:

| 파일 | 역할 |
|------|------|
| `src/commands/cnrb2solid.cpp` | `runCnrb2Solid()` 커맨드 진입점 + YAML 파싱 |
| `src/assembly/Cnrb2SolidConverter.cpp` | 핵심 변환 로직 (PCA, O-grid, 요소 생성) |
| `include/assembly/Cnrb2SolidConverter.h` | 헤더 |
| `src/main.cpp` | CLI 디스패치 추가 (기존 패턴 따름) |

### 3.5 raw-line 기반 처리 (assemble 통합)

`ModelAssembler`의 raw-line 패턴을 따라:

```cpp
// 1. CNRB 블록 위치 찾기 (rawLines_ 스캔)
//    *CONSTRAINED_NODAL_RIGID_BODY[_TITLE]
//    → title line (if _TITLE) + data line (PID, CID, NSID, PNODE, ...)

// 2. 노드셋 파싱
//    *SET_NODE_LIST[_TITLE] → NSID 매칭 → 노드 ID 수집

// 3. 실린더 생성 후 rawLines_에 삽입:
//    - *NODE (신규 노드)
//    - *ELEMENT_SOLID (O-grid HEX8)
//    - *PART (CNRB PID 재사용)
//    - *SECTION_SOLID (ELFORM=1)
//    - *MAT_ELASTIC (E, PR, RHO)
//    - *CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET

// 4. CNRB 블록 삭제 (rawLines_에서 해당 라인 제거)
// 5. PNODE 삭제 (해당 노드 라인 제거)
```

---

## 4. 구현 단계

### Phase 1: 파서 + 기본 변환 (Standalone)

1. `*CONSTRAINED_NODAL_RIGID_BODY` 파싱 (rawLines_ 스캔)
2. `*SET_NODE_LIST` 파싱
3. PCA 축 감지 구현
4. 원통좌표 변환 + Z-level 그룹핑
5. O-grid 메쉬 생성 (단일 R, 균일 Z)
6. HEX8 요소 생성 + LS-DYNA 노드 순서
7. Tied Contact 생성
8. CNRB 삭제 + 출력
9. **검증**: `references/CNRB/ConvertCNRBtoSolid/sample_cnrb.k` 로 테스트

### Phase 2: 다중 R + 볼트 헤드

1. R-value 클러스터링 (다중 반경)
2. R_max 기준 전체 O-grid 생성 + R_local 필터링 (단계형 실린더)
3. Auto NumCircumNodes (Z-level 최대 노드 수 기반)
4. 볼트 헤드: head_offset_r, head_thickness, head_position 파라미터 처리
5. 헤드 Z-level 추가 + R_local 맵에 R_head 등록 (기존 필터링 재사용)
6. **검증**: `references/CNRB/ConvertCNRBtoSolid_NonUniform/sample_nonuniform.k` 로 테스트
7. **검증**: 볼트 헤드 생성 후 LS-PrePost에서 형상 + Jacobian 확인

### Phase 3: assemble 통합

1. `ModelAssembler`에 `applyCnrb2Solid()` 추가
2. YAML operation `type: cnrb2solid` 파싱
3. ID 오프셋/리넘버링 연동
4. 다른 operation과의 순서 호환 확인

---

## 5. 기술적 고려사항

### 5.1 3x3 고유값 분해

외부 라이브러리(Eigen 등) 의존 없이 구현해야 한다.
3x3 대칭 행렬의 경우 Cardano's formula로 closed-form 해가 가능:

```
특성방정식: λ³ - tr(A)λ² + (cofactor sum)λ - det(A) = 0
→ Cardano's formula로 3개 실수근 구함
→ 각 고유값에 대해 (A - λI)x = 0 풀어서 고유벡터
```

기존 프로젝트에서 `Vector3D`의 `cross()`, `dot()`, `normalize()` 등 활용 가능.

### 5.2 LS-DYNA 호환성

- **PID 재사용**: CNRB의 PID를 솔리드 파트에 부여하여 ID 네임스페이스 유지
- **SECID/MID**: maxSecId++, maxMatId++ 로 새 ID 할당 (기존 패턴)
- **노드 ID**: maxNodeId 이후 연번 (기존 addedNodes_ 패턴)
- **요소 ID**: maxElementId 이후 연번 (기존 addedElements_ 패턴)

### 5.3 기존 코드 재활용

| 기능 | 기존 코드 | 활용 |
|------|----------|------|
| Vector3D 연산 | `src/core/Vector3D.h` | cross, dot, normalize |
| 노드/요소 추가 | `ModelAssembler::addedNodes_` | 동일 패턴 |
| rawLines_ 파싱 | `ale_buildPartMap()` 등 | CNRB/SET_NODE_LIST 스캔 |
| K-file 출력 | `KFileWriter` | 고정폭 필드 포맷팅 |
| YAML 파싱 | `AssemblyConfigReader` | operation 파싱 |

### 5.4 엣지 케이스

1. **CNRB 없는 모델**: 경고 출력 후 원본 그대로 출력
2. **PNODE가 없는 CNRB** (PNODE=0): 노드셋 중심점 사용
3. **노드가 4개 미만**: O-grid 불가 → 에러 메시지
4. **매우 작은 R**: InnerRadiusRatio 조정 또는 core-only 메쉬
5. **비원형 배치**: PCA 결과 2번째/3번째 고유값 비율로 원형도 체크

---

## 6. 예상 결과물

### 6.1 Uniform 케이스 (sample_cnrb.k)

```
입력: 24노드, R=3.0, Z=0/5/10 (3 Z-level)
CNRB PID=200, PNODE=1

출력:
- CNRB 삭제
- O-grid 실린더: N=8, m=2
  - Core: 4요소/layer × 2layer = 8
  - Ring: 8요소/layer × 2layer = 16
  - 총 24 HEX8 요소
- 새 노드: 9/layer × 3level = 27 (core+ring)
- Tied contact: 원본 24노드 ↔ PID=200 솔리드
```

### 6.2 Uniform + 볼트 헤드 케이스

```
입력: 위와 동일 + head_offset_r=1.5, head_thickness=2.0, head_position=top

R_shaft=3.0, R_head=4.5
Z-levels: 0, 5, 10 (샤프트) + 12 (헤드 추가)
전체 O-grid: R_head=4.5 기준 (core + shaft_ring + head_ring)

R_local 맵:
  Z=0:  R_local=3.0 → core + shaft_ring만 생성
  Z=5:  R_local=3.0 → core + shaft_ring만 생성
  Z=10: R_local=3.0 → core + shaft_ring만 생성 (헤드 바닥)
  Z=12: R_local=4.5 → core + shaft_ring + head_ring 전체 생성

결과:
  샤프트 layer (Z=0~5, 5~10): 각 (core + shaft_ring) × 2 = 기존과 동일
  헤드 layer (Z=10~12): core + shaft_ring + head_ring(s) = 확장
  노드는 모든 Z에 R_head까지 생성 (샤프트 구간 외곽 노드는 orphan)
```

### 6.3 NonUniform 케이스 (sample_nonuniform.k)

```
입력: 61노드, R~1.5(Z=0~2.7) + R~3.0(Z=4~10), 불균일 Z
CNRB PID=300

출력:
- 단계형 실린더: 작은 R 구간은 core+1ring, 큰 R 구간은 core+2ring
- Auto N: 가변 원주 노드수 (최대 Z-level의 노드수 기준)
- head_offset_r 지정 시: 큰 R(3.0) 쪽 끝에 추가 헤드 생성
```

---

## 7. 테스트 계획

| 단계 | 테스트 | 검증 기준 |
|------|--------|----------|
| 1 | Uniform 기본 변환 | 레퍼런스 출력(`sample_cnrb_cnrb2solid.k`)과 요소 수/토폴로지 일치 |
| 2 | 축 감지 (X/Y/Z 방향) | 회전된 모델에서 PCA 축 정확도 |
| 3 | NonUniform 변환 | 단계형 R 전환 정확, conformal mesh |
| 4 | LS-PrePost 시각화 | 메쉬 형상 + Jacobian 양수 확인 |
| 5 | assemble 통합 | 다른 operation과 조합 시 ID 충돌 없음 |
| 6 | ALL 모드 | 다수 CNRB 일괄 변환 |

---

## 8. 참고 파일

- `references/CNRB/ConvertCNRBtoSolid/ALGORITHM.md` - 상세 알고리즘 문서
- `references/CNRB/ConvertCNRBtoSolid/sample_cnrb.k` - 균일 테스트 입력
- `references/CNRB/ConvertCNRBtoSolid/sample_cnrb_cnrb2solid.k` - 균일 테스트 정답
- `references/CNRB/ConvertCNRBtoSolid_NonUniform/sample_nonuniform.k` - 비균일 입력
- `references/CNRB/ConvertCNRBtoSolid_NonUniform/sample_nonuniform_cnrb2solid.k` - 비균일 정답
