# KooRemapper 매핑 개념 문서

## 개요

KooRemapper는 **구조화된 육면체(HEX8) 레퍼런스 메쉬**를 기반으로 **임의의 플랫 메쉬**를 굽힘 형상으로 매핑하는 도구입니다.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Bent Mesh     │     │   Flat Mesh     │     │  Mapped Mesh    │
│  (Reference)    │  +  │   (Target)      │  →  │   (Result)      │
│  Structured     │     │  Any Type       │     │  Same as Flat   │
│  HEX8 Only      │     │  HEX8/TET4/...  │     │  Bent Shape     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## 메쉬 요구사항

### Bent Mesh (레퍼런스)
- **필수**: Structured Hexahedral (HEX8) 메쉬
- 3D 구조화 그리드 (i, j, k 인덱싱 가능)
- 굽힘/변형된 형상

### Flat Mesh (매핑 대상)
- **유연**: HEX8, TET4 등 다양한 요소 타입 지원
- Structured 또는 Unstructured
- 다른 해상도 가능
- 평평한(펼쳐진) 형상

## 핵심 알고리즘

### 1. Bent Mesh 분석

```
Bent Mesh
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ StructuredGridIndexer                                    │
│ - 요소 연결성 분석                                        │
│ - (i, j, k) 인덱스 할당                                   │
│ - 그리드 차원 결정 (dimI × dimJ × dimK)                   │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ BoundaryExtractor                                        │
│ - 8개 코너 노드 추출                                      │
│ - 12개 에지 추출                                          │
│ - 6개 면 추출                                             │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ EdgeCalculator                                           │
│ - 12개 에지의 노드 포인트 시퀀스 추출                      │
│ - 각 에지의 segment arc-length 계산                       │
│ - i-에지 (4개): 길이 방향                                 │
│ - j-에지 (4개): 폭 방향                                   │
│ - k-에지 (4개): 두께 방향                                 │
└─────────────────────────────────────────────────────────┘
```

### 2. 파라메트릭 공간 구축

```
8 Corners + 12 Edges + 6 Faces
            │
            ▼
┌─────────────────────────────────────────────────────────┐
│ ParametricMapper                                         │
│                                                          │
│  파라메트릭 좌표 (u, v, w) ∈ [0,1]³                       │
│                                                          │
│       k=1 (w=1)                                          │
│        7 ──────── 6                                      │
│       /│         /│                                      │
│      / │        / │     u: i-방향 (길이)                  │
│     4 ──────── 5  │     v: j-방향 (폭)                    │
│     │  │       │  │     w: k-방향 (두께)                  │
│     │  3 ──────│─ 2                                      │
│     │ /        │ /                                       │
│     │/         │/                                        │
│     0 ──────── 1        k=0 (w=0)                        │
│   (0,0,0)    (1,0,0)                                     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 3. Arc-Length 기반 보간 (핵심)

#### Arc-Length Based Edge Interpolation

```cpp
Vector3D EdgeInterpolator::interpolate(double t) {
    // t를 arc-length 비율로 해석
    double targetLength = t * totalLength_;
    
    // 해당 arc-length 위치의 세그먼트 찾기
    auto it = std::lower_bound(arcLengths_.begin(), arcLengths_.end(), targetLength);
    size_t idx = it - arcLengths_.begin();
    
    // 세그먼트 내 로컬 보간
    double segmentLength = arcLengths_[idx + 1] - arcLengths_[idx];
    double localT = (targetLength - arcLengths_[idx]) / segmentLength;
    
    return lerp(points_[idx], points_[idx + 1], localT);
}
```

**장점**:
- 노드 분포에 무관하게 물리적으로 정확한 위치 계산
- U-fold 등 곡률이 집중된 영역에서도 정확한 매핑
- FlatMeshGenerator와 EdgeInterpolator 간 완벽한 일관성

#### Edge-Based 3D Interpolation

```cpp
Vector3D edgeBasedInterpolate(double u, double v, double w) {
    // 4개 i-에지에서 u 위치의 점 계산 (arc-length 기반)
    Vector3D p00 = edges_[0].interpolate(u);  // j=0, k=0
    Vector3D p10 = edges_[1].interpolate(u);  // j=1, k=0
    Vector3D p01 = edges_[2].interpolate(u);  // j=0, k=1
    Vector3D p11 = edges_[3].interpolate(u);  // j=1, k=1

    // v, w 방향 bilinear 보간
    Vector3D bottom = lerp(p00, p10, v);  // k=0 라인
    Vector3D top = lerp(p01, p11, v);     // k=1 라인

    return lerp(bottom, top, w);
}
```

### 4. 노드 매핑 과정

```
Flat Mesh Node (x, y, z)
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│ 파라메트릭 좌표 계산                                      │
│                                                          │
│   u = (x - minX) / sizeX    (arc-length 비율)            │
│   v = (y - minY) / sizeY                                 │
│   w = (z - minZ) / sizeK                                 │
│                                                          │
│   * sizeX = bent mesh의 평균 arc-length                  │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│ ParametricMapper.mapToPhysical(u, v, w)                  │
│ - Arc-length 기반 edge interpolation 사용                │
└─────────────────────────────────────────────────────────┘
         │
         ▼
    Mapped Position (x', y', z')
```

## Arc-Length 일관성 원칙

KooRemapper의 핵심 설계 원칙은 **모든 컴포넌트가 동일한 arc-length 데이터를 사용**하는 것입니다:

```
┌─────────────────────────────────────────────────────────┐
│                    EdgeCalculator                        │
│   - 12개 edge의 segment lengths 계산                     │
│   - cumulative arc-lengths 제공                          │
└─────────────────────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│FlatMeshGen   │ │EdgeInterp    │ │MeshRemapper  │
│              │ │              │ │              │
│X = avg       │ │t → physical  │ │u = x/sizeX   │
│  arc-length  │ │  arc-length  │ │              │
│  of 4 edges  │ │  based       │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
```

### 왜 Arc-Length인가?

**Index-based (노드 인덱스 기반)의 문제점:**
```
Bent mesh에서 곡률이 높은 구간에 노드가 밀집된 경우:

Node Index:  0---1---2---3---4---5---6---7---8---9---10
             |   |   | | | | | | |   |   |   |
Arc-Length:  0% 10% 20%|30|35|40|45|50% 60% 80% 100%
                       ↑ 곡률 구간 ↑

Index-based: t=0.5 → node 5 (실제 arc-length 45%)
Arc-length:  t=0.5 → 정확히 50% arc-length 위치
```

**Arc-length 기반의 장점:**
- 노드 분포에 무관하게 물리적으로 정확한 위치
- `FlatMeshGenerator`가 생성한 X 좌표와 `EdgeInterpolator`가 1:1 대응
- t-remap 같은 특수 처리 불필요

## 지원 요소 타입

### HEX8 (8-node Hexahedron)
```
     7 ──────── 6
    /│         /│
   / │        / │
  4 ──────── 5  │
  │  │       │  │
  │  3 ──────│─ 2
  │ /        │ /
  │/         │/
  0 ──────── 1
```
- Bent mesh: 필수
- Flat mesh: 지원

### TET4 (4-node Tetrahedron)
```
       3
      /│\
     / │ \
    /  │  \
   /   │   \
  0────│────2
   \   │   /
    \  │  /
     \ │ /
      \│/
       1
```
- Bent mesh: 미지원
- Flat mesh: 지원
- LS-DYNA 출력: n5=n6=n7=n8=n4 형식

### Jacobian 계산

**HEX8**:
```cpp
// 요소 중심에서의 Jacobian
J = dX/du · (dX/dv × dX/dw)
```

**TET4**:
```cpp
// 6 × signed volume
J = (v1-v0) · ((v2-v0) × (v3-v0))
```

## 파일 구조

```
include/
├── mapper/
│   ├── ParametricMapper.h    # 파라메트릭 매핑
│   ├── EdgeInterpolator.h    # Arc-length 기반 에지 보간
│   ├── FaceInterpolator.h    # 면 보간
│   ├── FlatMeshGenerator.h   # Bent→Flat 메쉬 생성
│   └── MeshRemapper.h        # 메인 매핑 클래스
├── grid/
│   ├── StructuredGridIndexer.h  # 구조화 인덱싱
│   ├── BoundaryExtractor.h      # 경계 추출
│   └── EdgeCalculator.h         # 에지/arc-length 계산
└── core/
    ├── Mesh.h                # 메쉬 데이터
    ├── Element.h             # 요소 (HEX8, TET4)
    └── Node.h                # 노드

src/
├── mapper/
│   ├── ParametricMapper.cpp
│   ├── EdgeInterpolator.cpp    # Arc-length 기반 보간 구현
│   ├── FaceInterpolator.cpp
│   ├── FlatMeshGenerator.cpp   # Edge arc-length 평균 사용
│   └── MeshRemapper.cpp
└── ...
```

## 사용 예시

```bash
# 예제 메쉬 생성 (waterdrop)
KooRemapper generate waterdrop foldable --dim-i 50 --dim-j 25 --dim-k 3

# 생성되는 파일:
# - foldable_bent.k      : 구조화 HEX8 레퍼런스 (굽힘 형상)
# - foldable_flat.k      : 동일 해상도 HEX8 플랫
# - foldable_flat_fine.k : 2배 해상도 HEX8 플랫
# - foldable_flat_tet.k  : TET4 플랫

# HEX8 매핑
KooRemapper map foldable_bent.k foldable_flat_fine.k foldable_mapped.k

# TET4 매핑
KooRemapper map foldable_bent.k foldable_flat_tet.k foldable_mapped_tet.k
```

## 검증된 테스트 결과

### 테스트 예제 (2026-01-11)

| 예제 | Min Jacobian | Max Jacobian | Bounding Box | 상태 |
|------|-------------|--------------|--------------|------|
| arc30 | 5.45 | 7.63 | ✓ 일치 | ✅ |
| foldable (waterdrop) | 0.018 | 0.678 | ✓ 일치 | ✅ |
| torus | 19.16 | 30.28 | ✓ 일치 | ✅ |
| twist | 19.91 | 19.91 | ✓ 일치 | ✅ |
| wave | 7.67 | 40.65 | ✓ 일치 | ✅ |
| teardrop | 1.42 | 131.82 | ✓ 일치 | ✅ |

### 검증 항목
- **모든 Jacobian 양수**: 뒤집힌 요소 없음
- **Corner 노드 정확 일치**: 원본 bent mesh와 remapped mesh의 corner 노드 좌표 일치
- **Bounding Box 일치**: min/max 좌표가 원본과 정확히 일치
- **Unit Tests**: 52개 테스트 모두 통과
