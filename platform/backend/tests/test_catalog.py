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
        # "external" = 이 서버의 바이너리가 아니라 **다른 클러스터**에서 도는 작업.
        # 세 번째 값이라 여기에 더하지만, 아래에서 그 갈래의 불변식을 따로 고정한다 —
        # 안 그러면 "허용값을 늘린다" 가 검사를 느슨하게 만드는 일이 된다.
        assert op["invocation"] in ("positional", "yaml", "external")
        if op["invocation"] == "yaml":
            assert op["config_style"] in ("structured", "freeform"), name
        else:
            assert op["config_style"] is None, name


def test_external_ops_carry_no_local_invocation_machinery():
    """외부 작업은 로컬 argv 를 만들지 않는다 — 만들기 시작하면 두 실행 경로가 갈린다."""
    for name in catalog.operation_names():
        op = catalog.get_operation(name)
        if op["invocation"] != "external":
            continue
        for p in op["params"]:
            assert "order" not in p, f"{name}.{p['name']}: 외부 작업에 positional order 가 있다"
            assert "flag" not in p, f"{name}.{p['name']}: 외부 작업에 flag 가 있다"
            assert "yaml_path" not in p, f"{name}.{p['name']}: 외부 작업에 yaml_path 가 있다"


def test_the_local_builder_refuses_external_ops_clearly():
    """빈 argv 로 조용히 돌지 않는다 — 어디서 도는 작업인지 오류에 적는다."""
    from kooremapper_core.argbuild import build_command
    from pathlib import Path

    externals = [n for n in catalog.operation_names()
                 if catalog.get_operation(n)["invocation"] == "external"]
    assert externals, "외부 작업이 하나도 없다 — 이 검사가 아무것도 안 본다"
    for name in externals:
        # 스키마 검증이 먼저 돈다 — 그래서 **유효한** 인자로 불러야 external 분기까지 닿는다.
        args = (catalog.get_operation(name).get("example") or {}).get("args") or {}
        built = build_command(name, args, Path("/tmp"))
        assert built.argv == []
        assert built.error and "external" in built.error.lower(), built.error


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
