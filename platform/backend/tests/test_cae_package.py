# 해석 어휘(cae_*) 정본과 꾸러미 검사(app/reports/onto_package.py)를 지키는 시험 — 사용자 결정 10-31 (가) 캠페인 수준만 행으로
"""정본 `platform/core/ontology/dynaforge-cae.json` 은 KooD3plotReader 판 0.3 바이트 그대로여야 한다(배포된 생산 쪽 꾸러미가 그 지문을 싣는다).
꾸러미는 받아들인 판의 어휘로 검사하고, 맞지 않으면 아무것도 싣지 않는다. 픽스처 `fixtures/cae_package_v14_min.json` 은 실물 v14 꾸러미에서
런 둘만 남긴 것이다.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.reports import onto_package as op
from app.runner import ontology_def

FIX = Path(__file__).with_name("fixtures") / "cae_package_v14_min.json"
REAL = Path("/home/koopark/claude/KooD3plotReader/KooD3plotReader/.work/ontology")
RID = "01TESTREPORT0000000000000A"
SHA03 = "72ff9b49edd5a38bc1112268df85de5b61eb36cba09bf3e2bc4c07a08d4c4d64"   # 생산 쪽 첫 배포판(0.3)의 어휘 바이트


def _pkg() -> dict:
    return json.loads(FIX.read_text(encoding="utf-8"))


def _cases(pkg: dict) -> set[str]:
    return {o["properties"]["case_key"] for o in pkg["objects"] if o["type"] == "cae_run"}


def _check(pkg: dict, **kw):
    args = {"report_id": RID, "report_kind": "sphere", "html_sha256": pkg["source"]["html"]["sha256"],
            "case_keys": _cases(pkg)}
    args.update(kw)
    return op.check(pkg, **args)


# ── 정본 ────────────────────────────────────────────────────────────────────

def test_the_deployed_producers_bytes_stay_accepted():
    """생산 쪽 배포판은 0.3 바이트를 싣는다 — 정본을 올려도 그 판의 꾸러미가 통해야 한다(history 에 남긴다)."""
    raw = (op.VOCAB_DIR / op.ACCEPTED[SHA03]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA03 and json.loads(raw)["_version"] == "0.3"


def test_the_canonical_is_0_3_plus_flow_scalars_only_in_the_producers_format():
    """0.4 = 0.3 에 cae_run.flow_scalars_only(bool) 하나(KooD3plotReader 10-31 정의). 생산 쪽이 바이트 그대로 옮기므로 꼴이 정해져 있다."""
    raw = (op.VOCAB_DIR / op.CANONICAL).read_bytes()
    doc = json.loads(raw)
    assert doc["_version"] == "0.4" and hashlib.sha256(raw).hexdigest() in op.ACCEPTED
    assert raw == (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode(), "정본 꼴(indent 2 · 한글 그대로 · 끝 줄바꿈)"
    run = next(t for t in doc["types"] if t["slug"] == "cae_run")
    added = run["properties"].pop()
    assert (added["key"], added["data_type"]) == ("flow_scalars_only", "bool")
    old = json.loads((op.VOCAB_DIR / op.ACCEPTED[SHA03]).read_bytes())
    doc["_version"] = old["_version"]
    assert doc == old, "0.3 에서 칸 하나 말고 바뀐 것이 있다"


def test_every_accepted_version_is_on_disk_with_its_fingerprint():
    """받아들인 판 목록과 파일이 어긋나면 그 판의 꾸러미를 검사할 수 없다 — 정본을 올리며 옛 바이트를 안 옮긴 것이다."""
    assert op.CANONICAL in op.ACCEPTED.values()
    for sha, name in op.ACCEPTED.items():
        assert hashlib.sha256((op.VOCAB_DIR / name).read_bytes()).hexdigest() == sha, name


def test_the_canonical_vocabulary_passes_our_validator_alone_and_with_core():
    doc, rep = ontology_def.load(op.VOCAB_DIR / op.CANONICAL)
    assert rep.ok and not rep.notes, (rep.faults, rep.notes)
    core = json.loads((op.VOCAB_DIR / "dynaforge-core.json").read_text(encoding="utf-8"))
    both = {"groups": (core.get("groups") or []) + (doc.get("groups") or []), "types": core["types"] + doc["types"],
            "relation_types": (core.get("relation_types") or []) + (doc.get("relation_types") or [])}
    merged = ontology_def.validate(both)
    assert merged.ok and not merged.notes, merged.faults


# ── 받아들임 ────────────────────────────────────────────────────────────────

def test_a_matching_package_becomes_campaign_level_rows_and_edges():
    got = _check(_pkg())
    by = {}
    for r in got["rows"]:
        by.setdefault(r["type_slug"], []).append(r)
    assert {t: len(v) for t, v in by.items()} == {"cae_campaign": 1, "cae_part": 23, "cae_contact": 27,
                                                  "cae_load_path": 21, "cae_finding": 22}
    assert not {"cae_run", "cae_part_response", "cae_load_transfer"} & set(by), "런 단위는 행으로 싣지 않는다(결정 (가))"
    assert all(r["key"].startswith(f"{RID}/") for r in got["rows"])
    camp = by["cae_campaign"][0]
    assert camp["properties"]["report"] == RID and camp["key"] == f"{RID}/campaign"
    part = next(p for p in by["cae_part"] if p["properties"].get("worst_von_mises_run"))
    assert part["properties"]["campaign"] == f"{RID}/campaign"
    assert part["properties"]["worst_von_mises_run"].startswith(f"{RID}/run/Run_")
    rel = {}
    for e in got["edges"]:
        rel[e["relation"]] = rel.get(e["relation"], 0) + 1
    assert rel == {"contact_side": 51, "path_between": 42, "finding_about": 21, "campaign_report": 1}
    assert next(e for e in got["edges"] if e["relation"] == "campaign_report")["dst_key"] == RID
    assert any((e["properties"] or {}).get("role") for e in got["edges"] if e["relation"] == "contact_side")
    assert got["vocabulary"] == {"version": "0.3", "sha256": SHA03}
    assert got["runs"] == {"package": 2, "matched": 2, "missing": []}


def test_some_runs_missing_from_the_report_is_a_warning_not_a_refusal():
    pkg = _pkg()
    one = sorted(_cases(pkg))[:1]
    got = _check(pkg, case_keys=set(one))
    assert got["runs"]["matched"] == 1 and any("이 리포트에 없다" in w for w in got["warnings"])


def test_each_package_is_checked_with_its_own_version():
    """0.4 꾸러미는 flow_scalars_only 를 실을 수 있고, 0.3 꾸러미가 그 칸을 실으면 거절한다 — 판마다 그 판의 어휘로."""
    sha04 = next(s for s, n in op.ACCEPTED.items() if n == op.CANONICAL)
    pkg = _pkg()
    pkg["vocabulary"].update(version="0.4", sha256=sha04)
    _obj(pkg, "cae_run")["properties"]["flow_scalars_only"] = True
    got = _check(pkg)
    assert got["vocabulary"] == {"version": "0.4", "sha256": sha04} and got["rows"]
    _bad(lambda p: _obj(p, "cae_run")["properties"].update(flow_scalars_only=True), word="어휘에 없는 칸")


# ── 거절 — 아무것도 싣지 않는다 ─────────────────────────────────────────────

def _bad(mutate, *, kw=None, word=""):
    pkg = copy.deepcopy(_pkg())
    mutate(pkg)
    with pytest.raises(op.OntoPackageError) as exc:
        _check(pkg, **(kw or {}))
    assert word in str(exc.value), str(exc.value)


def _obj(pkg, typ):
    return next(o for o in pkg["objects"] if o["type"] == typ)


def test_refusals():
    _bad(lambda p: p.update(format="other"), word="모르는 꾸러미 꼴")
    _bad(lambda p: p["vocabulary"].update(sha256="0" * 64), word="받아들이지 않은 어휘 판")
    _bad(lambda p: None, kw={"report_kind": "impact"}, word="범위")
    _bad(lambda p: None, kw={"html_sha256": "f" * 64}, word="이 리포트의 꾸러미가 아니다")
    _bad(lambda p: None, kw={"case_keys": {"Run_other"}}, word="하나도 맞지 않는다")
    _bad(lambda p: _obj(p, "cae_part")["properties"].update(made_up=1), word="어휘에 없는 칸")
    _bad(lambda p: _obj(p, "cae_part")["properties"].update(severity="BAD"), word="어휘의 꼴(enum)")
    _bad(lambda p: _obj(p, "cae_part")["properties"].update(campaign="nope"), word="꾸러미에 없다")
    _bad(lambda p: _obj(p, "cae_part")["properties"].pop("part_id"), word="필수 칸")
    _bad(lambda p: p["relations"][0].update(relation="made_up"), word="모르는 관계")
    _bad(lambda p: p["relations"][0].update(dst=["cae_part", "part/999999"]), word="꾸러미에 없다")
    _bad(lambda p: p["objects"].append(copy.deepcopy(_obj(p, "cae_part"))), word="두 번")


# ── 실물(다른 리포의 표본이 있을 때) ─────────────────────────────────────────

@pytest.mark.skipif(not REAL.exists(), reason="KooD3plotReader 표본 없음")
@pytest.mark.parametrize("rel,kind", [("v14/report.ontology.json", "sphere"),
                                      ("impA/impact_report.ontology.json", "impact"),
                                      ("deep/report.ontology.json", "deep")])
def test_the_producers_real_samples_pass(rel, kind):
    p = REAL / rel
    if not p.exists():
        pytest.skip(f"{rel} 없음")
    pkg = json.loads(p.read_text(encoding="utf-8"))
    html = (pkg.get("source") or {}).get("html") or {}
    got = op.check(pkg, report_id=RID, report_kind=kind, html_sha256=html.get("sha256"), case_keys=_cases(pkg))
    assert got["rows"] and got["runs"]["matched"] == got["runs"]["package"]
