"""Operation catalog — single source of truth for the KooRemapper ops.

The data lives in `catalog_data.json` (one entry per op). This module loads it,
exposes lookups, and derives a JSON Schema per op for (a) request validation,
(b) frontend auto-form generation, and (c) MCP `describe_operation`.

Entry contract (see catalog_data.json):
  name, category, summary, description
  invocation     : "positional" | "yaml"
  config_style   : null | "structured" | "freeform"   (yaml only)
  takes_kfile, requires_gmsh, requires_tetgen : bool
  params[]       : ordered parameter definitions, each:
      name, type ("file"|"output"|"string"|"number"|"integer"|"boolean"
                  |"enum"|"array"|"object"|"config"),
      role ("input_file"|"output"|"value"|"flag"|"yaml_field"|"config"),
      required, description,
      order        (positional: argv order),
      flag         (flag role: e.g. "--thickness"/"--single"),
      yaml_path    (yaml_field role: dotted path),
      enum, default
  example        : {args:{...}, note}
  example_folder, notes
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

_DATA_PATH = Path(__file__).with_name("catalog_data.json")

# Map catalog param types to JSON Schema types.
_JSON_TYPE = {
    "file": "string",
    "output": "string",
    "string": "string",
    "number": "number",
    "integer": "integer",
    "boolean": "boolean",
    "enum": "string",
    "array": "array",
    "object": "object",
    "config": "object",
}


def _coerce_scalar(v, ptype: str):
    """Cast a scalar to the param's native type (agents may emit it as a string)."""
    if ptype == "integer":
        try:
            return int(v)
        except (TypeError, ValueError):
            return v
    if ptype == "number":
        try:
            return float(v)
        except (TypeError, ValueError):
            return v
    if ptype == "boolean" and isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "on")
    return v


def _coerce_enum(values: list, ptype: str) -> list:
    """Cast enum entries to the param's native type (agents may emit them as strings)."""
    if ptype not in ("integer", "number"):
        return values
    return [_coerce_scalar(v, ptype) for v in values]


@lru_cache
def _load() -> dict[str, dict]:
    if not _DATA_PATH.exists():
        return {}
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    ops = raw["operations"] if isinstance(raw, dict) else raw
    return {op["name"]: op for op in ops}


def list_operations() -> list[dict]:
    """Compact summaries for the catalog browser / MCP list_operations."""
    out = []
    for op in _load().values():
        out.append(
            {
                "name": op["name"],
                "category": op.get("category"),
                "summary": op.get("summary"),
                "invocation": op.get("invocation"),
                "takes_kfile": op.get("takes_kfile", False),
                "requires_gmsh": op.get("requires_gmsh", False),
                "requires_tetgen": op.get("requires_tetgen", False),
            }
        )
    return sorted(out, key=lambda d: (d["category"] or "", d["name"]))


def get_operation(name: str) -> dict | None:
    return _load().get(name)


def operation_names() -> list[str]:
    return list(_load().keys())


def args_json_schema(name: str) -> dict | None:
    """Build a JSON Schema for an op's `args` object from its params."""
    op = get_operation(name)
    if op is None:
        return None
    props: dict[str, Any] = {}
    required: list[str] = []
    for p in op.get("params", []):
        schema: dict[str, Any] = {"type": _JSON_TYPE.get(p["type"], "string")}
        if p.get("description"):
            schema["description"] = p["description"]
        if p.get("enum"):
            schema["enum"] = _coerce_enum(p["enum"], p["type"])
        if p.get("default") is not None:
            schema["default"] = _coerce_scalar(p["default"], p["type"])
        if p["type"] == "file":
            schema["x-kind"] = "session_file"  # hint: pick from session files
        props[p["name"]] = schema
        if p.get("required"):
            required.append(p["name"])
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": op.get("invocation") == "yaml"
        and op.get("config_style") == "freeform",
    }


def validate_args(name: str, args: dict) -> list[str]:
    """Validate args against the op schema. Returns a list of error strings (empty = ok)."""
    schema = args_json_schema(name)
    if schema is None:
        return [f"unknown operation: {name}"]
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{'.'.join(str(p) for p in e.path) or '(root)'}: {e.message}"
        for e in validator.iter_errors(args)
    ]
