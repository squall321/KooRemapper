# scenario.json(KooChainRun DOE 정의)을 조건 요약으로 정규화 — 리포트에 "어떤 시뮬인지"를 붙인다.
"""Summarize a KooChainRun ``scenario.json`` into compact simulation conditions.

한 K파일로 여러 해석(전각도·스캐터·스윕…)을 돌리므로, 리포트마다 scenario.json 을
받아 "이 결과가 어떤 조건이었는지"(angle_source·tolerance·높이·스텝)를 요약해 둔다.
``template``(.k 파일명)은 세션 내 원본 K파일 자동 매칭의 열쇠다.

방어적 파싱: 키가 없으면 None — 지어내지 않는다.
"""
from __future__ import annotations

import json
import math


class ScenarioParseError(ValueError):
    pass


def _num(v):
    """유한 숫자만 float — json.loads 는 1e999→inf 를 통과시키므로 int(inf) 500 을 막는다."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _int(v) -> int | None:
    f = _num(v)
    return int(f) if f is not None else None


def _base_count(source_type: str | None, src: dict) -> int | None:
    """angle_source 에서 기준 방향 수를 계산(가능할 때만)."""
    if source_type == "cuboid_geometry":
        g = src.get("cuboid_geometry") or {}
        return (6 if g.get("include_faces", True) else 0) \
            + (12 if g.get("include_edges", True) else 0) \
            + (8 if g.get("include_corners", True) else 0)
    if source_type == "fibonacci_lattice":
        g = src.get("fibonacci_lattice") or {}
        return _int(g.get("num_directions", g.get("num_points")))
    if source_type in ("pitching_sweep", "rolling_sweep"):
        g = src.get(source_type) or {}
        axis = "pitch" if source_type == "pitching_sweep" else "roll"
        lo, hi, step = _num(g.get(f"{axis}_min")), _num(g.get(f"{axis}_max")), _num(g.get(f"{axis}_step"))
        if None not in (lo, hi, step) and step > 0:
            # 부동소수 절단 오프바이원 방지: 2.9999999996 → 3 (ε 보정 후 내림)
            return int((hi - lo) / step + 1e-9) + 1
        return None
    if source_type == "case_txt_file":
        sel = (src.get("case_txt_file") or {}).get("selected_indices")
        return len(sel) if isinstance(sel, list) else None
    return None


# angle_source 원본 서브블록 반사 상한 — 임의 대형/중첩 JSON 이 JSONB·API 응답·
# MCP(LLM 컨텍스트)로 그대로 흘러가는 것을 막는다.
_ANGLE_SOURCE_MAX_CHARS = 20_000


def _sanitize(obj, depth: int = 0):
    """비유한 수(NaN/±Inf)→None 재귀 치환 — json.loads 는 통과시키지만 Postgres JSONB 는
    거부하므로(커밋 500), 원본 복사 블록은 저장 전에 반드시 거친다. 깊이 상한으로 방어."""
    if depth > 8:
        return None
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {str(k): _sanitize(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v, depth + 1) for v in obj]
    return obj


def _bounded_angle_source(src: dict) -> dict | None:
    sub = {k: v for k, v in src.items() if k != "source_type"}
    if not sub:
        return None
    try:
        if len(json.dumps(sub, ensure_ascii=False)) > _ANGLE_SOURCE_MAX_CHARS:
            return {"_truncated": True, "_note": "angle_source 가 너무 커서 원본 파일만 보관"}
    except (TypeError, ValueError):
        return {"_truncated": True}
    return _sanitize(sub)


def summarize_scenario(data: dict) -> dict:
    """scenario.json dict → 조건 요약. 시나리오 형태가 아니면 ScenarioParseError."""
    if not isinstance(data, dict):
        raise ScenarioParseError("scenario.json 이 JSON 객체가 아닙니다.")
    raw_scens = data.get("scenarios")
    if not isinstance(raw_scens, list) or not raw_scens:
        raise ScenarioParseError("scenarios 배열이 없습니다 — KooChainRun scenario.json 이 맞는지 확인하세요.")

    sp = data.get("simulation_params") if isinstance(data.get("simulation_params"), dict) else {}
    sim = {
        "drop_height": _num(sp.get("height", sp.get("drop_height"))),
        "t_final": _num(sp.get("tFinal", sp.get("t_final"))),
        "dt": _num(sp.get("dt")),
    }

    scens = []
    templates = []
    for s in raw_scens:
        if not isinstance(s, dict):
            continue
        src = s.get("angle_source") if isinstance(s.get("angle_source"), dict) else {}
        stype = src.get("source_type")
        tol_in = s.get("tolerance") if isinstance(s.get("tolerance"), dict) else None
        tol = None
        n_base = _base_count(stype, src)
        expected = None
        if tol_in:
            tol = {
                "roll": _sanitize(tol_in.get("roll")), "pitch": _sanitize(tol_in.get("pitch")),
                "yaw": _sanitize(tol_in.get("yaw")),
                "doe_type": tol_in.get("doe_type") if isinstance(tol_in.get("doe_type"), str) else None,
                "doe_count": _int(tol_in.get("doe_count")),
            }
            if n_base is not None and tol["doe_count"]:
                expected = n_base * tol["doe_count"]  # 방향마다 doe_count (실측 검증된 확장 규칙)
        elif n_base is not None:
            expected = n_base

        cum = s.get("cumulative") if isinstance(s.get("cumulative"), dict) else {}
        tpl = s.get("template")
        if isinstance(tpl, str) and tpl:
            templates.append(tpl)
        scens.append({
            "name": s.get("scenario_name"),
            "template": tpl,
            "source_type": stype,
            "angle_source": _bounded_angle_source(src),
            "tolerance": tol,
            "n_base_directions": n_base,
            "expected_runs": expected,
            "num_steps": cum.get("num_steps"),
            "mode_sequence": cum.get("mode_sequence"),
        })

    # 최종 요약 전체를 새니타이즈 — 원시 복사 필드(num_steps·mode_sequence·이름 등)까지
    # 비유한 수를 걸러 JSONB 저장이 절대 안 깨지게 한다.
    return _sanitize({
        "project_name": data.get("project_name"),
        "sim_params": sim,
        "scenarios": scens,
        "templates": templates,  # 세션 내 K파일 자동 매칭용(.k 파일명)
    })
