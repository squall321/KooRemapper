"""과거 리포트를 정본 과제에 붙이기 — ★**짐작으로 붙이지 않는다.**

틀려도 그럴듯한 것이 가장 나쁘다. 그럴듯한 오류는 몇 달 뒤 결과를 비교할 때 발견되고,
그때는 그 위에 결론이 얹혀 있다. 그래서 —

  · 짐작이 없는 두 길(**글자 그대로 같다** · **사람이 이미 붙였다**)만 자동으로 붙는다
  · 정규화해서 같아 보이는 것은 **후보**다 — 근거와 함께 보이고 사람이 고른다
  · 아무 후보도 없으면 **「못 붙였다」 고 목록으로 말한다**(조용히 건너뛰면 "다 붙었다" 로 읽힌다)

실측(붙은 수/못 붙은 수)은 **운영 데이터가 있어야** 한다 — 이 박스에는 리포트가 없다.
여기서는 합성으로 규칙만 고정한다.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete, select

from app.models import (SOURCE_HUB, ImpactReport, OntoAlias, OntoObject, OntoRelation,
                        Session, User)
from app.modules.ontology import services as onto
from app.shared import security, storage

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture()
def tag():
    return ulid.new().str[:10]


async def _session(db):
    u = User(email=f"m_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("x"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="m", storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    return u, s


async def _report(db, s, *, project="", code="", embed=""):
    em = {}
    if project:
        em["project"] = project
    if code:
        em["dev_revision"] = {"code": code}
    r = ImpactReport(id=ulid.new().str, session_id=s.id, user_id=s.user_id,
                     kind="sphere", project_name=embed, eng_meta=em or None, n_cases=0)
    db.add(r)
    await db.flush()
    return r


async def _task(db, key, label="", task_code=""):
    # key 는 **과제명**(rootdesign plm_task.key), 과제코드는 properties.task_code 다(KR-01).
    t = OntoObject(type_slug="plm_task", key=key, label=label or key,
                   source=SOURCE_HUB, properties=({"task_code": task_code} if task_code else {}))
    db.add(t)
    await db.flush()
    return t


async def _wipe(db, u=None, s=None, keys=()):
    for k in keys:
        await db.execute(delete(OntoRelation).where(OntoRelation.dst_key.like(f"{k}@%")))
        await db.execute(delete(OntoRelation).where(OntoRelation.src_key.like(f"{k}@%")))
        await db.execute(delete(OntoObject).where(OntoObject.key.like(f"{k}@%")))
        await db.execute(delete(OntoObject).where(OntoObject.key == k))
        await db.execute(delete(OntoAlias).where(OntoAlias.key == k))
    if s is not None:
        # ★**내 리포트의 선만** 지운다. `src_type == "impact_report"` 로 싹 지우면 공유
        #   개발 DB 에 있는 **다른 세션의 데이터**까지 날린다(실제로 거기에 있다).
        mine = (await db.execute(select(ImpactReport.id).where(
            ImpactReport.session_id == s.id))).scalars().all()
        if mine:
            await db.execute(delete(OntoRelation).where(
                OntoRelation.src_type == "impact_report", OntoRelation.src_key.in_(mine)))
        await db.execute(delete(ImpactReport).where(ImpactReport.session_id == s.id))
        await db.execute(delete(Session).where(Session.id == s.id))
    if u is not None:
        await db.execute(delete(User).where(User.id == u.id))
    await db.commit()


# ── 정규화는 비교용일 뿐 ───────────────────────────────────────────────────

async def test_normalize_is_for_comparing_only():
    assert onto.normalize("S26-DROP") == onto.normalize("s26 drop") == "s26drop"
    assert onto.normalize("감마_C2") == onto.normalize("감마 c 2")
    assert onto.normalize("") == "" and onto.normalize(None) == ""


# ── 짐작이 없는 두 길만 자동으로 ──────────────────────────────────────────

async def test_an_exact_key_links(db, tag):
    key = f"S26-{tag}"
    try:
        await _task(db, key)
        await db.commit()
        assert await onto.resolve_task(db, key) == (key, "exact")
    finally:
        await _wipe(db, keys=[key])


async def test_a_confirmed_alias_links(db, tag):
    key = f"S26-{tag}"
    try:
        await _task(db, key, label="갤럭시 S26 낙하")
        got = await onto.confirm_alias(db, alias="s26낙하", key=key, by="koo.park")
        await db.commit()
        assert got["ok"]
        assert await onto.resolve_task(db, "s26낙하") == (key, "alias")
    finally:
        await _wipe(db, keys=[key])


async def test_a_lookalike_does_not_link_by_itself(db, tag):
    """★구분기호만 다른 것도 **자동으로 붙이지 않는다** — 후보일 뿐이다."""
    key = f"S26-{tag}"
    try:
        await _task(db, key)
        await db.commit()
        assert await onto.resolve_task(db, f"s26 {tag}") == ("", "")
        cands = await onto.task_candidates(db, f"s26 {tag}")
        assert cands and cands[0]["key"] == key
        assert "구분기호" in cands[0]["why"]
    finally:
        await _wipe(db, keys=[key])


async def test_a_deleted_task_is_not_resolved(db, tag):
    """허브에서 사라진 과제에 새로 붙이지 않는다."""
    key = f"S26-{tag}"
    try:
        t = await _task(db, key)
        t.deleted = True
        await db.commit()
        assert await onto.resolve_task(db, key) == ("", "")
    finally:
        await _wipe(db, keys=[key])


async def test_a_string_cannot_point_at_two_tasks(db, tag):
    """★한 문자열이 두 과제를 가리키면 그 데이터로는 아무 질문에도 답할 수 없다."""
    a, b = f"A-{tag}", f"B-{tag}"
    try:
        await _task(db, a)
        await _task(db, b)
        await onto.confirm_alias(db, alias="같은말", key=a, by="x")
        await db.commit()
        got = await onto.confirm_alias(db, alias="같은말", key=b, by="y")
        assert got["ok"] is False and got["error"] == "already_bound"
        assert got["existing"] == a
    finally:
        await _wipe(db, keys=[a, b])


async def test_confirming_the_same_binding_again_is_fine(db, tag):
    key = f"S26-{tag}"
    try:
        await _task(db, key)
        await onto.confirm_alias(db, alias="같은말", key=key, by="x")
        got = await onto.confirm_alias(db, alias="같은말", key=key, by="y", note="다시")
        await db.commit()
        assert got["ok"]
        row = (await db.execute(select(OntoAlias).where(
            OntoAlias.alias == "같은말"))).scalar_one()
        assert row.confirmed_by == "y" and row.note == "다시"
    finally:
        await _wipe(db, keys=[key])


# ── 후보는 근거와 함께 ────────────────────────────────────────────────────

async def test_candidates_come_with_a_reason(db, tag):
    """근거 없는 후보 목록은 사람이 검증할 수 없고, 검증할 수 없으면 결국 맨 위를 누른다.

    KR-01 — key 는 **과제명**, 과제코드는 properties.task_code 다. 둘 다 근거로 뜬다."""
    key = f"갤럭시 {tag} 낙하 과제"       # 과제명(= plm_task.key)
    code = f"PRJ-{tag}"                   # 과제코드(= properties.task_code)
    try:
        await _task(db, key, label=key, task_code=code)
        await db.commit()
        for free, says in ((f"prj {tag}", "과제코드"),        # 과제코드 변형 → task_code 근거
                           (f"갤럭시{tag}낙하과제", "과제명"),  # 과제명 변형 → key 근거
                           (tag, "품고")):                     # 부분 일치
            cands = await onto.task_candidates(db, free)
            assert cands, free
            assert any(says in c["why"] for c in cands), (free, cands)
    finally:
        await _wipe(db, keys=[key])


async def test_no_candidate_is_invented(db):
    assert await onto.task_candidates(db, "") == []
    assert await onto.task_candidates(db, "아무것도없는말" + ulid.new().str) == []


# ── 계획은 쓰지 않는다 ────────────────────────────────────────────────────

async def test_the_plan_writes_nothing(db, tag):
    """★계획을 보는 것만으로 데이터가 바뀌면, 보는 것이 무서워진다."""
    key = f"S26-{tag}"
    u, s = await _session(db)
    try:
        await _task(db, key)
        await _report(db, s, project=key, code="dv1")
        await db.commit()
        before = len((await db.execute(select(OntoObject).where(
            OntoObject.type_slug == "dev_revision"))).scalars().all())
        got = await onto.plan_task_links(db)
        after = len((await db.execute(select(OntoObject).where(
            OntoObject.type_slug == "dev_revision"))).scalars().all())
        assert before == after, "계획이 썼다"
        mine = [e for e in got["plan"] if e["free"] == key][0]
        assert mine["verdict"] == "links" and mine["how"] == "exact"
        assert mine["codes"] == ["dv1"]
    finally:
        await _wipe(db, u, s, keys=[key])


async def test_the_plan_separates_links_proposals_and_unmatched(db, tag):
    key = f"S26-{tag}"
    u, s = await _session(db)
    try:
        await _task(db, key)
        await _report(db, s, project=key, code="dv1")                 # 붙는다
        await _report(db, s, project=f"s26 {tag}", code="dv1")        # 후보
        await _report(db, s, project=f"없는과제{tag}", code="dv1")     # 못 붙임
        await _report(db, s, code="dv1")                              # 이름조차 없다
        await db.commit()
        got = await onto.plan_task_links(db)
        by = {e["free"]: e for e in got["plan"]}
        assert by[key]["verdict"] == "links"
        assert by[f"s26 {tag}"]["verdict"] == "proposal"
        assert by[f"s26 {tag}"]["candidates"][0]["key"] == key
        assert by[f"없는과제{tag}"]["verdict"] == "unmatched"
        assert by[f"없는과제{tag}"]["candidates"] == []
        # ★이름조차 없는 리포트를 **세어서 말한다** — 빼면 "다 붙었다" 가 거짓이 된다
        assert got["counts"]["reports_without_a_name"] >= 1
        assert len(got["reports_without_a_name"]) == got["counts"]["reports_without_a_name"]
    finally:
        await _wipe(db, u, s, keys=[key])


async def test_the_embedded_name_is_the_fallback_in_the_same_order(db, tag):
    """`services.py` 의 폴백과 같은 순서 — 두 벌이 되면 한쪽만 고쳐진다."""
    u, s = await _session(db)
    try:
        r1 = await _report(db, s, project="수동", embed="박힌것")
        r2 = await _report(db, s, embed="박힌것")
        await db.commit()
        assert onto.report_free_task(r1) == "수동"
        assert onto.report_free_task(r2) == "박힌것"
    finally:
        await _wipe(db, u, s)


# ── 적용은 붙는 것만 ──────────────────────────────────────────────────────

async def test_apply_links_only_what_resolves(db, tag):
    key = f"S26-{tag}"
    u, s = await _session(db)
    try:
        await _task(db, key)
        r_ok = await _report(db, s, project=key, code="dv1")
        await _report(db, s, project=f"없는과제{tag}", code="dv1")
        await db.commit()
        done = await onto.apply_task_links(db, decided_by="koo.park")
        await db.commit()
        assert done["linked"] == 1 and done["strings"] == 1
        line = await onto.history(db, key)
        assert [x["code"] for x in line] == ["dv1"]
        assert line[0]["reports"] == [r_ok.id]
        assert line[0]["decided_by"] == "koo.park"
    finally:
        await _wipe(db, u, s, keys=[key])


async def test_a_report_without_a_code_is_counted_not_guessed(db, tag):
    """과제는 알지만 개정은 모른다 — **만들어 내지 않고** 건너뛴 수를 말한다."""
    key = f"S26-{tag}"
    u, s = await _session(db)
    try:
        await _task(db, key)
        await _report(db, s, project=key)          # 코드 없음
        await db.commit()
        done = await onto.apply_task_links(db, decided_by="x")
        await db.commit()
        assert done["linked"] == 0 and done["skipped_no_code"] == 1
        assert await onto.history(db, key) == []
    finally:
        await _wipe(db, u, s, keys=[key])


async def test_apply_can_be_narrowed_to_chosen_strings(db, tag):
    a, b = f"A-{tag}", f"B-{tag}"
    u, s = await _session(db)
    try:
        await _task(db, a)
        await _task(db, b)
        await _report(db, s, project=a, code="dv1")
        await _report(db, s, project=b, code="dv1")
        await db.commit()
        done = await onto.apply_task_links(db, only=[a], decided_by="x")
        await db.commit()
        assert done["linked"] == 1
        assert await onto.history(db, a) and await onto.history(db, b) == []
    finally:
        await _wipe(db, u, s, keys=[a, b])


async def test_an_alias_makes_the_next_report_link_by_itself(db, tag):
    """한 번 붙이면 같은 문자열이 다음에 들어와도 자동으로 붙는다 — 그것이 별칭의 값이다."""
    key = f"S26-{tag}"
    u, s = await _session(db)
    try:
        await _task(db, key)
        await _report(db, s, project="우리끼리부르는이름", code="dv1")
        await db.commit()
        assert [e["verdict"] for e in (await onto.plan_task_links(db))["plan"]
                if e["free"] == "우리끼리부르는이름"] == ["unmatched"]
        await onto.confirm_alias(db, alias="우리끼리부르는이름", key=key, by="koo.park")
        await db.commit()
        again = [e for e in (await onto.plan_task_links(db))["plan"]
                 if e["free"] == "우리끼리부르는이름"][0]
        assert again["verdict"] == "links" and again["how"] == "alias"
    finally:
        await _wipe(db, u, s, keys=[key])
