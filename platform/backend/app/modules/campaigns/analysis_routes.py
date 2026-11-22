# 캠페인 분석 REST 라우트(DF-05 · 06 · 08 ~ 12) — 무리 · 각도 표 · 통계 · 피크 · 기준값 · 여유 · 구면 지도 · 자리 · 짝 표 · 리비전 비교 · 설정 쌍
from __future__ import annotations

import asyncio
import hashlib
import math
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Campaign, User
from app.modules.campaigns import analysis as A
from app.modules.campaigns import angles as G
from app.modules.campaigns import services as svc
from app.modules.campaigns import sphere as SP
from app.shared.auth import get_current_user
from app.shared.responses import ok

router = APIRouter(tags=["campaigns"], prefix="/campaigns")
part_maps_router = APIRouter(tags=["campaigns"], prefix="/part-maps")

_UNPROCESSABLE = 422
_ROWS_MAX = 5000
_GROUPS_MAX = 200
_PARTS_MAX = 10000
_Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[^\s\x00-\x1f\x7f]+$")]
_Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def _campaign(db: AsyncSession, user: User, campaign_id: str) -> Campaign:
    c = await svc.get_owned(db, user.id, campaign_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "캠페인을 찾을 수 없습니다.")
    return c


def _metric(name: str) -> str:
    m = G.resolve_metric(name.strip())
    if m is None:
        raise HTTPException(_UNPROCESSABLE, f"모르는 지표 「{name}」 — 받는 것: {', '.join(G.METRICS)} · 별칭 {', '.join(G.METRIC_ALIASES)}")
    return m


def _csv(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def _axis(campaign: Campaign, given: str | None) -> str:
    return (given or campaign.thickness_axis or "Z").upper()


async def _groups(db: AsyncSession, campaign: Campaign, wanted: str | None) -> list[dict]:
    """정한 무리(없으면 `all` 하나)에서 고른 것만 — 모르는 무리 키는 422."""
    have = await A.part_groups(db, campaign.id) or [{"group_key": "all", "label": "모든 파트", "part_ids": None, "part_key": None}]
    keys = _csv(wanted)
    if not keys:
        return have
    by = {g["group_key"]: g for g in have}
    bad = [k for k in keys if k not in by]
    if bad:
        raise HTTPException(_UNPROCESSABLE, f"모르는 무리 — {', '.join(bad)}(정한 무리: {', '.join(by)})")
    return [by[k] for k in keys]


def _strip(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


_Filters = {"include_invalid": Query(default=False, description="참이면 제외 까닭이 있는 런도 넣는다(리포트가 있는 런 모두)"),
            "include_ke_jump": Query(default=False, description="참이면 첫 KE 가 ½mv² 와 어긋난 런(ke0_mismatch)도 넣는다"),
            "config_generation": Query(default=None, max_length=64, description="이 설정 세대의 런만")}


async def _rows(db, c, *, metrics, groups, thickness_axis, include_invalid, include_ke_jump, config_generation,
                keep_pm=False, ignore_superseded=False):
    runs, hd = await A.analysis_runs(db, c, include_invalid=include_invalid, include_ke_jump=include_ke_jump,
                                     config_generation=config_generation, ignore_superseded=ignore_superseded)
    return G.angle_rows(runs, groups, metrics, thickness_axis, keep_pm=keep_pm), hd, runs


# ── ⑤-1 무리 · 각도 표 · 통계 · 피크(DF-05 · 06) ────────────────────────────

class GroupItem(_Strict):
    group_key: _Key
    label: _Text | None = None
    part_ids: list[Annotated[int, Field(gt=0)]] = Field(min_length=1, max_length=_PARTS_MAX)
    part_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None


class GroupsBody(_Strict):
    groups: list[GroupItem] = Field(max_length=_GROUPS_MAX)


@router.put("/{campaign_id}/part-groups")
async def set_campaign_part_groups(campaign_id: str, body: GroupsBody, user: User = Depends(get_current_user),
                                   db: AsyncSession = Depends(get_db)):
    """부품 무리를 통째로 바꾼다(DF-05) — 빈 목록이면 지운다(그러면 무리 하나 `all` = 모든 파트로 센다). 같은 group_key 가 둘이면 422."""
    c = await _campaign(db, user, campaign_id)
    keys = [g.group_key for g in body.groups]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:
        raise HTTPException(_UNPROCESSABLE, f"같은 group_key 가 둘 이상입니다 — {', '.join(dup)}")
    got = await A.set_part_groups(db, c.id, [{**g.model_dump(), "part_ids": sorted(set(g.part_ids))} for g in body.groups])
    return ok({"campaign_id": campaign_id, "groups": got, "environment": settings.environment},
              message=f"무리 {len(got)}개" if got else "무리를 지웠습니다 — 모든 파트를 무리 하나(all)로 셉니다.")


@router.get("/{campaign_id}/angle-table")
async def campaign_angle_table(
    campaign_id: str,
    metrics: str = Query(default="peak_stress", description="지표(쉼표로 여럿) — 리포트 파트 지표 이름 또는 MET-* 별칭"),
    groups: str | None = Query(default=None, description="무리 키(쉼표로 여럿) — 비우면 정한 무리 전부"),
    thickness_axis: Literal["X", "Y", "Z"] | None = Query(default=None, description="두께축 — 비우면 캠페인의 것, 그것도 없으면 Z"),
    include_invalid: bool = _Filters["include_invalid"], include_ke_jump: bool = _Filters["include_ke_jump"],
    config_generation: str | None = _Filters["config_generation"],
    limit: int = Query(default=1000, ge=1, le=_ROWS_MAX), offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """캠페인 각도 표(DF-05) — 각도마다 방향 벡터(덱 틀) · 범주(face · edge · vertex) · 라벨(가장 가까운 26 방향) · 충격 수 · 두 번째 충격
    시각 · 첫 KE · 무리별 피크(값 · 파트 · 시각 ms · 충격 차수 · 그 충격의 KE 비) · 피크 출처. 머리 줄은 유효 n / 전체 N · 제외 까닭(KE 튐은
    `excluded_ke_jump`)."""
    c = await _campaign(db, user, campaign_id)
    ms = [_metric(m) for m in _csv(metrics)] or ["peak_stress"]
    gs = await _groups(db, c, groups)
    axis = _axis(c, thickness_axis)
    rows, hd, _ = await _rows(db, c, metrics=ms, groups=gs, thickness_axis=axis, include_invalid=include_invalid,
                              include_ke_jump=include_ke_jump, config_generation=config_generation)
    return ok({"campaign_id": campaign_id, "header": hd, "thickness_axis": axis, "metrics": ms,
               "units": {m: G.METRIC_UNITS[m] for m in ms}, "groups": gs, "matched": len(rows),
               "rows": _strip(rows[offset:offset + limit]), "limit": limit, "offset": offset, "environment": settings.environment},
              message=hd["line"])


@router.get("/{campaign_id}/angle-stats")
async def campaign_angle_stats(
    campaign_id: str,
    metric: str = Query(default="peak_stress", description="지표 하나 — 리포트 파트 지표 이름 또는 MET-* 별칭"),
    groups: str | None = Query(default=None, description="무리 키(쉼표로 여럿) — 비우면 정한 무리 전부"),
    thickness_axis: Literal["X", "Y", "Z"] | None = Query(default=None, description="두께축 — 비우면 캠페인의 것, 그것도 없으면 Z"),
    include_invalid: bool = _Filters["include_invalid"], include_ke_jump: bool = _Filters["include_ke_jump"],
    config_generation: str | None = _Filters["config_generation"],
    top: int = Query(default=10, ge=1, le=100, description="상위 · 하위 몇 각도"),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """캠페인 각도 통계(DF-05) — n · 제외 수(`excluded_ke_jump` 따로) · 다회 충격 비율(충격 구간을 받은 각도 가운데) · 무리별 분포(최소 ·
    p10 · 가운데 · p90 · 최대 · 평균) · 상위 · 하위 · 범주별 · 라벨별 · 피크 충격 차수 분포 · 덮임(26 방향 가운데 맞은 라벨)."""
    c = await _campaign(db, user, campaign_id)
    m = _metric(metric)
    gs = await _groups(db, c, groups)
    axis = _axis(c, thickness_axis)
    rows, hd, _ = await _rows(db, c, metrics=[m], groups=gs, thickness_axis=axis, include_invalid=include_invalid,
                              include_ke_jump=include_ke_jump, config_generation=config_generation)
    st = G.angle_stats(rows, [g["group_key"] for g in gs], m, top=top)
    return ok({"campaign_id": campaign_id, "header": hd, "thickness_axis": axis, "metric": m, "unit": G.METRIC_UNITS[m],
               "groups": gs, "stats": st, "environment": settings.environment}, message=hd["line"])


@router.get("/{campaign_id}/peaks")
async def campaign_peak_table(
    campaign_id: str,
    metric: str = Query(default="peak_stress", description="지표 하나 — 리포트 파트 지표 이름 또는 MET-* 별칭"),
    groups: str | None = Query(default=None, description="무리 키(쉼표로 여럿) — 비우면 정한 무리 전부"),
    include_invalid: bool = _Filters["include_invalid"], include_ke_jump: bool = _Filters["include_ke_jump"],
    config_generation: str | None = _Filters["config_generation"],
    limit: int = Query(default=1000, ge=1, le=_ROWS_MAX), offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """각도별 피크 표(DF-06) — 각도 × 무리마다 값 · 파트 · 피크 시각(ms) · 피크가 난 충격 차수 · 그 충격의 KE 비 · 충격 수 · 피크 출처
    (DF-04 `peak_source`). 충격별 표는 런의 충격 구간마다(시작 · 끝 ms · KE 비 · 무리별 그 충격의 피크 — 만드는 쪽이 보냈을 때)."""
    c = await _campaign(db, user, campaign_id)
    m = _metric(metric)
    gs = await _groups(db, c, groups)
    rows, hd, runs = await _rows(db, c, metrics=[m], groups=gs, thickness_axis=_axis(c, None), include_invalid=include_invalid,
                                 include_ke_jump=include_ke_jump, config_generation=config_generation)
    peaks = [{"run_key": r["run_key"], "case_key": r["case_key"], "doe": r["doe"], "group_key": g["group_key"],
              "value": r["peaks"][g["group_key"]][m]["value"], "part_id": r["peaks"][g["group_key"]][m]["part_id"],
              "t_peak_ms": r["peaks"][g["group_key"]][m]["t_peak_ms"], "peak_impact": r["peaks"][g["group_key"]][m]["peak_impact"],
              "ke_frac_at_impact": r["peaks"][g["group_key"]][m]["ke_frac_at_impact"], "n_impacts": r["n_impacts"],
              "peak_source": r["peak_source"]} for r in rows for g in gs]
    impacts = [{"run_key": run["run_key"], "doe": run["doe"], "impact": i.get("index"), "t_start_ms": i.get("t_start_ms"),
                "t_end_ms": i.get("t_end_ms"), "ke_frac": i.get("ke_frac"), "group_key": g["group_key"],
                "value": (i.get("peaks") or {}).get(g["group_key"])}
               for run in runs for i in sorted(run["impacts"] or [], key=lambda x: x.get("index") or 0) for g in gs]
    return ok({"campaign_id": campaign_id, "header": hd, "metric": m, "unit": G.METRIC_UNITS[m], "groups": gs,
               "matched": len(peaks), "peaks": peaks[offset:offset + limit], "impacts": impacts, "limit": limit, "offset": offset,
               "environment": settings.environment}, message=hd["line"])


# ── ⑤-2 기준값 · 여유(DF-08) ─────────────────────────────────────────────────

_UNIT_OK = {"MPa": {"MPa"}, "µε": {"µε", "ue", "microstrain"}, "": {"", "-", "mm/mm", "strain"}}


class CriterionItem(_Strict):
    part_id: int | None = Field(default=None, gt=0)
    group_key: _Key | None = None
    failure_mode: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None
    metric_axis: Literal["tension_principal_stress", "von_mises", "compressive_strain", "board_strain_ue", "effective_plastic_strain"]
    criterion_value: float = Field(gt=0, allow_inf_nan=False)
    unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=16)]
    source_platform: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None
    source_record_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)] | None = None
    version: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None

    @model_validator(mode="after")
    def _one_target_and_unit(self):
        if (self.part_id is None) == (self.group_key is None):
            raise ValueError("part_id · group_key 가운데 하나만 줍니다")
        want = G.MARGIN_AXES[self.metric_axis][2]
        if self.unit not in _UNIT_OK[want]:
            raise ValueError(f"{self.metric_axis} 의 단위는 {sorted(_UNIT_OK[want])} 가운데 하나입니다(받은 것 「{self.unit}」)")
        return self


class CriteriaBody(_Strict):
    criteria: list[CriterionItem] = Field(max_length=1000)


@router.put("/{campaign_id}/criteria")
async def set_campaign_criteria(campaign_id: str, body: CriteriaBody, user: User = Depends(get_current_user),
                                db: AsyncSession = Depends(get_db)):
    """기준값 묶음을 통째로 바꾼다(DF-08) — 항목마다 파트(`part_id`) 또는 무리(`group_key`) 하나 · 고장모드 · 지표 축 · 값 · 단위 · 출처
    (`source_platform` · `source_record_id` · `version`). 빈 목록이면 지운다. 같은 대상 · 지표 축 · 고장모드가 둘이면 422."""
    c = await _campaign(db, user, campaign_id)
    seen, items = set(), []
    for it in body.criteria:
        k = (it.part_id, it.group_key, it.metric_axis, it.failure_mode)
        if k in seen:
            raise HTTPException(_UNPROCESSABLE, f"같은 대상 · 지표 축 · 고장모드가 둘 이상입니다 — {k}")
        seen.add(k)
        d = it.model_dump()
        d["unit"] = G.MARGIN_AXES[it.metric_axis][2]
        items.append(d)
    got = await A.set_criteria(db, c.id, items)
    return ok({"campaign_id": campaign_id, "criteria": got, "environment": settings.environment},
              message=f"기준값 {len(got)}개" if got else "기준값을 지웠습니다 — 여유는 모두 「기준 미지정」 입니다.")


@router.get("/{campaign_id}/part-margin")
async def campaign_part_margin(
    campaign_id: str,
    metric_axis: Literal["tension_principal_stress", "von_mises", "compressive_strain", "board_strain_ue",
                         "effective_plastic_strain"] | None = Query(default=None, description="지표 축 — 비우면 기준값에 있는 축 전부"),
    include_invalid: bool = _Filters["include_invalid"], include_ke_jump: bool = _Filters["include_ke_jump"],
    config_generation: str | None = _Filters["config_generation"],
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """부품 위험 · 허용치 여유(DF-08) — 행 = 부품 또는 무리 · 지표 축 · 값(각도 최댓값) · 가운데값 · 기준값 · 기준 출처 · 비 · 가운데 비 ·
    기준 넘은 각도 비율 · 상위 10 % 각도. 기준값은 묶음(`set_campaign_criteria`)의 것만 쓴다 — 리포트의 항복값은 쓰지 않는다. 기준이 없는
    무리는 `criterion_unset`(비 null)."""
    c = await _campaign(db, user, campaign_id)
    groups = await A.part_groups(db, c.id)
    by_group = {g["group_key"]: g for g in groups}
    crit = await A.criteria(db, c.id)
    axes = [metric_axis] if metric_axis else sorted({b["metric_axis"] for b in crit})
    rows, hd, _ = await _rows(db, c, metrics=[], groups=groups, thickness_axis=_axis(c, None), include_invalid=include_invalid,
                              include_ke_jump=include_ke_jump, config_generation=config_generation, keep_pm=True)
    out = []
    for b in crit:
        if b["metric_axis"] not in axes:
            continue
        if b["part_id"] is not None:
            target, ids, label = {"part_id": b["part_id"]}, [b["part_id"]], None
        else:
            g = by_group.get(b["group_key"])
            target, label = {"group_key": b["group_key"]}, (g or {}).get("label")
            if g is None:
                out.append({"target": target, "metric_axis": b["metric_axis"], "status": "group_unknown", "criterion": b["criterion_value"]})
                continue
            ids = g["part_ids"]
        vals = [(r, v) for r in rows if (v := G.axis_value(r["_pm"], ids, b["metric_axis"])) is not None]
        out.append({"target": target, "label": label, "failure_mode": b["failure_mode"], "metric_axis": b["metric_axis"],
                    "unit": G.MARGIN_AXES[b["metric_axis"]][2], "status": "ok",
                    "criterion_source": {k: b[k] for k in ("source_platform", "source_record_id", "version")},
                    **G.margin(vals, b["criterion_value"])})
    bound = {(b["group_key"], b["metric_axis"]) for b in crit if b["group_key"]}
    for ax in axes:
        for g in groups or [{"group_key": "all", "label": "모든 파트", "part_ids": None}]:
            if (g["group_key"], ax) in bound:
                continue
            vals = [(r, v) for r in rows if (v := G.axis_value(r["_pm"], g["part_ids"], ax)) is not None]
            out.append({"target": {"group_key": g["group_key"]}, "label": g.get("label"), "failure_mode": None, "metric_axis": ax,
                        "unit": G.MARGIN_AXES[ax][2], "status": "criterion_unset", "criterion_source": None, **G.margin(vals, None)})
    msg = hd["line"] if axes else "기준값이 없습니다 — set_campaign_criteria 로 기준값 묶음을 두거나 metric_axis 를 고르세요."
    return ok({"campaign_id": campaign_id, "header": hd, "axes": axes, "criteria": crit, "rows": out,
               "environment": settings.environment}, message=msg)


# ── ⑤-3 구면 지도(DF-09) ────────────────────────────────────────────────────

@router.get("/{campaign_id}/sphere-map")
async def campaign_sphere_map(
    campaign_id: str,
    metric: str = Query(default="peak_stress", description="지표 하나 — 리포트 파트 지표 이름 또는 MET-* 별칭"),
    group: str | None = Query(default=None, max_length=64, description="무리 키 하나 — 비우면 첫 무리(무리가 없으면 all)"),
    format: Literal["json", "svg", "png"] = Query(default="json", description="json(격자 · 점) · svg(Mollweide 그림) · png(글자 없는 래스터)"),
    center: bool = Query(default=True, description="센 띠(cos 위도 가중 경도 열 평균이 가장 큰 열)를 경도 0° 로 돌린다"),
    thickness_axis: Literal["X", "Y", "Z"] | None = Query(default=None, description="두께축 — 비우면 캠페인의 것, 그것도 없으면 Z"),
    include_invalid: bool = _Filters["include_invalid"], include_ke_jump: bool = _Filters["include_ke_jump"],
    config_generation: str | None = _Filters["config_generation"],
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """구면 위험도 지도(DF-09) — 각도 값을 두께 틀의 경위도 격자(경도 361 × 위도 181)로 보간한다(가까운 8 방향 · 가중 1 / max(θ, 0.5°)²).
    json 은 격자 · 방향 점 · 돌린 경도 · 출처 줄(유효 n · 제외 · 세대), svg 는 Mollweide 띠 칠 · 등고선 · 방향 점 · 범례, png 는 띠 칠 래스터."""
    c = await _campaign(db, user, campaign_id)
    m = _metric(metric)
    gs = await _groups(db, c, group)
    g = gs[0]
    axis = _axis(c, thickness_axis)
    rows, hd, _ = await _rows(db, c, metrics=[m], groups=[g], thickness_axis=axis, include_invalid=include_invalid,
                              include_ke_jump=include_ke_jump, config_generation=config_generation)
    pts = [{"lon": r["lon"], "lat": r["lat"], "value": r["peaks"][g["group_key"]][m]["value"], "run_key": r["run_key"],
            "case_key": r["case_key"], "doe": r["doe"]}
           for r in rows if r["lon"] is not None and r["peaks"][g["group_key"]][m]["value"] is not None]
    if not pts:
        raise HTTPException(_UNPROCESSABLE, "방향과 값이 있는 각도가 없습니다 — 지도를 그릴 수 없습니다.")
    gr = await asyncio.to_thread(SP.grid, pts)
    shift = SP.center_shift(gr) if center else 0
    if shift:
        gr = SP.rotate(gr, shift)
        pts = [{**p, "lon": SP.wrap_lon(p["lon"] - shift)} for p in pts]
    lo = min(min(r) for r in gr)
    hi = max(max(r) for r in gr)
    gens = " · ".join(f"{x['config_generation'] or '(없음)'} {x['runs']}" for x in hd["generations"])
    prov = f"{c.name} · {m} · 무리 {g['group_key']} · {hd['line']} · 세대 {gens or '(없음)'} · 기준값 판 없음"
    if format == "png":
        data = await asyncio.to_thread(SP.raster_png, gr, lo, hi)
        return Response(content=data, media_type="image/png",
                        headers={"X-Content-SHA256": hashlib.sha256(data).hexdigest(), "X-Sphere-Shift-Deg": str(shift)})
    if format == "svg":
        text = await asyncio.to_thread(SP.svg, gr, lo, hi, pts, title=prov, unit=G.METRIC_UNITS[m])
        data = text.encode()
        return Response(content=data, media_type="image/svg+xml",
                        headers={"X-Content-SHA256": hashlib.sha256(data).hexdigest(), "X-Sphere-Shift-Deg": str(shift)})
    return ok({"campaign_id": campaign_id, "header": hd, "metric": m, "unit": G.METRIC_UNITS[m], "group": g, "thickness_axis": axis,
               "grid": {"lon0": -180.0, "lat0": -90.0, "step_deg": 1.0, "n_lon": SP.LON_N, "n_lat": SP.LAT_N,
                        "values": [[float(f"{v:.6g}") for v in row] for row in gr], "min": lo, "max": hi},
               "interpolation": {"neighbors": SP.K, "weight": "1/max(theta_deg, 0.5)^2", "min_deg": SP.MIN_DEG},
               "shift_deg": shift, "points": pts, "provenance": prov, "environment": settings.environment}, message=prov)


# ── ⑤-4 자리(DF-10) ─────────────────────────────────────────────────────────

class SiteMetricItem(_Strict):
    part: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    metric: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    value: float | None = Field(default=None, allow_inf_nan=False)
    time_ms: float | None = Field(default=None, allow_inf_nan=False)
    elem_id: int | None = Field(default=None, ge=0)
    ratio: float | None = Field(default=None, allow_inf_nan=False)


class SiteImpactor(_Strict):
    mass_g: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    height_mm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    ke_mj: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class SiteItem(_Strict):
    site_id: _Key
    face: Literal["TOP", "BOT"] | None = None
    col: int | None = None
    row: int | None = None
    x_mm: float | None = Field(default=None, allow_inf_nan=False)
    y_mm: float | None = Field(default=None, allow_inf_nan=False)
    under_category: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None
    impactor: SiteImpactor | None = None
    run_key: str | None = Field(default=None, min_length=1, max_length=128, pattern=r"^[^\s\x00-\x1f\x7f]+$")
    footprint: dict[str, str | int | float | bool | None] | None = None   # {measured: bool, …}
    metrics: list[SiteMetricItem] | None = Field(default=None, max_length=2000)


class SitesBody(_Strict):
    sites: list[SiteItem] = Field(max_length=_ROWS_MAX)


@router.put("/{campaign_id}/sites")
async def set_campaign_sites(campaign_id: str, body: SitesBody, user: User = Depends(get_current_user),
                             db: AsyncSession = Depends(get_db)):
    """부분충격 자리 표를 통째로 바꾼다(DF-10) — 자리 · 면(TOP · BOT) · 열 · 행 · x · y · 받침 분류 · 충격추 · 그 자리를 친 런 · footprint
    (`measured` 가 참이어야 실측으로 본다) · 자리 지표(부품 · 지표 · 값 · 시각 ms · 요소 · 비). 빈 목록이면 지운다. 같은 site_id 가 둘이면 422."""
    c = await _campaign(db, user, campaign_id)
    keys = [s.site_id for s in body.sites]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:
        raise HTTPException(_UNPROCESSABLE, f"같은 site_id 가 둘 이상입니다 — {', '.join(dup[:10])}")
    n = await A.set_sites(db, c.id, [s.model_dump(mode="json") for s in body.sites])
    return ok({"campaign_id": campaign_id, "sites": n, "environment": settings.environment}, message=f"자리 {n}개")


def _site_table(sites: list[dict], facts: dict[str, dict], crit: list[dict]) -> tuple[list[dict], dict]:
    """자리마다 지표(받은 것, 없으면 묶인 런의 리포트 피크 · 건강 에너지비) · 기준 대비 비 · 덮임."""
    by_part_axis = {(str(b["part_id"]), b["metric_axis"]): b for b in crit if b["part_id"] is not None}
    rows, missing = [], []
    for s in sites:
        mets = list(s["metrics"])
        source = "site_metrics" if mets else None
        f = facts.get(s["run_key"]) if s["run_key"] else None
        if not mets and f and f.get("parts_metrics") is not None:
            source = "run_report"
            for pid, pm in f["parts_metrics"].items():
                for k in ("peak_stress", "peak_principal_strain", "peak_g", "peak_disp"):
                    if isinstance(pm, dict) and pm.get(k) is not None:
                        mets.append({"part": str(pid), "metric": k, "value": pm[k], "time_ms": None, "elem_id": None, "ratio": None})
            er = (f.get("health") or {}).get("energy_ratio_max")
            if er is not None:
                mets.append({"part": "model", "metric": "energy_ratio_max", "value": er, "time_ms": None, "elem_id": None, "ratio": None})
        for m in mets:
            b = by_part_axis.get((m["part"], m["metric"]))
            if m.get("ratio") is None and b is not None and m.get("value") is not None:
                m["ratio"] = m["value"] / b["criterion_value"]
                m["criterion"] = b["criterion_value"]
        if not mets:
            missing.append(s["site_id"])
        ratios = [m["ratio"] for m in mets if m.get("ratio") is not None]
        rows.append({k: s[k] for k in ("site_id", "face", "col", "row", "x_mm", "y_mm", "under_category", "impactor", "run_key")}
                    | {"footprint_measured": bool((s["footprint"] or {}).get("measured") is True), "source": source,
                       "metrics": mets, "max_ratio": max(ratios) if ratios else None})
    measured = bool(sites) and all(r["footprint_measured"] for r in rows)
    cov = {"sites": len(sites), "with_results": len(sites) - len(missing), "missing": missing,
           "by_face": {f: sum(1 for s in sites if s["face"] == f) for f in sorted({s["face"] for s in sites}, key=str)},
           "footprints_are_measured": measured}
    if sites and not measured:
        cov["warning"] = "footprint 가 실측이라고 받지 않은 자리가 있다 — 자리 지도의 footprint 는 합성이다"
    return rows, cov


@router.get("/{campaign_id}/sites")
async def campaign_site_table(campaign_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """부분충격 자리 표(DF-10) — 자리마다 위치 · 받침 · 지표(부품 피크 · 접촉력 · 이탈 시각 · 되튐 · 에너지비 — 받은 자리 지표, 없으면 묶인
    런의 리포트 피크 · 건강 에너지비) · 기준 대비 비(파트 기준값이 그 지표 축이면) · 가장 큰 비. 덮임 — 결과 없는 자리 목록 · 면별 수 ·
    footprint 실측 여부(아니면 경고)."""
    c = await _campaign(db, user, campaign_id)
    ss = await A.sites(db, c.id)
    facts = await A.run_facts(db, c.id, {s["run_key"] for s in ss if s["run_key"]})
    rows, cov = _site_table(ss, facts, await A.criteria(db, c.id))
    return ok({"campaign_id": campaign_id, "coverage": cov, "rows": rows, "environment": settings.environment},
              message=f"자리 {cov['sites']} · 결과 {cov['with_results']} · 빠진 자리 {len(cov['missing'])}")


def _site_svg(rows: list[dict], cov: dict, *, value_of, title: str) -> str:
    faces = [f for f in ("TOP", "BOT") if any(r["face"] == f for r in rows)] or [None]
    W, H, pad = 420, 320, 30
    vals = [v for r in rows if (v := value_of(r)) is not None]
    lo, hi = (min(vals), max(vals)) if vals else (0.0, 1.0)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{len(faces) * (W + pad) + pad}" height="{H + 90}" font-family="sans-serif">',
           '<rect width="100%" height="100%" fill="white"/>', f'<text x="{pad}" y="20" font-size="13">{SP._esc(title)}</text>']
    for k, face in enumerate(faces):
        rs = [r for r in rows if r["face"] == face and r["x_mm"] is not None and r["y_mm"] is not None]
        x0 = pad + k * (W + pad)
        out.append(f'<rect x="{x0}" y="35" width="{W}" height="{H}" fill="none" stroke="#999"/>')
        out.append(f'<text x="{x0}" y="{H + 52}" font-size="11">{face or "(면 없음)"} · {len(rs)} 자리</text>')
        if not rs:
            continue
        xs, ys = [r["x_mm"] for r in rs], [r["y_mm"] for r in rs]
        sx = (W - 20) / ((max(xs) - min(xs)) or 1.0)
        sy = (H - 20) / ((max(ys) - min(ys)) or 1.0)
        sc = min(sx, sy)
        for r in rs:
            cx = x0 + 10 + (r["x_mm"] - min(xs)) * sc
            cy = 35 + H - 10 - (r["y_mm"] - min(ys)) * sc
            v = value_of(r)
            if v is None:
                out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="none" stroke="red"/>')
            else:
                col = SP.PALETTE[SP._band(v, lo, hi)]
                out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="rgb{col}"/>')
    note = f"값 {lo:.4g} ~ {hi:.4g} · 빈 빨간 원 = 결과 없는 자리 {len(cov['missing'])}"
    if cov.get("warning"):
        note += " · " + cov["warning"]
    out.append(f'<text x="{pad}" y="{H + 75}" font-size="10">{SP._esc(note)}</text>')
    out.append("</svg>")
    return "\n".join(out)


@router.get("/{campaign_id}/site-map")
async def campaign_site_map(
    campaign_id: str,
    metric: str | None = Query(default=None, max_length=64, description="칠할 지표 — 비우면 자리의 가장 큰 기준 대비 비(max_ratio)"),
    part: str | None = Query(default=None, max_length=64, description="그 지표의 부품(비우면 자리의 그 지표 최댓값)"),
    format: Literal["json", "svg"] = Query(default="svg", description="svg(면마다 자리 지도) · json(자리 점 · 값)"),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """부분충격 자리 지도(DF-10) — 면(TOP · BOT)마다 자리 점을 값으로 칠하고 결과 없는 자리는 빈 빨간 원으로. footprint 가 실측이 아니면
    그림 아래에 경고를 쓴다(합성 — 11-21 「생성기에 청하고 기다린다」)."""
    c = await _campaign(db, user, campaign_id)
    ss = await A.sites(db, c.id)
    facts = await A.run_facts(db, c.id, {s["run_key"] for s in ss if s["run_key"]})
    rows, cov = _site_table(ss, facts, await A.criteria(db, c.id))

    def value_of(r):
        if metric is None:
            return r["max_ratio"]
        vs = [m["value"] for m in r["metrics"] if m["metric"] == metric and (part is None or m["part"] == part) and m["value"] is not None]
        return max(vs) if vs else None
    title = f"{c.name} · {'max_ratio' if metric is None else metric}{'' if part is None else ' · 부품 ' + part}"
    if format == "svg":
        data = _site_svg(rows, cov, value_of=value_of, title=title).encode()
        return Response(content=data, media_type="image/svg+xml", headers={"X-Content-SHA256": hashlib.sha256(data).hexdigest()})
    pts = [{"site_id": r["site_id"], "face": r["face"], "x_mm": r["x_mm"], "y_mm": r["y_mm"], "value": value_of(r)} for r in rows]
    return ok({"campaign_id": campaign_id, "coverage": cov, "metric": metric, "part": part, "points": pts,
               "environment": settings.environment}, message=title)


# ── ⑤-5 파트 짝 표 · 리비전 비교(DF-11) ─────────────────────────────────────

class PartMapRow(_Strict):
    a_pid: int | None = Field(default=None, gt=0)
    b_pid: int | None = Field(default=None, gt=0)
    basis: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    center_dist_mm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    size_rel_diff: float | None = Field(default=None, allow_inf_nan=False)
    title_token_jaccard: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    role: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None

    @model_validator(mode="after")
    def _a_or_b(self):
        if self.a_pid is None and self.b_pid is None:
            raise ValueError("a_pid · b_pid 가운데 하나는 있어야 합니다")
        return self


class PartMapBody(_Strict):
    from_model: _Text
    to_model: _Text
    label: _Text | None = None
    rows: list[PartMapRow] = Field(min_length=1, max_length=20000)


@part_maps_router.post("", status_code=status.HTTP_201_CREATED)
async def import_part_map(body: PartMapBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """파트 짝 표를 올린다(DF-11) — 행마다 a_pid · b_pid(한쪽만이면 사라진 · 새로 생긴 파트) · 짝 근거 `basis`(필수 — `name` 뿐인 짝은
    비교에 쓰지 않는다) · 중심 거리 · 크기 차 · 제목 낱말 자카드 · 역할. 응답의 `map_id` 로 비교한다. 만든 사람만 본다."""
    row = await A.create_part_map(db, user.id, {"from_model": body.from_model, "to_model": body.to_model, "label": body.label,
                                                "rows": [r.model_dump() for r in body.rows]})
    return ok({**A.part_map_dict(row), "environment": settings.environment}, message=f"파트 짝 표 {row.id} · 행 {len(body.rows)}",
              status_code=status.HTTP_201_CREATED)


@part_maps_router.get("/{map_id}")
async def get_part_map(map_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """파트 짝 표 하나(DF-11)."""
    row = await A.get_part_map(db, user.id, map_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "파트 짝 표를 찾을 수 없습니다.")
    return ok({**A.part_map_dict(row), "environment": settings.environment})


@router.get("/compare")
async def compare_campaigns(
    a: str = Query(min_length=1, max_length=26, description="앞 리비전 캠페인 id"),
    b: str = Query(min_length=1, max_length=26, description="뒤 리비전 캠페인 id"),
    part_map: str = Query(min_length=1, max_length=26, description="파트 짝 표 id(import_part_map 의 map_id)"),
    metric: str = Query(default="peak_stress", description="지표 하나 — 리포트 파트 지표 이름 또는 MET-* 별칭"),
    match: Literal["doe", "angle"] = Query(default="doe", description="각도 맞춤 — doe(같은 DOE) · angle(각거리 허용치 안)"),
    tol_deg: float = Query(default=5.0, gt=0, le=90, description="angle 맞춤의 각거리 허용치(도)"),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """리비전 비교(DF-11) — 공통 각도만 쓴다(n 을 싣는다). 짝마다 각도별 비 b / a 의 가운데값 · 상위 5 합(각 캠페인의 가장 큰 다섯 값 합)과
    그 비 · 크기(상 · 중 · 하). 머리에 크기별 수 · 상위 5 짝. `name` 근거뿐인 짝은 쓰지 않고 센다 · 짝 없는 파트(사라진 · 새로 생긴) ·
    값을 못 맞춘 짝."""
    ca, cb = await _campaign(db, user, a), await _campaign(db, user, b)
    pm = await A.get_part_map(db, user.id, part_map)
    if pm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "파트 짝 표를 찾을 수 없습니다.")
    m = _metric(metric)
    ra, ha, runs_a = await _rows(db, ca, metrics=[], groups=[], thickness_axis=_axis(ca, None), include_invalid=False,
                                 include_ke_jump=False, config_generation=None, keep_pm=True)
    rb, hb, runs_b = await _rows(db, cb, metrics=[], groups=[], thickness_axis=_axis(cb, None), include_invalid=False,
                                 include_ke_jump=False, config_generation=None, keep_pm=True)
    pairs = G.match_angles(ra, rb, mode=match, tol_deg=tol_deg)
    used, name_only, unmatched, results = [], 0, [], []
    for row in pm.rows:
        if row.get("basis", "").strip().lower() == "name":
            name_only += 1
            continue
        if row.get("a_pid") is None or row.get("b_pid") is None:
            continue
        ap, bp = str(row["a_pid"]), str(row["b_pid"])
        va = [G._num((x["_pm"].get(ap) or {}).get(m)) for x, _y in pairs]
        vb = [G._num((y["_pm"].get(bp) or {}).get(m)) for _x, y in pairs]
        both = [(p, q) for p, q in zip(va, vb) if p is not None and q is not None]
        if not both:
            unmatched.append({"a_pid": row["a_pid"], "b_pid": row["b_pid"], "basis": row.get("basis")})
            continue
        ratios = sorted(q / p for p, q in both if p > 0)
        med = G.quantile(ratios, 0.5)
        ta = sum(sorted((p for p, _ in both), reverse=True)[:5])
        tb = sum(sorted((q for _, q in both), reverse=True)[:5])
        results.append({"a_pid": row["a_pid"], "b_pid": row["b_pid"], "basis": row.get("basis"), "role": row.get("role"), "n": len(both),
                        "median_ratio": med, "top5_sum_a": ta, "top5_sum_b": tb, "top5_ratio": (tb / ta) if ta else None,
                        "size": G.size_class(med)})
        used.append(row)
    # 짝을 믿는 행(양쪽이 있고 근거가 name 뿐이 아닌 것)으로 덮인 파트만 짝 있음 — name 짝뿐인 파트는 사라진 · 새로 생긴 쪽에 든다
    trusted = [r for r in pm.rows if r.get("a_pid") is not None and r.get("b_pid") is not None
               and r.get("basis", "").strip().lower() != "name"]
    a_ids = {str(r["a_pid"]) for r in trusted}
    b_ids = {str(r["b_pid"]) for r in trusted}
    pa = {pid for x in ra for pid in x["_pm"]}
    pb = {pid for x in rb for pid in x["_pm"]}
    size = {k: sum(1 for r in results if r["size"] == k) for k in ("high", "mid", "low")}
    top5 = sorted((r for r in results if r["median_ratio"]), key=lambda r: -abs(math.log2(r["median_ratio"])))[:5]
    head = {"common_angles": len(pairs), "match": match, "tol_deg": tol_deg if match == "angle" else None, "metric": m,
            "pairs_compared": len(results), "size_counts": size, "top5": top5, "name_only_skipped": name_only,
            "unmatched_pairs": len(unmatched), "a": {"campaign_id": a, "header": ha}, "b": {"campaign_id": b, "header": hb}}
    return ok({"header": head, "pairs": results, "unmatched": unmatched,
               "disappeared_parts": sorted(pa - a_ids, key=lambda s: (len(s), s)), "new_parts": sorted(pb - b_ids, key=lambda s: (len(s), s)),
               "part_map": {"map_id": pm.id, "from_model": pm.from_model, "to_model": pm.to_model},
               "environment": settings.environment},
              message=f"공통 각도 {len(pairs)} · 짝 {len(results)} · 크기 상 {size['high']} · 중 {size['mid']} · 하 {size['low']}")


# ── ⑤-6 쌍 규칙 · 설정 쌍 비교(DF-12) ───────────────────────────────────────

class PairMetricItem(_Strict):
    metric: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    group_key: _Key | None = None
    max_diff_pct: float = Field(gt=0, allow_inf_nan=False)


class PairRuleBody(_Strict):
    metrics: list[PairMetricItem] = Field(min_length=1, max_length=50)
    rank_corr_min: float = Field(default=0.9, ge=-1, le=1, allow_inf_nan=False)
    max_failed_pairs: int = Field(default=2, ge=0)


@router.put("/{campaign_id}/pair-rule")
async def set_campaign_pair_rule(campaign_id: str, body: PairRuleBody, user: User = Depends(get_current_user),
                                 db: AsyncSession = Depends(get_db)):
    """설정 쌍 합격 규칙(DF-12) — 지표 · 무리(비우면 all)마다 최대 차 %, 순위 상관 하한(기본 0.9), 넘은 쌍 상한(기본 2 — 넘으면 전량
    재실행). 통째로 바꾼다."""
    c = await _campaign(db, user, campaign_id)
    rule = {"metrics": [{"metric": _metric(x.metric), "group_key": x.group_key, "max_diff_pct": x.max_diff_pct} for x in body.metrics],
            "rank_corr_min": body.rank_corr_min, "max_failed_pairs": body.max_failed_pairs}
    got = await A.set_pair_rule(db, c, rule)
    return ok({"campaign_id": campaign_id, "pair_rule": got, "environment": settings.environment},
              message=f"쌍 규칙 — 지표 {len(rule['metrics'])} · 순위 상관 ≥ {rule['rank_corr_min']} · 넘은 쌍 ≤ {rule['max_failed_pairs']}")


@router.get("/{campaign_id}/config-pairs")
async def compare_config_pairs(
    campaign_id: str,
    old: str = Query(min_length=1, max_length=64, description="옛 설정 세대(config_generation)"),
    new: str = Query(min_length=1, max_length=64, description="새 설정 세대(config_generation)"),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """설정 쌍 비교(DF-12) — 같은 DOE 를 옛 · 새 세대로 돌린 쌍마다 규칙의 지표 · 무리별 차 %(새 − 옛) / 옛 · 순위 상관(스피어먼) · 넘은 쌍
    수 · 판정(pass · rerun_required · no_pairs). 옛 세대 런이 새 세대로 대체돼 있어도 넣는다(대체 까닭만 무시한다)."""
    c = await _campaign(db, user, campaign_id)
    if not c.pair_rule:
        raise HTTPException(_UNPROCESSABLE, "쌍 규칙이 없습니다 — set_campaign_pair_rule 로 먼저 둡니다.")
    groups = await A.part_groups(db, c.id)
    keys = {g["group_key"] for g in groups} | ({"all"} if not groups else set())
    bad = sorted({x.get("group_key") or "all" for x in c.pair_rule["metrics"]} - keys)
    if bad:
        raise HTTPException(_UNPROCESSABLE, f"쌍 규칙의 무리가 캠페인에 없습니다 — {', '.join(bad)}")
    ms = sorted({x["metric"] for x in c.pair_rule["metrics"]})
    ro, ho, _ = await _rows(db, c, metrics=ms, groups=groups, thickness_axis=_axis(c, None), include_invalid=False, include_ke_jump=False,
                            config_generation=old, ignore_superseded=True)
    rn, hn, _ = await _rows(db, c, metrics=ms, groups=groups, thickness_axis=_axis(c, None), include_invalid=False, include_ke_jump=False,
                            config_generation=new, ignore_superseded=True)
    got = G.config_pairs(ro, rn, c.pair_rule)
    return ok({"campaign_id": campaign_id, "old": {"config_generation": old, "header": ho}, "new": {"config_generation": new, "header": hn},
               "pair_rule": c.pair_rule, **got, "environment": settings.environment},
              message=f"쌍 {got['common_doe']} · 넘은 쌍 {got['failed_pairs']} · 판정 {got['verdict']}")
