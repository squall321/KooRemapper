# stcx(356대 클러스터) 전각도 낙하를 **SmartTwinMCP(:5013)로** 제출·조회하는 래퍼 + 덱 반입
"""왜 게이트웨이를 거치나 — 직접 ssh 를 하려면 이 컨테이너에 ssh·키·클러스터 자격이
들어와야 하고, 시나리오 생성·파티션 오토튠을 통째로 중복 구현해야 한다. 그 순간
DynaForge 가 클러스터 자격증명을 쥔 앱이 된다. 게이트웨이 뒤에는 이미 그 일을 하는
도구가 있고, 제출이 대시보드를 거치므로 **웹 제출과 같은 인증·권한·이력**이 붙는다.

**파일을 나른다 — 2026-10-14 에 뒤집혔다.** 예전 전제는 "두 쪽이 같은 경로를 본다" 였는데
사실이 아니었다. cae00 `/data` 는 로컬 디스크이고 stcx `/data` 는 다른 NFS 다 — stcx 는 이
서버의 경로를 **못 연다.** 그래서 제출 전에 stcx 대시보드(:5010)의 청크 업로드로 덱을 올리고,
그것이 돌려준 **헤드노드 절대경로**를 `model_file_path` 로 넘긴다(`StcxUploader`).
머리말의 다른 금지는 그대로다 — 이 컨테이너에 ssh·키·클러스터 자격은 들이지 않는다
(반입은 인증 없는 HTTP 이고, 제출은 여전히 게이트웨이 PAT 하나뿐이다).

**도구 이름은 접두사 붙은 별칭을 쓴다.** 게이트웨이는 이름 충돌 여부와 무관하게
`<백엔드키에서 하이픈 뺀 것>_<도구이름>` 별칭을 **항상** 등록하고(`gateway.py:718-726`),
맨이름은 그 이름이 유일할 때만 노출한다. 맨이름으로 부르면 나중에 다른 백엔드에 같은
이름이 생기는 순간 조용히 사라진다.
⚠ 그 별칭은 **호출 전용**이라 `tools/list`·`/tools-map` 에는 **안 보인다** — 목록은 `route`
만 싣고 호출은 `route` 다음에 `alias_route` 를 본다(`gateway.py:3419`). 목록에서 못 찾았다고
없는 이름이 아니다.

어떤 실패도 예외로 올리지 않는다 — `{"ok": False, "error": …}` 로 돌려준다. 잡 하나가
실패하는 것과 워커가 죽는 것은 다르다.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import httpx

# 게이트웨이 호출 시한(GATEWAY_CALL_TIMEOUT 기본 120s) **아래**로 잡는다. 위로 잡으면
# 게이트웨이가 먼저 끊고, 우리는 그것을 전송 오류로 읽어 원인을 잘못 짚는다.
DEFAULT_TIMEOUT = 60.0
PROTOCOL_VERSION = "2025-06-18"

# 백엔드 키 `smart-twin-mcp` → 별칭 접두사 `smarttwinmcp`(하이픈 제거).
# 예전에는 `smart-twin-cluster`(:5012 mcp_slurm)를 불렀다 — 그쪽은 쓰지 않는다.
_PREFIX = "smarttwinmcp"
TOOL_SUBMIT = f"{_PREFIX}_fullangle_drop_simulation"
TOOL_STATUS = f"{_PREFIX}_job_status"
# ★상태만으로는 끝났는지 알 수 없다 — `job_status` 응답에 `slurm_job_ids` 가 없고,
#   `squeue` 는 예외가 나도 `{}` 라 "다 끝났다"·"아직 큐에 안 올랐다"·"squeue 가 실패했다" 가
#   같은 모양이다. 레지스트리 행 전체를 주는 이 도구로 id 목록을 함께 받는다.
TOOL_DETAILS = f"{_PREFIX}_get_job_details"


# ── 응답 해석 ──────────────────────────────────────────────────────────────
# SmartTwinMCP 는 **JSON 봉투**를 돌려준다(`runner.py:40-49`) —
#   {"tool": …, "ok": bool, "exit_code": int|None, "stdout": str, "stderr": str,
#    "result": <stdout 이 JSON 이면 그것, 아니면 null>, "transport": …, "command": …}
#
# ⚠ 그런데 **인자 검증 실패는 봉투가 아니다** — `{"ok": false, "error": …, "tool": …}` 로
#   온다(`server.py:223-225` 가 도구를 돌리기 **전에** 막는다). `exit_code`·`stdout` 이
#   아예 없다. 두 모양을 다 받아야 한다.
#
# 예전 :5012 는 사람이 읽는 **글**을 돌려주고 실패도 성공 모양이었다. 그 텍스트 파서는
# 지웠다 — 프로토콜이 통째로 바뀌었으므로 되살릴 자리가 없다.

# Slurm 상태. 여기 없는 값은 **모른다**로 둔다 — 임의로 성공·실패로 접지 않는다.
STATES_ACTIVE = frozenset({
    "PENDING", "RUNNING", "CONFIGURING", "COMPLETING", "REQUEUED", "REQUEUE_HOLD",
    "RESIZING", "SUSPENDED", "SIGNALING", "STAGE_OUT", "PREEMPTED",
})
STATES_OK = frozenset({"COMPLETED"})
STATES_BAD = frozenset({
    "FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL", "OUT_OF_MEMORY", "BOOT_FAIL",
    "DEADLINE", "REVOKED", "SPECIAL_EXIT",
})


def _envelope(result: Any) -> dict:
    """응답을 딕트로 본다. 딕트가 아니면 빈 딕트다(사유는 호출부가 붙인다)."""
    return dict(result) if isinstance(result, Mapping) else {}


def _why(env: Mapping[str, Any]) -> str:
    """실패 사유를 **요청서가 정한 순서**로 뽑는다 — result.reason → error → stderr 꼬리.

    순서가 중요하다. 스크립트가 쓴 `reason` 이 가장 구체적이고, `error` 는 인자 검증이
    막은 것이고, `stderr` 는 둘 다 없을 때의 마지막 단서다.
    """
    inner = env.get("result")
    if isinstance(inner, Mapping) and inner.get("reason"):
        return str(inner["reason"])[:500]
    if env.get("error"):
        return str(env["error"])[:500]
    tail = str(env.get("stderr") or "").strip()
    if tail:
        return tail[-500:]
    return ""


def parse_submit(result: Any) -> dict:
    """제출 응답 → {"ok": True, "registry_id": N, "job_id": …, …} 또는 실패.

    **성공의 조건은 셋 다다** — 봉투의 `ok` · `result.ok` · `registry_id` 가 있다.
    하나라도 없으면 실패로 닫는다. 못 읽은 응답을 성공으로 접으면 잡은 없는데 화면에는
    도는 것으로 남고, 폴링이 영영 답을 못 찾는다.
    """
    env = _envelope(result)
    if not env:
        return {"ok": False, "error": "empty_response", "detail": ""}
    inner = env.get("result")
    inner = inner if isinstance(inner, Mapping) else {}
    if env.get("dry_run") or inner.get("dry_run"):
        # 스키마 기본값이 False 라 여기까지 오면 우리가 True 를 실었다는 뜻이다.
        return {"ok": False, "error": "dry_run",
                "detail": "미리보기만 돌았다 — dry_run 이 켜져 있다"}
    if not env.get("ok") or not inner.get("ok"):
        return {"ok": False, "error": "tool_refused",
                "detail": _why(env) or json.dumps(env, ensure_ascii=False)[:500]}
    if inner.get("registry_id") in (None, ""):
        # registry_id 가 없으면 폴링이 지목할 손잡이가 없다 — 제출된 것으로 치지 않는다.
        return {"ok": False, "error": "no_registry_id",
                "detail": json.dumps(inner, ensure_ascii=False)[:500]}
    return {
        "ok": True,
        "registry_id": inner["registry_id"],
        "job_id": str(inner.get("job_id") or ""),
        "work_dir": inner.get("work_dir") or "",
        "output_dir": inner.get("output_dir") or "",
        "sphere_report_path": inner.get("sphere_report_path") or "",
        "detail": json.dumps(inner, ensure_ascii=False)[:2000],
    }


class AmbiguousAngleSource(ValueError):
    """각도원을 값만 보고는 정할 수 없다 — 임의로 고르면 나머지가 조용히 무시된다."""


def deep_merge(base: dict, over: dict) -> dict:
    """딕트는 재귀 병합, 리스트·스칼라는 교체 — 서버 도구가 쓰는 규칙 그대로다.

    규칙이 서로 다르면 화면에서 본 것과 클러스터에서 도는 것이 달라진다.
    """
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _angle(over: dict) -> dict:
    """scenarios[0].angle_source 자리를 만들어 돌려준다(없으면 만든다)."""
    scen = over.setdefault("scenarios", [{}])
    if not scen:
        scen.append({})
    return scen[0].setdefault("angle_source", {})


# ── 낱낱 옵션 → scenario.json 자리 ────────────────────────────────────────
#
# ★2026-10-14 — **이 아래는 지금 살아 있는 경로가 아니다.** SmartTwinMCP 로 옮기면서
#   `extra_scenario_overrides` 를 **보내지 않기로** 했다(요청서 §2). 받는 쪽 병합이
#   **리스트를 통째로 바꾸므로**(`scenario_builder.py:88-89` "Lists in overrides REPLACE
#   base lists") `scenarios[0]…` 를 넘기면 기본 시나리오(피보나치 각도·후처리)가 **지워진다.**
#   그래서 `build_scenario_overrides` 는 호출되지 않는다 — 각도 방식·공차·DR·접촉·연속 낙하를
#   다시 여는 **다음 판(요청서 §5)**을 위해 표와 시험째로 남겨 둔다. 지우지 말 것.
#
# ⚠ **여기가 조용히 틀리는 자리다.** 서버 도구는 모르는 키를 그냥 병합해 두고 지나가므로,
#   이름이나 **자리**가 어긋나면 화면에서 고른 값이 해석에 **아무 영향을 안 주는데 잡은
#   성공한다.** 실제로 한 번 그랬다 — 각도 파라미터를 `angle_source` 바로 밑에 평평히
#   넣었는데, 파서는 `angle_source["fibonacci_lattice"]["num_points"]` 로 **한 단계 더
#   들어가서** 읽는다(pyKooCAE `Runner/CumulativeDesigner.py`). 방향 수를 아무리 바꿔도
#   프리셋 값 그대로 돌았을 것이다.
#
# 정본은 산문 카탈로그가 아니라 **파서**다 — `Runner/cli_help_kcr.py` 의 키 표와
# `/data/scenario/*/scenario.json` 실제 프리셋. 그 둘의 스냅샷을 리포에 두고 시험이 대조한다.
#
# 목적지 기호 → scenario.json 자리
_DEST_PATHS: dict[str, tuple[str, ...]] = {
    "top":      (),
    "scen":     ("scenarios", "0"),
    "sim":      ("simulation_params",),
    "surface":  ("simulation_params", "drop_surface"),
    "dr":       ("simulation_params", "dynamic_relaxation"),
    "angle":    ("scenarios", "0", "angle_source"),
    "cuboid":   ("scenarios", "0", "angle_source", "cuboid_geometry"),
    "fib":      ("scenarios", "0", "angle_source", "fibonacci_lattice"),
    "pitch":    ("scenarios", "0", "angle_source", "pitching_sweep"),
    "rollsw":   ("scenarios", "0", "angle_source", "rolling_sweep"),
    "casetxt":  ("scenarios", "0", "angle_source", "case_txt_file"),
    "explicit": ("scenarios", "0", "angle_source", "explicit"),
    "cum":      ("scenarios", "0", "cumulative"),
    "mix":      ("scenarios", "0", "cumulative", "angle_mixing"),
    "tol":      ("scenarios", "0", "tolerance"),
    "tolroll":  ("scenarios", "0", "tolerance", "roll"),
    "tolpitch": ("scenarios", "0", "tolerance", "pitch"),
    "tolyaw":   ("scenarios", "0", "tolerance", "yaw"),
    "post":     ("postprocess",),
    "env":      ("environment",),
}

# 각도원 이름 → 그 파라미터가 사는 목적지. 무엇을 골랐는지 유추할 때도 쓴다.
_ANGLE_DESTS = {"cuboid": "cuboid_geometry", "fib": "fibonacci_lattice",
                "pitch": "pitching_sweep", "rollsw": "rolling_sweep",
                "casetxt": "case_txt_file", "explicit": "explicit"}

_SCENARIO_MAP: dict[str, tuple[str, str]] = {
    # 모델
    "scenario_name": ("scen", "scenario_name"),
    # 각도 — 고르기
    "angle_source": ("angle", "source_type"),
    # 각도 — 육면체
    "include_faces": ("cuboid", "include_faces"),
    "include_edges": ("cuboid", "include_edges"),
    "include_corners": ("cuboid", "include_corners"),
    "cuboid_only": ("cuboid", "only"),
    # 각도 — 피보나치
    "num_directions": ("fib", "num_points"),
    "angle_spacing": ("fib", "angle_spacing"),
    "progressive": ("fib", "progressive"),
    "principal_directions": ("fib", "principal_directions"),
    "sampling_space": ("fib", "sampling_space"),
    "previous_stages": ("fib", "previous_stages"),
    # 각도 — 스윕
    "pitch_min": ("pitch", "pitch_min"),
    "pitch_max": ("pitch", "pitch_max"),
    "pitch_step": ("pitch", "pitch_step"),
    "pitch_roll_fixed": ("pitch", "roll_fixed"),
    "pitch_yaw_fixed": ("pitch", "yaw_fixed"),
    "roll_min": ("rollsw", "roll_min"),
    "roll_max": ("rollsw", "roll_max"),
    "roll_step": ("rollsw", "roll_step"),
    "roll_pitch_fixed": ("rollsw", "pitch_fixed"),
    # 각도 — 파일·직접
    "selected_indices": ("casetxt", "selected_indices"),
    "explicit_angles": ("explicit", "angles"),
    "explicit_file": ("explicit", "file"),
    # 각도 공차
    "tolerance_doe_type": ("tol", "doe_type"),
    "tolerance_doe_count": ("tol", "doe_count"),
    "tolerance_include_nominal": ("tol", "include_nominal"),
    "tolerance_roll": ("tolroll", "tolerance"),
    "tolerance_pitch": ("tolpitch", "tolerance"),
    "tolerance_yaw": ("tolyaw", "tolerance"),
    # 낙하 물리
    "height": ("sim", "height"),
    "gravity": ("sim", "gravity"),
    "t_final": ("sim", "tFinal"),
    "dt": ("sim", "dt"),
    "dtmin": ("sim", "dtmin"),
    "offset_distance": ("sim", "offset_distance"),
    "dr_nrcyck": ("dr", "nrcyck"),
    "dr_drtol": ("dr", "drtol"),
    "dr_drfctr": ("dr", "drfctr"),
    "dr_drterm": ("dr", "drterm"),
    "control_timestep": ("sim", "control_timestep"),
    "control_hourglass": ("sim", "control_hourglass"),
    "rigidify_small_dt_threshold": ("sim", "rigidify_small_dt_threshold"),
    # 바닥
    "drop_surface": ("surface", "type"),
    "surface_size": ("surface", "size"),
    "surface_mesh": ("surface", "mesh"),
    "num_outer_layers": ("surface", "num_outer_layers"),
    "ratio": ("surface", "ratio"),
    "roughness_mode": ("surface", "roughness_mode"),
    "r_max": ("surface", "r_max"),
    "shape_factor": ("surface", "shape_factor"),
    "shape_factor2": ("surface", "shape_factor2"),
    "deformable_to_rigid": ("surface", "deformable_to_rigid"),
    "density": ("sim", "density"),
    "youngs_modulus": ("sim", "youngs_modulus"),
    "poisson_ratio": ("sim", "poisson_ratio"),
    "non_reflecting_boundary": ("sim", "non_reflecting_boundary"),
    # 접촉
    "drop_contact": ("sim", "drop_contact"),
    "robust_contact": ("sim", "robust_contact"),
    "robust_contact_tolerance": ("sim", "robust_contact_tolerance"),
    "convert_general_to_single_surface": ("sim", "convert_general_to_single_surface"),
    "ensure_single_surface": ("sim", "ensure_single_surface"),
    "decompose_general_contact": ("sim", "decompose_general_contact"),
    "include_wall_in_general": ("sim", "include_wall_in_general"),
    "decompose_contact_margin": ("sim", "decompose_contact_margin"),
    "decompose_contact_absolute_margin_x": ("sim", "decompose_contact_absolute_margin_x"),
    "decompose_contact_absolute_margin_y": ("sim", "decompose_contact_absolute_margin_y"),
    "decompose_contact_absolute_margin_z": ("sim", "decompose_contact_absolute_margin_z"),
    # 연속 낙하
    "cumulative_steps": ("cum", "num_steps"),
    "mode_sequence": ("cum", "mode_sequence"),
    "base_angle_index": ("cum", "base_angle_index"),
    "angle_mixing": ("mix", "strategy"),
    "cyclic_offset": ("mix", "cyclic_offset"),
    "random_seed": ("mix", "random_seed"),
    "custom_mapping": ("mix", "custom_mapping"),
    # 후처리
    "postprocess_enabled": ("post", "enabled"),
    "auto_deep": ("post", "auto_deep"),
    "auto_sphere": ("post", "auto_sphere"),
    "deep_timeout_seconds": ("post", "deep_timeout_seconds"),
    "sphere_time_limit": ("post", "sphere_time_limit"),
    "section_view_mode": ("post", "section_view_mode"),
    "section_view_axes": ("post", "section_view_axes"),
    "section_view_fields": ("post", "section_view_fields"),
    "sv_threads": ("post", "sv_threads"),
    "ua_threads": ("post", "ua_threads"),
    "yield_stress_mpa": ("post", "yield_stress_mpa"),
    # 자원
    "ncpu": ("env", "ncpu"),
    "nodes_per_job": ("env", "nodes_per_job"),
    "mpi_enabled": ("env", "mpi_enabled"),
    # 고급
    "preserve_includes": ("top", "preserve_includes"),
}

# `dynamic_relaxation` 은 **bool 또는 객체**다. 토글만 주면 bool, 세부를 주면 객체가 된다.
_DR_TOGGLE = "dynamic_relaxation"

# scenario 가 아니라 **도구 인자**로 가는 것들(여기서 덮어쓰기로 만들지 않는다).
TOOL_ARGS = frozenset({"model", "job_name", "angle_preset", "case_txt", "memory",
                       "time_limit", "scenario_overrides"})


def _dest(over: dict, kind: str) -> dict:
    """목적지 자리를 만들어 돌려준다. 리스트 단계("0")는 첫 원소를 쓴다."""
    try:
        path = _DEST_PATHS[kind]
    except KeyError:                       # 표에 없는 기호 — 조용히 버리지 않는다
        raise KeyError(f"알 수 없는 목적지: {kind}") from None
    node: Any = over
    for i, step in enumerate(path):
        if step == "0":
            continue                        # 앞 단계에서 리스트를 만들며 첫 원소를 잡는다
        nxt = path[i + 1] if i + 1 < len(path) else None
        if nxt == "0":
            lst = node.setdefault(step, [{}])
            if not lst:
                lst.append({})
            node = lst[0]
        else:
            node = node.setdefault(step, {})
    return node


def build_scenario_overrides(args: Mapping[str, Any], *, has_case_txt: bool = False) -> dict:
    """폼에서 받은 낱낱 옵션을 scenario.json 구조로 옮긴다.

    **우선순위** — 여기서 만든 것 위에 사용자의 `scenario_overrides` 가 마지막으로 덮인다.
    그래야 서버에 새 옵션이 생겨도 이 표를 고치지 않고 바로 쓸 수 있다.
    """
    over: dict = {}

    # dynamic_relaxation 토글을 먼저 — 세부(dr)가 이 값을 보고 객체로 승격한다.
    dr_detail = any(args.get(k) is not None for k in
                    ("dr_nrcyck", "dr_drtol", "dr_drfctr", "dr_drterm"))
    if args.get(_DR_TOGGLE) is not None and not dr_detail:
        over.setdefault("simulation_params", {})[_DR_TOGGLE] = bool(args[_DR_TOGGLE])
    elif dr_detail:
        _dest(over, "dr")["enabled"] = bool(args.get(_DR_TOGGLE, True))

    used_angle_dests: list[str] = []
    for arg_key, (kind, scen_key) in _SCENARIO_MAP.items():
        v = args.get(arg_key)
        if v is None or v == "":
            continue
        _dest(over, kind)[scen_key] = v
        if kind in _ANGLE_DESTS:
            used_angle_dests.append(kind)

    # 각도원을 안 골랐으면 **실제로 준 값**으로 정한다. 파일을 골랐으면 그것이 곧 의사표시다.
    #
    # ⚠ 둘 이상으로 보이면 **고르지 않고 거절한다.** 예컨대 방향 수(피보나치)와 면 포함
    #   여부(육면체)를 함께 주면 어느 쪽을 원했는지 알 수 없는데, 임의로 하나를 고르면
    #   나머지 값은 조용히 무시된 채 잡이 성공한다 — 사용자는 몇 시간 뒤 결과를 보고야 안다.
    if has_case_txt:
        _dest(over, "angle")["source_type"] = "case_txt_file"
    elif not args.get("angle_source") and used_angle_dests:
        picked = sorted(set(used_angle_dests))
        if len(picked) > 1:
            raise AmbiguousAngleSource(
                "각도원을 알 수 없다 — " + " · ".join(_ANGLE_DESTS[k] for k in picked)
                + " 의 값이 함께 들어왔다. `angle_source` 를 골라 주거나 한쪽 값만 남겨라.")
        _dest(over, "angle")["source_type"] = _ANGLE_DESTS[picked[0]]

    user = args.get("scenario_overrides")
    if isinstance(user, dict) and user:
        over = deep_merge(over, user)
    return over


def slurm_ids_of(details: Any) -> list[str]:
    """`get_job_details` 응답에서 slurm id 목록을 뽑는다(집계 잡까지 포함).

    `job_status` 가 squeue 에 물을 때 `sphere_job_id` 를 목록에 더하므로
    (`job_status/latest/script.sh:19-21`) 여기서도 같이 센다 — 안 세면 본 잡이 끝나고
    집계만 남은 구간을 "다 끝났다" 로 읽는다.
    """
    env = _envelope(details)
    inner = env.get("result")
    job = (inner or {}).get("job") if isinstance(inner, Mapping) else None
    if not isinstance(job, Mapping):
        return []
    ids = [str(x) for x in (job.get("slurm_job_ids") or []) if str(x).strip()]
    if job.get("sphere_job_id"):
        ids.append(str(job["sphere_job_id"]))
    return ids


def registry_id_of(status: Any) -> Any:
    """상태 응답에서 레지스트리 행 id 를 꺼낸다(없으면 None).

    ⚠ 그 칸의 **이름이 `job_id`** 다(`job_status/latest/script.sh:16`) — 제출 응답의
    `job_id`(slurm job id)와 **같은 이름, 다른 것**이다. 섞으면 영영 못 찾는 잡이 된다.
    """
    env = _envelope(status)
    inner = env.get("result")
    if not env.get("ok") or not isinstance(inner, Mapping) or not inner.get("ok"):
        return None
    return inner.get("job_id")


def parse_status(status: Any, details: Any) -> dict:
    """두 응답을 합쳐 → {"state": "active"|"succeeded"|"failed"|"unknown", …}.

    **왜 둘인가** — `job_status` 응답에 `slurm_job_ids` 가 없다. 있는 것은 `squeue` 뿐인데
    `slurm_queue_for` 는 예외가 나도 `{}` 를 돌려주므로(`job_helpers.py:197-198`) 빈 `{}`
    하나가 세 가지를 뜻한다. 다 끝났다 · 아직 큐에 안 올랐다 · squeue 가 실패했다.
    빈 것을 그냥 성공으로 접으면 **제출 직후에 바로 끝난 것이 된다.**
    그래서 레지스트리 행을 주는 `get_job_details` 로 id 목록을 함께 받아 가른다.

    모르면 **모른다고 한다.** 임의로 성공이나 실패로 접으면, 도구가 고장 난 것과 잡이
    끝난 것이 같은 모양이 된다.
    """
    env_s, env_d = _envelope(status), _envelope(details)
    inner_s = env_s.get("result")
    inner_s = inner_s if isinstance(inner_s, Mapping) else {}
    if not env_s or not env_s.get("ok") or not inner_s.get("ok"):
        return {"state": "unknown", "reason": _why(env_s) or "status_unreadable",
                "raw": json.dumps(env_s, ensure_ascii=False)[:500]}
    if not env_d or not env_d.get("ok"):
        return {"state": "unknown", "reason": _why(env_d) or "details_unreadable",
                "raw": json.dumps(env_d, ensure_ascii=False)[:500]}

    ids = slurm_ids_of(details)
    squeue = inner_s.get("squeue")
    squeue = squeue if isinstance(squeue, Mapping) else {}
    raw = json.dumps({"squeue": squeue, "slurm_job_ids": ids}, ensure_ascii=False)[:2000]

    if not ids:
        # 제출은 됐는데 아직 slurm id 가 레지스트리에 안 적혔다 — 끝난 것이 아니다.
        return {"state": "active", "reason": "no_slurm_ids_yet", "raw": raw}

    states = []
    for v in squeue.values():
        s = str((v or {}).get("state") or "").upper().rstrip("+")   # CANCELLED+ 꼬리표
        if s:
            states.append(s)

    # **하나라도 실패면 실패다** — 방향 하나가 죽은 연구를 성공으로 넘기지 않는다.
    bad = [s for s in states if s in STATES_BAD]
    if bad:
        return {"state": "failed", "slurm": sorted(set(bad)), "raw": raw}
    if any(s in STATES_ACTIVE for s in states):
        return {"state": "active", "raw": raw}
    if states and all(s in STATES_OK for s in states):
        return {"state": "succeeded", "raw": raw}
    if not states:
        # id 는 있는데 큐에 하나도 없다 — 요청서가 정한 잠정 규칙으로 끝으로 본다.
        # ⚠ squeue 호출 실패와 구분이 안 된다. 실제 응답 원문을 받으면 여기를 고친다.
        return {"state": "succeeded", "reason": "all_gone_from_squeue", "raw": raw}
    return {"state": "unknown", "reason": f"unmapped_states:{sorted(set(states))}", "raw": raw}


class McpHttpClient:
    """streamable-http MCP 엔드포인트에 JSON-RPC 로 tools/call 하는 최소 클라이언트.

    `client` 를 주입받는다 — 시험은 MockTransport 를 실은 AsyncClient 를 넣어 망 없이 돈다.
    """

    def __init__(self, endpoint: str, *, headers: Mapping[str, str] | None = None,
                 client: httpx.AsyncClient | None = None,
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self._headers = dict(headers or {})
        self._client = client
        self._owns_client = client is None
        self._session_id: str | None = None
        self._next_id = 0

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    def _rpc_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _base_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
            **self._headers,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    @staticmethod
    def _decode(response: httpx.Response) -> dict | None:
        """application/json 과 text/event-stream 을 **둘 다** 받는다 — 서버가 어느 쪽으로
        답할지는 요청마다 달라진다. 한쪽만 읽으면 간헐적으로 '응답을 못 읽는' 모양이 된다."""
        text = response.text
        if "text/event-stream" in response.headers.get("content-type", ""):
            last = None
            for line in text.splitlines():
                if not line.startswith("data:"):
                    continue
                try:
                    last = json.loads(line[len("data:"):].strip())
                except ValueError:
                    continue
            return last
        try:
            return json.loads(text)
        except ValueError:
            return None

    async def _post(self, payload: dict) -> dict:
        response = await self._http().post(
            self.endpoint, headers=self._base_headers(),
            content=json.dumps(payload).encode("utf-8"), timeout=self.timeout)
        session_id = response.headers.get("mcp-session-id")
        if session_id:
            self._session_id = session_id
        if response.status_code >= 400:
            return {"ok": False, "error": f"http_{response.status_code}",
                    "detail": response.text[:500]}
        if response.status_code == 202:
            return {"ok": True, "result": {}}
        message = self._decode(response)
        if message is None:
            return {"ok": False, "error": "unparsable_response", "detail": response.text[:500]}
        if isinstance(message, dict) and message.get("error"):
            return {"ok": False, "error": "rpc_error", "detail": message["error"]}
        return {"ok": True, "result": (message or {}).get("result") or {}}

    async def _handshake(self) -> dict:
        if self._session_id is not None:
            return {"ok": True, "result": {}}
        reply = await self._post({
            "jsonrpc": "2.0", "id": self._rpc_id(), "method": "initialize",
            "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                       "clientInfo": {"name": "dynaforge", "version": "1"}},
        })
        if not reply["ok"]:
            return reply
        # 세션 헤더를 안 주는 서버에서도 재핸드셰이크를 반복하지 않게 표시만 남긴다.
        if self._session_id is None:
            self._session_id = ""
        await self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        return {"ok": True, "result": {}}

    @staticmethod
    def _unwrap(result: Mapping[str, Any]) -> Any:
        """structuredContent > text(JSON) > text 원문 순으로 꺼낸다."""
        if not isinstance(result, Mapping):
            return result
        if result.get("structuredContent") is not None:
            return result["structuredContent"]
        content = result.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, Mapping) and first.get("type") == "text":
                text = first.get("text")
                try:
                    return json.loads(text)
                except (TypeError, ValueError):
                    return text
        return result

    async def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> dict:
        try:
            handshake = await self._handshake()
            if not handshake["ok"]:
                return handshake
            reply = await self._post({
                "jsonrpc": "2.0", "id": self._rpc_id(), "method": "tools/call",
                "params": {"name": name, "arguments": dict(arguments or {})},
            })
        except httpx.HTTPError as exc:
            return {"ok": False, "error": "transport_error",
                    "detail": f"{type(exc).__name__}: {exc}"}
        if not reply["ok"]:
            return reply
        result = reply["result"] if isinstance(reply["result"], Mapping) else {}
        if result.get("isError"):
            return {"ok": False, "error": "tool_error", "detail": self._unwrap(result)}
        return {"ok": True, "result": self._unwrap(result)}

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None


# ── 덱 반입 ────────────────────────────────────────────────────────────────
# stcx 대시보드(:5010)의 청크 업로드. 3단계다 — init → chunk ×N → complete.
# 필드 이름은 **코드에서 읽어 맞췄다**(`file_upload_api.py:104-118`·`:210-223`·`:326-331`) —
#   init     JSON       {filename, file_size, job_id?, chunk_size?}
#                       → 201 {upload_id, chunk_size, total_chunks, storage_path, file_info}
#   chunk    multipart  form `upload_id` · form `chunk_index`(0부터) · file `chunk`
#                       · form `checksum`(선택, MD5 — 받는 쪽이 맞춰 본다)
#   complete JSON       {upload_id} → 200 {file_path, file_info}
#
# ★**`job_id` 를 반드시 싣는다.** 안 싣으면 저장 경로가
#   `/shared/uploads/users/<user>/data/` 로 모이는데(`file_classifier.py:302`), SSO 가 꺼져
#   **모든 요청이 `admin`** 이고(`jwt_middleware.py:61-67`) `complete` 는
#   `storage_path/filename` 에 그냥 쓴다(`:368`) — 같은 이름의 덱을 올린 두 잡이 **서로를
#   덮는다.** `job_id` 를 주면 `/shared/uploads/jobs/<job_id>/data/` 로 갈린다(`:297-299`).
#
# 청크 재전송은 안전하다 — `complete` 가 인덱스별 파일 존재를 다시 확인하므로
# (`:371-381`) 카운터가 부풀어도 병합 결과는 맞다.

UPLOAD_CHUNK_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_BYTES = 50 * 1024 * 1024 * 1024      # 받는 쪽 상한(`file_upload_api.py:43`)
UPLOAD_TIMEOUT = 300.0
# `complete` 는 청크 전부를 **서버에서 이어 붙인다**(`:370-384`) — 파일 크기에 비례하는
# 디스크 작업이라 GB 급에서는 분 단위다. init·chunk 와 같은 시한을 주면 거기서 끊긴다.
COMPLETE_TIMEOUT = 1800.0
_CHUNK_RETRY = 3                                # 분당 2000 청크 제한(`:190`)에 걸릴 수 있다
_CHUNK_BACKOFF_S = 5.0


def upload_name(name: str) -> str:
    """올릴 때 쓸 이름. 받는 쪽 패턴이 `^/.+\\.k$` 라 **`.k` 로 끝나야 한다**.

    `.key`·`.dyn`·`.K` 는 이름만 바꾼다 — **원본 파일은 건드리지 않는다.**
    패턴이 대소문자를 가리므로 `.K` 도 바꿔야 한다(`model_file_path` 스키마).
    """
    base = Path(name).name
    return base if base.endswith(".k") else Path(base).stem + ".k"


class StcxUploader:
    """세션의 덱 하나를 stcx 헤드노드로 올리고 **그쪽 절대경로**를 돌려준다.

    실패를 예외로 올리지 않는다 — 이 파일의 다른 것들과 같은 규약이다.
    """

    def __init__(self, base_url: str, *, client: httpx.AsyncClient | None = None,
                 timeout: float = UPLOAD_TIMEOUT) -> None:
        self._base = (base_url or "").strip().rstrip("/")
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    @property
    def available(self) -> bool:
        return bool(self._base)

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def _json(self, path: str, payload: dict, *, timeout: float | None = None) -> dict:
        try:
            res = await self._http().post(self._base + path, json=payload,
                                          timeout=timeout or self._timeout)
        except httpx.HTTPError as exc:
            return {"ok": False, "error": "transport_error",
                    "detail": f"{type(exc).__name__}: {exc}"}
        if res.status_code >= 400:
            return {"ok": False, "error": f"http_{res.status_code}", "detail": res.text[:400]}
        try:
            return {"ok": True, "body": res.json()}
        except ValueError:
            return {"ok": False, "error": "unparsable_reply", "detail": res.text[:400]}

    async def _chunk(self, upload_id: str, index: int, name: str, blob: bytes) -> dict:
        digest = hashlib.md5(blob).hexdigest()      # 전송 무결성용 — 받는 쪽이 맞춰 본다
        for attempt in range(_CHUNK_RETRY):
            try:
                res = await self._http().post(
                    self._base + "/api/v2/files/upload/chunk",
                    data={"upload_id": upload_id, "chunk_index": str(index),
                          "checksum": digest},
                    files={"chunk": (name, blob, "application/octet-stream")},
                    timeout=self._timeout)
            except httpx.HTTPError as exc:
                return {"ok": False, "error": "transport_error",
                        "detail": f"{type(exc).__name__}: {exc} (chunk {index})"}
            if res.status_code < 400:
                return {"ok": True}
            if res.status_code == 429 and attempt + 1 < _CHUNK_RETRY:
                await asyncio.sleep(_CHUNK_BACKOFF_S * (attempt + 1))
                continue
            return {"ok": False, "error": f"http_{res.status_code}",
                    "detail": f"chunk {index}: {res.text[:300]}"}
        return {"ok": False, "error": "chunk_retries_exhausted", "detail": f"chunk {index}"}

    async def upload(self, src: Path, *, job_id: str) -> dict:
        """→ {"ok": True, "file_path": "<헤드노드 절대경로>", …} 또는 실패."""
        if not self.available:
            return {"ok": False, "error": "unavailable",
                    "detail": "반입 주소가 설정되지 않았다(KOORM_STCX_BACKEND_URL)"}
        src = Path(src)
        try:
            size = src.stat().st_size
        except OSError as exc:
            return {"ok": False, "error": "unreadable_model",
                    "detail": f"{type(exc).__name__}: {exc}"}
        if size <= 0:
            return {"ok": False, "error": "empty_model", "detail": str(src)}
        if size > MAX_UPLOAD_BYTES:
            return {"ok": False, "error": "too_large",
                    "detail": f"{size}B — 받는 쪽 상한 {MAX_UPLOAD_BYTES}B 를 넘는다"}

        name = upload_name(src.name)
        init = await self._json("/api/v2/files/upload/init",
                                {"filename": name, "file_size": size, "job_id": str(job_id)})
        if not init["ok"]:
            return init
        body = init.get("body") or {}
        upload_id = str(body.get("upload_id") or "")
        chunk_size = int(body.get("chunk_size") or UPLOAD_CHUNK_BYTES)
        total = int(body.get("total_chunks") or 0)
        if not upload_id or chunk_size <= 0 or total <= 0:
            return {"ok": False, "error": "bad_init_reply",
                    "detail": json.dumps(body, ensure_ascii=False)[:400]}

        with src.open("rb") as fh:
            for index in range(total):
                blob = fh.read(chunk_size)
                if not blob:
                    # 파일이 전송 중에 줄었다. 반쪽 덱을 올려 두고 성공으로 넘기지 않는다.
                    return {"ok": False, "error": "short_read",
                            "detail": f"chunk {index}/{total} 에서 읽을 것이 없다"}
                sent = await self._chunk(upload_id, index, name, blob)
                if not sent["ok"]:
                    return sent

        done = await self._json("/api/v2/files/upload/complete", {"upload_id": upload_id},
                                timeout=COMPLETE_TIMEOUT)
        if not done["ok"]:
            return done
        path = str((done.get("body") or {}).get("file_path") or "")
        # 받는 쪽 도구의 패턴(`^/.+\.k$`)을 **여기서** 본다 — 제출이 거절되고 나서
        # "왜 안 됐지" 를 되짚는 것보다 반입 단계에서 말하는 편이 훨씬 싸다.
        if not path.startswith("/") or not path.endswith(".k"):
            return {"ok": False, "error": "bad_file_path",
                    "detail": f"반입 응답의 file_path 가 `^/.+\\.k$` 가 아니다: {path[:200]!r}"}
        return {"ok": True, "file_path": path, "bytes": size, "chunks": total,
                "upload_id": upload_id}

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None


class StcxClient:
    """DynaForge → 게이트웨이 → stcx. 자격이 없으면 **아무것도 부르지 않는다**."""

    def __init__(self, endpoint: str, token: str | None, *,
                 client: httpx.AsyncClient | None = None,
                 timeout: float = DEFAULT_TIMEOUT,
                 mcp: McpHttpClient | None = None) -> None:
        self.endpoint = endpoint
        self.token = (token or "").strip()
        self._mcp = mcp
        self._client = client
        self._timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.endpoint and self.token)

    def _client_or_none(self) -> McpHttpClient | None:
        if self._mcp is not None:
            return self._mcp
        if not self.available:
            return None
        self._mcp = McpHttpClient(
            self.endpoint, headers={"Authorization": f"Bearer {self.token}"},
            client=self._client, timeout=self._timeout)
        return self._mcp

    async def _call(self, tool: str, args: Mapping[str, Any]) -> dict:
        mcp = self._client_or_none()
        if mcp is None:
            # 꺼져 있는 것을 실패로 낸다 — 조용히 성공으로 넘어가면 잡이 제출된 줄 안다.
            return {"ok": False, "error": "unavailable",
                    "detail": "게이트웨이 주소 또는 PAT 가 설정되지 않았다(KOORM_GATEWAY_MCP/KOORM_GATEWAY_PAT)"}
        return await mcp.call(tool, args)

    @staticmethod
    def _locator(registry_id: Any, work_dir: str) -> dict:
        """잡을 지목하는 인자. `registry_id` 가 정석이고 `work_dir` 는 그것을 모를 때다.

        받는 쪽 스키마가 `additionalProperties: False` 라 둘 다 실으면 안 되는 것이 아니고
        둘 다 허용되지만, **하나만** 보낸다 — 두 값이 어긋났을 때 어느 쪽이 이겼는지
        모르는 상태를 만들지 않는다.
        """
        if registry_id not in (None, ""):
            return {"registry_id": int(registry_id)}
        return {"work_dir": work_dir} if work_dir else {}

    async def submit_fullangle_drop(self, args: Mapping[str, Any], *,
                                    dry_run: bool = False) -> dict:
        """전각도 낙하 제출. `args` 는 **이미 받는 쪽 이름으로 옮겨진** 것이다(매핑은 호출부).

        직접 노출 도구는 `args` **한 겹**을 받는다(`server.py:218-219`). 평평하게 보내면
        스키마 검증에서 통째로 떨어진다.

        `dry_run` 은 스키마 기본값이 이미 False 지만 **언제나 명시한다** — 기본값이 바뀌어도
        우리 뜻이 남는다. 예전 :5012 는 기본값이 True 였고, 그래서 미리보기만 돌았는데
        응답은 성공처럼 생긴 적이 있다.
        """
        return await self._call(TOOL_SUBMIT, {"args": {**dict(args), "dry_run": bool(dry_run)}})

    async def job_status(self, registry_id: Any = None, *, work_dir: str = "") -> dict:
        """squeue + KooChainRun 상태.

        ⚠ 응답의 `job_id` 는 **레지스트리 행 id** 다 — 제출 응답의 `job_id`(slurm job id)와
        **같은 이름, 다른 것**이다. 지목은 `registry_id` 로만 한다.
        """
        return await self._call(TOOL_STATUS, {"args": self._locator(registry_id, work_dir)})

    async def job_details(self, registry_id: Any = None, *, work_dir: str = "") -> dict:
        """레지스트리 행 전체 — **`slurm_job_ids` 가 여기 있다**(상태 응답에는 없다)."""
        return await self._call(TOOL_DETAILS, {"args": self._locator(registry_id, work_dir)})

    async def close(self) -> None:
        if self._mcp is not None:
            await self._mcp.close()
