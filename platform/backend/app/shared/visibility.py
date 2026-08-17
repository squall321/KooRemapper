# 세션 공개 범위 판정 — 소유자 외에 누가 볼 수 있는가를 한 곳에서 정한다.
"""가시성은 4단이다(HEAX Hub 와 같은 어휘).

    private     소유자만
    team        소유자 + 같은 team
    department  소유자 + 같은 department
    company     인증된 사용자 전부

판정을 이 모듈 하나로 모으는 이유 — 조회 지점마다 조건을 다시 쓰면 한 군데를 빠뜨리는
날이 온다. 그 빠짐은 '남의 모델이 보인다' 는 사고이고, 조용히 일어난다.

⚠ 빈 department·team 은 매칭되지 않는다. 소속 미설정 사용자끼리 NULL == NULL 로
서로 보이면 'team 공개' 가 사실상 전체 공개가 된다 — 그래서 양쪽 다 값이 있을 때만 통과.
"""
from __future__ import annotations

from sqlalchemy import ColumnElement, or_, select

from app.models import Session, User

PRIVATE = "private"
TEAM = "team"
DEPARTMENT = "department"
COMPANY = "company"

#  넓은 순 — UI·검증에서 이 순서를 쓴다.
LEVELS = (COMPANY, DEPARTMENT, TEAM, PRIVATE)


def is_valid(level: str | None) -> bool:
    return level in LEVELS


def visible_filter(viewer: User) -> ColumnElement[bool]:
    """viewer 가 볼 수 있는 세션의 SQL 조건.

    소유자 본인 + 공개 범위에 걸리는 남의 세션. team/department 는 viewer 의 소속이
    비어 있으면 아예 조건에서 빠진다(빈 값 매칭 금지).
    """
    conds = [
        Session.user_id == viewer.id,          # 내 것은 공개 범위와 무관하게 전부
        Session.visibility == COMPANY,          # 전사 공개
    ]

    # 같은 부서·팀 — 소유자의 소속을 서브쿼리로 본다(User 조인 없이 조건만으로 성립).
    if (viewer.department or "").strip():
        conds.append(
            (Session.visibility == DEPARTMENT)
            & Session.user_id.in_(
                select(User.id).where(User.department == viewer.department)
            )
        )
    if (viewer.team or "").strip():
        conds.append(
            (Session.visibility == TEAM)
            & Session.user_id.in_(select(User.id).where(User.team == viewer.team))
        )
    return or_(*conds)


def can_view(viewer: User, session: Session, owner: User | None) -> bool:
    """단건 판정 — visible_filter 와 같은 규칙을 파이썬으로.

    owner 는 team/department 판정에만 쓴다(없으면 소속 판정은 실패로 본다).
    """
    if session.user_id == viewer.id:
        return True
    vis = session.visibility or PRIVATE
    if vis == COMPANY:
        return True
    if owner is None:
        return False
    if vis == DEPARTMENT:
        d = (viewer.department or "").strip()
        return bool(d) and d == (owner.department or "").strip()
    if vis == TEAM:
        t = (viewer.team or "").strip()
        return bool(t) and t == (owner.team or "").strip()
    return False   # private
