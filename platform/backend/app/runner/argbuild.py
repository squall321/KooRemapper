# app.runner.argbuild — 공유 kooremapper_core.build_command 위에 플랫폼 번들-DB 기본값을 얹는다.
"""Backend argbuild — delegates to ``kooremapper_core.build_command`` and injects
the platform's bundled material-DB default for matdb, so the argv/config logic
lives once in platform/core (shared with the CLI and pyKooCAE module)."""
from __future__ import annotations

import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parents[3] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from kooremapper_core import argbuild as _core  # noqa: E402
from kooremapper_core.argbuild import BuiltCommand, _dump_yaml  # noqa: E402,F401

from app.config import settings  # noqa: E402

# matdb's material DB is bundled next to the binary (bin/materials/material_db.json).
# Injected as the default when a matdb job omits `database`, so the 525-material
# library is used with no session upload.
_BUNDLED_MATERIAL_DB = settings.kooremapper_bin.parent / "materials" / "material_db.json"


def build_command(op: str, args: dict, work_dir: Path) -> BuiltCommand:
    """Build the KooRemapper invocation, defaulting matdb's DB to the bundled lib."""
    return _core.build_command(op, args, work_dir, material_db_default=str(_BUNDLED_MATERIAL_DB))
