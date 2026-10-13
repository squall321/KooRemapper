# 결과 이미지가 리포트에 **붙는지** — 그림이 없으면 LLM 도 사람도 결과를 못 본다
"""번들 반입 + 미디어 매핑 계약 (2026-10-13).

왜 이 시험이 있나.

  "LLM 이 결과 이미지까지 리포트에 쓰면서 비교" 를 하려면 두 가지가 막혀 있었다(실측).
    ① 결과 이미지는 HTML 안에 **임베드되지 않는다** — 옆에 딸린 파일이라, HTML 하나만 올리면
       **애초에 플랫폼에 들어오지 않는다.**
    ② 들어와도 MCP 가 base64 를 dict 에 넣어 돌려주므로 모델에게는 **글자**로 왔다.

  ①을 번들 반입으로, ②를 `report_image`(ImageContent)로 고쳤다. 이 파일은 ①의 계약이다
  (②는 라이브 스택 관문 `platform/mcp_server/reports_smoke.py` 가 본다).

  ★매핑은 **리포트가 선언한 것만** 쓴다. 파일명으로 추측한 매핑은 틀려도 그럴듯해서 가장 나쁘다.
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest
import ulid
from sqlalchemy import delete

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import ImpactReport, Session, SessionFile, User  # noqa: E402
from app.modules.reports import services as svc  # noqa: E402
from app.reports import bundle, parser  # noqa: E402
from app.shared import security, storage  # noqa: E402

# ⚠ 모듈 전체에 asyncio 마크를 걸면 **동기 시험에도** 붙어 경고가 난다(이 파일은 순수 함수
# 시험과 DB 시험이 섞여 있다). 그래서 async 시험에만 건다.
_aio = pytest.mark.asyncio(loop_scope="session")

_ROOT = Path("/data/koopark/Test_Impact_A")
_HTML = _ROOT / "impact_report.html"
_MEDIA_DIR = _ROOT / "impact_report_data"


def _bundle_bytes(*, with_media: bool = True, attacks: bool = False) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(_HTML, "impact_report.html")
        if with_media:
            for p in sorted(_MEDIA_DIR.rglob("*")):
                if p.is_file():
                    z.write(p, str(p.relative_to(_ROOT)))
        if attacks:
            z.writestr("../../etc/evil.png", b"x")       # 트래버설
            z.writestr("/abs/evil.png", b"x")            # 절대경로
            z.writestr("notes.txt", b"ignored")          # 미디어도 HTML 도 아니다
    return buf.getvalue()


# ── 번들 추출(순수 함수) ─────────────────────────────────────────────────────

def test_bundle_blocks_traversal_and_non_media():
    """★압축 해제는 신뢰할 수 없는 입력이다 — 탈출 경로를 **거부하고 센다**."""
    if not _HTML.exists():
        pytest.skip("실제 impact 리포트 없음")
    b = bundle.extract(_bundle_bytes(attacks=True), "b.zip")
    assert b["html_name"] == "impact_report.html"
    assert b["skipped"].get("unsafe_path") == 2, b["skipped"]
    assert b["skipped"].get("other_ext") == 1, b["skipped"]
    paths = {m["path"] for m in b["media"]}
    assert not any(".." in p or p.startswith("/") for p in paths), paths


def test_bundle_separates_what_the_model_can_see():
    """png 는 모델이 보고 **mp4 는 못 본다** — 그 구분을 숨기면 '보여 줬는데 못 봤다' 가 된다."""
    if not _HTML.exists():
        pytest.skip("실제 impact 리포트 없음")
    b = bundle.extract(_bundle_bytes(), "b.zip")
    imgs = [m for m in b["media"] if m["can_llm_view"]]
    vids = [m for m in b["media"] if not m["can_llm_view"]]
    assert len(imgs) == 8 and len(vids) == 8, (len(imgs), len(vids))
    assert all(m["kind"] == "image" for m in imgs)
    assert all(m["path"].endswith(".mp4") for m in vids)


def test_bundle_without_html_is_refused():
    """리포트 없이 그림만 받지 않는다 — 어느 케이스의 그림인지 알 수 없다."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a/x.png", b"\x89PNG")
    with pytest.raises(bundle.BundleError) as e:
        bundle.extract(buf.getvalue(), "b.zip")
    assert "HTML" in str(e.value)


def test_not_a_bundle_is_refused():
    with pytest.raises(bundle.BundleError):
        bundle.extract(b"<html>not a bundle</html>", "r.html")


def test_looks_like_bundle_sniffs_content_not_just_name():
    """이름을 못 믿는 클라이언트가 있다 — 선두 바이트로도 본다."""
    raw = _bundle_bytes(with_media=False) if _HTML.exists() else None
    if raw is None:
        pytest.skip("실제 impact 리포트 없음")
    assert bundle.looks_like_bundle("whatever.bin", raw) is True
    assert bundle.looks_like_bundle("r.html", b"<html></html>") is False


# ── 매핑 정본 ────────────────────────────────────────────────────────────────

def test_media_map_uses_report_declaration_and_counts_empty_slots():
    """★실측 — 25 위치 중 8 개만 그림이 있고 17 항목은 **빈 항목**이다."""
    if not _HTML.exists():
        pytest.skip("실제 impact 리포트 없음")
    data = parser.extract_embedded_data(_HTML.read_text(encoding="utf-8", errors="replace"))
    m = parser.report_media_map(data, "impact")
    assert m["mapped_by"] == "set_report.media[set][position]"
    assert m["n_declared"] == 16 and m["n_empty_slots"] == 17, (m["n_declared"], m["n_empty_slots"])
    assert "8 / 25" in (m.get("generator_note") or ""), m.get("generator_note")
    one = m["declared"][0]
    assert one["case_key"] and one["role"] in ("peak", "view") and one["set_name"]


def test_media_map_refuses_to_guess_for_deep():
    """deep 은 매핑을 선언하지 않는다 — 파일명으로 **추측하지 않는다**."""
    if not _HTML.exists():
        pytest.skip("실제 impact 리포트 없음")
    data = parser.extract_embedded_data(_HTML.read_text(encoding="utf-8", errors="replace"))
    m = parser.report_media_map(data, "deep")
    assert m["n_declared"] == 0 and "추측하지 않는다" in m["note"]


# ── 저장·조회 ────────────────────────────────────────────────────────────────

async def _mk(db):
    u = User(email=f"media_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("x"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="media-test",
                storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    await db.refresh(s)
    storage.ensure_session_dir(u.id, sid)
    return u, s


async def _rm(db, u, s):
    await db.execute(delete(ImpactReport).where(ImpactReport.user_id == u.id))
    await db.execute(delete(SessionFile).where(SessionFile.session_id == s.id))
    await db.execute(delete(Session).where(Session.id == s.id))
    await db.execute(delete(User).where(User.id == u.id))
    await db.commit()
    d = storage.session_abs_dir(u.id, s.id)
    if d.exists():
        import shutil
        shutil.rmtree(d, ignore_errors=True)


@_aio
async def test_attach_media_persists_and_joins(db):
    """★그림을 저장하고 리포트에 **붙인다** — 그리고 그 칸이 **커밋된다**.

    ⚠ 실측으로 한 번 틀렸다: `ingest_report` 가 이미 커밋하고 돌아오므로, 뒤에서 flush 만
    하면 미디어 칸이 트랜잭션에 남아 사라진다(반입 응답은 16장이라고 말하는데 `/media` 가
    0 을 냈다). 그래서 이 시험은 **다시 읽어** 확인한다.
    """
    if not _HTML.exists():
        pytest.skip("실제 impact 리포트 없음")
    u, s = await _mk(db)
    try:
        b = bundle.extract(_bundle_bytes(), "b.zip")
        report = await svc.ingest_report(db, s, filename=b["html_name"], raw=b["html"])
        summary = await svc.attach_media(db, s, report, media=b["media"], html=b["html"])
        assert summary["n_stored"] == 16 and summary["n_mapped"] == 16, summary
        assert summary["n_images"] == 8 and summary["n_videos"] == 8, summary
        assert summary["n_empty_slots"] == 17, summary
        assert "missing_in_bundle" not in summary, summary

        # ★다시 읽어 확인 — flush 만으로는 사라졌다
        db.expunge_all()
        again = await db.get(ImpactReport, report.id)
        assert again.media and len(again.media) == 16, (again.media or [])[:1]
        row = again.media[0]
        for k in ("path", "file_id", "kind", "can_llm_view", "case_key", "role", "declared"):
            assert k in row, k
        # 저장 경로가 선언 경로와 같은 문자열이어야 조인이 된다
        assert row["path"] == row["stored_as"], (row["path"], row["stored_as"])

        got = svc.media_list(again, images_only=True)
        assert got["n_images"] == 8 and got["n_videos"] == 0
        assert len(got["cases_with_media"]) == 8
        one = svc.media_list(again, case_key=row["case_key"])
        assert one["n_returned"] == 2, one["n_returned"]      # peak png + view mp4
    finally:
        await _rm(db, u, s)


@_aio
async def test_media_list_says_so_when_empty(db):
    """그림이 없으면 **왜 없는지** 말한다 — 번들로 올려야 들어온다는 사실을 모르면 못 고친다."""
    if not _HTML.exists():
        pytest.skip("실제 impact 리포트 없음")
    u, s = await _mk(db)
    try:
        raw = _HTML.read_bytes()
        report = await svc.ingest_report(db, s, filename="impact_report.html", raw=raw)
        got = svc.media_list(report)
        assert got["n_total"] == 0
        assert "번들" in got["note"], got["note"]
    finally:
        await _rm(db, u, s)


@_aio
async def test_declared_but_missing_in_bundle_is_counted(db):
    """선언됐는데 번들에 없으면 **센다** — 조용히 빼면 '그 위치는 그림이 없다' 로 읽힌다."""
    if not _HTML.exists():
        pytest.skip("실제 impact 리포트 없음")
    u, s = await _mk(db)
    try:
        b = bundle.extract(_bundle_bytes(), "b.zip")
        half = b["media"][:4]                      # 일부만 올린 상황
        report = await svc.ingest_report(db, s, filename=b["html_name"], raw=b["html"])
        summary = await svc.attach_media(db, s, report, media=half, html=b["html"])
        assert summary["n_stored"] == 4
        assert summary["n_missing_in_bundle"] == 12, summary
        assert "안 올라왔다" in summary["missing_note"]
    finally:
        await _rm(db, u, s)
