# cae00 요청 KR-18 — /auth/sso/verify(표준 위임 점검) + X-Heax-Client 허용목록에 gateway.
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.modules.auth.routes import _SSO_CLIENT_NAMES

pytestmark = pytest.mark.asyncio(loop_scope="session")
P = "/api/v1"


async def test_gateway_is_an_allowed_client():
    assert "gateway" in _SSO_CLIENT_NAMES   # KR-18 ②


async def _client():
    import httpx
    from httpx import ASGITransport
    from app.main import create_app
    app = create_app()
    return httpx.AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False),
                             base_url="http://test")


async def test_sso_verify_404_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "heax_gateway_secret", "")
    async with await _client() as c:
        r = await c.post(f"{P}/auth/sso/verify")
    assert r.status_code == 404, r.status_code


async def test_sso_verify_204_on_match_401_on_mismatch(monkeypatch):
    monkeypatch.setattr(settings, "heax_gateway_secret", "s3cr3t-kr18")
    async with await _client() as c:
        ok = await c.post(f"{P}/auth/sso/verify", headers={"x-heax-gateway-secret": "s3cr3t-kr18"})
        bad = await c.post(f"{P}/auth/sso/verify", headers={"x-heax-gateway-secret": "wrong"})
        none = await c.post(f"{P}/auth/sso/verify")
    assert ok.status_code == 204, ok.status_code
    assert bad.status_code == 401, bad.status_code
    assert none.status_code == 401, none.status_code   # 헤더 없음도 불일치
