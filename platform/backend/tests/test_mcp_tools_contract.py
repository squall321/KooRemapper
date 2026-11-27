# MCP 도구 인자 설명(포털 arg-descriptions §2-3)과 MCP → REST 시간 한도(포털 time-limits 1-1)를 지키는 시험 — 사용자 결정 10-31
"""MCP 서버는 별도 venv 라 백엔드 venv 에서 import 하지 못한다. 그래서 `tests/mcp_probe.py` 를 그쪽 python 으로 돌려 FastMCP 목록
(`mcp.list_tools()`)과 느린 가짜 백엔드에서의 동작을 JSON 으로 받는다. MCP venv 가 없는 박스에서는 건너뛴다.

① 설명 — 게이트웨이가 세는 것은 inputSchema 맨 위 인자의 `description` 이다(`title` 아님). 형 · 기본값 · 필수 · 순서는 설명을 달기 전
   그대로여야 한다(`fixtures/mcp_arg_contract.json`). 허용값 · 상한 · 단위는 MCP 쪽 상수에서 만들고, 그 상수가 백엔드의 실제 제약과
   같은지를 여기서 대조한다 — 같은 이름의 인자라도 도구마다 뜻이 다르면 문구가 달라야 한다(severity).
② 한도 — 손잡이 기본값이 게이트웨이 600초보다 작고, 늦는 백엔드 · 여러 번 부르는 도구 · 안 끝나는 그림 잡이 호출 하나의 기한 안에
   손잡이 이름이 든 문구로 끝난다.
stateless — 서버가 세션을 쥐지 않는다(포털 MCP 현대화 1단계 · 사용자 결정 11-27). 실제 streamable-http 앱에 보내 본다.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PLATFORM = Path(__file__).resolve().parents[2]
SERVER = PLATFORM / "mcp_server" / "server.py"
MCP_PY = PLATFORM / "mcp_server" / "venv" / "bin" / "python"
PROBE = Path(__file__).with_name("mcp_probe.py")
CONTRACT = Path(__file__).with_name("fixtures") / "mcp_arg_contract.json"
TOOLS = ("create_session", "run_operation", "report_summary", "report_part_risk", "report_directional",
         "find_reports", "report_part_series", "report_findings")
needs_mcp = pytest.mark.skipif(not MCP_PY.exists(), reason="MCP venv 없음(platform/mcp_server/venv)")


def _probe(*args: str) -> dict:
    env = {"PATH": "/usr/bin:/bin"}            # 박스의 KOORM_MCP_API_TIMEOUT_S 가 섞이지 않게 — 기본값을 잰다
    got = subprocess.run([str(MCP_PY), "-I", str(PROBE), *args], capture_output=True, text=True, timeout=180, env=env)
    assert got.returncode == 0, got.stderr[-2000:]
    return json.loads(got.stdout.strip().splitlines()[-1])


def _server_constants() -> dict:
    """server.py 의 상수(리터럴)를 AST 로 — MCP 를 import 하지 않고 읽는다."""
    out = {}
    for node in ast.parse(SERVER.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                names = [tgt] if isinstance(tgt, ast.Name) else list(getattr(tgt, "elts", []))
                values = [node.value] if isinstance(tgt, ast.Name) else list(getattr(node.value, "elts", []))
                for n, v in zip(names, values):
                    if isinstance(n, ast.Name):
                        try:
                            out[n.id] = ast.literal_eval(v)
                        except ValueError:
                            pass
    return out


@pytest.fixture(scope="module")
def schemas() -> dict:
    return _probe("schemas", *TOOLS)


# ── ① 인자 설명 ─────────────────────────────────────────────────────────────

@needs_mcp
def test_every_argument_of_the_requested_tools_is_described(schemas):
    missing = [f"{t}.{a}" for t in TOOLS for a, spec in (schemas["tools"][t].get("properties") or {}).items()
               if not str(spec.get("description") or "").strip()]
    n = sum(len(schemas["tools"][t].get("properties") or {}) for t in TOOLS)
    # 36 → 37: find_reports 에 external_job_key 를 덧붙였다(2026-11-12, 포털 낙하 파이프라인 (b))
    # 37 → 38: find_reports 에 config_generation 을 덧붙였다(2026-11-22, DF-02 설정 세대)
    assert n == 38 and not missing, (n, missing)


@needs_mcp
def test_the_argument_contract_did_not_change(schemas):
    """형 · 기본값 · 필수 · 순서는 설명을 달기 전과 같다 — 설명만 단다(포털 §5)."""
    want = json.loads(CONTRACT.read_text(encoding="utf-8"))["tools"]
    for t in TOOLS:
        sch = schemas["tools"][t]
        got = {"args": [{"name": k, "schema": {kk: vv for kk, vv in v.items() if kk not in ("description", "title")}}
                        for k, v in (sch.get("properties") or {}).items()],
               "required": sch.get("required") or []}
        assert got == want[t], t


def _query(path: str, name: str):
    from app.main import app
    for r in app.routes:
        if getattr(r, "path", "") == path and "GET" in getattr(r, "methods", set()):
            for p in r.dependant.query_params:
                if name in (p.name, getattr(p, "alias", None)):   # 별칭으로도 — `status` 는 모듈 이름과 겹쳐 `status_` 로 받는다
                    return p.field_info
    raise AssertionError(f"{path} 에 {name} 가 없다")


def _pattern_values(info) -> tuple:
    pat = next(m.pattern for m in info.metadata if getattr(m, "pattern", None))
    return tuple(re.fullmatch(r"\^\((.*)\)\$", pat).group(1).split("|"))


def test_the_allowed_values_in_descriptions_are_the_backend_constraints():
    """MCP 상수(설명의 원천)가 백엔드의 실제 제약과 같다 — 다르면 설명이 거짓이 된다(LaminateAnalyzer 의 detail 이 그랬다)."""
    c = _server_constants()
    assert c["REPORT_KINDS"] == _pattern_values(_query("/api/v1/reports", "kind"))
    assert c["SEVERITIES"] == _pattern_values(_query("/api/v1/reports", "severity"))
    assert c["FIND_SORTS"] == _pattern_values(_query("/api/v1/reports", "sort"))
    assert c["SORT_ORDERS"] == _pattern_values(_query("/api/v1/reports", "order"))
    assert c["FIND_LIMIT_MAX"] == next(m.le for m in _query("/api/v1/reports", "limit").metadata if hasattr(m, "le"))
    assert c["HEIGHT_TOL_MM"] == _query("/api/v1/reports", "height_tol").default
    from app.modules.reports.services import _SEVERITY_RANK
    assert c["SEVERITIES"] == tuple(sorted(_SEVERITY_RANK, key=_SEVERITY_RANK.get, reverse=True)), "높은 것부터"
    from app.modules.sessions.schemas import SessionCreate
    assert c["SESSION_NAME_MAX"] == next(m.max_length for m in SessionCreate.model_fields["name"].metadata
                                         if hasattr(m, "max_length"))
    from app.modules.analysis.ndjson import _UNITS
    assert (c["UNIT_STRESS"], c["UNIT_ACCEL"], c["UNIT_LENGTH"]) == (_UNITS["stress"], _UNITS["g"], _UNITS["disp"])


@needs_mcp
def test_the_descriptions_say_the_values_and_each_tools_own_meaning(schemas):
    c = _server_constants()
    find = schemas["tools"]["find_reports"]["properties"]
    assert all(v in find["kind"]["description"] for v in c["REPORT_KINDS"])
    assert all(v in find["sort"]["description"] for v in c["FIND_SORTS"])
    assert f"1~{c['FIND_LIMIT_MAX']}" in find["limit"]["description"]
    assert c["UNIT_STRESS"] in find["min_worst_stress"]["description"] and c["UNIT_ACCEL"] in find["min_worst_g"]["description"]
    findings = schemas["tools"]["report_findings"]["properties"]["severity"]["description"]
    assert all(v in find["severity"]["description"] and v in findings for v in c["SEVERITIES"])
    # 같은 이름이라도 뜻이 다르다 — 찾기는 「이상」, 소견은 「같은 것만」(같은 문구를 쓰면 한쪽이 거짓이다)
    assert "이상" in find["severity"]["description"] and "같은" in findings and find["severity"]["description"] != findings


# ── ② 시간 한도 ─────────────────────────────────────────────────────────────

@needs_mcp
def test_the_default_limit_is_inside_the_gateway_limit(schemas):
    assert schemas["knob"] == "KOORM_MCP_API_TIMEOUT_S"
    assert schemas["gateway_call_timeout_s"] == 600 and 0 < schemas["api_timeout_s"] < 600, schemas


def test_no_hard_coded_limit_is_left_in_the_mcp_server():
    """예전엔 60 · 120 · 180 · 300 이 열여덟 곳에 글자로 박혀 있었다 — 남으면 그 도구만 손잡이를 안 따른다."""
    src = SERVER.read_text(encoding="utf-8")
    assert not re.findall(r"AsyncClient\([^)]*timeout=\d", src), "글자로 박힌 한도가 남았다"


@needs_mcp
def test_slow_backends_end_inside_one_call_deadline_with_the_knob_named():
    """손잡이 1초로 — 늦는 읽기 · 리포트 여섯 비교(요청 열둘 × 0.4초) · 안 끝나는 그림 잡이 1초 남짓에 끝나고 손잡이 이름을 말한다."""
    got = _probe("limits")
    assert got["api_timeout_s"] == 1.0
    knob = got["knob"]
    assert got["find_fast"]["ok"], got["find_fast"]
    for case in ("find_slow", "compare_six", "figure_never"):
        r = got[case]
        assert not r["ok"] and knob in (r["error"] or "") and r["elapsed"] < 1.8, (case, r)
    assert "job_id=j1" in got["figure_never"]["error"], "그림 잡은 계속 돈다 — 무엇을 지켜볼지 말해야 한다"


# ── 해석 온톨로지 도구(cae — 사용자 결정 10-31 (가)) ─────────────────────────

CAE_TOOLS = ("attach_cae_package", "report_cae", "find_cae_parts", "find_cae_load_paths")


@needs_mcp
def test_the_cae_tools_describe_every_argument():
    got = _probe("schemas", *CAE_TOOLS)["tools"]
    assert set(got) == set(CAE_TOOLS), sorted(got)
    missing = [f"{t}.{a}" for t in CAE_TOOLS for a, spec in (got[t].get("properties") or {}).items()
               if not str(spec.get("description") or "").strip()]
    assert not missing, missing


def test_the_cae_allowed_values_are_the_backend_constraints():
    c = _server_constants()
    assert c["CAE_SEVERITIES"] == _pattern_values(_query("/api/v1/cae/parts", "min_severity"))
    assert c["CAE_PATH_SORTS"] == _pattern_values(_query("/api/v1/cae/load-paths", "sort"))
    for path in ("/api/v1/cae/parts", "/api/v1/cae/load-paths"):
        assert c["CAE_LIMIT_MAX"] == next(m.le for m in _query(path, "limit").metadata if hasattr(m, "le"))
        assert c["REPORT_KINDS"] == _pattern_values(_query(path, "kind"))
    from app.modules.reports.services import CAE_PATH_SORTS, CAE_SEVERITY_RANK
    assert c["CAE_PATH_SORTS"] == CAE_PATH_SORTS
    ranked = tuple(k for k in sorted(CAE_SEVERITY_RANK, key=CAE_SEVERITY_RANK.get, reverse=True) if k != "INFO")
    assert c["CAE_SEVERITIES"] == ranked, "판정은 높은 것부터 — 소견만 쓰는 INFO 는 파트 판정에 없다"


# ── 캠페인 묶음 적재 도구(DF-01 · 11-20) ─────────────────────────────────────

CAMPAIGN_TOOLS = ("create_campaign", "ingest_campaign_manifest", "campaign_ingest_status",
                  # ② 출처 · 유효성(DF-02 · DF-03 · 11-22)
                  "set_campaign_health_thresholds", "campaign_provenance", "campaign_health_table", "report_health",
                  # ③ 추출 완전성 · 삭제 관문(DF-04 · 11-22)
                  "set_campaign_required_extractions", "campaign_deletion_clearance", "report_extraction",
                  # ④ 보고서용 묶음(DF-13 · 11-22)
                  "build_report_bundle", "report_bundle", "report_bundle_diff",
                  # ⑤ 캠페인 분석(DF-05 · 06 · 08 ~ 12 · 11-22)
                  "set_campaign_part_groups", "campaign_angle_table", "campaign_angle_stats", "campaign_peak_table",
                  "set_campaign_criteria", "campaign_part_margin", "campaign_sphere_map", "set_campaign_sites", "campaign_site_table",
                  "campaign_site_map", "import_part_map", "compare_campaigns", "set_campaign_pair_rule", "compare_config_pairs",
                  # ⑥ 핫스팟 자리 · 덱 세션(DF-07 · DF-15 · 11-22)
                  "set_campaign_frame_offset", "campaign_hotspot_sites", "rename_session_part")


@needs_mcp
def test_the_campaign_tools_describe_every_argument_and_mirror_the_rest_body():
    got = _probe("schemas", *CAMPAIGN_TOOLS)["tools"]
    assert set(got) == set(CAMPAIGN_TOOLS), sorted(got)
    missing = [f"{t}.{a}" for t in CAMPAIGN_TOOLS for a, spec in (got[t].get("properties") or {}).items()
               if not str(spec.get("description") or "").strip()]
    assert not missing, missing
    # 도구의 인자가 REST 본문의 칸과 같다 — 한쪽에만 칸이 생기면 그 칸은 MCP 로 못 보내거나 422 가 된다(모르는 칸은 거절)
    from app.modules.campaigns.routes import CampaignBody
    assert set(got["create_campaign"]["properties"]) == set(CampaignBody.model_fields)
    c = _server_constants()
    status = got["campaign_ingest_status"]["properties"]
    assert all(v in status["state"]["description"] for v in c["CAMPAIGN_STATES"])
    assert f"1~{c['CAMPAIGN_RUNS_MAX']}" in status["limit"]["description"]
    assert f"1~{c['CAMPAIGN_RUNS_MAX']}" in got["ingest_campaign_manifest"]["properties"]["runs"]["description"]
    # 문턱 쓰기 도구의 인자 = REST 본문의 칸(+ campaign_id) · 런 목록 설명에 ② 칸 이름이 다 있다
    from app.modules.campaigns.routes import HealthBody, ProvenanceBody, RunItem, ThresholdsBody
    assert set(got["set_campaign_health_thresholds"]["properties"]) == set(ThresholdsBody.model_fields) | {"campaign_id"}
    runs_desc = got["ingest_campaign_manifest"]["properties"]["runs"]["description"]
    for name in [*RunItem.model_fields, *ProvenanceBody.model_fields, *HealthBody.model_fields]:
        assert name in runs_desc, name
    for t in ("campaign_provenance", "campaign_health_table"):
        assert f"1~{c['CAMPAIGN_RUNS_MAX']}" in got[t]["properties"]["limit"]["description"], t
    for k, v in c["HEALTH_THRESHOLD_DEFAULTS"].items():
        assert k in got["create_campaign"]["properties"]["health_thresholds"]["description"], k
    # ③ — 런 목록 설명에 추출 칸이 다 있고, 필수 목록 설명에 항목 칸이 다 있다 · 쓰기 도구의 인자 = REST 본문(+ campaign_id)
    from app.modules.campaigns.routes import ExtractionBody, FieldItem, RequiredBody, RequiredItem
    for name in [*ExtractionBody.model_fields, *FieldItem.model_fields]:
        assert name in runs_desc, name
    for t, arg in (("create_campaign", "required_extractions"), ("set_campaign_required_extractions", "required_extractions")):
        desc = got[t]["properties"][arg]["description"]
        assert all(name in desc for name in RequiredItem.model_fields), (t, desc)
    assert set(got["set_campaign_required_extractions"]["properties"]) == set(RequiredBody.model_fields) | {"campaign_id"}
    clear = got["campaign_deletion_clearance"]["properties"]
    assert all(v in clear["status"]["description"] for v in c["CLEARANCE_STATUSES"])
    assert f"1~{c['CAMPAIGN_RUNS_MAX']}" in clear["limit"]["description"]
    # ④ — 짓기 도구의 인자 = REST 본문의 칸 · 명세 설명에 표 종류 · 지표 이름이 다 있다 · 쪽 상한이 설명에 있다
    from app.modules.campaigns import bundles as B
    from app.modules.campaigns.routes import BundleBody, BundleSpec, FigureSpec, TableSpec
    assert set(got["build_report_bundle"]["properties"]) == set(BundleBody.model_fields)
    spec_desc = got["build_report_bundle"]["properties"]["spec"]["description"]
    for name in [*BundleSpec.model_fields, *TableSpec.model_fields, *FigureSpec.model_fields, *c["BUNDLE_TABLE_KINDS"],
                 *B.RUN_METRICS, *B.CASE_METRICS, *B.PART_METRICS]:
        assert name in spec_desc, name
    assert f"1~{c['BUNDLE_ITEMS_PAGE_MAX']}" in got["report_bundle"]["properties"]["limit"]["description"]
    # ⑤ — 쓰기 도구의 인자 = REST 본문의 칸(+ campaign_id) · 항목 설명에 항목 칸 이름이 다 있다 · 런 목록 설명에 충격 칸
    from app.modules.campaigns import analysis_routes as AR
    from app.modules.campaigns.routes import ImpactItem
    for t, body, extra in (("set_campaign_part_groups", AR.GroupsBody, {"campaign_id"}), ("set_campaign_criteria", AR.CriteriaBody, {"campaign_id"}),
                           ("set_campaign_sites", AR.SitesBody, {"campaign_id"}), ("import_part_map", AR.PartMapBody, set()),
                           ("set_campaign_pair_rule", AR.PairRuleBody, {"campaign_id"})):
        assert set(got[t]["properties"]) == set(body.model_fields) | extra, t
    for t, arg, items in (("set_campaign_part_groups", "groups", [AR.GroupItem]), ("set_campaign_criteria", "criteria", [AR.CriterionItem]),
                          ("set_campaign_sites", "sites", [AR.SiteItem, AR.SiteMetricItem, AR.SiteImpactor]),
                          ("import_part_map", "rows", [AR.PartMapRow]), ("set_campaign_pair_rule", "metrics", [AR.PairMetricItem])):
        desc = got[t]["properties"][arg]["description"]
        for m in items:
            for name in m.model_fields:
                assert name in desc, (t, name)
    for name in ImpactItem.model_fields:
        assert name in runs_desc, name
    for t in ("campaign_angle_table", "campaign_peak_table"):
        assert f"1~{c['ANALYSIS_ROWS_MAX']}" in got[t]["properties"]["limit"]["description"], t
    for t in ("campaign_angle_table", "campaign_angle_stats", "campaign_peak_table", "campaign_sphere_map", "compare_campaigns"):
        key = "metrics" if t == "campaign_angle_table" else "metric"
        assert all(m in got[t]["properties"][key]["description"] for m in c["ANGLE_METRICS"] + c["METRIC_ALIASES"]), t
    assert all(a in got["campaign_part_margin"]["properties"]["metric_axis"]["description"] for a in c["MARGIN_AXES"])
    # ⑥ — 쓰기 도구의 인자 = REST 본문(+ 경로 칸)
    from app.modules.campaigns.analysis_routes import FrameOffsetBody
    from app.modules.sessions.schemas import PartRename
    assert set(got["set_campaign_frame_offset"]["properties"]) == set(FrameOffsetBody.model_fields) | {"campaign_id"}
    assert set(got["rename_session_part"]["properties"]) == set(PartRename.model_fields) | {"session_id", "part_id"}


def test_the_campaign_allowed_values_are_the_backend_constraints():
    c = _server_constants()
    from app.modules.campaigns.routes import RunsBody
    from app.modules.campaigns.services import STATES
    assert c["CAMPAIGN_STATES"] == STATES
    limit = _query("/api/v1/campaigns/{campaign_id}/ingest-status", "limit")
    assert c["CAMPAIGN_RUNS_MAX"] == next(m.le for m in limit.metadata if hasattr(m, "le"))
    assert c["CAMPAIGN_RUNS_MAX"] == next(m.max_length for m in RunsBody.model_fields["runs"].metadata
                                          if hasattr(m, "max_length"))
    from app.modules.campaigns.health import DEFAULTS
    assert c["HEALTH_THRESHOLD_DEFAULTS"] == DEFAULTS
    for path in ("/api/v1/campaigns/{campaign_id}/provenance", "/api/v1/campaigns/{campaign_id}/health",
                 "/api/v1/campaigns/{campaign_id}/deletion-clearance"):
        limit = _query(path, "limit")
        assert c["CAMPAIGN_RUNS_MAX"] == next(m.le for m in limit.metadata if hasattr(m, "le")), path
    # 허가 상태 단어 = 백엔드 판정의 상태 = 경로의 status 허용값
    from app.modules.campaigns.extraction import STATUSES as CLEAR
    assert c["CLEARANCE_STATUSES"] == CLEAR
    from typing import get_args
    st = _query("/api/v1/campaigns/{campaign_id}/deletion-clearance", "status")
    assert set(get_args(get_args(st.annotation)[0])) == set(CLEAR), st.annotation
    # ④ 표 종류 = 백엔드 명세의 kind · 쪽 상한 = 두 판 읽기 경로의 limit 상한
    from app.modules.campaigns.routes import TableSpec
    assert set(c["BUNDLE_TABLE_KINDS"]) == set(get_args(TableSpec.model_fields["kind"].annotation))
    for path in ("/api/v1/bundles/{bundle_id}", "/api/v1/campaigns/{campaign_id}/bundles/latest"):
        assert c["BUNDLE_ITEMS_PAGE_MAX"] == next(m.le for m in _query(path, "limit").metadata if hasattr(m, "le")), path
    # ⑤ 지표 · 별칭 · 축 이름 = 백엔드 각도 모듈의 것 · 행 상한 = 각도 표 · 피크 표 경로의 limit 상한 · 표 종류 축
    from app.modules.campaigns import angles as G
    assert c["ANGLE_METRICS"] == G.METRICS and c["METRIC_ALIASES"] == tuple(G.METRIC_ALIASES)
    assert c["MARGIN_AXES"] == tuple(G.MARGIN_AXES) and c["THICKNESS_AXES"] == G.AXES_THICK
    for path in ("/api/v1/campaigns/{campaign_id}/angle-table", "/api/v1/campaigns/{campaign_id}/peaks"):
        assert c["ANALYSIS_ROWS_MAX"] == next(m.le for m in _query(path, "limit").metadata if hasattr(m, "le")), path


# ── 경로 칸 감싸기(검토 반영 11-11 · 재검토 11-12) ─────────────────────────────────────
# 예전엔 경로에 사용자 값을 그대로 넣어 `ID?` 가 `DELETE /api/v1/reports/ID`(리포트 지우기)로, `#` 이 뒤를 자르고, `..` 이 남의 길로
# 갔다. 이제 경로의 사용자 값은 모두 `_seg(…)`(quote safe='' + 점 칸 감싸기)를 지나고, ★`/` · `\` 가 든 값은 거절한다 — 백엔드
# (uvicorn)는 `%2F` 를 `/` 로 풀어 그 길로 라우팅하므로 감싸도 칸 하나가 아니었다(rr4 — `delete_report(id+'/revision')` 가 끊기 라우트로).
# 과제명 · 객체 key 는 `/` 가 들 수 있고 받는 라우트가 `{…:path}` 라 `_seg_key`(예전 감싸기 그대로)를 쓴다 — 그 셋만.

KEY_PATHS = {"/ontology/tasks/{_seg_key(task_key)}/revisions", "/ontology/tasks/{_seg_key(task_key)}/compare",
             "/ontology/objects/{_seg(type_slug)}/{_seg_key(key)}"}


def test_every_path_f_string_wraps_its_values_in_seg():
    """정적 — server.py 의 경로 f-문자열(`f"/…"`)에 든 값은 하나도 빠짐없이 `_seg(…)` 다(새 도구가 빠뜨리면 여기서 빨개진다). `/` 를
    받는 `_seg_key(…)` 는 `{…:path}` 라우트 셋에만 — 다른 칸에 쓰면 `/` 가 다른 라우트로 샌다."""
    bad, keyed, n = [], set(), 0
    for node in ast.walk(ast.parse(SERVER.read_text(encoding="utf-8"))):
        if not (isinstance(node, ast.JoinedStr) and node.values and isinstance(node.values[0], ast.Constant)
                and str(node.values[0].value).startswith("/")):
            continue
        for v in node.values:
            if isinstance(v, ast.FormattedValue):
                n += 1
                call = v.value
                name = getattr(call.func, "id", "") if isinstance(call, ast.Call) else ""
                if name == "_seg_key":
                    keyed.add(ast.unparse(node)[2:-1])
                elif name != "_seg":
                    bad.append(ast.unparse(node))
    assert n >= 80 and not bad, (n, bad)
    assert keyed == KEY_PATHS, keyed


NASTY = ("01AB?x", "a/../../sessions/S1", "..", ".", "id#frag", "with space", "a\\b")
REFUSED = {"a/../../sessions/S1", "a\\b"}      # id 칸에서 거절 — 리포트 · 세션 · 잡 · 파일 id 에는 `/` · `\` 가 없다
PATHS = {   # 도구 → 백엔드가 받아야 할 경로(s 는 `_seg` 로 감싼 칸, k 는 `_seg_key` 로 감싼 key)
    "report_summary": "/api/v1/reports/{s}",
    "delete_report": "/api/v1/reports/{s}",
    "report_revision": "/api/v1/reports/{s}/revision",
    "unlink_report_revision": "/api/v1/reports/{s}/revision",
    "clear_report_unlink": "/api/v1/reports/{s}/revision/unlinked",
    "report_case": "/api/v1/reports/{s}/cases/{s}",
    "get_session": "/api/v1/sessions/{s}",
    "task_revisions": "/api/v1/ontology/tasks/{k}/revisions",
    "compare_task_revisions": "/api/v1/ontology/tasks/{k}/compare",
    "ontology_object": "/api/v1/ontology/objects/{s}/{k}",
    "recipe_get": "/api/v1/recipes/{s}",
    "ingest_campaign_manifest": "/api/v1/campaigns/{s}/runs",
}


@needs_mcp
def test_nasty_ids_reach_the_backend_as_one_encoded_segment():
    """`?` · `..` · `.` · `#` · 빈칸이 든 값이 경로 칸 **하나**로 그대로 간다 — 다른 길(리포트 지우기 · 남의 세션)로 새지 않는다.
    `/` · `\\` 가 든 id 는 **보내지 않고 거절**한다(백엔드가 `%2F` 를 풀어 다른 라우트로 간다 — 재검토 rr4). `/` 가 들 수 있는 과제명 ·
    객체 key 는 `{…:path}` 라우트로 감싼 그대로 간다."""
    got = _probe("paths", *NASTY)
    common = {"01AB?x": "01AB%3Fx", "..": "%2E%2E", ".": "%2E", "id#frag": "id%23frag", "with space": "with%20space"}
    assert {v: e for v, e in got["seg"].items() if v not in REFUSED} == common, got["seg"]
    assert all(got["seg"][v].startswith("REFUSED: ") and "경로 값" in got["seg"][v] for v in REFUSED), got["seg"]
    assert got["seg_key"] == {**common, "a/../../sessions/S1": "a%2F..%2F..%2Fsessions%2FS1", "a\\b": "a%5Cb"}, got["seg_key"]
    assert set(got["calls"]) == set(PATHS), sorted(got["calls"])
    for tool, per in got["calls"].items():
        for v, rec in per.items():
            sent = [p for _, p in rec["seen"]]
            if v in REFUSED and "{s}" in PATHS[tool]:
                assert sent == [] and "경로 값" in (rec["error"] or ""), (tool, v, sent, rec["error"])
                continue
            want = PATHS[tool].format(s=got["seg"][v], k=got["seg_key"][v])
            assert sent and sent[0] == want, (tool, v, sent, rec["error"])


# ── stateless(포털 MCP 현대화 1단계 · 사용자 결정 11-27) ─────────────────────────────────────

# stateless 에서 버려지는 서버 → 클라이언트 채널. 도구가 이것을 부르면 답이 오지 않거나 조용히 사라진다 — 쓰려면 먼저 포털 계약(mcp-modernize)과 맞춘다.
SERVER_TO_CLIENT = {"elicit", "create_message", "list_roots", "send_request", "send_ping",
                    "send_tool_list_changed", "send_resource_list_changed", "send_prompt_list_changed"}


MCP_SIF = PLATFORM / "infra" / "apptainer" / "mcp.sif"
CONSTRAINTS = PLATFORM / "infra" / "apptainer" / "mcp.constraints.txt"


def _assert_stateless(got: dict) -> None:
    assert got["stateless_http"] is True and got["json_response"] is False, got
    assert got["initialize"]["status"] == 200 and got["initialize"]["session_id"] is None, got["initialize"]
    call = got["call_without_initialize"]
    assert call["status"] == 200 and call["error"] is None and call["ctype"] == "text/event-stream", call
    assert got["forwarded"] == {"authorization": "Bearer probe-token", "x-heax-user-affiliation": "probe-aff",
                                "x-heax-aff-proof": None}, "stateless 호출에서 머리를 나르지 않았다 — 백엔드가 401 로 막는다"
    stale = got["stale_session_id"]
    assert stale["status"] == 200 and stale["error"] is None and stale["tools"] > 0, stale
    assert got["big_body"]["status"] == 200, f"본문 5 MiB 가 막혔다 — 큰 덱의 upload_kfile 이 끊긴다: {got['big_body']}"


@needs_mcp
def test_the_server_holds_no_session():
    """세션 번호를 내지 않고, initialize 없이 온 호출 · 재기동 전의 세션 번호를 단 호출을 받으며, 그 호출에도 들어온 머리를 백엔드로 나른다.

    예전(세션을 쥘 때)은 셋째 · 넷째가 400 「Missing session ID」 · 404 「Session not found」 였다 — MCP 를 다시 띄우면 게이트웨이가 쥔 세션이
    모두 끊겼다. 응답은 SSE 그대로라(json_response 아님) 같은 요청의 진행 알림은 간다. 이 시험은 시험 venv(SDK 1.x)로 잰다."""
    _assert_stateless(_probe("stateless"))


APPTAINER = shutil.which("apptainer")
needs_sif = pytest.mark.skipif(not (MCP_SIF.exists() and APPTAINER), reason="mcp.sif 또는 apptainer 없음")


def _sif_probe(mode: str) -> dict:
    got = subprocess.run([APPTAINER, "exec", "--env", "PYTHONNOUSERSITE=1", str(MCP_SIF), "python3", "-I", str(PROBE), mode],
                         capture_output=True, text=True, timeout=180, env={"PATH": "/usr/bin:/bin"})
    assert got.returncode == 0, got.stderr[-2000:]
    return json.loads(got.stdout.strip().splitlines()[-1])


@needs_sif
def test_the_sif_runs_the_pinned_sdk_and_holds_no_session_too():
    """운영이 도는 mcp.sif 안에서 같은 탐침 — SIF 의 SDK 가 고정판(mcp.constraints.txt)의 주 판과 같고, 그 SDK 로도 stateless 다.

    시험 venv(1.x)만 재면 운영 판(2.x)을 안 잰 것이다. 고정판만 고치고 SIF 를 다시 굽지 않았으면 여기서 빨갛다."""
    out = _sif_probe("stateless")
    pinned = re.search(r"^mcp==(\d+)\.", CONSTRAINTS.read_text(encoding="utf-8"), re.M).group(1)
    assert out["sdk2"] is (pinned == "2"), f"SIF 의 SDK 가 고정판 mcp {pinned}.x 와 다르다 — mcp.sif 를 다시 구워라"
    _assert_stateless(out)


def test_no_tool_uses_a_server_to_client_channel():
    """AST 로 — 글(주석 · 설명)에 낱말이 있는 것은 세지 않는다. 진행 알림(report_progress)은 같은 요청의 응답으로 가므로 막지 않는다."""
    used = sorted({(n.func.attr, n.lineno) for n in ast.walk(ast.parse(SERVER.read_text(encoding="utf-8")))
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in SERVER_TO_CLIENT})
    assert not used, f"stateless 에서 버려지는 채널을 부른다: {used}"


@needs_sif
def test_tool_errors_reach_the_model_under_the_sif_sdk():
    """공통 계약 P3 — 2.x 는 ToolError 가 아닌 예외의 글을 가리고 「Error executing tool <이름>」 만 보낸다. 도구 몸통 밖에서 ToolError 로
    바꾸므로(_bounded_tool) 손잡이 이름 · job_id 가 든 글이 그대로 온다. 1.x 시험 venv 는 어느 예외든 글을 보이므로 이것은 SIF 에서만 잰다."""
    got = _sif_probe("limits")
    knob = got["knob"]
    for case in ("find_slow", "compare_six", "figure_never"):
        assert not got[case]["ok"] and knob in (got[case]["error"] or ""), (case, got[case])
    assert "job_id=j1" in got["figure_never"]["error"], "몸통 안에서 바꿔 버리면 그림 기다림이 _Late 를 못 잡아 job_id 를 못 붙인다"


# ── 공통 계약 C1 ~ C8 전수(포털 mcp-modernize contract.md · 사용자 결정 11-27 「남기지 말고 최대한 많이」) ───────────────────────
# 도구 120 전부 — 표지 · 인자 설명 · 설명의 꼴 · 결과 꼴 · 닫힌 어휘와 숫자 경계가 백엔드와 같은지. 이름 · 동작은 그대로(조건).

HISTORY_WORDS = re.compile(r"(사용자 결정|요청서|검토 반영|재검토|실측|\bDF-\d+|\bKR-\d+|§\s?\d|\b20\d\d-\d\d-\d\d\b|heaxkooremapper)")
# 결과 꼴을 달지 않는 도구와 까닭 — 새 도구는 꼴을 달거나 여기에 까닭과 함께 올린다
NO_SHAPE = {
    "mesh_section_figure": "dict + 그림(Image) 섞인 목록",
    "mesh_surface_figure": "dict + 그림(Image) 섞인 목록",
    "mesh_stack_diagram": "dict + 그림(Image) 섞인 목록",
    "campaign_sphere_map": "dict + 그림(Image) 섞인 목록",
    "campaign_site_map": "dict + 그림(Image) 섞인 목록",
    "report_image": "글 + 그림(Image)",
    "report_compare": "글 + 그림(Image)",
    "download_result": "파일 내용(5 MB 까지) — 구조 결과로 두 번 실으면 응답이 두 배",
}
_WRITE_VERBS = {"post", "put", "patch", "delete"}
# 백엔드에 쓰지 않는데 읽기가 아닌 도구 — 이 박스의 파일을 쓴다
LOCAL_WRITES = {"save_result_to_path"}


@pytest.fixture(scope="module")
def tools() -> dict:
    return _probe("contract")


def _funcs() -> dict:
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    return {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _tool_defs() -> dict:
    return {k: n for k, n in _funcs().items() if isinstance(n, ast.AsyncFunctionDef)
            and any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "tool" for d in n.decorator_list)}


def _verbs(fn: ast.AST, funcs: dict, seen: frozenset = frozenset()) -> set:
    """도구가 백엔드에 보내는 HTTP 동사 — `_get` · `_post` · `_put` · `_delete` · `c.<동사>(…)`, 부르는 모듈 함수(그림 잡 등)까지 따라간다."""
    out = set()
    for c in ast.walk(fn):
        if isinstance(c, ast.Call):
            f = c.func
            if isinstance(f, ast.Name) and f.id in ("_get", "_post", "_put", "_delete"):
                out.add(f.id[1:])
            elif isinstance(f, ast.Name) and f.id in funcs and f.id not in seen:
                out |= _verbs(funcs[f.id], funcs, seen | {f.id})
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "c" \
                    and f.attr in ("get", "post", "put", "patch", "delete"):
                out.add(f.attr)
    return out


@needs_mcp
def test_every_tool_says_whether_it_reads_or_writes(tools):
    """C6 — 모든 도구에 readOnlyHint · openWorldHint, 바꾸는 도구는 destructiveHint · idempotentHint 까지."""
    for name, t in tools.items():
        a = t["annotations"] or {}
        assert "readOnlyHint" in a and "openWorldHint" in a, (name, a)
        if not a["readOnlyHint"]:
            assert "destructiveHint" in a and "idempotentHint" in a, (name, a)


@needs_mcp
def test_the_read_write_marks_match_what_the_tool_sends(tools):
    """C6 를 몸통과 대조 — 읽기 표지 도구는 GET 만 보내고, 쓰기 표지 도구는 POST · PUT · PATCH · DELETE 를 하나 이상 보낸다."""
    defs, funcs = _tool_defs(), _funcs()
    assert set(defs) == set(tools)
    for name, fn in defs.items():
        verbs, ro = _verbs(fn, funcs, frozenset({name})), tools[name]["annotations"]["readOnlyHint"]
        if ro:
            assert not verbs & _WRITE_VERBS, f"{name} 은 읽기 표지인데 {sorted(verbs)} 를 보낸다"
        elif name not in LOCAL_WRITES:
            assert verbs & _WRITE_VERBS, f"{name} 은 쓰기 표지인데 백엔드에 쓰지 않는다({sorted(verbs)})"


@needs_mcp
def test_every_argument_of_every_tool_is_described(tools):
    """C2 — 인자 설명 100%(게이트웨이가 세는 inputSchema 맨 위 인자의 description)."""
    bare = [(n, k) for n, t in tools.items() for k, v in (t["input"].get("properties") or {}).items() if not v.get("description")]
    assert not bare, bare


@needs_mcp
def test_descriptions_keep_the_contract_form(tools):
    """C1 — 1,500자 이하 · 첫 줄이 한 문장 · 결정 번호 · 날짜 · 실측 일화 · 요청 번호 · 게이트웨이 접두 이름이 없다(이력은 TOOLS.md 로)."""
    for name, t in tools.items():
        d = t["description"]
        assert 0 < len(d) <= 1500, (name, len(d))
        assert d.strip().splitlines()[0].strip(), name
        m = HISTORY_WORDS.search(d)
        assert not m, f"{name} 설명에 이력 낱말 {m.group(0)!r}"


@needs_mcp
def test_argument_and_result_field_texts_carry_no_history(tools):
    """C1 · C2 — 인자 설명 · 결과 칸 뜻에도 결정 번호 · 실측 일화 · 요청 번호가 없다(날짜는 꼴 예시로 쓰므로 여기서는 세지 않는다)."""
    words = re.compile(HISTORY_WORDS.pattern.replace(r"|\b20\d\d-\d\d-\d\d\b", ""))
    hits = []
    for name, t in tools.items():
        o = t["output"] or {}
        fields = [(f"{name}.{k}", v) for k, v in (t["input"].get("properties") or {}).items()]
        fields += [(f"{name}->{k}", v) for sect in [o.get("properties") or {}, *[d.get("properties") or {} for d in (o.get("$defs") or {}).values()]]
                   for k, v in sect.items()]
        hits += [(where, m.group(0)) for where, v in fields if (m := words.search(v.get("description") or ""))]
    assert not hits, hits


@needs_mcp
def test_structured_results_have_real_fields(tools):
    """C7 — 꼴이 없는 도구는 NO_SHAPE(까닭)뿐이고, 꼴은 칸 이름이 있다(껍데기 object 아님)."""
    bare = sorted(n for n, t in tools.items() if not t["output"])
    assert bare == sorted(NO_SHAPE), f"꼴 없는 도구가 목록과 다르다: {sorted(set(bare) ^ set(NO_SHAPE))}"
    for name, t in tools.items():
        o = t["output"]
        if not o:
            continue
        props = o.get("properties") or {}
        if set(props) == {"result"}:                   # 목록 — {"result": [행]} 의 행 꼴에 칸이 있어야 한다
            ref = (props["result"].get("items") or {}).get("$ref", "")
            props = (o.get("$defs") or {}).get(ref.rsplit("/", 1)[-1], {}).get("properties") or {}
        assert props and all(v.get("description") for v in props.values()), name


def _mx(info, key):
    return next(getattr(m, key) for m in info.metadata if getattr(m, key, None) is not None)


def _gq(path: str, name: str):
    """GET 경로의 쿼리 인자 field_info — 경로 꼴 그대로(`{report_id}` 등)."""
    return _query(path, name)


def test_closed_vocabularies_and_bounds_are_the_backend_constraints():
    """C3 · C4 — MCP 의 Literal · ge/le 상수가 백엔드가 실제로 받는 집합 · 경계와 같다(받는 집합은 그대로, 거절 자리만 MCP 로 옮긴다)."""
    import inspect
    from typing import get_args
    c = _server_constants()
    # 메시 그림 — 카탈로그 enum · 바이너리 검사
    from app.runner.catalog import get_operation
    sec = {p["name"]: p for p in get_operation("section")["params"]}
    assert set(c["MESH_SECTION_AXES"]) == set(sec["axis"]["enum"]) and set(c["MESH_SECTION_MODES"]) == set(sec["mode"]["enum"])
    src = PLATFORM.parent / "src" / "commands"
    stack = (src / "stackdiagram.cpp").read_text(encoding="utf-8")
    assert all(f'val == "{a}"' in stack for a in c["MESH_STACK_AXES"]) and "axis: 는 x, y, z 중 하나" in stack
    for cpp in ("section.cpp", "surfview.cpp", "stackdiagram.cpp"):
        assert f"c.width < {c['MESH_FIG_MIN_WIDTH_PX']} || c.height < {c['MESH_FIG_MIN_HEIGHT_PX']}" in \
            (src / cpp).read_text(encoding="utf-8"), cpp
    # 코퍼스
    from app.modules.corpus import routes as corpus
    for fn in (corpus.material_usage, corpus.section_contact_usage):
        info = inspect.signature(fn).parameters["limit"].default
        assert (_mx(info, "ge"), _mx(info, "le")) == (1, c["CORPUS_LIMIT_MAX"]), fn.__name__
    # 캠페인 분석
    from app.modules.campaigns import analysis_routes as AR, angles as G
    P = "/api/v1/campaigns/{campaign_id}"
    assert set(c["ANGLE_METRICS"]) | set(c["METRIC_ALIASES"]) == set(G.METRICS) | set(G.METRIC_ALIASES)
    for path in ("/angle-table", "/angle-stats", "/sphere-map"):
        assert c["THICKNESS_AXES"] == get_args(get_args(_gq(P + path, "thickness_axis").annotation)[0]), path
    assert c["MARGIN_AXES"] == get_args(get_args(_gq(P + "/part-margin", "metric_axis").annotation)[0])
    assert c["ANALYSIS_MATCH_MODES"] == get_args(_gq("/api/v1/campaigns/compare", "match").annotation)
    assert _mx(_gq(P + "/angle-table", "offset"), "ge") == 0 and _mx(_gq(P + "/peaks", "offset"), "ge") == 0
    assert _mx(_gq(P + "/angle-stats", "top"), "le") == c["ANALYSIS_TOP_MAX"]
    for path, name in ((P + "/angle-table", "config_generation"), (P + "/sphere-map", "group"), (P + "/hotspot-sites", "criterion")):
        assert _mx(_gq(path, name), "max_length") == c["ANALYSIS_KEY_MAX"], (path, name)
    assert _mx(_gq("/api/v1/campaigns/compare", "a"), "max_length") == c["ANALYSIS_ID_MAX"]
    tol = _gq("/api/v1/campaigns/compare", "tol_deg")
    assert (_mx(tol, "gt"), _mx(tol, "le")) == (0, 90)
    assert _mx(_gq(P + "/hotspot-sites", "part_id"), "gt") == 0
    assert _mx(_gq(P + "/hotspot-sites", "radius_mm"), "le") == c["ANALYSIS_RADIUS_MAX_MM"]
    for model, field, key in ((AR.GroupsBody, "groups", "ANALYSIS_GROUPS_MAX"), (AR.CriteriaBody, "criteria", "ANALYSIS_CRITERIA_MAX"),
                              (AR.SitesBody, "sites", "ANALYSIS_SITES_MAX"), (AR.PartMapBody, "rows", "ANALYSIS_PART_MAP_ROWS_MAX"),
                              (AR.PairRuleBody, "metrics", "ANALYSIS_PAIR_METRICS_MAX")):
        assert _mx(model.model_fields[field], "max_length") == c[key], key
    rc = AR.PairRuleBody.model_fields["rank_corr_min"]
    assert (_mx(rc, "ge"), _mx(rc, "le")) == (-1, 1) and _mx(AR.PairRuleBody.model_fields["max_failed_pairs"], "ge") == 0
    from app.modules.sessions.schemas import PartRename
    assert _mx(PartRename.model_fields["title"], "max_length") == c["RENAME_PART_TITLE_MAX"]
    assert _mx(PartRename.model_fields["file_id"], "gt") == 0
    # 리포트 · 해석 온톨로지
    assert _mx(_gq("/api/v1/cae/parts", "max_safety_factor"), "ge") == 0
    eng = _gq("/api/v1/cae/load-paths", "min_engage_ratio")
    assert (_mx(eng, "ge"), _mx(eng, "le")) == (0, 1)
    cp = "/api/v1/reports/{report_id}/contact_profile"
    from app.reports.parser import ANALYTICS_BLOCKS, CONTACT_PROFILE_METRICS, _HOTSPOT_ORDERS, _SCATTER_METRICS, _SPHERE_HOTSPOT_ORDERS
    assert c["CONTACT_METRICS"] == _pattern_values(_gq(cp, "metric")) == tuple(CONTACT_PROFILE_METRICS)
    assert _mx(_gq(cp, "top"), "le") == c["CONTACT_TOP_MAX"] and _mx(_gq(cp, "axis_top"), "le") == c["CONTACT_AXIS_TOP_MAX"]
    assert _mx(_gq("/api/v1/reports/{report_id}/hotspots", "top"), "le") == c["HOTSPOT_TOP_MAX"]
    mb = _gq("/api/v1/reports/{report_id}/blocks/{name}", "max_bytes")
    assert (_mx(mb, "ge"), _mx(mb, "le")) == (c["BLOCK_MAX_BYTES_MIN"], c["BLOCK_MAX_BYTES_MAX"])
    assert c["HOTSPOT_ORDERS_DEEP"] == tuple(_HOTSPOT_ORDERS) and c["HOTSPOT_ORDERS_SPHERE"] == tuple(_SPHERE_HOTSPOT_ORDERS)
    assert c["REPORT_ANALYTICS_BLOCKS"] == tuple(ANALYTICS_BLOCKS) and c["REPORT_SCATTER_METRICS"] == tuple(_SCATTER_METRICS)
    from app.modules.reports import services as RS
    assert c["WORST_CASE_METRICS"] == tuple(RS._SORT_COLS)
    assert _mx(_gq("/api/v1/reports/{report_id}/cases", "limit"), "le") == c["REPORT_CASES_LIMIT_MAX"]
    assert _mx(_gq("/api/v1/reports", "limit"), "ge") == 1
    Q, A = "/api/v1/reports/{report_id}/query", "/api/v1/reports/{report_id}/angle-stats"
    assert c["REPORT_QUERY_METRICS"] == tuple(RS._QUERY_METRICS)
    assert c["SORT_ORDERS"] == _pattern_values(_gq(Q, "sort"))
    assert _mx(_gq(Q, "limit"), "le") == c["REPORT_QUERY_LIMIT_MAX"]
    for path, name in ((Q, "angle_tol_deg"), (A, "tol_deg")):
        assert (_mx(_gq(path, name), "ge"), _mx(_gq(path, name), "le")) == (0, c["REPORT_ANGLE_TOL_MAX_DEG"]), (path, name)
    assert _mx(_gq(A, "top_parts"), "le") == c["REPORT_TOP_PARTS_MAX"]
    from app.reports.datahub import _STAGE_RE
    codes = {s for s in (p + r for p in ("pre", "dv", "pv", "pra", "mp") for r in ("", "1", "2", "3", "r"))
             if (m := _STAGE_RE.fullmatch(s)) and (m.group(1) in ("dv", "pv")) == bool(m.group(2))}
    assert set(c["REVISION_CODES"]) == codes and set(c["DATAHUB_STAGES"]) == codes | {""}
    # 리포트 적재 · 캠페인 묶음 · 보고서 묶음
    from app.modules.reports import routes as RR0
    assert set(c["REPORT_KINDS"]) == set(RR0._KINDS)
    from app.reports.datahub import DataHubError, parse_stage

    def _stage_ok(v):
        try:
            parse_stage(v)
            return True
        except DataHubError:
            return False
    assert set(c["DEV_REV_CODES"]) == {p + r for p in ("pre", "dv", "pv", "pra", "mp") for r in ("", "1", "2", "3", "r") if _stage_ok(p + r)}
    from app.modules.campaigns import extraction as CX, routes as CR, services as CS
    assert set(c["CAMPAIGN_THICKNESS_INPUTS"]) == set(get_args(get_args(CR.CampaignBody.model_fields["thickness_axis"].annotation)[0]))
    assert tuple(c["CAMPAIGN_STATES"]) == tuple(CS.STATES) and tuple(c["CLEARANCE_STATUSES"]) == tuple(CX.STATUSES)
    for tail in ("ingest-status", "provenance", "health", "deletion-clearance"):
        lim = _gq(f"/api/v1/campaigns/{{campaign_id}}/{tail}", "limit")
        assert (_mx(lim, "ge"), _mx(lim, "le")) == (1, c["ANALYSIS_ROWS_MAX"]), tail
        assert _mx(_gq(f"/api/v1/campaigns/{{campaign_id}}/{tail}", "offset"), "ge") == 0, tail
    runs = CR.RunsBody.model_fields["runs"]
    assert (_mx(runs, "min_length"), _mx(runs, "max_length")) == (1, c["CAMPAIGN_RUNS_MAX"])
    assert _mx(CR.CampaignBody.model_fields["drop_height_mm"], "ge") == 0 and _mx(CR.CampaignBody.model_fields["duration_ms"], "ge") == 0
    assert c["REQUIRED_EXTRACTIONS_MAX"] == CR._REQUIRED_MAX
    assert _mx(CR.CampaignBody.model_fields["required_extractions"], "max_length") == CR._REQUIRED_MAX
    th = CR.ThresholdsBody.model_fields
    assert (_mx(th["energy_ratio_max"], "gt"), _mx(th["hg_over_ie_max"], "gt"), _mx(th["added_mass_pct_max"], "ge"),
            _mx(th["ke0_rel_tol"], "ge")) == (0, 0, 0, 0)
    assert c["BUNDLE_CAMPAIGNS_MAX"] == CR._BUNDLE_CAMPAIGNS_MAX == _mx(CR.BundleBody.model_fields["campaign_ids"], "max_length")
    assert _mx(_gq("/api/v1/bundles/{bundle_id}", "version"), "ge") == 1
    assert _mx(_gq("/api/v1/bundles/{bundle_id}", "limit"), "le") == c["BUNDLE_ITEMS_PAGE_MAX"]
    assert _mx(_gq("/api/v1/bundles/{bundle_id}/diff", "from"), "ge") == 1 and _mx(_gq("/api/v1/bundles/{bundle_id}/diff", "to"), "ge") == 1
    # 과제 · 온톨로지 · 레시피
    from app.modules.ontology import routes as OR
    assert c["ONTO_STATES"] == tuple(OR._STATES)
    assert _mx(_gq("/api/v1/ontology/tasks", "limit"), "le") == c["TASK_LIMIT_MAX"]
    assert _mx(_gq("/api/v1/ontology/objects", "limit"), "le") == c["ONTO_FIND_LIMIT_MAX"]
    assert _mx(_gq("/api/v1/ontology/objects", "offset"), "ge") == 0
    assert _mx(_gq("/api/v1/ontology/task-links", "limit"), "le") == c["TASK_LINKS_LIMIT_MAX"]
    assert _mx(_gq("/api/v1/recipes", "limit"), "le") == c["RECIPE_SEARCH_LIMIT_MAX"]
    from app.modules.recipes import routes as RR, services as RSV
    rf = RR.RunBody.model_fields["report_ids"]
    assert (_mx(rf, "min_length"), _mx(rf, "max_length")) == (1, c["RECIPE_RUN_REPORTS_MAX"])
    assert c["RECIPE_NOTE_MIN"] == RSV._MIN_NOTE
