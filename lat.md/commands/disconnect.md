# disconnect — node duplication — full / czm / mefem (§19)

Source: [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp)
Manual: [`KooRemapper_Manual.md`#19-disconnect--노드-분리](../../docs/KooRemapper_Manual.md#19-disconnect--노드-분리)


## Synopsis

```
KooRemapper disconnect <args>
```

## What it does

Duplicates shared nodes between selected parts. Modes:
- `full` — inserts `*SECTION_SOLID_PERI` (ELFORM=48, DR=1.01).
- `czm` — cohesive-zone elements at interface.
- `mefem` — mesh-free enrichment.

Builds `activeElems` from baseMesh_ (not-removed) + addedElements_ for post-restack use.

## Key references

- [[lsdyna/section#LS-DYNA SECTION cards in KooRemapper]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §19. disconnect — 노드 분리._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
지정 파트의 경계면 노드를 **분리**하여 비연속 인터페이스를 생성합니다.

### 사용법

```bash
KooRemapper.exe disconnect <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: disconnected
target_pid: 1
mode: full               # full | czm | mefem
cohesive_part_id: 0      # CZM 모드 파트 ID (0=자동)
failure_strain: 0.05     # CZM 파괴 변형률
```

### 모드별 동작


**표 21-1. warpage 보정 파라미터 — 워피지 측정 기준면, 보정 방향, 스케일 팩터 설정.**

| 모드 | 동작 | LS-DYNA 출력 |
|------|------|-------------|
| `full` | 경계 노드 단순 분리 + PERI 요소 | `*SECTION_SOLID_PERI` (ELFORM=48, DR=1.01) |
| `czm` | 분리 면에 응집 요소 삽입 | `*ELEMENT_SOLID` (cohesive) + `*MAT_COHESIVE_*` |
| `mefem` | 미세균열 확장 파라미터 설정 | `*MAT_ADD_EROSION` (EPPF 값) |

---

<!-- END MANUAL EXCERPT -->
