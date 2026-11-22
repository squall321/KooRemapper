# 캠페인 REST 라우트 (/api/v1/campaigns) — 만들기 · 런 목록 올리기 · 적재 상태 · 출처 · 건강. 리포트 본문은 /reports/intake 로 온다.
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Campaign, User
from app.modules.campaigns import extraction as X
from app.modules.campaigns import health as H
from app.modules.campaigns import services as svc
from app.reports.datahub import DataHubError, parse_stage
from app.shared.auth import get_current_user
from app.shared.responses import fail, ok

router = APIRouter(tags=["campaigns"], prefix="/campaigns")

_UNPROCESSABLE = 422
_DOE_MAX = 64
_RUNS_MAX = 5000
_FIELDS_MAX = 1000      # 런 하나가 싣는 추출 장 수
_REQUIRED_MAX = 200     # 캠페인의 필수 추출 항목 수
_PARTS_MAX = 10000
_FieldName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class _Strict(BaseModel):
    # 모르는 칸은 조용히 버리지 않고 422 — 칸 이름을 틀리면 값이 빈 채로 들어간다
    model_config = ConfigDict(extra="forbid")


class ImpactorBody(_Strict):
    mass_g: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    height_mm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    ke_mj: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class ThresholdsBody(_Strict):
    # 건강 판정 문턱(DF-03) — 안 보낸 열쇠 · null 은 기본값(campaigns/health.py `DEFAULTS`). 미끄럼 에너지는 문턱이 없다
    energy_ratio_max: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    hg_over_ie_max: float | None = Field(default=None, gt=0, allow_inf_nan=False)       # 비 — 0.10 이 10 %
    added_mass_pct_max: float | None = Field(default=None, ge=0, allow_inf_nan=False)   # 백분율
    ke0_rel_tol: float | None = Field(default=None, ge=0, allow_inf_nan=False)          # 첫 KE 와 ½mv² 의 상대 차이
    contact_energy_min_mJ: float | None = Field(default=None, allow_inf_nan=False)


class RequiredItem(_Strict):
    # 필수 추출 한 항목(DF-04) — parts 가 없으면 「모든 파트」, states 기본 all(모든 상태를 읽은 추출이어야 한다)
    field: _FieldName
    parts: list[Annotated[int, Field(gt=0)]] | None = Field(default=None, max_length=_PARTS_MAX)
    states: Literal["all", "sampled"] = "all"


def _required_items(items: list[RequiredItem] | None) -> list[dict]:
    """필수 목록 → 저장 꼴(파트는 정렬 · 겹침 없이). 같은 field · parts · states 가 둘이면 422."""
    out, seen = [], set()
    for it in items or []:
        parts = None if it.parts is None else sorted(set(it.parts))
        key = (X.field_key(it.field), tuple(parts) if parts is not None else None, it.states)
        if key in seen:
            raise HTTPException(_UNPROCESSABLE, f"required_extractions 에 같은 항목이 둘입니다 — field {it.field!r}")
        seen.add(key)
        out.append({"field": it.field, "parts": parts, "states": it.states})
    return out


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
    health_thresholds: ThresholdsBody | None = None   # 건강 판정 문턱 — 나중엔 PUT /campaigns/{id}/health-thresholds
    # 필수 추출 목록(DF-04) — 삭제 허가가 본다. 나중엔 PUT /campaigns/{id}/required-extractions
    required_extractions: list[RequiredItem] | None = Field(default=None, max_length=_REQUIRED_MAX)


class ProvenanceBody(_Strict):
    # 런 출처(DF-02) — 요청서 표의 열쇠 그대로. 모르는 열쇠는 422(만드는 쪽의 꼴이 다르면 바로 보이게)
    wrapper_name: str | None = Field(default=None, max_length=128)
    wrapper_version: str | None = Field(default=None, max_length=64)
    prescription_set: str | None = Field(default=None, max_length=128)
    scenario_sha256: str | None = Field(default=None, max_length=128)
    runner_config_sha256: str | None = Field(default=None, max_length=128)
    deck_sha256: str | None = Field(default=None, max_length=128)
    include_sha256: list[str] | None = Field(default=None, max_length=1000)
    # 판 · MPP/SMP · 코어 수 — 요청서가 열쇠 이름을 적지 않아 글 · 숫자 값의 객체를 그대로 받는다
    solver: dict[str, str | int | float | bool | None] | None = None
    sif_version: str | None = Field(default=None, max_length=64)
    deep_report_tool_commit: str | None = Field(default=None, max_length=64)
    deep_report_flags: str | list[str] | None = None
    submitted_at: datetime | None = None


class HealthBody(_Strict):
    # 런 건강 수치(DF-03) — 요청서 표의 칸 그대로. 판정은 읽을 때 캠페인 문턱으로 센다
    normal_termination: bool | None = None            # d3hsp 근거 정상 종료
    scheduler_state: str | None = Field(default=None, max_length=64)   # 참고 칸(Slurm 상태) — 판정에 쓰지 않는다
    energy_ratio_max: float | None = Field(default=None, allow_inf_nan=False)
    hg_over_ie_max: float | None = Field(default=None, allow_inf_nan=False)          # 비 — 0.10 이 10 %
    added_mass_pct_device: float | None = Field(default=None, allow_inf_nan=False)   # 낙하판 뺀 값(%)
    added_mass_pct_total: float | None = Field(default=None, allow_inf_nan=False)    # 낙하판 포함 값(%)
    ke0_measured: float | None = Field(default=None, allow_inf_nan=False)
    ke0_expected: float | None = Field(default=None, allow_inf_nan=False)            # ½mv²
    contact_energy_min_mJ: float | None = Field(default=None, allow_inf_nan=False)
    nan_onset_ms: float | None = Field(default=None, allow_inf_nan=False)            # 없으면 null
    json_complete: bool | None = None


class FieldItem(_Strict):
    # 뽑은 장 하나(DF-04) — parts 가 없으면 「모든 파트」, states 가 없으면 런의 상태 수로 정한다(read = total 이면 all)
    field: _FieldName
    parts: list[Annotated[int, Field(gt=0)]] | None = Field(default=None, max_length=_PARTS_MAX)
    states: Literal["all", "sampled"] | None = None


class ExtractionBody(_Strict):
    # 런 추출 목록(DF-04) — 요청서 표의 칸 그대로. 허가 · 피크 표지는 읽을 때 캠페인의 필수 목록으로 센다
    d3plot_states_total: int | None = Field(default=None, ge=0)
    d3plot_states_read: int | None = Field(default=None, ge=0)
    peak_source: Literal["binout", "elout", "d3plot_full", "d3plot_sampled"] | None = None
    fields_extracted: list[_FieldName | FieldItem] | None = Field(default=None, max_length=_FIELDS_MAX)   # 글 하나 = {field: 그 글}
    d3plot_retained: bool | None = None
    d3plot_deleted_at: datetime | None = None

    @model_validator(mode="after")
    def _read_le_total(self):
        t, r = self.d3plot_states_total, self.d3plot_states_read
        if t is not None and r is not None and r > t:
            raise ValueError(f"d3plot_states_read({r}) 가 d3plot_states_total({t}) 보다 큽니다")
        return self


class RunItem(_Strict):
    # 빈칸 · 제어 문자 없는 글 — `stcx:<잡 id>:<DOE>` 꼴을 권한다(꼴은 검사하지 않는다)
    run_key: str = Field(min_length=1, max_length=128, pattern=r"^[^\s\x00-\x1f\x7f]+$")
    doe: str | int | None = None
    pitch: float | None = Field(default=None, allow_inf_nan=False)
    roll: float | None = Field(default=None, allow_inf_nan=False)
    # ② 출처 · 유효성(DF-02 · DF-03) — 보낸 칸만 맞춘다(null 은 비운다)
    provenance: ProvenanceBody | None = None
    config_generation: str | None = Field(default=None, min_length=1, max_length=64)
    superseded_by: str | None = Field(default=None, min_length=1, max_length=128, pattern=r"^[^\s\x00-\x1f\x7f]+$")
    health: HealthBody | None = None
    extraction: ExtractionBody | None = None          # ③ 추출 목록(DF-04)


class RunsBody(_Strict):
    runs: list[RunItem] = Field(min_length=1, max_length=_RUNS_MAX)


def _campaign_dict(c: Campaign) -> dict:
    return {
        "campaign_id": c.id, "name": c.name, "project": c.project, "dev_rev": c.dev_rev,
        "analysis_method": c.analysis_method, "analysis_target": c.analysis_target, "doe_strategy": c.doe_strategy,
        "drop_height_mm": c.drop_height_mm, "duration_ms": c.duration_ms, "thickness_axis": c.thickness_axis,
        "impactor": c.impactor, "health_thresholds": H.bundle(c.health_thresholds),
        "required_extractions": c.required_extractions, "created_at": c.created_at,
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
    # 문턱은 기본값에서 바꾼 열쇠만 둔다(안 보냈거나 기본값과 같으면 null)
    changed = {k: v for k, v in (body.health_thresholds.model_dump(exclude_none=True) if body.health_thresholds else {}).items()
               if v != H.DEFAULTS[k]}
    fields["health_thresholds"] = changed or None
    fields["required_extractions"] = _required_items(body.required_extractions) or None
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

    새 `run_key` 는 pending 으로 더하고, 있는 것은 상태 · 리포트를 둔 채 보낸 칸(doe · pitch · roll · provenance ·
    config_generation · superseded_by · health · extraction)만 맞춘다 — 객체 칸은 통째로 바꾸고 null 은 비운다. 다시 올려도 된다. 한 요청
    안에 같은 `run_key` 가 둘이면 422 고, 목록에서 런을 빼는 길은 없다. 한 요청에 5,000 런까지. `superseded_by` 는 같은
    캠페인의 다른 run_key 여야 한다(같은 요청에서 더하는 런도 된다 · 자기 자신 · 고리는 422).
    """
    c = await _require_campaign(db, user, campaign_id)
    items, seen, dup = [], set(), []
    for r in body.runs:
        if r.run_key in seen:
            dup.append(r.run_key)
        seen.add(r.run_key)
        it = r.model_dump(exclude_unset=True, mode="json")   # 시각은 ISO 글로 — JSONB 에 그대로 둔다
        if it.get("doe") is not None:
            it["doe"] = str(it["doe"])
            if len(it["doe"]) > _DOE_MAX:
                raise HTTPException(_UNPROCESSABLE, f"doe 가 너무 깁니다(최대 {_DOE_MAX}자) — run_key {r.run_key}")
        items.append(it)
    if dup:
        raise HTTPException(_UNPROCESSABLE,
                            f"한 요청 안에 같은 run_key 가 둘 이상입니다 — {', '.join(sorted(set(dup))[:10])}")
    try:
        got = await svc.upsert_runs(db, c.id, items)
    except svc.BadManifest as exc:
        raise HTTPException(_UNPROCESSABLE, str(exc))
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


@router.put("/{campaign_id}/health-thresholds")
async def set_campaign_health_thresholds(
    campaign_id: str,
    body: ThresholdsBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """캠페인의 건강 판정 문턱을 바꾼다 — 안 보낸 열쇠 · null 은 기본값이다(빈 몸이면 모두 기본값으로).

    기본값 — 에너지비 ≤ 1.05 · HG/IE < 0.10 · 추가 질량 0.5 % 넘으면 warn · 첫 KE 가 ½mv² 와 10 % 넘게 다르면 warn · 자체 접촉
    에너지 −100 mJ 아래 warn. 미끄럼 에너지는 문턱이 없다. 판정은 읽을 때 세므로 바꾼 문턱이 곧바로 건강 표에 든다.
    """
    c = await _require_campaign(db, user, campaign_id)
    tb = await svc.set_thresholds(db, c, body.model_dump(exclude_none=True))
    return ok({"campaign_id": campaign_id, "thresholds": tb, "environment": settings.environment},
              message=("문턱을 바꿨습니다 — " + ", ".join(tb["changed"])) if tb["changed"] else "문턱을 기본값으로 두었습니다.")


@router.get("/{campaign_id}/provenance")
async def campaign_provenance(
    campaign_id: str,
    config_generation: str | None = Query(default=None, max_length=64, description="이 설정 세대의 런만"),
    limit: int = Query(default=200, ge=1, le=_RUNS_MAX),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """캠페인의 런 출처 — 설정 세대별 런 수 · `mixed_config`(이름표가 붙은 세대가 둘 이상) · 출처가 빈 런 수 · 대체된 런 수 ·
    런마다 출처(`provenance` · `config_generation` · `superseded_by`). 세대가 이름표 없는 런은 `config_generation: null` 로 센다.
    """
    c = await _require_campaign(db, user, campaign_id)
    got = await svc.provenance_view(db, c, config_generation=config_generation, limit=limit, offset=offset)
    return ok({"campaign_id": campaign_id, **got, "limit": limit, "offset": offset, "environment": settings.environment})


@router.get("/{campaign_id}/health")
async def campaign_health_table(
    campaign_id: str,
    include_invalid: bool = Query(default=False, description="true 면 invalid · 대체 · 출처 빈 런도 싣는다"),
    limit: int = Query(default=200, ge=1, le=_RUNS_MAX),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """캠페인의 런 건강 표 — 머리 줄(유효 n / 전체 N · 제외 까닭별 건수) · 판정에 쓴 문턱 묶음(`ref`) · 런마다 건강 수치 ·
    판정(`validity` {status: valid | warn | invalid, reasons}) · 제외 까닭(`excluded_by`).

    기본은 통계에 넣는 런(valid · warn 이면서 대체되지 않고 출처가 있는 런)만 싣는다. 리포트가 없는 런은 `no_report`, 건강 수치가
    없는 런은 `health_missing` 으로 invalid 다(스케줄러 상태만으로 valid 로 보지 않는다).
    """
    c = await _require_campaign(db, user, campaign_id)
    got = await svc.health_table(db, c, include_invalid=include_invalid, limit=limit, offset=offset)
    return ok({"campaign_id": campaign_id, **got, "limit": limit, "offset": offset, "environment": settings.environment},
              message=got["header"]["line"])


class RequiredBody(_Strict):
    required_extractions: list[RequiredItem] = Field(max_length=_REQUIRED_MAX)


@router.put("/{campaign_id}/required-extractions")
async def set_campaign_required_extractions(
    campaign_id: str,
    body: RequiredBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """캠페인의 필수 추출 목록을 통째로 바꾼다(DF-04) — 빈 목록이면 지운다. 항목은 `field`(자유 글 — 견줄 때 대소문자 · 앞뒤 공백을
    가리지 않는다) · `parts`(정수 목록 · 없으면 모든 파트) · `states`(`all` · `sampled`, 기본 all).

    목록이 없는 캠페인은 모든 런의 삭제가 보류다(`required_extractions_unset` — 무엇을 지켜야 할지 모르면 지워도 된다고 하지 않는다).
    """
    c = await _require_campaign(db, user, campaign_id)
    got = await svc.set_required(db, c, _required_items(body.required_extractions))
    return ok({"campaign_id": campaign_id, "required_extractions": got, "environment": settings.environment},
              message=f"필수 추출 {len(got or [])}항목" if got else "필수 추출 목록을 지웠습니다 — 모든 런의 삭제가 보류됩니다.")


@router.get("/{campaign_id}/deletion-clearance")
async def campaign_deletion_clearance(
    campaign_id: str,
    status_: Literal["allow", "hold", "deleted"] | None = Query(default=None, alias="status",
                                                                 description="이 허가 상태의 런만 — allow · hold · deleted"),
    limit: int = Query(default=200, ge=1, le=_RUNS_MAX),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """캠페인의 d3plot 삭제 허가(DF-04) — **조회만** 한다(지우기는 KooChainRun KC-05). 머리 줄(허가 · 보류 · 이미 지움 수와
    까닭별 수) · 필수 목록 · 런마다 추출 · 피크 표지 · 허가(`clearance` {status: allow | hold | deleted, reasons, missing}).

    보류 까닭 — `required_extractions_unset` · `no_report` · `extraction_missing` · `extraction_incomplete`(빠진 항목은 `missing` —
    항목마다 `field_missing` · `parts_missing` · `states_sampled` · `states_unknown`). 이미 지운 런은 `deleted` 이고 빠진 항목이 있으면
    `extraction_lost` 를 단다(다시 못 뽑는다).
    """
    c = await _require_campaign(db, user, campaign_id)
    got = await svc.clearance_table(db, c, status=status_, limit=limit, offset=offset)
    return ok({"campaign_id": campaign_id, **got, "limit": limit, "offset": offset, "environment": settings.environment},
              message=got["header"]["line"])
