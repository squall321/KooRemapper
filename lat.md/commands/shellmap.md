# shellmap — QUAD4 shell-based mapping (§5)

Source: [ShellMapper.cpp](../../src/mapper/ShellMapper.cpp)
Manual: [`KooRemapper_Manual.md`#5-shellmap--quad4-셸-기반-매핑](../../docs/KooRemapper_Manual.md#5-shellmap--quad4-셸-기반-매핑)


## Synopsis

```
KooRemapper shellmap reference_shell.k template.k output.k
```

## What it does

Maps solid-detail meshes using a QUAD4 shell representation as the parametric domain. Useful when only a shell mid-surface is available.

## Key references

- [[modules/mapper#Module: src/mapper/]]
- [[lsdyna/section#LS-DYNA SECTION cards in KooRemapper]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §5. shellmap — QUAD4 셸 기반 매핑._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
QUAD4 셸 참조 형상을 기반으로 **평면 상세 고체 메시(solid detail mesh)**를
굽힘 형상으로 매핑. 두께 방향 위치는 자동 또는 명시적으로 지정.

### 사용법

```bash
KooRemapper.exe shellmap [--thickness <t>] <bent_shell.k> <flat_detail.k> <output.k>

Options:
  --thickness <t>   두께 명시적 지정 (기본: Z-범위 자동 감지)
```

### 동작 원리

1. 셸 참조 메시로부터 **법선 벡터 n̂** 계산
2. 평면 노드의 면내 위치 (u, v)를 셸 면에 투영
3. 두께 방향 위치 z를 셸 면에서 **±t/2** 범위로 맵핑

$$\mathbf{x}' = \mathbf{x}_{shell}(u,v) + \frac{z}{t/2} \cdot \frac{t}{2} \hat{\mathbf{n}}(u,v)$$

### 출력
- `output.k`: 매핑된 상세 고체 메시

### 주의사항
- 가전개(developable) 면에 최적화; 비가전개 면에서 왜곡 경고 출력
- QUAD4 전용 (TRIA3 미지원)

---

<!-- END MANUAL EXCERPT -->
