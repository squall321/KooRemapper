"""관계 종류에 `cardinality` 를 더한다 — 정의 파일에는 있고 코어 API 응답에는 없다

왜 뒤늦게 더하나. `0011` 을 쓸 때는 코어 API 의 `CoreRelationKindOut`(`slug`·`label`·`src`·
`dst`)만 보고 칸을 잡았다. 그런데 **정의 파일**(`pipeline/core/plm-core.json`)에는
`cardinality`(`many_to_one` 등)가 있다 — 그것이 "모델 하나에 원 모델은 하나" 를 말하는 자리다.

없으면 검증기가 그 제약을 못 본다. `0011` 을 고치지 않는 이유는 이미 적용됐기 때문이다
(다른 세션이 올렸을 수 있다). 적용된 판을 손대면 올린 곳과 안 올린 곳이 갈린다.

Revision ID: 0012_relation_cardinality
Revises: 0011_ontology
Create Date: 2026-10-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_relation_cardinality"
down_revision = "0011_ontology"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("onto_relation_types",
                  sa.Column("cardinality", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("onto_relation_types", "cardinality")
