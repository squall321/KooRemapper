"""SP 코어 수신 — **규칙 열하나를 전수로** 고정한다(가짜 허브, 망 없음).

규칙의 정본은 `external/StandardPlatform/docs/외부-시스템-연동-지침서.md` §4.2
(머리 186행 · 규칙 311~343행)@f7485c0 다. 번호를 시험 이름에 그대로 달아 둔다 — 한 줄을
고칠 때 무엇을 깨는지 보이게.

이 파일이 지키는 것의 성질은 하나다 — **빈 것·안 온 것·모르는 것을 「없다」 로 읽지 않는다.**
그 셋을 잘못 접으면 허브에서 지워진 과제가 우리 쪽에 영원히 살거나, 멀쩡한 과제가 조용히
사라진다. 둘 다 몇 달 뒤에 발견된다.

★`renamed_from`(규칙 4) 은 **수신 키트에 구현이 없다**(`ENVELOPE` 에도 없다) — 규칙이
요구하므로 우리가 채웠고, 여기서 고정한다.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
import ulid
from sqlalchemy import delete, select

from app.models import SOURCE_HUB, OntoObject, OntoRelation, OntoSyncState
from app.runner.sp_core import NOT_PUBLISHED, SpCoreClient, sync_all, sync_type

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _Hub:
    """가짜 허브. `/core` 카탈로그와 `/core/{type}` 쪽들을 **적힌 순서대로** 낸다."""

    def __init__(self, *, pages=None, relations=None, catalog=None,
                 fail=None, code=""):
        self.pages = list(pages or [])
        self.relations = list(relations or [])
        self.catalog_body = catalog
        self.fail = fail                 # (status, code) — 쪽 요청을 거절한다
        self.code = code
        self.asked: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.asked.append({"path": path, "params": dict(request.url.params)})
        if path.endswith("/core"):
            return httpx.Response(200, json=self.catalog_body or {
                "system": "테스트허브", "revision": "r1", "as_of": "T0",
                "types": [{"slug": "plm_task", "label": "과제", "count": 0,
                           "properties": [], "endpoint": "/core/plm_task",
                           "relations": []}]})
        if path.endswith("/relations"):
            return httpx.Response(200, json=self.relations.pop(0) if self.relations
                                  else {"items": [], "as_of": "T1", "next": None})
        if self.fail:
            status, code = self.fail
            return httpx.Response(status, json={"error": {"code": code, "message": "거절"}})
        if not self.pages:
            return httpx.Response(200, json={"items": [], "as_of": "T1", "next": None})
        return httpx.Response(200, json=self.pages.pop(0))


def _client(hub: _Hub, *, token="tok") -> SpCoreClient:
    return SpCoreClient("http://hub.test/api", token,
                        client=httpx.AsyncClient(transport=httpx.MockTransport(hub.handler)))


def _row(key, **kw):
    out = {"key": key, "label": kw.pop("label", f"이름-{key}"), "status": "active",
           "updated_at": "2026-10-14T00:00:00Z", "deleted": False, "hidden": False}
    out.update(kw)
    return out


def _page(items, *, as_of="T1", next_=None, **kw):
    return {"type_slug": "x", "items": items, "as_of": as_of, "next": next_, **kw}


@pytest.fixture()
def slug():
    """시험마다 고유한 타입 slug — 개발 DB 를 공유하므로 서로를 밟지 않는다."""
    return f"t_{ulid.new().str[:12].lower()}"


async def _cleanup(db, slug):
    await db.execute(delete(OntoObject).where(OntoObject.type_slug == slug))
    await db.execute(delete(OntoRelation).where(OntoRelation.src_type == slug))
    await db.execute(delete(OntoSyncState).where(OntoSyncState.type_slug == slug))
    await db.commit()


async def _objects(db, slug):
    return {o.key: o for o in (await db.execute(
        select(OntoObject).where(OntoObject.type_slug == slug))).scalars()}


# ── 규칙 1·2 — 시계 ─────────────────────────────────────────────────────────

async def test_rule1_the_server_clock_is_stored_verbatim(db, slug):
    """우리 시계로 만들면 몇 초 차이로 **그 사이 행이 샌다.**"""
    hub = _Hub(pages=[_page([_row("A")], as_of="2026-10-14T01:02:03.456789Z")])
    try:
        got = await sync_type(db, _client(hub), slug)
        await db.commit()
        assert got["ok"] and got["rows"] == 1
        state = await db.get(OntoSyncState, slug)
        assert state.objects_as_of == "2026-10-14T01:02:03.456789Z"
        # 다음 동기화는 그 값을 `since` 로 **그대로** 보낸다
        hub2 = _Hub(pages=[_page([], as_of="T2")])
        await sync_type(db, _client(hub2), slug)
        page_asks = [a for a in hub2.asked if a["path"].endswith(slug)]
        assert page_asks[0]["params"]["since"] == "2026-10-14T01:02:03.456789Z"
    finally:
        await _cleanup(db, slug)


async def test_rule2_the_clock_does_not_move_while_pages_remain(db, slug):
    """★쪽이 남았는데 시계를 옮기면 **남은 쪽을 영영 안 받는다.**"""
    hub = _Hub(pages=[_page([_row("A")], as_of=None, next_="c1"),
                      _page([_row("B")], as_of="TEND", next_=None)])
    try:
        got = await sync_type(db, _client(hub), slug)
        await db.commit()
        assert got["pages"] == 2 and got["rows"] == 2
        assert (await db.get(OntoSyncState, slug)).objects_as_of == "TEND"
        assert set(await _objects(db, slug)) == {"A", "B"}
    finally:
        await _cleanup(db, slug)


async def test_rule2_a_half_received_sync_keeps_the_old_clock(db, slug):
    """중간 쪽에서 끊기면 시계가 **안 움직인다** — 다음에 처음부터 다시 받는다."""
    first = _Hub(pages=[_page([_row("A")], as_of="T1", next_=None)])
    try:
        await sync_type(db, _client(first), slug)
        await db.commit()
        # 두 번째 동기화가 쪽을 남긴 채 실패한다
        broken = _Hub(pages=[_page([_row("B")], as_of=None, next_="c1")], fail=(500, ""))
        broken.pages = [_page([_row("B")], as_of=None, next_="c1")]
        got = await sync_type(db, _client(broken), slug)
        await db.commit()
        assert got["ok"] is False
        assert (await db.get(OntoSyncState, slug)).objects_as_of == "T1", "시계가 움직였다"
    finally:
        await _cleanup(db, slug)


# ── 규칙 3 — key 가 정체성 ──────────────────────────────────────────────────

async def test_rule3_the_second_sync_updates_instead_of_creating(db, slug):
    hub1 = _Hub(pages=[_page([_row("A", label="처음")])])
    hub2 = _Hub(pages=[_page([_row("A", label="나중")], as_of="T2")])
    try:
        await sync_type(db, _client(hub1), slug)
        await sync_type(db, _client(hub2), slug)
        await db.commit()
        objs = await _objects(db, slug)
        assert len(objs) == 1, "같은 key 가 둘이 됐다"
        assert objs["A"].label == "나중"
        assert objs["A"].source == SOURCE_HUB
    finally:
        await _cleanup(db, slug)


# ── 규칙 4 — deleted · merged_into · renamed_from · hidden ──────────────────

async def test_rule4_deleted_is_marked_not_removed(db, slug):
    """지우면 **우리 선이 끊긴 채 조용히 남는다.**"""
    try:
        await sync_type(db, _client(_Hub(pages=[_page([_row("A")])])), slug)
        await sync_type(db, _client(_Hub(pages=[_page([_row("A", deleted=True)], as_of="T2")])), slug)
        await db.commit()
        objs = await _objects(db, slug)
        assert "A" in objs and objs["A"].deleted is True
    finally:
        await _cleanup(db, slug)


async def test_rule4_merged_into_is_recorded_so_we_can_move_our_refs(db, slug):
    try:
        await sync_type(db, _client(_Hub(pages=[
            _page([_row("LOSER", deleted=True, merged_into="WINNER"), _row("WINNER")])])), slug)
        await db.commit()
        objs = await _objects(db, slug)
        assert objs["LOSER"].merged_into == "WINNER"
    finally:
        await _cleanup(db, slug)


async def test_rule4_renamed_from_moves_the_key_instead_of_making_a_twin(db, slug):
    """★**키트에 없는 처리다.** 없으면 새 식별자가 처음 보는 것이라 **같은 것이 둘이 된다** —
    옛 행은 아무도 안 지우므로 검색·집계에 두 번 센다."""
    try:
        await sync_type(db, _client(_Hub(pages=[_page([_row("OLD", label="옛 이름")])])), slug)
        await db.commit()
        got = await sync_type(db, _client(_Hub(pages=[
            _page([_row("NEW", label="새 이름", renamed_from="OLD")], as_of="T2")])), slug)
        await db.commit()
        objs = await _objects(db, slug)
        assert set(objs) == {"NEW"}, f"개명 뒤 행이 {sorted(objs)} — 둘이 됐다"
        assert got["renamed"] == 1
        assert objs["NEW"].label == "새 이름"
        assert "OLD" in (objs["NEW"].previous_keys or []), "옛 키를 버리면 옛 번호로 못 찾는다"
    finally:
        await _cleanup(db, slug)


async def test_rule4_hidden_deactivates_but_never_creates_a_ghost(db, slug):
    """`hidden` 은 이름·칸이 **안 온다** — 없던 것을 만들면 빈 라벨의 유령 행이 화면에 뜬다."""
    try:
        await sync_type(db, _client(_Hub(pages=[_page([_row("A")])])), slug)
        await db.commit()
        await sync_type(db, _client(_Hub(pages=[_page(
            [{"key": "A", "hidden": True, "deleted": True, "updated_at": "T2"},
             {"key": "NEVER_SEEN", "hidden": True, "deleted": True, "updated_at": "T2"}],
            as_of="T2")])), slug)
        await db.commit()
        objs = await _objects(db, slug)
        assert set(objs) == {"A"}, "안 보이게 된 것을 새로 만들었다"
        assert objs["A"].deleted is True and objs["A"].hidden is True
        assert objs["A"].label == "이름-A", "이름이 안 오는데 비웠다"
    finally:
        await _cleanup(db, slug)


# ── 규칙 5·10 — 모르는 칸 · 참조 칸 ────────────────────────────────────────

async def test_rule5_and_10_properties_are_stored_as_given(db, slug):
    """모르는 칸을 버리면 허브가 칸을 늘릴 때마다 우리를 고쳐야 한다.
    그리고 참조 칸의 값은 **보낼 때의 `key`** 다 — 풀지 않는다."""
    props = {"task_status": "진행", "project": "PRJ-1", "미래칸": [1, 2], "sra_on": True}
    try:
        await sync_type(db, _client(_Hub(pages=[_page([_row("A", properties=props)])])), slug)
        await db.commit()
        objs = await _objects(db, slug)
        assert objs["A"].properties == props
    finally:
        await _cleanup(db, slug)


# ── 규칙 6 — 같은 행 두 번 ─────────────────────────────────────────────────

async def test_rule6_the_same_row_twice_in_one_run_is_harmless(db, slug):
    """경계 시각과 긴 적재 구간에서 그렇다 — 덮어쓰면 해가 없어야 한다."""
    try:
        got = await sync_type(db, _client(_Hub(pages=[
            _page([_row("A", label="먼저"), _row("A", label="나중")])])), slug)
        await db.commit()
        assert got["ok"]
        objs = await _objects(db, slug)
        assert len(objs) == 1 and objs["A"].label == "나중"
    finally:
        await _cleanup(db, slug)


# ── 규칙 7 — 부재 대조 ─────────────────────────────────────────────────────

async def test_rule7_a_full_pull_sweeps_what_did_not_come(db, slug):
    """`since` 없이 받으면 지워진 것은 **안 온다.** 쓸어내지 않으면 허브에서 지워진 과제가
    우리 쪽에 **영원히 산다.**"""
    try:
        await sync_type(db, _client(_Hub(pages=[_page([_row("A"), _row("B")])])), slug)
        await db.commit()
        got = await sync_type(db, _client(_Hub(pages=[_page([_row("A")], as_of="T2")])),
                              slug, full=True)
        await db.commit()
        objs = await _objects(db, slug)
        assert objs["A"].deleted is False
        assert objs["B"].deleted is True, "전량에서 안 온 것을 그대로 뒀다"
        assert got["swept"] == 1
    finally:
        await _cleanup(db, slug)


async def test_rule7_an_empty_full_pull_sweeps_nothing(db, slug):
    """★전량인데 0건 — 「다 지워졌다」 와 「조회가 잘못됐다」 를 **가릴 수 없다.**
    조용히 전부 비활성으로 만들면 되돌릴 수 없으므로 아무것도 안 한다."""
    try:
        await sync_type(db, _client(_Hub(pages=[_page([_row("A"), _row("B")])])), slug)
        await db.commit()
        got = await sync_type(db, _client(_Hub(pages=[_page([], as_of="T2")])), slug, full=True)
        await db.commit()
        objs = await _objects(db, slug)
        assert got["swept"] == 0
        assert all(o.deleted is False for o in objs.values()), "빈 응답으로 전부 지웠다"
    finally:
        await _cleanup(db, slug)


async def test_rule7_an_incremental_pull_never_sweeps(db, slug):
    """증분에서는 「안 온 것」 이 「안 바뀐 것」 이다 — 쓸어내면 멀쩡한 것이 사라진다."""
    try:
        await sync_type(db, _client(_Hub(pages=[_page([_row("A"), _row("B")])])), slug)
        await db.commit()
        got = await sync_type(db, _client(_Hub(pages=[_page([_row("A")], as_of="T2")])), slug)
        await db.commit()
        assert "swept" not in got
        assert (await _objects(db, slug))["B"].deleted is False
    finally:
        await _cleanup(db, slug)


# ── 규칙 8 — 되살림 ────────────────────────────────────────────────────────

async def test_rule8_a_deleted_row_can_come_back(db, slug):
    try:
        await sync_type(db, _client(_Hub(pages=[_page([_row("A", deleted=True)])])), slug)
        await db.commit()
        assert (await _objects(db, slug))["A"].deleted is True
        await sync_type(db, _client(_Hub(pages=[_page([_row("A", deleted=False)], as_of="T2")])), slug)
        await db.commit()
        assert (await _objects(db, slug))["A"].deleted is False
    finally:
        await _cleanup(db, slug)


# ── 규칙 9 — 합쳐진 쪽의 선 ────────────────────────────────────────────────

async def test_rule9_edges_arrive_moved_to_the_winner(db, slug):
    """합치기는 진 쪽의 선을 이긴 쪽으로 **옮기므로** 새 끝점으로 다시 온다 —
    끊김을 따로 추론하지 않는다."""
    cat = {"system": "h", "revision": "r1", "as_of": "T0",
           "types": [{"slug": slug, "label": "x", "count": 0, "properties": [],
                      "endpoint": f"/core/{slug}", "relations": ["belongs_to"]}]}
    hub = _Hub(catalog=cat, pages=[_page([_row("WINNER")])],
               relations=[{"items": [{"src": "WINNER", "relation": "belongs_to",
                                      "dst": "PRJ-1", "dst_type": "plm_project"}],
                           "as_of": "T1", "next": None}])
    try:
        got = await sync_all(db, _client(hub), types=[slug])
        await db.commit()
        assert got["ok"], got
        edges = (await db.execute(select(OntoRelation).where(
            OntoRelation.src_type == slug))).scalars().all()
        assert len(edges) == 1
        assert (edges[0].src_key, edges[0].dst_key) == ("WINNER", "PRJ-1")
        assert edges[0].source == SOURCE_HUB
    finally:
        await _cleanup(db, slug)


# ── 규칙 11 — 404 는 두 가지 ───────────────────────────────────────────────

async def test_rule11_a_not_published_type_stops_instead_of_retrying(db, slug):
    """`APP-CORE-0001` 은 **고칠 곳이 다르다**(허브 관리자) — 멈추고 알린다."""
    try:
        got = await sync_type(db, _client(_Hub(fail=(404, NOT_PUBLISHED))), slug)
        await db.commit()
        assert got["ok"] is False and got["stopped"] is True
        state = await db.get(OntoSyncState, slug)
        assert state.last_status == "stopped" and NOT_PUBLISHED in (state.last_error or "")
    finally:
        await _cleanup(db, slug)


async def test_rule11_any_other_404_is_an_error_not_a_stop(db, slug):
    try:
        got = await sync_type(db, _client(_Hub(fail=(404, "SOMETHING-ELSE"))), slug)
        await db.commit()
        assert got["ok"] is False and got.get("stopped") is False
        assert (await db.get(OntoSyncState, slug)).last_status == "error"
    finally:
        await _cleanup(db, slug)


# ── reset · 꺼짐 · 공개 목록 ───────────────────────────────────────────────

async def test_a_reset_restarts_from_scratch_once(db, slug):
    try:
        await sync_type(db, _client(_Hub(pages=[_page([_row("A"), _row("B")])])), slug)
        await db.commit()
        hub = _Hub(pages=[{"reset": True, "reset_reason": "공개 범위가 바뀌었다"},
                          _page([_row("A")], as_of="T9")])
        got = await sync_type(db, _client(hub), slug)
        await db.commit()
        assert got["ok"] and got["reset"] == 1
        objs = await _objects(db, slug)
        assert objs["B"].deleted is True, "reset 뒤 전량 대조가 안 돌았다"
        assert (await db.get(OntoSyncState, slug)).last_status == "reset"
    finally:
        await _cleanup(db, slug)


async def test_a_reset_that_repeats_is_refused_instead_of_looping(db, slug):
    try:
        hub = _Hub(pages=[{"reset": True, "reset_reason": "a"}, {"reset": True, "reset_reason": "b"}])
        got = await sync_type(db, _client(hub), slug)
        await db.commit()
        assert got["ok"] is False and got["error"] == "reset_loop"
    finally:
        await _cleanup(db, slug)


async def test_without_a_token_nothing_is_called(db, slug):
    """꺼져 있는 것을 조용한 성공으로 바꾸지 않는다 — 받은 줄 알고 빈 화면을 본다."""
    hub = _Hub(pages=[_page([_row("A")])])
    try:
        got = await sync_type(db, _client(hub, token=""), slug)
        await db.commit()
        assert got["ok"] is False and got["error"] == "unavailable"
        assert hub.asked == []
    finally:
        await _cleanup(db, slug)


async def test_asking_for_a_type_the_hub_does_not_publish_is_skipped_with_notice(db, slug):
    """공개 안 된 타입은 **거절하지 않고 건너뛰며 알린다**(KR-06, 2026-10-27) — `skipped` 로 보여 준다.
    통째 거절하면 쓰는 타입 셋을 받으려다 공개 안 된 하나 때문에 나머지가 안 들어온다."""
    hub = _Hub()        # 카탈로그는 plm_task 만 공개한다
    got = await sync_all(db, _client(hub), types=["plm_task", "없는타입"])
    await db.commit()
    assert got["ok"] is True, got
    assert "없는타입" in got["skipped"] and "plm_task" in got["types"], got
    assert "plm_task" in got["opened"]


async def test_the_catalog_revision_is_recorded_so_a_definition_change_shows(db, slug):
    cat = {"system": "h", "revision": "r-7", "as_of": "T0",
           "types": [{"slug": slug, "label": "x", "count": 0, "properties": [],
                      "endpoint": f"/core/{slug}", "relations": []}]}
    try:
        got = await sync_all(db, _client(_Hub(catalog=cat, pages=[_page([_row("A")])])),
                             types=[slug])
        await db.commit()
        assert got["ok"] and got["revision"] == "r-7"
        assert (await db.get(OntoSyncState, slug)).catalog_revision == "r-7"
    finally:
        await _cleanup(db, slug)


async def test_rule6_applies_to_edges_too(db, slug):
    """같은 선이 한 쪽에 두 번 와도 깨지지 않는다 — Postgres 는 한 문장에서 같은 행을
    두 번 못 고친다(`CardinalityViolationError`). 접지 않으면 **그 쪽의 멀쩡한 선까지**
    안 들어간다."""
    cat = {"system": "h", "revision": "r1", "as_of": "T0",
           "types": [{"slug": slug, "label": "x", "count": 0, "properties": [],
                      "endpoint": f"/core/{slug}", "relations": ["belongs_to"]}]}
    edge = {"src": "A", "relation": "belongs_to", "dst": "PRJ-1", "dst_type": "plm_project"}
    hub = _Hub(catalog=cat, pages=[_page([_row("A")])],
               relations=[{"items": [dict(edge, properties={"n": 1}),
                                     dict(edge, properties={"n": 2}),
                                     {"src": "A", "relation": "belongs_to",
                                      "dst": "PRJ-2", "dst_type": "plm_project"}],
                           "as_of": "T1", "next": None}])
    try:
        got = await sync_all(db, _client(hub), types=[slug])
        await db.commit()
        assert got["ok"], got
        edges = (await db.execute(select(OntoRelation).where(
            OntoRelation.src_type == slug))).scalars().all()
        assert len(edges) == 2, f"선이 {len(edges)} 개 — 접기나 저장이 깨졌다"
        same = [e for e in edges if e.dst_key == "PRJ-1"]
        assert same[0].properties == {"n": 2}, "나중 것이 이겨야 한다"
    finally:
        await _cleanup(db, slug)
