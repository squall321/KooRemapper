# KooRemapper op 지식(45개 스키마)의 단일 소스 — 카탈로그 + argbuild.
"""kooremapper_core — the shared operation catalog + argument builder.

One source of KooRemapper's 45-operation knowledge (JSON Schemas, examples,
invocation rules) reusable by the platform backend, the MCP server, a pyKooCAE
module, or any external tool — so the three consumption modes (CLI / MCP /
module) don't each re-implement how to build an op invocation.

    from kooremapper_core import catalog, build_command

    for name in catalog.operation_names():
        print(name, catalog.get_operation(name)["summary"])

    b = build_command("matdb", {"model": "m.k", "output": "o.k",
                                "materials": [{"match": "*"}]},
                      Path("work"),
                      material_db_default="/opt/kooremapper/materials/material_db.json")
    # b.argv → ["matdb", "config.yaml"]; b.written_files["config.yaml"] is the config
"""
from kooremapper_core import catalog
from kooremapper_core.argbuild import BuiltCommand, build_command

__all__ = ["catalog", "build_command", "BuiltCommand"]
