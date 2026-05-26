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

```bash
KooRemapper.exe generate <type> [options] <output.k>

Types: teardrop, arc, scurve, helix, torus, twist, wave,
       bulge, taper, waterdrop
```

테스트 및 데모용 다양한 기하학적 형상 HEX8 메시 생성.

### generate-var — 변밀도 메시 생성

```bash
KooRemapper.exe generate-var [--ref <ref.k>] [--no-scale] <config.yaml> <output.k>
```

#### YAML 설정 (평면 타입)

```yaml
type: flat
zones:
  - id: 1
    nx: 10
    ny: 8
    nz: 2
    x_min: 0.0
    x_max: 50.0
    y_min: 0.0
    y_max: 40.0
```

#### YAML 설정 (곡선 타입)

```yaml
type: curved
centerline: centerline.dat   # 중심선 좌표 파일
reference: ref_mesh.k        # 참조 두께용
zones:
  - ...
```

---

<!-- END MANUAL EXCERPT -->
