# 핫스팟 묶음 · 덱 세션 관리(DF-07 · DF-15) — 캠페인의 결과 → 덱 틀 이동값 칸과 세션의 덱 판 · CAD 연결 칸(모두 null 허용)
"""핫스팟 묶음 · 덱 세션 관리(요청서 DF-07 · DF-15 · 계획 docs/01-plan/features/df-hotspot-session-1122.plan.md).

왜 필요한가. 리포트의 핫스팟 군집 좌표는 결과(d3plot) 틀이라 덱 틀과 어긋난다 — 캠페인에 이동값을 둬야 덱 좌표로 묶을 수 있다. 리스크 앱이
DynaForge 덱 세션을 근거로 쓸 때 어느 덱 판 · 어느 CAD 판인지 헷갈려 판이 엇갈린 일이 있었다 — 세션에 판 라벨과 CAD 연결을 두고 다르면 경고한다.

새 칸은 모두 null 허용이다 — 옛 코드가 그대로 돈다.

Revision ID: 0026_hotspot_session
Revises: 0025_campaign_analysis
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026_hotspot_session"
down_revision = "0025_campaign_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("frame_offset", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("sessions", sa.Column("deck_revision_label", sa.String(length=64), nullable=True))
    op.add_column("sessions", sa.Column("linked_cad", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "linked_cad")
    op.drop_column("sessions", "deck_revision_label")
    op.drop_column("campaigns", "frame_offset")
