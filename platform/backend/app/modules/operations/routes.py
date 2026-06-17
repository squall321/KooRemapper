"""Operation catalog API — what KooRemapper can do + each op's arg schema.

Read-only and not user-specific, but still requires auth (consistent surface).
Feeds the frontend catalog browser / auto-form and the MCP describe_operation tool.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import User
from app.runner import catalog
from app.shared.auth import get_current_user
from app.shared.responses import ok

router = APIRouter(tags=["operations"])


@router.get("/operations")
async def list_operations(_user: User = Depends(get_current_user)):
    return ok(catalog.list_operations())


@router.get("/operations/{op}")
async def describe_operation(op: str, _user: User = Depends(get_current_user)):
    entry = catalog.get_operation(op)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"알 수 없는 오퍼레이션: {op}")
    return ok({**entry, "args_schema": catalog.args_json_schema(op)})
