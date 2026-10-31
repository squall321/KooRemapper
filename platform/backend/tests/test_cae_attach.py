# 해석 온톨로지 적재(attach_ontology) · 보기 · 리포트를 건너는 질의 · 가시성 · 리포트 삭제 연쇄 · 번들 짝짓기 시험 — 사용자 결정 10-31 (가)
"""실제 dev DB 에 사용자 · 세션 · 리포트(각도 둘) · 원본 HTML 파일 행을 만들고 픽스처 꾸러미(`fixtures/cae_package_v14_min.json`)를 싣는다.
원본 HTML 파일 행의 sha256 은 꾸러미가 적은 짝 HTML 지문으로 둔다(파일 바이트는 필요 없다 — 짝은 지문으로 짓는다). 끝나면 만든 사용자를
지운다(세션 · 리포트 · 행은 FK 로 함께 사라진다 — 그것도 시험한다).
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest
import ulid
from sqlalchemy import delete, func, select

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import ImpactCase, ImpactReport, OntoObject, OntoRelation, Session, SessionFile, User
from app.modules.reports import services as svc
from app.reports import bundle as bundle_mod
from app.reports.onto_package import OntoPackageError
from app.shared import security

pytestmark = pytest.mark.asyncio(loop_scope="session")
FIX = Path(__file__).with_name("fixtures") / "cae_package_v14_min.json"
P = "/api/v1"


def _pkg() -> dict:
    return json.loads(FIX.read_text(encoding="utf-8"))


async def _make(db, *, admin: bool = False, with_report: bool = True):
    u = User(email=f"cae_{ulid.new().str}@kooremapper.test", password_hash=security.hash_password("x"),
             is_active=True, is_system_admin=admin)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    if not with_report:
        return u, None
    pkg = _pkg()
    s = Session(id=ulid.new().str, user_id=u.id, name="cae", storage_path=f"{u.id}/cae")
    db.add(s)
    await db.flush()
    html = SessionFile(session_id=s.id, filename="report.html", rel_path=f"{u.id}/cae/report.html", kind="input",
                       size_bytes=1, sha256=pkg["source"]["html"]["sha256"])
    db.add(html)
    await db.flush()
    rep = ImpactReport(id=ulid.new().str, session_id=s.id, user_id=u.id, kind="sphere", n_cases=2,
                       source_file_id=html.id, label="cae 시험")
    db.add(rep)
    await db.flush()
    for o in pkg["objects"]:
        if o["type"] == "cae_run":
            db.add(ImpactCase(report_id=rep.id, case_key=o["properties"]["case_key"],
                              identity={"angle": {"name": o["label"]}}))
    await db.commit()
    return u, rep


async def _drop(db, *users):
    for u in users:
        if u is not None:
            await db.execute(delete(User).where(User.id == u.id))
    await db.commit()


async def _rows(db, rid: str) -> tuple[int, int]:
    n_obj = (await db.execute(select(func.count()).select_from(OntoObject).where(OntoObject.report_id == rid))).scalar_one()
    n_rel = (await db.execute(select(func.count()).select_from(OntoRelation).where(OntoRelation.report_id == rid))).scalar_one()
    return n_obj, n_rel


async def test_attach_view_idempotence_and_cascade(db):
    u, rep = await _make(db)
    try:
        raw = FIX.read_bytes()
        got = await svc.attach_ontology(db, rep, raw, filename="report.ontology.json")
        assert got["already"] is False and got["vocabulary"]["version"] == "0.3"
        assert await _rows(db, rep.id) == (94, 115), "캠페인 수준 행 94 · 선 115(다대다 114 + campaign_report)"
        again = await svc.attach_ontology(db, rep, raw)
        assert again["already"] is True and await _rows(db, rep.id) == (94, 115)

        view = await svc.ontology_view(db, rep)
        assert view["loaded"] and view["campaign"]["key"] == "campaign"
        sev = [p.get("severity") for p in view["parts"]]
        assert sev == sorted(sev, key=lambda s: -svc.CAE_SEVERITY_RANK.get(str(s), 2)), "위험한 것부터"
        imp = [p.get("impulse_max") for p in view["load_paths"] if p.get("impulse_max") is not None]
        assert imp == sorted(imp, reverse=True), "충격량 큰 것부터"
        with_run = [p for p in view["parts"] if p.get("worst_von_mises_run_case")]
        assert with_run and all(p.get("worst_von_mises_run_identity") for p in with_run), "최악 런의 각도는 impact_cases 에서"
        # 단일면 접촉(모델 전체 한 면 — *CONTACT_AUTOMATIC_SINGLE_SURFACE)은 파트로 못 풀어 양쪽이 없다(계약 §8) — 나머지는 다 있다
        lonely = [c for c in view["contacts"] if not c["sides"]]
        assert [c.get("contact_card") for c in lonely] == ["*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID"], lonely
        assert any(f["about"] for f in view["findings"])
        assert all(not k.startswith(rep.id) for p in view["parts"] for k in (p["key"], p.get("campaign", "")))

        await db.execute(delete(ImpactReport).where(ImpactReport.id == rep.id))     # 리포트를 지우면 행 · 선도 함께
        await db.commit()
        assert await _rows(db, rep.id) == (0, 0)
    finally:
        await _drop(db, u)


async def test_a_package_for_another_report_changes_nothing(db):
    u, rep = await _make(db)
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        before = await _rows(db, rep.id)
        other = _pkg()
        other["source"]["html"]["sha256"] = "f" * 64
        with pytest.raises(OntoPackageError):
            await svc.attach_ontology(db, rep, json.dumps(other).encode())
        assert await _rows(db, rep.id) == before, "거절했는데 행이 바뀌었다"
        files = (await db.execute(select(SessionFile.filename).where(
            SessionFile.session_id == rep.session_id, SessionFile.filename.like("ontology/%")))).scalars().all()
        assert len(files) == 1, f"거절한 꾸러미 파일이 남았다 {files}"
    finally:
        await _drop(db, u)


async def test_report_rows_follow_report_visibility(db):
    owner, rep = await _make(db)
    stranger, _ = await _make(db, with_report=False)
    admin, _ = await _make(db, admin=True, with_report=False)
    try:
        await svc.attach_ontology(db, rep, FIX.read_bytes())
        mine = await svc.find_cae_rows(db, owner.id, type_slug="cae_part", min_severity="WARNING")
        assert any(r["report_id"] == rep.id for r in mine)
        assert not [r for r in await svc.find_cae_rows(db, stranger.id, type_slug="cae_part") if r["report_id"] == rep.id]
        paths = await svc.find_cae_rows(db, admin.id, type_slug="cae_load_path", is_admin=True, limit=500)
        assert any(r["report_id"] == rep.id for r in paths), "관리자는 전사"

        import httpx
        from httpx import ASGITransport

        from app.main import create_app
        from app.shared.auth import get_current_user
        app = create_app()
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            app.dependency_overrides[get_current_user] = lambda: stranger
            assert (await c.get(f"{P}/reports/{rep.id}/cae")).status_code == 404, "남의 리포트 온톨로지를 열었다"
            r = await c.post(f"{P}/reports/{rep.id}/cae", files={"file": ("x.json", FIX.read_bytes())})
            assert r.status_code == 404, "남이 꾸러미를 붙였다"
            # 전사 공개인 일반 보기에는 리포트 행이 없다
            from app.modules.ontology.routes import require_ontology
            app.dependency_overrides[require_ontology] = lambda: {"enabled": True}
            got = (await c.get(f"{P}/ontology/objects", params={"type": "cae_part"})).json()["data"]
            assert got["total"] == 0, "리포트 행이 전사 보기에 나왔다"
            one = await c.get(f"{P}/ontology/objects/cae_part/{rep.id}/part/1")
            assert one.status_code == 404
            app.dependency_overrides[get_current_user] = lambda: owner
            view = (await c.get(f"{P}/reports/{rep.id}/cae")).json()["data"]
            assert view["loaded"] and view["parts"]
            listed = (await c.get(f"{P}/cae/parts", params={"min_severity": "CRITICAL"})).json()["data"]
            assert all(i["severity"] == "CRITICAL" for i in listed["items"])
    finally:
        await _drop(db, owner, stranger, admin)


async def test_a_bundle_pairs_the_package_with_the_same_stem_only():
    def zipped(names: dict[str, bytes]) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for n, d in names.items():
                z.writestr(n, d)
        return buf.getvalue()
    html = b"<html>report</html>"
    got = bundle_mod.extract(zipped({"camp/report_g1.html": html, "camp/report_g1.ontology.json": b"{}",
                                     "camp/report_g2.ontology.json": b"{}"}), "b.zip")
    assert got["ontology"] == {"name": "report_g1.ontology.json", "data": b"{}"}
    got2 = bundle_mod.extract(zipped({"report.html": html, "other.ontology.json": b"{}"}), "b.zip")
    assert got2["ontology"] is None, "줄기가 다른 꾸러미를 짝으로 집었다"
