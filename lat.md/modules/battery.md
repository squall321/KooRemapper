# Module: src/battery/

Battery-domain mesh, contacts, swelling, control-card generation.

| File | Role |
|------|------|
| [BatteryMeshStacked.cpp](../../src/battery/BatteryMeshStacked.cpp) | stacked-cell mesh generation |
| [BatteryMeshWound.cpp](../../src/battery/BatteryMeshWound.cpp) | jelly-roll / wound-cell mesh generation |
| [BatteryContacts.cpp](../../src/battery/BatteryContacts.cpp) | inter-layer contact card generation |
| [BatteryMaterials.cpp](../../src/battery/BatteryMaterials.cpp) | preset materials for cathode/anode/separator/etc. |
| [BatterySwelling.cpp](../../src/battery/BatterySwelling.cpp) | charge-state-driven swelling field |
| [BatteryControl.cpp](../../src/battery/BatteryControl.cpp) | top-level orchestration; emits `*CONTROL_*` |
| [BatteryWriter.cpp](../../src/battery/BatteryWriter.cpp) | final `.k` emit |
| [BatteryConfig.h](../../src/battery/BatteryConfig.h) | YAML schema struct |
| [BatteryIds.h](../../src/battery/BatteryIds.h) | PID/MID range conventions |

## Cross-references

- Driver: [[commands/battery#battery — battery mesh/control generator]].
- Generated artifacts: `battery_stacked_*`, `battery_wound_*` `.k` files in repo root.
