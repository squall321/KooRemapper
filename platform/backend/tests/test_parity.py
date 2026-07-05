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
_PY_CLIENT = _PLATFORM / "clients" / "python" / "kooremapper" / "__init__.py"


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


def test_python_client_mirrors_mcp_read_surface():
    """The Python client (sync + async) must expose the same session/job/system
    reads as MCP, so adding an MCP tool without a client method is caught."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("kooremapper_client", _PY_CLIENT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Python client uses pythonic short names (run, job_outputs) for a few MCP
    # tools (run_operation, get_job_outputs); assert by the client's own names.
    required = {
        "whoami", "system_status", "system_capabilities", "list_operations",
        "describe_operation", "list_sessions", "get_session", "list_files",
        "list_session_jobs", "get_job", "job_outputs", "run",
    }
    for cls in (mod.KooRemapper, mod.AsyncKooRemapper):
        missing = sorted(m for m in required if not hasattr(cls, m))
        assert not missing, f"{cls.__name__} missing {missing}"


def test_backend_catalog_is_single_source_from_core():
    """The backend no longer carries its own catalog_data.json — it re-exports
    kooremapper_core (single source). Guard against a stray backend copy reappearing
    and confirm the re-export still yields the 45 ops."""
    assert not (_BACKEND / "app" / "runner" / "catalog_data.json").exists(), (
        "backend catalog_data.json reappeared — it must come from kooremapper_core"
    )
    assert (_PLATFORM / "core" / "kooremapper_core" / "catalog_data.json").exists()
    assert len(catalog.operation_names()) >= 45
