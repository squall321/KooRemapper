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


# 여러 줄 문자열(material_card 등)을 리터럴 블록 `key: |` 로 내보내기 전에 정규화한다.
# PyYAML 은 아래 세 경우에 블록 표기를 포기하거나 명시 들여쓰기 헤더를 붙이는데, 그러면 C++ 파서가
# 카드를 못 읽어 조용히 mid=0 짜리 덱이 나온다(따옴표 문자열 한 줄이 그대로 덱에 써지기도 한다):
#   - 줄 끝 공백  → 따옴표 문자열   (LS-DYNA 고정 폭 칸은 끝 공백에 의미 없음 → 뗀다)
#   - TAB         → 따옴표 문자열   (고정 폭 카드에 탭은 자리 표시일 뿐 → 편집기 기준 8칸으로 편다)
#   - 앞쪽 빈 줄  → `|2` 헤더       (카드 앞 빈 줄은 의미 없음 → 버린다)
# 셋 다 칸 위치(10칸 정렬)를 바꾸지 않는다. 첫 줄이 공백으로 시작하는 카드는 YAML 규칙상 `|2` 를
# 피할 수 없고, 선행 공백을 떼면 MID 칸이 망가지므로 여기서는 손대지 않는다.
def _normalize_block_text(data: str) -> str:
    lines = [line.rstrip() for line in data.expandtabs(8).split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n" if lines else ""


def _represent_str(dumper, data):  # noqa: ANN001
    text = _normalize_block_text(data)
    if "\n" in text.rstrip("\n"):
        return dumper.represent_scalar("tag:yaml.org,2002:str", text, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_KDumper.add_representer(str, _represent_str)


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
