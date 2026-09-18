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
| `pid_refs` | 빈 파트를 가리키는 자리를 못 옮겼을 때의 종료 코드 — **`strict` / `warn` 만**. `strict` 는 rc=1(덱은 씁니다), `warn` 은 같은 보고 + rc=0 ([아래](#pid_refs--못-옮긴-자리가-남았을-때의-종료-코드)) | `strict` |

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

### 층으로 나누면 원 파트가 빈 파트가 된다 — 그 참조를 이제 도구가 다룬다 (2026-09-18)

restack 은 대상 파트를 층으로 나누면서 **층마다 새 PID·SECID·MID** 를 발급합니다.
원 `*PART` 카드는 지워지지 않고 **요소 0 개인 빈 파트**로 남습니다.
그래서 원 PID 를 가리키던 tied 조건·세트·이력·감쇠는 전부 **빈 파트를 가리키게** 됩니다 —
덱은 그대로 풀리지만 그 조건들이 아무 일도 하지 않습니다.

**이제 도구가 옮길 수 있는 것은 옮기고, 못 옮긴 것이 남으면 rc=1 로 멈춥니다(덱은 씁니다).**
훑는 축은 셋입니다.

**표 12-2. restack·merge 가 훑는 세 축 — 무엇이 빈 자리를 가리키게 되는가.**

| 축 | 무엇을 찾는가 |
|---|---|
| `PID` | restack·merge 가 비운 원 파트 번호를 가리키는 자리 |
| `EID` | 없어진 원 요소 번호를 가리키는 자리 |
| `NODE` | restack 이 지운 원 중간면 노드를 가리키는 자리 |

`NODE` 축은 **두께 방향 요소가 2개 이상이던 파트**를 restack 할 때 생깁니다 — 원 중간면 노드가 사라지므로
거기 매달린 `*BOUNDARY_SPC_NODE`·`*SET_SEGMENT`·`*SET_NODE` 가 갈 곳을 잃습니다.

```
  [WARN] restack: PID 1 가 빈 파트가 됐습니다 — 지워진 PID·요소·노드를 가리키던 자리 1 건 — 옮긴 것 0 건, 못 옮긴 것 1 건 (새 층 PID: 2,3)
    [NODE] line 55 *BOUNDARY_SPC_NODE (manual): restack 이 지운 중간면 노드입니다 — 새 층 노드로 다시 지정하세요
        |         10         0         1         1         1
```

### 무엇이 자동으로 옮겨지고 무엇이 보고만 되는가

**표 12-3. 죽은 PID 참조 이관 규칙 — restack 과 merge 의 차이. 모두 2026-09-18 실행으로 확인했습니다.**

| 가리키는 자리 | restack | merge |
|---|---|---|
| 체적 의미로 쓰이는 `*SET_PART_LIST`·`_TITLE` | 죽은 PID 를 **층 PID 전부**로 바꿉니다(한 줄 8개 규칙을 지켜 줄을 늘립니다) | 죽은 PID 를 **합친 PID 하나**로 바꿉니다 |
| `*SET_PART_COLUMN` | 죽은 PID 줄을 **층 수만큼 복제**합니다(딸린 칸은 그대로 복사) | 합친 PID 줄 하나로 바꿉니다 |
| tied 계열 접촉 — `*CONTACT_*TIED*`·`*TIEBREAK*`·`*SPOTWELD*`·`*CONTACT_CONSTRAINT_*` | 상대측(SURFB) 기하를 적층 축에 투영해 **층이 유일하게 정해질 때만** 그 층으로 옮깁니다. 애매하거나 shell 층이 섞이면 옮기지 않고 보고만 합니다(`left`) | 옮기지 않고 보고만 합니다(`left`) — 합쳐진 파트에서 원 파트의 면을 특정할 수 없습니다 |
| 한 세트를 tied 와 체적 소비자가 함께 쓰는 경우 | 세트를 **복제해 가릅니다**(새 SID 를 발급해 tied 쪽만 그 층을 담습니다) | 해당 없음(새 PID 가 하나뿐입니다) |
| 그 밖의 접촉 — AUTOMATIC·ERODING·SINGLE_SURFACE 등 | 모든 층이 solid 일 때 **층 전부를 담은 새 세트**로 바꾸고 STYP 를 3→2 로 고칩니다 | 합친 PID 로 바꿉니다 |
| 스칼라 PID 칸 — `*DAMPING_PART_MASS`·`_STIFFNESS`, `*DATABASE_HISTORY_PART`, `*MAT_ADD_THERMAL_EXPANSION`, `*PART_MOVE`, `*BOUNDARY_PRESCRIBED_MOTION_RIGID`, `*DEFORMABLE_TO_RIGID`, `*INITIAL_VELOCITY_GENERATION` 의 PID 칸 | **`manual`(직접 고치세요)** — 칸 하나에 층 N 개를 담을 수 없습니다 | **옮깁니다** — 새 PID 가 하나뿐이라 칸에 그대로 들어갑니다 |
| `*ELEMENT_MASS` | `manual` — `집중질량을 층에 나눌 수 없습니다 — 직접 배분하세요` | **2번째 칸**에 있는 죽은 PID 만 옮깁니다. 그 밖의 칸(EID·노드 축 포함)에 있으면 `manual` 로 남습니다 |
| `*CONSTRAINED_RIGID_BODIES` 의 두 칸이 모두 죽은 경우 | `manual` | 옮기지 않고 보고만 합니다(`left`) — 합치면 자기 자신을 가리키게 됩니다 |
| `EID` 축 — `*SET_SOLID`·`_SHELL`·`_BEAM`·`_TSHELL`, `*INITIAL_STRESS_*`, `*INITIAL_STRAIN_SOLID`, `*DATABASE_HISTORY_SOLID` 등 | `manual` | `manual` |
| `NODE` 축 — `*SET_NODE`, `*SET_SEGMENT`, `*BOUNDARY_SPC_NODE`, 그 세트를 쓰는 `*CONSTRAINED_NODAL_RIGID_BODY` | `manual` | `manual` |
| 칸 뜻이 카드마다 다른 키워드 — `*DEFINE_FRICTION`, `*ALE_*`, `*CONSTRAINED_LAGRANGE_IN_SOLID`, `*RIGIDWALL_*`, `*AIRBAG_*`, `*SET_PART_*_GENERATE` | `unknown` | `unknown` |
| 화이트리스트 밖의 그 밖 키워드 | `maybe` — **rc 에는 넣지 않습니다** | `maybe` |
| 덱에 `*INCLUDE` 가 있는 경우 | 소비자를 다 볼 수 없어 세트를 펴지 않고 **보고만** 합니다(`left`) | 같습니다 |

> **`*INCLUDE` 가 있으면 '0 건' 을 믿지 마세요** — 인클루드 파일 안은 읽지 않습니다.
> 그 안에 빈 PID·지운 요소·지운 노드를 가리키는 자리가 있어도 찾지 못하며,
> 그 사실 자체를 `[ALL] *INCLUDE (left)` 한 줄로 알립니다.

### `$ KOOREMAPPER-PIDREF` 블록 읽는 법

못 옮긴 자리가 남든 아니든, 발견이 하나라도 있으면 출력 덱의 **머리(`*KEYWORD` 바로 뒤)** 에
`$ KOOREMAPPER-PIDREF` 주석 블록이 들어갑니다. 콘솔은 상위 20 건만 보이고 접지만,
이 블록에는 **발견을 전부** 적습니다. 발견이 0 건이면 블록도 없습니다(예전 출력과 바이트 그대로 같습니다).

실제 출력입니다(아래 "빈 파트 참조 예제" 의 덱 머리).

```
*KEYWORD
$ KOOREMAPPER-PIDREF: 5 reference(s) — restack/merge 가 비운 PID·지운 요소·지운 노드를 가리키던 자리입니다 (옮김 3, 못 옮김 2)
$ KOOREMAPPER-PIDREF: 등급 moved=이 덱에서 옮겼습니다, left=옮기지 못했습니다(이유가 붙습니다), manual=직접 고치세요, unknown=칸 자리 미확정, maybe=화이트리스트 밖(칸 뜻 미확인 — rc 에는 넣지 않습니다)
$ KOOREMAPPER-PIDREF: 줄 번호는 이 op 가 읽은 입력 덱 기준입니다(이 블록과 이관으로 늘어난 줄만큼 아래로 밀려 있습니다)
$ KOOREMAPPER-PIDREF [PID] line 70 *SET_PART_LIST (moved): 세트 300: 죽은 PID 를 층 PID 2개 전부로 바꿨습니다(구성원 2개)
$ KOOREMAPPER-PIDREF   |          1
$ KOOREMAPPER-PIDREF [PID] line 75 *CONTACT_TIED_SURFACE_TO_SURFACE (moved): slave part 1 → 층 2(PID 4) 로 바꿨습니다(상대측 기하를 적층 축에 투영해 층이 하나로 정해졌습니다)
$ KOOREMAPPER-PIDREF   |          1         2         3         3
$ KOOREMAPPER-PIDREF [PID] line 78 *CONTACT_AUTOMATIC_SURFACE_TO_SURFACE (moved): slave part 1 → 층 PID 2개를 담은 새 세트 301 (STYP 3→2) 로 바꿨습니다
$ KOOREMAPPER-PIDREF   |          1         2         3         3
$ KOOREMAPPER-PIDREF [PID] line 80 *DAMPING_PART_MASS (manual): `_SET` 변형으로 바꾸고 전 층 세트를 주세요
$ KOOREMAPPER-PIDREF   |          1       0.0
$ KOOREMAPPER-PIDREF [PID] line 82 *DATABASE_HISTORY_PART (manual): 층 PID 를 목록에 더하거나 `_SET` 변형으로 바꾸세요
$ KOOREMAPPER-PIDREF   |          1
$ KOOREMAPPER-PIDREF-END
```

한 발견은 **두 줄**입니다 — 첫 줄이 `[축] line N 키워드 (등급): 무엇을 했는지 / 왜 못 했는지`,
둘째 줄(`|` 로 시작)이 그 줄의 원문입니다.

**표 12-4. `$ KOOREMAPPER-PIDREF` 등급 다섯 개.**

| 등급 | 뜻 | rc 에 넣는가 |
|---|---|---|
| `moved` | 이 덱에서 실제로 옮겼습니다. 더 할 일이 없습니다 | 아니오 |
| `left` | 옮길 수 있는 자리였지만 옮기지 못했습니다. 이유가 뒤에 붙습니다 | **예** |
| `manual` | 도구가 옮길 수 없는 자리입니다. 직접 고치세요 | **예** |
| `unknown` | 칸 뜻이 카드마다 달라 자리를 확정하지 않았습니다. 그 줄을 직접 확인하세요 | **예** |
| `maybe` | 화이트리스트 밖이라 칸 뜻을 확인하지 않았습니다. 값이 우연히 같기만 해도 걸립니다 | **아니오** |

> **줄 번호는 입력 덱 기준입니다.** 출력 덱에서 같은 번호를 찾으면 엉뚱한 줄이 나옵니다 —
> 이 블록과 이관으로 늘어난 줄만큼 아래로 밀려 있습니다.
> 위 예의 `line 70` 은 **입력** `model.k` 의 70 행(`*SET_PART_LIST` 의 구성원 줄)입니다.

> `maybe` 를 rc 에서 뺀 이유는 오탐입니다 — 화이트리스트 밖 줄의 아무 정수 칸이나 죽은 PID 와 견주므로,
> 흔한 `target_pid: 1` 이면 `*BOUNDARY_SPC_SET` 의 DOF 플래그 같은 값이 그대로 걸립니다.
> 보고는 남기되 rc 는 올리지 않습니다.

### `pid_refs` — 못 옮긴 자리가 남았을 때의 종료 코드

**표 12-5. `pid_refs` 키 — 값·기본값·쓰는 자리.**

| 항목 | 내용 |
|---|---|
| 값 | `strict`(기본) 또는 `warn` **둘뿐** |
| 기본값 | `strict` — 못 옮긴 자리(`left`·`manual`·`unknown`)가 남으면 **rc=1**. 덱은 씁니다 |
| `warn` | **같은 보고**를 하고 **rc=0** 으로 끝냅니다. 기존 파이프라인의 탈출구입니다 |
| 쓰는 자리 | `assemble` 의 `operations[]` 항목(`- type: restack`·`- type: merge`)과, 단독 `restack`·`merge` YAML 의 **op 수준**(최상위 키) |
| 그 밖의 값 | **rc=1 + 출력 파일 없음** — `invalid pid_refs 'loose' (must be one of strict, warn)` |

```yaml
model: model.k
output: stacked.k
target_pid: 1
direction: z
pid_refs: warn            # strict(기본) | warn — op 수준(최상위) 키다
layers:
  - title: L1
    thickness: 1.0
    material_card: |
      *MAT_ELASTIC
      $#     mid        ro         e        pr
        MID001  7.85E-09    210000       0.3
  - title: L2
    thickness: 1.0
    material_card: |
      *MAT_ELASTIC
      $#     mid        ro         e        pr
        MID002  7.85E-09    210000       0.3
```

> **rc=1 을 기본으로 둔 이유** — pyKooCAE 체인과 플랫폼 워커는 **종료 코드로만** 성공을 판정합니다.
> rc=0 이면 콘솔 경고가 자동화에 아예 보이지 않은 채 그 덱이 그대로 솔버까지 갑니다.

rc=1 일 때의 마지막 출력입니다(위 예제 덱에서 `pid_refs` 를 빼거나 `strict` 로 둔 경우 — 위 YAML 그대로는 `warn` 이라 rc=0 입니다).

```
[ERROR] restack/merge 가 비운 PID·지운 요소·지운 노드를 아직 가리키는 자리가 2 건 남았습니다 — 덱은 stacked.k 에 썼지만 그대로 풀면 그 조건들이 아무 일도 하지 않습니다.
  [PID] line 80 *DAMPING_PART_MASS (manual): `_SET` 변형으로 바꾸고 전 층 세트를 주세요
  [PID] line 82 *DATABASE_HISTORY_PART (manual): 층 PID 를 목록에 더하거나 `_SET` 변형으로 바꾸세요
  전체 목록은 덱 머리의 $ KOOREMAPPER-PIDREF 블록에 있습니다. 알고도 넘기려면 pid_refs: warn 을 주세요(같은 보고, rc=0).
```

> `pid_refs: warn` 을 줘도 `[WARN] …` 요약 안의 **"못 옮긴 자리가 남아 rc=1 로 끝냅니다"** 줄은 그대로 나옵니다 —
> 같은 보고를 그대로 내기 때문입니다. 실제 종료 코드는 0 이고, `[ERROR]` 마무리 줄은 나오지 않습니다.

### 빈 파트 참조 예제 (2026-09-18 실행 확인)

`lx=20, ly=10, lz=2`, `2×2×2` 박스(PID 1)에 이웃 파트 PID 2(z=2..3)를 붙이고 아래 카드를 넣은 덱 `model.k` 를
2 층으로 restack 한 결과입니다.

```
*SET_PART_LIST
       300
         1
*LOAD_BODY_PARTS
       300
*CONTACT_TIED_SURFACE_TO_SURFACE
$#   ssid      msid     sstyp     mstyp
         1         2         3         3
*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE
$#   ssid      msid     sstyp     mstyp
         1         2         3         3
*DAMPING_PART_MASS
         1       0.0
*DATABASE_HISTORY_PART
         1
```

```
  [WARN] restack: PID 1 가 빈 파트가 됐습니다 — 지워진 PID·요소·노드를 가리키던 자리 5 건 — 옮긴 것 3 건, 못 옮긴 것 2 건 (새 층 PID: 3,4)
    [PID] line 70 *SET_PART_LIST (moved): 세트 300: 죽은 PID 를 층 PID 2개 전부로 바꿨습니다(구성원 2개)
        |          1
    [PID] line 75 *CONTACT_TIED_SURFACE_TO_SURFACE (moved): slave part 1 → 층 2(PID 4) 로 바꿨습니다(상대측 기하를 적층 축에 투영해 층이 하나로 정해졌습니다)
        |          1         2         3         3
    [PID] line 78 *CONTACT_AUTOMATIC_SURFACE_TO_SURFACE (moved): slave part 1 → 층 PID 2개를 담은 새 세트 301 (STYP 3→2) 로 바꿨습니다
        |          1         2         3         3
    [PID] line 80 *DAMPING_PART_MASS (manual): `_SET` 변형으로 바꾸고 전 층 세트를 주세요
        |          1       0.0
    [PID] line 82 *DATABASE_HISTORY_PART (manual): 층 PID 를 목록에 더하거나 `_SET` 변형으로 바꾸세요
        |          1
    못 옮긴 자리가 남아 rc=1 로 끝냅니다(덱은 씁니다). pid_refs: warn 을 주면 같은 보고를 하고 rc=0 으로 끝냅니다.
```

- tied 접촉은 상대(PID 2, z=2..3)가 적층 위쪽에만 닿아 **층 2 로 유일하게 정해졌습니다.**
  상대가 여러 층에 걸치면 옮기지 않고 이유를 적습니다 —
  `상대측이 층 1,2 에 걸쳐 층이 하나로 정해지지 않습니다 — 전 층으로 펴면 내부 계면까지 묶입니다`.
- AUTOMATIC 접촉은 tied 가 아니므로 층 전부를 담은 **새 세트 301** 을 만들고 STYP 를 3→2 로 고칩니다.
- 감쇠·이력은 칸이 하나라 층 2 개를 담을 수 없어 `manual` 로 남고, 그래서 **rc=1** 입니다.

### 재질 카드 — MID 칸과 제목 줄

- **MID 칸에 숫자를 직접 적으면 그 번호를 그대로 씁니다.** 이미 쓰이는 번호면 새 번호를 발급하고 알립니다.

  ```
    Restack layer 2: material MID 90 is already in use -> assigned MID 91
  ```

  위는 두 층이 모두 MID 칸에 `90` 을 적은 경우입니다 — 층 1 은 MID **90** 을 그대로 받고, 층 2 는 **91** 을 받습니다.
  숫자가 아닌 라벨(`MID001` 등)은 예전처럼 층마다 새 MID 로 바뀝니다.

- **`*MAT_..._TITLE` 카드에 제목 줄이 없으면** 데이터 줄을 제대로 읽고 `[WARN]` 을 낸 뒤
  **빠진 제목 줄을 층 제목으로 채워** 내보냅니다(`title` 키가 없으면 `Restack Layer N`).

  ```
    [WARN] Restack layer 1: *MAT_..._TITLE card had no title line -> filled it with 'SKIN' (the line after *MAT_..._TITLE is read as the title, so the data line was being eaten)
  ```

  `*MAT_..._TITLE` 다음 첫 줄은 제목으로 읽히므로, 제목 줄이 없으면 데이터 줄이 제목으로 먹혀 그 재질이 등록되지 않습니다.
  예전에는 경고 없이 그렇게 나갔습니다.

- **구조가 깨진 카드는 rc=1 입니다** — `*MAT` 키워드 줄이 없거나, 키워드 줄 뒤에 데이터 줄이 아예 없는 경우입니다.

  ```
  [ERROR] [restack] Operation 1: layer 1 material_card *MAT 키워드 줄이 없습니다 / no '*MAT...' keyword line
  [ERROR] [restack] Operation 1: layer 1 material_card 키워드 줄 뒤에 데이터 줄이 없습니다 — MID 를 쓸 자리가 없어 mid 0 덱이 됩니다 / no data line after the keyword line
  ```

- 층 카드도 `offset`·CZM 과 같은 **MaterialCardValidator** 를 거칩니다.
  **물성 지적은 `[WARN]` 으로만** 내리고 덱은 그대로 씁니다(rc=0) — 임의의 물성 카드를 넣는 restack 을 막지 않기 위해서입니다.

  ```
    [WARN] Restack layer 1 material_card: *MAT_ELASTIC: Expected at least 4 fields (MID, RO, E, PR), found 3
  ```

### 강체 파트는 restack 을 거절한다

대상 파트가 **강체**면 층을 나누기 전에 rc=1 로 멈춥니다. 예전에는 경고 한 줄 없이
강체 구속도 박아 둔 질량도 사라진 변형체 여러 층이 나갔습니다.

```
[ERROR] restack: PID 1 는 *MAT_RIGID(MID 1) 강체 파트입니다 — 층을 나누면 강체 구속이 사라지고 변형체 여러 층이 됩니다. 강체를 유지하려면 restack 대신 두께를 직접 바꾸세요 / cannot restack a rigid part
[ERROR] restack: PID 1 에는 *PART_INERTIA 가 걸려 있습니다 — 그 카드의 질량·관성은 새 층으로 나눌 수 없습니다. 층을 나누려면 *PART_INERTIA 를 먼저 푸세요 / cannot restack a *PART_INERTIA part
```

거절 조건은 둘입니다 — 파트의 MID 가 `*MAT_RIGID`(= `*MAT_020`)이거나, 그 파트에 `*PART_INERTIA` 가 걸린 경우입니다.

### 새 층이 물려받는 것 — ELFORM·HGID·TMID

**표 12-6. 새 층이 원 파트에서 물려받는 값.**

| 값 | 어디서 | 물려받는가 |
|---|---|---|
| `ELFORM` | 원 `*SECTION_SOLID`/`*SECTION_SHELL` 의 칸 1 | **같은 요소 종류일 때만** 물려받습니다 |
| `HGID` | 원 `*PART` 카드의 5번째 칸 | 물려받습니다(0 이 아닐 때) |
| `TMID` | 원 `*PART` 카드의 8번째 칸 | 물려받습니다(0 이 아닐 때) |
| `EOSID` | 원 `*PART` 카드의 4번째 칸 | **물려받지 않습니다** — 상태방정식은 원 재질에 매인 것이고 새 층은 새 MID 를 받습니다 |

`solid` ↔ `tshell` 은 같은 ELFORM 번호라도 뜻이 다른 정식이므로 넘기지 않습니다 —
`*SECTION_SOLID` ELFORM 2 인 파트를 `element_type: tshell` 로 restack 하면 새 `*SECTION_TSHELL` 은 ELFORM **1** 로 태어납니다.

물려받을 `HGID`·`TMID` 가 없으면 예전과 같은 **세 칸짜리** `*PART` 카드를 씁니다(출력이 바뀌지 않습니다).
있으면 여덟 칸 카드로 바뀝니다.

```
*PART
L1
$#     pid     secid       mid     eosid      hgid      grav    adpopt      tmid
         2         2        90         0         7         0         0         9
```

---

<!-- END MANUAL EXCERPT -->
