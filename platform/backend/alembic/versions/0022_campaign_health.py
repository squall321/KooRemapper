# 캠페인 런의 출처 · 설정 세대 · 대체 · 건강 칸과 캠페인의 건강 문턱 — 모두 null 허용 칸이라 옛 코드가 그대로 돈다
"""런 출처 · 유효성(요청서 DF-02 · DF-03 · 계획 docs/01-plan/features/df-provenance-health-1122.plan.md).

왜 필요한가. 한 캠페인에 옛 설정 런과 새 설정 런이 섞이고, 스케줄러가 「완료」 라 한 런 가운데 해석이 중간에 멈춘 것 · 첫 운동
에너지가 0 인 것 · NaN 으로 바뀐 것이 통계에 섞였다. 런 목록이 출처 · 세대 · 대체 · 건강 수치를 실어 오면 행에 두고, 판정은
읽을 때 캠페인의 문턱으로 센다(판정 칸은 두지 않는다 — 문턱을 바꾸면 곧바로 다시 판정된다).

Revision ID: 0022_campaign_health
Revises: 0021_campaigns
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022_campaign_health"
down_revision = "0021_campaigns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("health_thresholds", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("campaign_runs", sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("campaign_runs", sa.Column("config_generation", sa.String(length=64), nullable=True))
    op.add_column("campaign_runs", sa.Column("superseded_by", sa.String(length=128), nullable=True))
    op.add_column("campaign_runs", sa.Column("health", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("campaign_runs", "health")
    op.drop_column("campaign_runs", "superseded_by")
    op.drop_column("campaign_runs", "config_generation")
    op.drop_column("campaign_runs", "provenance")
    op.drop_column("campaigns", "health_thresholds")
