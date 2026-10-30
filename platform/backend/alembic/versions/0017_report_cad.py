"""리포트에 붙인 CAD 형상 묶음 — StepForge fe_cad(C-6 가중치 · C-7 glb)의 요약과 저장한 파일 자리

왜 필요한가. 브라우저 변형 뷰어(총괄 P2)는 리포트 각도를 누르면 그 기기의 glb 를 연다. 리포트와 형상을 잇는 길은
「리포트에 묶음 붙이기」 로 정했다(사용자 결정 10-30) — 붙인 것이 그 리포트의 형상이다. 화면이 glb 노드를 파트에 잇고
묶음 정보를 보이려면 받는 쪽 검사를 통과한 요약(열쇠 · 덱 · 파트 표 · 파일 id)이 리포트 한 칸에 있어야 한다.
null 허용이라 옛 코드에 영향 없다.

계획 `docs/01-plan/features/deform-viewer-1030.plan.md`

Revision ID: 0017_report_cad
Revises: 0016_report_renders
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017_report_cad"
down_revision = "0016_report_renders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("impact_reports", sa.Column("cad", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("impact_reports", "cad")
