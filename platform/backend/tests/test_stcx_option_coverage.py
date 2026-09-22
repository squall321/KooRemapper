"""**"고려 가능한 옵션이 다 들어갔나" 를 말이 아니라 검사로 만든다.**

정본은 산문이 아니라 **파서**다. 처음엔 서버 MCP 도구가 내주는 옵션 카탈로그(산문)를
기준으로 삼았는데, 그것은 실제 옵션의 일부만 적은 문서였다 — `postprocess.*` 11개,
`tolerance.*`, `gravity`, `dtmin`, `drop_contact`, `control_timestep/hourglass`,
`explicit` 각도원, `only`/`angle_spacing`/`previous_stages` 가 통째로 빠져 있었다.

그래서 기준을 둘로 바꿨다(스냅샷 `data/stcx_scenario_keys.json`).
  ① `pyKooCAE/Runner/cli_help_kcr.py` 의 **키 표**(점 경로·타입·기본값을 직접 적어 둔 것)
  ② `/data/scenario/*/scenario.json` **실제 프리셋 파일**의 잎 키

그리고 이 대조가 잡아낸 실제 결함이 있다. 각도 파라미터를 `angle_source` 바로 밑에
평평히 넣고 있었는데, 파서는 `angle_source["fibonacci_lattice"]["num_points"]` 로 **한
단계 더 들어가서** 읽는다(`Runner/CumulativeDesigner.py`). 방향 수를 아무리 바꿔도
프리셋 값 그대로 돌고, **잡은 성공한다.**

여기서 지키는 것 — 정본이 이름 붙인 키가 하나도 빠짐없이 (a) 폼 칸이거나 (b) 도구
인자이거나 (c) **이유와 함께** 못 내는 것으로 적혀 있는지. 그리고 칸↔매핑이 양방향으로
맞는지(한쪽만 있으면 못 고르거나 조용히 버려진다).
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from app.runner import catalog
from app.runner.stcx_client import _DEST_PATHS, _DR_TOGGLE, _SCENARIO_MAP, TOOL_ARGS

SNAP = json.loads((Path(__file__).parent / "data" / "stcx_scenario_keys.json").read_text("utf-8"))
OP = "stcx_fullangle_drop"

# 칸으로 내지 않는 것 — **이유를 적는다.** 이유 없이 빼면 빠뜨린 것과 구분되지 않는다.
NOT_A_FIELD: dict[str, str] = {
    "project_name": "잡 이름으로 서버가 자동 치환한다.",
    "template": '"%INPUTFILE%" 고정 — 업로드한 모델 파일명으로 자동 치환된다.',
    "base_dir": "작업 루트는 서버가 정한다(잡 디렉터리).",
    "angle_source.case_txt_file.file_path": "`case_txt` 를 고르면 서버가 자동 설정한다.",
    "angle_source.fibonacci_lattice.num_directions": "`num_directions` 칸이 쓰는 정식 키는 num_points 다(파서가 둘 다 받는다).",
    "environment.time_limit": "`time_limit` **도구 인자**로 간다.",
    "environment.memory": "`memory` 도구 인자로 간다.",
    "environment.lsdyna_memory": "`memory` 도구 인자로 간다.",
    "environment.partition": "파티션은 서버가 관리한다(카탈로그: 경로·sif·라이선스 키는 건드리지 말 것).",
    "environment.solver_command": "서버 관리 — 솔버 실행 명령.",
    "environment.sif_path": "서버 관리 — SIF 경로.",
    "environment.koochainrun_path": "서버 관리 — 도구 경로.",
    "environment.koomeshmodifier_path": "서버 관리 — 도구 경로.",
    "environment.lsdyna_path": "서버 관리 — 솔버 경로.",
    "environment.mpi_path": "서버 관리 — MPI 경로.",
    "environment.mpi_launcher": "서버 관리 — MPI 실행기.",
    "environment.apptainer_sif": "서버 관리 — 컨테이너 이미지.",
    "environment.apptainer_bind": "서버 관리 — 컨테이너 바인드.",
    "environment.apptainer_env": "서버 관리 — 컨테이너 환경변수.",
    "environment.apptainer_tmpdir": "서버 관리 — 컨테이너 임시 폴더.",
    "environment.lsdyna_apptainer_sif": "서버 관리 — 솔버 컨테이너 이미지.",
    "environment.lsdyna_apptainer_bind": "서버 관리 — 솔버 컨테이너 바인드.",
    "environment.lsdyna_apptainer_env.LSTC_LICENSE_SERVER": "서버 관리 — 라이선스 서버(카탈로그가 명시적으로 건드리지 말라고 한다).",
    "environment.lsdyna_apptainer_env.LSTC_FILE": "서버 관리 — 라이선스 파일.",
    "environment.lsdyna_apptainer_env.FI_PROVIDER": "서버 관리 — MPI 패브릭.",
    "environment.lsdyna_apptainer_env.I_MPI_FABRICS": "서버 관리 — MPI 패브릭.",
    "environment.lsdyna_apptainer_env.LD_LIBRARY_PATH": "서버 관리 — 라이브러리 경로.",
    "tolerance.yaw": "`tolerance_yaw` 칸이 그 아래 `tolerance` 를 쓴다(yaw 자체는 자리다).",
    "CHAIN_NODES": "드라이버 잡 자원 — **템플릿 env 고정이라 scenario 로 못 바꾼다.**",
    "CHAIN_JOBS_PER_NODE": "드라이버 잡 자원 — 템플릿 env 고정.",
    "CHAIN_NCPU": "드라이버 잡 자원 — 템플릿 env 고정.",
    "CHAIN_POSTPROCESS": "드라이버 잡 자원 — 템플릿 env 고정.",
}


def _authoritative() -> set[str]:
    """정본이 이름 붙인 키 — 키 표 ∪ 실제 프리셋 잎(scenarios[] 접두사는 뗀다)."""
    keys = set(SNAP["k_table"])
    keys |= {k.replace("scenarios[].", "") for k in SNAP["preset_keys"]}
    # 컨테이너(자식이 있는 경로)는 옵션이 아니라 자리다
    return {k for k in keys if not any(o.startswith(k + ".") for o in keys)}


def _params() -> list[dict]:
    return catalog.get_operation(OP)["params"]


def _covered_paths() -> set[str]:
    """우리가 실제로 쓰는 **점 경로**. 매핑의 목적지+키를 그대로 조립한다."""
    out = set()
    for _arg, (kind, key) in _SCENARIO_MAP.items():
        # 정본은 시나리오 안의 키를 `angle_source.…` 처럼 짧게 적는다(스냅샷도 그렇게 맞춘다).
        path = [p for p in _DEST_PATHS[kind] if p not in ("0", "scenarios")]
        out.add(".".join([*path, key]))
    out.add("simulation_params." + _DR_TOGGLE)          # 토글
    for sub in ("nrcyck", "drtol", "drfctr", "drterm", "enabled"):
        out.add(f"simulation_params.{_DR_TOGGLE}.{sub}")
    return out


def test_the_snapshot_is_real():
    assert SNAP["k_table"] and SNAP["preset_keys"], "스냅샷이 비었다"
    assert len(_authoritative()) >= 90, f"정본 키가 {len(_authoritative())}개뿐 — 스냅샷이 깨졌다"
    for must in ("simulation_params.gravity", "postprocess.auto_sphere",
                 "angle_source.fibonacci_lattice.num_points", "tolerance.doe_count"):
        assert must in _authoritative(), f"{must} 가 정본에 없다 — 스냅샷이 옛것이다"


def test_every_authoritative_key_is_accounted_for():
    """빠진 것과 일부러 뺀 것을 **가른다**."""
    covered = _covered_paths()
    missing = sorted(k for k in _authoritative()
                     if k not in covered and k not in NOT_A_FIELD)
    assert not missing, (
        "정본에 있는데 우리 쪽에 **칸도 이유도 없는** 옵션이다.\n"
        "칸으로 내거나, 못 내는 이유를 NOT_A_FIELD 에 적어라:\n  " + "\n  ".join(missing))


def test_no_stale_exemptions():
    known = _authoritative() | {"CHAIN_NODES", "CHAIN_JOBS_PER_NODE", "CHAIN_NCPU",
                                "CHAIN_POSTPROCESS"}
    stale = sorted(k for k in NOT_A_FIELD if k not in known)
    assert not stale, f"정본에 없는 면제가 남아 있다(지워라): {stale}"


def test_every_exemption_has_a_reason():
    empty = [k for k, v in NOT_A_FIELD.items() if not (v or "").strip()]
    assert not empty, f"이유 없는 면제: {empty}"


def test_angle_params_are_nested_under_their_source_type():
    """**이 대조가 실제로 잡아낸 결함이다.** 평평하면 파서가 못 읽는다."""
    flat = sorted(p for p in _covered_paths()
                  if p.startswith("angle_source.") and p.count(".") == 1
                  and p != "angle_source.source_type")
    assert not flat, f"각도 파라미터가 source_type 아래로 안 들어갔다: {flat}"
    assert "angle_source.fibonacci_lattice.num_points" in _covered_paths()
    assert "angle_source.cuboid_geometry.include_faces" in _covered_paths()


def test_every_mapped_arg_is_a_real_form_field():
    names = {p["name"] for p in _params()}
    orphan = sorted(k for k in _SCENARIO_MAP if k not in names)
    assert not orphan, f"매핑은 있는데 폼에 칸이 없다(영영 못 고른다): {orphan}"


def test_every_form_field_goes_somewhere():
    names = {p["name"] for p in _params()}
    lost = sorted(n for n in names
                  if n not in _SCENARIO_MAP and n not in TOOL_ARGS and n != _DR_TOGGLE)
    assert not lost, f"폼 칸이 어디로도 안 간다(고른 값이 버려진다): {lost}"


def test_every_field_is_grouped_and_described():
    bad = [p["name"] for p in _params() if not p.get("group") or not p.get("description")]
    assert not bad, f"묶음이나 설명이 없는 칸: {bad}"


def test_every_destination_is_reachable():
    """표에 있는 목적지 기호가 전부 실제 자리로 풀리는지 — 오타면 KeyError 로 죽는다."""
    from app.runner.stcx_client import _dest
    for kind in _DEST_PATHS:
        assert isinstance(_dest({}, kind), dict)
