# 캠페인(한 과제 · 한 판의 런 묶음)과 그 런 목록 — campaigns · campaign_runs. 리포트 표는 건드리지 않는다
"""캠페인 묶음 적재(요청서 DF-01 · 계획 docs/01-plan/features/df-campaign-intake-1120.plan.md).

왜 필요한가. 리포트는 하나씩 들어왔고 「이 묶음에 몇이 들어왔나 · 무엇이 빠졌나」 를 물을 자리가 없었다. 같은 런을 다시
올리면 리포트가 하나 더 생겼다. 런 목록을 먼저 받아 행으로 두면 거절된 런(리포트 없음)도 남아 목록 수 = 받음 + 건너뜀 +
거절 + 아직이 맞고, 런마다 지문(sha256)을 두면 같은 내용을 다시 받지 않는다.

리포트가 지워지면 런은 남고 report_id 만 빈다(SET NULL) — 그 런은 다시 받을 수 있다.

Revision ID: 0021_campaigns
Revises: 0020_cae_report_rows
Create Date: 2026-11-20
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021_campaigns"
down_revision = "0020_cae_report_rows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("project", sa.String(length=64), nullable=True),
        sa.Column("dev_rev", sa.String(length=8), nullable=True),
        sa.Column("analysis_method", sa.String(length=64), nullable=True),
        sa.Column("analysis_target", sa.String(length=64), nullable=True),
        sa.Column("doe_strategy", sa.String(length=64), nullable=True),
        sa.Column("drop_height_mm", sa.Float(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("thickness_axis", sa.String(length=1), nullable=True),
        sa.Column("impactor", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("created_by", "name", name="uq_campaigns_owner_name"),
    )
    op.create_table(
        "campaign_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.String(length=26), nullable=False),
        sa.Column("run_key", sa.String(length=128), nullable=False),
        sa.Column("report_id", sa.String(length=26), nullable=True),
        sa.Column("doe", sa.String(length=64), nullable=True),
        sa.Column("pitch", sa.Float(), nullable=True),
        sa.Column("roll", sa.Float(), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("ingest_state", sa.String(length=12), server_default="pending", nullable=False),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["impact_reports.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "run_key", name="uq_campaign_runs_key"),
    )
    op.create_index("ix_campaign_runs_report_id", "campaign_runs", ["report_id"])


def downgrade() -> None:
    op.drop_table("campaign_runs")
    op.drop_table("campaigns")
