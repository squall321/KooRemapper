# 전사 코퍼스 통계 API — 인증만 되면 누구나. 개인 식별 정보는 담지 않는다.
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.shared.auth import get_current_user
from app.shared.responses import ok

from . import services as svc

router = APIRouter(tags=["corpus"])


@router.get("/corpus/summary")
async def corpus_summary(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """모델 규모 감각 — 세션·파일·잡 수와 메시 규모 분포(전사, 개인 식별 없음)."""
    return ok(await svc.corpus_summary(db))


@router.get("/corpus/materials")
async def material_usage(
    limit: int = Query(default=30, ge=1, le=200),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """물성 카드별 사용 모델 수 — 시험 우선순위의 '실사용 빈도' 근거."""
    return ok(await svc.material_usage(db, limit=limit))


@router.get("/corpus/operations")
async def operation_usage(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """오퍼레이션 실행 이력 — 조직이 실제로 쓰는 전처리 관행."""
    return ok(await svc.operation_usage(db))


@router.get("/corpus/sections-contacts")
async def section_contact_usage(
    limit: int = Query(default=20, ge=1, le=200),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """요소 정식·접촉 카드 사용 분포 — 해석 설계 관행 근거."""
    return ok(await svc.section_contact_usage(db, limit=limit))


@router.get("/corpus/reports")
async def report_corpus(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """해석 결과 분포 — 리포트 종류·케이스 수·반복되는 findings."""
    return ok(await svc.report_corpus(db))
