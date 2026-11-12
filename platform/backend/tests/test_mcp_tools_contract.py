# MCP 도구 인자 설명(포털 arg-descriptions §2-3)과 MCP → REST 시간 한도(포털 time-limits 1-1)를 지키는 시험 — 사용자 결정 10-31
"""MCP 서버는 별도 venv 라 백엔드 venv 에서 import 하지 못한다. 그래서 `tests/mcp_probe.py` 를 그쪽 python 으로 돌려 FastMCP 목록
(`mcp.list_tools()`)과 느린 가짜 백엔드에서의 동작을 JSON 으로 받는다. MCP venv 가 없는 박스에서는 건너뛴다.

① 설명 — 게이트웨이가 세는 것은 inputSchema 맨 위 인자의 `description` 이다(`title` 아님). 형 · 기본값 · 필수 · 순서는 설명을 달기 전
   그대로여야 한다(`fixtures/mcp_arg_contract.json`). 허용값 · 상한 · 단위는 MCP 쪽 상수에서 만들고, 그 상수가 백엔드의 실제 제약과
   같은지를 여기서 대조한다 — 같은 이름의 인자라도 도구마다 뜻이 다르면 문구가 달라야 한다(severity).
② 한도 — 손잡이 기본값이 게이트웨이 600초보다 작고, 늦는 백엔드 · 여러 번 부르는 도구 · 안 끝나는 그림 잡이 호출 하나의 기한 안에
   손잡이 이름이 든 문구로 끝난다.
"""
from __future__ import annotations

import ast
import json
import re
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
    assert n == 36 and not missing, (n, missing)


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
                if p.name == name:
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
