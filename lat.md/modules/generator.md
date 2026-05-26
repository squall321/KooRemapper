# Module: src/generator/

Programmatic mesh generation from YAML.

| File | Role |
|------|------|
| [YamlConfigReader.cpp](../../src/generator/YamlConfigReader.cpp) | shared YAML parser → `YamlNode` tree |
| [CurveInterpolator.cpp](../../src/generator/CurveInterpolator.cpp) | curve sampling for curved meshes |
| [CurvedMeshGenerator.cpp](../../src/generator/CurvedMeshGenerator.cpp) | curved/bent mesh generation |
| [VariableDensityMeshGenerator.cpp](../../src/generator/VariableDensityMeshGenerator.cpp) | variable-density mesh (`generate-var`) |

## Cross-references

- [[commands/generate#generate — YAML-driven mesh generation (§8)]] — driver.
- [[modules/mapper#Module: src/mapper/]] consumes generated meshes.

TODO: density-field interpolation rules, smoothing pass.
