# restack — layer restacking (§12)

Source: [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp)
Manual: [`KooRemapper_Manual.md`#12-restack--레이어-재적층](../../docs/KooRemapper_Manual.md#12-restack--레이어-재적층)


## Synopsis

```
KooRemapper restack <args>
```

## What it does

Re-orders or re-spaces plate/tier layers (e.g., battery cells). Operates on z-ordered HEX8 stacks.

## Key references

- [[modules/assembly#Module: src/assembly/]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §12. restack — 레이어 재적층._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
기존 파트를 두께 방향으로 제거하고, **각기 다른 두께와 재료**를 가진 레이어 스택으로 재생성합니다.

### 사용법

```bash
KooRemapper.exe restack <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: restacked
target_pid: 1
direction: z              # auto | x | y | z (적층 방향)
element_type: solid       # solid | tshell | shell
material:
  E: 210000
  nu: 0.3
layers:
  - thickness: 0.3
    material_card: |
      *MAT_ELASTIC
      $#     mid        ro         e        pr
        MID001  7.85E-09    210000       0.3
  - thickness: 0.5
    material_card: |
      *MAT_ELASTIC
      $#     mid        ro         e        pr
        MID001  2.50E-09     70000       0.33
```

### 파라미터


**표 14-1. indent YAML 설정 파라미터 — 압입 깊이, 위치, 반경, 방향 등 압입/엠보싱 제어 파라미터.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `model` | 입력 K-파일 | — |
| `output` | 출력 접두어 | — |
| `target_pid` | 대상 파트 ID | — |
| `direction` | 적층 방향 (auto/x/y/z) | `auto` |
| `element_type` | 요소 유형 | `solid` |
| `layers` | 레이어 리스트 (thickness + material_card) | — |

> **참고**: `MID001`, `MID002` 등의 플레이스홀더가 자동으로 실제 MID로 치환됩니다.

### 동작
1. `target_pid` 파트의 요소 분석 → 두께 방향 결정
2. 표면 메시(QUAD4) 추출
3. 각 레이어를 누적 두께로 압출(extrude)
4. 재료 카드 등록 + 새 파트/섹션/재료 ID 발급

---

<!-- END MANUAL EXCERPT -->
