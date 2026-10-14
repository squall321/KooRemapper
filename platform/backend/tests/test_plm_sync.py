"""기준정보 주기 수신의 배선 — **꺼져 있는 것이 기본**이고, 꺼짐이 조용한 성공이 아니다.

허브가 아직 없다(계획서 §7 ②). 그래서 기본이 꺼짐이고, 꺼져 있을 때 **아무것도 부르지
않는다.** 없는 곳을 주기적으로 두드리면 로그가 실패로 가득 차고 **진짜 실패가 그 속에
묻힌다** — 그 상태가 가장 비싸다.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
import ulid
from sqlalchemy import delete, select

from app.models import OntoObject, OntoRelation, OntoSyncState
from app.runner.sp_core import SpCoreClient
from app.worker import plm_sync

pytestmark = pytest.mark.asyncio(loop_scope="session")

_RUNNER = Path(__file__).resolve().parents[1] / "app" / "worker" / "runner_loop.py"


@pytest.fixture()
def on(monkeypatch):
    """설정 셋을 채워 켜 둔다."""
    from app.config import settings
    monkeypatch.setattr(settings, "sp_core_url", "http://hub.test/api")
    monkeypatch.setattr(settings, "sp_core_token", "tok")
    monkeypatch.setattr(settings, "sp_core_sync_sec", 600)
    return settings


async def test_it_is_off_by_default():
    """허브 주소를 코드에 박지 않았으므로 **기본은 꺼짐**이다."""
    from app.config import settings
    assert settings.sp_core_sync_sec == 0
    assert settings.sp_core_url == "" and settings.sp_core_token == ""


@pytest.mark.parametrize("blank", ["sp_core_url", "sp_core_token", "sp_core_sync_sec"])
async def test_one_blank_setting_turns_it_off(monkeypatch, on, blank):
    """셋 중 **하나라도** 비면 꺼진 것이다 — 반쪽으로 돌면 "받았는데 비어 있다" 가 된다."""
    monkeypatch.setattr(on, blank, 0 if blank.endswith("_sec") else "")
    assert plm_sync.enabled() is False


async def test_when_enabled_it_says_so(on):
    assert plm_sync.enabled() is True


async def test_being_off_is_an_explicit_failure_not_a_quiet_success():
    assert plm_sync.enabled() is False
    got = await plm_sync.sync_once()
    assert got["ok"] is False and got["error"] == "disabled"


async def test_the_type_list_is_not_hardcoded():
    """목록을 박으면 허브에 타입이 늘어도 우리를 고쳐야 한다 — 공개된 것 전부를 받는다."""
    assert plm_sync.wanted_types() is None


async def test_sync_once_writes_and_commits(db, on):
    """받은 것은 **커밋한다** — 성공한 타입은 남아야 한다."""
    slug = f"t_{ulid.new().str[:12].lower()}"
    cat = {"system": "허브", "revision": "r1", "as_of": "T0",
           "types": [{"slug": slug, "label": "과제", "count": 1, "properties": [],
                      "endpoint": f"/core/{slug}", "relations": []}]}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/core"):
            return httpx.Response(200, json=cat)
        return httpx.Response(200, json={"items": [
            {"key": "PRJ-1", "label": "과제 하나", "status": "active",
             "updated_at": "T1", "deleted": False}], "as_of": "T1", "next": None})

    client = SpCoreClient("http://hub.test/api", "tok",
                          client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    try:
        got = await plm_sync.sync_once(client=client)
        assert got["ok"], got
        # **다른 세션**에서 보인다 = 정말 커밋됐다
        rows = (await db.execute(select(OntoObject).where(
            OntoObject.type_slug == slug))).scalars().all()
        assert [r.key for r in rows] == ["PRJ-1"]
    finally:
        await db.execute(delete(OntoObject).where(OntoObject.type_slug == slug))
        await db.execute(delete(OntoSyncState).where(OntoSyncState.type_slug == slug))
        await db.commit()


# ── 배선이 지워지지 않게 ───────────────────────────────────────────────────

async def test_the_worker_still_calls_it():
    """한 줄짜리 배선이라 조용히 사라질 수 있다 — 사라지면 수신이 **영원히 안 돈다.**"""
    text = _RUNNER.read_text(encoding="utf-8")
    assert "plm_sync.enabled()" in text, "게이트가 없다"
    assert "plm_sync.sync_once()" in text, "호출이 없다"
    assert "max(60, settings.sp_core_sync_sec)" in text, "간격 하한이 없다 — 1초로 두드릴 수 있다"


# ── S1-7 — 부서는 **거울이 아니라 선의 끝점**이다 ──────────────────────────

async def test_a_relation_to_a_system_type_never_creates_an_object_row(db, on):
    """★부서를 `onto_objects` 에 복제하면 **두 벌이 되고 반드시 갈린다**(SP §3.6).

    DynaForge 의 소속 정본은 **포탈**이다 — 게이트웨이가 HMAC 로 서명한
    `X-Heax-User-Affiliation` 을 `shared/affiliation.py` 가 검증하고
    `shared/visibility.py` 가 판정한다. 그래서 받은 선의 **먼 끝은 행을 만들지 않는다**
    (SP 의 `object_links` 와 같은 자리 — 한쪽 끝이 `objects` 밖이다).
    """
    slug = f"t_{ulid.new().str[:12].lower()}"
    cat = {"system": "허브", "revision": "r1", "as_of": "T0",
           "types": [{"slug": slug, "label": "과제", "count": 1, "properties": [],
                      "endpoint": f"/core/{slug}", "relations": ["dept_in_charge"]}]}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/core"):
            return httpx.Response(200, json=cat)
        if path.endswith("/relations"):
            return httpx.Response(200, json={"items": [
                {"src": "PRJ-1", "relation": "dept_in_charge",
                 "dst": "CAEG", "dst_type": "workspace"}], "as_of": "T1", "next": None})
        return httpx.Response(200, json={"items": [
            {"key": "PRJ-1", "label": "과제 하나", "updated_at": "T1"}],
            "as_of": "T1", "next": None})

    client = SpCoreClient("http://hub.test/api", "tok",
                          client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    try:
        got = await plm_sync.sync_once(client=client)
        assert got["ok"], got
        edges = (await db.execute(select(OntoRelation).where(
            OntoRelation.src_type == slug))).scalars().all()
        assert len(edges) == 1 and edges[0].dst_key == "CAEG", "선이 안 들어왔다"
        assert edges[0].dst_type == "workspace"
        # ★행은 **없어야** 한다
        made = (await db.execute(select(OntoObject).where(
            OntoObject.type_slug == "workspace"))).scalars().all()
        assert made == [], f"부서를 행으로 복제했다: {[m.key for m in made]}"
    finally:
        await db.execute(delete(OntoRelation).where(OntoRelation.src_type == slug))
        await db.execute(delete(OntoObject).where(OntoObject.type_slug == slug))
        await db.execute(delete(OntoSyncState).where(OntoSyncState.type_slug == slug))
        await db.commit()
