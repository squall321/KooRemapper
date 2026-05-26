# map — HEX8 structured mesh mapping (§4)

Source: [MeshRemapper.cpp](../../src/mapper/MeshRemapper.cpp), [ParametricMapper.cpp](../../src/mapper/ParametricMapper.cpp)
Manual: [`KooRemapper_Manual.md`#4-map--hex8-구조화-메시-매핑](../../docs/KooRemapper_Manual.md#4-map--hex8-구조화-메시-매핑)
Theory: [[theory/isoparametric-map#Isoparametric mapping]], [[theory/arc-length-param#Arc-length parameterization]]

## Synopsis

```
KooRemapper map reference.k template.k output.k
```

## What it does

Maps a reference structured HEX8 mesh onto a deformed template mesh via isoparametric (i,j,k) coordinates. The arc/width/thickness axis triple is determined by [StructuredGridIndexer.cpp](../../src/grid/StructuredGridIndexer.cpp).

## Key references

- [[modules/mapper#Module: src/mapper/]] — interpolator family
- [[theory/isoparametric-map#Isoparametric mapping]]
- [[theory/structured-grid#Structured grid BFS indexing]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §4. map — HEX8 구조화 메시 매핑._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
평면(flat) 상세 메시(HEX8)를 굽힘(bent) 참조 구조화 메시에 등매개변수 방법으로 매핑.
참조 메시는 **구조화된 HEX8**이어야 하며, 상세 메시는 임의 형상이어도 무방합니다.

### 사용법

```bash
KooRemapper.exe map [--single] <bent_mesh.k> <flat_mesh.k> <output.k>

Options:
  --single, -s    단일 스레드 모드 (기본: 병렬)
```

### 동작 원리

각 상세 메시 노드 **p**에 대해:

1. 참조 메시에서 포함하는 요소 검색
2. 자연 좌표 **(ξ, η, ζ)** 역계산 (Newton-Raphson)
3. 굽힘 참조 형상의 같은 자연 좌표로 위치 변환

$$\mathbf{x}(\xi, \eta, \zeta) = \sum_{i=1}^{8} N_i(\xi, \eta, \zeta) \, \mathbf{x}_i$$

여기서 HEX8 형상 함수:

$$N_i = \frac{1}{8}(1 + \xi_i\xi)(1 + \eta_i\eta)(1 + \zeta_i\zeta)$$

### 출력
- `output.k`: 매핑된 위치의 상세 메시

### 주의사항
- 참조 메시는 반드시 **규칙적 HEX8 구조** 필요
- 상세 메시 노드가 참조 요소 외부에 있으면 경고 출력
- `info` 명령으로 Jacobian 통계 확인 가능

---

<!-- END MANUAL EXCERPT -->
