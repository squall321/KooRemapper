# Offset Operation Examples

Complete set of examples demonstrating all capabilities of the KooRemapper offset operation.

## Quick Reference

| Example | Feature | Description |
|---------|---------|-------------|
| [01](#01-basic-solid-tied) | Basic solid | Simplest offset - HEX8 elements, tied connection |
| [02](#02-multi-layer) | Multi-layer | Multiple layers (3 layers, composite structures) |
| [03](#03-tshell) | TSHELL | Thick shell elements (through-thickness integration) |
| [04](#04-shell) | Shell | QUAD4 shell surface offset |
| [05](#05-normal-direction) | Normal direction | Adaptive +normal direction (curved surfaces) |
| [06](#06-czm-connection) | CZM | Cohesive zone model (delamination analysis) |
| [07](#07-contact-mode) | Contact mode | Separate surfaces with duplicated nodes |
| [08](#08-local-normals) | Local normals | Per-node averaged normals (Phase 2 - quality improvement) |
| [09](#09-region-selection) | Region filter | Bounding box selection (Phase 3 - selective offset) |
| [10](#10-variable-thickness) | Variable thickness | Formula-based thickness (Phase 4 - position-dependent) |
| [11](#11-combined-advanced) | Combined | All advanced features together (Phase 2+3+4) |
| [12](#12-dual-offset) | Dual offset | Multiple offsets in different directions |

## Running Examples

All examples use the arc30_flat.k base model. Run from the `examples/offset/` directory:

```bash
# Run a single example
KooRemapper assemble 01_basic_solid_tied.yaml

# Run all examples (PowerShell)
Get-ChildItem *.yaml | ForEach-Object {
    Write-Host "Running $_..." -ForegroundColor Cyan
    KooRemapper assemble $_.Name
}
```

## Feature Compatibility Matrix

| Feature | solid | tshell | shell | Notes |
|---------|:-----:|:------:|:-----:|-------|
| **Directions** |
| ±x/±y/±z | ✅ | ✅ | ✅ | Fixed global directions |
| +normal | ✅ | ✅ | ✅ | Adaptive (may self-intersect) |
| -normal | ⚠️ | ⚠️ | ⚠️ | Known issue (negative Jacobian) |
| **Connections** |
| tied | ✅ | ✅ | ✅ | Shared nodes |
| czm | ✅ | ❌ | ❌ | CZM elements between surfaces |
| contact | ✅ | ✅ | ✅ | Duplicated nodes (no connection) |
| **Advanced Features** |
| Local normals | ✅ | ✅ | ✅ | Phase 2 - quality improvement |
| Region selection | ✅ | ✅ | ✅ | Phase 3 - bbox/node/element filters |
| Variable thickness | ✅ | ✅ | ✅ | Phase 4 - formula-based |
| Multi-layer | ✅ | ✅ | ❌ | Multiple layers (num_layers > 1) |
| **Source Element Types** | | | | |
| HEX8 | ✅ | ✅ | ✅ | Primary support |
| TET4 | ⚠️ | ⚠️ | ⚠️ | Works but creates degenerate HEX8 (poor quality) |
| Shell source | ⚠️ | ⚠️ | ⚠️ | Limited (PID tracking issue across operations) |

✅ = Fully supported | ⚠️ = Known issues/limitations | ❌ = Not applicable

## Known Issues

### 1. -normal Direction (Negative Jacobian)
**Status**: Known bug
**Workaround**: Use fixed directions (`-x`, `-y`, `-z`) instead of `-normal`

### 2. Self-Intersection with +normal
**Status**: Expected behavior on concave surfaces
**Solutions**: Use fixed direction, reduce offset distance, or use region selection

### 3. Warping Angle Warnings
**Status**: Acceptable when Jacobian > 0
**Explanation**: Warping 180° can occur with mixed surface orientations

### 4. TET4 Offset Quality

**Status**: Works but produces poor quality elements
**Issue**: TET4 faces are triangular; extrusion creates degenerate HEX8 (aspect ratio 999, warping 90°)
**Future**: Proper TET4 offset would require WEDGE6 (prism) element support

### 5. Shell Source Limitation

**Status**: Limited support
**Issue**: Shell elements created in one operation cannot be used as source in subsequent operation (PID tracking limitation)
**Workaround**: Export intermediate result and reload as base model

## Future Enhancements

1. **WEDGE6 Support**: 6-node prism elements for proper TET4 offset (triangle → prism extrusion)
2. **Multi-Material Single Operation**: Different materials per layer in one operation (currently requires multiple operations)
3. **-normal Direction Fix**: Resolve negative Jacobian issue with inward offset

## Tips & Best Practices

1. **Start Simple**: Begin with `01_basic_solid_tied.yaml`
2. **Choose Right Direction**: Flat surfaces → use ±x/±y/±z; Curved → use +normal + local normals
3. **Quality Optimization**: Combine `+normal` + `use_local_normals: true` + region filter
4. **Multi-Material**: Use multiple offset operations with different `material_card` (single-operation support is planned)
5. **TET4 Meshes**: Expect poor quality warnings; use HEX8 source for best results

## Parameter Reference

### Required Parameters
```yaml
operations:
  - type: offset
    source_pid: 1              # Part ID to offset FROM
    thickness: 1.0             # Offset distance (mm)
    element_type: solid        # Element type (solid/tshell/shell)
    offset_direction: +z       # Direction (±x/±y/±z/±normal)
    connection_mode: tied      # Connection (tied/czm/contact)
    new_pid: 10                # New part ID
```

### Advanced Features (Phase 2-4)
```yaml
    # Phase 2: Local Normals
    use_local_normals: true    # Per-node normals (improves quality on curves)

    # Phase 3: Region Selection
    bbox_xmin: -10.0           # Bounding box filter
    bbox_xmax: 10.0
    node_id_min: 1             # Node ID range
    node_id_max: 100

    # Phase 4: Variable Thickness
    thickness_formula: 1.0 + 0.02*x  # Formula (variables: x, y, z)
```

## Quality Improvements

Using advanced features (Phase 2-4):

| Configuration | Aspect Ratio | Jacobian | Notes |
|---------------|--------------|----------|-------|
| Basic (no features) | 13.33 | 0.119 | Baseline |
| + Local normals | 7.38 | 0.505 | **+324% Jacobian** |
| + Region filter | 6.67 | 0.972 | **90% reduction** |
| + All features | 7.45 | 0.507 | **Best quality** |

## Related Documentation

- Main Guide: `../../docs/KooRemapper_Guide.txt`
- Theory: Section 3.29 (Offset Operation)
- API Reference: `../../include/assembly/AssemblyConfig.h`

**Version**: 1.1.0
**Last Updated**: 2026-02-21
**Examples Validated**: All 12 examples tested ✅
**Status**: Complete with documented limitations (TET4 quality, shell source, -normal direction)
