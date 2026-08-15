"""Parity guards — keep web / MCP / Python in lockstep with the catalog.

These are pure (no DB): they assert the single-source-of-truth invariants that
let a new operation propagate to all three surfaces with no per-surface code:
  - every catalog op is describable (has an args_schema) → web SchemaForm,
    MCP describe_operation and Python describe_operation all work for any op;
  - the mcp_tools count advertised by /system/capabilities is derived (not
    hand-written) from the actual number of @mcp.tool tools.
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


def test_advertised_mcp_tool_count_is_derived_from_server():
    """capabilities 의 mcp_tools 는 리터럴이 아니라 MCP 소스에서 산출돼야 한다.

    system/routes 의 _mcp_tool_count() 가 server.py 의 실제 @mcp.tool( 수와 일치하는지
    검증한다(도구 추가/삭제 시 손댈 리터럴이 없어야 한다 = 하드코딩 금지).
    """
    from app.modules.system.routes import _mcp_tool_count

    actual = _MCP_SERVER.read_text(encoding="utf-8").count("@mcp.tool(")
    assert actual >= 20, f"unexpectedly few MCP tools: {actual}"
    assert _mcp_tool_count() == actual

    # system/routes 에 mcp_tools=<숫자> 리터럴이 남아있지 않아야 한다.
    routes_src = _SYSTEM_ROUTES.read_text(encoding="utf-8")
    assert not re.search(r"['\"]?mcp_tools['\"]?\s*[:=]\s*\d+", routes_src), (
        "system/routes.py 에 mcp_tools 숫자 리터럴이 있습니다 — 동적 산출로 바꾸세요."
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
    and confirm the re-export still yields all ops."""
    assert not (_BACKEND / "app" / "runner" / "catalog_data.json").exists(), (
        "backend catalog_data.json reappeared — it must come from kooremapper_core"
    )
    assert (_PLATFORM / "core" / "kooremapper_core" / "catalog_data.json").exists()
    assert len(catalog.operation_names()) >= 45
