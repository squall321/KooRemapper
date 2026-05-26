# Module: src/squeeze/

| File | Role |
|------|------|
| [SqueezeConfigReader.cpp](../../src/squeeze/SqueezeConfigReader.cpp) | YAML → squeeze config |

Drives [[commands/squeeze#squeeze — interference-fit compression + reverse prestress (§7)]]. Two methods supported:

1. Direct strain specification + node displacement + dynain reverse stress.
2. Thermal expansion: insert `*MAT_ADD_THERMAL_EXPANSION` to model swelling.

See [[commands/squeeze#squeeze — interference-fit compression + reverse prestress (§7)]] for full YAML semantics.
