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


# ★2026-10-14 — **물어볼 곳이 없어졌다.** 제출이 SmartTwinMCP(:5013)로 옮겨졌고, 그쪽
# `fullangle_drop_simulation` 은 각도를 **피보나치 N개**로만 받는다(`num_angles`). 프리셋을
# 내주던 :5012 의 `smarttwin_scenario_options` 는 쓰지 않는다.
#
# 그래서 빈 목록을 돌려주는데, **빈 목록만 돌려주지는 않는다** — 빈 목록은 "프리셋이 없다"
# 처럼 보이는데 실제로는 "이번 판에서 프리셋이라는 개념이 없다" 다. 사유를 같이 보낸다.
@router.get("/stcx/options")
async def stcx_options(_user: User = Depends(get_current_user)):
    """각도 프리셋 목록 — 이번 판에서는 **비어 있고, 왜 비었는지**를 함께 돌려준다."""
    return ok({
        "available": False,
        "reason": "presets_not_supported",
        "detail": "stcx 제출이 SmartTwinMCP 로 옮겨졌다 — 각도는 방향 수(num_directions)로만"
                  " 정한다. 프리셋·육면체·스윕·각도 파일은 다음 판이다.",
        "presets": [],
        "catalog": "",
    })
