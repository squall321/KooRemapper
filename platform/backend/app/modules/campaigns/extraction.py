# 캠페인 런의 추출 목록을 필수 추출 목록과 견줘 d3plot 삭제 허가 · 피크 출처 표지를 내는 순수 함수 — DB 를 모른다
"""추출 완전성 · 삭제 관문(요청서 DF-04 · 계획 docs/01-plan/features/df-extraction-clearance-1122.plan.md 4 · 5절).

허가와 표지는 저장하지 않는다 — 읽을 때 지금 필수 목록으로 센다. 삭제는 하지 않는다(KooChainRun KC-05 의 일이다).
"""
from __future__ import annotations

PEAK_SOURCES = ("binout", "elout", "d3plot_full", "d3plot_sampled")
STATUSES = ("allow", "hold", "deleted")


def field_key(name: str) -> str:
    """field 이름의 견줌 열쇠 — 앞뒤 공백을 떼고 대소문자를 가리지 않는다(이름은 자유 글이다)."""
    return " ".join(str(name).split()).casefold()


def run_states(extraction: dict) -> str | None:
    """런 전체의 상태 범위 — read = total 이면 all, 적으면 sampled. 수가 없으면 피크 출처로(d3plot_full · d3plot_sampled), 그도
    없으면 모른다(None)."""
    total, read = extraction.get("d3plot_states_total"), extraction.get("d3plot_states_read")
    if isinstance(total, int) and isinstance(read, int) and total > 0:
        return "all" if read >= total else "sampled"
    return {"d3plot_full": "all", "d3plot_sampled": "sampled"}.get(extraction.get("peak_source"))


def extracted_items(extraction: dict) -> list[dict]:
    """`fields_extracted` 를 `{key, field, parts(None = 모든 파트), states}` 로 — 글 하나는 모든 파트 · 런의 상태 범위다."""
    default_states = run_states(extraction)
    out = []
    for it in extraction.get("fields_extracted") or []:
        if isinstance(it, str):
            it = {"field": it}
        parts = it.get("parts")
        out.append({"key": field_key(it["field"]), "field": it["field"],
                    "parts": None if parts is None else sorted(set(parts)),
                    "states": it.get("states") or default_states})
    return out


def _gap(req: dict, have: list[dict]) -> dict | None:
    """필수 항목 하나가 채워졌으면 None, 아니면 빠진 까닭 — field_missing · parts_missing(빠진 파트) · states_sampled ·
    states_unknown 가운데 가장 가까운 추출의 것."""
    same = [h for h in have if h["key"] == field_key(req["field"])]
    base = {"field": req["field"], "parts": req.get("parts"), "states": req.get("states") or "all"}
    if not same:
        return {**base, "reason": "field_missing"}
    want_parts = req.get("parts")
    want_all_states = (req.get("states") or "all") == "all"
    best = None
    for h in same:
        if h["parts"] is None:
            lack: list[int] | None = []
        elif want_parts is None:
            lack = None                     # 필수가 「모든 파트」 인데 추출은 일부 — 무엇이 빠졌는지 셀 수 없다
        else:
            lack = sorted(set(want_parts) - set(h["parts"]))
        states_ok = (not want_all_states) or h["states"] == "all"
        if lack == [] and states_ok:
            return None
        if lack == [] and not states_ok:
            cand = {**base, "reason": "states_unknown" if h["states"] is None else "states_sampled"}
        else:
            cand = {**base, "reason": "parts_missing", "parts_missing": lack}
        if best is None or (best["reason"] == "parts_missing" and cand["reason"] != "parts_missing"):
            best = cand
    return best


def clearance(*, has_report: bool, extraction: dict | None, required: list[dict] | None) -> dict:
    """`{status: allow | hold | deleted, reasons: [...], missing: [...]}` — 계획 4절의 규칙."""
    deleted = bool(extraction) and (extraction.get("d3plot_retained") is False or bool(extraction.get("d3plot_deleted_at")))
    missing = [g for g in (_gap(r, extracted_items(extraction)) for r in (required or [])) if g] if extraction else []
    if deleted:
        reasons = ["already_deleted"] + (["extraction_lost"] if missing else [])
        return {"status": "deleted", "reasons": reasons, "missing": missing}
    reasons = []
    if not required:
        reasons.append("required_extractions_unset")
    if not has_report:
        reasons.append("no_report")
    if not extraction:
        reasons.append("extraction_missing")
    elif missing:
        reasons.append("extraction_incomplete")
    return {"status": "hold" if reasons else "allow", "reasons": reasons, "missing": missing}


def peak_provenance(extraction: dict | None) -> dict:
    """피크 출처 표지 — 응답마다 싣는다. 추출이 없으면 네 칸이 null · `known: false`.

    `peak_may_be_missed` — d3plot 표본 상태에서 나온 피크(`d3plot_sampled` · 또는 `d3plot_*` 인데 읽은 상태가 전체보다 적다)면 참,
    시간 이력 출력(`binout` · `elout`)이면 거짓, 출처를 모르면 null.
    """
    if not extraction:
        return {"known": False, "peak_source": None, "states_read": None, "states_total": None, "peak_may_be_missed": None}
    src = extraction.get("peak_source")
    read, total = extraction.get("d3plot_states_read"), extraction.get("d3plot_states_total")
    if src == "d3plot_sampled":
        missed: bool | None = True
    elif src == "d3plot_full":
        missed = isinstance(read, int) and isinstance(total, int) and read < total
    elif src in ("binout", "elout"):
        missed = False
    else:
        missed = None
    return {"known": True, "peak_source": src, "states_read": read, "states_total": total, "peak_may_be_missed": missed}


def header(rows: list[dict]) -> dict:
    """머리 줄 — 전체 · 허가 · 보류 · 이미 지움 수와 까닭별 수."""
    n = {st: sum(1 for r in rows if r["clearance"]["status"] == st) for st in STATUSES}
    by: dict[str, int] = {}
    for r in rows:
        for why in r["clearance"]["reasons"]:
            by[why] = by.get(why, 0) + 1
    line = f"삭제 허가 {n['allow']} / 전체 {len(rows)} · 보류 {n['hold']} · 이미 지움 {n['deleted']}"
    if by:
        line += " · " + " · ".join(f"{k} {v}" for k, v in sorted(by.items(), key=lambda kv: (-kv[1], kv[0])))
    return {"total": len(rows), **n, "reasons": by, "line": line}
