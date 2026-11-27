# 자동 파이프라인 실행 원장 — 포털이 낸 전각도 낙하 한 번(stcx 잡 → 후처리 예약 → sphere 리포트)을 run_ref 하나로 묶는다(KR-AP2)
"""자동 파이프라인 KR-AP2(포털 계약 v1.1 §2 · 계획 docs/01-plan/features/auto-pipeline-1127.plan.md).

`idem_key` 는 유일하다 — 포털이 응답을 잃고 다시 불러도 같은 실행을 돌려준다(계약 §2 · §4-1). 새 표라 옛 코드가 그대로 돈다.

Revision ID: 0028_auto_runs
Revises: 0027_session_task
Create Date: 2026-11-27
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0028_auto_runs"
down_revision = "0027_session_task"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auto_runs",
        sa.Column("run_ref", sa.String(length=26), primary_key=True),
        sa.Column("idem_key", sa.String(length=64), nullable=False, unique=True),
        sa.Column("profile", sa.String(length=32), nullable=False),
        sa.Column("subject", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_session_id", sa.String(length=26), nullable=True),
        sa.Column("run_session_id", sa.String(length=26), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stcx_job_id", sa.String(length=26), nullable=True),
        sa.Column("postprocess_job_id", sa.String(length=26), nullable=True),
        sa.Column("report_id", sa.String(length=26), nullable=True),
        sa.Column("stage", sa.String(length=16), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("auto_runs")
