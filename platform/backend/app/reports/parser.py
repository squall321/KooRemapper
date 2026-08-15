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
import re

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
    """숫자면 float, None/비숫자면 None (미측정을 0으로 왜곡하지 않음)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
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
    parts_in = data.get("parts") or {}

    parts = []
    parts_metrics = {}
    for pid, p in parts_in.items():
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
def normalize_sphere(data: dict) -> dict:
    sim_params_in = data.get("sim_params") or {}
    parts_in = data.get("parts") or {}

    parts = []
    for pid, p in parts_in.items():
        name = p.get("name") or p.get("part_name") or f"Part_{pid}"
        parts.append({"part_id": _to_int(pid), "name": name, "group": p.get("group") or _group_of(name)})

    cases = []
    for r in data.get("results") or []:
        angle = r.get("angle") or {}
        pm = {}
        for pid, p in (r.get("parts") or {}).items():
            pm[str(pid)] = {
                "peak_stress": _num(p.get("peak_stress")),
                "peak_strain": _num(p.get("peak_strain")),
                "peak_g": _num(p.get("peak_g")),
                "peak_disp": _num(p.get("peak_disp")),
                "time_of_peak_stress": _num(p.get("time_of_peak_stress")),
                "time_of_peak_g": _num(p.get("time_of_peak_g")),
            }
        cases.append({
            "case_key": r.get("folder") or angle.get("name") or f"run_{len(cases)}",
            "identity": {
                "angle": {
                    "name": angle.get("name"),
                    "roll": _num(angle.get("roll")),
                    "pitch": _num(angle.get("pitch")),
                    "yaw": _num(angle.get("yaw")),
                    "category": angle.get("category"),
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
            "unit_system": None,
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
    }


# ── impact 정규화 ────────────────────────────────────────────────────
def normalize_impact(data: dict) -> dict:
    """전위치 부분충격(F1~F6 × XY 그리드). 케이스=충격 위치(pos_id).

    임베드 payload 는 결과를 평탄한 ``results[]`` 로 담고, 각 행이
    (face, pos_id, x, y, part_id, g/s/e/d[, s1/s3/e1/e3/evm]) 이다. pos_id 로 묶어
    위치별 케이스를 만들고, 파트별 메트릭 약어를 공통 스키마로 편다.
    """
    meta = data.get("meta") or {}
    kpi = data.get("kpi") or {}
    sim_params_in = meta.get("sim_params") or {}
    impactor = meta.get("impactor") or {}

    parts = []
    for p in data.get("parts") or []:
        name = p.get("name") or f"Part_{p.get('id')}"
        parts.append({"part_id": _to_int(p.get("id")), "name": name, "group": p.get("group") or _group_of(name)})

    by_pos: dict[str, dict] = {}
    for row in data.get("results") or []:
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


def parse_html(html: str, *, kind_hint: str | None = None) -> dict:
    """리포트 HTML → 공통 정규화 스터디 dict. kind_hint 로 자동판별을 덮어쓸 수 있다."""
    data = extract_embedded_data(html)
    kind = kind_hint or detect_kind(data)
    if kind not in _NORMALIZERS:
        raise ReportParseError(f"지원하지 않는 kind: {kind}")
    return _NORMALIZERS[kind](data)


def parse_data(data: dict, *, kind_hint: str | None = None) -> dict:
    """이미 파싱된 임베드/사이드카 dict → 공통 정규화 스터디 dict."""
    kind = kind_hint or detect_kind(data)
    return _NORMALIZERS[kind](data)
