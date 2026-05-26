# refine — 1:2 / 1:3 subdivision (§17)

Source: [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp)
Manual: [`KooRemapper_Manual.md`#17-refine--메시-세분화](../../docs/KooRemapper_Manual.md#17-refine--메시-세분화)


## Synopsis

```
KooRemapper refine <args>
```

## What it does

Supports QUAD4/TRIA3/HEX8 (1:2, 1:3) and TET4 (1:2). Edge midpoints via `edgeMidNodeMap_`, edge thirds via `edgeThirdNodeMap_`, face centers via `faceCenterNodeMap_`. HEX8 1:3 face interior dedup uses canonical bilinear ordering (min ID + direction toward smaller neighbor) with affine (s,t) transform.

## Key references

- [[lsdyna/element#LS-DYNA ELEMENT cards in KooRemapper]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §17. refine — 메시 세분화._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
요소를 엣지 방향으로 **1:2 또는 1:3** 비율로 균일 세분화합니다.

### 사용법

```bash
KooRemapper.exe refine <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: refined
target_pid: 0            # 0 = 전체
ratio: 2                 # 2 또는 3
```

### 지원 요소 유형


**표 18-1. ELFORM 코드 목록 — LS-DYNA 요소 공식(ELFORM) 번호와 각 공식의 특성 요약.**

| 요소 | ratio=2 | ratio=3 |
|------|---------|---------|
| QUAD4 | 4개 서브 쿼드 | 9개 서브 쿼드 |
| TRIA3 | 4개 서브 삼각형 | 9개 서브 삼각형 |
| HEX8 | 8개 서브 헥스 | 27개 서브 헥스 |
| TET4 | 8개 서브 테트 | — |

---

<!-- END MANUAL EXCERPT -->
