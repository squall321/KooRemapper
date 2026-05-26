# Structured grid BFS indexing

Stub mirroring `docs/KooRemapper_Theory_Document.md` §2.6.

Source code: (see See-also)

## Summary

Assigns (i,j,k) to unstructured HEX8 cells via BFS over face adjacency. Seed face on boundary; arc/width/thickness fall out of neighbor counts. Implemented in [StructuredGridIndexer.cpp](../../src/grid/StructuredGridIndexer.cpp).

## See also

- [[modules/grid#Module: src/grid/]]

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §2.6 — 구조화 그리드 인덱싱 - **실제 사용**._

<!-- BEGIN EXCERPT -->



> **구현 위치**: `StructuredIndexer`, `MeshConnectivity`

### 2.6.1 목적

비정렬(unstructured) 메시 요소에 (i, j, k) 구조화 인덱스를 할당합니다.

### 2.6.2 BFS 기반 알고리즘

**Step 1: 코너 요소 탐색**

코너 요소 조건: 정확히 3개의 면 이웃을 가진 요소

```
for each element e:
    if neighbor_count(e) == 3:
        corner_elements.add(e)
```

**Step 2: 기하 기반 축 방향 결정**

요소 중심(centroid)의 상대 위치에서 축 방향 계산:

```
direction_i = average(neighbor_centroids) - element_centroid
direction_j = perpendicular_in_plane(direction_i)
direction_k = cross(direction_i, direction_j)
```

**Step 3: BFS 전파**

```python
def BFS_indexing(start_element):
    queue = [(start_element, 0, 0, 0)]
    visited = {}

    while queue:
        (elem, i, j, k) = queue.pop(0)
        if elem in visited:
            continue
        visited[elem] = (i, j, k)

        for (neighbor, direction) in get_face_neighbors(elem):
            if direction == +i: queue.add((neighbor, i+1, j, k))
            if direction == -i: queue.add((neighbor, i-1, j, k))
            if direction == +j: queue.add((neighbor, i, j+1, k))
            if direction == -j: queue.add((neighbor, i, j-1, k))
            if direction == +k: queue.add((neighbor, i, j, k+1))
            if direction == -k: queue.add((neighbor, i, j, k-1))
```

**Step 4: 축 순서 정렬**

조건: $dim_k \leq dim_j \leq dim_i$

필요시 축을 교환하여 조건 만족

**Step 5: 노드 순서 정규화**

LS-DYNA HEX8 표준 노드 순서:
- 하단면 (k=0): 반시계 방향 n₀, n₁, n₂, n₃
- 상단면 (k=1): 반시계 방향 n₄, n₅, n₆, n₇
- k-축: 하단 → 상단 방향

---

# 3. 변형 해석 알고리즘

> **KooRemapper 실제 구현 요약**
>
> 변형 해석은 다음 단계로 수행됩니다:
> 1. **변형 구배 계산**: `DeformationGradient::computeHex8()` - 야코비안 기반 계산
> 2. **변형률 계산**: `StrainTensor::fromDeformationGradient()` - 공학/Green-Lagrange 선택 가능
> 3. **응력 계산**: `StressTensor::fromStrain()` - Hooke 법칙 적용
> 4. **가우스 적분**: 1점 또는 8점 적분 선택 가능 (`setGaussPoints()`)

---

<!-- END EXCERPT -->
