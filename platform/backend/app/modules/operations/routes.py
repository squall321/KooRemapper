"""Operation catalog API — what KooRemapper can do + each op's arg schema.

Read-only and not user-specific, but still requires auth (consistent surface).
Feeds the frontend catalog browser / auto-form and the MCP describe_operation tool.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import User
from app.runner import catalog
from app.runner.stcx_client import StcxClient, parse_presets
from app.config import settings
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


# 각도 프리셋 목록은 **서버가 들고 있다.** 여기 박아 두면 클러스터에 프리셋이 늘어도
# 화면에는 안 보이고, 사용자는 있는 것을 못 쓴다. 그래서 물어서 그대로 보여 준다.
@router.get("/stcx/options")
async def stcx_options(_user: User = Depends(get_current_user)):
    """stcx 전각도 낙하의 옵션 카탈로그(원문) + 고를 수 있는 각도 프리셋.

    게이트웨이가 안 닿거나 PAT 가 없으면 **빈 목록이 아니라 사유를 돌려준다** — 빈 목록은
    "프리셋이 없다" 처럼 보이는데, 실제로는 물어보지도 못한 것이다.
    """
    client = StcxClient(settings.gateway_mcp, settings.gateway_pat)
    try:
        res = await client.scenario_options("fullangle_drop")
    finally:
        await client.close()
    if not res.get("ok"):
        return ok({"available": False, "reason": res.get("error"),
                   "detail": str(res.get("detail"))[:300], "presets": [], "catalog": ""})
    raw = res.get("result")
    text = raw if isinstance(raw, str) else str((raw or {}).get("result", "") if isinstance(raw, dict) else raw)
    return ok({"available": True, "presets": parse_presets(raw), "catalog": text})
