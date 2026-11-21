# 리포트 받기가 한 번에 하나만 도는지 — 동시에 온 올리기의 풀린 데이터가 곱해지지 않게 세운 줄의 계약
"""리포트 받기 줄(계획 docs/01-plan/features/df-campaign-intake-1120.plan.md 9절 · 2026-11-20).

리포트를 풀면 파일의 약 8 배를 쓴다. 상한은 그대로 두고 받기를 한 번에 하나로 세웠다 — 이 파일은 그 줄이 서 있는지만 본다
(DB 를 쓰지 않는다). 잠금은 시험마다 새로 갈아 끼운다(모듈의 잠금을 이 시험의 루프에 묶지 않는다).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.reports import services as svc  # noqa: E402

_aio = pytest.mark.asyncio(loop_scope="session")


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
    got = await asyncio.gather(
        svc.ingest_report("db", "s", filename="a.html", raw=b"1", campaign_run_id=7),
        svc.ingest_report("db", "s", filename="bad.html", raw=b"2"),
        svc.ingest_report("db", "s", filename="c.html", raw=b"3"),
        return_exceptions=True,
    )
    assert peak == 1, f"받기가 {peak} 건 겹쳤다"
    assert got[0] == "a.html" and isinstance(got[1], ValueError) and got[2] == "c.html"
    assert seen[0] == {"db": "db", "session": "s", "filename": "a.html", "raw": b"1", "campaign_run_id": 7}
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
    assert held == [True, False], held      # 풀 때는 줄 안 · 커밋 때는 줄 밖
    assert summary["n_stored"] == 0 and report.media == []
