# /api/health 가 DB 를 본다 — 죽었으면 503 · database.ok=false, 칸 이름은 그대로(HWAX 포털 수정 제안서 K1 ③, 2026-10-18)
"""왜 — 10-17 09:32 ~ 10-18 03:53 DynaForge DB(postgres :5436)가 꺼진 채 18시간이었는데 /api/health 가 DB 를 안 봐서 200 이었다.
감독자 · 게이트웨이 · 포털 update-all 의 헬스게이트가 못 잡았고, 그동안 사람별 로그인(/api/v1/auth/sso)이 500(ConnectionRefusedError, 31건)
이었다. 인증 없이 열리는 엔드포인트라 예외 이름만 싣는다.
"""
import asyncio
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import Response  # noqa: E402

import app.main as m  # noqa: E402


def _call(monkeypatch, ping):
    async def _p():
        return ping
    monkeypatch.setattr(m, "_db_ping", _p)
    app = m.create_app()
    route = next(r for r in app.routes if getattr(r, "path", None) == "/api/health")
    resp = Response()
    body = asyncio.run(route.endpoint(response=resp))
    return resp.status_code, body


def test_DB_가_살면_200_이고_칸은_그대로다(monkeypatch):
    code, body = _call(monkeypatch, {"ok": True})
    assert code == 200 and body["success"] is True
    d = body["data"]
    assert d["status"] == "ok" and d["database"] == {"ok": True}
    for k in ("env", "name", "binary_present", "gmsh"):
        assert k in d, k


def test_DB_가_죽으면_503_이고_예외_이름만_싣는다(monkeypatch):
    code, body = _call(monkeypatch, {"ok": False, "error": "ConnectionRefusedError"})
    assert code == 503 and body["success"] is False and body["data"]["status"] == "degraded"
    assert body["data"]["database"] == {"ok": False, "error": "ConnectionRefusedError"}
    assert body["message"] == "database 가 응답하지 않는다"


def test_핑은_닿지_않는_DB_에서_한도_안에_실패로_답한다(monkeypatch):
    """실제 _db_ping — 닫힌 포트의 DB 는 예외 이름으로 ok=False(헬스가 매달리지 않는다)."""
    import app.database as dbm
    from sqlalchemy.ext.asyncio import create_async_engine

    eng = create_async_engine("postgresql+asyncpg://u:p@127.0.0.1:1/x")
    monkeypatch.setattr(dbm, "engine", eng)
    monkeypatch.setattr(m, "_DB_PING_TIMEOUT_S", 5.0)
    got = asyncio.run(m._db_ping())
    assert got["ok"] is False and got["error"], got
