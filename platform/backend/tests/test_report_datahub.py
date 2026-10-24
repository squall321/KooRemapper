# DataHub 등재 레코드 빌더(순수 함수) 검증 — 네트워크 불필요.
"""Unit tests for app.reports.datahub record building (no network).

Verifies the generic sim_report envelope: eng_meta shape (DoeRef-safe), domain
discriminators land in durable places (inputs + tags + attachment.extra), and
stage parsing rules.
"""
from __future__ import annotations

import pytest

from app.models import ImpactCase, ImpactReport
from app.reports import datahub


def _report():
    r = ImpactReport(
        id="01TESTREPORT0000000000000",
        session_id="s", user_id=1, kind="sphere",
        generator="koo_sphere_report", project_name="Test_001",
        doe_strategy="cuboid_26", test_dir="/x",
        sim_params={"yield_stress": 800}, parts=[{"part_id": 1, "name": "Front\\Metal", "group": "Front"}],
        findings=[{"severity": "CRITICAL", "title": "t", "detail": "d", "recommendation": "r"}],
        summary={"worst_stress": {"value": 1046.2}}, n_cases=1,
    )
    c = ImpactCase(
        report_id=r.id, case_key="Run_x", identity={"angle": {"name": "E01"}},
        parts_metrics={"1": {"peak_stress": 1046.2}}, max_stress=1046.2, max_g=4.9e5,
    )
    return r, [c]


def test_parse_stage_rules():
    assert datahub.parse_stage("dv1") == {"phase": "dv", "round": "1"}
    assert datahub.parse_stage("pre") == {"phase": "pre"}
    assert datahub.parse_stage("pvr") == {"phase": "pv", "round": "r"}
    for bad in ("dv", "pre1", "xx", ""):
        with pytest.raises(datahub.DataHubError):
            datahub.parse_stage(bad)


def test_build_record_generic_envelope():
    r, cases = _report()
    rec = datahub.build_record(
        r, cases, sim_id="SIM-MX-CAE-2026-0000000001",
        project="S26-DROP", stage="dv1", variation="antA",
        doe="fullangle26:Test_001", unit="mm-t-s", title=None, html_name="report.html",
    )
    assert rec["data_type"] == "SIM" and rec["doc_type"] == "sim_report"
    assert rec["source_system"] == "DynaForge"
    # DoeRef 안전: study/case/factors 만.
    doe = rec["content"]["eng_meta"]["doe"]
    assert set(doe) <= {"study", "case", "factors"}
    assert doe["study"] == "fullangle26" and doe["case"] == "Test_001"
    assert doe["factors"]["strategy"] == "cuboid_26"
    assert rec["content"]["eng_meta"]["dev_revision"] == {"phase": "dv", "round": "1"}
    assert rec["content"]["eng_meta"]["design_variation"] == "antA"
    # 도메인 판별자는 생존 위치 3곳에.
    assert rec["content"]["inputs"]["sim_domain"] == "drop_impact"
    assert rec["content"]["inputs"]["report_kind"] == "sphere"
    assert "sim:drop_impact" in rec["tags"] and "kind:sphere" in rec["tags"]
    assert rec["content"]["attachments"][0]["extra"]["report_kind"] == "sphere"
    # 첨부 경로 규약(zip 내 경로와 일치해야 함).
    assert rec["content"]["attachments"][0]["file_path"] == "SIM-MX-CAE-2026-0000000001/report.html"
    assert rec["content"]["attachments"][0]["kind"] == "document"
    # 파트 → components, 최악 케이스 요약.
    assert len(rec["content"]["components"]) == 1
    assert rec["content"]["outputs"]["worst_cases"][0]["max_stress"] == 1046.2


def test_build_record_without_doe():
    r, cases = _report()
    rec = datahub.build_record(
        r, cases, sim_id="SIM-MX-CAE-2026-0000000002",
        project="P", stage="pre", variation=None, doe=None, unit="mm-t-s",
        title=None, html_name="r.html",
    )
    # doe 미지정이면 eng_meta.doe 없음(DoeRef.study 필수라 빈 doe 를 만들지 않는다).
    assert "doe" not in rec["content"]["eng_meta"]
    # doe_strategy 는 inputs 에 항상 보존.
    assert rec["content"]["inputs"]["doe_strategy"] == "cuboid_26"


def test_build_record_attaches_a_registered_hub_expert():
    """등재 레코드는 허브에 등록된 전문가 밑으로 간다(HWAX 요청서 10-15 K6-1 나).

    예전 키 dynaforge-report 는 허브에 등록된 적이 없어, 적재가 이름=키·설명 0자의 빈 전문가를
    말없이 만들었다(2026-08-15 스모크 등재). 이 등재는 낙하 해석이라 있는 전문가로 돌린다.
    """
    r, cases = _report()
    rec = datahub.build_record(
        r, cases, sim_id="SIM-MX-CAE-2026-0000000003",
        project="P", stage="dv1", variation=None, doe=None, unit="mm-t-s",
        title=None, html_name="r.html",
    )
    assert rec["agents"] == ["sim-drop-impact"]
    assert datahub.HUB_AGENT == "sim-drop-impact"


def test_build_record_carries_hotspot_summary_only_when_given():
    # 결정 7A(10-24) — 핫스팟 요약은 content.outputs.hotspots 에. 안 주면 키를 두지 않는다(빈 목록을 지어내지 않는다).
    r, cases = _report()
    kw = dict(sim_id="SIM-MX-CAE-2026-0000000002", project="S26-DROP", stage="dv1", variation=None,
              doe=None, unit="mm-t-s", title=None, html_name="report.html")
    hs = {"n_clusters": 3, "criteria": ["max_shear"], "parts": [1],
          "envelope": [{"part_id": 1, "criterion": "max_shear", "worst_angle": "E01", "stress_max": 812.0, "n_angles": 2}]}
    rec = datahub.build_record(r, cases, hotspots=hs, **kw)
    assert rec["content"]["outputs"]["hotspots"] == hs
    rec2 = datahub.build_record(r, cases, **kw)
    assert "hotspots" not in rec2["content"]["outputs"]


@pytest.mark.parametrize("kind,canned,expect", [
    ("sphere", {"available": True, "n_clusters": 5, "criteria": ["max_shear"], "parts": [1, 2], "order": "stress_max",
                "order_note": "n", "envelope": [{"part_id": 1}], "envelope_note": "e", "clusters": [{"x": 1}]},
     {"envelope": [{"part_id": 1}], "envelope_note": "e"}),
    ("deep", {"available": True, "n_clusters": 2, "criteria": ["x_tension"], "parts": [3], "order": "stress_max",
              "order_note": "n", "clusters": [{"part_id": 3}], "truncated": {"returned": 1, "total": 2}},
     {"clusters": [{"part_id": 3}], "truncated": {"returned": 1, "total": 2}}),
    ("deep", {"available": False, "n_records": 0, "clusters": []}, None),
    ("impact", {"available": True, "clusters": [{"part_id": 9}]}, None),
])
async def test_datahub_hotspot_summary_follows_the_hotspots_route(monkeypatch, kind, canned, expect):
    # 등재 요약은 `/hotspots` 와 같은 계산을 쓴다(베끼지 않는다) — sphere 는 포락, deep 은 군집, 없으면 None.
    from app.modules.reports import services
    calls = []

    async def fake_hotspots(db, report, **kw):
        calls.append(kw)
        return canned
    monkeypatch.setattr(services, "hotspots", fake_hotspots)
    r, _ = _report()
    r.kind = kind
    got = await services._datahub_hotspot_summary(None, r)
    if expect is None:
        assert got is None
    else:
        for k, v in expect.items():
            assert got[k] == v
        assert got["n_clusters"] == canned["n_clusters"] and got["criteria"] == canned["criteria"]
        assert ("envelope" in got) == (kind == "sphere") and ("clusters" in got) == (kind == "deep")
        assert calls == [{"top": services._DATAHUB_HOTSPOT_TOP}]
