# 외부 적재의 공식 답(capabilities.intake) · environment 칸 · inspect sha256 이 응답에 실리는지(2026-11-17 사용자 결정)
"""외부 적재 공식 답 · 환경 칸 · inspect 지문 (2026-11-17 · 결정 문서 D4 · D5 · 리스크 앱 RK-06).

왜 이 시험이 있나.

  게이트웨이 11-17 점검 — `/system/capabilities` 는 적재를 말하지 않았고, 적재 주소 · 토큰 · 크기 상한은 MCP 도구의 글 안에만
  있었다. 사용 쪽은 주소를 추측하다 401 에 멈췄다. 이제 capabilities 가 `intake` 묶음으로 답하고(게이트웨이 카탈로그가 그대로
  싣는다), 리포트 응답마다 어느 환경(dev · prod)의 report_id 인지 싣고, inspect 가 덱 지문(sha256)을 낸다. DB 없이 라우트 함수를
  바로 부른다.
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starlette.requests import Request  # noqa: E402

from app.config import settings  # noqa: E402
from app.modules.reports.schemas import ReportListItem, ReportRead  # noqa: E402


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/api/v1/system/capabilities", "headers": [],
                    "query_string": b"", "scheme": "http", "server": ("127.0.0.1", 8700), "client": ("127.0.0.1", 1)})


def _caps():
    from app.modules.system import routes as sysr
    resp = asyncio.run(sysr.capabilities(_request(), None))
    import json
    return json.loads(resp.body)["data"]


def test_capabilities_declares_intake(monkeypatch):
    monkeypatch.setattr(settings, "public_base", "")
    it = _caps()["intake"]
    assert it["method"] == "POST" and it["path"] == "/api/v1/reports/intake", it
    assert it["token"] == "kr_pat" and it["portal_auth_required"] is False and it["batch"] is False, it
    assert it["max_upload_mb"] == settings.max_upload_mb and it["max_report_mb"] == settings.max_report_mb, it
    assert it["public_url"] is None, it   # 주소를 모르면 지어내지 않는다


def test_capabilities_public_url_from_public_base(monkeypatch):
    monkeypatch.setattr(settings, "public_base", "https://portal.example:8088/")
    it = _caps()["intake"]
    assert it["public_url"] == "https://portal.example:8088/apps/kooremapper_api/api/v1/reports/intake", it


def test_environment_words(monkeypatch):
    for raw, word in (("development", "dev"), ("production", "prod"), ("Production ", "prod"), ("staging", "unknown")):
        monkeypatch.setattr(settings, "app_env", raw)
        assert settings.environment == word, (raw, settings.environment)


def test_report_responses_carry_environment(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    now = datetime.now(timezone.utc)
    # 필수 칸만 채운 행 — 없는 선택 칸은 스키마 기본값이 된다(from_attributes)
    row = SimpleNamespace(id="r1", session_id="s1", kind="sphere", label=None, source_file_id=None, generator=None,
                          generator_version=None, project_name=None, test_dir=None, sim_params=None, parts=None,
                          findings=None, summary=None, n_cases=1, created_at=now)
    for schema in (ReportRead, ReportListItem):
        dumped = schema.model_validate(row).model_dump()
        assert dumped["environment"] == "prod", (schema.__name__, dumped.get("environment"))


def test_inspect_carries_the_file_sha256(monkeypatch):
    from app.modules.sessions import routes as sr

    async def fake_get(db, user, session_id, file_id):
        return SimpleNamespace(filename="deck.k", sha256="ab" * 32, meta={"modelmeta": {"element_id_collisions": 3}})

    monkeypatch.setattr(sr.svc, "get_viewable_file", fake_get)
    import json
    d = json.loads(asyncio.run(sr.inspect_file("s1", 1, None, None)).body)["data"]
    assert d["sha256"] == "ab" * 32 and d["meta"]["modelmeta"]["element_id_collisions"] == 3, d
