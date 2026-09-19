"""report shared_affiliation: 반입 시점에 얼린 소속 id(읽기 공유 범위)

Revision ID: 0006_report_shared_affiliation
Revises: 0005_report_search_axes
Create Date: 2026-09-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_report_shared_affiliation"
down_revision = "0005_report_search_axes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("impact_reports", sa.Column("shared_affiliation", sa.String(120)))
    op.create_index(
        "ix_impact_reports_shared_affiliation", "impact_reports", ["shared_affiliation"]
    )


def downgrade() -> None:
    op.drop_index("ix_impact_reports_shared_affiliation", table_name="impact_reports")
    op.drop_column("impact_reports", "shared_affiliation")
