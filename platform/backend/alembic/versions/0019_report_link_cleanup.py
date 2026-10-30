# 지운 리포트를 끝으로 하는 우리 선(개정 잇기)을 DB 가 함께 지우게 하는 트리거 + 이미 남은 것 정리 — 사용자 결정 10-30
"""왜 트리거인가. 선의 끝점은 key 문자열로 잇는다 — `onto_relations` 는 끝점 타입이 여럿이라(허브 거울 · 개정 · 리포트)
FK 를 걸 수 없다. 그래서 리포트가 지워질 때 그 선을 지우는 일을 FK `ON DELETE CASCADE` 처럼 DB 가 맡는다. 리포트가
지워지는 길은 하나가 아니다 — 리포트 삭제 API · 세션 삭제의 연쇄(`impact_reports.session_id` CASCADE) · 사용자 연쇄 ·
시험의 정리 · 손으로 지움. 길마다 코드로 떼면 하나를 빠뜨린다(10-30 dev 에 지운 리포트의 `measured_at` 선 411개 — 전부
그렇게 남은 것이었다. 리포트가 없는 선이 개정 비교의 리포트 수에 들어갔다).

이미 남은 것은 여기서 한 번 지운다 — 리포트가 없으니 잃는 정보가 없다. 되돌리기는 트리거만 걷는다(지운 선은 되살릴 뜻이 없다).
"""
from alembic import op

revision = "0019_report_link_cleanup"
down_revision = "0018_sp_receive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE OR REPLACE FUNCTION onto_drop_report_links() RETURNS trigger AS $$
BEGIN
  DELETE FROM onto_relations
   WHERE (src_type = 'impact_report' AND src_key = OLD.id)
      OR (dst_type = 'impact_report' AND dst_key = OLD.id);
  RETURN OLD;
END;
$$ LANGUAGE plpgsql;
""")
    op.execute("""
CREATE TRIGGER trg_impact_reports_drop_links
AFTER DELETE ON impact_reports
FOR EACH ROW EXECUTE FUNCTION onto_drop_report_links();
""")
    op.execute("""
DELETE FROM onto_relations e
 WHERE (e.src_type = 'impact_report' AND NOT EXISTS (SELECT 1 FROM impact_reports r WHERE r.id = e.src_key))
    OR (e.dst_type = 'impact_report' AND NOT EXISTS (SELECT 1 FROM impact_reports r WHERE r.id = e.dst_key));
""")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_impact_reports_drop_links ON impact_reports")
    op.execute("DROP FUNCTION IF EXISTS onto_drop_report_links()")
