"""SP 코어 수신(층 1) — 받는 쪽 규칙 열여섯을 **하나씩** 고정한다(가짜 허브, 망 없음).

규칙의 정본은 StandardPlatform `backend/app/modules/coreapi/kit/01-AI-GUIDE.md` §5.6@778db2f(키트 2026-10-21 판)다.
번호를 시험 이름에 그대로 달아 둔다 — 한 줄을 고칠 때 무엇을 깨는지 보이게. 여덟 단계를 통째로 겪게 하는 채점은
`test_sp_testbed.py`(SP 시험장)가 하고, 여기는 규칙 하나하나와 **DynaForge 사정**(허브 선과 우리 선이 한 표에 산다)을 본다.

이 파일이 지키는 것의 성질은 하나다 — **빈 것 · 안 온 것 · 모르는 것을 「없다」 로 읽지 않는다.** 그 셋을 잘못 접으면
허브에서 지워진 과제가 우리 쪽에 영원히 살거나, 멀쩡한 과제가 조용히 사라진다. 둘 다 몇 달 뒤에 발견된다.

10-14 판(규칙 열하나)에서 뜻이 바뀐 셋은 시험에 까닭을 적었다 — 0건 전량 · 합쳐진 쪽의 선 · 공개 안 된 타입.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
import ulid
from sqlalchemy import delete, func, select

from app.models import (SOURCE_HUB, SOURCE_SELF, OntoCatalog, OntoObject, OntoPreviousKey, OntoRelation,
                        OntoSyncState, OntoType)
from app.runner.sp_core import NOT_PUBLISHED, SpCoreClient, sync_all

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _Hub:
    """가짜 허브. `/core` 카탈로그(시험의 타입을 공개)와 `/core/{type}` 쪽들을 **적힌 순서대로** 낸다."""

    def __init__(self, slug, *, pages=None, relations=None, catalog=None, fail=None, fail_times=None,
                 relations_on=False, extra_types=()):
        self.slug = slug
        self.pages = list(pages or [])
        self.relations = list(relations or [])
        self.catalog_body = catalog
        self.fail = fail                 # (status, code) — 쪽 요청을 거절한다
        self.fail_times = fail_times     # None 이면 늘, 숫자면 그만큼만 거절한다
        self.relations_on = relations_on or bool(relations)
        self.extra_types = list(extra_types)
        self.asked: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.asked.append({"path": path, "params": dict(request.url.params)})
        if path.endswith("/core"):
            return httpx.Response(200, json=self.catalog_body or {
                "system": "테스트허브", "revision": "r1", "as_of": "T0",
                "types": [{"slug": s, "label": s, "count": 0, "properties": [],
                           "relations": ["belongs_to"] if (self.relations_on and s == self.slug) else []}
                          for s in [self.slug, *self.extra_types]]})
        if path.endswith("/relations"):
            return httpx.Response(200, json=self.relations.pop(0) if self.relations
                                  else {"items": [], "as_of": "T1", "next": None})
        if self.fail and (self.fail_times is None or self.fail_times > 0):
            if self.fail_times is not None:
                self.fail_times -= 1
            status, code = self.fail
            return httpx.Response(status, json={"error": {"code": code, "message": "거절"}})
        if not self.pages:
            return httpx.Response(200, json={"items": [], "as_of": "T1", "next": None})
        return httpx.Response(200, json=self.pages.pop(0))


def _client(hub: _Hub, *, token="tok", sleeps=None) -> SpCoreClient:
    async def _sleep(sec):
        if sleeps is not None:
            sleeps.append(sec)
    return SpCoreClient("http://hub.test/api", token, sleep=_sleep,
                        client=httpx.AsyncClient(transport=httpx.MockTransport(hub.handler)))


async def _sync(db, hub, slug, **kw):
    return await sync_all(db, _client(hub, sleeps=kw.pop("sleeps", None)), types=[slug], **kw)


def _row(key, **kw):
    out = {"key": key, "label": kw.pop("label", f"이름-{key}"), "status": "active",
           "updated_at": "2026-10-14T00:00:00Z", "deleted": False, "hidden": False}
    out.update(kw)
    return out


def _page(items, *, as_of="T1", next_=None, **kw):
    return {"type_slug": "x", "items": items, "as_of": as_of, "next": next_, **kw}


@pytest.fixture()
async def slug(db):
    """시험마다 고유한 타입 slug — 개발 DB 를 공유하므로 서로를 밟지 않는다. 끝나면 남긴 것을 모두 걷는다."""
    s = f"t_{ulid.new().str[:12].lower()}"
    floor = (await db.execute(select(func.coalesce(func.max(OntoCatalog.id), 0)))).scalar_one()
    yield s
    await db.rollback()
    await db.execute(delete(OntoObject).where(OntoObject.type_slug == s))
    await db.execute(delete(OntoRelation).where((OntoRelation.src_type == s) | (OntoRelation.dst_type == s)))
    await db.execute(delete(OntoSyncState).where(OntoSyncState.type_slug.in_([s, f"{s}_b"])))
    await db.execute(delete(OntoPreviousKey).where(OntoPreviousKey.type_slug == s))
    await db.execute(delete(OntoType).where(OntoType.slug.in_([s, f"{s}_b"]), OntoType.source == SOURCE_HUB))
    await db.execute(delete(OntoCatalog).where(OntoCatalog.id > floor))
    await db.commit()


async def _objects(db, slug):
    return {o.key: o for o in (await db.execute(
        select(OntoObject).where(OntoObject.type_slug == slug)
        .execution_options(populate_existing=True))).scalars()}


async def _edges(db, slug):
    return (await db.execute(select(OntoRelation).where(OntoRelation.src_type == slug)
                             .execution_options(populate_existing=True))).scalars().all()


# ── 규칙 1 · 2 — 시계 ───────────────────────────────────────────────────────

async def test_rule1_the_server_clock_is_stored_verbatim(db, slug):
    """우리 시계로 만들면 몇 초 차이로 **그 사이 행이 샌다.**"""
    got = await _sync(db, _Hub(slug, pages=[_page([_row("A")], as_of="2026-10-14T01:02:03.456789Z")]), slug)
    await db.commit()
    assert got["result"] == "ok" and got["types"][slug]["rows"] == 1
    assert (await db.get(OntoSyncState, slug)).objects_as_of == "2026-10-14T01:02:03.456789Z"
    # 다음 받기는 그 값을 `since` 로 **그대로** 보낸다
    hub2 = _Hub(slug, pages=[_page([], as_of="T2")])
    await _sync(db, hub2, slug)
    asks = [a for a in hub2.asked if a["path"].endswith(slug)]
    assert asks[0]["params"]["since"] == "2026-10-14T01:02:03.456789Z"


async def test_rule2_the_clock_does_not_move_while_pages_remain(db, slug):
    """★쪽이 남았는데 시계를 옮기면 **남은 쪽을 영영 안 받는다.**"""
    got = await _sync(db, _Hub(slug, pages=[_page([_row("A")], as_of=None, next_="c1"),
                                            _page([_row("B")], as_of="TEND")]), slug)
    await db.commit()
    assert got["types"][slug]["pages"] == 2 and got["types"][slug]["rows"] == 2
    assert (await db.get(OntoSyncState, slug)).objects_as_of == "TEND"
    assert set(await _objects(db, slug)) == {"A", "B"}


async def test_rule2_a_half_received_run_keeps_the_old_clock(db, slug):
    """중간 쪽에서 끊기면 시계가 **안 움직인다** — 다음 받기가 거기서 다시 받는다."""
    await _sync(db, _Hub(slug, pages=[_page([_row("A")], as_of="T1")]), slug)
    await db.commit()
    broken = _Hub(slug, fail=(500, ""))
    got = await _sync(db, broken, slug, sleeps=[])
    await db.commit()
    assert got["result"] == "failed" and got["error"].startswith("server")
    assert (await db.get(OntoSyncState, slug)).objects_as_of == "T1", "시계가 움직였다"


# ── 규칙 3 — key 가 정체성 ──────────────────────────────────────────────────

async def test_rule3_the_second_run_updates_instead_of_creating(db, slug):
    await _sync(db, _Hub(slug, pages=[_page([_row("A", label="처음")])]), slug)
    await _sync(db, _Hub(slug, pages=[_page([_row("A", label="나중")], as_of="T2")]), slug)
    await db.commit()
    objs = await _objects(db, slug)
    assert len(objs) == 1, "같은 key 가 둘이 됐다"
    assert objs["A"].label == "나중" and objs["A"].source == SOURCE_HUB


# ── 규칙 4 — deleted · merged_into · hidden ─────────────────────────────────

async def test_rule4_deleted_is_marked_not_removed_and_keeps_its_fields(db, slug):
    """지우면 우리 기록이 가리키는 것이 사라진다. 그리고 지운 행은 **칸이 빈 채로** 온다 — 그것으로 덮으면 이미 쓴
    기록이 보일 값이 사라진다(§5.4-3)."""
    await _sync(db, _Hub(slug, pages=[_page([_row("A", properties={"grade": "A"})])]), slug)
    await _sync(db, _Hub(slug, pages=[_page([_row("A", deleted=True, properties={})], as_of="T2")]), slug)
    await db.commit()
    a = (await _objects(db, slug))["A"]
    assert a.deleted is True
    assert a.properties == {"grade": "A"}, "지운 행의 빈 칸으로 가진 칸을 덮었다"


async def test_rule4_merged_into_is_recorded(db, slug):
    await _sync(db, _Hub(slug, pages=[_page([_row("LOSER", deleted=True, merged_into="WINNER"),
                                             _row("WINNER")])]), slug)
    await db.commit()
    assert (await _objects(db, slug))["LOSER"].merged_into == "WINNER"


async def test_rule4_hidden_deactivates_but_never_creates_a_ghost(db, slug):
    """`hidden` 은 이름 · 칸이 **안 온다** — 없던 것을 만들면 빈 라벨의 유령 행이 화면에 뜬다."""
    await _sync(db, _Hub(slug, pages=[_page([_row("A")])]), slug)
    await _sync(db, _Hub(slug, pages=[_page(
        [{"key": "A", "label": "A", "hidden": True, "deleted": True, "updated_at": "T2"},
         {"key": "NEVER_SEEN", "label": "NEVER_SEEN", "hidden": True, "deleted": True, "updated_at": "T2"}],
        as_of="T2")]), slug)
    await db.commit()
    objs = await _objects(db, slug)
    assert set(objs) == {"A"}, "안 보이게 된 것을 새로 만들었다"
    assert objs["A"].deleted is True and objs["A"].hidden is True
    assert objs["A"].label == "이름-A", "이름이 식별자로 바뀌었다"


# ── 규칙 5 — 바뀐 식별자 ───────────────────────────────────────────────────

async def test_rule5_previous_keys_move_the_row_even_after_two_renames(db, slug):
    """오래 안 받았으면 가진 것이 마지막 옛 식별자가 아니다(A→B→C 에서 A) — 옛 식별자를 **전부** 본다.
    옮기지 않으면 새 식별자가 처음 보는 것이라 같은 것이 둘이 된다."""
    await _sync(db, _Hub(slug, pages=[_page([_row("V-2", label="옛 이름")])]), slug)
    await db.commit()
    got = await _sync(db, _Hub(slug, pages=[_page([_row("V-2b", label="새 이름", renamed_from="V-2a",
                                                         previous_keys=["V-2", "V-2a"])], as_of="T2")]), slug)
    await db.commit()
    objs = await _objects(db, slug)
    assert set(objs) == {"V-2b"}, f"개명 뒤 행이 {sorted(objs)} — 둘이 됐다"
    assert got["types"][slug]["renamed"] == 1 and objs["V-2b"].label == "새 이름"
    assert {"V-2", "V-2a"} <= set(objs["V-2b"].previous_keys or [])
    pairs = dict((await db.execute(select(OntoPreviousKey.old_key, OntoPreviousKey.key).where(
        OntoPreviousKey.type_slug == slug))).all())
    assert pairs == {"V-2": "V-2b", "V-2a": "V-2b"}, "옛 → 새 짝을 남기지 않으면 다른 곳의 옛 값을 못 푼다"


async def test_rule5_a_rename_moves_hub_edge_ends_but_not_ours(db, slug):
    """허브 선의 끝은 받는 쪽이 옮긴다. **우리 선**(개정 · 리포트)은 층 1 이 건드리지 않는다 — 층 2 가 옮긴다."""
    hub = _Hub(slug, pages=[_page([_row("P-1")])],
               relations=[{"items": [{"src": "P-1", "relation": "belongs_to", "dst": "PRJ-1",
                                      "dst_type": f"{slug}_b"}], "as_of": "T1", "next": None}])
    await _sync(db, hub, slug)
    db.add(OntoRelation(relation="ours", src_type="dev_revision", src_key=f"{slug}-rev", dst_type=slug,
                        dst_key="P-1", source=SOURCE_SELF))
    await db.commit()
    await _sync(db, _Hub(slug, pages=[_page([_row("P-1X", renamed_from="P-1")], as_of="T2")], relations_on=True),
                slug)
    await db.commit()
    hub_edges = [e for e in await _edges(db, slug) if not e.deleted]
    assert [(e.src_key, e.dst_key) for e in hub_edges] == [("P-1X", "PRJ-1")], "허브 선의 출발 끝을 옮기지 않았다"
    ours = (await db.execute(select(OntoRelation).where(OntoRelation.source == SOURCE_SELF,
                                                        OntoRelation.dst_type == slug)
                             .execution_options(populate_existing=True))).scalars().all()
    assert [e.dst_key for e in ours] == ["P-1"], "층 1 이 우리 선을 건드렸다"
    await db.execute(delete(OntoRelation).where(OntoRelation.src_type == "dev_revision",
                                                OntoRelation.dst_type == slug))
    await db.commit()


# ── 규칙 6 — 칸은 통째로 · 모르는 칸도 담는다 · 같은 행 두 번 ──────────────

async def test_rule6_properties_are_stored_as_given_and_replaced_whole(db, slug):
    """모르는 칸을 버리면 허브가 칸을 늘린 날 깨진다. 합치면 허브에서 비운 칸이 남는다."""
    props = {"task_status": "진행", "project": "PRJ-1", "미래칸": [1, 2], "sra_on": True}
    await _sync(db, _Hub(slug, pages=[_page([_row("A", properties=props)])]), slug)
    await db.commit()
    assert (await _objects(db, slug))["A"].properties == props
    await _sync(db, _Hub(slug, pages=[_page([_row("A", properties={"project": "PRJ-1"})], as_of="T2")]), slug)
    await db.commit()
    assert (await _objects(db, slug))["A"].properties == {"project": "PRJ-1"}, "비운 칸이 남았다"


async def test_rule6_the_same_row_twice_in_one_page_is_harmless(db, slug):
    """Postgres 는 한 문장에서 같은 행을 두 번 못 고친다 — 접지 않으면 그 쪽의 멀쩡한 행까지 안 들어간다."""
    got = await _sync(db, _Hub(slug, pages=[_page([_row("A", label="먼저"), _row("A", label="나중")])]), slug)
    await db.commit()
    assert got["result"] == "ok"
    objs = await _objects(db, slug)
    assert len(objs) == 1 and objs["A"].label == "나중"


async def test_rule6_applies_to_edges_too(db, slug):
    edge = {"src": "A", "relation": "belongs_to", "dst": "PRJ-1", "dst_type": f"{slug}_b"}
    hub = _Hub(slug, pages=[_page([_row("A")])],
               relations=[{"items": [dict(edge, properties={"n": 1}), dict(edge, properties={"n": 2}),
                                     {"src": "A", "relation": "belongs_to", "dst": "PRJ-2", "dst_type": f"{slug}_b"}],
                           "as_of": "T1", "next": None}])
    got = await _sync(db, hub, slug)
    await db.commit()
    assert got["result"] == "ok", got
    edges = await _edges(db, slug)
    assert len(edges) == 2, f"선이 {len(edges)} 개 — 접기나 저장이 깨졌다"
    assert [e for e in edges if e.dst_key == "PRJ-1"][0].properties == {"n": 2}, "나중 것이 이겨야 한다"


# ── 규칙 7 — 부재 대조 · 안전장치 ──────────────────────────────────────────

async def test_rule7_a_full_pull_deactivates_what_did_not_come(db, slug):
    """`since` 없이 받으면 지워진 것은 **안 온다** — 정리하지 않으면 허브에서 지워진 것이 영원히 산다."""
    await _sync(db, _Hub(slug, pages=[_page([_row("A"), _row("B")])]), slug)
    await db.commit()
    got = await _sync(db, _Hub(slug, pages=[_page([_row("A")], as_of="T2")]), slug, full=True)
    await db.commit()
    objs = await _objects(db, slug)
    assert objs["A"].deleted is False and objs["B"].deleted is True
    assert got["types"][slug]["gone"] == 1 and got["result"] == "ok"


async def test_rule7_a_small_set_is_cleaned_even_when_nothing_came(db, slug):
    """★10-14 판은 「전량인데 0건이면 아무것도 안 한다」 였다. 키트 10-21 판은 안전장치를 **10건 · 절반** 으로 정했다 —
    10건 이하는 정말 줄어든 것으로 보고 정리한다(규칙 7). 그 넘는 것은 아래 시험."""
    await _sync(db, _Hub(slug, pages=[_page([_row("A"), _row("B")])]), slug)
    await db.commit()
    got = await _sync(db, _Hub(slug, pages=[_page([], as_of="T2")]), slug, full=True)
    await db.commit()
    assert got["types"][slug]["gone"] == 2 and got["result"] == "ok"
    assert all(o.deleted for o in (await _objects(db, slug)).values())


async def test_rule7_more_than_half_missing_is_held_back_and_needs_a_check(db, slug):
    """토큰의 부서 · 공개 범위가 바뀐 날 전부를 비활성으로 만들지 않는다 — 정리를 멈추고 「확인 필요」(규칙 7 · 16).
    사람이 확인한 뒤 「강제 정리」(allow_shrink)로만 적용한다."""
    rows = [_row(f"K{i:02d}") for i in range(12)]
    await _sync(db, _Hub(slug, pages=[_page(rows)]), slug)
    await db.commit()
    got = await _sync(db, _Hub(slug, pages=[_page(rows[:1], as_of="T2")]), slug, full=True)
    await db.commit()
    assert got["result"] == "needs_check" and got["types"][slug]["held_back"] == 11
    assert any("정리하지 않았다" in p for p in got["problems"]), got["problems"]
    assert sum(1 for o in (await _objects(db, slug)).values() if o.deleted) == 0, "멈췄어야 하는데 정리했다"
    forced = await _sync(db, _Hub(slug, pages=[_page(rows[:1], as_of="T3")]), slug, full=True, allow_shrink=True)
    await db.commit()
    assert forced["result"] == "ok" and forced["types"][slug]["gone"] == 11


async def test_rule7_an_incremental_pull_never_cleans(db, slug):
    """증분에서는 「안 온 것」 이 「안 바뀐 것」 이다 — 정리하면 멀쩡한 것이 사라진다."""
    await _sync(db, _Hub(slug, pages=[_page([_row("A"), _row("B")])]), slug)
    await db.commit()
    got = await _sync(db, _Hub(slug, pages=[_page([_row("A")], as_of="T2")]), slug)
    await db.commit()
    assert got["types"][slug]["gone"] == 0
    assert (await _objects(db, slug))["B"].deleted is False


# ── 규칙 8 — 되살림 ────────────────────────────────────────────────────────

async def test_rule8_a_deleted_row_comes_back_and_its_edges_are_pulled_again(db, slug):
    """되살아난 것의 선은 바뀐 것이 아니라 증분으로 다시 오지 않는다 — 선을 **처음부터** 다시 받는다."""
    await _sync(db, _Hub(slug, pages=[_page([_row("A", deleted=True)])], relations_on=True), slug)
    await db.commit()
    hub = _Hub(slug, pages=[_page([_row("A")], as_of="T2")], relations_on=True)
    got = await _sync(db, hub, slug)
    await db.commit()
    assert (await _objects(db, slug))["A"].deleted is False and got["types"][slug]["revived"] == 1
    rel_asks = [a for a in hub.asked if a["path"].endswith("/relations")]
    assert rel_asks and "since" not in rel_asks[0]["params"], "되살렸는데 선을 증분으로 물었다"
    assert any("되살아난" in n for n in got["notes"])


# ── 규칙 10 — 사라진 것의 선 ───────────────────────────────────────────────

async def test_rule10_the_losers_old_edges_are_cut_and_ours_are_kept(db, slug):
    """★10-14 판은 「합치기는 진 쪽의 선을 이긴 쪽으로 옮겨 새로 온다 — 끊김을 추론하지 않는다」 였다. 반만 맞았다 —
    새 선은 오지만 **옛 선의 끊김은 안 온다.** 받는 쪽이 끊지 않으면 없는 객체에 매달린 선이 남는다(규칙 10).
    끊는 것은 **허브 선만**이다 — 같은 표의 우리 선(사람이 확정한 개정)은 그대로 둔다(사용자 결정 10-30)."""
    dst_b = f"{slug}_b"
    first = _Hub(slug, pages=[_page([_row("LOSER"), _row("WINNER")])],
                 relations=[{"items": [{"src": "LOSER", "relation": "belongs_to", "dst": "PRJ-1", "dst_type": dst_b}],
                             "as_of": "T1", "next": None}])
    await _sync(db, first, slug)
    db.add(OntoRelation(relation="ours", src_type="dev_revision", src_key=f"{slug}-rev", dst_type=slug,
                        dst_key="LOSER", source=SOURCE_SELF))
    await db.commit()
    second = _Hub(slug, pages=[_page([_row("LOSER", deleted=True, merged_into="WINNER")], as_of="T2")],
                  relations=[{"items": [{"src": "WINNER", "relation": "belongs_to", "dst": "PRJ-1", "dst_type": dst_b}],
                              "as_of": "T2", "next": None}])
    await _sync(db, second, slug)
    await db.commit()
    live = {(e.src_key, e.dst_key) for e in await _edges(db, slug) if not e.deleted}
    assert live == {("WINNER", "PRJ-1")}, f"진 쪽의 옛 선이 남았다: {live}"
    ours = (await db.execute(select(OntoRelation).where(OntoRelation.source == SOURCE_SELF,
                                                        OntoRelation.dst_type == slug)
                             .execution_options(populate_existing=True))).scalars().all()
    assert [(e.dst_key, e.deleted) for e in ours] == [("LOSER", False)], "우리 선을 기계가 끊었다"
    await db.execute(delete(OntoRelation).where(OntoRelation.src_type == "dev_revision",
                                                OntoRelation.dst_type == slug))
    await db.commit()


async def test_rule10_an_edge_to_a_gone_object_is_not_inserted(db, slug):
    """허브는 출발이 지워진 선만 거르고 도착이 지워진 선은 보낸다 — 도착이 이쪽에서 비활성이면 넣지 않는다."""
    hub = _Hub(slug, pages=[_page([_row("A"), _row("GONE", deleted=True)])],
               relations=[{"items": [{"src": "A", "relation": "belongs_to", "dst": "GONE", "dst_type": slug}],
                           "as_of": "T1", "next": None}])
    got = await _sync(db, hub, slug)
    await db.commit()
    assert not [e for e in await _edges(db, slug) if not e.deleted]
    assert got["relations"][slug]["skipped_gone"] == 1


# ── 규칙 11 — 404 · 재시도 · 인증 ──────────────────────────────────────────

async def test_rule11_a_not_published_type_is_skipped_and_needs_a_check(db, slug):
    """★10-14 판은 「멈추고 알린다」 였다. 키트 10-21 판은 **그 타입만 건너뛰고** 나머지를 받은 뒤 「확인 필요」 다 —
    공개를 거둔 타입 하나에 전체가 멈추지 않게(규칙 11 · 16). 코드를 사유에 남긴다(고칠 곳이 허브 관리자다)."""
    got = await _sync(db, _Hub(slug, fail=(404, f"APP-{NOT_PUBLISHED}")), slug)
    await db.commit()
    assert got["ok"] is True and got["result"] == "needs_check"
    assert any(slug in p and NOT_PUBLISHED in p for p in got["problems"]), got["problems"]
    state = await db.get(OntoSyncState, slug)
    assert state.last_status == "skipped" and NOT_PUBLISHED in (state.last_error or "")


async def test_rule11_any_other_404_is_an_address_error_and_stops(db, slug):
    got = await _sync(db, _Hub(slug, fail=(404, "SOMETHING-ELSE")), slug)
    await db.commit()
    assert got["result"] == "failed" and got["error"].startswith("not_found")
    assert (await db.get(OntoSyncState, slug)).last_status == "error"


async def test_rule11_server_errors_are_retried_after_two_and_four_seconds(db, slug):
    sleeps: list[float] = []
    hub = _Hub(slug, pages=[_page([_row("A")])], fail=(503, ""), fail_times=2)
    got = await _sync(db, hub, slug, sleeps=sleeps)
    await db.commit()
    assert got["result"] == "ok" and sleeps == [2.0, 4.0]
    assert "A" in await _objects(db, slug)


async def test_rule11_an_auth_error_stops_at_once_without_retrying(db, slug):
    sleeps: list[float] = []
    got = await _sync(db, _Hub(slug, fail=(401, "")), slug, sleeps=sleeps)
    await db.commit()
    assert got["result"] == "failed" and got["error"].startswith("auth") and sleeps == []


# ── 규칙 9 — reset ─────────────────────────────────────────────────────────

async def test_rule9_a_reset_restarts_from_scratch_once(db, slug):
    await _sync(db, _Hub(slug, pages=[_page([_row("A"), _row("B")])]), slug)
    await db.commit()
    hub = _Hub(slug, pages=[{"reset": True, "reset_reason": "공개 범위가 바뀌었다"}, _page([_row("A")], as_of="T9")])
    got = await _sync(db, hub, slug)
    await db.commit()
    assert got["result"] == "ok" and got["types"][slug]["reset"] == 1
    assert (await _objects(db, slug))["B"].deleted is True, "reset 뒤 부재 대조가 안 돌았다"


async def test_rule9_a_reset_that_repeats_is_refused_instead_of_looping(db, slug):
    hub = _Hub(slug, pages=[{"reset": True, "reset_reason": "a"}, {"reset": True, "reset_reason": "b"}])
    got = await _sync(db, hub, slug)
    await db.commit()
    assert got["result"] == "failed" and got["error"].startswith("reset_loop")


# ── 규칙 12 · 16 — 정의 판 · 공개 목록 · 꺼짐 ─────────────────────────────

async def test_rule12_definitions_are_mirrored_and_a_revision_change_restarts_everything(db, slug):
    """받은 정의로 화면이 생긴다 — 타입 정의를 `onto_types`(source=hub)에 둔다. 판이 바뀌면 달라진 점을 남기고
    모든 흐름을 처음부터 받는다(새로 열린 칸 · 관계의 기존 값은 증분으로 오지 않는다)."""
    def cat(rev, props):
        return {"system": "h", "revision": rev, "as_of": "T0",
                "types": [{"slug": slug, "label": "시험", "count": 1, "properties": props, "relations": []}]}
    await _sync(db, _Hub(slug, catalog=cat("r-1", [{"key": "a", "data_type": "text"}]),
                         pages=[_page([_row("A")])]), slug)
    await db.commit()
    t = (await db.execute(select(OntoType).where(OntoType.slug == slug))).scalar_one()
    assert t.source == SOURCE_HUB and t.label == "시험" and t.catalog_revision == "r-1"
    hub = _Hub(slug, catalog=cat("r-2", [{"key": "a", "data_type": "text"}, {"key": "b", "data_type": "number"}]),
               pages=[_page([_row("A")], as_of="T2")])
    got = await _sync(db, hub, slug)
    await db.commit()
    assert any("r-1 → r-2" in n for n in got["notes"]) and any(f"+ {slug}.b" in n for n in got["notes"]), got["notes"]
    asks = [a for a in hub.asked if a["path"].endswith(slug)]
    assert "since" not in asks[0]["params"], "정의가 바뀌었는데 증분으로 받았다"
    assert (await db.get(OntoSyncState, slug)).catalog_revision == "r-2"


async def test_rule16_a_requested_type_the_hub_does_not_publish_is_skipped_with_notice(db, slug):
    """받기로 한 타입이 카탈로그에 없으면 거절하지 않고 건너뛰며 「확인 필요」 로 알린다(KR-06 · 규칙 16)."""
    got = await sync_all(db, _client(_Hub(slug)), types=[slug, "없는타입"])
    await db.commit()
    assert got["ok"] is True and got["result"] == "needs_check"
    assert "없는타입" in got["skipped"] and slug in got["types"]


async def test_without_a_token_nothing_is_called(db, slug):
    """꺼져 있는 것을 조용한 성공으로 바꾸지 않는다 — 받은 줄 알고 빈 화면을 본다."""
    hub = _Hub(slug, pages=[_page([_row("A")])])
    got = await sync_all(db, _client(hub, token=""), types=[slug])
    assert got["result"] == "failed" and got["error"].startswith("unavailable")
    assert hub.asked == []
