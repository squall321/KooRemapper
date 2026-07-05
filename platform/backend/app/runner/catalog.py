# app.runner.catalog — 공유 kooremapper_core.catalog 재수출(op 지식 단일 소스).
"""Backend catalog access — a thin re-export of ``kooremapper_core.catalog`` so
the 45-op knowledge (catalog_data.json + loader/validator) lives in ONE place
(platform/core), shared by the CLI, MCP, and pyKooCAE module."""
from __future__ import annotations

import sys
from pathlib import Path

# platform/backend/app/runner/catalog.py → platform/core (bind-mounted at
# /workspace/platform/core in the api container; on sys.path for local tests too).
_CORE = Path(__file__).resolve().parents[3] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from kooremapper_core.catalog import (  # noqa: E402,F401
    args_json_schema,
    get_operation,
    list_operations,
    operation_names,
    validate_args,
)
