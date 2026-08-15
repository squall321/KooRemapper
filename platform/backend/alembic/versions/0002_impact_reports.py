"""impact/drop report ingestion: impact_reports, impact_cases

Revision ID: 0002_impact_reports
Revises: 0001_initial
Create Date: 2026-08-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_impact_reports"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "impact_reports",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("session_id", sa.String(26), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("label", sa.String(255)),
        sa.Column("source_file_id", sa.BigInteger(), sa.ForeignKey("session_files.id", ondelete="SET NULL")),
        sa.Column("generator", sa.String(40)),
        sa.Column("generator_version", sa.String(40)),
        sa.Column("schema_str", sa.String(64)),
        sa.Column("project_name", sa.String(255)),
        sa.Column("doe_strategy", sa.String(64)),
        sa.Column("test_dir", sa.String(1024)),
        sa.Column("sim_params", postgresql.JSONB()),
        sa.Column("parts", postgresql.JSONB()),
        sa.Column("findings", postgresql.JSONB()),
        sa.Column("summary", postgresql.JSONB()),
        sa.Column("n_cases", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_impact_reports_session_id", "impact_reports", ["session_id"])
    op.create_index("ix_impact_reports_user_id", "impact_reports", ["user_id"])
    op.create_index("ix_impact_reports_kind", "impact_reports", ["kind"])
    op.create_index("ix_impact_reports_source_file_id", "impact_reports", ["source_file_id"])
    op.create_index("ix_impact_reports_created_at", "impact_reports", ["created_at"])

    op.create_table(
        "impact_cases",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("report_id", sa.String(26), sa.ForeignKey("impact_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_key", sa.String(255), nullable=False),
        sa.Column("identity", postgresql.JSONB()),
        sa.Column("num_states", sa.Integer()),
        sa.Column("success", sa.Boolean()),
        sa.Column("parts_metrics", postgresql.JSONB()),
        sa.Column("max_stress", sa.Float()),
        sa.Column("max_g", sa.Float()),
        sa.Column("max_disp", sa.Float()),
        sa.Column("min_safety_factor", sa.Float()),
    )
    op.create_index("ix_impact_cases_report_id", "impact_cases", ["report_id"])


def downgrade() -> None:
    op.drop_index("ix_impact_cases_report_id", table_name="impact_cases")
    op.drop_table("impact_cases")
    for ix in (
        "ix_impact_reports_created_at",
        "ix_impact_reports_source_file_id",
        "ix_impact_reports_kind",
        "ix_impact_reports_user_id",
        "ix_impact_reports_session_id",
    ):
        op.drop_index(ix, table_name="impact_reports")
    op.drop_table("impact_reports")
