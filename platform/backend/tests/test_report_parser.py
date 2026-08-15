# 리포트 파서(deep/sphere/impact)를 실제 생성 HTML 로 검증한다.
"""Contract tests for app.reports.parser against REAL generated report HTML.

Sample HTML lives outside the repo (SmartTwinPostprocessor sample outputs +
one freshly generated impact report). Tests skip gracefully when a sample is
absent, so CI without the samples still passes; the assertions that DO run pin
the normalized schema against ground truth.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.reports import parser

_DEEP = Path("/data/SmartTwinPostprocessor/lib/koo_deep_report/single_report/report.html")
_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")
# impact 는 세션 중 생성한 스크래치패드 산출물(있으면 검증).
_IMPACT_CANDIDATES = [
    Path("/tmp/claude-1000/-home-koopark-claude-KooRemapper/"
         "c1650bf4-b3b2-4d9d-88d1-a34a9ec0f959/scratchpad/impact_report.html"),
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


@pytest.mark.skipif(not _DEEP.exists(), reason="deep 샘플 없음")
def test_deep_normalizes():
    study = parser.parse_html(_read(_DEEP))
    assert study["kind"] == "deep"
    assert study["source"]["generator"] == "koo_deep_report"
    # 예제는 파트 23종(비연속: "23" 누락).
    assert len(study["parts"]) == 23
    assert len(study["cases"]) == 1
    c = study["cases"][0]
    assert c["case_key"] == "single"
    # 글로벌 최악 응력이 요약과 케이스 롤업에 일관.
    assert study["summary"]["peak_stress"] == pytest.approx(3748.51419693, rel=1e-6)
    assert study["summary"]["peak_stress_part_id"] == 1
    assert c["rollup"]["max_stress"] == pytest.approx(3748.51419693, rel=1e-6)
    # 파트 이름의 리터럴 백슬래시 → 그룹 추출.
    p1 = next(p for p in study["parts"] if p["part_id"] == 1)
    assert p1["group"] == "Front"


@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
def test_sphere_normalizes():
    study = parser.parse_html(_read(_SPHERE))
    assert study["kind"] == "sphere"
    assert study["source"]["generator"] == "koo_sphere_report"
    # Test_001 = 26방향(cuboid).
    assert len(study["cases"]) == 26
    assert study["project"]["doe_strategy"] == "cuboid_26"
    # 각 케이스는 각도 identity 를 갖는다.
    a0 = study["cases"][0]["identity"]["angle"]
    assert set(a0) == {"name", "roll", "pitch", "yaw", "category"}
    # 전역 최악 응력이 어느 각도에서 났는지 롤업.
    ws = study["summary"]["worst_stress"]
    assert ws["value"] is not None and ws["case_key"] is not None
    # findings 정규화(severity 문자열).
    assert all(isinstance(f["severity"], str) for f in study["findings"])


@pytest.mark.skipif(not any(p.exists() for p in _IMPACT_CANDIDATES), reason="impact 샘플 없음")
def test_impact_normalizes():
    path = next(p for p in _IMPACT_CANDIDATES if p.exists())
    study = parser.parse_html(_read(path))
    assert study["kind"] == "impact"
    assert study["source"]["generator"] == "koo_impact_report"
    # 케이스 = 충격 위치(pos_id). 2면 × 25위치 = 50 케이스.
    assert len(study["cases"]) == 50
    ident = study["cases"][0]["identity"]
    assert set(ident) >= {"face", "pos_id", "pos_x", "pos_y"}
    assert ident["face"] in {"F1", "F2"}
    # 위치당 파트 메트릭(g/s/e/d → 공통 키).
    pm = next(iter(study["cases"][0]["parts_metrics"].values()))
    assert set(pm) >= {"peak_stress", "peak_strain", "peak_g", "peak_disp"}
    # 12 파트.
    assert len(study["parts"]) == 12


def test_detect_kind_signatures():
    assert parser.detect_kind({"results": [], "sphere_coverage": 1.0}) == "sphere"
    assert parser.detect_kind({"positions": [], "results": []}) == "impact"
    assert parser.detect_kind({"generated_by": "koo_impact_report", "x": 1}) == "impact"
    assert parser.detect_kind({"sim": {}, "glstat": {}}) == "deep"
    with pytest.raises(parser.ReportParseError):
        parser.detect_kind({"nope": 1})


@pytest.mark.skipif(not _DEEP.exists(), reason="deep 샘플 없음")
def test_deep_case_energy_and_series():
    data = parser.extract_embedded_data(_read(_DEEP))
    e = parser.case_energy(data, "deep")
    assert e["kind"] == "deep"
    assert e["energy_balance"]["energy_ratio_min"] == pytest.approx(0.999311, rel=1e-4)
    assert "t" in e["energy_series"]  # glstat 에너지 시계열
    # 파트 1 시계열: von_mises global_max = 전역 최악.
    s = parser.part_series(data, "deep", "single", 1)
    assert s["part_id"] == 1
    assert s["stress"]["von_mises"]["global_max"] == pytest.approx(3748.51419693, rel=1e-6)


@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
def test_sphere_part_series():
    data = parser.extract_embedded_data(_read(_SPHERE))
    # 첫 케이스의 folder 를 case_key 로.
    r0 = (data.get("results") or [])[0]
    key = r0.get("folder") or (r0.get("angle") or {}).get("name")
    s = parser.part_series(data, "sphere", key, 1)
    assert s["kind"] == "sphere" and s["part_id"] == 1
    # 다운샘플 시계열이 있거나(측정됨) 최소한 케이스는 찾았다.
    assert "note" not in s


def test_deferred_koo_data_script():
    # deferred(tier C) 임베드: <script type=application/json id=koo-data>.
    payload = {"positions": [], "results": [], "faces": [], "doe_analysis": {}}
    html = (
        "<html><body>"
        f'<script type="application/json" id="koo-data">{json.dumps(payload)}</script>'
        "</body></html>"
    )
    data = parser.extract_embedded_data(html)
    assert parser.detect_kind(data) == "impact"
