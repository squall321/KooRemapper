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
    flow = flows.get(case_key) if case_key else None
    if flow is None and flows:
        flow = next(iter(flows.values()))
    if not isinstance(flow, dict):
        return {"kind": kind, "case_key": case_key, "energy_flow": None,
                "note": "이 리포트/케이스엔 에너지 플로우 데이터가 없습니다."}
    return {
        "kind": kind, "case_key": case_key,
        "energy_flow": {
            "impactor_ke_initial": _num(flow.get("impactor_ke_initial")),
            "impactor_ke_final": _num(flow.get("impactor_ke_final")),
            "energy_dissipated": _num(flow.get("energy_dissipated")),
            "propagation_order": flow.get("propagation_order"),
            "nodes": [
                {"node_id": n.get("node_id"), "is_impactor": n.get("is_impactor"),
                 "peak_ie": _num(n.get("peak_ie")), "peak_ke": _num(n.get("peak_ke"))}
                for n in (flow.get("nodes") or [])
            ],
            "edges": [
                {"src": e.get("src"), "dst": e.get("dst"), "name": e.get("name"),
                 "peak_force": _num(e.get("peak_force")), "total_work": _num(e.get("total_work")),
                 "confidence": _num(e.get("confidence"))}
                for e in (flow.get("edges") or [])
            ],
        },
    }


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
        parts.append({
            "part_id": _to_int(p.get("id")),
            "name": p.get("name"),
            "group": p.get("group"),
            "footprint": fp if isinstance(fp, list) else None,
            "zmin": _num(p.get("zmin")),
            "zmax": _num(p.get("zmax")),
        })
    return {"kind": "impact", "device_outline": outline, "device_bbox": bbox, "parts": parts}


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
        out: dict = {"kind": "deep", "part_id": part_id, "stress": {}, "motion": {}}
        for entry in data.get("stress") or []:
            if str(entry.get("part_id")) == pid:
                out["stress"][entry.get("quantity") or "von_mises"] = {
                    "t": entry.get("t"), "max": entry.get("max_vals"), "avg": entry.get("avg_vals"),
                    "global_max": _num(entry.get("global_max")),
                }
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
