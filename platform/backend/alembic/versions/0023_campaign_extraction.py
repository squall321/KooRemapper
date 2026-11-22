# 캠페인 런의 추출 목록과 캠페인의 필수 추출 목록 — 모두 null 허용 칸이라 옛 코드가 그대로 돈다
"""추출 완전성 · d3plot 삭제 관문(요청서 DF-04 · 계획 docs/01-plan/features/df-extraction-clearance-1122.plan.md).

왜 필요한가. d3plot 은 런마다 수십 ~ 수백 GB 라 리포트 뒤에 지운다. 지운 뒤에는 다시 못 뽑으므로 캠페인이 요구한 추출이 다 들어온
런만 지워야 하고, 피크가 d3plot 표본 상태에서 나온 값인지 응답에 보여야 한다. 런 목록이 추출 목록(상태 수 · 피크 출처 · 뽑은 장 ·
지움)을 실어 오면 행에 두고, 삭제 허가와 피크 표지는 읽을 때 캠페인의 필수 목록으로 센다(저장하지 않는다).

Revision ID: 0023_campaign_extraction
Revises: 0022_campaign_health
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023_campaign_extraction"
down_revision = "0022_campaign_health"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("required_extractions", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("campaign_runs", sa.Column("extraction", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("campaign_runs", "extraction")
    op.drop_column("campaigns", "required_extractions")
