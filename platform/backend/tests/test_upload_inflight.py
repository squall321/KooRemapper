# 진행 중 올리기 수 — multipart 요청이 도는 동안만 세고, 끝나면(예외 포함) 줄며, /api/health 에 실린다
"""운영 11-26 · 사용자 결정 「수를 보이고 재기동이 기다린다」 — stop · 재기동 스크립트가 이 수가 0 이 될 때까지 기다린다
(`_common.sh` 의 `wait_uploads_drained` — 스크립트 쪽은 test_deploy_r04_1125.py ④)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
from fastapi import FastAPI, Request

from app.shared import inflight
from app.shared.inflight import UploadCounter, uploads_in_flight

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _app(gate: asyncio.Event, seen: list):
    app = FastAPI()
    app.add_middleware(UploadCounter)

    @app.post("/up")
    async def up(request: Request):
        await request.body()
        seen.append(uploads_in_flight())
        await gate.wait()
        return {"ok": True}

    @app.post("/boom")
    async def boom(request: Request):
        await request.body()
        seen.append(uploads_in_flight())
        raise RuntimeError("처리 중 깨짐")

    @app.post("/json")
    async def as_json(request: Request):
        await request.body()
        seen.append(uploads_in_flight())
        return {"ok": True}
    return app


async def test_a_multipart_upload_is_counted_only_while_it_runs():
    gate, seen = asyncio.Event(), []
    base = uploads_in_flight()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(gate, seen)), base_url="http://t") as c:
        job = asyncio.create_task(c.post("/up", files={"f": ("a.k", b"*KEYWORD\n" * 1000)}))
        for _ in range(100):
            if seen:
                break
            await asyncio.sleep(0.01)
        assert seen == [base + 1] and uploads_in_flight() == base + 1, "도는 동안 세지 않았다"
        gate.set()
        assert (await job).status_code == 200
    assert uploads_in_flight() == base, "끝난 뒤 줄지 않았다"


async def test_a_failing_upload_is_still_uncounted_and_json_is_not_counted():
    gate, seen = asyncio.Event(), []
    base = uploads_in_flight()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(gate, seen), raise_app_exceptions=False),
                                 base_url="http://t") as c:
        r = await c.post("/boom", files={"f": ("a.k", b"x")})
        assert r.status_code == 500
        assert uploads_in_flight() == base, "예외로 끝난 올리기가 수에 남았다 — 재기동이 영영 기다린다"
        await c.post("/json", json={"a": 1})
    assert seen == [base + 1, base], "multipart 가 아닌 요청을 셌다"


def test_only_multipart_bodies_are_uploads():
    def scope(method, ctype):
        return {"type": "http", "method": method, "headers": [(b"content-type", ctype)]}
    assert inflight._is_upload(scope("POST", b"multipart/form-data; boundary=x"))
    assert inflight._is_upload(scope("PUT", b"Multipart/Form-Data; boundary=x"))
    assert not inflight._is_upload(scope("GET", b"multipart/form-data"))
    assert not inflight._is_upload(scope("POST", b"application/json"))
    assert not inflight._is_upload({"type": "http", "method": "POST", "headers": []})


async def test_health_carries_the_count(db):
    from app.main import create_app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t") as c:
        body = (await c.get("/api/health")).json()
    assert body["data"]["uploads_in_flight"] == uploads_in_flight()
