# 해석 객체 → 코어 다리(core-link SRC-08) 시험 — 정확 일치만 규칙 선 · 후보 · 사람 선 보존 · 끊긴 사람 선 · 타입 검사 · 가시성
"""실제 dev DB 에 사용자 · 세션 · 리포트(각도 둘)를 만들고 실물 v14 꾸러미 픽스처(`fixtures/cae_package_v14_min.json` — 파트 23 · 소견 22 ·
캠페인 1)를 싣는다. 코어 거울은 이 시험이 잠깐 넣는 허브 행(part · failure_mode · analysis_method)과 우리 별칭 · 옛 key 다 — 정해진
key 로 넣고 앞뒤에 지운다(dev 거울에는 이 세 타입이 없다 — 받을 타입 기본값 밖).

거울 픽스처가 v14 에 낳는 것(손으로 셈 — 아래 EXPECT).
  파트  규칙 6 — part/2(옛 key) · part/3(이름) · part/18(허브 별칭) · part/20(우리 별칭) · part/21(key) · part/23(그만 씀이어도 정확은 잇는다)
        후보 7 — part/1(같은 이름 둘) · part/4(구분기호만 다름) · part/12 · part/13(「pkg\\pkg1」 을 품는다) · part/16 · part/17 · part/19(SUBPKG)
        못 붙임 10 — 사라진 행(Geom\\솔리드)과 그만 쓴 후보(SUBPBA)는 보지 않는다
  소견  규칙 1(finding/3 — 제목이 이름과 같다) · 후보 1(finding/18 — 「Motor」 를 품는다) · 못 붙임 20
  캠페인 규칙 1(drop_all_angle — 우리 별칭)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
import ulid
from sqlalchemy import delete, select

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import (SOURCE_HUB, ImpactCase, ImpactReport, OntoAlias, OntoObject, OntoPreviousKey, OntoRelation,
                        Session, SessionFile, User)
from app.modules.reports import bridges as br
from app.modules.reports import services as svc
from app.reports import onto_package as op
from app.shared import security, storage

ON_SESSION_LOOP = pytest.mark.asyncio(loop_scope="session")     # DB 픽스처와 같은 루프 — 순수 시험에는 달지 않는다
FIX = Path(__file__).with_name("fixtures") / "cae_package_v14_min.json"
TAG = "cae-bridge-test"         # 우리 별칭 행의 note — 이 시험이 넣은 것만 지운다

# (type, key, label, status, deleted, aliases)
MIRROR = [
    ("part", "cbt:pcb", "PCB\\PCB", "active", False, None),
    ("part", "Display\\Display", "디스플레이", "active", False, None),
    ("part", "cbt:motor", "모터", "active", False, ["PKG\\Motor"]),
    ("part", "cbt:bond", "본드", "active", False, None),
    ("part", "cbt:wall", "벽", "active", False, None),
    ("part", "cbt:metal-a", "Front\\Metal", "active", False, None),
    ("part", "cbt:metal-b", "Front\\Metal", "active", False, None),
    ("part", "cbt:pkg1", "pkg\\pkg 1", "active", False, None),
    ("part", "cbt:subpkg", "SUBPKG", "active", False, None),
    ("part", "cbt:geom", "Geom\\솔리드", "active", True, None),
    ("part", "cbt:part23", "Part 23", "deprecated", False, None),
    ("part", "cbt:subpba", "SUBPBA", "deprecated", False, None),
    ("failure_mode", "cbt:fm-shock", "Part 2 (Front\\Wall): peak 0.65 MG", "active", False, None),
    ("failure_mode", "cbt:fm-motor", "Motor", "active", False, None),
    ("analysis_method", "cbt:am-drop", "낙하 해석", "active", False, None),
]
EXTRA = [("part", "cbt:geom2"), ("part", "cbt:frame-live"), ("part", "cbt:frame-old"), ("part", "cbt:battery")]  # 시험 도중 넣는 행
ALIASES = [("part", "Bond\\Bond", "cbt:bond"), ("analysis_method", "drop_all_angle", "cbt:am-drop")]
PREVIOUS = [("part", "Front\\Wall", "cbt:wall")]

EXPECT = {"rule": 8, "human": 0, "stale": 0, "renamed": 0, "candidates": 8, "unmatched": 30, "unnamed": 0}
EXPECT_BY = {"cae_campaign": {"objects": 1, "rule": 1, "human": 0, "stale": 0, "renamed": 0, "candidates": 0, "unmatched": 0,
                              "unnamed": 0},
             "cae_part": {"objects": 23, "rule": 6, "human": 0, "stale": 0, "renamed": 0, "candidates": 7, "unmatched": 10,
                          "unnamed": 0},
             "cae_finding": {"objects": 22, "rule": 1, "human": 0, "stale": 0, "renamed": 0, "candidates": 1, "unmatched": 20,
                             "unnamed": 0}}
RULES = {"campaign": ("follows_method", "cbt:am-drop", "alias"), "part/2": ("maps_to", "cbt:wall", "previous_key"),
         "part/3": ("maps_to", "cbt:pcb", "label"), "part/18": ("maps_to", "cbt:motor", "hub_alias"),
         "part/20": ("maps_to", "cbt:bond", "alias"), "part/21": ("maps_to", "Display\\Display", "key"),
         "part/23": ("maps_to", "cbt:part23", "label"), "finding/3": ("indicates", "cbt:fm-shock", "label")}
CANDIDATES = {"part/1": ["cbt:metal-a", "cbt:metal-b"], "part/4": ["cbt:pkg1"], "part/12": ["cbt:pkg1"],
              "part/13": ["cbt:pkg1"], "part/16": ["cbt:subpkg"], "part/17": ["cbt:subpkg"], "part/19": ["cbt:subpkg"],
              "finding/18": ["cbt:fm-motor"]}


def _pkg() -> dict:
    return json.loads(FIX.read_text(encoding="utf-8"))


def _raw(pkg: dict) -> bytes:
    return json.dumps(pkg, ensure_ascii=False).encode("utf-8")


def _without_finding(pkg: dict, key: str) -> dict:
    """소견 하나를 뺀 꾸러미 — 소견은 아무 칸도 가리키지 않으므로 그 행과 finding_about 줄만 빼면 검사를 통과한다."""
    pkg["objects"] = [o for o in pkg["objects"] if not (o["type"] == "cae_finding" and o["key"] == key)]
    pkg["relations"] = [r for r in pkg["relations"] if r["src"] != ["cae_finding", key]]
    return pkg


async def _clean_mirror(db) -> None:
    for t, k in [(m[0], m[1]) for m in MIRROR] + EXTRA:
        await db.execute(delete(OntoObject).where(OntoObject.type_slug == t, OntoObject.key == k,
                                                  OntoObject.report_id.is_(None)))
    await db.execute(delete(OntoAlias).where(OntoAlias.note == TAG))
    for t, old, _ in PREVIOUS:
        await db.execute(delete(OntoPreviousKey).where(OntoPreviousKey.type_slug == t, OntoPreviousKey.old_key == old))
    await db.commit()


async def _mirror(db) -> None:
    await _clean_mirror(db)
    for t, k, label, st, gone, aliases in MIRROR:
        db.add(OntoObject(type_slug=t, key=k, label=label, status=st, deleted=gone, source=SOURCE_HUB, report_id=None,
                          properties={"aliases": aliases} if aliases else {}))
    for t, alias, key in ALIASES:
        db.add(OntoAlias(type_slug=t, alias=alias, key=key, source="manual", confirmed_by="test", note=TAG))
    for t, old, key in PREVIOUS:
        db.add(OntoPreviousKey(type_slug=t, old_key=old, key=key))
    await db.commit()


_CREATED: list[int] = []      # 이 시험이 만든 사용자 id — 정리는 ORM 객체가 아니라 이 수로 한다(되감긴 세션의 객체는 만료돼 못 읽는다)


async def _make(db, *, admin: bool = False, with_report: bool = True, shared: str | None = None):
    u = User(email=f"cbt_{ulid.new().str}@kooremapper.test", password_hash=security.hash_password("x"),
             is_active=True, is_system_admin=admin)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    _CREATED.append(u.id)
    if not with_report:
        return u, None
    pkg = _pkg()
    sid = ulid.new().str
    # 세션 자리는 진짜 꼴로 — 꾸러미 파일 행의 rel_path 와 디스크 자리가 같아야 지운 파일을 디스크에서도 본다
    s = Session(id=sid, user_id=u.id, name="cbt", storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.flush()
    html = SessionFile(session_id=s.id, filename="report.html", rel_path=f"{s.storage_path}/report.html", kind="input",
                       size_bytes=1, sha256=pkg["source"]["html"]["sha256"])
    db.add(html)
    await db.flush()
    rep = ImpactReport(id=ulid.new().str, session_id=s.id, user_id=u.id, kind="sphere", n_cases=2,
                       source_file_id=html.id, label="다리 시험", shared_affiliation=shared)
    db.add(rep)
    await db.flush()
    for o in pkg["objects"]:
        if o["type"] == "cae_run":
            db.add(ImpactCase(report_id=rep.id, case_key=o["properties"]["case_key"],
                              identity={"angle": {"name": o["label"]}}))
    await db.commit()
    return u, rep


async def _drop(db, *users):
    """만든 사용자를 지운다(세션 · 리포트 · 행 · 선은 FK 로 함께). 시험이 깨져 세션이 되감겼어도 지우도록 먼저 되감고 id 로 지운다."""
    await db.rollback()
    ids, _CREATED[:] = list(_CREATED), []
    for uid in ids:
        await db.execute(delete(User).where(User.id == uid))
    await db.commit()


@pytest.fixture
async def mirror(db):
    await _mirror(db)
    try:
        yield
    finally:
        await _clean_mirror(db)


async def _lines(db, rid: str) -> dict[tuple[str, str], OntoRelation]:
    rows = (await db.execute(select(OntoRelation).where(
        OntoRelation.report_id == rid, OntoRelation.relation.in_(br.relations())))).scalars().all()
    return {(r.src_key.removeprefix(f"{rid}/"), r.dst_key): r for r in rows}


def _flat(counts: dict) -> dict:
    return {k: counts[k] for k in EXPECT}


# ── 순수 — 정확 · 후보 규칙 ────────────────────────────────────────────────────────────────

def _pool(**kw) -> br._Pool:
    p = br._Pool()
    for key, label in kw.get("objs", {}).items():
        p.labels[key] = label
        for how, text in (("key", key), ("label", label)):
            p.exact.setdefault(text, {}).setdefault(key, set()).add(how)
            p.names.append((key, br.normalize(text), how))
    p.ours.update(kw.get("ours", {}))
    return p


def test_exact_is_the_task_link_rule_strip_only():
    """「정확」 은 과제 잇기(resolve_task)와 같다 — 앞뒤 공백만 걷는다. 대소문자 · 구분기호가 다르면 정확이 아니라 후보다."""
    p = _pool(objs={"Q1": "PCB Main"})
    assert br.match(p, "  PCB Main ")["verdict"] == "rule"
    got = br.match(p, "pcb-main")
    assert got["verdict"] == "candidates" and got["options"][0]["key"] == "Q1"
    assert got["options"][0]["why"] == br._WHY_SAME["label"]


def test_exact_sources_that_disagree_are_candidates_not_a_line():
    """우리 별칭은 Q2 인데 다른 객체 Q1 의 이름이 같은 글이면 「정확히 하나」 가 아니다 — 어느 쪽도 정하지 않고 둘 다 후보로 낸다.
    별칭이 먼저라 Q2 로 긋던 것을 뒤집었다(검토 11-11 · 과제 잇기도 같은 규칙으로 바뀐다)."""
    p = _pool(objs={"Q1": "Bracket", "Q2": "브래킷"}, ours={"Bracket": "Q2"})
    got = br.match(p, "Bracket")
    assert got["verdict"] == "candidates" and "key" not in got
    assert [(o["key"], o["why"]) for o in got["options"]] == [("Q1", f"{br._WHY_MANY}(이름)"), ("Q2", f"{br._WHY_MANY}(우리 별칭)")]


def test_exact_sources_that_agree_draw_one_line_named_by_the_strongest():
    """여러 칸이 **같은** 객체를 가리키면 하나다 — 규칙 선이고, 맞은 칸은 우리 별칭 > key > 이름 > 허브 별칭 > 옛 key 차례로 하나를 적는다."""
    p = _pool(objs={"Q1": "Bracket"}, ours={"Bracket": "Q1"})
    got = br.match(p, "Bracket")
    assert (got["verdict"], got["key"], got["matched_by"]) == ("rule", "Q1", "alias")
    assert br.match(_pool(objs={"Q1": "Q1"}), "Q1")["matched_by"] == "key", "key 와 이름이 같은 글이면 key"


def test_several_exact_matches_are_candidates_not_a_line():
    p = _pool(objs={"Q1": "Frame", "Q2": "Frame"})
    got = br.match(p, "Frame")
    assert got["verdict"] == "candidates" and "key" not in got
    assert [(o["key"], o["why"]) for o in got["options"]] == [("Q1", f"{br._WHY_MANY}(이름)"), ("Q2", f"{br._WHY_MANY}(이름)")]


def test_containment_needs_two_characters_and_ranks_longer_first():
    p = _pool(objs={"Q1": "A", "Q2": "PKG", "Q3": "SUBPKG"})
    got = br.match(p, "PKG\\SUBPKG2")
    assert [o["key"] for o in got["options"]] == ["Q3", "Q2"], "길게 품은 것이 먼저 · 한 글자는 아무 글에나 걸려 보지 않는다"
    assert br.match(p, "")["verdict"] == "unnamed" and br.match(p, None)["verdict"] == "unnamed"
    assert br.match(p, "ZZZ")["verdict"] == "unmatched"


def test_candidates_are_capped_with_the_rest_counted():
    p = _pool(objs={f"Q{i}": f"Frame{i}" for i in range(8)})
    got = br.match(p, "frame")
    assert len(got["options"]) == br.CANDIDATES_PER_OBJECT and got["more"] == 8 - br.CANDIDATES_PER_OBJECT


@ON_SESSION_LOOP
async def test_a_deprecated_object_is_never_offered_as_a_candidate(db, mirror):
    """그만 씀(deprecated)은 새로 고르는 목록에 안 낸다 — 글자 그대로 둘이 맞아 후보가 된 자리(여럿 맞음)에서도(검토 11-11 P3).
    둘이 맞았으니 규칙 선은 아니고, 후보에는 살아 있는 것만 남는다."""
    db.add_all([OntoObject(type_slug="part", key="cbt:frame-live", label="CBT Frame", status="active", source=SOURCE_HUB),
                OntoObject(type_slug="part", key="cbt:frame-old", label="CBT Frame", status="deprecated", source=SOURCE_HUB)])
    await db.commit()
    got = br.match(await br._pool(db, "part"), "CBT Frame")
    assert got["verdict"] == "candidates" and "key" not in got
    assert [o["key"] for o in got["options"]] == ["cbt:frame-live"], got["options"]


def test_the_code_names_one_property_per_bridge_and_the_vocabulary_has_it():
    """끝 타입 · 카디널리티는 정의 파일에서 읽는다 — 코드는 부르는 칸만 정하고, 그 칸은 해석 어휘(모든 받아들인 판)에 있어야 한다."""
    got = br.bridges()
    assert {t: (b.relation, b.dst_type, b.cardinality) for t, b in got.items()} == {
        "cae_campaign": ("follows_method", "analysis_method", "many_to_one"),
        "cae_part": ("maps_to", "part", "many_to_one"),
        "cae_finding": ("indicates", "failure_mode", "many_to_many")}
    for sha in op.ACCEPTED:
        types = {t["slug"]: {p["key"] for p in t["properties"]} for t in op.vocabulary(sha)["types"]}
        for t, b in got.items():
            assert b.name_prop in types[t], (sha[:12], t, b.name_prop)


# ── 붙이기 — 실물 v14 와 거울 픽스처 ───────────────────────────────────────────────────────

@ON_SESSION_LOOP
async def test_attaching_v14_draws_exact_lines_and_lists_candidates(db, mirror):
    u, rep = await _make(db)
    try:
        got = await svc.attach_ontology(db, rep, FIX.read_bytes(), filename="report.ontology.json")
        b = got["bridges"]
        assert _flat(b) == EXPECT and b["by_type"] == EXPECT_BY, b
        assert b["mirror"] == {"analysis_method": 1, "part": 11, "failure_mode": 2} and not b["notes"]
        assert _flat(rep.ontology["bridges"]) == EXPECT, "리포트 요약(ontology)에도 같은 셈"

        lines = await _lines(db, rep.id)
        assert {k[0]: (r.relation, k[1], r.properties["matched_by"]) for k, r in lines.items()} == RULES
        assert all(r.properties["basis"] == "rule" and r.source == "dynaforge" for r in lines.values())
        assert lines[("part/18", "cbt:motor")].properties["matched_text"] == "PKG\\Motor"
        assert not [k for k in lines if k[0] == "part/1"], "같은 이름이 둘이면 선이 아니라 후보다"

        view = (await svc.ontology_view(db, rep))["bridges"]
        assert {c["src_key"]: [o["key"] for o in c["options"]] for c in view["candidates"]} == CANDIDATES
        one = next(c for c in view["candidates"] if c["src_key"] == "part/1")
        assert {o["why"] for o in one["options"]} == {f"{br._WHY_MANY}(이름)"} and one["name"] == "Front\\Metal"
        assert view["unmatched"]["cae_part"] == ["part/5", "part/6", "part/7", "part/8", "part/9", "part/10", "part/11",
                                                 "part/14", "part/15", "part/22"]
        assert len(view["unmatched"]["cae_finding"]) == 20 and view["stale"] == [] and "drift" not in view
        assert [ln["src_key"] for ln in view["lines"]] == ["campaign", "part/2", "part/3", "part/18", "part/20", "part/21",
                                                           "part/23", "finding/3"]
        ln = next(x for x in view["lines"] if x["src_key"] == "part/3")
        assert (ln["dst_label"], ln["dst_active"], ln["src_label"], ln["basis"]) == ("PCB\\PCB", True, "PCB\\PCB", "rule")
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
async def test_an_empty_mirror_says_why_nothing_links(db):
    """dev 처럼 세 타입을 받지 않은 박스 — 못 붙였다고만 하지 않고 까닭(받을 타입)을 말한다."""
    await _clean_mirror(db)
    u, rep = await _make(db)
    try:
        got = (await svc.attach_ontology(db, rep, FIX.read_bytes()))["bridges"]
        if any(got["mirror"].values()):
            pytest.skip(f"dev 거울에 다리 끝 타입이 있다 — {got['mirror']}")
        assert got["rule"] == got["candidates"] == 0 and got["unmatched"] == 46
        assert len(got["notes"]) == 3 and all("KOORM_SP_CORE_TYPES" in n for n in got["notes"])
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
async def test_reattaching_keeps_human_lines_and_redraws_rule_lines(db, mirror):
    u, rep = await _make(db)
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        a = await br.confirm(db, rep, src_key="part/1", dst_key="cbt:metal-a", by="owner@x", note="같은 이름 둘 중 앞")
        f = await br.confirm(db, rep, src_key="finding/18", dst_key="cbt:fm-motor", by="owner@x")
        o = await br.confirm(db, rep, src_key="part/3", dst_key="cbt:subpkg", by="owner@x")
        await db.commit()
        assert a["ok"] and f["ok"] and o["ok"] and o["replaced_rule"] == ["cbt:pcb"], o
        assert _flat(o["bridges"]) == {**EXPECT, "rule": 7, "human": 3, "candidates": 6}, "part/3 은 사람이 이겼다(다대일)"
        before = await _lines(db, rep.id)
        human_ids = {k: r.id for k, r in before.items() if r.properties["basis"] == "human"}
        assert set(human_ids) == {("part/1", "cbt:metal-a"), ("finding/18", "cbt:fm-motor"), ("part/3", "cbt:subpkg")}
        assert ("part/3", "cbt:pcb") not in before

        # 거울이 바뀐다 — key 로 잇던 부품이 사라지고, 사라졌던 이름이 새 행으로 온다
        gone = (await db.execute(select(OntoObject).where(OntoObject.type_slug == "part",
                                                         OntoObject.key == "Display\\Display"))).scalar_one()
        gone.deleted = True
        db.add(OntoObject(type_slug="part", key="cbt:geom2", label="Geom\\솔리드", status="active", source=SOURCE_HUB))
        await db.commit()
        view = (await svc.ontology_view(db, rep))["bridges"]
        assert view["drift"]["add"] == [{"relation": "maps_to", "src_key": "part/22", "dst_key": "cbt:geom2"}]
        assert view["drift"]["drop"] == [{"relation": "maps_to", "src_key": "part/21", "dst_key": "Display\\Display"}]

        same = await svc.attach_ontology(db, rep, FIX.read_bytes())       # 같은 바이트 — 행은 그대로, 다리는 다시
        want = {**EXPECT, "rule": 7, "human": 3, "candidates": 6}
        assert same["already"] is True and _flat(same["bridges"]) == want, same["bridges"]
        pkg = _pkg()
        pkg["_note"] = str(pkg.get("_note") or "") + " (다시 낸 판)"
        again = await svc.attach_ontology(db, rep, _raw(pkg))              # 다른 바이트 — 행을 통째로 바꾼다
        assert again["already"] is False and _flat(again["bridges"]) == want, again["bridges"]

        after = await _lines(db, rep.id)
        assert {k: r.id for k, r in after.items() if r.properties["basis"] == "human"} == human_ids, "사람 선은 그 행 그대로"
        kept = after[("part/1", "cbt:metal-a")].properties
        assert (kept["decided_by"], kept["note"], kept["src_label"]) == ("owner@x", "같은 이름 둘 중 앞", "Front\\Metal")
        assert ("part/22", "cbt:geom2") in after and ("part/21", "Display\\Display") not in after, "규칙 선은 다시 지었다"
        view = (await svc.ontology_view(db, rep))["bridges"]
        assert "drift" not in view and view["stale"] == []
        assert {x["src_key"] for x in view["lines"] if x["basis"] == "human"} == {"part/1", "part/3", "finding/18"}
        assert not [c for c in view["candidates"] if c["src_key"] in ("part/1", "finding/18")], "사람 선이 있으면 후보를 안 낸다"
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
async def test_a_human_line_whose_object_was_renamed_is_kept_and_shown_as_drift(db, mirror):
    """같은 key 의 해석 객체 이름이 다시 반입에서 바뀌면(part/3 「PCB\\PCB」 → 「Battery\\Cell」) 사람 선은 남고 규칙은 그 파트를 그대로
    건너뛰지만, 조용히 따라가지 않는다 — 확정 때 남긴 이름(src_label)과 지금 이름이 다르다고 셈 · 보기의 drift 에 낸다(검토 11-11 P7)."""
    u, rep = await _make(db)
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        got = await br.confirm(db, rep, src_key="part/3", dst_key="cbt:subpkg", by="o")
        await db.commit()
        assert got["ok"] and got["line"]["src_label"] == "PCB\\PCB"
        line_id = (await _lines(db, rep.id))[("part/3", "cbt:subpkg")].id
        db.add(OntoObject(type_slug="part", key="cbt:battery", label="Battery\\Cell", status="active", source=SOURCE_HUB))
        await db.commit()                     # 새 이름과 글자 그대로 맞는 코어 부품 — 규칙이 사람 선을 이기면 이리로 긋는다
        pkg = _pkg()
        for o in pkg["objects"]:
            if o["type"] == "cae_part" and o["key"] == "part/3":
                o["label"] = o["properties"]["name"] = "Battery\\Cell"
        res = await svc.attach_ontology(db, rep, _raw(pkg))
        b = res["bridges"]
        assert (b["human"], b["renamed"], b["stale"]) == (1, 1, 0) and b["by_type"]["cae_part"]["renamed"] == 1, b
        assert "이름 바뀐 사람 선 1" in br.brief(b)
        lines = await _lines(db, rep.id)
        assert lines[("part/3", "cbt:subpkg")].id == line_id, "사람 선은 그 행 그대로"
        assert not [k for k in lines if k[0] == "part/3" and k[1] != "cbt:subpkg"], "사람 선이 이긴다 — 새 이름으로 규칙 선을 긋지 않는다"
        view = (await svc.ontology_view(db, rep))["bridges"]
        assert view["drift"]["renamed"] == [{"relation": "maps_to", "src_key": "part/3", "dst_key": "cbt:subpkg",
                                             "src_label_then": "PCB\\PCB", "src_label_now": "Battery\\Cell"}]
        assert "add" not in view["drift"] and "drop" not in view["drift"] and view["drift"]["note"]
        ln = next(x for x in view["lines"] if x["src_key"] == "part/3")
        assert (ln["basis"], ln["src_label"], ln["renamed_from"]) == ("human", "Battery\\Cell", "PCB\\PCB")
        assert view["stale"] == [] and view["counts"]["renamed"] == 1
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
async def test_a_human_line_whose_object_disappears_is_kept_as_stale(db, mirror):
    u, rep = await _make(db)
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        got = await br.confirm(db, rep, src_key="finding/22", dst_key="cbt:fm-shock", by="owner@x")   # 후보가 아니어도 타입이 맞으면
        await db.commit()
        assert got["ok"] and got["line"]["basis"] == "human"
        title = next(o["label"] for o in _pkg()["objects"] if o["key"] == "finding/22")

        res = await svc.attach_ontology(db, rep, _raw(_without_finding(_pkg(), "finding/22")))
        assert res["counts"]["loaded"]["cae_finding"] == 21
        assert (res["bridges"]["stale"], res["bridges"]["human"]) == (1, 0), res["bridges"]
        assert res["bridges"]["by_type"]["cae_finding"]["stale"] == 1
        assert ("finding/22", "cbt:fm-shock") in await _lines(db, rep.id), "끊긴 사람 선은 지우지 않는다"
        view = (await svc.ontology_view(db, rep))["bridges"]
        assert [(s["src_key"], s["dst_key"], s["basis"], s["src_label"]) for s in view["stale"]] == [
            ("finding/22", "cbt:fm-shock", "human", title)], "사라진 객체의 이름은 확정 때 남긴 것으로 보인다"
        assert not [x for x in view["lines"] if x["src_key"] == "finding/22"]

        gone = await br.remove(db, rep, src_key="finding/22", dst_key="cbt:fm-shock")
        await db.commit()
        assert gone["ok"] and gone["was_stale"] is True and gone["bridges"]["stale"] == 0
        assert ("finding/22", "cbt:fm-shock") not in await _lines(db, rep.id)
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
async def test_types_and_conflicts_are_refused(db, mirror):
    u, rep = await _make(db)
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())

        async def refused(**kw) -> tuple[int, str, str]:
            got = await br.confirm(db, rep, by="owner@x", **kw)
            await db.commit()           # 거절은 아무것도 안 바꾼다 — 잠금만 푼다(되감으면 행 객체가 만료돼 async 에서 못 읽는다)
            assert not got["ok"], got
            return got["status"], got["error"], got["detail"]

        st, err, why = await refused(src_key="part/5", dst_key="cbt:fm-shock")
        assert (st, err) == (422, "wrong_type") and "failure_mode" in why and "part 에만" in why
        assert (await refused(src_key="part/5", dst_key="cbt:pcb", dst_type="failure_mode"))[:2] == (422, "wrong_type")
        assert (await refused(src_key="part/5", dst_key="cbt:pcb", relation="indicates"))[:2] == (422, "wrong_relation")
        st, err, why = await refused(src_key="contact/172", dst_key="cbt:pcb")
        assert (st, err) == (422, "no_bridge") and "maps_to" in why
        assert (await refused(src_key="part/999", dst_key="cbt:pcb"))[:2] == (404, "not_found")
        assert (await refused(src_key="part/5", dst_key="cbt:nope"))[:2] == (422, "not_in_mirror")
        assert (await refused(src_key="part/5", dst_key="cbt:geom"))[:2] == (422, "inactive")

        assert (await br.confirm(db, rep, src_key="part/1", dst_key="cbt:metal-a", by="o"))["ok"]
        await db.commit()
        st, err, _ = await refused(src_key="part/1", dst_key="cbt:metal-b")
        assert (st, err) == (409, "already_bound"), "다대일 — 한 파트에 사람 선 하나(먼저 지운다)"
        again = await br.confirm(db, rep, src_key="part/1", dst_key="cbt:metal-a", by="o")
        assert again["ok"] and again["already"] is True
        # 다대다 — 소견 하나에 사람 선 둘, 규칙 선과도 함께 선다
        assert (await br.confirm(db, rep, src_key="finding/3", dst_key="cbt:fm-motor", by="o"))["ok"]
        assert (await br.confirm(db, rep, src_key="finding/18", dst_key="cbt:fm-motor", by="o"))["ok"]
        both = await br.confirm(db, rep, src_key="finding/18", dst_key="cbt:fm-shock", by="o")
        await db.commit()
        assert both["ok"] and both["bridges"]["human"] == 4
        lines = await _lines(db, rep.id)
        assert lines[("finding/3", "cbt:fm-shock")].properties["basis"] == "rule", "다대다는 규칙 선이 사람 선 곁에 남는다"
        # 규칙 선과 같은 짝을 확정하면 그 선이 사람 선으로 오른다
        up = await br.confirm(db, rep, src_key=f"{rep.id}/part/2", dst_key="cbt:wall", by="o")
        await db.commit()
        assert up["ok"] and up["promoted_rule"] is True
        assert (await _lines(db, rep.id))[("part/2", "cbt:wall")].properties["basis"] == "human"

        no = await br.remove(db, rep, src_key="part/3", dst_key="cbt:pcb")
        assert (no["status"], no["error"]) == (409, "rule_line"), "규칙 선은 지우지 않는다"
        assert (await br.remove(db, rep, src_key="part/3", dst_key="cbt:nope"))["status"] == 404
        await db.commit()
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
async def test_a_broken_bridge_view_does_not_take_the_cae_view_down(db, monkeypatch):
    """다리 보기가 깨져도 파트 판정 · 하중 경로는 선다 — 붙이기가 다리 실패에 안 무너지는 것과 같은 자세."""
    u, rep = await _make(db)
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())

        async def broken(*a, **kw):
            raise RuntimeError("거울 행 꼴이 이상하다")
        monkeypatch.setattr(br, "view", broken)
        view = await svc.ontology_view(db, rep)
        assert view["loaded"] and len(view["parts"]) == 23 and view["load_paths"]
        assert view["bridges"] == {"error": "RuntimeError: 거울 행 꼴이 이상하다"}
    finally:
        await _drop(db, u)


def _pause_in_plan(monkeypatch, who):
    """`who` 세션이 다리 계획에 들어서면(리포트 행 잠금을 쥔 채) 멈춘다 — 다른 길을 그 사이에 끼워 넣어 겹침을 만든다."""
    import asyncio
    paused, go = asyncio.Event(), asyncio.Event()
    orig = br.plan

    async def hook(dbx, report, **kw):
        if dbx is who and not go.is_set():
            paused.set()
            await go.wait()
        return await orig(dbx, report, **kw)
    monkeypatch.setattr(br, "plan", hook)
    return paused, go


@ON_SESSION_LOOP
async def test_a_reattach_during_a_confirm_does_not_deadlock(db, mirror, monkeypatch):
    """확정(B)이 리포트 행 잠금을 쥔 채 다리 계획에 멈춘 사이 새 꾸러미 붙이기(A)가 들어와도 교착이 없다(검토 11-11 P4).
    붙이기도 본 트랜잭션 처음에 같은 잠금을 먼저 잡는다 — 모든 길이 같은 차례로 잠근다. 고치기 전에는 A 가 선을 지운 뒤 FK 검사에서
    B 의 행 잠금을, B 는 규칙 선 지우기에서 A 를 기다려 교착이었다."""
    import asyncio

    from app.database import SessionLocal

    u, rep = await _make(db)
    rid = rep.id
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        pkg = _pkg()
        pkg["_note"] = str(pkg.get("_note") or "") + " (확정과 겹쳐 다시 낸 판)"
        async with SessionLocal() as sa, SessionLocal() as sb:
            ra, rb = await sa.get(ImpactReport, rid), await sb.get(ImpactReport, rid)
            paused, go = _pause_in_plan(monkeypatch, sb)

            async def confirm():
                got = await br.confirm(sb, rb, src_key="part/1", dst_key="cbt:metal-a", by="o")
                await sb.commit()
                return got
            tb = asyncio.create_task(confirm())
            await asyncio.wait_for(paused.wait(), 15)
            ta = asyncio.create_task(svc.attach_ontology(sa, ra, _raw(pkg)))
            await asyncio.sleep(2.0)                      # A 가 막힐 자리까지 가게 둔다
            go.set()
            res = await asyncio.gather(asyncio.wait_for(tb, 40), asyncio.wait_for(ta, 40), return_exceptions=True)
            for s in (sa, sb):
                await s.rollback()
        assert not any(isinstance(x, BaseException) for x in res), res
        confirmed, attached = res
        assert confirmed["ok"] and attached["already"] is False and attached["bridges"]["human"] == 1, attached["bridges"]
        lines = await _lines(db, rid)
        assert lines[("part/1", "cbt:metal-a")].properties["basis"] == "human", "겹친 확정의 사람 선이 다시 붙이기를 넘어 남았다"
        assert _flat(attached["bridges"]) == {**EXPECT, "human": 1, "candidates": EXPECT["candidates"] - 1}
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
async def test_a_confirm_does_not_write_back_a_summary_read_before_a_reattach(db, mirror):
    """확정 요청이 리포트를 읽은 뒤 새 꾸러미가 붙고 다리까지 굳어도, 확정은 잠근 뒤 요약을 다시 읽고 쓴다 — 잠그기 전에 읽은 옛 요약
    (꾸러미 지문 · 파일)으로 새 요약을 덮지 않는다(검토 11-11 P5)."""
    from app.database import SessionLocal

    u, rep = await _make(db)
    rid = rep.id
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        async with SessionLocal() as sb:
            rb = await sb.get(ImpactReport, rid)                 # 확정 요청이 먼저 리포트를 읽었다(옛 요약)
            pkg = _pkg()
            pkg["_note"] = str(pkg.get("_note") or "") + " (확정 전에 새로 낸 판)"
            new = await svc.attach_ontology(db, rep, _raw(pkg))  # 그사이 새 꾸러미가 붙고 다리까지 굳었다
            got = await br.confirm(sb, rb, src_key="part/1", dst_key="cbt:metal-a", by="o")
            await sb.commit()
            assert got["ok"], got
        stored = (await db.execute(select(ImpactReport.ontology).where(ImpactReport.id == rid))).scalar_one()
        assert (stored["sha256"], stored["file_id"]) == (new["sha256"], new["file_id"]), "확정이 새 꾸러미 요약을 옛 값으로 덮었다"
        assert stored["bridges"]["human"] == 1
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
async def test_two_confirms_on_one_many_to_one_part_leave_one_human_line(db, mirror, monkeypatch):
    """양성 대조(검토 P6) — 다대일 파트에 사람 선 둘이 겹쳐 들어와도 잠금이 줄 세워 하나만 서고 다른 하나는 already_bound 다."""
    import asyncio

    from app.database import SessionLocal

    u, rep = await _make(db)
    rid = rep.id
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        async with SessionLocal() as s1, SessionLocal() as s2:
            r1, r2 = await s1.get(ImpactReport, rid), await s2.get(ImpactReport, rid)
            paused, go = _pause_in_plan(monkeypatch, s1)

            async def one(s, r, dst):
                got = await br.confirm(s, r, src_key="part/1", dst_key=dst, by="o")
                await s.commit()
                return got
            t1 = asyncio.create_task(one(s1, r1, "cbt:metal-a"))
            await asyncio.wait_for(paused.wait(), 15)
            t2 = asyncio.create_task(one(s2, r2, "cbt:metal-b"))
            await asyncio.sleep(0.5)
            go.set()
            res = await asyncio.gather(asyncio.wait_for(t1, 30), asyncio.wait_for(t2, 30), return_exceptions=True)
        assert [(x.get("ok"), x.get("error")) for x in res] == [(True, None), (False, "already_bound")], res
        human = [k for k, r in (await _lines(db, rid)).items() if k[0] == "part/1" and r.properties["basis"] == "human"]
        assert human == [("part/1", "cbt:metal-a")]
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
async def test_deleting_the_report_takes_its_human_lines_with_it(db, mirror):
    """사람 선도 리포트의 것이다 — 리포트를 지우면 FK 로 함께 사라진다(지운 리포트를 가리키는 선이 남지 않는다 — 0019 의 교훈)."""
    u, rep = await _make(db)
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        await br.confirm(db, rep, src_key="part/1", dst_key="cbt:metal-a", by="o")
        await db.commit()
        rid = rep.id
        assert len(await _lines(db, rid)) == 9
        await db.execute(delete(ImpactReport).where(ImpactReport.id == rid))
        await db.commit()
        assert await _lines(db, rid) == {}
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
async def test_bridge_lines_stay_out_of_the_public_ontology_views(db, mirror):
    """일반 보기(로그인한 누구나)의 코어 객체 선에 리포트의 다리 선이 새지 않는다 — 리포트 가시성(10-31 결정)."""
    import httpx
    from httpx import ASGITransport

    from app.main import create_app
    from app.modules.ontology.routes import require_ontology
    from app.shared.auth import get_current_user

    u, rep = await _make(db)
    stranger, _ = await _make(db, with_report=False)
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        await br.confirm(db, rep, src_key="part/1", dst_key="cbt:metal-a", by="o")
        await db.commit()
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: stranger
        app.dependency_overrides[require_ontology] = lambda: {"enabled": True}
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            for key in ("cbt:pcb", "cbt:metal-a"):
                got = (await c.get(f"/api/v1/ontology/objects/part/{key}")).json()["data"]
                assert got["object"]["key"] == key and got["in"] == [], got["in"]
    finally:
        await _drop(db, u, stranger)


# ── REST — 사람 선 확정 · 지우기(리포트 주인 · 시스템 관리자, 사용자 결정 11-10) ─────────────────────

AFF = "CAEG"
SECRET = "cbt-gateway-secret"


def _aff_headers(email: str) -> dict:
    """게이트웨이가 찍은 소속 증명(app/shared/affiliation.py 의 v1 꼴) — 같은 소속 읽기 사용자를 만든다."""
    import hashlib
    import hmac
    import time
    exp = int(time.time()) + 600
    sig = hmac.new(SECRET.encode(), f"v1|{email.strip().lower()}|{AFF}|{exp}".encode(), hashlib.sha256).hexdigest()
    return {"X-Heax-User-Affiliation": AFF, "X-Heax-Aff-Proof": f"v1.{exp}.{sig}"}


def _client(app):
    import httpx
    from httpx import ASGITransport
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


@ON_SESSION_LOOP
async def test_only_the_owner_and_a_system_admin_confirm_or_delete(db, mirror, monkeypatch):
    from app.config import settings
    from app.main import create_app
    from app.shared.auth import get_current_user

    monkeypatch.setattr(settings, "heax_gateway_secret", SECRET)
    owner, rep = await _make(db, shared=AFF)
    reader, _ = await _make(db, with_report=False)
    stranger, _ = await _make(db, with_report=False)
    admin, _ = await _make(db, admin=True, with_report=False)
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        app = create_app()
        url = f"/api/v1/reports/{rep.id}/cae/bridges"
        pick = {"src_key": "part/1", "dst_key": "cbt:metal-a", "dst_type": "part", "note": "앞의 것"}
        async with _client(app) as c:
            app.dependency_overrides[get_current_user] = lambda: reader
            seen = await c.get(f"/api/v1/reports/{rep.id}/cae", headers=_aff_headers(reader.email))
            assert seen.status_code == 200 and seen.json()["data"]["bridges"]["candidates"], "같은 소속은 다리 후보를 본다"
            r = await c.post(url, json=pick, headers=_aff_headers(reader.email))
            assert r.status_code == 403 and "리포트 주인과 시스템 관리자" in r.json()["message"], r.text
            app.dependency_overrides[get_current_user] = lambda: stranger
            assert (await c.post(url, json=pick)).status_code == 404, \
                "소속이 다른(증명 없는) 사람 — 읽지도 못하니 리포트가 있다는 것도 알리지 않는다"

            app.dependency_overrides[get_current_user] = lambda: owner
            r = await c.post(url, json=pick)
            assert r.status_code == 200, r.text
            got = r.json()["data"]
            assert got["line"]["basis"] == "human" and got["line"]["decided_by"] == owner.email and got["bridges"]["human"] == 1

            app.dependency_overrides[get_current_user] = lambda: reader
            r = await c.delete(url, params={"src_key": "part/1", "dst_key": "cbt:metal-a"}, headers=_aff_headers(reader.email))
            assert r.status_code == 403, r.text
            app.dependency_overrides[get_current_user] = lambda: admin
            r = await c.delete(url, params={"src_key": "part/1", "dst_key": "cbt:metal-a"})
            assert r.status_code == 200 and r.json()["data"]["bridges"]["human"] == 0, r.text
            r = await c.post(url, json={"src_key": "part/4", "dst_key": "cbt:pkg1"})
            assert r.status_code == 200 and r.json()["data"]["line"]["decided_by"] == admin.email, "관리자는 남의 리포트에도"
        lines = await _lines(db, rep.id)
        assert ("part/1", "cbt:metal-a") not in lines and lines[("part/4", "cbt:pkg1")].properties["basis"] == "human"
    finally:
        await _drop(db, owner, reader, stranger, admin)


@ON_SESSION_LOOP
async def test_rest_refusals_carry_their_status_and_reason(db, mirror):
    from app.main import create_app
    from app.shared.auth import get_current_user

    owner, rep = await _make(db)
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: owner
        url = f"/api/v1/reports/{rep.id}/cae/bridges"
        async with _client(app) as c:
            async def post(**body):
                r = await c.post(url, json=body)
                return r.status_code, r.json().get("message") or ""
            st, why = await post(src_key="part/5", dst_key="cbt:fm-shock")
            assert st == 422 and why.startswith("wrong_type") and "part 에만" in why
            assert (await post(src_key="part/5", dst_key="cbt:pcb", dst_type="analysis_method"))[0] == 422
            assert (await post(src_key="contact/172", dst_key="cbt:pcb"))[1].startswith("no_bridge")
            assert (await post(src_key="part/999", dst_key="cbt:pcb"))[0] == 404
            assert (await post(src_key="campaign", dst_key="cbt:am-drop", relation="follows_method"))[0] == 200
            assert (await post(src_key="part/1", dst_key="cbt:metal-a"))[0] == 200
            st, why = await post(src_key="part/1", dst_key="cbt:metal-b")
            assert st == 409 and why.startswith("already_bound")
            r = await c.delete(url, params={"src_key": "part/3", "dst_key": "cbt:pcb"})
            assert r.status_code == 409 and r.json()["message"].startswith("rule_line")
            assert (await c.delete(url, params={"src_key": "part/3", "dst_key": "cbt:zzz"})).status_code == 404
            # 꾸러미를 안 실은 리포트에는 확정할 것이 없다
            bare = ImpactReport(id=ulid.new().str, session_id=rep.session_id, user_id=owner.id, kind="sphere", n_cases=0)
            db.add(bare)
            await db.commit()
            r = await c.post(f"/api/v1/reports/{bare.id}/cae/bridges", json={"src_key": "part/1", "dst_key": "cbt:pcb"})
            assert r.status_code == 409 and "꾸러미부터" in r.json()["message"]
    finally:
        await _drop(db, owner)


# ── 다리가 깨져도 붙이는 길은 선다(검토 11-11 P1 · P2) — 다시 짓기가 부르는 쪽 세션을 되감지 않는다 ─────────────────

SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")


def _bundle_for(html: bytes) -> bytes:
    """sphere 샘플 HTML + 그 각도 키로 고친 v14 꾸러미를 한 묶음(zip)으로 — 번들 반입이 같은 이름 줄기의 꾸러미를 싣는다."""
    import hashlib
    import io
    import zipfile

    from app.reports import parser
    keys = [c["case_key"] for c in parser.parse_html(html.decode("utf-8", "replace"), kind_hint="sphere")["cases"]]
    pkg = _pkg()
    pkg["source"]["html"] = {"file": "report.html", "sha256": hashlib.sha256(html).hexdigest()}
    runs = iter(keys)
    for o in pkg["objects"]:
        if o["type"] == "cae_run":
            o["properties"]["case_key"] = next(runs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("report.html", html)
        z.writestr("report.ontology.json", json.dumps(pkg))
    return buf.getvalue()


def _broken_plan(monkeypatch) -> None:
    async def boom(*a, **kw):
        raise RuntimeError("다리 계획이 깨졌다(시험)")
    monkeypatch.setattr(br, "plan", boom)


@ON_SESSION_LOOP
@pytest.mark.skipif(not SPHERE.exists(), reason="sphere 샘플 없음")
@pytest.mark.parametrize("broken", [False, True])
async def test_bundle_intake_survives_a_bridge_failure(db, monkeypatch, broken):
    """번들 반입은 꾸러미를 붙인 뒤 리포트 칸을 읽어 응답을 짓는다 — 다리가 세션을 되감으면 그 칸이 만료돼 500 이었다(P1)."""
    import httpx
    from httpx import ASGITransport

    from app.main import create_app
    from app.shared.auth import get_current_user

    u, _ = await _make(db, with_report=False)
    try:
        if broken:
            _broken_plan(monkeypatch)
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: u
        async with httpx.AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t") as c:
            r = await c.post("/api/v1/reports/intake",
                             files={"file": ("bundle.zip", _bundle_for(SPHERE.read_bytes()), "application/zip")})
        assert r.status_code == 201, (r.status_code, r.text[:600])
        onto = r.json()["data"]["ontology"]
        assert onto["ok"] is True and onto["loaded"]["cae_part"] == 23
        if broken:
            assert onto["bridges"] == {"error": "RuntimeError: 다리 계획이 깨졌다(시험)"}
        else:
            assert {"rule", "human", "stale", "candidates", "unmatched", "unnamed"} <= set(onto["bridges"])
        rid = r.json()["data"]["report_id"]
        stored = (await db.execute(select(ImpactReport.ontology).where(ImpactReport.id == rid))).scalar_one()
        assert stored["counts"]["loaded"]["cae_part"] == 23, "꾸러미 행은 다리와 상관없이 굳었다"
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
async def test_rest_attach_survives_a_bridge_failure(db, monkeypatch):
    import httpx
    from httpx import ASGITransport

    from app.main import create_app
    from app.shared.auth import get_current_user

    u, rep = await _make(db)
    try:
        _broken_plan(monkeypatch)
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: u
        async with httpx.AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t") as c:
            r = await c.post(f"/api/v1/reports/{rep.id}/cae",
                             files={"file": ("report.ontology.json", FIX.read_bytes(), "application/json")})
        assert r.status_code == 200, r.text[:400]
        got = r.json()["data"]
        assert got["bridges"] == {"error": "RuntimeError: 다리 계획이 깨졌다(시험)"} and got["counts"]["loaded"]["cae_part"] == 23
        assert "코어 다리를 못 지었다" in r.json()["message"]
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
async def test_a_broken_bridge_definition_fails_only_the_bridges(db, mirror, monkeypatch):
    """다리 정의(dynaforge-core.json)를 못 읽어도 꾸러미는 실리고, 다시 붙일 때 사람 선은 사람 표시만으로 남는다."""
    u, rep = await _make(db)
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        assert (await br.confirm(db, rep, src_key="part/1", dst_key="cbt:metal-a", by="o"))["ok"]
        await db.commit()

        def unreadable():
            raise ValueError("정의 파일을 못 읽었다(시험)")
        monkeypatch.setattr(br, "bridges", unreadable)
        pkg = _pkg()
        pkg["_note"] = str(pkg.get("_note") or "") + " (정의가 깨진 뒤 다시 낸 판)"
        got = await svc.attach_ontology(db, rep, _raw(pkg))
        assert got["already"] is False and got["counts"]["loaded"]["cae_part"] == 23
        assert got["bridges"] == {"error": "ValueError: 정의 파일을 못 읽었다(시험)"}
        human = (await db.execute(select(OntoRelation).where(
            OntoRelation.report_id == rep.id, OntoRelation.src_key == f"{rep.id}/part/1"))).scalars().all()
        assert [(h.dst_key, h.properties["basis"]) for h in human] == [("cbt:metal-a", "human")], "사람 선은 남는다"
        rule = (await db.execute(select(OntoRelation).where(
            OntoRelation.report_id == rep.id, OntoRelation.properties["basis"].astext == "rule"))).scalars().all()
        assert rule == [], "규칙 선은 꾸러미 선과 함께 걷혔고 다리가 깨져 다시 서지 않았다"
    finally:
        await _drop(db, u)


# ── 오류는 짧은 꼴로(검토 2차 11-11 항목 7) ─────────────────────────────────────────────────────

def test_an_error_goes_out_as_class_and_one_line_without_sql_or_values():
    """응답 · 7-1 원장의 오류(`bridges.error` · 보기 · 꾸러미 실패 까닭)는 「클래스: 한 줄」(300자 안) — SQL 문 · 매개변수 · DETAIL(값) ·
    배경 링크를 싣지 않는다(전문은 서버 로그). 예전에는 SQLAlchemy 오류 전문(약 1.6 KB)이 그대로 실렸다."""
    from sqlalchemy.exc import IntegrityError, PendingRollbackError

    orig = Exception("<class 'asyncpg.exceptions.UniqueViolationError'>: duplicate key value violates unique constraint "
                     "\"uq_onto_relations_edge\"\nDETAIL:  Key (src_key)=(비밀-값) already exists.")
    exc = IntegrityError("INSERT INTO onto_relations (relation, src_key) VALUES ($1, $2)", ("maps_to", "비밀-값"), orig)
    assert "[SQL" in str(exc) and "비밀-값" in str(exc), "전문은 문장 · 값까지 든다"
    assert br.short_error(exc) == ('IntegrityError: UniqueViolationError: duplicate key value violates unique constraint '
                                   '"uq_onto_relations_edge"')
    pending = PendingRollbackError("Can't reconnect until invalid transaction is rolled back.  Please rollback() fully "
                                   "before proceeding", code="8s2b")
    assert "Background on this error" in str(pending)
    assert br.short_error(pending) == ("PendingRollbackError: Can't reconnect until invalid transaction is rolled back.  "
                                       "Please rollback() fully before proceeding")
    assert br.short_error(RuntimeError("x" * 1000)) == ("RuntimeError: " + "x" * 1000)[:300]
    assert br.short_error(RuntimeError()) == "RuntimeError"


# ── 꾸러미 붙이기는 리포트 행 잠금 아래 한 트랜잭션(검토 2차 11-11 항목 2 · 3 · 4) ─────────────────────────────

def _dup_edge(monkeypatch) -> None:
    """꾸러미 선 하나를 두 번 — 검사를 지난 뒤 본 쓰기가 DB 유일 제약에서 깨진다(다리 밖의 실패)."""
    orig = op.check

    def dup(*a, **k):
        got = orig(*a, **k)
        got["edges"] = got["edges"] + got["edges"][:1]
        return got
    monkeypatch.setattr(op, "check", dup)


async def _package_files(db, sid: str, rid: str) -> list[str]:
    return sorted((await db.execute(select(SessionFile.filename).where(
        SessionFile.session_id == sid, SessionFile.filename.like(f"ontology/{rid}/%")))).scalars().all())


def _disk_files(uid: int, sid: str, rid: str) -> list[str]:
    d = storage.session_abs_dir(uid, sid) / "ontology" / rid
    return sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file()) if d.exists() else []


def _variant(tag: str) -> bytes:
    pkg = _pkg()
    pkg["_note"] = str(pkg.get("_note") or "") + f" ({tag})"
    return _raw(pkg)


async def _count(db, model, *where) -> int:
    from sqlalchemy import func
    return (await db.execute(select(func.count()).select_from(model).where(*where))).scalar_one()


def _columns_expired(obj) -> set[str]:
    """만료된 칸(관계 말고 열) — 비어 있어야 부르는 쪽이 async 에서 그 객체를 계속 읽는다."""
    from sqlalchemy import inspect
    return inspect(obj).expired_attributes & {c.key for c in inspect(type(obj)).column_attrs}


@ON_SESSION_LOOP
async def test_a_package_write_that_fails_rolls_back_and_leaves_no_file(db, monkeypatch):
    """본 쓰기가 DB 에서 깨지면(꾸러미 선 둘 → 유일 제약) 되감고 이번 파일 행 · 디스크 파일을 걷는다 — 옛 꾸러미 · 행 · 요약이 그대로이고
    리포트 객체 · 세션을 계속 쓸 수 있다. REST 는 500 과 짧은 까닭. 예전에는 깨진 커밋 뒤 만료된 객체를 읽다 PendingRollbackError 가 나
    정리가 돌지 않았고 파일 행 · 디스크 파일이 남았다."""
    import httpx
    from httpx import ASGITransport
    from sqlalchemy import text

    from app.main import create_app
    from app.shared.auth import get_current_user

    u, rep = await _make(db)
    uid, rid, sid = u.id, rep.id, rep.session_id
    try:
        first = await svc.attach_ontology(db, rep, FIX.read_bytes())
        files, disk = await _package_files(db, sid, rid), _disk_files(uid, sid, rid)
        rows = await _count(db, OntoObject, OntoObject.report_id == rid)
        assert files == [first["file"]] and len(disk) == 1
        _dup_edge(monkeypatch)
        raw = _variant("선이 겹친 판")
        with pytest.raises(svc.OntoAttachError) as err:
            await svc.attach_ontology(db, rep, raw)
        why = str(err.value)
        assert "UniqueViolationError" in why and "[SQL" not in why and "INSERT" not in why and len(why) <= 300, why
        assert not _columns_expired(rep), "되감은 뒤 리포트 객체를 다시 읽어 둔다"
        assert rep.ontology["sha256"] == first["sha256"]
        assert (await db.execute(text("select 1"))).scalar_one() == 1
        assert await _package_files(db, sid, rid) == files, "이번 파일 행이 남았다"
        assert _disk_files(uid, sid, rid) == disk, "이번 디스크 파일이 남았다"
        stored = (await db.execute(select(ImpactReport.ontology).where(ImpactReport.id == rid))).scalar_one()
        assert (stored["sha256"], stored["file_id"]) == (first["sha256"], first["file_id"])
        assert await _count(db, OntoObject, OntoObject.report_id == rid) == rows

        await db.refresh(u)                   # 되감기는 이 세션의 사용자 객체도 만료시켰다 — 라우트가 읽는다
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: u
        async with httpx.AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t") as c:
            r = await c.post(f"/api/v1/reports/{rid}/cae", files={"file": ("report.ontology.json", raw, "application/json")})
        assert r.status_code == 500 and r.json()["message"].startswith("온톨로지 꾸러미를 싣지 못했다"), r.text[:400]
        assert "UniqueViolationError" in r.json()["message"] and "[SQL" not in r.text
        assert await _package_files(db, sid, rid) == files and _disk_files(uid, sid, rid) == disk
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
@pytest.mark.skipif(not SPHERE.exists(), reason="sphere 샘플 없음")
async def test_bundle_intake_answers_with_an_ontology_error_when_the_package_write_fails(db, monkeypatch):
    """번들 반입의 리포트 · 세션은 꾸러미보다 먼저 굳는다 — 꾸러미 쓰기가 깨져도 500 이 아니라 반입 결과(201)에 `ontology` 오류를 싣는다.
    예전에는 500 이라 클라이언트가 다시 보내 리포트 · 세션이 둘씩 남았다."""
    import httpx
    from httpx import ASGITransport

    from app.main import create_app
    from app.shared.auth import get_current_user

    u, _ = await _make(db, with_report=False)
    uid = u.id
    try:
        _dup_edge(monkeypatch)
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: u
        async with httpx.AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t") as c:
            r = await c.post("/api/v1/reports/intake",
                             files={"file": ("bundle.zip", _bundle_for(SPHERE.read_bytes()), "application/zip")})
        assert r.status_code == 201, (r.status_code, r.text[:600])
        data = r.json()["data"]
        onto = data["ontology"]
        assert onto["ok"] is False and "UniqueViolationError" in onto["error"], onto
        assert "[SQL" not in onto["error"] and len(onto["error"]) <= 300 and "다시 보내지 말고" in onto["why"], onto
        assert data["kind"] == "sphere" and data["n_cases"] > 0, "응답은 굳은 반입 그대로다"
        assert await _count(db, ImpactReport, ImpactReport.user_id == uid) == 1
        assert await _count(db, Session, Session.user_id == uid) == 1
        rid = data["report_id"]
        assert (await db.execute(select(ImpactReport.ontology).where(ImpactReport.id == rid))).scalar_one() is None
        assert await _package_files(db, data["session_id"], rid) == [] and _disk_files(uid, data["session_id"], rid) == []
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
@pytest.mark.parametrize("path", ["attach", "confirm", "remove"])
async def test_a_write_queued_behind_a_report_delete_is_a_404_and_writes_nothing(db, mirror, monkeypatch, path):
    """리포트 지우기가 커밋 전에 행을 쥔 동안 들어온 쓰기(꾸러미 붙이기 · 사람 선 확정 · 지우기) — 지우기가 굳으면 잠글 행이 없어 404 다.
    예전에는 잠금이 조용히 지나가 쓰기가 FK 에서 깨지고(500) 붙이기는 꾸러미 파일을 남겼다."""
    import asyncio

    import httpx
    from httpx import ASGITransport

    from app.database import SessionLocal
    from app.main import create_app
    from app.shared.auth import get_current_user

    u, rep = await _make(db)
    uid, rid, sid = u.id, rep.id, rep.session_id
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        if path == "remove":
            assert (await br.confirm(db, rep, src_key="part/1", dst_key="cbt:metal-a", by="o"))["ok"]
            await db.commit()
        before = await _package_files(db, sid, rid)
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: u
        url = f"/api/v1/reports/{rid}"
        async with SessionLocal() as sx, httpx.AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False),
                                                            base_url="http://t") as c:
            rx = await sx.get(ImpactReport, rid)
            gate, real_commit = asyncio.Event(), sx.commit

            async def held_commit():                  # 지우기의 문장은 다 나갔고(행을 쥐었다) 커밋 앞에서 기다린다
                await sx.flush()
                await gate.wait()
                await real_commit()
            monkeypatch.setattr(sx, "commit", held_commit)
            td = asyncio.create_task(svc.delete_report(sx, rx))
            await asyncio.sleep(0.5)
            if path == "attach":
                call = c.post(f"{url}/cae", files={"file": ("report.ontology.json", _variant("지우는 중"), "application/json")})
            elif path == "confirm":
                call = c.post(f"{url}/cae/bridges", json={"src_key": "part/2", "dst_key": "cbt:wall"})
            else:
                call = c.delete(f"{url}/cae/bridges", params={"src_key": "part/1", "dst_key": "cbt:metal-a"})
            tw = asyncio.create_task(call)
            await asyncio.sleep(1.0)
            assert not tw.done(), "쓰기가 지우기의 행 잠금을 기다리지 않았다"
            gate.set()
            await asyncio.wait_for(td, 30)
            r = await asyncio.wait_for(tw, 30)
        assert r.status_code == 404 and "지워졌다" in r.json()["message"], (r.status_code, r.text[:400])
        assert await _count(db, ImpactReport, ImpactReport.id == rid) == 0
        left = await _package_files(db, sid, rid)
        assert set(left) <= set(before), f"쓰기가 꾸러미 파일을 남겼다: {sorted(set(left) - set(before))}"
        assert len(_disk_files(uid, sid, rid)) <= len(before), "쓰기가 디스크 파일을 남겼다"
    finally:
        await _drop(db, u)


@ON_SESSION_LOOP
async def test_already_is_decided_on_the_summary_read_after_the_lock(db):
    """「이미 실었다」 는 잠근 뒤 다시 읽은 요약으로 정한다 — B 가 리포트를 읽은 뒤 A 가 다른 꾸러미 Z 를 붙였으면, B 가 붙이는 X 는
    (B 가 본 옛 요약과 같아도) 정말로 싣는다. 거꾸로 지금 X 가 실려 있으면 already 로 **지금** 요약(파일)을 돌려준다. 예전에는 B 가
    잠그기 전에 읽은 요약으로 already 와 옛 X 요약을 냈고 DB 에는 Z 가 남았다."""
    from app.database import SessionLocal

    u, rep = await _make(db)
    rid, sid = rep.id, rep.session_id
    try:
        x = await svc.attach_ontology(db, rep, FIX.read_bytes())
        z_raw = _variant("Z")
        async with SessionLocal() as sb:
            rb = await sb.get(ImpactReport, rid)                          # B 가 읽었다(요약 X)
            await svc.attach_ontology(db, rep, z_raw)                     # 그사이 A 가 Z 를 붙였다
            got = await svc.attach_ontology(sb, rb, FIX.read_bytes())     # B 가 X 를 붙인다
        stored = (await db.execute(select(ImpactReport.ontology).where(ImpactReport.id == rid))).scalar_one()
        assert got["already"] is False and got["sha256"] == x["sha256"] == stored["sha256"], (got["already"], stored["sha256"])
        assert stored["file_id"] == got["file_id"] != x["file_id"]
        assert await _package_files(db, sid, rid) == [got["file"]], "Z 의 파일은 지난 꾸러미로 지워졌다"

        async with SessionLocal() as sc:
            rc = await sc.get(ImpactReport, rid)                          # C 가 읽었다(요약 X — 그때 파일)
            await svc.attach_ontology(db, rep, z_raw)                     # Z 를 붙였다가
            now = await svc.attach_ontology(db, rep, FIX.read_bytes())    # 다시 X — 새 파일
            same = await svc.attach_ontology(sc, rc, FIX.read_bytes())
        assert same["already"] is True and same["file_id"] == now["file_id"] != got["file_id"], (same["file_id"], now["file_id"])
    finally:
        await _drop(db, u)


# ── 다리 커밋이 깨지면 되감고 다시 읽는다(검토 2차 11-11 항목 6) ─────────────────────────────────────────

async def _kill_connection(dbx) -> None:
    """이 세션이 쥔 DB 연결을 서버 쪽에서 끊는다(pg_terminate_backend — 자기 연결만) — 커밋 중 연결이 끊긴 것을 만든다."""
    import asyncio

    import asyncpg
    from sqlalchemy import text

    from app.config import settings
    pid = (await dbx.execute(text("select pg_backend_pid()"))).scalar_one()
    c = await asyncpg.connect(settings.database_url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        await c.fetchval("select pg_terminate_backend($1)", pid)
    finally:
        await c.close()
    await asyncio.sleep(0.2)


@ON_SESSION_LOOP
async def test_a_lost_commit_after_the_rebuild_rolls_back_and_rereads(db, monkeypatch):
    """같은 꾸러미 다시 붙이기의 다리 커밋에서 연결이 끊기면 — 되감고 리포트를 다시 읽어 두고 짧은 오류를 돌려준다. 그 뒤 세션 · 리포트
    객체를 그대로 쓸 수 있다. 예전에는 깨진 트랜잭션을 둔 채 돌아와 부르는 쪽의 다음 문장이 깨졌다(7-1 은 원장을 못 적었다)."""
    from sqlalchemy import text

    u, rep = await _make(db)
    try:
        first = await svc.attach_ontology(db, rep, FIX.read_bytes())
        real_commit = db.commit

        async def lost_commit():
            monkeypatch.setattr(db, "commit", real_commit)
            await _kill_connection(db)
            await real_commit()
        monkeypatch.setattr(db, "commit", lost_commit)
        got = await svc.attach_ontology(db, rep, FIX.read_bytes())      # 같은 바이트 — 다리만 다시 짓고 커밋한다
        assert got["already"] is True and set(got["bridges"]) == {"error"}, got["bridges"]
        err = got["bridges"]["error"]
        assert "[SQL" not in err and "Background" not in err and len(err) <= 300, err
        assert not _columns_expired(rep) and rep.ontology["sha256"] == first["sha256"]
        assert (await db.execute(text("select 1"))).scalar_one() == 1
        await db.commit()
        assert "error" not in (await svc.attach_ontology(db, rep, FIX.read_bytes()))["bridges"], "다음 붙이기는 다시 짓는다"
    finally:
        await _drop(db, u)


# ── 이름 바뀐 사람 선은 부르는 이름으로 · 다시 확정하면 풀린다(검토 2차 11-11 항목 8) ───────────────────────────────

@ON_SESSION_LOOP
async def test_renamed_follows_the_name_the_rule_matches_on_and_a_reconfirm_clears_it(db, mirror):
    """renamed 는 규칙이 견주는 칸(파트 name · 소견 title · 캠페인 scenario_kind)으로 센다 — 캠페인 이름(label)만 바뀌고 종류가 그대로면
    같은 다리다. 같은 짝을 다시 확정하면 남긴 이름을 지금 것으로 맞춰(`relabeled`) 그 표시가 풀린다. 예전에는 label 로 견줘 캠페인 이름만
    바뀌어도 renamed 였고, 다시 확정해도 남긴 이름을 안 고쳐 표시가 안 풀렸다."""
    u, rep = await _make(db)
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        c = await br.confirm(db, rep, src_key="campaign", dst_key="cbt:am-drop", by="o")      # 규칙 선을 사람 선으로
        f = await br.confirm(db, rep, src_key="finding/1", dst_key="cbt:fm-motor", by="o")
        await db.commit()
        assert c["ok"] and c["promoted_rule"] and f["ok"]
        lines = await _lines(db, rep.id)
        assert lines[("campaign", "cbt:am-drop")].properties["src_label"] == "drop_all_angle", "캠페인은 종류를 남긴다"
        old_title = lines[("finding/1", "cbt:fm-motor")].properties["src_label"]
        pkg = _pkg()
        for o in pkg["objects"]:
            if o["type"] == "cae_campaign":
                o["label"] = "다른 캠페인 이름"                             # 이름만 — 종류(부르는 칸)는 그대로
            if o["type"] == "cae_finding" and o["key"] == "finding/1":
                o["label"] = o["properties"]["title"] = "다른 소견 제목"
        b = (await svc.attach_ontology(db, rep, _raw(pkg)))["bridges"]
        assert (b["renamed"], b["by_type"]["cae_campaign"]["renamed"], b["by_type"]["cae_finding"]["renamed"]) == (1, 0, 1), b
        view = (await svc.ontology_view(db, rep))["bridges"]
        assert view["drift"]["renamed"] == [{"relation": "indicates", "src_key": "finding/1", "dst_key": "cbt:fm-motor",
                                             "src_label_then": old_title, "src_label_now": "다른 소견 제목"}]

        again = await br.confirm(db, rep, src_key="finding/1", dst_key="cbt:fm-motor", by="other@x")   # 사람이 「같은 것」 이라 한다
        await db.commit()
        assert again["ok"] and again["already"] and again["relabeled"] == {"was": old_title, "now": "다른 소견 제목"}, again
        assert again["bridges"]["renamed"] == 0 and "renamed_from" not in again["line"]
        kept = (await _lines(db, rep.id))[("finding/1", "cbt:fm-motor")].properties
        assert (kept["src_label"], kept["decided_by"]) == ("다른 소견 제목", "other@x")
        view = (await svc.ontology_view(db, rep))["bridges"]
        assert "drift" not in view and view["counts"]["renamed"] == 0
        same = await br.confirm(db, rep, src_key="campaign", dst_key="cbt:am-drop", by="o")
        await db.commit()
        assert same["already"] and "relabeled" not in same, "이름이 그대로면 고칠 것이 없다"
    finally:
        await _drop(db, u)


# ── 끝이 거울에 없는 우리 별칭도 엇갈림이다(검토 2차 11-11 항목 9) ─────────────────────────────────────────

def test_an_alias_whose_target_is_not_in_the_mirror_is_a_disagreement():
    """우리 별칭의 끝이 거울에 없어도(지워짐 · 허브가 바꾼 옛 key) 사람이 그 글을 다른 객체로 정했다는 기록이다 — 다른 칸이 한 객체로 맞아도
    규칙 선이 아니라 후보다. 그 끝은 확정할 수 없어 후보로 내지 않는다. 다른 데 맞는 것이 없으면 못 붙임이다."""
    p = _pool(objs={"Q1": "Holder"})
    p.stray["Holder"] = "Q-gone"
    got = br.match(p, "Holder")
    assert got["verdict"] == "candidates" and "key" not in got
    assert [(o["key"], o["why"]) for o in got["options"]] == [("Q1", br._WHY_STRAY.format(key="Q-gone") + "(이름)")]
    p.stray["Lone"] = "Q-gone"
    assert br.match(p, "Lone")["verdict"] == "unmatched"


@ON_SESSION_LOOP
async def test_a_stray_alias_turns_an_exact_line_into_a_candidate(db, mirror):
    """실물 꾸러미로 — part/3(PCB\\PCB)은 이름으로 cbt:pcb 에 규칙 선이었다. 같은 글을 거울에 없는 key 로 가리키는 우리 별칭이 생기면
    규칙 선이 아니라 후보다. 허브가 key 를 바꿔 옛 key 를 가리키는 별칭도 같다(옛 key 를 따라가지 않는다)."""
    gone = ("part", "cbt:gone-pcb")
    u, rep = await _make(db)
    try:
        db.add(OntoAlias(type_slug="part", alias="PCB\\PCB", key=gone[1], source="manual", confirmed_by="test", note=TAG))
        db.add(OntoObject(type_slug="part", key="cbt:holder", label="CBT Holder", status="active", source=SOURCE_HUB))
        db.add(OntoObject(type_slug="part", key="cbt:holder-new", label="새 key 홀더", status="active", source=SOURCE_HUB))
        db.add(OntoPreviousKey(type_slug="part", old_key="cbt:holder-old", key="cbt:holder-new"))
        db.add(OntoAlias(type_slug="part", alias="CBT Holder", key="cbt:holder-old", source="manual", confirmed_by="test",
                         note=TAG))
        await db.commit()
        got = await svc.attach_ontology(db, rep, FIX.read_bytes())
        assert _flat(got["bridges"]) == {**EXPECT, "rule": EXPECT["rule"] - 1, "candidates": EXPECT["candidates"] + 1}, got["bridges"]
        assert ("part/3", "cbt:pcb") not in await _lines(db, rep.id)
        view = (await svc.ontology_view(db, rep))["bridges"]
        c = next(x for x in view["candidates"] if x["src_key"] == "part/3")
        assert [(o["key"], o["why"]) for o in c["options"]][:1] == [("cbt:pcb", br._WHY_STRAY.format(key=gone[1]) + "(이름)")], c
        hit = br.match(await br._pool(db, "part"), "CBT Holder")
        assert hit["verdict"] == "candidates" and [o["key"] for o in hit["options"]] == ["cbt:holder"], hit
    finally:
        await db.rollback()
        await db.execute(delete(OntoObject).where(OntoObject.key.in_(["cbt:holder", "cbt:holder-new"]),
                                                  OntoObject.report_id.is_(None)))
        await db.execute(delete(OntoPreviousKey).where(OntoPreviousKey.old_key == "cbt:holder-old"))
        await db.commit()
        await _drop(db, u)
