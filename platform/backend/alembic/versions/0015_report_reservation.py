"""리포트 예약 원장 — 외부 잡 키(유일)와 예약 때 받은 해석 조건

왜 필요한가. 후처리 예약(7-1)은 클러스터 잡 하나가 끝나면 그 리포트를 예약자 명의로 반입한다. 같은 잡을
두 번 반입하면 같은 결과가 두 리포트로 갈라져 비교 · 검색에서 겹쳐 센다 — 잡 하나에 리포트 하나(7-2)를
DB 가 지킨다. 예약 때 받은 해석 조건(높이 · 바닥 · 프리셋 · 위치 DOE)은 리포트 자신의 값을 덮지 않도록
따로 둔다(7-5). 둘 다 null 허용이라 손으로 올린 리포트와 옛 코드에는 영향이 없다.

계획 docs/01-plan/features/postprocess-reservation-1028.plan.md

Revision ID: 0015_report_reservation
Revises: 0014_recipes
Create Date: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015_report_reservation"
down_revision = "0014_recipes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("impact_reports", sa.Column("external_job_key", sa.String(length=64), nullable=True))
    op.add_column("impact_reports", sa.Column("reservation", postgresql.JSONB(), nullable=True))
    op.create_unique_constraint("uq_impact_reports_external_job_key", "impact_reports", ["external_job_key"])


def downgrade() -> None:
    op.drop_constraint("uq_impact_reports_external_job_key", "impact_reports", type_="unique")
    op.drop_column("impact_reports", "reservation")
    op.drop_column("impact_reports", "external_job_key")
