"""argbuild tests — positional/flag ordering + YAML serialization style."""
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from app.runner.argbuild import _dump_yaml, build_command  # noqa: E402


def _wd():
    return Path(tempfile.mkdtemp())


def test_positional_flags_after():
    b = build_command("map", {"single": True, "bent_mesh": "b.k", "flat_mesh": "f.k", "output": "o.k"}, _wd())
    assert b.error is None
    # positionals first, then flags (extract-surface requires this)
    assert b.argv == ["map", "b.k", "f.k", "o.k", "--single"], b.argv


def test_positional_valued_flag():
    b = build_command("prestress", {"ref_mesh": "r.k", "def_mesh": "d.k", "output": "o.dynain", "E": 210000, "strain": "green"}, _wd())
    assert b.error is None
    assert b.argv[:4] == ["prestress", "r.k", "d.k", "o.dynain"]
    assert "--E" in b.argv and "210000" in b.argv
    assert "--strain" in b.argv and "green" in b.argv


def test_yaml_structured_written():
    wd = _wd()
    b = build_command("relax", {"model": "m.k", "output": "r.k", "level": 3, "mode": "explicit"}, wd)
    assert b.argv[0]=="relax" and b.argv[1].endswith("config.yaml")
    cfg = yaml.safe_load((wd / "config.yaml").read_text())
    assert cfg == {"model": "m.k", "output": "r.k", "level": 3, "mode": "explicit"}


def test_yaml_freeform_verbatim():
    wd = _wd()
    config = {"base_model": "x.k", "output": "r", "operations": [{"type": "bend", "target_pid": 1}]}
    b = build_command("assemble", {"config": config}, wd)
    assert b.argv[0]=="assemble" and b.argv[1].endswith("config.yaml")
    cfg = yaml.safe_load((wd / "config.yaml").read_text())
    assert cfg == config


def test_dump_yaml_scalar_arrays_flow_mappings_block():
    text = _dump_yaml({"loads": [{"part": 1, "direction": [0, 0, 1]}], "material": {"E": 1.0, "nu": 0.3}})
    # scalar array inline (flow)
    assert "direction: [0, 0, 1]" in text
    # block sequence indented
    assert "loads:\n  - part: 1" in text
    # mapping stays block (not flow), so no inline brace for material
    assert "material:\n  E: 1.0" in text
    assert "{E:" not in text


def test_dump_yaml_nested_array_flow_inner():
    text = _dump_yaml({"operations": [{"shape": {"points": [[3, 3], [7, 3]]}}]})
    # inner coordinate arrays flow, outer block + indented
    assert "- [3, 3]" in text
    assert "points:\n" in text


def test_validation_error_propagates():
    b = build_command("map", {"bent_mesh": "b.k"}, _wd())
    assert b.error and "flat_mesh" in b.error


def test_unknown_op_error():
    b = build_command("nope", {}, _wd())
    assert b.error and "unknown" in b.error


def test_all_catalog_examples_build():
    """Every op's catalog example must build a command without error — guards
    against an argbuild/catalog change breaking any op (M14)."""
    from app.runner import catalog

    failures = []
    for name in catalog.operation_names():
        op = catalog.get_operation(name)
        args = (op.get("example") or {}).get("args") or {}
        b = build_command(name, args, _wd())
        if b.error:
            failures.append(f"{name}: {b.error}")
    assert not failures, "catalog examples that fail to build:\n" + "\n".join(failures)


def test_matdb_defaults_to_bundled_db():
    """Omitting `database` for matdb injects the bundled library path (L8)."""
    from app.runner.argbuild import _BUNDLED_MATERIAL_DB

    b = build_command("matdb", {"model": "m.k", "output": "o.k", "mat_type": "MAT_ELASTIC"}, _wd())
    assert b.error is None
    cfg = b.written_files.get("config.yaml", "")
    assert str(_BUNDLED_MATERIAL_DB) in cfg, "bundled DB path not injected"
    # an explicit database is respected (not overridden)
    b2 = build_command("matdb", {"model": "m.k", "output": "o.k", "database": "custom.json"}, _wd())
    assert "custom.json" in b2.written_files.get("config.yaml", "")
