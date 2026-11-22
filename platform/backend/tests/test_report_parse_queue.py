# 리포트 받기가 한 번에 하나만 도는지 — 동시에 온 올리기의 풀린 데이터가 곱해지지 않게 세운 줄의 계약
"""리포트 받기 줄(계획 docs/01-plan/features/df-campaign-intake-1120.plan.md 9절 · 2026-11-20).

리포트를 풀면 파일의 약 8 배를 쓴다. 상한은 그대로 두고 받기를 한 번에 하나로 세웠다 — 이 파일은 그 줄이 서 있는지 본다.
잠금은 시험마다 새로 갈아 끼운다(모듈의 잠금을 이 시험의 루프에 묶지 않는다).

줄에 선 올리기가 DB 연결을 쥔 채 기다리면 동시 40 건에서 풀이 말라 500 이 났다(11-20 · 23 건). 이제 라우트 길은 줄에 서기 전에
커밋해 연결을 놓고, 워커의 후처리 반입 길은 잡 원장과 리포트가 한 커밋이어야 해서 커밋하지 않는다(계획
docs/01-plan/features/df-provenance-health-1122.plan.md 5절). 연결 시험만 DB 를 쓴다.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.reports import services as svc  # noqa: E402

_aio = pytest.mark.asyncio(loop_scope="session")


class _FakeDb:
    """커밋 부름을 잠금 상태와 함께 적는다."""

    def __init__(self, lock_ref):
        self.commits: list[bool] = []
        self._lock_ref = lock_ref

    async def commit(self):
        self.commits.append(self._lock_ref().locked())


@_aio
async def test_ingest_runs_one_at_a_time_and_frees_the_line_on_error(monkeypatch):
    """동시에 부른 받기 셋이 겹치지 않고, 하나가 실패해도 뒤의 것이 돈다. 인자는 안쪽 함수에 그대로 간다."""
    monkeypatch.setattr(svc, "_PARSE_LOCK", asyncio.Lock())
    active = peak = 0
    seen: list[dict] = []

    async def fake(db, session, **kw):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        seen.append({"db": db, "session": session, **kw})
        await asyncio.sleep(0.02)          # 파싱 자리 — 여기서 다른 받기가 끼어들 수 있어야 시험이 뜻이 있다
        active -= 1
        if kw["filename"] == "bad.html":
            raise ValueError("케이스 없음")
        return kw["filename"]

    monkeypatch.setattr(svc, "_ingest_report", fake)
    db = _FakeDb(lambda: svc._PARSE_LOCK)
    got = await asyncio.gather(
        svc.ingest_report(db, "s", filename="a.html", raw=b"1", campaign_run_id=7),
        svc.ingest_report(db, "s", filename="bad.html", raw=b"2"),
        svc.ingest_report(db, "s", filename="c.html", raw=b"3"),
        return_exceptions=True,
    )
    assert peak == 1, f"받기가 {peak} 건 겹쳤다"
    assert got[0] == "a.html" and isinstance(got[1], ValueError) and got[2] == "c.html"
    assert seen[0] == {"db": db, "session": "s", "filename": "a.html", "raw": b"1", "campaign_run_id": 7}
    assert len(db.commits) == 3          # 셋 다 줄에 서기 전에 커밋했다(연결을 놓는다)
    assert not svc._PARSE_LOCK.locked()


@_aio
async def test_attach_media_parses_inside_the_line(monkeypatch):
    """미디어 붙이기도 리포트를 통째로 푼다 — 받기와 같은 줄 안에서 풀고, 풀고 나면 줄을 놓는다."""
    monkeypatch.setattr(svc, "_PARSE_LOCK", asyncio.Lock())
    held: list[bool] = []

    def fake_extract(text):
        held.append(svc._PARSE_LOCK.locked())
        return {}

    monkeypatch.setattr(svc.parser, "extract_embedded_data", fake_extract)
    monkeypatch.setattr(svc.parser, "report_media_map",
                        lambda data, kind: {"declared": [], "n_declared": 0, "n_empty_slots": 0})

    class _Db:
        async def commit(self):
            held.append(svc._PARSE_LOCK.locked())

    report = SimpleNamespace(kind="impact", media=None)
    summary = await svc.attach_media(_Db(), None, report, media=[], html=b"<html></html>")
    assert held == [False, True, False], held      # 줄 앞 커밋(연결을 놓는다) · 풀 때는 줄 안 · 끝 커밋은 줄 밖
    assert summary["n_stored"] == 0 and report.media == []


@_aio
async def test_worker_path_keeps_its_transaction(monkeypatch):
    """워커는 잡 원장을 고친 채 부르고 리포트와 한 커밋으로 굳힌다 — 줄 앞에서 커밋하지 않는다. 라우트 길(기본)은 커밋한다."""
    monkeypatch.setattr(svc, "_PARSE_LOCK", asyncio.Lock())

    async def fake(db, session, **kw):
        assert "keep_transaction" not in kw          # 안쪽 함수로는 넘기지 않는다
        return kw["filename"]

    monkeypatch.setattr(svc, "_ingest_report", fake)
    db = _FakeDb(lambda: svc._PARSE_LOCK)
    assert await svc.ingest_report(db, "s", filename="w.html", raw=b"1", keep_transaction=True) == "w.html"
    assert db.commits == []
    assert await svc.ingest_report(db, "s", filename="r.html", raw=b"1") == "r.html"
    assert db.commits == [False]


@_aio
async def test_waiting_upload_does_not_hold_a_db_connection(monkeypatch):
    """줄을 남이 쥔 동안 기다리는 받기는 풀의 연결을 빌려 두지 않는다 — 예전엔 기다리는 수만큼 연결이 묶여 풀이 말랐다."""
    from app.database import SessionLocal, engine

    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"DB unavailable: {exc}")
    pool = engine.sync_engine.pool
    monkeypatch.setattr(svc, "_PARSE_LOCK", asyncio.Lock())
    done = asyncio.Event()

    async def fake(db, session, **kw):
        await db.execute(text("SELECT 1"))          # 줄 안에서는 다시 빌린다
        done.set()
        return "ok"

    monkeypatch.setattr(svc, "_ingest_report", fake)
    await svc._PARSE_LOCK.acquire()                 # 남이 받는 중
    try:
        base = pool.checkedout()
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))      # 라우트가 사용자 · 세션을 읽어 연결을 빌린 상태
            assert pool.checkedout() == base + 1
            task = asyncio.create_task(svc.ingest_report(db, "s", filename="a.html", raw=b"1"))
            for _ in range(50):
                await asyncio.sleep(0.01)
                if pool.checkedout() == base:
                    break
            assert pool.checkedout() == base, "줄을 기다리는 받기가 연결을 쥐고 있다"
            assert not task.done()
            svc._PARSE_LOCK.release()
            assert await asyncio.wait_for(task, 10) == "ok" and done.is_set()
    finally:
        if svc._PARSE_LOCK.locked():
            svc._PARSE_LOCK.release()
