"""개정 잇기 — **기계는 후보를 내고 사람이 확정한다.**

여기서 지키는 것 셋.
① **순환을 막는다** — 안 막으면 개정 줄을 따라가는 질의가 영원히 돈다.
② ★**사람의 확정을 기계가 덮지 않는다** — 자동 경로가 다시 지나가며 `rev_source` 를
   되돌리면 사람이 고친 사실이 사라진다. 재인제스트는 리포트를 **새로 만들기** 때문에
   이 경로를 반드시 다시 지나간다.
③ **어긋남을 조용히 맞추지 않는다** — 맞추면 사람이 넣은 값과 저장된 값이 달라지고 그
   차이는 아무 데도 안 뜬다.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete, select

from app.models import SOURCE_HUB, ImpactReport, OntoObject, OntoRelation
from app.modules.ontology import services as onto

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture()
def task():
    """시험마다 고유한 과제코드 — 개발 DB 를 공유하므로 서로를 밟지 않는다."""
    return f"PRJ-{ulid.new().str[:10]}"


def _report(*, project="", code="", embed="", rid=None):
    em = {}
    if project:
        em["project"] = project
    if code:
        em["dev_revision"] = {"code": code}
    return ImpactReport(id=rid or ulid.new().str, session_id="s", user_id=1,
                        kind="sphere", project_name=embed, eng_meta=em or None, n_cases=0)


async def _clean(db, task):
    like = f"{task}@%"
    await db.execute(delete(OntoRelation).where(OntoRelation.dst_key.like(like)))
    await db.execute(delete(OntoRelation).where(OntoRelation.src_key.like(like)))
    await db.execute(delete(OntoObject).where(OntoObject.key.like(like)))
    await db.execute(delete(OntoObject).where(OntoObject.key == task))
    await db.commit()


async def _edges(db, relation, **where):
    stmt = select(OntoRelation).where(OntoRelation.relation == relation,
                                      OntoRelation.deleted.is_(False))
    for k, v in where.items():
        stmt = stmt.where(getattr(OntoRelation, k) == v)
    return (await db.execute(stmt)).scalars().all()


# ── 순서는 데이터다 ────────────────────────────────────────────────────────

async def test_the_sequence_puts_the_phases_in_order():
    """`r`(재차수)을 그 단계 **끝**에 두는 것은 우리가 고른 약속이다 — 그래서 데이터로 둔다."""
    order = ["pre", "dv1", "dv2", "dv3", "dvr", "pv1", "pv2", "pv3", "pvr", "pra", "mp"]
    seqs = []
    for code in order:
        rev = onto.parse_stage(code)
        seqs.append(onto.rev_seq(rev["phase"], rev.get("round")))
    assert seqs == sorted(seqs), list(zip(order, seqs))
    assert len(set(seqs)) == len(seqs), "두 판이 같은 순서를 갖는다"


# ── 확정 ───────────────────────────────────────────────────────────────────

async def test_set_revision_makes_the_object_and_three_edges(db, task):
    rep = _report()
    try:
        got = await onto.set_revision(db, rep, task_key=task, code="dv1",
                                      decided_by="koo.park")
        await db.commit()
        assert got["ok"], got
        assert got["key"] == f"{task}@dv1"
        obj = (await db.execute(select(OntoObject).where(
            OntoObject.key == got["key"]))).scalar_one()
        p = obj.properties
        assert (p["code"], p["phase"], p["round"]) == ("dv1", "dv", "1")
        assert p["rev_seq"] == onto.rev_seq("dv", "1")
        assert p["rev_source"] == "manual" and p["decided_by"] == "koo.park"
        assert obj.source == "dynaforge", "자체 객체여야 한다"
        assert len(await _edges(db, onto.REL_OF, src_key=got["key"])) == 1
        measured = await _edges(db, onto.REL_MEASURED, dst_key=got["key"])
        assert [e.src_key for e in measured] == [rep.id]
        assert measured[0].src_type == "impact_report", "리포트는 선의 끝점으로만 산다"
        # 리포트를 `onto_objects` 에 복제하지 않았다
        made = (await db.execute(select(OntoObject).where(
            OntoObject.type_slug == "impact_report"))).scalars().all()
        assert made == []
    finally:
        await _clean(db, task)


async def test_a_bad_code_is_refused(db, task):
    rep = _report()
    for bad in ("dv", "pv", "mp2", "zz", ""):
        got = await onto.set_revision(db, rep, task_key=task, code=bad)
        assert got["ok"] is False, bad


async def test_a_missing_task_mirror_does_not_block_but_says_so(db, task):
    """허브가 아직 없다 — 막으면 개정을 아예 못 붙인다. 대신 **확인 못 했다**고 말한다."""
    rep = _report()
    try:
        got = await onto.set_revision(db, rep, task_key=task, code="pre")
        await db.commit()
        assert got["ok"] and got["task_unverified"] is True
        assert "확인" in got["detail"]
    finally:
        await _clean(db, task)


async def test_a_present_task_mirror_is_verified(db, task):
    rep = _report()
    try:
        db.add(OntoObject(type_slug="plm_task", key=task, label="과제",
                          source=SOURCE_HUB, properties={}))
        await db.flush()
        got = await onto.set_revision(db, rep, task_key=task, code="pre")
        await db.commit()
        assert got["ok"] and got["task_unverified"] is False
    finally:
        await _clean(db, task)


# ── ① 순환 ────────────────────────────────────────────────────────────────

async def test_a_self_supersede_is_refused(db, task):
    rep = _report()
    try:
        got = await onto.set_revision(db, rep, task_key=task, code="dv1",
                                      supersedes=f"{task}@dv1")
        assert got["ok"] is False and got["error"] == "self_supersede"
    finally:
        await _clean(db, task)


async def test_a_cycle_in_the_chain_is_refused(db, task):
    """★안 막으면 개정 줄을 따라가는 질의가 **영원히 돈다.**"""
    try:
        await onto.set_revision(db, _report(), task_key=task, code="pre")
        await onto.set_revision(db, _report(), task_key=task, code="dv1",
                                supersedes=f"{task}@pre")
        await db.commit()
        # pre 가 dv1 을 앞 판으로 삼으면 pre → dv1 → pre 가 된다
        got = await onto.set_revision(db, _report(), task_key=task, code="pre",
                                      supersedes=f"{task}@dv1")
        assert got["ok"] is False and got["error"] == "cycle"
    finally:
        await _clean(db, task)


# ── ② 사람의 확정을 기계가 덮지 않는다 ────────────────────────────────────

async def test_a_manual_decision_survives_a_later_automatic_pass(db, task):
    """★**이 시험이 S3 의 이유다.** 재인제스트는 리포트를 새로 만들므로 자동 경로를 반드시
    다시 지나간다. 그때 `rev_source` 가 `eng_meta` 로 되돌아가면 사람이 고친 사실이 사라진다."""
    try:
        first = _report()
        await onto.set_revision(db, first, task_key=task, code="dv1",
                                decided_by="koo.park", note="사람이 확인함")
        await db.commit()
        # 재인제스트 — **새 리포트 행**이 같은 eng_meta 로 자동 경로를 지나간다
        again = _report(project=task, code="dv1")
        got = await onto.link_from_eng_meta(db, again)
        await db.commit()
        assert got["ok"], got
        obj = (await db.execute(select(OntoObject).where(
            OntoObject.key == f"{task}@dv1"))).scalar_one()
        p = obj.properties
        assert p["rev_source"] == "manual", "사람의 확정이 지워졌다"
        assert p["decided_by"] == "koo.park" and p["note"] == "사람이 확인함"
        # 새 리포트도 같은 개정에 이어진다(개정 객체는 하나다)
        measured = await _edges(db, onto.REL_MEASURED, dst_key=f"{task}@dv1")
        assert sorted(e.src_key for e in measured) == sorted([first.id, again.id])
        assert len((await db.execute(select(OntoObject).where(
            OntoObject.key == f"{task}@dv1"))).scalars().all()) == 1
    finally:
        await _clean(db, task)


async def test_an_automatic_link_can_be_overwritten_by_a_person(db, task):
    """반대 방향은 열려 있어야 한다 — 기계가 붙인 것을 사람이 고친다."""
    try:
        rep = _report(project=task, code="dv1")
        await onto.link_from_eng_meta(db, rep)
        await db.commit()
        obj = (await db.execute(select(OntoObject).where(
            OntoObject.key == f"{task}@dv1"))).scalar_one()
        assert obj.properties["rev_source"] == "eng_meta"
        await onto.set_revision(db, rep, task_key=task, code="dv1", decided_by="koo.park")
        await db.commit()
        await db.refresh(obj)
        assert obj.properties["rev_source"] == "manual"
    finally:
        await _clean(db, task)


async def test_nothing_to_link_is_an_explicit_failure(db, task):
    got = await onto.link_from_eng_meta(db, _report())
    assert got["ok"] is False and got["error"] == "nothing_to_link"


# ── ③ 어긋남 ─────────────────────────────────────────────────────────────

async def test_a_matching_link_reports_no_mismatch(db, task):
    try:
        rep = _report(project=task, code="dv1")
        await onto.link_from_eng_meta(db, rep)
        await db.commit()
        assert await onto.mismatch(db, rep) is None
    finally:
        await _clean(db, task)


async def test_a_differing_link_is_shown_not_silently_fixed(db, task):
    """★관계가 정본이지만 **조용히 맞추지 않는다.**"""
    try:
        rep = _report(project=task, code="dv1")
        await onto.set_revision(db, rep, task_key=task, code="pv2", decided_by="koo.park")
        await db.commit()
        said = await onto.mismatch(db, rep)
        assert said and said["kind"] == "differs"
        assert said["linked"] == f"{task}@pv2" and said["eng_meta"] == f"{task}@dv1"
        # eng_meta 는 **그대로** 남아 있다(DataHub 등재·필터가 쓴다)
        assert rep.eng_meta["dev_revision"]["code"] == "dv1"
    finally:
        await _clean(db, task)


async def test_a_link_without_eng_meta_is_also_said(db, task):
    try:
        rep = _report()
        await onto.set_revision(db, rep, task_key=task, code="dv1")
        await db.commit()
        said = await onto.mismatch(db, rep)
        assert said and said["kind"] == "eng_meta_missing"
    finally:
        await _clean(db, task)


async def test_no_link_at_all_is_not_a_mismatch(db, task):
    assert await onto.mismatch(db, _report(project=task, code="dv1")) is None


# ── 후보 ───────────────────────────────────────────────────────────────────

async def test_the_eng_meta_code_is_the_strongest_candidate(db, task):
    got = await onto.candidates(db, _report(project=task, code="dv2"))
    assert got[0]["source"] == "eng_meta" and got[0]["code"] == "dv2"
    assert got[0]["valid"] is True and got[0]["rev_seq"] == onto.rev_seq("dv", "2")


async def test_an_embedded_name_offers_its_tail(db, task):
    got = await onto.candidates(db, _report(embed="감마_pv1"))
    codes = {c["code"] for c in got}
    assert "pv1" in codes
    assert any(c["source"] == "report_embed" for c in got)


async def test_a_candidate_that_is_not_a_valid_code_is_shown_not_dropped(db, task):
    """버리면 사람이 **고칠 기회**를 잃는다 — 보여 주고 왜 안 되는지 말한다."""
    got = await onto.candidates(db, _report(embed="감마_C2"))
    bad = [c for c in got if c["code"] == "c2"]
    assert bad and bad[0]["valid"] is False and bad[0]["why"]


async def test_nothing_is_invented_when_there_is_no_evidence(db, task):
    """없는 후보를 만들어 내면 사람이 그것을 고를 수 있게 된다."""
    assert await onto.candidates(db, _report()) == []


async def test_the_hub_model_revision_is_offered_when_the_task_is_known(db, task):
    try:
        db.add(OntoObject(type_slug="plm_model", key="SM-G999", label="모델",
                          source=SOURCE_HUB,
                          properties={"task": task, "model_revision": "dv3",
                                      "model_revision_kind": "차수"}))
        await db.flush()
        got = await onto.candidates(db, _report(), task_key=task)
        hub = [c for c in got if c["source"] == "hub_model_revision"]
        assert hub and hub[0]["code"] == "dv3"
        assert "SM-G999" in hub[0]["evidence"] and "차수" in hub[0]["evidence"]
    finally:
        await db.execute(delete(OntoObject).where(OntoObject.key == "SM-G999"))
        await _clean(db, task)


# ── 개정 줄 ────────────────────────────────────────────────────────────────

async def test_the_history_is_ordered_and_carries_the_reports(db, task):
    try:
        r0, r1, r2 = _report(), _report(), _report()
        await onto.set_revision(db, r0, task_key=task, code="pre")
        await onto.set_revision(db, r1, task_key=task, code="dv1",
                                supersedes=f"{task}@pre")
        await onto.set_revision(db, r2, task_key=task, code="dv1")   # 같은 판에 둘째 리포트
        await onto.set_revision(db, _report(), task_key=task, code="mp",
                                supersedes=f"{task}@dv1")
        await db.commit()
        line = await onto.history(db, task)
        assert [x["code"] for x in line] == ["pre", "dv1", "mp"]
        assert [x["rev_seq"] for x in line] == sorted(x["rev_seq"] for x in line)
        dv1 = [x for x in line if x["code"] == "dv1"][0]
        assert sorted(dv1["reports"]) == sorted([r1.id, r2.id])
        assert dv1["supersedes"] == f"{task}@pre"
        assert line[0]["supersedes"] is None
    finally:
        await _clean(db, task)


async def test_an_unknown_task_has_an_empty_history(db, task):
    assert await onto.history(db, task) == []


# ── 배선 — 인제스트·PATCH 가 실제로 잇는가 ─────────────────────────────────
# 도메인 로직이 맞아도 **부르는 곳이 없으면** 아무 일도 안 일어난다. 그 한 줄이 조용히
# 사라지는 것이 가장 흔한 실패다.

_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")


async def _mk_user_session(db):
    from app.models import Session, User
    from app.shared import security, storage
    u = User(email=f"rev_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("x"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="rev-test",
                storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    await db.refresh(s)
    storage.ensure_session_dir(u.id, sid)
    return u, s


async def _drop_user_session(db, u, s):
    from app.models import ImpactReport as IR
    from app.models import Session, SessionFile, User
    from app.shared import storage
    await db.execute(delete(IR).where(IR.session_id == s.id))
    await db.execute(delete(SessionFile).where(SessionFile.session_id == s.id))
    await db.execute(delete(Session).where(Session.id == s.id))
    await db.execute(delete(User).where(User.id == u.id))
    await db.commit()
    d = storage.session_abs_dir(u.id, s.id)
    if d.exists():
        import shutil
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
async def test_ingesting_with_eng_meta_links_the_revision(db, task):
    """★종단 — 과제·개정을 적어 올리면 **선이 생겨 있어야** 한다."""
    from app.modules.reports import services as rsvc
    u, s = await _mk_user_session(db)
    try:
        rep = await rsvc.ingest_report(db, s, filename="Test_001_report.html",
                                       raw=_SPHERE.read_bytes(),
                                       project=task, dev_rev="dv2")
        line = await onto.history(db, task)
        assert [x["code"] for x in line] == ["dv2"], line
        assert line[0]["reports"] == [rep.id]
        assert line[0]["rev_source"] == "eng_meta", "자동 경로가 남긴 근거여야 한다"
        assert await onto.mismatch(db, rep) is None
    finally:
        await _drop_user_session(db, u, s)
        await _clean(db, task)


@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
async def test_ingesting_without_eng_meta_links_nothing_and_still_succeeds(db):
    """메타는 **선택**이다 — 안 채운 리포트가 아예 안 들어오면 그것이 훨씬 비싸다."""
    from app.modules.reports import services as rsvc
    u, s = await _mk_user_session(db)
    try:
        rep = await rsvc.ingest_report(db, s, filename="Test_001_report.html",
                                       raw=_SPHERE.read_bytes())
        assert rep.id
        assert await _edges(db, onto.REL_MEASURED, src_key=rep.id) == []
    finally:
        await _drop_user_session(db, u, s)


@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
async def test_patching_the_meta_moves_the_link(db, task):
    """`eng_meta` 를 손으로 고치면 선이 **뒤처지지 않는다.**"""
    from app.modules.reports import services as rsvc
    u, s = await _mk_user_session(db)
    try:
        rep = await rsvc.ingest_report(db, s, filename="Test_001_report.html",
                                       raw=_SPHERE.read_bytes(),
                                       project=task, dev_rev="dv1")
        await rsvc.update_report_meta(db, rep, dev_rev="pv3")
        line = await onto.history(db, task)
        codes = {x["code"] for x in line}
        assert "pv3" in codes, line
        assert rep.id in [r for x in line if x["code"] == "pv3" for r in x["reports"]]
    finally:
        await _drop_user_session(db, u, s)
        await _clean(db, task)
