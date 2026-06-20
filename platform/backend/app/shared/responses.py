"""Standard response envelope: {success, data, message, errors}.

Mirrors the ReportArchive convention so the frontend + MCP client can unwrap
responses uniformly.
"""
from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


def ok(data: Any = None, message: str | None = None, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {"success": True, "data": data, "message": message, "errors": None}
        ),
    )


def fail(
    message: str,
    *,
    status_code: int = 400,
    errors: Any = None,
    data: Any = None,
    headers: dict | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {"success": False, "data": data, "message": message, "errors": errors}
        ),
        headers=headers,
    )
