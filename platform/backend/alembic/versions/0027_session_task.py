# 세션의 허브 과제 · 개발 단계 칸 — 자동 파이프라인 원천(KR-AP1)이 subject.project · revision 으로 싣는다
"""자동 파이프라인 KR-AP1(포털 요청 11-27 · 계획 docs/01-plan/features/auto-pipeline-1127.plan.md).

세션에는 허브 과제 · 개발 단계 칸이 없었다(linked_cad · 자유 덱 판 라벨만). 사용자 결정(11-27) 「세션에 과제 · 개발 단계 칸」 —
사람이 넣고, 과제는 판 확정과 같은 규칙으로 풀어 과제명을, 개발 단계는 dev_rev 꼴을 남긴다. 비면 null(자동 파이프라인이 막힘으로
세운다). 새 칸은 모두 null 허용이다 — 옛 코드가 그대로 돈다.

Revision ID: 0027_session_task
Revises: 0026_hotspot_session
Create Date: 2026-11-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0027_session_task"
down_revision = "0026_hotspot_session"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("task_key", sa.String(length=300), nullable=True))
    op.add_column("sessions", sa.Column("dev_rev", sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "dev_rev")
    op.drop_column("sessions", "task_key")
