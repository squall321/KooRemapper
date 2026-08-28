# ra.analysis.v1 NDJSON 생성기를 실제 sphere 데이터로 규격 대조 검증(네트워크·DB 불필요).
"""ReportArchive 규격(ra.analysis.v1) 준수 검증.

규격서 원칙 "예시는 실제 파서에 먹여 검증한다"를 우리 쪽에서도 지킨다 — 실제 sphere
리포트 HTML → 정규화 → NDJSON 생성기를 돌려, run 줄 + fact 줄이 규격을 따르는지 본다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.reports import parser
from app.modules.analysis.ndjson import iter_ndjson_lines

_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")


def _report_and_cases(html: str):
    study = parser.parse_html(html)
    report = SimpleNamespace(
        id="01TESTRUNKEY000000000000A", kind=study["kind"], label=study["project"]["name"],
        parts=study["parts"], findings=study["findings"],
        project_name=study["project"]["name"], test_dir=study["project"]["test_dir"],
        created_at=datetime(2026, 7, 31, 9, 12, tzinfo=timezone.utc),
    )
    cases = [SimpleNamespace(case_key=c["case_key"], identity=c["identity"],
                             parts_metrics=c["parts_metrics"]) for c in study["cases"]]
    return report, cases


@pytest.mark.skipif(not _SPHERE.exists(), reason="sphere 샘플 없음")
def test_ndjson_conforms_to_ra_analysis_v1():
    report, cases = _report_and_cases(_SPHERE.read_text(encoding="utf-8", errors="replace"))
    lines = list(iter_ndjson_lines(report, cases))
    assert len(lines) > 1

    # 모든 줄이 유효 JSON(NDJSON) + 각 줄 끝 개행.
    objs = [json.loads(ln) for ln in lines]
    assert all(ln.endswith("\n") for ln in lines)

    # 맨 앞 = run 줄, 규격 §3.1.
    run = objs[0]
    assert run["type"] == "run"
    assert run["schema"] == "ra.analysis.v1"
    assert run["schema_version"] == 1
    assert run["workflow"] == "full_angle_drop"  # sphere
    assert run["run_key"] == "01TESTRUNKEY000000000000A"
    assert run["units"]["stress"] == "MPa" and run["units"]["g"] == "G"  # 단위 명시(§3.1 경고)
    assert run["parts"] and all("part_name" in v for v in run["parts"].values())
    assert run["analyzed_at"].startswith("2026-07-31T09:12")

    # 나머지 = fact 줄, 규격 §3.2.
    facts = objs[1:]
    assert facts and all(f["type"] == "fact" for f in facts)
    for f in facts:
        assert isinstance(f["value"], (int, float)) and not isinstance(f["value"], bool)  # 숫자만
        assert f["axis_key"] and f["part_key"] and f["quantity"]
    # sphere axis_meta 에 방향(roll/pitch) → 구면 분포도 트리거.
    assert any("roll" in f["axis_meta"] and "pitch" in f["axis_meta"] for f in facts)
    # 물리량은 알려진 집합.
    assert {f["quantity"] for f in facts} <= {
        "stress", "strain", "g", "disp", "max_principal_stress", "min_principal_stress", "vm_strain"}


def test_ndjson_skips_nonnumeric_values():
    report = SimpleNamespace(
        id="X", kind="sphere", label="t", parts=[{"part_id": 1, "name": "A", "group": "G"}],
        findings=[], project_name="p", test_dir=None, created_at=None,
    )
    cases = [SimpleNamespace(case_key="c1", identity={"angle": {"roll": 0, "pitch": 90}},
                             parts_metrics={"1": {"peak_stress": None, "peak_g": 5.0}})]
    objs = [json.loads(x) for x in iter_ndjson_lines(report, cases)]
    facts = [o for o in objs if o["type"] == "fact"]
    # None 은 건너뛰고 5.0(g)만 fact 로.
    assert len(facts) == 1 and facts[0]["quantity"] == "g" and facts[0]["value"] == 5.0
    assert objs[0]["analyzed_at"] is None  # created_at 없으면 null(지어내지 않음)
