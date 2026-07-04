"""Translate (operation, args) into an actual KooRemapper invocation.

The runner executes with cwd = the session storage dir, so file references are
plain filenames (relative paths resolve naturally, exactly like the examples).

Invocation models (driven by the catalog entry):
  positional : argv = [op, *flags, *ordered_positionals]
               - role flag    : boolean→[flag]; valued→[flag, str(value)]
               - role config  : write args[name] dict to <name>.yaml, use that path
               - else         : use args[name] as the positional token (filename/value)
  yaml/structured : build a nested dict from each param's yaml_path, write config.yaml
  yaml/freeform   : write args["config"] verbatim to config.yaml
In both yaml cases argv = [op, "config.yaml"].
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from kooremapper_core import catalog



class _KDumper(yaml.SafeDumper):
    """YAML dumper matching KooRemapper's custom C++ parser expectations:
    - block sequences are INDENTED under their key (`  - item`), and
    - scalar-only collections use flow style (`[0, 0, 1]`, `[1, 2, 3]`, `[3, 3]`).
    This reproduces the style of the example .yaml files the parser was built for.
    """


def _increase_indent(self, flow=False, indentless=False):  # noqa: ANN001
    return super(_KDumper, self).increase_indent(flow, False)


_KDumper.increase_indent = _increase_indent  # type: ignore[assignment]


def _represent_list(dumper, data):  # noqa: ANN001
    # Scalar-only sequences → flow ([0, 0, 1] / [1, 2, 3]); anything containing a
    # mapping or nested list → block (one indented `- ` per item). Mappings always
    # stay block (the C++ parser is line-oriented).
    scalar = all(isinstance(x, (int, float, str, bool)) or x is None for x in data)
    return dumper.represent_sequence(
        "tag:yaml.org,2002:seq", data, flow_style=scalar
    )


_KDumper.add_representer(list, _represent_list)


# Job.args is stored as JSONB, which does NOT preserve key order. KooRemapper's
# YAML parser is order-sensitive (it needs the discriminator `type`/`action` key
# before the type-specific fields — e.g. indent reads r1/r2 into a default
# profile if `type` hasn't been seen yet). Emit those keys first in every mapping.
_PRIORITY_KEYS = ("type", "action")


def _represent_dict(dumper, data):  # noqa: ANN001
    keys = [k for k in _PRIORITY_KEYS if k in data] + [k for k in data if k not in _PRIORITY_KEYS]
    return dumper.represent_mapping("tag:yaml.org,2002:map", [(k, data[k]) for k in keys])


_KDumper.add_representer(dict, _represent_dict)


def _dump_yaml(obj) -> str:
    return yaml.dump(
        obj, Dumper=_KDumper, default_flow_style=False, allow_unicode=True, sort_keys=False
    )


@dataclass
class BuiltCommand:
    argv: list[str]  # WITHOUT the binary path (runner prepends it)
    written_files: dict[str, str] = field(default_factory=dict)  # filename -> yaml text (audit)
    error: str | None = None


def _set_dotted(d: dict, dotted: str, value: Any) -> None:
    keys = dotted.split(".")
    cur = d
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = value


def build_command(op: str, args: dict, work_dir: Path,
                  material_db_default: str | None = None) -> BuiltCommand:
    entry = catalog.get_operation(op)
    if entry is None:
        return BuiltCommand(argv=[], error=f"unknown operation: {op}")

    # matdb convenience: if no database given and a default library path is
    # provided by the caller, inject it (so callers can use a bundled DB).
    if op == "matdb" and not args.get("database") and material_db_default:
        args = {**args, "database": str(material_db_default)}

    # Validate against the op's JSON Schema first.
    errs = catalog.validate_args(op, args)
    if errs:
        return BuiltCommand(argv=[], error="; ".join(errs))

    params = entry.get("params", [])
    invocation = entry.get("invocation")

    if invocation == "positional":
        return _build_positional(op, entry, params, args, work_dir)
    if invocation == "yaml":
        return _build_yaml(op, entry, params, args, work_dir)
    return BuiltCommand(argv=[], error=f"unknown invocation: {invocation}")


def _build_positional(op, entry, params, args, work_dir) -> BuiltCommand:
    flags: list[str] = []
    positionals: list[tuple[int, str]] = []
    written: dict[str, str] = {}

    for p in params:
        name, role = p["name"], p["role"]
        if name not in args and not p.get("required"):
            if role == "flag":
                continue
            # optional positional omitted
            continue
        val = args.get(name)
        if role == "flag":
            flag = p.get("flag") or f"--{name}"
            if p["type"] == "boolean":
                if bool(val):
                    flags.append(flag)
            elif val is not None:
                flags.extend([flag, str(val)])
        elif role == "config" or p["type"] == "config":
            fname = f"{name}.yaml"
            text = _dump_yaml(val or {})
            (work_dir / fname).write_text(text, encoding="utf-8")
            written[fname] = text
            positionals.append((p.get("order", len(positionals)), fname))
        else:  # input_file / output / value
            positionals.append((p.get("order", len(positionals)), str(val)))

    positionals.sort(key=lambda t: t[0])
    # Positionals FIRST, then flags: extract-surface requires positionals before
    # options, and the other positional ops (map/prestress/shellmap/generate)
    # accept flags in either position.
    argv = [op, *[v for _, v in positionals], *flags]
    return BuiltCommand(argv=argv, written_files=written)


def _build_yaml(op, entry, params, args, work_dir) -> BuiltCommand:
    style = entry.get("config_style")
    if style == "freeform":
        config = args.get("config") or {}
        if not isinstance(config, dict):
            return BuiltCommand(argv=[], error="`config` must be an object")
    else:  # structured
        config = {}
        for p in params:
            name = p["name"]
            if name not in args:
                continue
            path = p.get("yaml_path") or name
            _set_dotted(config, path, args[name])

    text = _dump_yaml(config)
    cfg_path = work_dir / "config.yaml"
    cfg_path.write_text(text, encoding="utf-8")
    # Absolute path so ops that resolve companion files (dat_file, model, …)
    # relative to the CONFIG's directory (e.g. warpage/bend) find them in the
    # session dir. cwd is already the session dir, so this is strictly safer.
    return BuiltCommand(argv=[op, str(cfg_path)], written_files={"config.yaml": text})
