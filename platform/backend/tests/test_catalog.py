"""Catalog integrity + arg-schema validation tests (no DB required)."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.runner import catalog  # noqa: E402


def test_catalog_loads_all_ops():
    names = catalog.operation_names()
    assert len(names) >= 45, f"expected >=45 ops, got {len(names)}"
    assert "map" in names and "assemble" in names and "meshfix" in names


def test_every_op_has_required_fields():
    for name in catalog.operation_names():
        op = catalog.get_operation(name)
        for field in ("category", "summary", "invocation", "params", "example"):
            assert field in op, f"{name} missing {field}"
        assert op["invocation"] in ("positional", "yaml")
        if op["invocation"] == "yaml":
            assert op["config_style"] in ("structured", "freeform"), name
        else:
            assert op["config_style"] is None, name


def test_every_schema_builds():
    for name in catalog.operation_names():
        schema = catalog.args_json_schema(name)
        assert schema["type"] == "object"
        assert isinstance(schema["required"], list)


def test_every_example_passes_its_own_schema():
    for name in catalog.operation_names():
        args = catalog.get_operation(name)["example"]["args"]
        errs = catalog.validate_args(name, args)
        assert errs == [], f"{name} example fails its own schema: {errs}"


def test_validate_args_catches_missing_required():
    errs = catalog.validate_args("map", {"bent_mesh": "b.k"})
    assert any("flat_mesh" in e for e in errs)
    assert any("output" in e for e in errs)


def test_validate_args_catches_bad_enum():
    errs = catalog.validate_args("relax", {"model": "m.k", "output": "o.k", "mode": "bogus"})
    assert any("mode" in e for e in errs)


def test_unknown_op():
    assert catalog.get_operation("nope") is None
    assert catalog.args_json_schema("nope") is None
    assert catalog.validate_args("nope", {}) == ["unknown operation: nope"]


def test_gmsh_tetgen_flags():
    assert catalog.get_operation("meshfix")["requires_gmsh"] is True
    # gmsh required only for meshfix
    for name in catalog.operation_names():
        if name != "meshfix":
            assert catalog.get_operation(name)["requires_gmsh"] is False, name
