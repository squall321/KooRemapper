# SRC-11 — 받을 타입 밖인데 거울에 남은 타입을 받기 상태에 「멈춘 타입」 으로 띄운다(타입 줄 표시 + problems 한 줄)
"""포털 요청서 1-1 실측(11-09) — 거울 받기가 기본 세 타입만 돌고 나머지 32 타입은 10-28 에 받은 그대로였는데, 받기 상태는 모두
`ok` 로 보였다. 타입 줄의 `last_status` 는 마지막 실행의 기록이라 고치지 않고 `stopped` 표시와 `problems` 를 따로 단다.
기본 받을 타입(셋)은 그대로다 — 넓히는 것은 박스 설정(BOX-01)이다.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
import ulid
from sqlalchemy import delete

from app.models import OntoSyncState, User
from app.modules.ontology.routes import require_ontology
from app.shared import security
from app.worker import plm_sync

_aio = pytest.mark.asyncio(loop_scope="session")

P = "/api/v1"
DEFAULT = "plm_project,plm_task,plm_model"


def test_the_default_receive_list_is_unchanged():
    from app.config import Settings
    assert Settings.model_fields["sp_core_types"].default == DEFAULT, "기본 받을 타입은 셋 그대로다(넓히는 것은 박스 설정)"


def test_a_type_outside_the_list_is_stopped(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "sp_core_types", DEFAULT)
    got = plm_sync.stopped_types(["plm_task", "failure_mode", "plm_model", "cause"], opened={"plm_task", "failure_mode"})
    assert got == {"failure_mode": "not_in_list", "cause": "not_in_list"}, "목록이 있으면 카탈로그와 상관없이 목록 밖이 멈춘 것이다"


def test_with_an_empty_list_a_type_the_hub_no_longer_publishes_is_stopped(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "sp_core_types", "")
    assert plm_sync.stopped_types(["plm_task", "old_type"], opened={"plm_task"}) == {"old_type": "not_published"}
    assert plm_sync.stopped_types(["plm_task", "old_type"], opened=None) == {}, "카탈로그를 모르면 짐작하지 않는다"


async def _user(db):
    u = User(email=f"stop_{ulid.new().str}@kooremapper.test", password_hash=security.hash_password("x"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@_aio
async def test_the_sync_state_flags_a_stopped_type_and_says_so(db, monkeypatch):
    from app.config import settings
    from app.main import create_app
    tag = ulid.new().str.lower()
    # 이름은 앞에 오게 — 줄의 이름 목록은 앞 12개만 적는다(실제 거울이 있는 박스에서도 이 시험의 타입이 보이게)
    inside, outside = f"a0_in_{tag}", f"a0_out_{tag}"
    monkeypatch.setattr(settings, "sp_core_types", f"{DEFAULT},{inside}")
    then = datetime(2026, 10, 28, 3, 0, tzinfo=timezone.utc)
    for slug in (inside, outside):
        db.add(OntoSyncState(type_slug=slug, objects_as_of="T1", last_run_at=then, last_status="ok"))
    await db.commit()
    u = await _user(db)
    try:
        app = create_app()
        app.dependency_overrides[require_ontology] = lambda: {"enabled": True, "reason": None}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                     base_url="http://test") as c:
            r = await c.get(f"{P}/ontology/sync",
                            headers={"authorization": f"Bearer {security.create_access_token(u.id)}"})
        assert r.status_code == 200, r.text[:300]
        d = r.json()["data"]
        rows = {t["type_slug"]: t for t in d["types"]}
        assert rows[outside]["stopped"] is True and rows[outside]["stopped_why"] == "not_in_list"
        assert rows[outside]["last_status"] == "ok", "상태 칸은 마지막 실행의 기록 그대로다"
        assert rows[inside]["stopped"] is False and rows[inside]["stopped_why"] is None
        assert outside in d["stopped_types"] and inside not in d["stopped_types"]
        assert d["receive_types"] == [*DEFAULT.split(","), inside]
        lines = [p for p in d["problems"] if p.startswith("멈춘 타입")]
        assert len(lines) == 1, d["problems"]
        assert outside in lines[0] and "KOORM_SP_CORE_TYPES" in lines[0] and "마지막으로 받은 때" in lines[0], lines[0]
        assert inside not in lines[0].split("그대로다): ", 1)[1], "받을 타입은 멈춘 타입 이름에 들지 않는다"
    finally:
        await db.execute(delete(OntoSyncState).where(OntoSyncState.type_slug.in_([inside, outside])))
        await db.execute(delete(User).where(User.id == u.id))
        await db.commit()
