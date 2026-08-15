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
