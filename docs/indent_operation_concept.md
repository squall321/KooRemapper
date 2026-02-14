# `indent` 오퍼레이션: 부분 영역 표면 모핑 (필렛 인덴트)

## 1. 개요

### 목적
CAD 업데이트 없이 FEM 메쉬에서 직접 부분 영역 재설계를 검토한다.
공정(스탬핑/프레싱/사출)에서 나올 법한 필렛 형상을 자동 생성하여,
설계 변경 효과를 빠르게 평가할 수 있다.

### 동작 요약
```
 1. 대상 파트의 면 방향(plane + direction) 지정
 2. 면 위에 indent 형상 정의 (다각형/스플라인 closed loop)
 3. 각 노드의 loop까지의 signed distance로 영역 분류
 4. 안쪽 = 평면 indent (depth d), 경계 = quarter-arc 필렛, 바깥 = 원래 표면
 5. 외곽면 노드 이동 → 내부 노드 두께 보간 → 응력 계산(선택)
```

### 용도
- 사출 게이트/핀 위치 검토 (부분 눌림)
- 스탬핑 금형 형상 검토
- 배터리 셀 스웰링 부분 영역 평가
- 접합 홈/가이드 설계 검토
- 두께 변화 영역 영향도 분석


## 2. 컨셉

### 2.1 단면도

```
  위에서 본 평면도 (XY 평면, -Z 방향 indent):

  ╔═══════════════════════════════════════╗
  ║         원래 표면 (변경 없음)          ║
  ║                                       ║
  ║    ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐        ║
  ║    ╎   d = r1+r2 경계        ╎        ║
  ║    ╎  ┌───────────────────┐  ╎        ║
  ║    ╎  │  d = r1 경계      │  ╎        ║
  ║    ╎  │  ┌─────────────┐  │  ╎        ║
  ║    ╎  │  │  d < 0      │  │  ╎        ║
  ║    ╎  │  │ Flat indent │  │  ╎        ║
  ║    ╎  │  └─────────────┘  │  ╎        ║
  ║    ╎  │   r1 zone (steep) │  ╎        ║
  ║    ╎  └───────────────────┘  ╎        ║
  ║    ╎    r2 zone (gentle)     ╎        ║
  ║    └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘        ║
  ║                                       ║
  ╚═══════════════════════════════════════╝

  ※ 경계선은 signed distance의 등고선 (기하학적 offset loop이 아님)
```

```
  A-A 단면 (Quarter-Arc 필렛):

              r2 zone          r1 zone    flat     r1 zone         r2 zone
           (gentle arc)     (steep arc)  indent  (steep arc)    (gentle arc)

  z=0  ━━━━━━╲                                                ╱━━━━━━━
              ╲  ← r2 arc                          r2 arc →  ╱
               ╲   (완만)                           (완만)   ╱
                |                                          |
                | ← 접선 수직   접선 수직 →                 |
                |    (r1/r2 접합)                           |
               ╱                                            ╲
              ╱  ← r1 arc                          r1 arc →  ╲
             ╱    (급경사)                          (급경사)    ╲
  z=-d  ━━━╱━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╲━━━

  → 전체 전이 폭: r1 + r2
  → r1 구간: indent 바닥에서 수평 접선으로 시작, 수직 접선으로 끝
  → r2 구간: 수직 접선으로 시작, 원래 표면에서 수평 접선으로 끝
  → depth = r1+r2일 때: 정확한 1/4 원호, depth < r1+r2일 때: 1/4 타원
```

### 2.2 면 방향 / 인덴트 방향

| plane | 면내 축1 | 면내 축2 | 인덴트 방향 |
|-------|---------|---------|------------|
| xy    | x       | y       | +z 또는 -z |
| yz    | y       | z       | +x 또는 -x |
| zx    | z       | x       | +y 또는 -y |

- 인덴트 방향: 파트 표면을 "밀어넣는" 방향
- 예: plane=xy, direction=-z → +z를 바라보는 상면을 -z로 눌러내림

### 2.3 형상 정의 (Base Loop)

Closed loop으로 인덴트 영역의 경계를 정의:

```yaml
shape:
  type: polygon    # polygon | spline
  points:          # 면내 좌표 (x1, x2), 시계/반시계 모두 가능
    - [20, 15]
    - [80, 15]
    - [80, 35]
    - [20, 35]
```

- **polygon**: 점을 직선으로 연결 (사각형, L자 등)
- **spline**: 점을 cubic Catmull-Rom 스플라인으로 보간 (곡선 형상)
- 마지막 점 → 첫 점 자동 연결 (closed)

### 2.4 영역 분류 (Signed Distance 기반)

> **핵심 설계 결정**: 명시적 offset loop 생성을 하지 않는다.
> 각 노드의 base loop까지의 signed distance만으로 영역을 분류한다.
> 이렇게 하면 concave loop의 offset 자기교차 문제가 완전히 회피된다.

각 노드의 면내 좌표 (x₁, x₂)에서 base loop까지의 signed distance `d`:
```
  d < 0           : 루프 안쪽 → flat indent (깊이 = depth)
  0 ≤ d < r1      : r1 구간 → 하부 arc (indent 바닥 → 수직 접선)
  r1 ≤ d < r1+r2  : r2 구간 → 상부 arc (수직 접선 → 원래 표면)
  d ≥ r1+r2       : 루프 바깥 → 변경 없음
```

signed distance 부호 규약:
- 음수 = loop 안쪽 (indent 영역)
- 양수 = loop 바깥쪽

### 2.5 Quarter-Arc 프로파일 함수

두 개의 1/4 원호(quarter arc)로 높이가 다른 두 평면을 연결한다.
스탬핑/프레싱 금형의 필렛과 동일한 형상이다.

```
스케일링 팩터:
  k = depth / (r1 + r2)       (≤ 1 권장)

  k = 1: 정확한 1/4 원호 (depth = r1+r2)
  k < 1: 1/4 타원 (depth < r1+r2, 완만한 전이)
  k > 1: 경고 (급경사 타원 arc, depth > r1+r2). 수식은 유효하나 메쉬 품질 주의

r1 구간 (d ∈ [0, r1]) — 하부 arc (indent 바닥 → 접합점):
  t = d / r1
  h(d) = -depth + k·r1·(1 - sqrt(1 - t²))

  검증:
    h(0) = -depth ✓ (indent 바닥에서 연속)
    h(r1) = -depth + k·r1 = -depth·r2/(r1+r2) ✓
    h'(0) = 0 ✓ (수평 접선: flat indent와 매끄럽게 연결)
    h'(r1) → ∞ (수직 접선: 접합점)

r2 구간 (d ∈ [r1, r1+r2]) — 상부 arc (접합점 → 원래 표면):
  u = (r1+r2-d) / r2
  h(d) = -k·r2·(1 - sqrt(1 - u²))

  검증:
    h(r1) = -k·r2 = -depth·r2/(r1+r2) ✓ (하부 arc와 일치)
    h(r1+r2) = 0 ✓ (원래 표면으로 복귀)
    h'(r1) → ∞ (수직 접선: 접합점에서 하부 arc와 방향 일치)
    h'(r1+r2) = 0 ✓ (수평 접선: 원래 표면과 매끄럽게 연결)

요약:
  d < 0:       h = -depth              (flat indent)
  d ∈ [0,r1]:  h = -depth + k·r1·(1 - √(1-(d/r1)²))
  d ∈ [r1,R]:  h = -k·r2·(1 - √(1-((R-d)/r2)²))     여기서 R = r1+r2
  d ≥ R:       h = 0                   (원래 표면)
```

**프로파일 특성**:
- **C⁰ 연속**: 접합점(d=r1)에서 높이 일치 + 양쪽 수직 접선 방향 일치
- **수평 접선**: d=0 (indent 바닥)과 d=r1+r2 (원래 표면)에서 수평 → 평면과 매끄럽게 연결
- **비대칭**: r1 < r2이면 하부 급경사 + 상부 완만 (일반 스탬핑 필렛)
- **물리적 의미**: 금형 펀치 필렛(r1) + 다이 필렛(r2) 형상 그대로
- **제약**: depth ≤ r1+r2 권장. depth = r1+r2이면 정확한 원호. 초과 시 급경사 경고.

### 2.6 두께 관통 보간 (Through-Thickness)

외곽면만 이동하면 요소가 뒤집히거나 심하게 왜곡됨.
내부 노드도 두께 방향으로 보간 이동:

```
  t_frac = 두께 방향 상대 위치 (0=반대면, 1=indent면)

  indent 방향이 -z (상면을 아래로):
    t_frac = (n - n_min) / (n_max - n_min)
    → t_frac=1 (상면): h_surface (full indent)
    → t_frac=0 (하면): h_surface × bottom_ratio

  displacement = h_surface × [bottom_ratio + (1 - bottom_ratio) × t_frac]
```

**bottom_ratio 옵션**:
- 0.0 (기본): 상면만 이동, 하면 고정 → 두께 변화 발생
- 0.5: 상면 100%, 하면 50% → 부분 관통
- 1.0: 전체 관통 (rigid body처럼 이동) → 두께 보존

### 2.7 내부 노드 스무싱

> **설계 결정**: 초기 구현은 through-thickness 선형 보간만.
> Laplacian 스무싱은 복잡하고 느리며, extrude 형상에서는 불필요.
> 비정규 메쉬가 필요해질 때 추가.

Through-thickness 선형 보간:
- 파트의 법선 방향 BB (n_min, n_max) 계산
- 각 노드의 n_coord로 t_frac 결정
- indent면 → 반대면 사이를 선형 보간

이 방식의 한계:
- extrude 형상(두께 방향이 일정)에만 정확
- 곡면 파트에서는 두께 방향이 노드마다 다름 → 근사적


## 3. YAML 설정

```yaml
operations:
  - type: indent
    target_pid: 3
    plane: xy               # xy | yz | zx
    direction: -z           # +z/-z, +x/-x, +y/-y
    depth: 0.5              # 인덴트 깊이 (양수, 단위=모델 단위)
    r1: 2.0                 # 내측 필렛 폭 (steep side)
    r2: 3.0                 # 외측 필렛 폭 (gentle side)
    shape:
      type: polygon         # polygon | spline
      points:               # 면내 좌표 (x1, x2)
        - [20, 15]
        - [80, 15]
        - [80, 35]
        - [20, 35]
    # 선택 옵션
    bottom_ratio: 0.0       # 하면 이동 비율 (0.0=상면만, 1.0=관통, 기본:0.0)
    stress: false           # 초기응력 계산 (기본: false, DR 권장)
```

### 3.1 shape 타입별 예시

**polygon (직선 경계)**
```yaml
shape:
  type: polygon
  points:
    - [20, 15]    # 사각형 indent
    - [80, 15]
    - [80, 35]
    - [20, 35]
```

**spline (곡선 경계)**
```yaml
shape:
  type: spline
  points:
    - [50, 10]    # 타원 근사
    - [85, 25]
    - [50, 40]
    - [15, 25]
```

### 3.2 복합 예시 (squeeze + indent)

```yaml
base_model: battery_cell.k
output: indent_study

material:
  E: 210000
  nu: 0.3

dynamic_relaxation: true

operations:
  - type: squeeze
    target_pid: 3
    eps_x: 0.0
    eps_y: 0.0
    eps_z: -0.01

  - type: indent
    target_pid: 3
    plane: xy
    direction: -z
    depth: 0.3
    r1: 1.5
    r2: 2.5
    shape:
      type: spline
      points:
        - [30, 20]
        - [70, 20]
        - [70, 40]
        - [30, 40]
```


## 4. 알고리즘 상세

### 4.1 Closed Loop 표현

```cpp
class ClosedLoop {
public:
    void setPolygon(const std::vector<Vec2>& points);
    void setSpline(const std::vector<Vec2>& controlPoints,
                   int samplesPerSegment = 20);

    double signedDistance(const Vec2& p) const;  // 안쪽=음, 바깥=양
    bool isInside(const Vec2& p) const;

private:
    std::vector<Vec2> segments_;    // 평가된 세그먼트 (밀도 높은)
    // offset() 메서드는 의도적으로 제공하지 않음 (§2.4 참조)
};
```

> **설계 결정**: `offset()` 메서드를 제공하지 않는다.
> offset loop 계산은 concave 형상에서 자기교차(self-intersection) 문제를 일으킨다.
> 대신 signed distance 기반으로 영역을 분류하여 이 문제를 완전히 회피한다.

### 4.2 Signed Distance 계산

**문제점**: 단순 cross-product 부호 판별은 concave polygon에서 오류.
**해결**: Winding Number 알고리즘으로 내부/외부 판별.

```
signedDistance(P):
  1. 최소 거리 계산
     min_dist = ∞
     for each segment (A, B) in loop:
         t = clamp(dot(P-A, B-A) / |B-A|², 0, 1)
         closest = A + t*(B-A)
         dist = |P - closest|
         if dist < min_dist:
             min_dist = dist

  2. 부호 판별 (Winding Number)
     wn = 0
     for each segment (A, B):
         if A.y ≤ P.y:
             if B.y > P.y:
                 if cross(B-A, P-A) > 0: wn++
         else:
             if B.y ≤ P.y:
                 if cross(B-A, P-A) < 0: wn--

     inside = (wn ≠ 0)
     return inside ? -min_dist : +min_dist
```

**Winding Number의 장점**:
- Convex/concave/복잡한 형상 모두 정확
- O(N) per query (N = 세그먼트 수)
- 수치적으로 안정

### 4.3 성능 최적화

**문제점**: 노드 수 × 세그먼트 수 = O(N·M)이 대형 모델에서 병목.

**해결: AABB 사전 필터링**
```
1. Loop의 bounding box + (r1+r2) 여유 → affected_bbox
2. affected_bbox 밖의 노드는 즉시 skip (d ≥ r1+r2 보장)
3. 나머지 노드에 대해서만 정밀 signed distance 계산

예상 효과: 10,000 노드 모델에서 ~90% 노드 skip
```

**추가 최적화 (필요시)**:
- 세그먼트를 grid cell에 분류 → spatial hash
- 그러나 초기 구현에서는 AABB 필터만으로 충분할 것

### 4.4 표면 노드 감지

> **문제점**: HEX8 요소의 6개 면을 모두 검사하고, face-sharing을 판별해야 함.
> 순진한 구현은 O(elements²)이 됨.

**해결: Face Hash Map**
```
1. HEX8의 6개 면 정의 (노드 인덱스 조합):
   face 0: {0,1,2,3}, face 1: {4,5,6,7},
   face 2: {0,1,5,4}, face 3: {2,3,7,6},
   face 4: {0,3,7,4}, face 5: {1,2,6,5}

2. 각 면의 노드 ID를 정렬 → face key
   std::tuple<int,int,int,int> sorted(n0,n1,n2,n3)

3. face_count[face_key]++ 로 카운트
   count == 1 → 외곽면 (다른 요소와 공유 안 됨)
   count == 2 → 내부면

4. 외곽면의 법선 계산:
   normal = cross(n1-n0, n3-n0)
   if dot(normal, indent_direction) > 0.5:  ← 코사인 60°
       → 이 면의 4개 노드 = indent 대상 표면 노드
```

**시간 복잡도**: O(elements) — 각 요소의 6면을 해시맵에 삽입

### 4.5 Quarter-Arc 프로파일 (IndentProfile)

```cpp
class IndentProfile {
public:
    IndentProfile(double depth, double r1, double r2);

    // signed distance → 법선 방향 변위 (음수 = indent 방향)
    double getDisplacement(double signed_dist) const;

    // 전이 구간 전체 폭
    double transitionWidth() const { return r1_ + r2_; }

private:
    double depth_, r1_, r2_;
    double k_;            // = depth / (r1+r2), 스케일링 팩터

    double arcR1(double d) const;  // d ∈ [0, r1]
    double arcR2(double d) const;  // d ∈ [r1, r1+r2]
};
```

### 4.6 Through-Thickness 보간

```
applyIndent() 내부:

for each node in target_pid:
    (x1, x2) = 면내 좌표
    n = 법선 좌표

    d = loop.signedDistance(Vec2(x1, x2))
    if d >= r1 + r2: continue   // 영향 범위 밖

    h_surface = profile.getDisplacement(d)

    // 두께 방향 감쇠
    if indent_direction is negative:
        t_frac = (n - n_min) / (n_max - n_min)   // 0=하면, 1=상면
    else:
        t_frac = (n_max - n) / (n_max - n_min)   // 0=상면, 1=하면

    h = h_surface * [bottom_ratio + (1 - bottom_ratio) * t_frac]

    // 노드 이동: h=-depth, dir=-z → Δz = -(-depth)*(-1) = -depth ✓
    node.coord[normalAxis] -= h * sign(indent_direction)
```


## 5. 예상 문제점과 대책

### 5.1 프로파일 형상 (Quarter-Arc 채택)

**이전 검토**:
- smoothstep: 각 구간 양끝 기울기=0 → 접합점에서 기울기=0 (S자 아님)
- Cubic Hermite: 변곡점 기울기 명시 → S자는 되지만 실제 금형과 다름

**최종 설계: Quarter-Arc (1/4 원호)**
실제 스탬핑/프레싱 금형의 필렛 형상을 그대로 반영.
r1 = 펀치 필렛, r2 = 다이 필렛로 대응.
두 arc의 접합점(d=r1)에서 양쪽 수직 접선 → 방향 일치 (C⁰+).
평면 접합부(d=0, d=r1+r2)에서 수평 접선 → 평면과 매끄럽게 연결.

### 5.2 Concave Loop의 Offset 자기교차

**문제**: L자형, 별모양 등 concave loop을 오프셋하면
꼭짓점에서 자기교차(self-intersection) 발생.
```
     ┌─┐         offset        ┌──┐
     │ └──┐       →          ╱╲  └────┐
     │    │                 ╱ ╳╲      │  ← 자기교차!
     └────┘                ╱  ╲╱      │
                          └──────────┘
```

**대책**: 명시적 offset loop을 계산하지 않음.
signed distance 기반으로 영역을 분류하므로 이 문제가 발생하지 않음.
d=r1, d=r1+r2는 "등거리 경계"일 뿐 기하학적 loop이 아님.

### 5.3 Concave Loop의 Inside/Outside 판별

**문제**: 단순 cross-product는 concave polygon에서 부호 오류.
```
  ┌──┐
  │  └──┐     P 점이 "오목한 부분" 안쪽에 있으면
  │  P  │     최근접 edge의 cross-product가 바깥을 가리킴
  │  ┌──┘
  └──┘
```

**대책**: Winding Number 알고리즘 사용 (§4.2).
어떤 형태의 polygon/spline이든 정확한 내부/외부 판별.

### 5.4 Through-Thickness 정확도

**문제**: `t_frac = (n - n_min)/(n_max - n_min)`은
파트 전체 BB 기반이므로, 국소적으로 두께가 다르면 부정확.
```
     ┌──────────┐
     │  ┌────┐  │   ← 파트 상면이 평면이 아닌 경우
     │  │    │  │      BB의 n_max ≠ 해당 위치의 실제 표면
     └──┘    └──┘
```

**대책 (Phase 1)**: 파트가 extrude 형상이라고 가정.
→ BB 기반 t_frac이 정확.
대부분의 사용 사례(배터리 셀, 판재)에서 유효.

**대책 (향후)**: indent 영역 내의 노드만 대상으로
국소 n_min/n_max 계산 → 곡면 파트에도 대응 가능.

### 5.5 요소 품질 열화

**문제**: depth가 크거나 r1이 작으면 arc 곡률이 커져서
요소가 심하게 왜곡되거나 Jacobian < 0 (뒤집힘).

```
  depth/r1 > 0.5 → 경고 (급경사 필렛)
  depth > thickness * 0.8 → 에러 (두께 관통)
  depth / element_size > 1.0 → 경고 (해상도 부족)
```

**대책**: 사전 검증 + 경고/에러 메시지
```
[WARN] Steep fillet: depth/r1 = 0.63 > 0.5
       Consider increasing r1 or decreasing depth
[ERROR] Indent depth (0.9) exceeds 80% of part thickness (1.0)
```

### 5.6 메쉬 해상도 vs 필렛 크기

**문제**: r1+r2 전이 구간에 요소가 1~2개밖에 없으면
arc 필렛이 제대로 표현되지 않음.

```
  요소 크기 = 2.0, r1+r2 = 3.0
  → 전이 구간에 요소 ~1.5개 → 계단 형상

  요소 크기 = 0.5, r1+r2 = 3.0
  → 전이 구간에 요소 ~6개 → 매끄러운 arc 필렛
```

**대책**: 사전 경고
```
[WARN] Transition zone (r1+r2=3.0) spans only ~1.5 elements
       Recommend r1+r2 >= 4× element size for smooth fillet
```

### 5.7 Indent이 파트 경계 넘어가는 경우

**문제**: indent 영역 + r1+r2가 파트 BB 밖으로 나감.

**대책**: 허용. 파트 경계 밖의 노드는 없으므로 자연스럽게 잘림.
경고만 출력:
```
[WARN] Indent transition zone extends beyond part boundary
       Fillet may be truncated at part edge
```

### 5.8 Spline 오버슈트

**문제**: Catmull-Rom 스플라인은 control point 사이에서 오버슈트 가능.
indent 영역이 의도보다 크거나 작을 수 있음.

**대책**:
- 스플라인을 높은 밀도로 샘플링 (segment당 20점)
- 사용자에게 스플라인 결과를 시각적으로 확인하도록 권장
- 향후: centripetal Catmull-Rom (오버슈트 감소)으로 전환 가능


## 6. 구현 계획

### 새 파일

| 파일 | 설명 | 예상 규모 |
|------|------|----------|
| `include/assembly/ClosedLoop.h` | Closed loop (polygon/spline, signed distance) | ~50줄 |
| `src/assembly/ClosedLoop.cpp` | Winding number + segment distance | ~250줄 |
| `include/assembly/IndentProfile.h` | Quarter-arc 프로파일 클래스 | ~30줄 |
| `src/assembly/IndentProfile.cpp` | Quarter-arc 프로파일 | ~80줄 |

### 수정 파일

| 파일 | 변경 내용 | 예상 규모 |
|------|----------|----------|
| `include/assembly/AssemblyConfig.h` | `IndentOperation` 구조체, `INDENT` enum | ~30줄 |
| `src/assembly/AssemblyConfigReader.cpp` | `type: indent` YAML 파싱 + 검증 | ~80줄 |
| `include/assembly/ModelAssembler.h` | `applyIndent()` 선언 | ~5줄 |
| `src/assembly/ModelAssembler.cpp` | `applyIndent()` + face detection | ~400줄 |
| `src/main.cpp` | `INDENT` dispatch | ~5줄 |
| `CMakeLists.txt` | 새 소스 파일 추가 | ~2줄 |

**총 예상**: 새 코드 ~430줄 + 기존 수정 ~520줄 ≈ **~950줄**

### 구현 순서

```
Phase 1: ClosedLoop (polygon만)                         ★ 핵심
  1.1 Polygon 세그먼트 저장
  1.2 Signed distance (최근접점 + winding number)
  1.3 AABB 바운딩박스 (사전 필터용)
  → 단위 테스트: 사각형/L자 polygon의 signed distance 검증

Phase 2: IndentProfile                                   ★ 핵심
  2.1 Quarter-arc 프로파일
  2.2 depth, r1, r2 → getDisplacement(d)
  → 단위 테스트: 프로파일 값, C⁰ 연속, 경계값 검증

Phase 3: YAML 파싱 + 검증
  3.1 IndentOperation 구조체
  3.2 AssemblyConfigReader 확장
  3.3 검증: plane/direction 일관성, depth>0, r1>0, r2>0
  3.4 검증: depth < thickness * 0.8, depth/r1 경고

Phase 4: applyIndent() (polygon, bottom_ratio=0)         ★ 핵심
  4.1 plane → axis 매핑 (bend 코드 패턴 재사용)
  4.2 노드/요소 수집, BB 계산
  4.3 AABB 사전 필터
  4.4 signed distance → arc 프로파일 → through-thickness 보간
  4.5 노드 좌표 업데이트
  → 테스트: 사각형 indent on small block

Phase 5: Face Detection (표면 노드 최적화)
  5.1 Face hash map으로 외곽면 감지
  5.2 표면 노드 집합 구축 (선택적 최적화)
  ※ Phase 4에서는 모든 노드에 t_frac 적용으로도 동작함
     Face detection은 성능 최적화 + 검증용

Phase 6: Spline 확장
  6.1 Catmull-Rom spline interpolation (closed loop)
  6.2 스플라인 → 밀도 높은 segment 배열로 변환
  6.3 이후 로직은 polygon과 동일 (signed distance 재사용)
  → 테스트: 원형/타원 spline indent

Phase 7: 테스트 + 검증
  7.1 small block (8 요소) polygon indent
  7.2 large block (10,000 요소) polygon indent
  7.3 large block spline indent
  7.4 squeeze + indent 조합
  7.5 edge cases: 경계 넘김, 깊은 indent, L자 형상
  7.6 기존 기능 regression (52 unit tests)
```

**핵심 경로**: Phase 1 → 2 → 3 → 4 (이것만으로 polygon indent 동작)
**후속**: Phase 5 (최적화) → 6 (spline) → 7 (검증)


## 7. 검증 계획

### 7.1 기본 검증 (사각형 indent)
```
10×10×2 블록, 사각형 indent [3,3]→[7,7], depth=0.5, r1=0.5, r2=1.0

기대값:
  - (5,5) 상면 z: 2.0 → 1.5 ✓ (full depth)
  - (3,5) 상면 z: d=0 (loop 위) → flat indent 경계

사실상 (k = 0.5/(0.5+1.0) = 1/3):
  - d < 0 (loop 안쪽): z = 2.0 - 0.5 = 1.5
  - d = 0 (loop 위): z = 2.0 - 0.5 = 1.5 (flat indent 경계)
  - d = r1 = 0.5: z = 2.0 + h(r1) = 2.0 - k·r2 = 2.0 - 0.333 = 1.667 (arc 접합점)
  - d = r1+r2 = 1.5: z = 2.0 (원래)
  - d > 1.5: z = 2.0 (변경 없음)

  하면 (z=0): 변경 없음 (bottom_ratio=0)
  중간 (z=1): 상면의 50% 이동
```

### 7.2 프로파일 검증
```
C⁰ 연속: h(r1⁻) = h(r1⁺) = -k·r2 (양쪽 arc 접합점 높이 일치)
접선 방향: d=r1에서 양쪽 arc 모두 수직 접선 (방향 일치)
수평 접선: h'(0) = 0, h'(r1+r2) = 0 (평면과 매끄러운 연결)
경계: h(0) = -depth, h(r1+r2) = 0 정확
단조: d ∈ [0, r1+r2]에서 h 단조 증가
```

### 7.3 대형 모델 성능
```
50×40×5 블록 (10,000 요소, 12,546 노드):
  - AABB 필터 후 실제 계산 노드 < 30%
  - 처리 시간 < 500ms
```

### 7.4 메쉬 품질
```
indent 후 모든 요소의 min Jacobian > 0 확인
(Jacobian 계산은 검증 시에만, 실제 코드에는 경고만)
```


## 8. 향후 확장 가능성

- **다중 indent**: 같은 파트에 여러 indent 순차 적용 (이미 지원 구조)
- **emboss (양각)**: depth를 음수로 해석 → 돌출 형상
- **비균일 depth**: indent 영역 내 depth를 dat 그리드로 지정
- **경사 indent**: 법선이 아닌 임의 방향 (회전 변환)
- **곡면 파트**: 국소 두께 방향 감지 (surface normal 기반)
- **응력 계산**: arc 곡률 기반 Kirchhoff 굽힘 응력 (bend 코드 재활용)
- **자동 리메쉬**: indent 영역의 요소 세분화
