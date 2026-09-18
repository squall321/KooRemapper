# generate — YAML-driven mesh generation (§8)

Source: [generator](../../src/generator/) (CurvedMeshGenerator, VariableDensityMeshGenerator)
Manual: [`KooRemapper_Manual.md`#8-generate--generate-var--메시-생성](../../docs/KooRemapper_Manual.md#8-generate--generate-var--메시-생성)


## Synopsis

```
KooRemapper generate config.yaml
```

## What it does

Builds a fresh `.k` file from a YAML description (curves, density fields). `generate-var` is the variable-density variant.

## Key references

- [[modules/generator#Module: src/generator/]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §8. generate / generate-var — 메시 생성._

<!-- BEGIN MANUAL EXCERPT -->



### generate — 예제 메시 생성

호출형태는 두 가지입니다(help `Usage:`).

```bash
KooRemapper generate [options] <type> <output_prefix>
KooRemapper generate box <config.yaml>

Types: teardrop, arc, scurve, helix, torus, twist, bendtwist,
       wave, bulge, taper, waterdrop

Options:
  --dim-i <n>   I 방향 요소 수 (기본 10)
  --dim-j <n>   J 방향 요소 수 (기본 5)
  --dim-k <n>   K 방향 요소 수 (기본 5)
```

테스트 및 데모용 다양한 기하학적 형상 HEX8 메시 생성.
`box` 하위명령은 YAML 로 직육면체 메시를 만듭니다 — 키는 **`output`(필수)**, `lx/ly/lz`, `nx/ny/nz`, `rho/E/nu`, `mid/secid/pid`, `part_title` 입니다.

```yaml
output: box.k          # 필수 — 없으면 '[ERROR] [box] output not specified' 로 종료 코드 1
lx: 20.0
ly: 10.0
lz: 2.0
nx: 10
ny: 5
nz: 2
rho: 7.85e-9
E: 210000.0
nu: 0.3
mid: 1
secid: 1
pid: 1
part_title: PLATE
```

> **`output` 은 필수입니다.** 예전 판의 키 목록에는 `output` 이 빠져 있어, 그대로 복사하면
> `[ERROR] [box] output not specified` 로 **종료 코드 1** 이 납니다(실행해 확인).
> `output` 의 상대 경로는 [§3.1(a)](#31-yaml-공통-규칙-모든-op) 대로 **그 YAML 파일이 있는 폴더** 기준입니다.

### generate-var — 변밀도 메시 생성

호출형태는 positional 입니다(`--ref`, `--no-scale` 는 옵션).

```bash
KooRemapper generate-var [options] <config.yaml> <output.k>

Options:
  --ref <file>   스케일링용 참조 평면 메시
  --no-scale     참조로 스케일하지 않고 YAML 길이를 그대로 사용
```

#### YAML 설정 (평면 타입, `type: flat`)

스키마는 `variable_density` + `elements_j/k` 구조입니다(존별 `length`/`num_elements`).
**존 이름은 아래 5개로 고정**되어 있고, `reference` 로 J·K 방향 치수를 주지 않으면 그 두 방향이 1.0 으로 떨어집니다.

```yaml
type: flat                     # 생략 시 기본 flat
reference:
  dimensions:                  # J·K 방향 실제 치수 (없으면 둘 다 1.0 이 된다)
    length_i: 100.0
    length_j: 10.0
    length_k: 2.0
  # flat_mesh: "ref_flat.k"    # 참조 메시로 자동 스케일할 때 (--no-scale 이면 무시)
elements_j: 5                  # J 방향 요소 수
elements_k: 2                  # K 방향 요소 수
variable_density:              # 존 이름 고정 5개
  zone1_dense_start:
    length: 10.0
    num_elements: 10
  zone2_increasing:
    length: 20.0
    num_elements: 8
  zone3_sparse:
    length: 40.0
    num_elements: 8
  zone4_decreasing:
    length: 20.0
    num_elements: 8
  zone5_dense_end:
    length: 10.0
    num_elements: 10
```

실행 결과(확인): `KooRemapper generate-var var.yaml var.k` → 810 노드 / 440 요소, 바운딩 박스 `100 × 10 × 2`.

> **예전 판 예제는 퇴화 메시를 만들었습니다.** `reference.dimensions` 없이 `zone1` 만 적은 예제를 그대로 돌리면
> 종료 코드는 0 이지만 바운딩 박스가 `10 × 1 × 1` 인 (J·K 방향 치수가 1.0 으로 떨어진) 메시가 나옵니다.
> `elements_j: 50`·`elements_k: 10` 까지 그대로 쓰면 두께 1.0 을 10층으로 쪼갠 25,000 요소짜리 납작한 메시가 됩니다.
>
> **존 이름은 `zone1_dense_start`·`zone2_increasing`·`zone3_sparse`·`zone4_decreasing`·`zone5_dense_end` 5개로 고정**입니다
> (다른 이름은 읽히지 않습니다). 전부 채울 필요는 없지만, 쓰려면 이 이름이어야 합니다.

#### YAML 설정 (곡선 타입, `type: curved`)

중심선 좌표(`centerline_points`)를 보간해 단면을 스윕합니다.

```yaml
type: curved
reference:
  flat_mesh: "ref_flat.k"      # 스케일용(선택)
centerline_points:
  - [0, 0]
  - [50, 0]
  - [100, 50]
  - [150, 50]
interpolation: catmull_rom     # linear | catmull_rom | bspline
cross_section:                 # 참조가 없을 때만
  width: 10.0
  thickness: 2.0
elements_along_curve: 100
elements_j: 20
elements_k: 5
```

> **v1.8.0 정정**: 구버전 정본이 보이던 `zones:`(id/nx/ny/nz/x_min/x_max…) 형식은 v1.8.0 바이너리가 파싱하는 스키마와 다릅니다. help 기준은 위 `variable_density`/`centerline_points` 구조입니다(zones 형식 병행 지원 여부는 확인 필요).
>
> **출력 내용**: `generate-var` 가 쓰는 K파일은 `*NODE` + `*ELEMENT_SOLID` + `*END` 뿐입니다 —
> `*PART`·`*SECTION`·`*MAT` 카드는 들어가지 않으므로(확인), 해석에 쓰려면 파트·재질 카드를 따로 붙여야 합니다.
> 그래서 `KooRemapper info` 로 보면 `Parts: 0` 으로 나옵니다.

---

<!-- END MANUAL EXCERPT -->
