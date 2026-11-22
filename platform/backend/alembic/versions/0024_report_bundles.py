# 보고서용 묶음 — report_bundles(판 하나가 한 행) · report_bundle_items(숫자 하나가 한 행). 다른 표는 건드리지 않는다
"""보고서용 묶음 출력(요청서 DF-13 · 계획 docs/01-plan/features/df-report-bundles-1122.plan.md).

왜 필요한가. 보고서 · 영상 생성기가 숫자를 손으로 옮기거나 고정 경로의 숫자 JSON 하나를 읽었다 — 결과가 바뀌어도 어느 숫자가
바뀌었는지, 숫자가 어느 리포트 · 케이스 · 지표에서 왔는지 거슬러 갈 길이 없었다. 묶음은 주소(`bundle_id`) 하나에 판을 쌓고, 판마다
수치 기준 줄 · 표 · 그림 · 출처 · 앞 판 대비 바뀐 숫자를 두며, 숫자마다 출처 경로를 항목 표에 둔다.

묶음은 만든 사람의 것이다(캠페인과 같다). 판을 지우면 그 항목도 지워진다.

Revision ID: 0024_report_bundles
Revises: 0023_campaign_extraction
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024_report_bundles"
down_revision = "0023_campaign_extraction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_bundles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("bundle_id", sa.String(length=26), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("campaign_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("basis", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tables", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("figures", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("citation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bundle_id", "version", name="uq_report_bundles_version"),
    )
    op.create_index("ix_report_bundles_created_by", "report_bundles", ["created_by"])
    op.create_table(
        "report_bundle_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("bundle_row_id", sa.BigInteger(), nullable=False),
        sa.Column("item_key", sa.String(length=512), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=True),
        sa.Column("source_path", sa.String(length=512), nullable=False),
        sa.ForeignKeyConstraint(["bundle_row_id"], ["report_bundles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_bundle_items_row_key", "report_bundle_items", ["bundle_row_id", "item_key"])


def downgrade() -> None:
    op.drop_table("report_bundle_items")
    op.drop_table("report_bundles")
