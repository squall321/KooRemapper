# 리포트에서 나온 온톨로지 행(해석 어휘 cae_*)을 리포트에 묶는 칸 — onto_objects · onto_relations.report_id(FK CASCADE) · impact_reports.ontology
"""사용자 결정 10-31 — DynaForge 가 해석 어휘를 싣되 (가) 캠페인 수준만 행으로(계획 docs/01-plan/features/cae-ontology-1031.plan.md).

리포트에서 나온 행은 그 리포트의 것이다 — 리포트를 지우면 함께 사라져야 하고(FK ON DELETE CASCADE), 읽는 것도 리포트 가시성을 따라야 한다
(조인할 칸이 있어야 한다). 키 접두(`<리포트 id>/`)로 지우면 색인을 못 탄다. 허브 거울 · 우리 개정 행은 report_id 가 비어 있다.
impact_reports.ontology 는 적재 요약(어휘 판 · 꾸러미 파일 · 건수 · 경고)이다.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020_cae_report_rows"
down_revision = "0019_report_link_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("onto_objects", "onto_relations"):
        op.add_column(table, sa.Column("report_id", sa.String(26),
                                       sa.ForeignKey("impact_reports.id", ondelete="CASCADE"), nullable=True))
        op.create_index(f"ix_{table}_report_id", table, ["report_id"])
    op.add_column("impact_reports", sa.Column("ontology", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("impact_reports", "ontology")
    for table in ("onto_relations", "onto_objects"):
        op.drop_index(f"ix_{table}_report_id", table_name=table)
        op.drop_column(table, "report_id")
