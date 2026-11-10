"""정의 파일의 꼴 — **허브의 것과 우리 것을 같은 눈으로** 본다.

여기서 지키는 것 둘.
① 우리 정의가 흠 없이 통과한다.
② ★**허브의 `plm-core.json`·`work-core.json` 을 그대로 읽어 통과시킨다.** 그것이 "꼴을
   맞췄다" 의 증거다 — 안 되면 나중에 정의를 주고받을 때 변환기가 필요해진다.

그리고 판별력을 본다 — 통과만 확인하는 검증기는 **아무것도 안 보는 것과 구별되지 않는다.**
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json

import pytest

from app.runner.ontology_def import (CARDINALITIES, DATA_TYPES, EXTERNAL_TYPES, load,
                                     validate)

ROOT = Path(__file__).resolve().parents[3]
OURS = ROOT / "platform" / "core" / "ontology" / "dynaforge-core.json"
CAE = OURS.with_name("dynaforge-cae.json")      # 해석 어휘 — 생산 쪽과 바이트 사본(고치지 않는다). 다리의 출발 타입이 여기 있다
HUB = ROOT / "external" / "StandardPlatform" / "pipeline" / "core"


def _cae_types() -> set[str]:
    return {t["slug"] for t in json.loads(CAE.read_text(encoding="utf-8"))["types"]}


# ── ① 우리 정의 ────────────────────────────────────────────────────────────

def test_our_definition_passes_cleanly():
    """다리(cae_* → 코어)의 출발 타입은 해석 어휘 파일에 있다 — 두 파일을 함께 아는 눈으로 본다(합친 검사는 test_cae_package)."""
    doc, rep = load(OURS, known_types=set(EXTERNAL_TYPES) | _cae_types())
    assert rep.ok, rep.faults
    assert not rep.notes, f"모르는 키가 남았다: {rep.notes}"
    assert [t["slug"] for t in doc["types"]] == ["dev_revision"]


def test_alone_the_bridges_point_at_types_this_file_does_not_define():
    """판별력 — 해석 어휘를 모르는 눈에는 다리 출발 타입이 「아는 타입이 아니다」 로 걸린다(검사를 건너뛴 것이 아니다)."""
    _, rep = load(OURS)
    assert not rep.ok
    assert {f.split(":")[0] for f in rep.faults} == {"relation_types/maps_to", "relation_types/indicates",
                                                      "relation_types/follows_method"}, rep.faults
    assert all("cae_" in f for f in rep.faults), rep.faults


# ── 코어와 잇기 SRC-08 — 해석 객체 → 코어 다리 셋(사용자 결정 Q-5 · 이름 11-10) ─────────

BRIDGES = {"maps_to": ("cae_part", "part", "many_to_one"),
           "indicates": ("cae_finding", "failure_mode", "many_to_many"),
           "follows_method": ("cae_campaign", "analysis_method", "many_to_one")}


def test_the_three_bridges_and_their_cardinalities():
    """★`maps_to` 는 StepForge 의 part_role → part 와 같은 이름이다 — 한 질의(maps_to → part)로 두 앱을 묻는다."""
    doc, _ = load(OURS)
    rels = {r["slug"]: r for r in doc["relation_types"]}
    got = {s: (r["src_type_slugs"], r["dst_type_slugs"], r["cardinality"]) for s, r in rels.items() if s in BRIDGES}
    assert got == {s: ([src], [dst], card) for s, (src, dst, card) in BRIDGES.items()}
    for slug in BRIDGES:
        r = rels[slug]
        assert r["acyclic"] is False and r["transitive"] is False, "끝 타입이 겹치지 않는다 — 막을 순환이 없다"
        assert r["description"] and r["inverse_label"], slug
        basis = next(p for p in r["properties"] if p["key"] == "basis")
        assert basis["enum_options"] == ["rule", "human"] and basis["required"] is True, slug
    for end in ("part", "failure_mode", "analysis_method"):
        assert end in EXTERNAL_TYPES, f"{end} 는 허브 거울이다 — 우리 정의 파일에 타입을 만들지 않는다"
        assert end not in {t["slug"] for t in doc["types"]}


def test_the_bridge_sources_are_in_the_cae_vocabulary_which_we_do_not_edit():
    """다리는 자체 정의에 둔다 — 정본 해석 어휘(생산 쪽과 바이트 사본)에는 코어로 가는 관계가 없다."""
    cae = json.loads(CAE.read_text(encoding="utf-8"))
    assert {src for src, _, _ in BRIDGES.values()} <= _cae_types()
    assert not set(BRIDGES) & {r["slug"] for r in cae["relation_types"]}
    hub_ends = {"part", "failure_mode", "analysis_method"}
    assert not [r["slug"] for r in cae["relation_types"] if set(r.get("dst_type_slugs") or []) & hub_ends]


def test_the_revision_type_carries_what_the_plan_says():
    doc, _ = load(OURS)
    props = {p["key"] for p in doc["types"][0]["properties"]}
    assert {"task", "model", "code", "phase", "round", "rev_seq", "rev_source",
            "status", "decided_by", "decided_at"} <= props


def test_the_sequence_is_data_not_code():
    """★순서를 정규식 나열에 암묵으로 두면 화면도 MCP 도 그 뜻을 알 방법이 없다."""
    doc, _ = load(OURS)
    seq = [p for p in doc["types"][0]["properties"] if p["key"] == "rev_seq"][0]
    assert seq["data_type"] == "number" and seq.get("required") is True


def test_the_code_pattern_matches_the_one_the_reports_already_use():
    """`eng_meta` 가 이미 검증하는 형식과 **같아야** 한다 — 두 벌이 되면 한쪽만 고쳐진다."""
    import re
    from app.reports.datahub import _STAGE_RE
    doc, _ = load(OURS)
    pat = [p for p in doc["types"][0]["properties"] if p["key"] == "code"][0]["pattern"]
    ours = re.compile(pat)
    for good in ("pre", "dv1", "dv2", "dvr", "pv3", "pra", "mp"):
        assert ours.fullmatch(good), good
        assert _STAGE_RE.fullmatch(good), f"{good} 가 리포트 쪽 형식과 안 맞는다"
    for bad in ("dv", "pv", "pre1", "mp2", "zz", "DV1"):
        assert not ours.fullmatch(bad), bad


# ── 결 맞추기 — StepForge 와 같은 관계 이름 ────────────────────────────────

def test_the_shared_relation_names_match_stepforge_exactly():
    """★뜻이 같은 관계는 **이름이 같아야** 한다 — 나중에 한 질의로 양쪽 개정을 묻는다.
    그리고 타입 slug 는 **달라야** 한다(같은 꼴 다른 축 — 허브에서 만날 수 있다)."""
    doc, _ = load(OURS)
    rels = {r["slug"] for r in doc["relation_types"]}
    assert {"revision_of", "supersedes"} <= rels
    assert doc["types"][0]["slug"] == "dev_revision"
    assert doc["types"][0]["slug"] != "cad_revision", "StepForge 의 축과 섞였다"


def test_the_revision_chain_cannot_loop():
    doc, _ = load(OURS)
    sup = [r for r in doc["relation_types"] if r["slug"] == "supersedes"][0]
    assert sup["acyclic"] is True
    assert sup["src_type_slugs"] == sup["dst_type_slugs"] == ["dev_revision"]


def test_the_task_reference_points_at_the_hub_mirror():
    """과제는 **받는 것**이다 — 우리 정의 파일에 과제 타입을 만들지 않는다."""
    doc, _ = load(OURS)
    task = [p for p in doc["types"][0]["properties"] if p["key"] == "task"][0]
    assert task["data_type"] == "object_ref" and task["ref_type_slug"] == "plm_task"
    assert "plm_task" not in {t["slug"] for t in doc["types"]}
    assert "plm_task" in EXTERNAL_TYPES


# ── ② 허브의 정의를 그대로 읽는다 ──────────────────────────────────────────

@pytest.mark.parametrize("name", ["plm-core", "work-core"])
def test_the_hub_definitions_pass_unchanged(name):
    """★이것이 "꼴을 맞췄다" 의 증거다. 바꿔서 통과시키면 증거가 아니다."""
    path = HUB / f"{name}.json"
    if not path.exists():
        pytest.skip(f"submodule 이 없다: {path}")
    _, rep = load(path)
    assert rep.ok, rep.faults
    assert not rep.notes, f"모르는 키가 남았다: {rep.notes}"


def test_the_hub_task_type_is_what_we_expect():
    path = HUB / "plm-core.json"
    if not path.exists():
        pytest.skip("submodule 이 없다")
    doc, _ = load(path)
    by = {t["slug"]: t for t in doc["types"]}
    assert set(by) == {"plm_project", "plm_test_site", "plm_task", "plm_model"}
    assert by["plm_task"]["key_policy"] == "required"      # key = 과제코드
    # 개발모델이 모델명에서 자른 개정 조각을 들고 있다 — 우리 후보의 근거 ③ 이다
    assert "model_revision" in {p["key"] for p in by["plm_model"]["properties"]}


# ── 판별력 — 흠을 정말 잡는가 ──────────────────────────────────────────────

def _doc(**kw):
    base = {"groups": [{"slug": "g", "label": "G"}],
            "types": [{"slug": "a", "label": "A", "nav_group_slug": "g", "properties": []}],
            "relation_types": []}
    base.update(kw)
    return base


@pytest.mark.parametrize("doc,says", [
    (_doc(types=[{"slug": "a", "label": "A", "properties": [
        {"key": "x", "label": "X", "data_type": "말도안되는종류"}]}]), "data_type"),
    (_doc(types=[{"slug": "a", "label": "A", "properties": [
        {"key": "x", "label": "X", "data_type": "object_ref"}]}]), "ref_type_slug"),
    (_doc(types=[{"slug": "a", "label": "A", "properties": [
        {"key": "x", "label": "X", "data_type": "object_ref",
         "ref_type_slug": "없는타입"}]}]), "아는 타입이 아니다"),
    (_doc(types=[{"slug": "a", "label": "A", "properties": [
        {"key": "x", "label": "X", "data_type": "enum"}]}]), "enum_options"),
    (_doc(types=[{"slug": "a", "label": "A", "nav_group_slug": "없는묶음",
                  "properties": []}]), "groups 에 없다"),
    (_doc(types=[{"slug": "a", "label": "A", "key_policy": "아무거나",
                  "properties": []}]), "key_policy"),
    (_doc(types=[{"slug": "a", "label": "A", "properties": []},
                 {"slug": "a", "label": "또 A", "properties": []}]), "두 번 나온다"),
    (_doc(relation_types=[{"slug": "r", "label": "R", "inverse_label": "역",
                           "cardinality": "아무거나"}]), "cardinality"),
    (_doc(relation_types=[{"slug": "r", "label": "R"}]), "inverse_label"),
    (_doc(relation_types=[{"slug": "r", "label": "R", "inverse_label": "역",
                           "acyclic": True, "src_type_slugs": ["a"],
                           "dst_type_slugs": ["plm_task"]}]), "막는 것이 없다"),
    (_doc(relation_types=[{"slug": "r", "label": "R", "inverse_label": "역",
                           "src_type_slugs": ["a"], "dst_type_slugs": ["a"]}]),
     "영원히 돈다"),
    # 관계에 붙는 칸도 타입 칸과 같은 눈으로(SRC-08 다리의 basis 등)
    (_doc(relation_types=[{"slug": "r", "label": "R", "inverse_label": "역", "properties": [
        {"key": "x", "label": "X", "data_type": "말도안되는종류"}]}]), "data_type"),
    (_doc(relation_types=[{"slug": "r", "label": "R", "inverse_label": "역", "properties": [
        {"key": "x", "label": "X", "data_type": "enum"}]}]), "enum_options"),
    (_doc(relation_types=[{"slug": "r", "label": "R", "inverse_label": "역", "properties": [
        {"key": "x", "label": "X", "data_type": "text"}, {"key": "x", "label": "또 X", "data_type": "text"}]}]),
     "두 번 나온다"),
    (_doc(relation_types=[{"slug": "r", "label": "R", "inverse_label": "역", "properties": ["basis"]}]),
     "표(객체)가 아닌"),
])
def test_the_validator_actually_catches_each_fault(doc, says):
    rep = validate(doc)
    assert not rep.ok, f"흠을 못 잡았다: {doc}"
    assert any(says in f for f in rep.faults), rep.faults


def test_an_unknown_key_is_a_note_not_a_fault():
    """수신 규칙 5 와 같은 자세 — 허브가 칸을 늘려도 우리가 안 깨진다."""
    rep = validate(_doc(types=[{"slug": "a", "label": "A", "미래칸": 1,
                                "properties": []}]))
    assert rep.ok
    assert any("미래칸" in n for n in rep.notes)


def test_a_broken_file_is_a_fault_not_an_exception(tmp_path):
    bad = tmp_path / "x.json"
    bad.write_text("{ 깨진", encoding="utf-8")
    _, rep = load(bad)
    assert not rep.ok and "JSONDecodeError" in rep.faults[0]
    _, missing = load(tmp_path / "nope.json")
    assert not missing.ok


def test_the_allowed_sets_are_the_ones_sp_documents():
    """SP §4.2 의 속성 종류와 카디널리티 — 늘리거나 줄이면 정의가 서로 안 읽힌다."""
    assert DATA_TYPES == {"text", "text_long", "number", "date", "datetime", "bool",
                          "enum", "url", "object_ref", "file"}
    assert CARDINALITIES == {"one_to_one", "one_to_many", "many_to_one", "many_to_many"}
