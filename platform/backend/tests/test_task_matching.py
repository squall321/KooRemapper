"""과거 리포트를 정본 과제에 붙이기 — ★**짐작으로 붙이지 않는다.**

틀려도 그럴듯한 것이 가장 나쁘다. 그럴듯한 오류는 몇 달 뒤 결과를 비교할 때 발견되고,
그때는 그 위에 결론이 얹혀 있다. 그래서 —

  · 짐작이 없는 두 길(**글자 그대로 같다** · **사람이 이미 붙였다**)만 자동으로 붙는다 — 그 원천들이 **과제 하나로 모일
    때만**이다. 엇갈리면(별칭과 같은 글자의 허브 과제 · 두 과제의 과제코드) 후보다(검토 R8 · R6, 11-11). 그만 쓴 과제는 살아 있는
    과제가 하나도 안 맞을 때만 센다(사용자 결정 11-12 — 하나면 잇고 여럿이면 못 붙임)
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
    return ulid.new().str          # 통째로 — 앞자리는 시각이라 잘라 쓰면 1초 안에 겹친다(시험 격리)


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


async def _task(db, key, label="", task_code="", status="active"):
    # key 는 **과제명**(rootdesign plm_task.key), 과제코드는 properties.task_code 다(KR-01).
    t = OntoObject(type_slug="plm_task", key=key, label=label or key, status=status,
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


async def test_sources_that_disagree_make_a_candidate_not_a_move(db, tag):
    """검토 R8 — 사람이 「word 는 t1」 이라 별칭을 붙인 뒤 허브가 글자 그대로 word 라는 다른 과제를 내면, 어느 쪽도 조용히 이기지
    않는다. 이미 이은 리포트는 그대로 두고, 계획은 엇갈림(`ambiguous`)과 두 후보(근거 포함)를 낸다."""
    from app.models import ImpactReport as IR
    t1, word = f"T1-{tag}", f"W-{tag}"
    u, s = await _session(db)
    try:
        await _task(db, t1)
        assert (await onto.confirm_alias(db, alias=word, key=t1, by="admin@x"))["ok"]
        r = await _report(db, s, project=word, code="dv1")
        await db.commit()
        assert (await onto.auto_link_tasks(db, report_ids=[r.id]))["linked"] == 1
        await db.commit()
        await _task(db, word)                                  # 허브가 나중에 같은 글자의 다른 과제를 낸다
        await db.commit()
        assert await onto.resolve_task(db, word) == ("", "")
        e = (await onto.plan_task_links(db, scope=IR.id.in_([r.id])))["plan"][0]
        assert e["verdict"] == "proposal" and e["ambiguous"] is True, e
        assert [(c["key"], c["why"]) for c in e["candidates"][:2]] == \
            [(word, "과제명이 글자 그대로 같다"), (t1, "사람이 붙인 별칭이 가리킨다")], e["candidates"]
        again = await onto.auto_link_tasks(db, report_ids=[r.id])
        await db.commit()
        assert again["linked"] == 0, again
        assert [x["reports"] for x in await onto.history(db, t1)] == [[r.id]], "같은 글자의 허브 과제가 사람의 별칭을 조용히 이겼다"
        assert await onto.history(db, word) == []
    finally:
        await _wipe(db, u, s, keys=[t1, word])


async def test_a_task_code_shared_by_two_tasks_is_a_stable_candidate(db, tag):
    """검토 R6 · R6b — 과제코드가 두 과제에 걸리면 잇지 않고 후보로 낸다(허브 별칭과 같은 규칙 — 하나뿐일 때만). 후보 차례는
    key 차례라 행을 고쳐도(물리 차례가 바뀌어도) 실행마다 같다."""
    from app.models import ImpactReport as IR
    a, b, code = f"A-{tag}", f"B-{tag}", f"C-{tag}"
    u, s = await _session(db)
    try:
        await _task(db, b, task_code=code)                     # 나중 key 를 먼저 넣는다
        await _task(db, a, task_code=code)
        r = await _report(db, s, project=code, code="dv1")
        await db.commit()
        assert await onto.resolve_task(db, code) == ("", ""), "과제코드가 두 과제에 걸렸는데 하나를 골랐다"
        orders = []
        for i in range(3):
            e = (await onto.plan_task_links(db, scope=IR.id.in_([r.id])))["plan"][0]
            assert e["verdict"] == "proposal" and e["ambiguous"] is True, e
            orders.append([c["key"] for c in e["candidates"][:2]])
            row = (await db.execute(select(OntoObject).where(OntoObject.key == (a if i % 2 == 0 else b)))).scalar_one()
            row.properties = {**(row.properties or {}), "touch": i}   # 받기가 행을 고친 것처럼 — 물리 차례가 바뀐다
            await db.commit()
        assert orders == [[a, b]] * 3, orders
        got = await onto.auto_link_tasks(db, report_ids=[r.id])
        await db.commit()
        assert got["linked"] == 0 and await onto.history(db, a) == [] and await onto.history(db, b) == []
    finally:
        await _wipe(db, u, s, keys=[a, b, code])


# ── 살아 있는 과제가 정한다(사용자 결정 11-12 — 다리와 같은 규칙을 과제 잇기에도) ──────────────────────

async def test_a_deprecated_task_never_vetoes_a_live_match(db, tag):
    """그만 쓴(deprecated) 과제는 살아 있는 과제의 일치를 막지 못한다 — 이름이 살아 있는 과제의 과제코드 · 과제명과 같은 글자여도,
    과제코드를 같이 써도 살아 있는 과제로 잇는다(재검토 rr2b — 예전엔 엇갈림이라 과제코드로 잇던 리포트가 안 이어졌다)."""
    live, code = f"A-{tag}", f"C-{tag}"
    quiet = [f"B-{tag}", f"D-{tag}", f"E-{tag}"]
    try:
        await _task(db, live, task_code=code)
        await _task(db, quiet[0], label=code, status="deprecated")          # 이름 = 살아 있는 과제의 과제코드
        await _task(db, quiet[1], label=live, status="deprecated")          # 이름 = 살아 있는 과제의 과제명
        await _task(db, quiet[2], task_code=code, status="deprecated")      # 과제코드를 같이 쓴다
        assert await onto.resolve_task(db, code) == (live, "task_code")
        assert await onto.resolve_task(db, live) == (live, "exact")
    finally:
        await _wipe(db, keys=[live, code, *quiet])


async def test_deprecated_tasks_count_only_when_no_live_task_matches(db, tag):
    """살아 있는 과제가 하나도 안 맞을 때만 그만 쓴 과제를 센다 — 하나면 예전처럼 잇고, 여럿이면 못 붙임(그만 쓴 과제는 후보로도 내지
    않는다 — 새로 고르는 목록, 10-30 결정)."""
    from app.models import ImpactReport as IR
    one, a, b, code = f"O-{tag}", f"A-{tag}", f"B-{tag}", f"C-{tag}"
    u, s = await _session(db)
    try:
        await _task(db, one, status="deprecated")
        await _task(db, a, task_code=code, status="deprecated")
        await _task(db, b, task_code=code, status="deprecated")
        assert await onto.resolve_task(db, one) == (one, "exact")
        assert await onto.resolve_task(db, code) == ("", "")
        r = await _report(db, s, project=code, code="dv1")
        e = (await onto.plan_task_links(db, scope=IR.id.in_([r.id])))["plan"][0]
        assert (e["verdict"], e["candidates"]) == ("unmatched", []), e
    finally:
        await _wipe(db, u, s, keys=[one, a, b, code])


async def test_among_live_tasks_a_same_label_still_only_disagrees(db, tag):
    """살아 있는 과제끼리는 그대로(D7) — 이름(label)만으로는 잇지 않고, 다른 과제의 이름이 같은 글자면 엇갈림(후보)이다."""
    a, b = f"A-{tag}", f"B-{tag}"
    try:
        await _task(db, a)
        await _task(db, b, label=a)
        assert await onto.resolve_task(db, a) == ("", "")
        cands, ambiguous = await onto.candidates_for(db, a)
        assert ambiguous and [c["key"] for c in cands][:2] == [a, b], cands
    finally:
        await _wipe(db, keys=[a, b])


async def test_an_alias_whose_task_is_missing_disagrees_and_never_links(db, tag):
    """사람이 붙인 별칭의 끝(과제)이 거울에 없으면(허브에서 지워짐 · 합쳐짐 · 받은 적 없음) 엇갈림이다 — 다른 원천이 한 과제로 맞아도
    잇지 않고 후보로 낸다. 그 끝은 거울에 없어 고를 수 없으니 후보로 내지 않고 `alias_missing` 으로 보인다(SRC-08 다리와 같은 규칙 —
    예전엔 거울에 없는 그 key 로 풀려 확인 못 한 과제의 판을 만들었다)."""
    from app.models import ImpactReport as IR
    live, gone, word = f"L-{tag}", f"G-{tag}", f"W-{tag}"
    u, s = await _session(db)
    try:
        await _task(db, live)
        assert (await onto.confirm_alias(db, alias=word, key=gone, by="kim"))["ok"]      # 끝이 거울에 없는 별칭
        assert (await onto.confirm_alias(db, alias=live, key=gone, by="kim"))["ok"]      # 살아 있는 과제명과 같은 글자 · 끝이 없다
        assert await onto.resolve_task(db, word) == ("", ""), "끝이 거울에 없는 별칭으로 풀었다"
        assert await onto.resolve_task(db, live) == ("", ""), "끝이 없는 별칭이 엇갈리는데 과제명으로 이었다"
        cands, ambiguous = await onto.candidates_for(db, live)
        assert ambiguous and [c["key"] for c in cands] == [live] and gone in cands[0]["why"], cands
        r = await _report(db, s, project=word, code="dv1")
        e = (await onto.plan_task_links(db, scope=IR.id.in_([r.id])))["plan"][0]
        assert e["verdict"] != "links" and e.get("alias_missing") == gone, e
        got = await onto.auto_link_tasks(db, report_ids=[r.id])
        assert got["linked"] == 0 and await onto.history(db, gone) == [], got
    finally:
        await _wipe(db, u, s, keys=[live, gone, word])


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


async def test_the_plan_reads_the_tasks_once_for_all_unresolved_strings(db, tag, monkeypatch):
    """계획은 받기마다 전부를 본다(SRC-09 자동 잇기) — 못 푼 문자열마다 과제 전부를 다시 읽으면 문자열 수 × 과제 수가 된다."""
    u, s = await _session(db)
    calls = []
    real = onto._live_tasks

    async def counted(_db):
        calls.append(1)
        return await real(_db)

    monkeypatch.setattr(onto, "_live_tasks", counted)
    try:
        for n in range(3):
            await _report(db, s, project=f"없는과제{tag}-{n}", code="dv1")
        await db.commit()
        got = await onto.plan_task_links(db)
        mine = [e for e in got["plan"] if e["free"].startswith(f"없는과제{tag}-")]
        assert len(mine) == 3 and all(e["verdict"] == "unmatched" for e in mine), mine
        assert len(calls) == 1, f"과제를 {len(calls)}번 읽었다"
    finally:
        await _wipe(db, u, s)


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
        # 이 시험의 문자열만 고른다 — 고르지 않으면 공유 dev DB 의 남의 리포트까지 잇는다(시험 격리)
        done = await onto.apply_task_links(db, only=[key, f"없는과제{tag}"])
        await db.commit()
        assert done["linked"] == 1 and done["strings"] == 1
        line = await onto.history(db, key)
        assert [x["code"] for x in line] == ["dv1"]
        assert line[0]["reports"] == [r_ok.id]
        # 일괄 적용은 자동 잇기와 같은 기계 출처다 — 판에 관리자 이름을 찍지 않는다(검토 반영 11-11)
        assert line[0]["rev_source"] == "rule" and line[0]["decided_by"] is None, line[0]
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
        done = await onto.apply_task_links(db, only=[key])      # 이 시험의 문자열만(시험 격리)
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
        done = await onto.apply_task_links(db, only=[a])
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
        free = f"우리끼리부르는이름{tag}"           # 고정 글자면 겹쳐 도는 시험끼리 같은 별칭을 다툰다(시험 격리)
        await _report(db, s, project=free, code="dv1")
        await db.commit()
        assert [e["verdict"] for e in (await onto.plan_task_links(db))["plan"]
                if e["free"] == free] == ["unmatched"]
        await onto.confirm_alias(db, alias=free, key=key, by="koo.park")
        await db.commit()
        again = [e for e in (await onto.plan_task_links(db))["plan"]
                 if e["free"] == free][0]
        assert again["verdict"] == "links" and again["how"] == "alias"
    finally:
        await _wipe(db, u, s, keys=[key])
