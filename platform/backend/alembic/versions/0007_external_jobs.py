"""외부 잡(다른 클러스터에 던진 것)의 수명을 프로세스가 아니라 칸으로 판정한다

로컬 잡은 워커의 자식이라 워커가 죽으면 같이 죽는다. stcx 에 던진 잡은 아니다 —
API 를 재기동해도 계속 돈다. 그 둘을 못 가르면 재기동 한 번에 도는 잡이 failed 로
지워진다(reconcile_orphans).

Revision ID: 0007_external_jobs
Revises: 0006_report_shared_affiliation
Create Date: 2026-09-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_external_jobs"
down_revision = "0006_report_shared_affiliation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("external_kind", sa.String(40)))
    op.add_column("jobs", sa.Column("external_ref", postgresql.JSONB()))
    op.add_column("jobs", sa.Column("external_poll_at", sa.DateTime(timezone=True)))
    op.create_index("ix_jobs_external_kind", "jobs", ["external_kind"])
    # 폴링 스캔이 읽는 조합 — 외부 잡만, 기한이 지난 것만.
    op.create_index("ix_jobs_external_poll_at", "jobs", ["external_poll_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_external_poll_at", table_name="jobs")
    op.drop_index("ix_jobs_external_kind", table_name="jobs")
    op.drop_column("jobs", "external_poll_at")
    op.drop_column("jobs", "external_ref")
    op.drop_column("jobs", "external_kind")
