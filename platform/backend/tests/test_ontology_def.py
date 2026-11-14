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

import ast
import hashlib
import json

import pytest

from app.runner.ontology_def import (CARDINALITIES, DATA_TYPES, EXTERNAL_TYPES, load,
                                     validate)

ROOT = Path(__file__).resolve().parents[3]
OURS = ROOT / "platform" / "core" / "ontology" / "dynaforge-core.json"
CAE = OURS.with_name("dynaforge-cae.json")      # 해석 어휘 — 생산 쪽과 바이트 사본(고치지 않는다). 다리의 출발 타입이 여기 있다
HUB = ROOT / "external" / "StandardPlatform" / "pipeline" / "core"
# SP 의 정의 가져오기 — 받는 칸 목록(TOP_KEYS · *_FIELDS)의 정본. 서브모듈이 없으면 그 시험은 건너뛴다(허브 정의 시험과 같다)
SP_IMPORTER = ROOT / "external" / "StandardPlatform" / "backend" / "app" / "modules" / "ontology" / "importer.py"
SP_MODELS = SP_IMPORTER.with_name("models.py")       # 칸마다 String(N) — SP 가 저장하는 글자 상한의 정본
SP_SERVICES = SP_IMPORTER.with_name("services.py")   # SLUG_RE · KEY_RE — slug · 속성 key 의 꼴


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
    """다리 셋의 끝 · 카디널리티. ★`maps_to` 는 StepForge 와 **같은 정의**다 — 출발에 그쪽 `part_role` 과 우리 `cae_part` 가 함께 있고,
    한 질의(maps_to → part)로 두 앱을 묻는다(블록 지문은 아래 시험이 고정한다)."""
    doc, _ = load(OURS)
    rels = {r["slug"]: r for r in doc["relation_types"]}
    for slug, (src, dst, card) in BRIDGES.items():
        r = rels[slug]
        assert src in r["src_type_slugs"] and r["dst_type_slugs"] == [dst] and r["cardinality"] == card, slug
        # 빠지면 SP 기본값(거짓)이다 — 공유 블록(maps_to)은 이 칸을 싣지 않는다. 끝 타입이 겹치지 않아 막을 순환도 없다
        assert r.get("acyclic", False) is False and r.get("transitive", False) is False, slug
        assert r["description"] and r["inverse_label"], slug
        basis = next(p for p in r["properties"] if p["key"] == "basis")
        assert {"rule", "human"} <= set(basis["enum_options"]) and basis["required"] is True, slug
    assert rels["maps_to"]["src_type_slugs"] == ["part_role", "cae_part"]
    assert [r["src_type_slugs"] for s, r in rels.items() if s in ("indicates", "follows_method")] == [["cae_finding"], ["cae_campaign"]]
    for end in ("part", "failure_mode", "analysis_method"):
        assert end in EXTERNAL_TYPES, f"{end} 는 허브 거울이다 — 우리 정의 파일에 타입을 만들지 않는다"
        assert end not in {t["slug"] for t in doc["types"]}
    assert "part_role" in EXTERNAL_TYPES and "part_role" not in {t["slug"] for t in doc["types"]}, "StepForge 의 타입이다"


# ★StepForge 도 이 블록을 **바이트 그대로**(같은 칸 · 같은 차례) 싣는다(사용자 결정 11-11). 고칠 때는 두 앱이 함께 고치고 이 지문을 같이 바꾼다.
MAPS_TO_SHA256 = "e5749ad481197908248576dd11c82eef6c2962545e9bf58a9247fd7568b96d07"


def test_maps_to_is_the_block_stepforge_carries_unchanged():
    """SP 가져오기는 지우지 않고, 마지막 가져오기가 src_type_slugs · enum 을 덮으며, 다른 출처가 관리하는 정의는 「그대로」 가 아니면
    거절한다(`importer._refuse_managed`) — 두 앱의 블록이 한 글자라도 다르면 한 허브에 둘을 싣지 못하거나 서로 덮는다."""
    doc, _ = load(OURS)
    block = next(r for r in doc["relation_types"] if r["slug"] == "maps_to")
    raw = json.dumps(block, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(raw.encode("utf-8")).hexdigest() == MAPS_TO_SHA256
    assert list(block) == ["slug", "label", "inverse_label", "description", "cardinality", "src_type_slugs", "dst_type_slugs",
                           "properties"], "칸 차례도 같게 둔다"
    assert [p["key"] for p in block["properties"]] == ["basis", "matched_by", "matched_text", "src_label", "decided_by",
                                                       "decided_at", "note"]
    basis = block["properties"][0]
    assert basis["enum_options"] == ["human", "other", "rule"], "other 는 StepForge 의 값이다 — 우리는 쓰지 않는다"


def test_the_bridge_sources_are_in_the_cae_vocabulary_which_we_do_not_edit():
    """다리는 자체 정의에 둔다 — 정본 해석 어휘(생산 쪽과 바이트 사본)에는 코어로 가는 관계가 없다."""
    cae = json.loads(CAE.read_text(encoding="utf-8"))
    assert {src for src, _, _ in BRIDGES.values()} <= _cae_types()
    assert not set(BRIDGES) & {r["slug"] for r in cae["relation_types"]}
    hub_ends = {"part", "failure_mode", "analysis_method"}
    assert not [r["slug"] for r in cae["relation_types"] if set(r.get("dst_type_slugs") or []) & hub_ends]


def test_the_bridge_descriptions_state_the_rule_the_matcher_runs():
    """`indicates` · `follows_method` 의 설명은 허브에 실린다 — 규칙 선을 말하는 글이 지금 견줌(`bridges.match`)과 같아야 한다(검토 3차 12).
    살아 있는 객체가 정하고 그만 쓴 객체는 살아 있는 것이 하나도 안 맞을 때만 센다(사용자 결정 11-12). 과제 잇기와는 갈리는 자리가 있어
    (bridges 머리말) 「과제 잇기의 정확과 같다」 고 하지 않는다. `maps_to` 는 공유 블록이라 규칙을 앱 문서로 넘긴다 — 여기서 보지 않는다."""
    doc, _ = load(OURS)
    rels = {r["slug"]: r for r in doc["relation_types"]}
    for slug in ("indicates", "follows_method"):
        text = rels[slug]["description"]
        assert "살아 있는 코어 객체" in text and "그만 쓴(deprecated) 객체는 살아 있는 객체가 하나도 안 맞을 때만" in text, slug
        assert "과제 잇기의" not in text, f"{slug} 설명이 과제 잇기와 같다고 아직 말한다"


def test_the_revision_type_carries_what_the_plan_says():
    doc, _ = load(OURS)
    props = {p["key"] for p in doc["types"][0]["properties"]}
    assert {"task", "model", "code", "phase", "round", "rev_seq", "rev_source",
            "status", "decided_by", "decided_at"} <= props


def test_every_revision_source_the_code_writes_is_in_the_definition():
    """판의 `rev_source` 로 코드가 쓰는 값은 모두 정의의 값 목록에 있다 — 기계가 허브 판정으로 만든 판은 `rule` 이다(자동 잇기 · 반입 · 메타
    고침, `SOURCE_RULE`). 목록에 없으면 정의대로 읽는 쪽(허브 · 화면)이 모르는 값을 받는다(검토 11-14 — `rule` 이 빠져 있었다)."""
    from app.modules.ontology import services as onto
    doc, _ = load(OURS)
    src = [p for p in doc["types"][0]["properties"] if p["key"] == "rev_source"][0]
    assert {"eng_meta", onto.SOURCE_RULE, "manual"} <= set(src["enum_options"]), src["enum_options"]
    assert "`rule`" in src["help"], src["help"]


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


# ── 결 맞추기 — StepForge 와 같은 관계 이름 · 다른 정의 ─────────────────────────

def test_the_revision_relations_share_names_with_stepforge_but_not_definitions():
    """`revision_of` · `supersedes` 는 StepForge 와 **이름만 같다** — 그쪽은 끝 타입이 cad_revision 이고 supersedes 가 transitive 가
    아니다(사용자 결정 11-12 — 정의는 그대로, 글만 고친다). 「한 질의로 두 앱의 개정을 묻는다」 는 약속은 거뒀다 — 설명은 한 허브에 두 앱
    정의를 함께 싣기 전에 맞춰야 한다고 말해야 한다. 타입 slug 는 **달라야** 한다(같은 꼴 다른 축 — 허브에서 만날 수 있다)."""
    doc, _ = load(OURS)
    rels = {r["slug"]: r for r in doc["relation_types"]}
    assert {"revision_of", "supersedes"} <= set(rels)
    assert doc["types"][0]["slug"] == "dev_revision"
    assert doc["types"][0]["slug"] != "cad_revision", "StepForge 의 축과 섞였다"
    for slug in ("revision_of", "supersedes"):
        text = rels[slug]["description"]
        assert "다른 정의" in text and "cad_revision" in text and "맞춰야 한다" in text, (slug, text)
        assert "한 질의" not in text, f"{slug} 설명이 거둔 약속(한 질의로 두 앱)을 아직 한다"
    kind = doc["types"][0]["description"]
    assert "똑같이 쓴다" not in kind and "정의가 다르다" in kind, "타입 설명이 두 관계 이름을 아직 「똑같이 쓴다」 고 한다(검토 3차 12)"


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


# ── ③ SP 가져오기가 받는 키만 — 모르는 키 하나가 파일 전체를 못 들이게 한다 ─────────────────

_SP_SETS = ("TOP_KEYS", "GROUP_FIELDS", "TYPE_FIELDS", "PROPERTY_FIELDS", "RELATION_FIELDS")


def _sp_key_sets() -> dict[str, set[str]]:
    """SP `importer.py` 의 칸 목록 — 모듈을 import 하지 않고(그쪽도 `app` 패키지라 우리와 이름이 겹친다) 리터럴을 AST 로 읽는다."""
    out: dict[str, set[str]] = {}
    for node in ast.parse(SP_IMPORTER.read_text(encoding="utf-8")).body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        for t in targets:
            if isinstance(t, ast.Name) and t.id in _SP_SETS:
                out[t.id] = set(ast.literal_eval(node.value))
    return out


def _unknown_to_sp(doc: dict, sets: dict[str, set[str]]) -> list[str]:
    """정의 문서에서 SP 가져오기가 모르는 키 — `_reject_unknown` 이 거절할 자리마다 한 줄."""
    bad = [f"(최상위) {k}" for k in sorted(set(doc) - sets["TOP_KEYS"])]
    for g in doc.get("groups") or []:
        bad += [f"groups/{g.get('slug')} {k}" for k in sorted(set(g) - sets["GROUP_FIELDS"])]
    for kind, items, fields in (("types", doc.get("types") or [], "TYPE_FIELDS"),
                                ("relation_types", doc.get("relation_types") or [], "RELATION_FIELDS")):
        for one in items:
            bad += [f"{kind}/{one.get('slug')} {k}" for k in sorted(set(one) - sets[fields])]
            for prop in one.get("properties") or []:
                bad += [f"{kind}/{one.get('slug')}.{prop.get('key')} {k}" for k in sorted(set(prop) - sets["PROPERTY_FIELDS"])]
    return bad


def test_our_definition_carries_only_keys_sp_import_accepts():
    """SP 가져오기는 모르는 키를 거절한다(`_reject_unknown`) — 최상위 `_note` 하나가 파일 전체를 못 들이게 했다(검토 11-11).
    정본 해석 어휘(dynaforge-cae.json)는 생산 쪽과 바이트 사본이라 이 시험 밖이다(`_version` · `_note` 를 싣는다)."""
    if not SP_IMPORTER.exists():
        pytest.skip(f"submodule 이 없다: {SP_IMPORTER}")
    sets = _sp_key_sets()
    assert set(sets) == set(_SP_SETS), f"SP 칸 목록을 다 읽지 못했다: {sorted(set(_SP_SETS) - set(sets))}"
    doc = json.loads(OURS.read_text(encoding="utf-8"))
    assert _unknown_to_sp(doc, sets) == []
    # 판별력 — 대조가 정말 본다(최상위 · 관계 · 관계 칸의 모르는 키를 잡는다)
    rel = {**doc["relation_types"][0], "미래칸": 1}
    rel["properties"] = [{"key": "x", "label": "X", "data_type": "text", "모르는칸": 1}]
    got = _unknown_to_sp({**doc, "_note": "x", "relation_types": [rel]}, sets)
    assert any(g.startswith("(최상위) _note") for g in got) and any("미래칸" in g for g in got) \
        and any("모르는칸" in g for g in got), got


# ── ④ SP 가 저장하는 값의 꼴 — 키 이름만이 아니라 값이 표에 들어가나(검토 2차 11-11) ─────────────────
# SP 의 진짜 계획(importer.plan, e2676ad)이 indicates · follows_method 의 matched_by help(218자)를 「200자까지」 로 거절했다 —
# 키 이름 대조는 그것을 못 본다. `_field_errors` 와 같은 규칙으로 본다 — 칸 이름이 표의 String(N) 칸이면 글자 수 ≤ N(문자 수),
# CHOICES 의 칸이면 허용값 안, slug · 속성 key 는 SLUG_RE · KEY_RE(`require_slug` · `require_key`).

_SP_TABLE_OF = {"groups": "NavGroup", "types": "ObjectType", "relation_types": "RelationType"}


def _sp_value_rules() -> tuple[dict[str, dict[str, int | None]], dict[str, tuple], str, str]:
    """SP models.py 의 표마다 (칸 → String(N) 의 N · 글자가 아닌 칸은 None), importer.py 의 CHOICES(칸 → 허용값),
    services.py 의 SLUG_RE · KEY_RE 꼴 — 모두 리터럴을 AST 로 읽는다(그쪽도 app 패키지라 import 하지 않는다)."""
    tree = ast.parse(SP_MODELS.read_text(encoding="utf-8"))
    consts: dict[str, object] = {}
    tables: dict[str, dict[str, int | None]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                consts[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
        if isinstance(node, ast.ClassDef) and node.name in (*_SP_TABLE_OF.values(), "PropertyDef"):
            cols: dict[str, int | None] = {}
            for st in node.body:
                call = st.value if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) else None
                if not (isinstance(call, ast.Call) and getattr(call.func, "id", None) == "mapped_column" and call.args):
                    continue
                kind = call.args[0]
                if isinstance(kind, ast.Call) and getattr(kind.func, "id", None) == "String" and kind.args:
                    n = kind.args[0]
                    cols[st.target.id] = n.value if isinstance(n, ast.Constant) else consts[n.id]
                else:
                    cols[st.target.id] = None                 # Text · JSONB · Boolean … — 글자 상한이 없다
            tables[node.name] = cols
    choices: dict[str, tuple] = {}
    for node in ast.parse(SP_IMPORTER.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "CHOICES":
            for k, v in zip(node.value.keys, node.value.values):
                if isinstance(v, ast.Name) and v.id in consts:   # revision.SOURCES 처럼 다른 모듈 것은 우리 파일이 안 쓴다
                    choices[k.value] = tuple(consts[v.id])
    pats = {}
    for node in ast.parse(SP_SERVICES.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) in ("SLUG_RE", "KEY_RE"):
            pats[node.targets[0].id] = node.value.args[0].value
    return tables, choices, pats["SLUG_RE"], pats["KEY_RE"]


def _refused_by_sp(doc: dict, rules) -> list[str]:
    """SP 가져오기가 값 때문에 거절할 자리 — 글자 칸 상한 · 글자 아님 · 허용값 밖 · slug/key 꼴. 한 자리에 한 줄."""
    import re
    tables, choices, slug_re, key_re = rules
    bad: list[str] = []

    def check(where: str, one: dict, table: str, *, ident: str, ident_re: str) -> None:
        if not re.fullmatch(ident_re, str(one.get(ident) or "")):
            bad.append(f"{where} {ident}={one.get(ident)!r} 꼴이 아니다")
        for name, value in one.items():
            if name in (ident, "properties") or value is None:
                continue
            if name in choices and value not in choices[name]:
                bad.append(f"{where}.{name}={value!r} 는 {choices[name]} 밖이다")
            limit = tables[table].get(name, "없음")
            if limit == "없음" or limit is None:
                continue
            if not isinstance(value, str):
                bad.append(f"{where}.{name} 는 글자여야 한다")
            elif len(value) > limit:
                bad.append(f"{where}.{name} {len(value)}자 > {limit}자")

    for kind, table in _SP_TABLE_OF.items():
        for one in doc.get(kind) or []:
            where = f"{kind}/{one.get('slug')}"
            check(where, one, table, ident="slug", ident_re=slug_re)
            for end in ("src_type_slugs", "dst_type_slugs"):
                bad += [f"{where}.{end} {t!r} 꼴이 아니다" for t in one.get(end) or [] if not re.fullmatch(slug_re, t)]
            for prop in one.get("properties") or []:
                check(f"{where}.{prop.get('key')}", prop, "PropertyDef", ident="key", ident_re=key_re)
    return bad


def test_our_definition_values_fit_what_sp_stores():
    """키 이름만 맞아도 SP 는 값에서 거절한다 — 공유 maps_to 블록을 포함해 우리 파일의 모든 값이 SP 표에 들어가야 한다."""
    if not (SP_MODELS.exists() and SP_SERVICES.exists()):
        pytest.skip(f"submodule 이 없다: {SP_MODELS}")
    rules = _sp_value_rules()
    tables, choices, _, _ = rules
    assert {"help", "label", "key", "data_type"} <= set(tables["PropertyDef"]) and tables["PropertyDef"]["help"] == 200
    assert {"cardinality", "data_type", "key_policy"} <= set(choices), "SP 의 허용값을 다 읽지 못했다"
    doc = json.loads(OURS.read_text(encoding="utf-8"))
    assert _refused_by_sp(doc, rules) == []
    # 판별력 — 긴 help · 허용값 밖 · slug 꼴이 아닌 것을 잡는다
    rel = json.loads(json.dumps(doc["relation_types"][-1]))
    rel["properties"][0]["help"] = "가" * 201
    rel["cardinality"] = "아무거나"
    rel["slug"] = "Bad-Slug"
    got = _refused_by_sp({**doc, "relation_types": [rel]}, rules)
    assert any("201자 > 200자" in g for g in got) and any("cardinality" in g for g in got) \
        and any("꼴이 아니다" in g for g in got), got


# ── ⑤ SP 가 종류 · 빈 값 · 규칙으로 거절하는 자리 — 글자 길이와 허용값 너머(재검토 11-14 결함 3c) ─────────────────
# 정의 파일을 한 군데씩 바꾼 162벌 가운데 SP 의 진짜 계획(importer.plan, 13e6b02 · 빈 허브)이 113벌을 거절했는데, 그중 36벌에서
# 이 파일이 초록이었다 — 종류가 다른 값(참/거짓 칸의 글자 · 숫자 칸의 글자) · 비울 수 없는 칸의 null · 묶음의 색과 상위 묶음 · 투영 타입의 원 표 · accept ·
# 목록 화면이 가리키는 자리 · 재귀 관계. ④ 는 글자 칸의 길이 · 허용값 · slug/key 꼴까지 본다 — 여기는 그 나머지를 **빈 허브가
# 하는 대로** 본다. 값의 종류 · 빈 값, 묶음의 색 · 상위 묶음, accept, 재귀 관계는 SP 의 규칙을 그대로 옮겼다.
# 화면(list_view · form_view · detail_view) · 투영 타입(kind_class=system · system_source) · 인터페이스(최상위 interfaces)의 규칙은
# 옮기지 않았다 — 우리 파일이 그것을 **안 쓴다**는 것만 못박는다(이 절의 마지막 시험). 화면은 SP 의 views.validate_* 가 모르는 항목 ·
# 가리키는 자리 · 정렬 · 트리 · 롤업 · 폼의 묶음(sections)까지 보고, 원 표 이름은 SP 가 띄울 때 채우는 등록부(shared/system_sources)에
# 있어야 하고, 인터페이스는 제 칸 목록과 구현 타입 맞추기가 따로 있다 — 옮기면 그쪽 코드를 여기 다시 짓는 셈이다. 쓰기 시작하는 날
# 그 시험이 빨개지고, 그때 규칙을 옮긴다. 허브에 든 것에 달린 판정은 파일만으로 알 수 없다 — 있던 관계는 안 적은 acyclic 이
# 저장값을 따르고, 허브에만 있는 상위 묶음은 빈 허브만 거절한다. SP 가 따로 규칙을 둔 키 가운데 우리 검사기가 모르는 것(revision_key ·
# quantity_key · lineage_source · interface_slugs)은 ① 의 「모르는 키가 남았다」 가 잡는다 — 검사기에 그 키를 들이는 날 그 규칙도 옮긴다.

# `_field_errors` 가 칸의 종류를 가르는 대로 — Text 도 글자(String 의 하위형)이고, 그 밖(JSONB …)은 안 본다
_SP_KIND = {"String": str, "Text": str, "Boolean": bool, "Integer": int, "Float": (int, float)}


def _sp_named(path: Path, name: str):
    """SP 소스의 모듈 수준 이름 하나 — 리터럴은 그 값, `re.compile("…")` 은 그 꼴(글자). AST 로 읽는다(import 하지 않는다)."""
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name:
            return node.value.args[0].value if isinstance(node.value, ast.Call) else ast.literal_eval(node.value)
    raise AssertionError(f"SP {path.name} 에 {name} 이 없다")


def _sp_column_kinds() -> dict[str, dict[str, tuple[str | None, bool]]]:
    """SP models.py 의 표마다 (칸 → 종류 이름 · 비울 수 있나). 비울 수 있나는 SQLAlchemy 가 정하는 대로 읽는다 —
    `nullable=` 을 적었으면 그 값, 안 적었으면 `Mapped[… | None]` 인가."""
    tables: dict[str, dict[str, tuple[str | None, bool]]] = {}
    for node in ast.parse(SP_MODELS.read_text(encoding="utf-8")).body:
        if not (isinstance(node, ast.ClassDef) and node.name in (*_SP_TABLE_OF.values(), "PropertyDef")):
            continue
        cols = tables.setdefault(node.name, {})
        for st in node.body:
            call = st.value if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) else None
            if not (isinstance(call, ast.Call) and getattr(call.func, "id", None) == "mapped_column" and call.args):
                continue
            kind = call.args[0].func if isinstance(call.args[0], ast.Call) else call.args[0]
            said = [k.value.value for k in call.keywords if k.arg == "nullable"]
            optional = any(isinstance(n, ast.Constant) and n.value is None for n in ast.walk(st.annotation))
            cols[st.target.id] = (getattr(kind, "id", None), said[0] if said else optional)
    return tables


def _wrong_kind_for_sp(doc: dict, kinds, shapes) -> list[str]:
    """SP 가져오기가 값의 종류 때문에 거절할 자리 — `_field_errors` 의 차례 그대로(목록 · 표 · slug 칸은 null 을 받는다). 한 자리에 한 줄."""
    lists, dicts, slugs = shapes
    bad: list[str] = []

    def check(where: str, one: dict, table: str) -> None:
        for name, value in one.items():
            if name in ("slug", "key", "properties") or (table == "NavGroup" and name == "color"):
                continue                                  # 묶음의 색은 `_field_errors` 밖이다 — 아래 규칙(group_color_error)이 본다
            if name in lists:
                ok = value is None or (isinstance(value, list) and all(isinstance(v, str) for v in value))
            elif name in dicts:
                ok = value is None or isinstance(value, dict)
            elif name in slugs:
                ok = value is None or isinstance(value, str)
            elif name not in kinds[table]:
                continue
            elif value is None:
                ok = kinds[table][name][1]
            else:                                         # 참/거짓은 정수 · 숫자로 안 친다
                want = _SP_KIND.get(kinds[table][name][0])
                ok = want is None or (isinstance(value, want) and (want is bool or not isinstance(value, bool)))
            if not ok:
                bad.append(f"{where}.{name}={value!r} — " + ("비울 수 없다" if value is None else "종류가 틀렸다"))

    for kind, table in _SP_TABLE_OF.items():
        for one in doc.get(kind) or []:
            check(f"{kind}/{one.get('slug')}", one, table)
            for prop in one.get("properties") or []:
                check(f"{kind}/{one.get('slug')}.{prop.get('key')}", prop, "PropertyDef")
    return bad


def test_our_definition_values_are_the_kind_sp_columns_take():
    """길이가 맞아도 SP 는 종류에서 거절한다 — 참/거짓 칸의 글자, 숫자 칸의 글자, 비울 수 없는 칸의 null. 우리 파일의 모든 값이 제 칸의 종류여야 한다."""
    if not (SP_MODELS.exists() and SP_IMPORTER.exists()):
        pytest.skip(f"submodule 이 없다: {SP_MODELS}")
    kinds = _sp_column_kinds()
    shapes = [_sp_named(SP_IMPORTER, name) for name in ("LIST_FIELDS", "DICT_FIELDS", "SLUG_FIELDS")]
    assert (kinds["RelationType"]["transitive"], kinds["PropertyDef"]["min_value"], kinds["NavGroup"]["sort_order"],
            kinds["ObjectType"]["description"]) == (("Boolean", False), ("Float", True), ("Integer", False), ("Text", False)), \
        "SP 표의 칸 종류 · 비울 수 있나를 다 읽지 못했다"
    assert "enum_options" in shapes[0] and "list_view" in shapes[1] and "nav_group_slug" in shapes[2]
    doc = json.loads(OURS.read_text(encoding="utf-8"))
    assert _wrong_kind_for_sp(doc, kinds, shapes) == []
    # 판별력 — 틀린 종류와 비울 수 없는 칸의 null 을 자리마다 잡는다
    prop = {"key": "p", "label": "P", "data_type": "number", "required": "yes", "sort_order": "3", "min_value": True,
            "help": None, "enum_options": "a,b"}
    got = _wrong_kind_for_sp({"groups": [{"slug": "g", "label": None, "sort_order": True}],
                              "types": [{"slug": "t", "label": "T", "list_view": ["code"], "properties": [prop]}],
                              "relation_types": [{"slug": "r", "label": "R", "transitive": "false", "description": None,
                                                  "src_type_slugs": ["t", 7]}]}, kinds, shapes)
    assert sorted(g.split("=")[0].rsplit(".", 1)[1] for g in got) == sorted(
        ["label", "sort_order", "list_view", "required", "sort_order", "min_value", "help", "enum_options",
         "transitive", "description", "src_type_slugs"]), got
    # SP 가 받는 이웃은 안 잡는다 — 정수로 적은 숫자 칸 · 비워도 되는 칸의 null · 목록 · 표 · slug 칸의 null · 묶음 색의 null
    prop = {"key": "p", "label": "P", "data_type": "number", "min_value": 0, "max_value": 9.5, "decimals": None,
            "enum_options": None, "default_value": {"a": 1}}
    assert _wrong_kind_for_sp({"groups": [{"slug": "g", "label": "G", "color": None}],
                               "types": [{"slug": "t", "label": "T", "list_view": None, "nav_group_slug": None,
                                          "properties": [prop]}]}, kinds, shapes) == []


def _refused_by_sp_rules(doc: dict, color_re: str) -> list[str]:
    """SP 의 계획이 규칙으로 거절할 자리 — 빈 허브에서. 규칙마다 그쪽 함수 이름을 곁에 적는다. 한 자리에 한 줄."""
    import re
    bad: list[str] = []
    groups = [g for g in doc.get("groups") or [] if g.get("slug")]
    known = {str(g["slug"]) for g in groups}
    parent_of = {str(g["slug"]): g["parent_slug"] or None for g in groups if "parent_slug" in g}
    for g in groups:
        slug, color, parent = str(g["slug"]), str(g.get("color") or "").strip(), str(g.get("parent_slug") or "")
        if color and not re.match(color_re, color):           # services.group_color_error — 비운 색은 받는다
            bad.append(f"groups/{slug}.color={g['color']!r} 는 #rrggbb 가 아니다")
        # services.group_parent_error — 자기 자신 · 없는 묶음 · 이미 상위가 있는 묶음은 상위가 못 되고, 아래에 묶음을 둔 묶음은
        # 상위를 못 갖는다(묶음은 두 단계까지)
        if parent and (parent == slug or parent not in known or parent_of.get(parent) or slug in parent_of.values()):
            bad.append(f"groups/{slug}.parent_slug={parent!r} 는 상위 묶음이 못 된다")
    for kind in ("types", "relation_types"):
        for one in doc.get(kind) or []:
            # importer._plan_properties — accept 는 파일 속성에만 적는다(종류를 안 적은 속성은 허브의 저장값을 따른다 — 빈 허브에는 없다)
            bad += [f"{kind}/{one.get('slug')}.{p.get('key')} accept 는 file 속성에만 쓴다" for p in one.get("properties") or []
                    if p.get("accept") is not None and p.get("data_type") != "file"]
    for r in doc.get("relation_types") or []:
        transitive = bool(r.get("transitive", False))         # importer._relation_flags — 안 적은 acyclic 은 transitive 를 따른다
        if transitive and not bool(r.get("acyclic", transitive)):
            bad.append(f"relation_types/{r.get('slug')} 재귀로 펼치는데(transitive) 순환을 안 막는다(acyclic)")
    return bad


def test_our_definition_passes_the_rules_sp_plans_with():
    """종류까지 맞아도 SP 의 계획은 규칙으로 거절한다 — 묶음의 색 · 상위 묶음, accept, 재귀 관계."""
    if not SP_SERVICES.exists():
        pytest.skip(f"submodule 이 없다: {SP_SERVICES}")
    color_re = _sp_named(SP_SERVICES, "COLOR_RE")
    assert "#" in color_re, "SP 의 색 꼴을 읽지 못했다"
    doc = json.loads(OURS.read_text(encoding="utf-8"))
    assert _refused_by_sp_rules(doc, color_re) == []
    # 판별력 — 규칙마다 하나씩 어긴 것을 자리마다 잡는다
    shot = {"key": "shot", "label": "그림", "data_type": "text", "accept": "image"}
    got = _refused_by_sp_rules({
        "groups": [{"slug": "g", "label": "G", "color": "red", "parent_slug": "nope"}],
        "types": [{"slug": "t", "label": "T", "properties": [shot]}],
        "relation_types": [{"slug": "r", "label": "R", "transitive": True, "acyclic": False}]}, color_re)
    assert len(got) == 4 and all(any(word in g for g in got) for word in (".color=", ".parent_slug=", "accept", "acyclic")), got

    def no_parent_for(*pairs: tuple[str, str | None]) -> list[str]:
        groups = [{"slug": slug, "label": slug, **({"parent_slug": parent} if parent else {})} for slug, parent in pairs]
        return [g.split(".parent_slug")[0] for g in _refused_by_sp_rules({"groups": groups}, color_re)]

    # 상위 묶음의 네 갈래 — 자기 자신 · 없는 묶음, 세 단계에서는 가운데(아래에 묶음을 뒀다)와 맨 아래(상위가 이미 상위를 가졌다)가 다 걸린다
    assert no_parent_for(("a", "a")) == ["groups/a"] and no_parent_for(("a", "nope")) == ["groups/a"]
    assert no_parent_for(("top", None), ("mid", "top"), ("leaf", "mid")) == ["groups/mid", "groups/leaf"]
    # SP 가 받는 이웃은 안 잡는다 — 대문자 색 · 비운 색 · 두 단계 묶음 · 파일 속성의 accept · acyclic 을 안 적은 재귀 관계
    assert _refused_by_sp_rules({
        "groups": [{"slug": "top", "label": "위", "color": ""}, {"slug": "g", "label": "G", "color": "#8B5CF6", "parent_slug": "top"}],
        "types": [{"slug": "t", "label": "T", "properties": [{**shot, "data_type": "file"}]}],
        "relation_types": [{"slug": "r", "label": "R", "transitive": True}]}, color_re) == []


def _uses_what_is_not_mirrored(doc: dict) -> list[str]:
    """SP 규칙을 이 파일에 옮기지 않은 것을 정의가 쓰는 자리 — 화면 모양 · 투영 타입 · 인터페이스. 한 자리에 한 줄."""
    # 빈 목록 · null 은 SP 도 지나친다 — 그 밖의 값은 목록이 아니어도 센다(importer._require_shape 가 모양이 틀렸다고 거절한다)
    used = ["(최상위) interfaces"] if doc.get("interfaces") not in (None, []) else []
    for t in doc.get("types") or []:
        where = f"types/{t.get('slug')}"
        # 빈 화면({} · null)은 SP 도 안 본다(views.validate_* 의 `if not spec`) — 채운 화면만 센다
        used += [f"{where}.{name}" for name in ("list_view", "form_view", "detail_view") if t.get(name)]
        # services.system_source_error 가 보는 두 칸 — 투영 종류이거나 원 표를 적었으면 센다
        if str(t.get("kind_class") or "record") == "system" or str(t.get("system_source") or ""):
            used.append(f"{where} kind_class={t.get('kind_class')!r} · system_source={t.get('system_source')!r}")
    return used


def test_our_definition_uses_nothing_whose_sp_rules_are_not_mirrored_here():
    """화면 모양 · 투영 타입 · 인터페이스는 SP 규칙을 옮기지 않았다 — 정의가 그것을 쓰기 시작하면 이 파일은 SP 가 거절할 것을 초록으로
    지나친다. 그래서 안 쓴다는 것을 못박는다(SP 가 받는 바른 화면에도 빨개진다 — 일부러다)."""
    doc = json.loads(OURS.read_text(encoding="utf-8"))
    assert _uses_what_is_not_mirrored(doc) == [], \
        "정의가 화면 · 투영 타입 · 인터페이스를 쓰기 시작했다 — SP 의 그 규칙(views.validate_* · system_source_error · _plan_interfaces)을 먼저 옮긴다"
    # 판별력 — 채운 화면 셋 · 투영 종류 · 원 표 · 인터페이스를 자리마다 잡는다
    got = _uses_what_is_not_mirrored({"interfaces": [{"slug": "i", "label": "I"}], "types": [
        {"slug": "a", "list_view": {"columns": ["key"]}, "form_view": {"sections": []}, "detail_view": {"sections": []}},
        {"slug": "b", "kind_class": "system", "system_source": "user"}, {"slug": "c", "system_source": "user"},
        {"slug": "d", "kind_class": "system"}]})
    assert [g.split(" ")[0] for g in got] == ["(최상위)", "types/a.list_view", "types/a.form_view", "types/a.detail_view",
                                               "types/b", "types/c", "types/d"], got
    # 빈 화면 · 보통 종류 · 빈 인터페이스 목록(과 null)은 안 잡는다 — 목록이 아닌 interfaces 는 비어 있어도 잡는다
    assert _uses_what_is_not_mirrored({"interfaces": [], "types": [
        {"slug": "a", "list_view": {}, "form_view": None, "kind_class": "record", "system_source": ""},
        {"slug": "b", "kind_class": "reference"}]}) == [] == _uses_what_is_not_mirrored({"interfaces": None})
    assert _uses_what_is_not_mirrored({"interfaces": {}}) == ["(최상위) interfaces"]


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
