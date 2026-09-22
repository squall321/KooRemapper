"""**"고려 가능한 옵션이 다 들어갔나" 를 말이 아니라 검사로 만든다.**

서버의 옵션 카탈로그는 기계가 읽는 스키마가 아니라 **손으로 쓴 산문**이다
(KooSlurm `mcp_slurm/server.py` 의 `_DROP_OPTIONS_DOC`). 그래서 우리 쪽 폼과 매핑 표가
그것과 어긋나도 아무도 모른다 — 도구는 모르는 키를 그냥 병합해 두고 지나가므로, 화면에서
고른 값이 **해석에 아무 영향을 안 주는데 잡은 성공한다.**

여기서 하는 일은 셋이다.
  ① 그 산문의 스냅샷을 리포에 둔다(`tests/data/stcx_scenario_catalog.txt`).
  ② 거기 이름 붙은 옵션이 **하나도 빠짐없이** 어딘가에 속하는지 본다 —
     낱낱 칸이거나, 도구 인자이거나, "칸으로 안 낸다" 고 **이유와 함께** 적힌 것이거나.
  ③ 서버가 살아 있으면 스냅샷이 아직 최신인지도 본다(안 살아 있으면 건너뛴다).

②의 `NOT_A_FIELD` 가 핵심이다. 빠뜨린 것과 일부러 뺀 것을 **가른다** — 이유를 적지 않으면
시험이 실패하므로, 다음 사람이 "이게 왜 없지" 를 다시 조사하지 않는다.
"""
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

import pytest

from app.runner import catalog
from app.runner.stcx_client import _DR_TOGGLE, _SCENARIO_MAP, TOOL_ARGS

SNAPSHOT = Path(__file__).parent / "data" / "stcx_scenario_catalog.txt"
OP = "stcx_fullangle_drop"

# 칸으로 내지 않는 것 — **이유를 적는다.** 이유 없이 빼면 빠뜨린 것과 구분되지 않는다.
NOT_A_FIELD: dict[str, str] = {
    "project_name": "잡 이름으로 서버가 자동 치환한다(직접 설정 불필요).",
    "template": '"%INPUTFILE%" 고정 — 업로드한 모델 파일명으로 자동 치환된다.',
    "file_path": "각도 파일 경로는 `case_txt` 를 고르면 서버가 자동 설정한다.",
    "lsdyna_memory": "`memory` **도구 인자**로 간다(scenario 덮어쓰기가 아니다).",
    "enabled": "`dynamic_relaxation` 토글이 이 값을 켠다(세부를 주면 객체로 승격된다).",
    "chain_nodes": "드라이버 잡 자원 — **템플릿 env 고정이라 scenario 로 못 바꾼다.**",
    "chain_jobs_per_node": "드라이버 잡 자원 — 템플릿 env 고정.",
    "chain_ncpu": "드라이버 잡 자원 — 템플릿 env 고정.",
    "chain_postprocess": "드라이버 잡 자원 — 템플릿 env 고정.",
}

# 카탈로그 산문에 식별자처럼 보이지만 **옵션이 아닌 것** — 구역 제목·열거값·타입·단위·도구 이름.
# 여기에 없는 새 식별자는 옵션으로 간주된다 — 그래야 서버에 옵션이 늘면 시험이 먼저 안다.
_NOT_OPTIONS = {
    # 구역·컨테이너
    "simulation_params", "environment", "angle_source", "cumulative", "angle_mixing",
    "scenarios", "drop_surface", "scenario", "scenario_overrides",
    # 열거값
    "Plane", "PlaneGraded", "PlanewithRoughness", "RigidWall", "Random",
    "DROP", "IMPACT", "STAT", "THERM", "VIB",
    "same_angle", "cyclic", "random", "opposite", "custom_mapping",
    "cuboid_geometry", "fibonacci_lattice", "pitching_sweep", "rolling_sweep", "case_txt_file",
    "fullangle_drop", "fullangle", "fibonacci",
    # 도구 이름·도구 인자
    "smarttwin_submit", "smarttwin_scenario_options", "smarttwin",
    "slurm_job_results", "slurm_job_log",
    "model_path", "case_txt_path", "angle_preset", "job_name", "time_limit",
    "sim_type", "dry_run", "memory",
    # 타입·단위·산문 조각
    "bool", "dict", "float", "int", "list", "string", "True", "False", "true", "false",
    "MPa", "tonne", "D2R", "DOE", "DYNA", "IGA", "INCLUDE", "INPUTFILE", "LSTC_",
    "json", "txt", "sif", "env", "data", "base", "index", "offset", "direction",
    "face", "packing", "step", "drop",
}


def _catalog_option_names(text: str) -> set[str]:
    """**넓게 잡고 소음만 걸러낸다.** 반대로 하면(좁게 잡기) 새 옵션이 조용히 새어 나간다 —
    실제로 처음에는 `tFinal`·`size`·`mesh`·`type` 을 못 잡은 채로 통과했다."""
    toks = set(re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", text))
    return {t for t in toks - _NOT_OPTIONS if not t.isdigit()}


def _covered() -> set[str]:
    """우리가 실제로 닿는 이름 — scenario 키 + 칸 이름 + 도구 인자."""
    params = {p["name"] for p in catalog.get_operation(OP)["params"]}
    scen_keys = {scen_key for _, scen_key in _SCENARIO_MAP.values()}
    return params | scen_keys | set(TOOL_ARGS) | {_DR_TOGGLE}


def test_the_snapshot_is_actually_readable():
    """스냅샷이 비거나 정규식이 깨지면 아래 시험이 **아무것도 안 보고 통과**한다."""
    text = SNAPSHOT.read_text(encoding="utf-8")
    assert "옵션 카탈로그" in text, "스냅샷이 그 카탈로그가 아니다"
    names = _catalog_option_names(text)
    assert len(names) >= 55, f"이름을 {len(names)}개만 뽑았다 — 추출이 깨졌다"
    for must in ("tFinal", "size", "mesh", "type", "strategy", "lsdyna_memory"):
        assert must in names, f"{must} 를 못 뽑았다 — 좁게 잡으면 새 옵션이 조용히 샌다"


def test_every_option_the_server_names_is_accounted_for():
    """빠진 것과 일부러 뺀 것을 **가른다**. 이유 없이 빠진 것이 있으면 실패한다."""
    names = _catalog_option_names(SNAPSHOT.read_text(encoding="utf-8"))
    covered, lowered = _covered(), {k.lower() for k in NOT_A_FIELD}
    missing = sorted(n for n in names
                     if n not in covered and n.lower() not in lowered)
    assert not missing, (
        "서버 카탈로그에 있는데 우리 쪽에 **칸도 이유도 없는** 옵션이다.\n"
        "칸으로 내거나, 못 내는 이유를 NOT_A_FIELD 에 적어라:\n  " + ", ".join(missing))


def test_no_stale_exemptions():
    """카탈로그에서 사라진 이름이 면제 목록에 남아 있으면, 그 줄은 아무것도 안 지킨다."""
    names = _catalog_option_names(SNAPSHOT.read_text(encoding="utf-8"))
    lowered = {n.lower() for n in names}
    stale = sorted(n for n in NOT_A_FIELD if n.lower() not in lowered)
    assert not stale, f"카탈로그에 없는 면제가 남아 있다(지워라): {stale}"


def test_every_exemption_has_a_reason():
    empty = [k for k, v in NOT_A_FIELD.items() if not (v or "").strip()]
    assert not empty, f"이유 없는 면제: {empty}"


def test_every_mapped_arg_is_a_real_form_field():
    """매핑 표에만 있고 칸이 없으면, 그 옵션은 폼에서 영영 못 고른다."""
    params = {p["name"] for p in catalog.get_operation(OP)["params"]}
    orphan = sorted(k for k in _SCENARIO_MAP if k not in params)
    assert not orphan, f"매핑은 있는데 폼에 칸이 없다: {orphan}"


def test_every_form_field_goes_somewhere():
    """반대쪽 — 칸은 있는데 어디로도 안 가면, 고른 값이 **조용히 버려진다.**"""
    params = {p["name"] for p in catalog.get_operation(OP)["params"]}
    lost = sorted(p for p in params
                  if p not in _SCENARIO_MAP and p not in TOOL_ARGS and p != _DR_TOGGLE)
    assert not lost, f"폼 칸이 어디로도 안 간다(고른 값이 버려진다): {lost}"


def test_every_field_is_grouped():
    """67칸을 한 줄로 늘어놓으면 아무도 못 쓴다 — 화면이 묶을 수 있게 group 을 단다."""
    bad = [p["name"] for p in catalog.get_operation(OP)["params"] if not p.get("group")]
    assert not bad, f"group 이 없는 칸: {bad}"


@pytest.mark.skipif(not __import__("os").environ.get("STCX_LIVE_CHECK"),
                    reason="실서버 대조는 STCX_LIVE_CHECK=1 일 때만 (게이트웨이·PAT 필요)")
def test_the_snapshot_still_matches_the_live_catalog():
    """서버 문서가 바뀌면 스냅샷을 갱신하라고 여기서 알려 준다."""
    import anyio

    from app.config import settings
    from app.runner.stcx_client import StcxClient

    async def _go():
        c = StcxClient(settings.gateway_mcp, settings.gateway_pat)
        try:
            return await c.scenario_options("fullangle_drop")
        finally:
            await c.close()

    res = anyio.run(_go)
    if not res.get("ok"):
        pytest.skip(f"카탈로그를 못 가져왔다: {res.get('error')}")
    live = json.dumps(res["result"], ensure_ascii=False)
    for name in _catalog_option_names(SNAPSHOT.read_text(encoding="utf-8")):
        assert name in live.lower(), f"스냅샷에만 있고 실서버엔 없다: {name} — 스냅샷을 갱신하라"
