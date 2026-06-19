"""System status + capabilities — powers the frontend status/parity view and the
MCP system tools. Shows what's healthy and what web/MCP each support."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Job, User
from app.runner import catalog
from app.shared.auth import get_current_user
from app.shared.responses import ok

router = APIRouter(tags=["system"])

APP_VERSION = "0.1.0"


def _gmsh_available() -> bool:
    # next to the binary (findGmshExe convention) or on PATH
    bindir = settings.kooremapper_bin.parent
    for c in (bindir / "gmsh" / "gmsh.exe", bindir / "gmsh" / "gmsh"):
        if c.exists():
            return True
    return shutil.which("gmsh") is not None


@router.get("/system/status")
async def system_status(_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    db_ok = True
    queued = running = 0
    try:
        await db.execute(text("SELECT 1"))
        queued = (await db.execute(select(func.count(Job.id)).where(Job.status == "queued"))).scalar_one()
        running = (await db.execute(select(func.count(Job.id)).where(Job.status == "running"))).scalar_one()
    except Exception:
        db_ok = False
    return ok({
        "version": APP_VERSION,
        "env": settings.app_env,
        "api": {"ok": True, "port": settings.api_port},
        "database": {"ok": db_ok, "port": None},
        "worker": {"concurrency": settings.worker_concurrency, "queued": queued, "running": running},
        "binary": {"present": settings.kooremapper_bin.exists(), "path": str(settings.kooremapper_bin)},
        "gmsh": {"available": _gmsh_available(), "note": "meshfix 전용"},
        "mcp": {"port": settings.mcp_port, "url": f"http://<host>:{settings.mcp_port}/mcp"},
        "rate_limit": {"enabled": settings.ratelimit_enabled},
        "signup": {"enabled": settings.allow_signup},
        "operations": len(catalog.operation_names()),
    })


# Capability parity matrix: which features are reachable via web and via MCP.
_PARITY = [
    {"feature": "세션 관리", "web": True, "mcp": True},
    {"feature": "파일 업로드/조회/다운로드", "web": True, "mcp": True, "note": "MCP는 로컬경로 업로드도 지원"},
    {"feature": "오퍼레이션 카탈로그/옵션", "web": True, "mcp": True},
    {"feature": "오퍼레이션 실행/Job/로그/취소", "web": True, "mcp": True},
    {"feature": "내 정보(whoami)", "web": True, "mcp": True},
    {"feature": "시스템 상태", "web": True, "mcp": True},
    {"feature": "MCP 토큰 발급", "web": True, "mcp": False, "note": "보안상 웹 전용"},
    {"feature": "사용자 관리(admin)", "web": True, "mcp": False},
]


@router.get("/system/capabilities")
async def capabilities(_user: User = Depends(get_current_user)):
    return ok({
        "operations": len(catalog.operation_names()),
        "mcp_tools": 20,
        "parity": _PARITY,
        "mcp_add_hint": (
            f"claude mcp add --transport http kooremapper "
            f"http://<host>:{settings.mcp_port}/mcp --header \"Authorization: Bearer kr_...\""
        ),
        "mcp_desktop_hint": "Claude Desktop은 mcp-remote 브리지 사용 (mcp_server/CLAUDE_DESKTOP.md)",
    })
