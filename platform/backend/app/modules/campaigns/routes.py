# 캠페인 REST 라우트 (/api/v1/campaigns) — 만들기 · 런 목록 올리기 · 적재 상태. 리포트 본문은 /reports/intake 로 온다.
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Campaign, User
from app.modules.campaigns import services as svc
from app.reports.datahub import DataHubError, parse_stage
from app.shared.auth import get_current_user
from app.shared.responses import fail, ok

router = APIRouter(tags=["campaigns"], prefix="/campaigns")

_UNPROCESSABLE = 422
_DOE_MAX = 64
_RUNS_MAX = 5000


class _Strict(BaseModel):
    # 모르는 칸은 조용히 버리지 않고 422 — 칸 이름을 틀리면 값이 빈 채로 들어간다
    model_config = ConfigDict(extra="forbid")


class ImpactorBody(_Strict):
    mass_g: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    height_mm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    ke_mj: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class CampaignBody(_Strict):
    name: str = Field(min_length=1, max_length=255)
    project: str | None = Field(default=None, max_length=64)   # 과제명 — intake 폼의 project 와 같은 길이
    dev_rev: str | None = Field(default=None, max_length=8)    # 개발단계 (pre|dv1..dvr|pv..|pra|mp) — intake 와 같은 꼴
    analysis_method: str | None = Field(default=None, max_length=64)
    analysis_target: str | None = Field(default=None, max_length=64)
    doe_strategy: str | None = Field(default=None, max_length=64)
    drop_height_mm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    duration_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    thickness_axis: Literal["X", "Y", "Z", "x", "y", "z"] | None = None
    impactor: ImpactorBody | None = None


class RunItem(_Strict):
    # 빈칸 · 제어 문자 없는 글 — `stcx:<잡 id>:<DOE>` 꼴을 권한다(꼴은 검사하지 않는다)
    run_key: str = Field(min_length=1, max_length=128, pattern=r"^[^\s\x00-\x1f\x7f]+$")
    doe: str | int | None = None
    pitch: float | None = Field(default=None, allow_inf_nan=False)
    roll: float | None = Field(default=None, allow_inf_nan=False)


class RunsBody(_Strict):
    runs: list[RunItem] = Field(min_length=1, max_length=_RUNS_MAX)


def _campaign_dict(c: Campaign) -> dict:
    return {
        "campaign_id": c.id, "name": c.name, "project": c.project, "dev_rev": c.dev_rev,
        "analysis_method": c.analysis_method, "analysis_target": c.analysis_target, "doe_strategy": c.doe_strategy,
        "drop_height_mm": c.drop_height_mm, "duration_ms": c.duration_ms, "thickness_axis": c.thickness_axis,
        "impactor": c.impactor, "created_at": c.created_at,
    }


async def _require_campaign(db: AsyncSession, user: User, campaign_id: str) -> Campaign:
    c = await svc.get_owned(db, user.id, campaign_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "캠페인을 찾을 수 없습니다.")
    return c


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_campaign(
    body: CampaignBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """캠페인(한 과제 · 한 판의 런 묶음)을 만든다. 같은 이름을 이미 썼으면 409 — 글과 `data.campaign_id` 가 그 id 다.

    그다음 `POST /campaigns/{id}/runs` 로 런 목록을 올리고, 런마다 `POST /reports/intake` 에 `campaign_id` · `run_key` 를
    붙여 리포트를 보낸다.
    """
    uid = user.id  # 이름이 겹쳐 되감으면 user 가 만료된다 — 먼저 꺼내 둔다
    fields = body.model_dump()
    fields["name"] = name = body.name.strip()
    if not name:
        raise HTTPException(_UNPROCESSABLE, "name 이 비었습니다.")
    if body.dev_rev:
        try:
            parse_stage(body.dev_rev)
        except DataHubError as exc:
            raise HTTPException(_UNPROCESSABLE, f"dev_rev — {exc}")
    if body.thickness_axis:
        fields["thickness_axis"] = body.thickness_axis.upper()
    row = await svc.create_campaign(db, uid, fields)
    if row is None:
        cid = await svc.find_by_name(db, uid, name)
        return fail(f"같은 이름의 캠페인이 이미 있습니다 — campaign_id {cid}", status_code=status.HTTP_409_CONFLICT,
                    data={"campaign_id": cid})
    return ok({**_campaign_dict(row), "environment": settings.environment},
              message="캠페인을 만들었습니다 — 런 목록을 POST /campaigns/{id}/runs 로 올리세요.",
              status_code=status.HTTP_201_CREATED)


@router.post("/{campaign_id}/runs")
async def ingest_campaign_manifest(
    campaign_id: str,
    body: RunsBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """런 목록(매니페스트)을 올린다 — 리포트를 받기 전에 「무엇이 올 것인가」 를 먼저 적는다.

    새 `run_key` 는 pending 으로 더하고, 있는 것은 상태 · 리포트를 둔 채 보낸 칸(doe · pitch · roll)만 맞춘다. 다시 올려도
    된다. 한 요청 안에 같은 `run_key` 가 둘이면 422 고, 목록에서 런을 빼는 길은 없다. 한 요청에 5,000 런까지.
    """
    c = await _require_campaign(db, user, campaign_id)
    items, seen, dup = [], set(), []
    for r in body.runs:
        if r.run_key in seen:
            dup.append(r.run_key)
        seen.add(r.run_key)
        it = r.model_dump(exclude_unset=True)
        if it.get("doe") is not None:
            it["doe"] = str(it["doe"])
            if len(it["doe"]) > _DOE_MAX:
                raise HTTPException(_UNPROCESSABLE, f"doe 가 너무 깁니다(최대 {_DOE_MAX}자) — run_key {r.run_key}")
        items.append(it)
    if dup:
        raise HTTPException(_UNPROCESSABLE,
                            f"한 요청 안에 같은 run_key 가 둘 이상입니다 — {', '.join(sorted(set(dup))[:10])}")
    got = await svc.upsert_runs(db, c.id, items)
    return ok({"campaign_id": campaign_id, **got, "environment": settings.environment},
              message=f"런 목록 {got['listed']}건(새로 {got['added']} · 고침 {got['updated']})")


@router.get("/{campaign_id}/ingest-status")
async def campaign_ingest_status(
    campaign_id: str,
    state: str | None = Query(default=None, description="이 상태의 런만 — pending · received · skipped · rejected"),
    limit: int = Query(default=200, ge=1, le=_RUNS_MAX),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """캠페인의 적재 상태 — 목록 수 · 상태별 수 · 런마다 상태 · report_id · 지문 · 거절 까닭.

    `counts.listed = pending + received + skipped + rejected` 다. `ingest_state` 는 그 런의 **마지막 시도 결과**고
    `report_id` 는 그 런이 **가진 리포트**라, 가진 리포트가 있는데 뒤에 다른 내용이 와 거절된 런은 rejected 이면서
    report_id 가 있다(`counts.with_report` 가 리포트를 가진 런 수다). 리포트가 지워진 런은 pending 으로 돌아온다.
    """
    c = await _require_campaign(db, user, campaign_id)
    if state is not None and state not in svc.STATES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"state 는 {list(svc.STATES)} 중 하나여야 합니다.")
    got = await svc.ingest_status(db, c.id, state=state, limit=limit, offset=offset)
    return ok({"campaign": _campaign_dict(c), **got, "limit": limit, "offset": offset,
               "environment": settings.environment})
