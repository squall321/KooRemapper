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


**표 12-1. restack YAML 파라미터 — 대상 파트, 적층 방향, 요소 유형, 레이어 목록.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `model` | 입력 K-파일 | — |
| `output` | 출력 접두어 | — |
| `target_pid` | 대상 파트 ID | — |
| `direction` | 적층 방향 — `auto`·`x`·`y`·`z`·`+x`·`-x`·`+y`·`-y`·`+z`·`-z` | `auto` |
| `element_type` | 요소 유형 — **`solid` / `tshell` / `shell` 만** (소문자) | `solid` |
| `layers` | 레이어 리스트 (thickness + material_card) | — |

> **`element_type` 허용값(2026-09-18 변경)**: `solid`·`tshell`·`shell` **세 값만** 받습니다. 대소문자도 구분해
> `SOLID` 조차 거절합니다 — `[ERROR] restack: unsupported element_type 'hex' (allowed: solid, tshell, shell)` 와 함께
> **종료 코드 1, 출력 파일 없음** 입니다. 층(`layers[]`)별 `element_type` 도 같습니다(빈 값이면 op 수준 값을 상속).
> 예전에는 `shell`·`tshell` 이 아닌 값이 전부 조용히 `solid` 로 처리됐으므로, `hex` 같은 값을 적어 둔 **기존 YAML 은 지금 깨집니다.**
> 이 검증은 단독 `restack` 과 `assemble` 의 `- type: restack` 양쪽에 똑같이 걸립니다.

> **재질 카드 MID 칸**: 각 층 `material_card` 의 첫 `*MAT` 카드 MID 칸(1~10열, `*MAT_…_TITLE` 이면 제목 다음 줄)에 쓴 값은 라벨입니다. `MID001`·`MAT01`·`@MID@`·`14` 무엇이든 층마다 새로 발급한 MID 로 바뀌고, 같은 MID 를 가리키는 `*MAT_ADD_…` 카드도 함께 바뀝니다.
> - 라벨과 카드 내용(MID 칸 제외)이 같은 층끼리만 MID 하나를 공유합니다. 라벨이 같아도 물성이 다르면 따로 발급하고 `material label 'X' reused with a different card -> separate MID N` 을 안내합니다(위 예시의 두 층은 라벨은 같고 물성이 달라 MID 가 둘).
> - 값은 LS-DYNA 고정 폭 10열 칸 안에 두세요(블록 들여쓰기를 뺀 뒤 기준). 쉼표 자유 형식도 됩니다.
> - YAML `|` 블록은 키보다 깊게 들여쓴 줄까지이며 끝 빈 줄은 버립니다. 제목에 `:` 나 `-` 가 있어도 됩니다.

### 동작
1. `target_pid` 파트의 요소 분석 → 두께 방향 결정
2. 표면 메시(QUAD4) 추출
3. 각 레이어를 누적 두께로 압출(extrude)
4. 재료 카드 등록 + 새 파트/섹션/재료 ID 발급

### 위 예제의 실제 실행 결과 (2026-09-18 확인)

`lx=20, ly=10, lz=2` 박스(PID 1, MID 1)에 위 YAML 을 그대로 돌린 출력입니다.

```
  Restack layer 2: material label 'MID001' reused with a different card -> separate MID 3
  Thickness mismatch: layers=0.800000 original=2.000000 eps=1.500000 → *INITIAL_STRAIN_SOLID on 100 solid elements
  Restack Part 1 (Z-axis): 2 layers -> 2 layers (2 elements), 50 elements/layer, 66 columns
[restack] Done -> restacked.k
```

- 출력 덱의 `*MAT_ELASTIC` 은 **3장**입니다 — 원본 MID 1 + 새 층 2장.
- `Restack Layer 1` 파트는 **MID 2**(7.85E-09 / 210000 / 0.3), `Restack Layer 2` 파트는 **MID 3**(2.50E-09 / 70000 / 0.33).
  **두 층이 서로 다른 재질을 제대로 받습니다** — 두 층이 같은 라벨 `MID001` 을 써도 카드 내용이 다르므로 MID 를 따로 발급합니다
  (예전에는 둘째 층 재질이 사라졌습니다).
- `layers` 두께 합(0.3 + 0.5 = 0.8)이 원본 두께(2.0)와 다르면 그 차이를 초기 변형률로 넣어
  `*INITIAL_STRAIN_SOLID` 를 함께 씁니다. **두께를 그대로 유지하고 싶으면 `layers` 두께 합을 원본 두께에 맞추세요.**

---

<!-- END MANUAL EXCERPT -->
