"""report search axes: focus + denormalized worst/severity/height/scenario_type

Revision ID: 0005_report_search_axes
Revises: 0004_report_provenance
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_report_search_axes"
down_revision = "0004_report_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("impact_reports", sa.Column("focus", sa.String(64)))
    op.add_column("impact_reports", sa.Column("worst_stress", sa.Float()))
    op.add_column("impact_reports", sa.Column("worst_g", sa.Float()))
    op.add_column("impact_reports", sa.Column("max_severity", sa.String(12)))
    op.add_column("impact_reports", sa.Column("drop_height", sa.Float()))
    op.add_column("impact_reports", sa.Column("scenario_type", sa.String(32)))
    op.create_index("ix_impact_reports_focus", "impact_reports", ["focus"])
    op.create_index("ix_impact_reports_worst_stress", "impact_reports", ["worst_stress"])
    op.create_index("ix_impact_reports_max_severity", "impact_reports", ["max_severity"])
    op.create_index("ix_impact_reports_drop_height", "impact_reports", ["drop_height"])
    op.create_index("ix_impact_reports_scenario_type", "impact_reports", ["scenario_type"])


def downgrade() -> None:
    for ix in ("ix_impact_reports_scenario_type", "ix_impact_reports_drop_height",
               "ix_impact_reports_max_severity", "ix_impact_reports_worst_stress",
               "ix_impact_reports_focus"):
        op.drop_index(ix, table_name="impact_reports")
    for col in ("scenario_type", "drop_height", "max_severity", "worst_g", "worst_stress", "focus"):
        op.drop_column("impact_reports", col)
