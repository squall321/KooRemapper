# 리포트 HTML의 임베드 데이터(const …={…})를 추출해 공통 kind 스키마로 정규화한다.
"""Extract and normalize embedded report data from koo_*_report HTML.

The generated HTML files are self-contained: the entire dataset is embedded as a
strict-JSON JavaScript object literal (deep → ``const DATA = {…}``, sphere →
``const REPORT_DATA = {…}``, impact → see ``normalize_impact``). We locate that
assignment, balance-match its braces (string-aware, so braces inside part names
or finding text don't fool us), ``json.loads`` it, detect the report ``kind``,
and normalize to the common study schema documented in docs/impact-ingest/plan.md.

Pure functions, no I/O — callers pass HTML text (or an already-parsed sidecar
JSON dict). Never trusts field presence: part-id keys are strings and
non-contiguous, names may hold literal backslashes, and many metrics are ``null``
meaning "not measured" (never coerced to 0).
"""
from __future__ import annotations

import json
import math
import re
import statistics

# 임베드 데이터 대입식: `const IDENT = {`. 알려진 식별자를 우선 시도하고, 없으면
# 모든 `const IDENT = {…}` 를 훑어 kind 시그니처가 잡히는 가장 큰 객체를 고른다.
_ASSIGN_RE = re.compile(r"(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{")
_PREFERRED_IDENTS = ("DATA", "REPORT_DATA", "REPORT")


class ReportParseError(ValueError):
    """HTML에서 임베드 데이터를 못 찾았거나 kind 를 판별하지 못함."""


def _balanced_json(text: str, open_brace_idx: int) -> str:
    """``text[open_brace_idx]`` 의 '{' 부터 짝이 맞는 '}' 까지의 JSON 문자열을 돌려준다.

    문자열 리터럴 안의 중괄호/이스케이프를 인식해 건너뛴다(파트 이름의 백슬래시,
    findings 본문의 중괄호 등에 속지 않도록).
    """
    depth = 0
    in_str = False
    esc = False
    for k in range(open_brace_idx, len(text)):
        c = text[k]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[open_brace_idx : k + 1]
    raise ReportParseError("임베드 데이터의 중괄호 짝을 찾지 못했습니다.")


def extract_embedded_data(html: str) -> dict:
    """리포트 HTML에서 임베드된 데이터 객체를 파싱해 dict 로 돌려준다.

    두 임베드 방식을 지원한다.
      1) 인라인(대부분): ``const DATA = {…}`` / ``const REPORT_DATA = {…}``.
      2) deferred(대형 impact tier C): ``<script type="application/json" id="koo-data">…</script>``.
    chunked(tier D)는 데이터가 별도 파일로 쪼개져 단일 HTML만으론 복원 불가 —
    이 경우 부분 객체라도 kind 가 잡히면 반환하되, 케이스가 비면 상위에서 걸러진다.
    """
    best: dict | None = None

    # 1) const IDENT = {…}
    candidates: list[tuple[str, int]] = []  # (ident, brace_index)
    for m in _ASSIGN_RE.finditer(html):
        brace = html.index("{", m.start())
        candidates.append((m.group(1), brace))

    def _priority(item: tuple[str, int]) -> tuple[int, int]:
        ident, _ = item
        try:
            return (_PREFERRED_IDENTS.index(ident), 0)
        except ValueError:
            return (len(_PREFERRED_IDENTS), item[1])

    for ident, brace in sorted(candidates, key=_priority):
        try:
            obj = json.loads(_balanced_json(html, brace))
        except (ReportParseError, json.JSONDecodeError):
            continue
        if not isinstance(obj, dict):
            continue
        if _detect_kind_opt(obj) is not None:
            return obj
        if best is None or len(obj) > len(best):
            best = obj

    # 2) <script type="application/json" id="koo-data">…</script>
    m = re.search(r'<script[^>]*id=["\']koo-data["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(1).strip())
            if isinstance(obj, dict):
                if _detect_kind_opt(obj) is not None:
                    return obj
                if best is None or len(obj) > len(best):
                    best = obj
        except json.JSONDecodeError:
            pass

    if best is not None:
        return best
    raise ReportParseError("HTML에서 임베드 리포트 데이터를 찾지 못했습니다.")


# ── kind 판별 ────────────────────────────────────────────────────────
def _detect_kind_opt(data: dict) -> str | None:
    """임베드 객체의 키 시그니처로 리포트 kind 를 판별. 미상이면 None."""
    keys = set(data.keys())
    # impact: 면×위치 DOE — positions+results 쌍 + faces/doe_analysis. (results 를 sphere 와
    # 공유하므로 sphere 보다 먼저 판별해 오분류를 막는다.)
    if data.get("generated_by") == "koo_impact_report":
        return "impact"
    if ("positions" in keys and "results" in keys) or ({"faces", "doe_analysis"} <= keys):
        return "impact"
    # sphere: 각도별 results + 구면 커버리지.
    if "results" in keys and ({"sphere_coverage", "angular_spacing_deg"} & keys):
        return "sphere"
    # deep: 단건 심층 — 텐서/에너지/단일 sim 블록.
    if "peak_element_tensors" in keys or ({"sim", "glstat"} <= keys) or ({"sim", "parts", "summary"} <= keys):
        return "deep"
    return None


def detect_kind(data: dict) -> str:
    kind = _detect_kind_opt(data)
    if kind is None:
        raise ReportParseError(f"리포트 kind 판별 실패 (keys={sorted(data)[:12]})")
    return kind


# ── 공통 유틸 ────────────────────────────────────────────────────────
def _group_of(name: str) -> str:
    """파트 이름에서 그룹 접두(백슬래시/슬래시 앞부분)를 뽑는다. 없으면 'Other'."""
    if not name:
        return "Other"
    for sep in ("\\", "/"):
        if sep in name:
            return name.split(sep)[0]
    return "Other"


def _num(v):
    """숫자면 float, None/비숫자면 None (미측정을 0으로 왜곡하지 않음).

    NaN/Infinity 는 None 으로 막는다 — json.loads 는 JS 의 NaN/Infinity 를 그대로
    파싱하는데, 이 값이 JSONB 컬럼에 들어가면 Postgres 커밋이 깨진다(유효 JSON 아님).
    """
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):  # NaN 또는 ±Inf
            return None
        return f
    return None


def _max_notnone(vals):
    xs = [v for v in vals if v is not None]
    return max(xs) if xs else None


def _min_notnone(vals):
    xs = [v for v in vals if v is not None]
    return min(xs) if xs else None


def _norm_findings(findings) -> list:
    """findings 를 {severity,title,detail,recommendation} 로 정규화.

    severity 가 Enum 직렬화("Severity.CRITICAL")로 새어 들어와도 값만 남긴다.
    """
    out = []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        sev = f.get("severity")
        if isinstance(sev, str) and sev.startswith("Severity."):
            sev = sev.split(".", 1)[1]
        out.append({
            "severity": sev,
            "title": f.get("title"),
            "detail": f.get("detail"),
            "recommendation": f.get("recommendation"),
        })
    return out


# ── deep 정규화 ──────────────────────────────────────────────────────
def normalize_deep(data: dict) -> dict:
    sim = data.get("sim") or {}
    meta = data.get("metadata") or {}
    summary_in = data.get("summary") or {}
    parts_in = data.get("parts")
    if not isinstance(parts_in, dict):
        parts_in = {}

    parts = []
    parts_metrics = {}
    for pid, p in parts_in.items():
        if not isinstance(p, dict):
            continue
        name = p.get("name") or f"Part_{pid}"
        parts.append({"part_id": _to_int(pid), "name": name, "group": _group_of(name)})
        parts_metrics[str(pid)] = {
            "peak_stress": _num(p.get("peak_stress")),
            "time_of_peak_stress": _num(p.get("time_of_peak_stress")),
            "peak_strain": _num(p.get("peak_strain")),
            "peak_disp": _num(p.get("peak_disp_mag")),
            "peak_vel": _num(p.get("peak_vel_mag")),
            "peak_acc": _num(p.get("peak_acc_mag")),
            "peak_principal": _num(p.get("peak_max_principal")),
            "min_principal": _num(p.get("peak_min_principal")),
            "peak_principal_strain": _num(p.get("peak_max_principal_strain")),
            "min_principal_strain": _num(p.get("peak_min_principal_strain")),
            "safety_factor": _num(p.get("safety_factor")),
        }

    case = {
        "case_key": "single",
        "identity": {},
        "meta": {
            "num_states": meta.get("num_states"),
            "tier": sim.get("tier"),
            "tier_label": sim.get("tier_label"),
            "success": sim.get("normal_termination"),
            "termination_source": sim.get("termination_source"),
            "t_end": _num(meta.get("end_time")),
        },
        "parts_metrics": parts_metrics,
        "rollup": _case_rollup(parts_metrics),
        # deep 전용 — 케이스 상세/에너지플로우 도구가 쓴다.
        "glstat_available": bool(data.get("glstat")),
        "contact_available": bool(data.get("contact_metrics")),
    }

    return {
        "kind": "deep",
        "source": {
            "generator": "koo_deep_report",
            "generator_version": meta.get("kood3plot_version"),
            "schema": None,
            "ingested_from": "html",
        },
        "project": {
            "name": sim.get("name") or (meta.get("d3plot_path") or "").rsplit("/", 1)[-1],
            "doe_strategy": None,
            "test_dir": sim.get("path"),
        },
        "sim_params": {
            "yield_stress": _num(data.get("yield_stress")),
            "num_states": meta.get("num_states"),
            "t_end": _num(meta.get("end_time")),
            "unit_system": None,
        },
        "parts": parts,
        "findings": [],
        "summary": {
            "peak_stress": _num(summary_in.get("peak_stress")),
            "peak_stress_part_id": summary_in.get("peak_stress_part_id"),
            "peak_strain": _num(summary_in.get("peak_strain")),
            "peak_disp": _num(summary_in.get("peak_disp")),
            "energy_ratio_min": _num(summary_in.get("energy_ratio_min")),
            "tier": sim.get("tier"),
        },
        "cases": [case],
    }


# ── sphere 정규화 ────────────────────────────────────────────────────
def _sphere_part_metrics(p: dict) -> dict:
    """sphere 파트의 스칼라 물리량을 전부 통과시킨다(시계열 *_ts·중첩 제외).

    상류(koo_sphere_report)가 새 지표를 넣으면 하드코딩 없이 자동 인식된다(peak_vel 등).
    - energy{peak_ie/peak_ke/final_ie/final_ke(+time)} 블록은 평탄화해 방향별 분석 대상이 되게.
    - peak_plastic_strain 이 없고 peak_strain 이 있으면 명시 별칭 추가(상류 확인: sphere 의
      peak_strain 은 유효소성변형률이다 — 이름만 달랐다).
    """
    m: dict = {}
    for k, v in (p or {}).items():
        if k.endswith("_ts") or isinstance(v, (dict, list, bool)):
            continue
        if isinstance(v, (int, float)):
            m[k] = _num(v)
    e = p.get("energy")
    if isinstance(e, dict):
        for ek in ("peak_ie", "peak_ke", "final_ie", "final_ke", "peak_ie_time", "peak_ke_time"):
            if ek in e:
                m[ek] = _num(e.get(ek))
    # 펄스 형상(10-17~) — 생성기가 **다운샘플 전** 값으로 따로 싣는다(「줄인 배열로 다시 적분하면 충격량이
    # 20% 넘게 빗나간다」). dict 라 위 통과에서 빠졌다 — 평탄화해 방향별 분석 대상이 되게 한다. 못 쟀으면 키가 없다.
    pu = p.get("pulse")
    if isinstance(pu, dict):
        for pk, pv in pu.items():
            if isinstance(pv, (int, float)) and not isinstance(pv, bool):
                m[pk if pk.startswith("pulse_") else "pulse_" + pk] = _num(pv)
    if "peak_plastic_strain" not in m and m.get("peak_strain") is not None:
        m["peak_plastic_strain"] = m["peak_strain"]
    return m


def normalize_sphere(data: dict) -> dict:
    sim_params_in = data.get("sim_params")
    if not isinstance(sim_params_in, dict):
        sim_params_in = {}
    parts_in = data.get("parts")
    if not isinstance(parts_in, dict):
        parts_in = {}

    parts = []
    for pid, p in parts_in.items():
        if not isinstance(p, dict):
            continue
        name = p.get("name") or p.get("part_name") or f"Part_{pid}"
        parts.append({"part_id": _to_int(pid), "name": name, "group": p.get("group") or _group_of(name)})

    cases = []
    for r in data.get("results") or []:
        if not isinstance(r, dict):
            continue
        angle = r.get("angle") or {}
        pm = {}
        for pid, p in (r.get("parts") or {}).items():
            pm[str(pid)] = _sphere_part_metrics(p)
        # 등장방형 마커용 방향 좌표(lon/lat). swap 규약을 여기서 한 번만 반영해
        # 저장한다 — 소비자(웹 마커·근접필터)가 Euler+swap 을 재계산하지 않도록.
        _lon_deg, _lat_deg = _angle_lonlat(angle)
        cases.append({
            "case_key": r.get("folder") or angle.get("name") or f"run_{len(cases)}",
            "identity": {
                "angle": {
                    "name": angle.get("name"),
                    "roll": _num(angle.get("roll")),
                    "pitch": _num(angle.get("pitch")),
                    "yaw": _num(angle.get("yaw")),
                    "category": angle.get("category"),
                    "swap": bool(angle.get("swap")),
                    "lon": _lon_deg,
                    "lat": _lat_deg,
                }
            },
            "meta": {"num_states": r.get("num_states"), "success": True},
            "parts_metrics": pm,
            "rollup": _case_rollup(pm),
        })

    return {
        "kind": "sphere",
        "source": {
            "generator": "koo_sphere_report",
            "generator_version": None,
            "schema": None,
            "ingested_from": "html",
        },
        "project": {
            "name": data.get("project_name"),
            "doe_strategy": data.get("doe_strategy"),
            "test_dir": data.get("test_dir"),
        },
        "sim_params": {
            "t_final": _num(sim_params_in.get("t_final")),
            "dt": _num(sim_params_in.get("dt")),
            "drop_height": _num(sim_params_in.get("drop_height")),
            "density": _num(sim_params_in.get("density")),
            "youngs_modulus": _num(sim_params_in.get("youngs_modulus")),
            "poisson_ratio": _num(sim_params_in.get("poisson_ratio")),
            "yield_stress": _num(data.get("yield_stress")),
            # 생성기가 검출한 단위계(10-17~). `detected=false` 면 기본값이다 — 그 구분은 summary.unit_system 에 남긴다.
            "unit_system": (data.get("unit_system") or {}).get("id") if isinstance(data.get("unit_system"), dict) else None,
        },
        "parts": parts,
        "findings": _norm_findings(data.get("findings")),
        "summary": _sphere_summary(data, cases, parts_in),
        "cases": cases,
    }


def _sphere_summary(data: dict, cases: list, parts_in: dict) -> dict:
    """스터디 전역 롤업: 전체 최악 응력/G/변위와 그게 난 각도."""
    worst_stress = {"value": None, "case_key": None, "part_id": None}
    worst_g = {"value": None, "case_key": None, "part_id": None}
    for c in cases:
        for pid, m in c["parts_metrics"].items():
            s = m.get("peak_stress")
            if s is not None and (worst_stress["value"] is None or s > worst_stress["value"]):
                worst_stress = {"value": s, "case_key": c["case_key"], "part_id": _to_int(pid)}
            g = m.get("peak_g")
            if g is not None and (worst_g["value"] is None or g > worst_g["value"]):
                worst_g = {"value": g, "case_key": c["case_key"], "part_id": _to_int(pid)}
    return {
        "total_runs": data.get("total_runs"),
        "successful_runs": data.get("successful_runs"),
        "failed_runs": data.get("failed_runs"),
        "angular_spacing_deg": _num(data.get("angular_spacing_deg")),
        "sphere_coverage": _num(data.get("sphere_coverage")),
        "worst_stress": worst_stress,
        "worst_g": worst_g,
        "n_findings": len(data.get("findings") or []),
        # 단위계 — peak-G 가 어느 환산으로 나왔나. `detected=false` 면 기본 환산이고 `note` 가 사유다(생성기 값 그대로).
        "unit_system": data.get("unit_system") if isinstance(data.get("unit_system"), dict) else None,
        # 각도 런을 분석한 unified_analyzer 빌드 {커밋: 런 수} — 여럿이면 캠페인이 **섞인 판**으로 분석됐다.
        "analyzer_builds": data.get("tool_builds") if isinstance(data.get("tool_builds"), dict) else None,
    }


# ── impact 정규화 ────────────────────────────────────────────────────
def normalize_impact(data: dict) -> dict:
    """전위치 부분충격(F1~F6 × XY 그리드). 케이스=충격 위치(pos_id).

    임베드 payload 는 결과를 평탄한 ``results[]`` 로 담고, 각 행이
    (face, pos_id, x, y, part_id, g/s/e/d[, s1/s3/e1/e3/evm]) 이다. pos_id 로 묶어
    위치별 케이스를 만들고, 파트별 메트릭 약어를 공통 스키마로 편다.
    """
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    kpi = data.get("kpi") if isinstance(data.get("kpi"), dict) else {}
    sim_params_in = meta.get("sim_params") if isinstance(meta.get("sim_params"), dict) else {}
    impactor = meta.get("impactor") if isinstance(meta.get("impactor"), dict) else {}

    # impact parts 는 리스트가 정상이나, 잘못된 kind 힌트로 dict 가 들어와도 죽지 않게 방어.
    parts_raw = data.get("parts")
    if isinstance(parts_raw, dict):
        parts_raw = list(parts_raw.values())
    elif not isinstance(parts_raw, list):
        parts_raw = []
    parts = []
    for p in parts_raw:
        if not isinstance(p, dict):
            continue
        name = p.get("name") or f"Part_{p.get('id')}"
        parts.append({"part_id": _to_int(p.get("id")), "name": name, "group": p.get("group") or _group_of(name)})

    by_pos: dict[str, dict] = {}
    for row in data.get("results") or []:
        if not isinstance(row, dict):
            continue
        pos_id = row.get("pos_id")
        if pos_id is None:
            continue
        c = by_pos.get(pos_id)
        if c is None:
            c = by_pos[pos_id] = {
                "case_key": pos_id,
                "identity": {
                    "face": row.get("face"),
                    "pos_id": pos_id,
                    "pos_x": _num(row.get("x")),
                    "pos_y": _num(row.get("y")),
                },
                "meta": {"success": True},
                "parts_metrics": {},
            }
        pid = row.get("part_id")
        c["parts_metrics"][str(pid)] = {
            "peak_stress": _num(row.get("s")),
            "peak_strain": _num(row.get("e")),
            "peak_g": _num(row.get("g")),
            "peak_disp": _num(row.get("d")),
            "peak_principal": _num(row.get("s1")),
            "min_principal": _num(row.get("s3")),
            "peak_principal_strain": _num(row.get("e1")),
            "min_principal_strain": _num(row.get("e3")),
            "peak_vm_strain": _num(row.get("evm")),
        }

    cases = []
    for c in by_pos.values():
        c["rollup"] = _case_rollup(c["parts_metrics"])
        cases.append(c)

    return {
        "kind": "impact",
        "source": {
            "generator": data.get("generated_by") or "koo_impact_report",
            "generator_version": None,
            "schema": None,
            "ingested_from": "html",
        },
        "project": {
            "name": meta.get("project"),
            "doe_strategy": meta.get("generation_mode"),
            "test_dir": meta.get("test_dir"),
        },
        "sim_params": {
            "t_final": _num(sim_params_in.get("t_final") or sim_params_in.get("tFinal")),
            "dt": _num(sim_params_in.get("dt")),
            "yield_stress": _num(kpi.get("stress_limit")),
            "unit_system": (data.get("unit_labels") or {}).get("unit_system")
            if isinstance(data.get("unit_labels"), dict) else None,
            "impactor": {
                "type": impactor.get("type"),
                "mass": _num(impactor.get("mass")),
                "velocity": _num(impactor.get("velocity")),
                "kinetic_energy": _num(impactor.get("kinetic_energy")),
            },
        },
        "parts": parts,
        "findings": _norm_findings(data.get("findings")),
        "summary": _impact_summary(kpi, cases),
        "cases": cases,
    }


def _impact_summary(kpi: dict, cases: list) -> dict:
    worst = kpi.get("worst") or {}
    return {
        "n_positions": kpi.get("n_positions"),
        "n_faces": kpi.get("n_faces"),
        "n_parts": kpi.get("n_parts"),
        "n_pairs": kpi.get("n_pairs"),
        "n_valid_runs": kpi.get("n_valid_runs"),
        "n_critical": kpi.get("n_critical"),
        "diss_pct": _num(kpi.get("diss_pct")),
        "worst_g": {
            "value": _num(kpi.get("worst_g")),
            "case_key": worst.get("pos_id"),
            "face": worst.get("face"),
            "part_name": worst.get("part_name"),
        },
        "worst_stress": {"value": _num(kpi.get("worst_s")), "case_key": None, "part_id": None},
        "crit_threshold": _num(kpi.get("crit_threshold")),
        "warn_threshold": _num(kpi.get("warn_threshold")),
    }


# ── 공통 케이스 롤업 ─────────────────────────────────────────────────
def _case_rollup(parts_metrics: dict) -> dict:
    """케이스 내 파트들에 대한 승격용 스칼라(랭킹 정렬 컬럼 소스)."""
    stresses = [m.get("peak_stress") for m in parts_metrics.values()]
    gs = [m.get("peak_g") for m in parts_metrics.values()]
    disps = [m.get("peak_disp") for m in parts_metrics.values()]
    sfs = [m.get("safety_factor") for m in parts_metrics.values()]
    return {
        "max_stress": _max_notnone(stresses),
        "max_g": _max_notnone(gs),
        "max_disp": _max_notnone(disps),
        "min_safety_factor": _min_notnone(sfs),
    }


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return v


# ── 진입점 ───────────────────────────────────────────────────────────
_NORMALIZERS = {
    "deep": normalize_deep,
    "sphere": normalize_sphere,
    "impact": normalize_impact,
}


def _normalize(data: dict, kind: str) -> dict:
    """kind 노멀라이저 실행. 모양 불일치(잘못된 kind 힌트 등)로 인한 예외는
    ReportParseError 로 감싸 상위에서 400 으로 흐르게 한다(500 방지)."""
    if kind not in _NORMALIZERS:
        raise ReportParseError(f"지원하지 않는 kind: {kind}")
    try:
        return _NORMALIZERS[kind](data)
    except ReportParseError:
        raise
    except Exception as exc:  # noqa: BLE001 — 모양 불일치를 사용자 입력 오류로 취급
        raise ReportParseError(
            f"'{kind}' 정규화 실패 — kind 힌트가 리포트 종류와 맞지 않을 수 있습니다 ({type(exc).__name__})."
        ) from exc


def parse_html(html: str, *, kind_hint: str | None = None) -> dict:
    """리포트 HTML → 공통 정규화 스터디 dict. kind_hint 로 자동판별을 덮어쓸 수 있다."""
    data = extract_embedded_data(html)
    return _normalize(data, kind_hint or detect_kind(data))


def parse_data(data: dict, *, kind_hint: str | None = None) -> dict:
    """이미 파싱된 임베드/사이드카 dict → 공통 정규화 스터디 dict."""
    return _normalize(data, kind_hint or detect_kind(data))


# ── 심화 추출기(원본 HTML 재파싱용) ─────────────────────────────────
# DB 엔 요약·케이스 스칼라만 저장하므로, 에너지 밸런스·접촉·시계열 같은 상세는
# 원본 HTML 을 다시 파싱해 필요할 때만 뽑는다.

def case_energy(data: dict, kind: str, case_key: str | None = None) -> dict:
    """케이스의 에너지/접촉 상세.

    deep: glstat 에너지 밸런스 + 접촉력(rcforc) + contact_metrics(있으면).
    sphere/impact: energy_flows[case_key] 하중경로 그래프(있으면).
    """
    if kind == "deep":
        g = data.get("glstat") or {}
        b = data.get("binout") or {}
        rc = [
            {"id": c.get("id"), "name": c.get("name"), "side": c.get("side"),
             "peak_fmag": _num(c.get("peak_fmag"))}
            for c in (b.get("rcforc") or [])
        ]
        return {
            "kind": "deep",
            "energy_balance": {
                "energy_ratio_min": _num(g.get("energy_ratio_min")),
                "energy_ratio_max": _num(g.get("energy_ratio_max")),
                "has_mass_added": g.get("has_mass_added"),
                "normal_termination": g.get("normal_termination"),
            },
            "energy_series": {
                k: g.get(k) for k in
                ("t", "total_energy", "kinetic_energy", "internal_energy",
                 "hourglass_energy", "energy_ratio")
                if g.get(k) is not None
            },
            "contacts": sorted(rc, key=lambda c: (c["peak_fmag"] is None, -(c["peak_fmag"] or 0))),
            "contact_metrics": data.get("contact_metrics"),
            "has_matsum": bool(b.get("matsum")),
        }
    # sphere/impact — 각 케이스별 에너지 플로우 그래프.
    flows = data.get("energy_flows") or {}
    detail_note = data.get("energy_flows_note") or None
    base = {"kind": kind, "case_key": case_key, **({"detail_note": detail_note} if detail_note else {})}
    if not isinstance(flows, dict) or not flows:
        return {**base, "energy_flow": None, "flow_case_key": None, "n_flows": 0,
                "note": "이 리포트엔 에너지 플로우 데이터가 없습니다."}
    if case_key:
        flow = flows.get(case_key)
        if not isinstance(flow, dict):
            # ★다른 케이스로 떨어지지 않는다 — 예전엔 첫 흐름을 **이 케이스 이름으로** 돌려줬다(조용히 틀린 값).
            #   생성기는 상세(시계열)를 접촉력이 큰 상위 케이스에만 싣는다(`energy_flows_note`).
            return {**base, "energy_flow": None, "flow_case_key": None, "n_flows": len(flows),
                    "available_case_keys": sorted(flows)[:200],
                    "note": "이 케이스엔 하중경로 상세가 없습니다 — "
                            + (detail_note or "상세는 일부 케이스에만 실린다")
                            + " 전 케이스의 파트쌍 접촉력은 contact_profile 에 있다."}
        used = case_key
    else:
        # 케이스를 안 주면 대표 하나 — **어느 케이스인지 반드시 적는다**(flow_case_key).
        used = next(iter(flows))
        flow = flows[used]
        if not isinstance(flow, dict):
            return {**base, "energy_flow": None, "flow_case_key": None, "n_flows": len(flows),
                    "note": "하중경로 꼴을 읽지 못했습니다."}
    return {**base, "flow_case_key": used, "n_flows": len(flows), "energy_flow": normalize_flow(flow)}


# ── 하중경로(energy_flows) 두 꼴 ─────────────────────────────────────────────
#
# 생성기의 **중립** 꼴(`koo_deep_report/core/energy_flow_builder.build_flow_graph` — JSON 사이드카)과 HTML 에
# 싣는 **압축** 꼴(`_compact_energy_flows` — sphere·impact 생성기 둘 다)은 키 이름이 다르다.
#   중립       : impactor_ke_initial · nodes[node_id, peak_ke, peak_ie, final_*] · edges[peak_force, total_work,
#                total_impulse, confidence, first_engage_t, contact_id] · propagation_order
#   sphere 압축: ke_init · ke_final · dissipated · t · nodes[id, name, ke[], ie[]] · edges[pf, tw, ti, cid, f[], fei]
#   impact 압축: (위와 같은 흐름 키 + propagation_order · depth_map · contact_*) · edges[peak_f, total_w, total_imp,
#                conf, cid, f[], w[], imp[], t[]] — **엣지 이름이 sphere 와 또 다르다**(실측)
# ⚠ 예전엔 중립 이름만 읽어 HTML 로 들어온 리포트의 접촉력·일·운동에너지가 **전부 null** 이었다(2026-10-23 실측 —
#   sphere·impact 둘 다 HTML 은 압축 꼴이다).
# ★압축본의 `ke`/`ie` 는 **솎은** 시계열이다. 생성기 규칙 — 「시계열 요약은 항상 원해상도 선계산」 — 이라 그 위의
#   max 는 참피크를 놓친다. 피크를 다시 재지 않고 null 로 두고 까닭을 적는다.

def _first(d: dict, *keys):
    for k in keys:
        if d.get(k) is not None:
            return d[k]
    return None


def _flow_form(flow: dict) -> str:
    if any(k in flow for k in ("ke_init", "ke_final", "dissipated")):
        return "html_compact"
    e0 = next((e for e in flow.get("edges") or [] if isinstance(e, dict)), None)
    if e0 is not None and ("pf" in e0 or "peak_f" in e0) and "peak_force" not in e0:
        return "html_compact"
    n0 = next((n for n in flow.get("nodes") or [] if isinstance(n, dict)), None)
    if n0 is not None and "id" in n0 and "node_id" not in n0:
        return "html_compact"
    return "neutral"


def normalize_flow(flow: dict) -> dict:
    """하중경로 하나를 한 꼴로 — 중립·압축 어느 쪽이 와도 같은 이름으로 낸다(없는 값은 null + 까닭)."""
    form = _flow_form(flow)
    nodes = []
    for n in flow.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        nodes.append({
            "node_id": _first(n, "node_id", "id"),
            "name": n.get("name"),
            "is_impactor": bool(n.get("is_impactor")),
            "peak_ke": _num(n.get("peak_ke")), "peak_ie": _num(n.get("peak_ie")),
            "final_ke": _num(n.get("final_ke")), "final_ie": _num(n.get("final_ie")),
        })
    edges = []
    for e in flow.get("edges") or []:
        if not isinstance(e, dict):
            continue
        edges.append({
            "src": e.get("src"), "dst": e.get("dst"), "name": e.get("name"),
            "contact_id": _first(e, "contact_id", "cid"),
            "peak_force": _num(_first(e, "peak_force", "pf", "peak_f")),
            "total_work": _num(_first(e, "total_work", "tw", "total_w")),
            "total_impulse": _num(_first(e, "total_impulse", "ti", "total_imp")),
            "confidence": _num(_first(e, "confidence", "conf")),
            "first_engage_idx": _first(e, "first_engage_idx", "fei"),
            "first_engage_t": _num(e.get("first_engage_t")),
        })
    out = {
        "form": form,
        "impactor_ke_initial": _num(_first(flow, "impactor_ke_initial", "ke_init")),
        "impactor_ke_final": _num(_first(flow, "impactor_ke_final", "ke_final")),
        "energy_dissipated": _num(_first(flow, "energy_dissipated", "dissipated")),
        "propagation_order": flow.get("propagation_order"),
        "nodes": nodes,
        "edges": edges,
    }
    if form == "html_compact":
        # 실제로 빠진 칸만 적는다 — 생성기마다 압축 꼴이 다르다(impact 는 confidence·전파 순서를 싣는다).
        missing = []
        if all(n["peak_ke"] is None and n["peak_ie"] is None for n in nodes):
            missing.append("노드의 원해상도 피크(peak_ke·peak_ie·final_*)")
        if edges and all(e["confidence"] is None for e in edges):
            missing.append("엣지 confidence")
        if edges and all(e["first_engage_t"] is None for e in edges):
            missing.append("first_engage_t")
        if flow.get("propagation_order") is None:
            missing.append("전파 순서")
        out["form_note"] = ("HTML 압축본이다" + (" — " + " · ".join(missing) + " 가 실려 있지 않아 null 이다"
                                                  "(솎은 시계열로 다시 재지 않는다)" if missing else "")
                            + (". first_engage_idx 는 솎은 시간축의 인덱스다." if any(
                                e["first_engage_idx"] is not None for e in edges) else "."))
    # impact 압축본이 함께 싣는 접촉 계측 요약(contact_available·contact_checks…) — 버리지 않는다.
    contact = {k[len("contact_"):]: flow[k] for k in flow if k.startswith("contact_")}
    if contact:
        out["contact"] = contact
    if isinstance(flow.get("depth_map"), dict):
        out["depth_map"] = flow["depth_map"]
    return out


def extract_geometry(data: dict, kind: str) -> dict:
    """공간 컨텍스트(부품 위치 시각화용) — impact 는 디바이스 외곽선 + 파트 footprint(XY),
    sphere/deep 은 각도 기반이라 부품 위치는 원본 렌더에만 있다(빈 값 반환).

    impact HTML DATA 의 device_outline/device_bbox/parts[].footprint 를 그대로 추린다.
    """
    if kind != "impact":
        return {"kind": kind, "device_outline": None, "device_bbox": None, "parts": []}
    outline = data.get("device_outline")
    if not isinstance(outline, list):
        outline = None
    bbox = data.get("device_bbox") if isinstance(data.get("device_bbox"), dict) else None
    parts = []
    for p in data.get("parts") or []:
        if not isinstance(p, dict):
            continue
        fp = p.get("footprint")
        # ★`_synthetic_footprint` 를 **떼지 않는다.** 상류 생성기(`koo_impact_report`)는 실제
        # footprint 가 없는 파트에 **파트 id 해시로 사각형을 지어내고**(황금비 각 + 해시 반지름,
        # `report/payload/__init__.py`) 이 플래그를 달고 자기 HTML 에 "SYNTHETIC FOOTPRINTS
        # n/전체" 배지를 띄운다. 여기서 플래그를 떼면 DynaForge 는 **지어낸 사각형을 실측 외곽선
        # 처럼** 내려준다 — 실측으로 유일한 impact 픽스처에서 **25/25 파트가 합성**이었고
        # zmin/zmax 도 전부 None 이다. 그림이 조용히 거짓이 되는 자리다.
        parts.append({
            "part_id": _to_int(p.get("id")),
            "name": p.get("name"),
            "group": p.get("group"),
            "footprint": fp if isinstance(fp, list) else None,
            "synthetic_footprint": bool(p.get("_synthetic_footprint")),
            "zmin": _num(p.get("zmin")),
            "zmax": _num(p.get("zmax")),
        })
    syn = sum(1 for p in parts if p["synthetic_footprint"])
    return {
        "kind": "impact", "device_outline": outline, "device_bbox": bbox, "parts": parts,
        # 한눈에 보이는 요약 — 파트 표를 다 훑지 않아도 "이 외곽선을 믿어도 되나" 를 알 수 있다.
        "synthetic_footprints": syn,
        "footprints_are_measured": syn == 0,
        **({"footprint_warning":
            "파트 %d/%d 의 footprint 는 상류 생성기가 **파트 id 해시로 지어낸 사각형**이다"
            "(실측 형상이 아니다). 부품 위치·크기로 쓰면 안 된다." % (syn, len(parts))}
           if syn else {}),
    }


def _ts_with_max(ts: dict | None, alt_key: str) -> dict | None:
    """시계열에 표준 'max' 키가 없으면 대체 값키(alt_key)로 별칭을 얹는다.
    (구버전 리포트: g_ts→'g', disp_ts→'mag'. 신버전은 'max' 를 이미 가짐)."""
    if not isinstance(ts, dict):
        return ts
    if "max" not in ts and alt_key in ts:
        return {**ts, "max": ts[alt_key]}
    return ts


def part_series(data: dict, kind: str, case_key: str, part_id: int) -> dict:
    """한 케이스·한 파트의 시계열(다운샘플). DB 미저장분을 원본에서 복원."""
    pid = str(part_id)
    if kind == "deep":
        # ⚠ 전에는 `stress` **하나만** 읽었다. 같은 모양의 배열이 일곱 개인데 여섯이 끊겨
        #   주응력·주변형·변형 **시계열**이 어디에도 도달하지 않았다(피크값만 살아 있었다).
        #   실측: `max_principal`·`min_principal`·`max_principal_strain`·
        #   `min_principal_strain`·`strain`·`vm_strain` 이 리포트에 있는데 버려졌다.
        out: dict = {"kind": "deep", "part_id": part_id, "stress": {}, "motion": {},
                     "series_blocks": []}
        for block in DEEP_SERIES_BLOCKS:
            entries = data.get(block)
            if not isinstance(entries, list) or not entries:
                continue
            bucket = {}
            for entry in entries:
                if not isinstance(entry, dict) or str(entry.get("part_id")) != pid:
                    continue
                bucket[entry.get("quantity") or block] = {
                    "t": entry.get("t"), "max": entry.get("max_vals"), "avg": entry.get("avg_vals"),
                    "global_max": _num(entry.get("global_max")),
                    "global_min": _num(entry.get("global_min")),
                    "time_of_max": _num(entry.get("time_of_max")),
                    "unit": entry.get("unit"),
                }
            if not bucket:
                continue
            out["series_blocks"].append(block)
            # `stress` 는 종전 소비자가 그 자리를 쓰므로 모양을 유지한다(하위 호환).
            if block == "stress":
                out["stress"] = bucket
            else:
                out[block] = bucket
        m = (data.get("motion") or {}).get(pid)
        if isinstance(m, dict):
            out["motion"] = {k: m.get(k) for k in ("t", "disp_mag", "vel_mag", "acc_mag") if m.get(k) is not None}
        return out
    if kind == "sphere":
        for r in data.get("results") or []:
            if (r.get("folder") or (r.get("angle") or {}).get("name")) == case_key:
                p = (r.get("parts") or {}).get(pid) or {}
                # g_ts 는 값키가 'g', disp_ts 는 'mag' 라 표준 'max' 별칭을 얹는다(소비자 일관).
                return {"kind": "sphere", "case_key": case_key, "part_id": part_id,
                        "stress_ts": p.get("stress_ts"), "strain_ts": p.get("strain_ts"),
                        "g_ts": _ts_with_max(p.get("g_ts"), "g"),
                        "disp_ts": _ts_with_max(p.get("disp_ts"), "mag"),
                        "acc_ts": p.get("acc_ts")}
        return {"kind": "sphere", "case_key": case_key, "part_id": part_id, "note": "케이스를 찾지 못함"}
    # impact — 평탄 results 행에서 (pos_id, part_id) 매칭.
    for row in data.get("results") or []:
        if row.get("pos_id") == case_key and str(row.get("part_id")) == pid:
            return {"kind": "impact", "case_key": case_key, "part_id": part_id,
                    "stress_ts": row.get("stress_ts")}
    return {"kind": "impact", "case_key": case_key, "part_id": part_id, "note": "케이스/파트를 찾지 못함"}


def part_energy_series(data: dict, kind: str, part_id: int | None = None) -> dict:
    """파트별 에너지(내부/운동) 시계열 — deep 리포트의 binout matsum(있을 때).

    LS-DYNA matsum 이 덤프된 deep run 이면 파트별 IE/KE(+hourglass) 시간이력이 리포트에
    임베드된다(part_ids/part_names/t/internal_energy/kinetic_energy). part_id 지정 시 그
    파트만. sphere/impact 는 파트별 에너지 시계열이 리포트에 없다(글로벌 에너지·하중경로만).
    """
    if kind != "deep":
        return {"kind": kind, "part_id": part_id, "parts": [],
                "note": "파트별 에너지 시계열은 deep 리포트(matsum)에서만 제공됩니다 — "
                        "sphere/impact 는 글로벌 에너지·하중경로 그래프만 있습니다."}
    binout = data.get("binout")
    ms = binout.get("matsum") if isinstance(binout, dict) else None
    if not isinstance(ms, dict):
        return {"kind": "deep", "part_id": part_id, "t": None, "parts": [],
                "note": "이 리포트엔 matsum(파트별 에너지)이 없습니다 — LS-DYNA run 이 matsum 을 "
                        "덤프해야 파트별 에너지 시계열이 담깁니다."}
    t = ms.get("t") or []
    pids = ms.get("part_ids") or []
    names = ms.get("part_names") or []

    def _per_part(mat):
        # 임베드는 파트-메이저([n_parts][n_times]) 의도. [n_times][n_parts] 로 오면 전치.
        if not isinstance(mat, list) or not mat:
            return []
        if len(mat) != len(pids) and t and len(mat) == len(t):
            return [list(col) for col in zip(*mat)]
        return mat

    ie, ke, hg = _per_part(ms.get("internal_energy")), _per_part(ms.get("kinetic_energy")), _per_part(ms.get("hourglass_energy"))

    def _series(rows, i):
        s = rows[i] if i < len(rows) else None
        return [_num(x) for x in s] if isinstance(s, list) else None

    def _peak(s):
        vals = [x for x in (s or []) if isinstance(x, (int, float))]
        return max(vals) if vals else None

    parts = []
    for i, pid in enumerate(pids):
        s_ie, s_ke, s_hg = _series(ie, i), _series(ke, i), _series(hg, i)
        row = {"part_id": _to_int(pid), "part_name": names[i] if i < len(names) else None,
               "internal_energy": s_ie, "kinetic_energy": s_ke,
               "peak_internal_energy": _peak(s_ie), "peak_kinetic_energy": _peak(s_ke)}
        if s_hg is not None:
            row["hourglass_energy"] = s_hg
        parts.append(row)
    if part_id is not None:
        parts = [p for p in parts if p["part_id"] == part_id]
    return {"kind": "deep", "t": [_num(x) for x in t], "parts": parts,
            "note": None if parts else "matsum 에서 해당 파트를 찾지 못했습니다."}


# ── 스캐터링/섭동 분석 (sphere 전용) ────────────────────────────────
# 26면 낙하 주변의 방향 섭동에 대한 응답 산포. 케이스를 최근접 26 정준방향으로 묶어
# 방향별 통계(mean/std/CoV/최악)와 민감도를 낸다. sphere 리포트에서 도출한다.
# ── 결과 이미지 매핑 ─────────────────────────────────────────────────────────
#
# 결과 이미지는 HTML 안에 임베드되지 **않는다** — 옆에 딸린 파일이다(`app/reports/bundle.py`).
# 그 파일을 **어느 케이스의 그림인지** 아는 정본은 리포트 자신의 구조다.
#
#   impact: `set_report.media[set_i][pos_i] = {png, mp4}`
#           ↔ `set_report.positions[pos_i].id`(케이스) · `set_report.sets[set_i]`(세트)
#
# ⚠ 실측 — 25 위치 중 **8 개만** 미디어가 있고 나머지 17 항목은 **빈 항목**(null)이다
#   (리포트 자신도 `note: "세트 산출물이 있는 위치: 8 / 25."` 로 적는다). 빈 항목을 건너뛰지
#   않으면 그림이 없는 위치에 그림이 있다고 말하게 된다.
#
# ⚠ deep 리포트에는 이 매핑이 **없다**. 그 그림은 형제 `custom_report/` 안에 있고 별개
#   산출물이다. 그래서 deep 번들의 미디어는 **매핑 없이** 목록만 낸다 — 파일명 규칙으로
#   케이스를 **추측하지 않는다**(추측한 매핑은 틀려도 그럴듯해 보인다).

def report_media_map(data: dict, kind: str) -> dict:
    """리포트가 선언한 (미디어 경로 → 케이스·세트) 매핑. 선언이 없으면 빈 매핑.

    반환 `{"declared": [...], "n_declared", "n_empty_slots", "note", "mapped_by"}`
    """
    out = {"declared": [], "n_declared": 0, "n_empty_slots": 0,
           "mapped_by": None, "note": None}
    if kind != "impact":
        out["note"] = ("이 리포트 종류는 미디어 매핑을 선언하지 않는다 — 번들에 들어온 그림은 "
                       "케이스에 묶지 않고 목록으로만 낸다(파일명으로 추측하지 않는다)")
        return out
    sr = data.get("set_report")
    if not isinstance(sr, dict):
        out["note"] = "`set_report` 가 없다 — 선언된 미디어가 없다"
        return out
    media = sr.get("media")
    positions = sr.get("positions") or []
    sets = sr.get("sets") or []
    if not isinstance(media, list):
        out["note"] = "`set_report.media` 가 없다"
        return out
    out["mapped_by"] = "set_report.media[set][position]"
    for si, per_set in enumerate(media):
        if not isinstance(per_set, list):
            continue
        sinfo = sets[si] if si < len(sets) and isinstance(sets[si], dict) else {}
        for pi, ent in enumerate(per_set):
            # ★빈 항목 — 그 위치는 그림이 **없다**. 건너뛰되 센다.
            if not isinstance(ent, dict) or not (ent.get("png") or ent.get("mp4")):
                out["n_empty_slots"] += 1
                continue
            pinfo = positions[pi] if pi < len(positions) and isinstance(positions[pi], dict) else {}
            case_key = pinfo.get("id")
            for role, path in (("peak", ent.get("png")), ("view", ent.get("mp4"))):
                if not path:
                    continue
                out["declared"].append({
                    "path": path,
                    "case_key": case_key,
                    "set_index": si,
                    "set_name": sinfo.get("name"),
                    "set_title": sinfo.get("title"),
                    "role": role,
                    "kind": "image" if role == "peak" else "video",
                    "face": pinfo.get("face"),
                    "x": _num(pinfo.get("x")), "y": _num(pinfo.get("y")),
                })
    out["n_declared"] = len(out["declared"])
    if sr.get("note"):
        out["generator_note"] = sr["note"]
    return out


# ── 큰 분석 블록 요약 ────────────────────────────────────────────────────────
#
# `doe_analysis`(하위 14) · `deep_analytics`(6) · `insights`(6) · `physics`(4) ·
# `solver_quality`(2) 는 꺼낼 수는 있어도 그대로는 쓰기 어렵다. 그래서 요약을 얹는다.
#
# ★요약을 **내가 다시 계산하지 않는다.** 하위 분석은 거의 모두 생성기가 계산한 `summary` 를
#   들고 있고(실측), 그것이 HTML 화면과 같은 숫자다. 내가 per_position 을 다시 집계하면 그
#   숫자가 화면과 **조용히 갈릴** 수 있다 — 이 리포가 사본 문제로 이미 여러 번 치른 값이다.
#   그래서 `summary` 는 **그대로 올리고**, 상세는 **형태만** 적는다(원본은 `/blocks` 로).
#
# ★`available=false` · `empty=true` 를 **크게** 적는다. 그 플래그를 빼고 요약만 내면 받는 쪽이
#   "계산됐는데 값이 0" 으로 읽는다 — 사실은 **계산되지 않았다**.

#: 요약 대상 블록. 생성기가 늘리면 여기 한 줄 더한다(그리고 `list_blocks` 가 늘 전수를 본다).
ANALYTICS_BLOCKS = ("doe_analysis", "deep_analytics", "insights", "physics",
                    "solver_quality", "contact_profile", "set_report")

#: "계산되지 않았다" 를 뜻하는 플래그 — 이름만 보고 뜻을 뒤집지 않도록 둘을 나눠 적는다.
_NEGATIVE_FLAGS = {"empty": True, "available": False, "ok": False, "is_mock": True}


def _sub_shape(v) -> dict:
    if isinstance(v, dict):
        return {"type": "object", "count": len(v), "keys": sorted(v)[:24]}
    if isinstance(v, list):
        return {"type": "array", "count": len(v),
                "keys": sorted(v[0])[:24] if v and isinstance(v[0], dict) else []}
    return {"type": type(v).__name__, "value": v if isinstance(v, (int, float, str, bool)) else None}


def _summarize_sub(name: str, v) -> dict:
    """하위 분석 하나 — 생성기의 `summary` 는 그대로, 나머지는 형태만."""
    if not isinstance(v, dict):
        return {"name": name, "shape": _sub_shape(v)}
    out: dict = {"name": name}
    caveats = []
    for flag, bad in _NEGATIVE_FLAGS.items():
        if flag in v and bool(v[flag]) is bad:
            caveats.append(flag)
    if caveats:
        out["not_computed"] = caveats
        out["not_computed_note"] = ("%s — 이 분석은 **계산되지 않았다**(값이 0 인 것이 아니다)"
                                    % ", ".join("%s=%s" % (f, v.get(f)) for f in caveats))
    if isinstance(v.get("summary"), (dict, list)):
        out["summary"] = v["summary"]          # ★생성기 값 그대로 — 다시 계산하지 않는다
    # 요약 밖의 쓸모 있는 스칼라·소형 dict 는 같이 올린다(큰 것은 형태만).
    detail = {}
    for k, sv in v.items():
        if k in ("summary",) or k in _NEGATIVE_FLAGS:
            continue
        if isinstance(sv, (int, float, str, bool)) or sv is None:
            out.setdefault("values", {})[k] = sv
        elif isinstance(sv, (dict, list)) and _rough_bytes(sv) <= 1200:
            out.setdefault("values", {})[k] = sv
        else:
            detail[k] = _sub_shape(sv)
    if detail:
        out["detail_shape"] = detail
    return out


def analytics_summary(data: dict, block: str | None = None) -> dict:
    """큰 분석 블록의 요약 — 하위 분석별 `summary` + 상세의 형태.

    원본은 가리지 않는다: 같은 데이터를 `get_block(name, path=…)` 로 끝까지 꺼낼 수 있다.
    """
    names = [block] if block else list(ANALYTICS_BLOCKS)
    out: dict = {"blocks": [], "requested": block,
                 "raw_access_note": "원본은 `/blocks/{name}` (path= 로 하위 선택)로 꺼낸다"}
    for name in names:
        v = data.get(name)
        if v is None:
            out["blocks"].append({"name": name, "available": False,
                                  "note": "이 리포트에 없는 블록이다"})
            continue
        entry: dict = {"name": name, "available": True, "bytes": _rough_bytes(v)}
        if isinstance(v, dict):
            entry["subs"] = [_summarize_sub(k, v[k]) for k in sorted(v)]
            entry["n_subs"] = len(entry["subs"])
        else:
            entry["shape"] = _sub_shape(v)
        out["blocks"].append(entry)
    out["n_blocks"] = len(out["blocks"])
    return out


# ── 핫스팟 군집 (deep) ───────────────────────────────────────────────────────
#
# 생성기: `koo_deep_report` 를 `unified_analyzer --hotspot-clusters` 산출물로 돌리면
# `DATA.hotspot` 에 (파트 × 판정기준) 레코드가 실린다. 실측 34파트 × 3기준 = 102 레코드.
#
# 레코드 스칼라 — top_percent(상위 몇 %를 뽑았나) · threshold_value(그 문턱) ·
#   distance_threshold / element_size_ref(군집 묶는 거리) · element_count_{selected,clustered,total} ·
#   direction(max|min) · uniform(값이 고르면 군집이 뜻없다) · bbox_min/max · weight_measure
# 군집 항 — rank · center · radius_enclosing / radius_rms · element_count · volume ·
#   stress_max / stress_mean · strain_max / strain_mean · peak_element_id · peak_time
#
# ★`uniform=true` 는 "값이 고르다" 는 뜻이다 — 그때의 군집은 **핫스팟이 아니다**. 숨기지 않고
#   적어서 내보낸다(숨기면 받는 쪽이 '가장 뜨거운 곳' 으로 읽는다).

_HOTSPOT_ORDERS = ("stress_max", "stress_mean", "volume", "element_count",
                   "radius_enclosing", "rank")


def hotspot_clusters(data: dict, *, criterion: str | None = None,
                     part_id: int | None = None, top: int = 20,
                     order: str = "stress_max", case_key: str | None = None) -> dict:
    """핫스팟 군집 — 평탄화해서 정렬·상한을 둔 목록으로 낸다.

    deep 은 최상위 `hotspot`(파트 × 판정기준 레코드), sphere 는 각도 런마다 `results[i].hotspot`(압축 꼴)이다
    — 꼴을 보고 가른다. sphere 는 `case_key`(각도 런 폴더)로 한 각도만 볼 수 있고, 파트 × 기준마다 가장 센 각도를
    뽑은 `envelope` 를 함께 낸다.
    """
    recs = data.get("hotspot")
    if not (isinstance(recs, list) and recs) and any(
            isinstance(r, dict) and r.get("hotspot") for r in data.get("results") or []):
        return _sphere_hotspots(data, criterion=criterion, part_id=part_id, top=top, order=order,
                                case_key=case_key)
    if not isinstance(recs, list) or not recs:
        return {"available": False, "n_records": 0, "clusters": [],
                "note": "이 리포트에는 핫스팟 군집이 없다 — 생성기를 "
                        "`unified_analyzer --hotspot-clusters` 로 돌려야 실린다"}
    if order not in _HOTSPOT_ORDERS:
        order = "stress_max"

    criteria, parts, flat = set(), set(), []
    n_uniform = 0
    for rec in recs:
        if not isinstance(rec, dict):
            continue
        crit = rec.get("criterion")
        pid = _to_int(rec.get("part_id"))
        criteria.add(crit)
        parts.add(pid)
        if rec.get("uniform"):
            n_uniform += 1
        if criterion and crit != criterion:
            continue
        if part_id is not None and pid != part_id:
            continue
        ctx = {
            "part_id": pid, "part_name": rec.get("part_name"), "criterion": crit,
            "direction": rec.get("direction"), "element_type": rec.get("element_type"),
            # ★군집이 뜻을 갖는 전제들 — 같이 실어 보낸다
            "uniform": bool(rec.get("uniform")),
            "top_percent": _num(rec.get("top_percent")),
            "threshold_value": _num(rec.get("threshold_value")),
            "value_extreme": _num(rec.get("value_extreme")),
            "distance_threshold": _num(rec.get("distance_threshold")),
            "element_size_ref": _num(rec.get("element_size_ref")),
            "element_count_selected": rec.get("element_count_selected"),
            "element_count_clustered": rec.get("element_count_clustered"),
            "element_count_total": rec.get("element_count_total"),
            "bbox_min": rec.get("bbox_min"), "bbox_max": rec.get("bbox_max"),
            "strain_available": bool(rec.get("strain_available")),
            "strain_measure": rec.get("strain_measure"),
            "weight_measure": rec.get("weight_measure"),
        }
        for c in rec.get("clusters") or []:
            if not isinstance(c, dict):
                continue
            flat.append({**ctx,
                         "rank": c.get("rank"),
                         "center": c.get("center"),
                         "radius_enclosing": _num(c.get("radius_enclosing")),
                         "radius_rms": _num(c.get("radius_rms")),
                         "element_count": c.get("element_count"),
                         "volume": _num(c.get("volume")),
                         "stress_max": _num(c.get("stress_max")),
                         "stress_mean": _num(c.get("stress_mean")),
                         "strain_max": _num(c.get("strain_max")),
                         "strain_mean": _num(c.get("strain_mean")),
                         "peak_element_id": c.get("peak_element_id"),
                         "peak_time": _num(c.get("peak_time"))})

    # ⚠ direction=min 인 기준은 값이 **음수**다 — 절대값으로 줄을 세워야 '가장 센 곳' 이 된다.
    def key(x):
        v = x.get(order)
        if v is None:
            return (1, 0.0)
        return (0, -abs(v)) if order in ("stress_max", "stress_mean") else (0, -v)

    flat.sort(key=key)
    total = len(flat)
    shown = flat[: max(0, top)] if top else flat
    out = {
        "available": True,
        "n_records": len(recs),
        "n_clusters": total,
        "criteria": sorted(c for c in criteria if c),
        "parts": sorted(p for p in parts if p is not None),
        "order": order,
        "order_note": "stress_* 는 **절대값** 기준이다 — direction=min 기준의 값은 음수다",
        "filter": {"criterion": criterion, "part_id": part_id},
        "clusters": shown,
    }
    if n_uniform:
        out["uniform_records"] = n_uniform
        out["uniform_note"] = ("값이 고른(uniform) 레코드가 %d 개다 — 그 군집은 '가장 뜨거운 곳' "
                               "이 아니다" % n_uniform)
    if total > len(shown):
        out["truncated"] = {"returned": len(shown), "total": total}
    return out


# ── 핫스팟 군집 (sphere — 각도 런마다) ────────────────────────────────────────
#
# 생성기(`koo_sphere_report`, 10-17~)는 각도 런마다 `results[i].hotspot` 에 (파트 × 판정기준) 항목을 **압축해** 싣는다.
#   항목  : p(part_id) · cr(criterion) · et(element_type, 있을 때) · cl[군집]
#   군집  : c(center) · r(radius_enclosing) · k(rank) · n(element_count) · s(stress_max) — 있을 때만 e(strain_max) ·
#           w(energy_total) · wd(energy_max) · t(peak_time). **없는 값은 키가 없다**(0 으로 채우지 않는다).
# 원형에 있던 volume · stress_mean · peak_element_id · radius_rms 와 레코드 스칼라(uniform · top_percent · threshold …)는
# 압축본에 없다 — **지어내지 않는다.** 군집이 2만 개를 넘으면 생성기가 순위 라운드로빈으로 고르고 `hotspot_cap_note`
# 를 남긴다(전수는 생성기 report.json 의 hotspot_clusters).

_SPHERE_CLUSTER_KEYS = (("c", "center"), ("r", "radius_enclosing"), ("k", "rank"), ("n", "element_count"),
                        ("s", "stress_max"), ("e", "strain_max"), ("w", "energy_total"),
                        ("wd", "energy_max"), ("t", "peak_time"))
_SPHERE_HOTSPOT_ORDERS = ("stress_max", "element_count", "radius_enclosing", "rank",
                          "strain_max", "energy_total", "energy_max")


def _hotspot_sort_key(order: str):
    def key(x):
        v = x.get(order)
        if v is None:
            return (1, 0.0)
        if order == "rank":
            return (0, v)
        return (0, -abs(v)) if order.startswith("stress") else (0, -v)
    return key


def _sphere_hotspots(data: dict, *, criterion: str | None, part_id: int | None, top: int,
                     order: str, case_key: str | None) -> dict:
    results = [r for r in data.get("results") or [] if isinstance(r, dict)]
    runs = [r for r in results if r.get("hotspot")]
    names = {str(k): (v.get("name") if isinstance(v, dict) else None)
             for k, v in (data.get("parts") or {}).items()} if isinstance(data.get("parts"), dict) else {}
    common = {
        "kind": "sphere",
        "n_angles_total": len(results),
        "n_angles_with_clusters": len(runs),
        "hotspot_parts": data.get("hotspot_parts"),
        "mesh_available": isinstance(data.get("hotspot_mesh"), (dict, list)),
        **({"mesh_note": data["hotspot_mesh_note"]} if data.get("hotspot_mesh_note") else {}),
        # 생성기 상한 — 조용히 자른 것처럼 보이지 않게 그대로 올린다
        **({"cap_note": data["hotspot_cap_note"]} if data.get("hotspot_cap_note") else {}),
        "compact_note": ("HTML 압축본이다 — 군집의 volume·stress_mean·peak_element_id 와 레코드의 uniform·top_percent·"
                         "threshold 는 실려 있지 않다. 값이 고른(uniform) 파트의 군집도 섞여 있을 수 있다 — "
                         "원형은 생성기 report.json 의 hotspot_clusters 에 있다."),
    }
    if order not in _SPHERE_HOTSPOT_ORDERS:
        order = "stress_max"
    criteria, parts, flat = set(), set(), []
    n_records = n_all = 0
    env: dict = {}
    for r in runs:
        ck = r.get("folder") or (r.get("angle") or {}).get("name")
        a = r.get("angle") or {}
        angle = {"name": a.get("name"), "roll": _num(a.get("roll")), "pitch": _num(a.get("pitch")),
                 "yaw": _num(a.get("yaw")), "category": a.get("category")}
        for it in r.get("hotspot") or []:
            if not isinstance(it, dict):
                continue
            n_records += 1
            crit = it.get("cr")
            pid = _to_int(it.get("p"))
            criteria.add(crit)
            parts.add(pid)
            for c in it.get("cl") or []:
                if not isinstance(c, dict):
                    continue
                n_all += 1
                row = {"case_key": ck, "angle": angle, "part_id": pid, "part_name": names.get(str(pid)),
                       "criterion": crit, "element_type": it.get("et")}
                for short, full in _SPHERE_CLUSTER_KEYS:
                    v = c.get(short)
                    row[full] = None if v is None else (v if short in ("c", "k", "n") else _num(v))
                if criterion and crit != criterion:
                    continue
                if part_id is not None and pid != part_id:
                    continue
                # 포락 — 각도 필터와 무관하게 전 각도에서 (파트, 기준)마다 가장 센 군집
                e = env.setdefault((pid, crit), {"angles": set(), "worst": None})
                e["angles"].add(ck)
                sv = row["stress_max"]
                if sv is not None and (e["worst"] is None or abs(sv) > abs(e["worst"]["stress_max"])):
                    e["worst"] = row
                if case_key and ck != case_key:
                    continue
                flat.append(row)

    if not runs:
        return {"available": False, "n_records": 0, "clusters": [], **common,
                "note": "이 리포트에는 핫스팟 군집이 없다 — 각도 런의 분석 YAML 에서 `hotspot_clusters` 를 켜야"
                        "(`unified_analyzer --hotspot-clusters`) 실린다"}
    flat.sort(key=_hotspot_sort_key(order))
    total = len(flat)
    shown = flat[: max(0, top)] if top else flat
    envelope = []
    for (pid, crit), e in env.items():
        w = e["worst"]
        envelope.append({
            "part_id": pid, "part_name": names.get(str(pid)), "criterion": crit,
            "n_angles": len(e["angles"]),
            "worst_case_key": w["case_key"] if w else None,
            "worst_angle": w["angle"] if w else None,
            "stress_max": w["stress_max"] if w else None,
            "element_count": w["element_count"] if w else None,
            "radius_enclosing": w["radius_enclosing"] if w else None,
            "center": w["center"] if w else None,
            "peak_time": w["peak_time"] if w else None,
        })
    envelope.sort(key=lambda x: (x["stress_max"] is None, -abs(x["stress_max"] or 0.0)))
    out = {
        "available": True, **common,
        "n_records": n_records,
        "n_clusters": total,
        "n_clusters_all": n_all,
        "criteria": sorted(c for c in criteria if c),
        "parts": sorted(p for p in parts if p is not None),
        "order": order,
        "order_note": "stress_* 는 **절대값** 기준이다 — direction=min 기준의 값은 음수다",
        "filter": {"criterion": criterion, "part_id": part_id, "case_key": case_key},
        "envelope": envelope[: max(0, top)] if top else envelope,
        "envelope_note": "파트 × 기준마다 전 각도에서 가장 센(|응력| 최대) 군집 하나 — n_angles 는 그 파트·기준에"
                         " 군집이 난 각도 수다",
        "clusters": shown,
    }
    if top and len(envelope) > top:
        out["envelope_truncated"] = {"returned": top, "total": len(envelope)}
    if total > len(shown):
        out["truncated"] = {"returned": len(shown), "total": total}
    return out


# ── 파트쌍 × 각도(위치) 접촉 프로파일 (sphere · impact) ───────────────────────
#
# 생성기 계약 — sphere `_contact_profile` 과 impact `build_contact_profile` 이 **같은 꼴**이다(생성기 주석: 「렌더러를
# 공유한다」). pairs[{key, src, dst, cid, name, resolved}] + pf/ti/tw(pairs × 축 행렬). 축은 sphere=`results`(각도) ·
# impact=`positions`(위치) 와 1:1 이다. 그 축에 그 접촉이 없으면 None — **0 이 아니다**('접촉 안 함' ≠ '힘 0').
# resolved=false 는 접촉 정의가 파트로 분해되지 않은 것(single-surface 등)이다 — 파트쌍인 척하지 않는다.
# 스칼라만 담으므로 **전 각도**가 실린다 — 시계열 상세(energy_flows)가 상위 각도만 실리는 것과 다르다.

CONTACT_PROFILE_METRICS = {"pf": "peak_force", "ti": "total_impulse", "tw": "total_work"}


def _profile_axis(data: dict, kind: str) -> list:
    out = []
    if kind == "impact":
        for p in data.get("positions") or []:
            if not isinstance(p, dict):
                continue
            pid = p.get("pos_id")
            out.append({"case_key": None if pid is None else str(pid), "label": None if pid is None else str(pid),
                        "x": _num(p.get("x")), "y": _num(p.get("y")), "face": p.get("face")})
        return out
    for r in data.get("results") or []:
        if not isinstance(r, dict):
            continue
        a = r.get("angle") or {}
        out.append({"case_key": r.get("folder") or a.get("name"), "label": a.get("name"),
                    "roll": _num(a.get("roll")), "pitch": _num(a.get("pitch")), "yaw": _num(a.get("yaw")),
                    "category": a.get("category")})
    return out


def _part_names(data: dict) -> dict:
    parts = data.get("parts")
    if isinstance(parts, dict):
        return {str(k): (v.get("name") if isinstance(v, dict) else None) for k, v in parts.items()}
    if isinstance(parts, list):
        return {str(p.get("id")): p.get("name") for p in parts if isinstance(p, dict) and p.get("id") is not None}
    return {}


def _cell(mat: list, i: int, j: int):
    row = mat[i] if i < len(mat) and isinstance(mat[i], list) else []
    v = row[j] if j < len(row) else None
    return None if v is None else _num(v)


def contact_profile(data: dict, kind: str, *, metric: str = "pf", top: int = 30,
                    case_key: str | None = None, matrix: bool = False,
                    axis_top: int | None = None, max_cells: int = 120_000) -> dict:
    """파트쌍 × 각도(위치) 접촉 스칼라 — 쌍마다 최대(그 각도) · 축마다 가장 센 쌍 · 한 각도의 엣지 · (선택) 행렬.

    `metric` ∈ pf(peak_force) · ti(total_impulse) · tw(total_work). 크기 비교는 **|값|** 이다(tw 는 음수가 있다).
    """
    cp = data.get("contact_profile")
    trust = data.get("contact_trust") if isinstance(data.get("contact_trust"), dict) else None
    base = {"kind": kind, "metric": metric, "metric_name": CONTACT_PROFILE_METRICS.get(metric),
            **({"trust": trust} if trust else {})}
    if metric not in CONTACT_PROFILE_METRICS:
        return {**base, "available": False, "error": "metric 은 pf · ti · tw 중 하나다"}
    if not isinstance(cp, dict) or not cp.get("pairs"):
        return {**base, "available": False,
                "note": "이 리포트에는 파트쌍 접촉 프로파일이 없다 — 생성기가 하중경로(binout 의 matsum·rcforc)를 "
                        "만들지 못하면 비어 있다"}
    axis = _profile_axis(data, kind)
    names = _part_names(data)
    raw_pairs = [pr for pr in cp["pairs"] if isinstance(pr, dict)]
    mats = {m: (cp.get(m) or []) for m in CONTACT_PROFILE_METRICS}
    mat = mats[metric]
    n_axis = len(axis)

    def pair_row(i: int, pr: dict) -> dict:
        src, dst = str(pr.get("src")), str(pr.get("dst"))
        vals = [(j, _cell(mat, i, j)) for j in range(n_axis)]
        vals = [(j, v) for j, v in vals if v is not None]
        pj, pv = max(vals, key=lambda t: abs(t[1])) if vals else (None, None)
        return {"key": pr.get("key"), "src": src, "dst": dst,
                "src_name": names.get(src), "dst_name": names.get(dst),
                "contact_id": pr.get("cid"), "name": pr.get("name"), "resolved": bool(pr.get("resolved")),
                "n_engaged": len(vals), "peak": pv,
                "peak_case_key": axis[pj]["case_key"] if pj is not None else None,
                "peak_label": axis[pj]["label"] if pj is not None else None}

    rows = [pair_row(i, pr) for i, pr in enumerate(raw_pairs)]
    order = sorted(range(len(rows)),
                   key=lambda i: (not rows[i]["resolved"], rows[i]["peak"] is None, -abs(rows[i]["peak"] or 0.0)))
    axis_summary = []
    for j, ax in enumerate(axis):
        best, n_eng = None, 0
        for i in range(len(raw_pairs)):
            v = _cell(mat, i, j)
            if v is None:
                continue
            n_eng += 1
            if best is None or abs(v) > abs(best[1]):
                best = (i, v)
        axis_summary.append({**ax, "n_engaged": n_eng,
                             "top_pair": rows[best[0]]["key"] if best else None,
                             "top_value": best[1] if best else None})
    out = {**base, "available": True,
           "axis_kind": "position" if kind == "impact" else "angle",
           "n_pairs": len(rows), "n_resolved": sum(1 for r in rows if r["resolved"]), "n_axis": n_axis,
           "pairs": [rows[i] for i in order][: max(0, top)] if top else [rows[i] for i in order],
           "note": "None = 그 %s 에 그 접촉이 없다(0 이 아니다) · resolved=false 는 파트로 분해되지 않은 접촉 · "
                   "크기 비교는 |값|" % ("위치" if kind == "impact" else "각도")}
    if top and len(rows) > top:
        out["pairs_truncated"] = {"returned": top, "total": len(rows)}
    if axis_top:
        ranked = sorted(axis_summary, key=lambda a: (a["top_value"] is None, -abs(a["top_value"] or 0.0)))
        out["axis_summary"] = ranked[:axis_top]
        out["axis_summary_note"] = "가장 센 접촉이 큰 %s 상위 %d/%d" % (
            "위치" if kind == "impact" else "각도", min(axis_top, n_axis), n_axis)
    else:
        out["axis_summary"] = axis_summary
    if case_key:
        j = next((k for k, ax in enumerate(axis) if ax["case_key"] == case_key), None)
        if j is None:
            out["at"] = {"case_key": case_key, "found": False, "note": "그 케이스가 축에 없다"}
        else:
            edges = []
            for i, pr in enumerate(raw_pairs):
                vals = {m: _cell(mats[m], i, j) for m in CONTACT_PROFILE_METRICS}
                if all(v is None for v in vals.values()):
                    continue
                r = rows[i]
                edges.append({"key": r["key"], "src": r["src"], "dst": r["dst"], "src_name": r["src_name"],
                              "dst_name": r["dst_name"], "name": r["name"], "resolved": r["resolved"],
                              **{CONTACT_PROFILE_METRICS[m]: v for m, v in vals.items()}})
            edges.sort(key=lambda e: (e["peak_force"] is None, -abs(e["peak_force"] or 0.0)))
            out["at"] = {"case_key": case_key, "found": True, **axis[j], "edges": edges}
    if matrix:
        cells = len(rows) * n_axis
        if cells > max_cells:
            out["matrix"] = None
            out["matrix_note"] = "행렬이 %d 칸이라 상한 %d 을 넘는다 — metric 을 하나로 · axis 를 줄여 다시 청하라" % (
                cells, max_cells)
        else:
            out["matrix"] = {"pairs": [rows[i]["key"] for i in order],
                             "values": [[_cell(mat, i, j) for j in range(n_axis)] for i in order]}
    return out


# ── 거동 군집 (impact) ───────────────────────────────────────────────────────

def behavior_clusters(data: dict) -> dict:
    """impact 리포트의 거동 아키타입 군집 — 위치를 몇 가지 거동으로 묶은 결과.

    ★`is_mock` 을 **그대로 올린다.** 합성 군집을 실측으로 읽으면 결론이 거짓이 된다
    (같은 부류의 사고를 `synthetic_footprint` 에서 이미 치렀다).
    """
    c = data.get("clusters")
    if not isinstance(c, dict) or not c:
        return {"available": False, "note": "이 리포트에는 거동 군집이 없다"}
    arche = c.get("archetypes") or []
    labels = c.get("labels") if isinstance(c.get("labels"), dict) else {}
    members: dict[str, list] = {}
    for pos, idx in labels.items():
        i = _to_int(idx)
        name = arche[i] if isinstance(i, int) and 0 <= i < len(arche) else str(idx)
        members.setdefault(str(name), []).append(pos)
    groups = [{"archetype": k, "index": arche.index(k) if k in arche else None,
               "n_positions": len(v), "positions": sorted(v)}
              for k, v in members.items()]
    groups.sort(key=lambda g: -g["n_positions"])
    out = {
        "available": True,
        "n_clusters": _to_int(c.get("n")),
        "archetypes": arche,
        "features_used": c.get("features_used") or [],
        "n_positions_labeled": len(labels),
        "groups": groups,
    }
    # ★선언한 군집 수와 **실제로 쓰인** 아키타입 수가 다를 수 있다. 실측: n=4 인데 25위치가
    #   전부 한 아키타입(`slow-decay`)이었다 — 군집이 **분리되지 않은** 것이다. 그것을 적지
    #   않으면 받는 쪽이 "거동이 네 가지" 로 읽는다.
    n_used = len(groups)
    out["n_archetypes_used"] = n_used
    if out["n_clusters"] and n_used < out["n_clusters"]:
        out["degenerate"] = True
        out["degenerate_note"] = (
            "선언 %s 군집 중 **실제로 쓰인 것은 %d 개**다 — 거동이 갈리지 않았다는 뜻이고, "
            "'%s' 가지 거동으로 읽으면 안 된다"
            % (out["n_clusters"], n_used, out["n_clusters"]))
    else:
        out["degenerate"] = False

    if c.get("is_mock"):
        out["is_mock"] = True
        out["mock_note"] = ("★이 군집은 **합성(mock)** 이다 — 실측 거동이 아니므로 결론의 "
                            "근거로 쓰지 말라")
    else:
        out["is_mock"] = False
    return out


# ── 일반 블록 접근 ───────────────────────────────────────────────────────────
#
# ★왜 이것이 있나 (2026-10-13). 정규화(`normalize_*`)는 **허용 목록**이다. 생성기가 임베드
# 키를 늘리면 플랫폼은 가만히 있어도 뒤처지고, 뒤처진 것이 **보이지 않는다**(에러도 경고도
# 없다). 실측으로 그 상태였다 — deep 21키 중 11, impact 27키 중 18 이 어디에도 도달하지
# 않았고 그중에 핫스팟 군집 102건과 거동 군집이 있었다.
#
# 그래서 허용 목록을 늘리는 대신 **모든 최상위 블록을 이름으로 꺼낼 수 있게** 한다.
# 원본 HTML 은 이미 보관된다(`ImpactReport.source_file_id` — 온디맨드 재파싱용).

#: 정규화·전용 함수가 **원본에서 읽는** 최상위 키. 이 목록은 `list_blocks` 가
#: `read_by_parser` 를 적는 근거이고, 회귀가 '새 키가 생겼다' 를 알려 주는 기준이다.
#: ⚠ 출력 필드명과 **섞어 세지 말라** — `"min_principal"` 은 `parts_metrics` 의 출력 키이기도
#: 해서, 이름만 grep 하면 읽지도 않는 키가 '읽힘' 으로 세어진다(실측으로 속았다).
PARSER_READS = frozenset({
    # 공통/정규화
    "parts", "findings", "summary", "metadata", "sim", "yield_stress", "meta",
    # sphere
    "results", "sim_params", "project_name", "doe_strategy", "total_runs",
    "successful_runs", "failed_runs", "sphere_coverage", "angular_spacing_deg",
    # deep
    "glstat", "contact_metrics", "binout", "motion", "stress", "test_dir",
    # deep 시계열(DEEP_SERIES_BLOCKS 로 넓혔다)
    "strain", "vm_strain", "max_principal", "min_principal",
    "max_principal_strain", "min_principal_strain",
    # impact
    "kpi", "unit_labels", "generated_by", "device_bbox", "device_outline", "energy_flows",
    # sphere 새 판(10-17~) — 정규화 요약(unit_system · tool_builds) · 하중경로 응답(energy_flows_note) ·
    # 핫스팟 응답(hotspot_parts · hotspot_mesh · hotspot_mesh_note · hotspot_cap_note) · 전용 함수(contact_profile ·
    # contact_trust — impact 도 같은 꼴). 남기는 것(device_mesh 등)은 회귀의 EXPECTED_UNREAD 가 까닭과 함께 고정한다.
    "unit_system", "tool_builds", "energy_flows_note",
    "hotspot_parts", "hotspot_mesh", "hotspot_mesh_note", "hotspot_cap_note",
    "contact_profile", "contact_trust",
    # impact `positions` — contact_profile 의 축(위치)으로 읽는다.
    "positions",
})


def _rough_bytes(v) -> int:
    """직렬화 크기 어림 — 응답을 불리기 전에 재려는 용도다(정확할 필요는 없다)."""
    try:
        return len(json.dumps(v, ensure_ascii=False, default=str))
    except Exception:
        return -1


def _block_shape(v) -> dict:
    if isinstance(v, dict):
        return {"type": "object", "count": len(v), "sub_keys": sorted(v)[:40]}
    if isinstance(v, list):
        first = v[0] if v else None
        return {"type": "array", "count": len(v),
                "sub_keys": sorted(first)[:40] if isinstance(first, dict) else [],
                "item_type": type(first).__name__ if first is not None else None}
    return {"type": type(v).__name__, "count": None, "sub_keys": []}


def list_blocks(data: dict) -> dict:
    """임베드 데이터의 최상위 블록 목록 — 이름·형태·크기·`read_by_parser`.

    `read_by_parser=False` 가 "쓸 수 없다" 는 뜻은 아니다. `get_block` 으로 꺼낼 수 있다.
    그 칸은 **정규화가 아직 해석하지 않는다**는 사실을 숨기지 않기 위해 있다.
    """
    blocks = []
    for name in sorted(data):
        v = data[name]
        sh = _block_shape(v)
        blocks.append({"name": name, **sh,
                       "bytes": _rough_bytes(v),
                       "read_by_parser": name in PARSER_READS})
    return {
        "n_blocks": len(blocks),
        "n_unread": sum(1 for b in blocks if not b["read_by_parser"]),
        "blocks": blocks,
    }


def get_block(data: dict, name: str, path: str | None = None,
              max_bytes: int = 200_000, limit: int | None = None) -> dict:
    """최상위 블록(또는 그 하위 경로)을 꺼낸다.

    `path` 는 `a.b.0.c` 꼴 — dict 키와 list 인덱스를 점으로 잇는다.
    `limit` 는 배열을 앞에서 몇 개만. 크기가 `max_bytes` 를 넘으면 **잘랐다고 말한다** —
    조용히 자르면 받는 쪽이 전체를 본 줄로 안다.
    """
    if name not in data:
        return {"name": name, "found": False,
                "available": sorted(data)[:80],
                "note": "그런 블록이 없다 — list_blocks 로 목록을 보라"}
    cur = data[name]
    walked = []
    for seg in (path or "").split(".") if path else []:
        if seg == "":
            continue
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        elif isinstance(cur, list) and seg.lstrip("-").isdigit() and -len(cur) <= int(seg) < len(cur):
            cur = cur[int(seg)]
        else:
            return {"name": name, "found": False, "path": path, "walked": ".".join(walked),
                    "note": "경로가 끊겼다 — 여기서 쓸 수 있는 키/인덱스: %s"
                            % (sorted(cur)[:30] if isinstance(cur, dict)
                               else ("0..%d" % (len(cur) - 1) if isinstance(cur, list) else "(스칼라)"))}
        walked.append(seg)

    truncated = None
    if isinstance(cur, list) and limit is not None and len(cur) > limit:
        truncated = {"kind": "limit", "returned": limit, "total": len(cur)}
        cur = cur[:limit]
    nbytes = _rough_bytes(cur)
    if nbytes > max_bytes:
        if isinstance(cur, list) and cur:
            keep = max(1, int(len(cur) * max_bytes / max(nbytes, 1)))
            truncated = {"kind": "bytes", "returned": keep, "total": len(cur),
                         "bytes": nbytes, "max_bytes": max_bytes}
            cur = cur[:keep]
        else:
            return {"name": name, "found": True, "path": path, "value": None,
                    "shape": _block_shape(cur), "bytes": nbytes,
                    "truncated": {"kind": "too_big", "bytes": nbytes, "max_bytes": max_bytes},
                    "note": "통째로는 너무 크다 — `path` 로 하위를 좁히거나 max_bytes 를 올려라"}
    out = {"name": name, "found": True, "path": path, "value": cur,
           "shape": _block_shape(cur), "bytes": _rough_bytes(cur),
           "read_by_parser": name in PARSER_READS}
    if truncated:
        out["truncated"] = truncated
        out["note"] = "배열을 잘라서 돌려줬다 — 전체 %d 중 %d" % (truncated["total"], truncated["returned"])
    return out


#: deep 리포트의 **같은 모양** 시계열 배열들 — `[{part_id, quantity, t, max_vals, avg_vals,
#: global_max, global_min, time_of_max, unit}, …]`. 전에는 `stress` 하나만 읽어 나머지 여섯이
#: 끊겨 있었다. 생성기가 늘리면 여기 한 줄만 더한다.
DEEP_SERIES_BLOCKS = ("stress", "strain", "vm_strain",
                      "max_principal", "min_principal",
                      "max_principal_strain", "min_principal_strain")

_SCATTER_METRICS = ("peak_stress", "peak_strain", "peak_plastic_strain", "peak_g",
                    "peak_disp", "peak_vel", "peak_ie", "peak_ke")
_CUBE_BASES: list[tuple[tuple[int, int, int], tuple[float, float, float]]] | None = None


def _cube_bases():
    """26 정준 큐브 방향(면6·엣지12·코너8) 단위벡터."""
    global _CUBE_BASES
    if _CUBE_BASES is None:
        bs = []
        for x in (-1, 0, 1):
            for y in (-1, 0, 1):
                for z in (-1, 0, 1):
                    if (x, y, z) == (0, 0, 0):
                        continue
                    n = math.sqrt(x * x + y * y + z * z)
                    bs.append(((x, y, z), (x / n, y / n, z / n)))
        _CUBE_BASES = bs
    return _CUBE_BASES


def _angle_vec(a: dict) -> tuple[float, float, float]:
    """각도(roll/pitch/yaw[+swap]) → 단위 방향벡터. sphere 리포트 변환과 동일."""
    swap = bool(a.get("swap"))
    roll = _num(a.get("roll")) or 0.0
    pitch = _num(a.get("pitch")) or 0.0
    if swap:
        lat, lon = math.radians(pitch), math.radians(roll)
    else:
        lat, lon = math.radians(roll), math.radians(pitch)
    lat = max(-math.pi / 2, min(math.pi / 2, lat))
    return (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))


def _angle_lonlat(a: dict) -> tuple[float, float]:
    """각도 → 등장방형 투영 좌표(경도 lon∈[-180,180], 위도 lat∈[-90,90], 도).

    _angle_vec 과 동일한 규약(swap 반영)이라 방향벡터↔lon/lat 이 정합한다.
    lat=asin(vz), lon=atan2(vy,vx) 이지만 clamp 후 항등이므로 직접 계산한다.
    """
    swap = bool(a.get("swap"))
    roll = _num(a.get("roll")) or 0.0
    pitch = _num(a.get("pitch")) or 0.0
    lat, lon = (pitch, roll) if swap else (roll, pitch)
    lat = max(-90.0, min(90.0, lat))
    lon = ((lon + 180.0) % 360.0) - 180.0  # [-180,180] 로 래핑
    return (lon, lat)


def _nearest_base(v):
    """벡터를 최근접 26 정준방향에 배정 → (key_tuple, angular_error_deg)."""
    best, bdot = None, -2.0
    for key, bv in _cube_bases():
        dot = max(-1.0, min(1.0, v[0] * bv[0] + v[1] * bv[1] + v[2] * bv[2]))
        if dot > bdot:
            bdot, best = dot, key
    return best, math.degrees(math.acos(max(-1.0, min(1.0, bdot))))


def _base_category(key: tuple[int, int, int]) -> str:
    return {1: "face", 2: "edge", 3: "corner"}[sum(1 for c in key if c != 0)]


def scatter_analysis(data: dict, kind: str, *, metric: str = "peak_stress",
                     part_id: int | None = None) -> dict:
    """방향 섭동 산포 분석(sphere 전용).

    각 케이스를 최근접 26 정준방향으로 묶어 방향별 metric 산포(n/mean/std/CoV/min/max/
    최악 케이스)를 계산한다. part_id 미지정 시 케이스별 파트 최댓값을 쓴다.
    방향당 표본이 1개뿐이면(순수 26면) 산포=0 이라 degenerate 로 표시한다.
    """
    if kind != "sphere":
        return {"kind": kind, "note": "스캐터 분석은 sphere(전각도) 리포트에서만 지원됩니다."}
    if metric not in _SCATTER_METRICS:
        raise ReportParseError(f"metric 은 {list(_SCATTER_METRICS)} 중 하나여야 합니다.")

    groups: dict[tuple, dict] = {}
    n_cases = 0
    for r in data.get("results") or []:
        if not isinstance(r, dict):
            continue
        a = r.get("angle") or {}
        parts = r.get("parts") or {}
        if part_id is not None:
            val = _sphere_part_metrics(parts.get(str(part_id)) or {}).get(metric)
        else:
            vals = [_sphere_part_metrics(p or {}).get(metric) for p in parts.values()]
            vals = [x for x in vals if x is not None]
            val = max(vals) if vals else None
        if val is None:
            continue
        key, err = _nearest_base(_angle_vec(a))
        case_key = r.get("folder") or a.get("name") or f"run_{n_cases}"
        g = groups.setdefault(key, {"values": [], "cases": [], "rep_name": None, "rep_err": 1e9})
        g["values"].append(val)
        g["cases"].append((val, case_key))
        if err < g["rep_err"]:
            g["rep_err"], g["rep_name"] = err, a.get("name")
        n_cases += 1

    out_groups = []
    for key, g in groups.items():
        vals = g["values"]
        mean = statistics.fmean(vals)
        std = statistics.stdev(vals) if len(vals) > 1 else 0.0  # 표본(n-1) — angle_group_stats 와 통일
        worst = max(g["cases"], key=lambda c: c[0])
        out_groups.append({
            "base": ",".join(str(c) for c in key),
            "category": _base_category(key),
            "representative": g["rep_name"],
            "n": len(vals),
            "mean": mean,
            "std": std,
            "cov": (std / mean) if mean else None,
            "min": min(vals),
            "max": max(vals),
            "worst_value": worst[0],
            "worst_case_key": worst[1],
        })
    out_groups.sort(key=lambda d: -d["mean"])

    degenerate = all(g["n"] <= 1 for g in out_groups)
    most_scattered = None
    scat = [g for g in out_groups if g["n"] >= 2 and g["cov"] is not None]
    if scat:
        most_scattered = max(scat, key=lambda d: d["cov"])
    return {
        "kind": "sphere", "metric": metric, "part_id": part_id,
        "n_cases": n_cases, "n_bases": len(out_groups),
        "degenerate": degenerate,
        "note": ("방향당 표본이 1개뿐이라 산포가 0입니다 — 섭동 DOE(방향당 여러 run)가 아니면 "
                 "민감도가 나오지 않습니다.") if degenerate else None,
        "most_severe": out_groups[0] if out_groups else None,
        "most_scattered": most_scattered,
        "groups": out_groups,
    }
