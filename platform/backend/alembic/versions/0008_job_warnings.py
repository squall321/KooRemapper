"""성공한 잡에도 경고를 남긴다 — 개행 왕복 대조(P1-8)

`error_summary` 는 실패 자리다. 그런데 이 리포의 실제 사고는 **rc=0 인데 산출 덱이 상한**
모양이었다(캠페인 사건 1 요소 소실 · 사건 7 restack 무증상 붕괴). 개행 왕복 경고도 같은
부류라 성공한 잡에 실릴 자리가 필요하다.

Revision ID: 0008_job_warnings
Revises: 0007_external_jobs
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_job_warnings"
down_revision = "0007_external_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "warnings")
