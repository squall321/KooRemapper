# 소속 단위 읽기 공유가 '상세'와 '검색' 두 자리에서 같게 도나 (실 DB)
"""Affiliation-scoped read sharing — detail(get_readable_report) and discovery(find_reports/facets).

요청서 platform/docs/REQUEST-postprocess-operation.md §7-3·§8:
같은 소속이면 읽기, 수정·삭제는 소유자만. 빈 소속은 절대 매칭하지 않는다
(소속 없는 사람끼리 서로의 리포트를 읽으면 '소속 공유' 가 전체 공개가 된다).

찾을 수 있는 것과 열 수 있는 것이 어긋나면 비교가 안 되므로 두 자리를 함께 시험한다.
Runs against the live dev postgres (see conftest); self-cleaning.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete

from app.models import ImpactReport, Session, User
from app.modules.reports import services as svc
from app.shared import security, storage

pytestmark = pytest.mark.asyncio(loop_scope="session")

AFF = "CAEG"
OTHER_AFF = "MXG"


async def _mk_user(db):
    u = User(
        email=f"share_{ulid.new().str}@kooremapper.test",
        password_hash=security.hash_password("x"),
        is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="share-test",
                storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    return u, s


async def _mk_report(db, user, session, *, shared: str | None):
    r = ImpactReport(
        id=ulid.new().str, session_id=session.id, user_id=user.id,
        kind="sphere", label="share-test", shared_affiliation=shared,
    )
    db.add(r)
    await db.commit()
    return r


async def _cleanup(db, users, sessions):
    for u in users:
        await db.execute(delete(ImpactReport).where(ImpactReport.user_id == u.id))
    for s in sessions:
        await db.execute(delete(Session).where(Session.id == s.id))
    for u in users:
        await db.execute(delete(User).where(User.id == u.id))
    await db.commit()


@pytest.fixture
async def pair(db):
    owner, o_sess = await _mk_user(db)
    reader, r_sess = await _mk_user(db)
    try:
        yield owner, o_sess, reader, r_sess
    finally:
        await _cleanup(db, [owner, reader], [o_sess, r_sess])


async def test_detail_owner_always_reads(db, pair):
    owner, o_sess, reader, _ = pair
    r = await _mk_report(db, owner, o_sess, shared=None)
    # 소속을 못 받아도 소유자는 읽는다
    assert await svc.get_readable_report(db, owner.id, r.id, "") is not None
    # 남은 못 읽는다
    assert await svc.get_readable_report(db, reader.id, r.id, AFF) is None


async def test_detail_same_affiliation_reads(db, pair):
    owner, o_sess, reader, _ = pair
    r = await _mk_report(db, owner, o_sess, shared=AFF)
    assert await svc.get_readable_report(db, reader.id, r.id, AFF) is not None
    assert await svc.get_readable_report(db, reader.id, r.id, OTHER_AFF) is None
    # 검증 실패(= 소속 없음)는 공유분을 열지 못한다
    assert await svc.get_readable_report(db, reader.id, r.id, "") is None


async def test_detail_empty_never_matches_empty(db, pair):
    """소속 없는 리포트 + 소속 없는 사람 — 절대 열리면 안 된다."""
    owner, o_sess, reader, _ = pair
    r = await _mk_report(db, owner, o_sess, shared=None)
    assert await svc.get_readable_report(db, reader.id, r.id, "") is None


async def test_search_sees_shared_report(db, pair):
    owner, o_sess, reader, _ = pair
    shared = await _mk_report(db, owner, o_sess, shared=AFF)
    private = await _mk_report(db, owner, o_sess, shared=None)

    ids = {x.id for x in await svc.find_reports(db, reader.id, affiliation=AFF)}
    assert shared.id in ids and private.id not in ids

    # 소속이 다르거나 검증 실패면 아무것도 안 보인다
    for aff in (OTHER_AFF, ""):
        ids = {x.id for x in await svc.find_reports(db, reader.id, affiliation=aff)}
        assert shared.id not in ids and private.id not in ids

    # 소유자는 둘 다 본다
    ids = {x.id for x in await svc.find_reports(db, owner.id, affiliation="")}
    assert shared.id in ids and private.id in ids


async def test_search_filters_still_apply_to_shared(db, pair):
    """공유분이라고 필터를 건너뛰면 안 된다 — 범위만 넓히는 것이다."""
    owner, o_sess, reader, _ = pair
    shared = await _mk_report(db, owner, o_sess, shared=AFF)
    ids = {x.id for x in await svc.find_reports(db, reader.id, affiliation=AFF, kind="sphere")}
    assert shared.id in ids
    ids = {x.id for x in await svc.find_reports(db, reader.id, affiliation=AFF, kind="deep")}
    assert shared.id not in ids


async def test_facets_count_shared(db, pair):
    owner, o_sess, reader, _ = pair
    await _mk_report(db, owner, o_sess, shared=AFF)

    def _sphere(f):
        return sum(x["count"] for x in f["kind"] if x["value"] == "sphere")

    seen = await svc.report_facets(db, reader.id, affiliation=AFF)
    blind = await svc.report_facets(db, reader.id, affiliation="")
    assert _sphere(seen) == _sphere(blind) + 1
