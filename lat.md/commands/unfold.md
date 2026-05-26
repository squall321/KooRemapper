# unfold — bent mesh → flat (§9)

Source: [ShellUnfolder.cpp](../../src/mapper/ShellUnfolder.cpp)
Manual: [`KooRemapper_Manual.md`#9-unfold--굽힘-메시-전개](../../docs/KooRemapper_Manual.md#9-unfold--굽힘-메시-전개)


## Synopsis

```
KooRemapper unfold <args>
```

## What it does

Unfolds a bent mesh onto its flat counterpart by accumulating arc length along the arc axis. Critical for the closed-loop case — see [[project_unfold_axis_perm]].

## Key references

- [[modules/mapper#Module: src/mapper/]]
- [[theory/arc-length-param#Arc-length parameterization]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §9. unfold — 굽힘 메시 전개._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
굽힘(bent) 구조화 HEX8 메시로부터 **평면(flat) 전개 메시**를 생성합니다.
`map` 명령의 역방향 연산으로, 굽힘 구조화 메시의 호 길이(arc-length) 매개변수화를 사용하여
평면 형상을 복원합니다.

### 사용법

```bash
KooRemapper.exe unfold <bent_mesh.k> <output_flat.k>
```

### 파라미터


**표 7-1. squeeze YAML 파트 설정 예 — 직접 변형률(eps_x/y/z)과 등방 팽창(swelling) 두 가지 방법의 비교.**

| 파라미터 | 설명 |
|----------|------|
| `bent_mesh.k` | 굽힘 구조화 HEX8 메시 (입력) |
| `output_flat.k` | 전개된 평면 메시 (출력) |

### 동작 원리

1. 입력 메시의 구조화 격자 차원(I, J, K) 자동 감지
2. 각 축 방향으로 호 길이(arc-length) 계산
3. 호 길이를 기반으로 평면 좌표 재매핑

### 출력

- `output_flat.k`: 전개된 평면 메시
- 콘솔: 격자 차원(I, J, K) 및 평면 길이(I=호 길이, J, K) 출력

### 주의사항
- 입력 메시는 반드시 **규칙적 HEX8 구조화 메시**여야 합니다
- 비구조화 메시에는 사용할 수 없습니다

---

<!-- END MANUAL EXCERPT -->
