# 캠페인 분석(DF-05 · 06 · 08 ~ 12) — 런의 충격 구간 · 캠페인의 쌍 규칙 칸과 무리 · 기준값 · 파트 짝 · 자리 · 자리 지표 표 다섯
"""캠페인 분석(요청서 DF-05 · 06 · 08 ~ 12 · 계획 docs/01-plan/features/df-campaign-analysis-1122.plan.md).

왜 필요한가. 각도 표 · 피크 표 · 여유 · 구면 지도 · 자리 지도 · 리비전 비교 · 설정 쌍 판정을 리포트 하나씩이 아니라 캠페인 단위로 내야 한다.
리포트에 없는 것 — 충격 구간(만드는 쪽이 런 목록에 싣는다) · 부품 무리 · 기준값 묶음 · 파트 짝 표 · 자리 표 · 쌍 합격 규칙 — 을 받을 자리가
없었다. 판정 · 비 · 격자는 저장하지 않고 읽을 때 센다.

새 칸 둘은 null 허용이고 새 표는 있던 표를 건드리지 않는다 — 옛 코드가 그대로 돈다.

Revision ID: 0025_campaign_analysis
Revises: 0024_report_bundles
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025_campaign_analysis"
down_revision = "0024_report_bundles"
branch_labels = None
depends_on = None

_J = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column("campaign_runs", sa.Column("impacts", _J, nullable=True))
    op.add_column("campaigns", sa.Column("pair_rule", _J, nullable=True))
    op.create_table(
        "campaign_part_groups",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.String(length=26), nullable=False),
        sa.Column("group_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("part_ids", _J, nullable=False),
        sa.Column("part_key", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "group_key", name="uq_campaign_part_groups_key"),
    )
    op.create_table(
        "criteria_bindings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.String(length=26), nullable=False),
        sa.Column("part_id", sa.Integer(), nullable=True),
        sa.Column("group_key", sa.String(length=64), nullable=True),
        sa.Column("failure_mode", sa.String(length=64), nullable=True),
        sa.Column("metric_axis", sa.String(length=40), nullable=False),
        sa.Column("criterion_value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("source_platform", sa.String(length=64), nullable=True),
        sa.Column("source_record_id", sa.String(length=128), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("(part_id IS NULL) <> (group_key IS NULL)", name="ck_criteria_bindings_one_target"),
    )
    op.create_index("ix_criteria_bindings_campaign_id", "criteria_bindings", ["campaign_id"])
    op.create_table(
        "part_maps",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("from_model", sa.String(length=255), nullable=False),
        sa.Column("to_model", sa.String(length=255), nullable=False),
        sa.Column("rows", _J, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_part_maps_created_by", "part_maps", ["created_by"])
    op.create_table(
        "campaign_sites",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.String(length=26), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("face", sa.String(length=8), nullable=True),
        sa.Column("col", sa.Integer(), nullable=True),
        sa.Column("row", sa.Integer(), nullable=True),
        sa.Column("x_mm", sa.Float(), nullable=True),
        sa.Column("y_mm", sa.Float(), nullable=True),
        sa.Column("under_category", sa.String(length=64), nullable=True),
        sa.Column("impactor", _J, nullable=True),
        sa.Column("run_key", sa.String(length=128), nullable=True),
        sa.Column("footprint", _J, nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "site_id", name="uq_campaign_sites_key"),
    )
    op.create_table(
        "campaign_site_metrics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("site_row_id", sa.BigInteger(), nullable=False),
        sa.Column("part", sa.String(length=64), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("time_ms", sa.Float(), nullable=True),
        sa.Column("elem_id", sa.BigInteger(), nullable=True),
        sa.Column("ratio", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["site_row_id"], ["campaign_sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaign_site_metrics_site_row_id", "campaign_site_metrics", ["site_row_id"])


def downgrade() -> None:
    op.drop_table("campaign_site_metrics")
    op.drop_table("campaign_sites")
    op.drop_table("part_maps")
    op.drop_table("criteria_bindings")
    op.drop_table("campaign_part_groups")
    op.drop_column("campaigns", "pair_rule")
    op.drop_column("campaign_runs", "impacts")
