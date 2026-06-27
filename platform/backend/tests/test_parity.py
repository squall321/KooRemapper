"""Parity guards — keep web / MCP / Python in lockstep with the catalog.

These are pure (no DB): they assert the single-source-of-truth invariants that
let a new operation propagate to all three surfaces with no per-surface code:
  - every catalog op is describable (has an args_schema) → web SchemaForm,
    MCP describe_operation and Python describe_operation all work for any op;
  - the hand-written mcp_tools count advertised by /system/capabilities matches
    the actual number of @mcp.tool tools (the one literal that can drift).
"""
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from app.runner import catalog  # noqa: E402

_PLATFORM = _BACKEND.parent
_MCP_SERVER = _PLATFORM / "mcp_server" / "server.py"
_SYSTEM_ROUTES = _BACKEND / "app" / "modules" / "system" / "routes.py"


def test_every_op_is_describable():
    """Any op must yield a usable args_schema (the describe route serves
    args_json_schema), or web SchemaForm / MCP / Python can't expose it generically."""
    names = catalog.operation_names()
    assert len(names) >= 45
    missing = []
    for name in names:
        schema = catalog.args_json_schema(name)
        if not isinstance(schema, dict) or "properties" not in schema:
            missing.append(name)
    assert not missing, f"ops without a usable args_schema: {missing}"


def test_advertised_mcp_tool_count_matches_server():
    """The mcp_tools number in /system/capabilities must match the real tool count.

    This is the only place the count is hand-written; if an @mcp.tool is added or
    removed without updating the literal, the web System page mis-reports it.
    """
    server_src = _MCP_SERVER.read_text(encoding="utf-8")
    actual = server_src.count("@mcp.tool(")
    assert actual >= 20, f"unexpectedly few MCP tools: {actual}"

    routes_src = _SYSTEM_ROUTES.read_text(encoding="utf-8")
    m = re.search(r"['\"]?mcp_tools['\"]?\s*[:=]\s*(\d+)", routes_src)
    assert m, "could not find the mcp_tools count in system/routes.py"
    advertised = int(m.group(1))
    assert advertised == actual, (
        f"/system/capabilities advertises mcp_tools={advertised} but server.py has "
        f"{actual} @mcp.tool tools — update the literal in system/routes.py"
    )
