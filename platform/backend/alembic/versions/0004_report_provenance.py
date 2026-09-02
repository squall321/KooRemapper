"""report provenance: source K-file link, scenario conditions, manual eng_meta

Revision ID: 0004_report_provenance
Revises: 0003_visibility
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_report_provenance"
down_revision = "0003_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("impact_reports", sa.Column(
        "source_kfile_id", sa.BigInteger(),
        sa.ForeignKey("session_files.id", ondelete="SET NULL"),
    ))
    op.add_column("impact_reports", sa.Column(
        "scenario_file_id", sa.BigInteger(),
        sa.ForeignKey("session_files.id", ondelete="SET NULL"),
    ))
    op.add_column("impact_reports", sa.Column("scenario", postgresql.JSONB()))
    op.add_column("impact_reports", sa.Column("eng_meta", postgresql.JSONB()))
    op.create_index("ix_impact_reports_source_kfile_id", "impact_reports", ["source_kfile_id"])


def downgrade() -> None:
    op.drop_index("ix_impact_reports_source_kfile_id", table_name="impact_reports")
    for col in ("eng_meta", "scenario", "scenario_file_id", "source_kfile_id"):
        op.drop_column("impact_reports", col)
