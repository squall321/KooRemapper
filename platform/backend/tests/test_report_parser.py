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
_SPHERE_DENSE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_006_report.html")
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


def test_garbage_inputs_raise_cleanly():
    # 임베드 데이터가 없거나 빈/비HTML 입력은 ReportParseError(→400) 여야 하고, 크래시 금지.
    for bad in ("", "   ", "<html><body>no data</body></html>", "*KEYWORD\n*END\n"):
        with pytest.raises(parser.ReportParseError):
            parser.parse_html(bad)


def test_wrong_kind_hint_does_not_crash():
    # kind 힌트가 데이터 모양과 어긋나도 500(예외 누수)이 아니라 ReportParseError 로.
    sphere_like = {"results": [], "sphere_coverage": 1.0, "parts": {"1": {"name": "A", "group": "G"}}}
    # sphere dict parts 를 impact 로 강제 → 과거엔 AttributeError(500). 이제 방어.
    study = parser.parse_data(sphere_like, kind_hint="impact")
    assert study["kind"] == "impact"  # 방어적으로 정규화(케이스 0 → 상위에서 400)
    assert study["cases"] == []


@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
def test_wrong_kind_hint_on_real_sphere_html():
    # 실제 sphere HTML 에 impact 힌트 → 크래시 없이 빈 케이스(상위 인제스트가 400 처리).
    study = parser.parse_html(_read(_SPHERE), kind_hint="impact")
    assert study["cases"] == []


@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
def test_scatter_pure26_is_degenerate():
    # 순수 26면(방향당 1 run) → 26방향 배정 + degenerate(산포 0).
    data = parser.extract_embedded_data(_read(_SPHERE))
    r = parser.scatter_analysis(data, "sphere", metric="peak_stress")
    assert r["kind"] == "sphere" and r["n_bases"] == 26
    assert r["degenerate"] is True and r["most_scattered"] is None
    assert r["most_severe"]["mean"] == pytest.approx(1046.2, rel=1e-3)


@pytest.mark.skipif(not _SPHERE_DENSE.exists(), reason="dense sphere 샘플 없음")
def test_scatter_dense_sphere_real_spread():
    # 조밀 구면(1146방향) → 방향당 표본 다수 → 진짜 산포·민감도.
    data = parser.extract_embedded_data(_read(_SPHERE_DENSE))
    r = parser.scatter_analysis(data, "sphere", metric="peak_stress")
    assert r["degenerate"] is False
    assert r["n_bases"] == 26 and r["n_cases"] > 100
    assert r["most_scattered"] is not None and r["most_scattered"]["n"] >= 2
    assert r["most_scattered"]["cov"] > 0
    # 각 그룹은 방향 범주를 갖는다.
    assert {g["category"] for g in r["groups"]} <= {"face", "edge", "corner"}


def test_scatter_non_sphere_noted():
    r = parser.scatter_analysis({"sim": {}, "glstat": {}}, "deep", metric="peak_stress")
    assert "note" in r  # deep/impact 는 스캐터 미지원 안내


def test_num_rejects_nan_inf():
    # JSONB 커밋을 깨뜨리는 NaN/Inf 는 None 으로. (json.loads 는 JS NaN/Infinity 를 파싱함)
    assert parser._num(float("nan")) is None
    assert parser._num(float("inf")) is None
    assert parser._num(float("-inf")) is None
    assert parser._num(3.5) == 3.5
    assert parser._num(True) is None and parser._num("x") is None


def test_normalize_sphere_scrubs_nan_metrics():
    data = {
        "results": [{"folder": "R1", "angle": {"name": "F1", "category": "face"},
                     "parts": {"1": {"peak_stress": float("nan"), "peak_g": 5.0}}}],
        "sphere_coverage": 1.0, "parts": {"1": {"name": "A", "group": "G"}},
    }
    study = parser.parse_data(data, kind_hint="sphere")
    pm = study["cases"][0]["parts_metrics"]["1"]
    assert pm["peak_stress"] is None  # NaN → None (JSONB 안전)
    assert pm["peak_g"] == 5.0
    assert study["cases"][0]["rollup"]["max_g"] == 5.0


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
