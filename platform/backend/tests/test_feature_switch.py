"""기능 스위치 — **옵션이 없으면 있는 것으로 정하고, 꺼지면 없어진다.**

포탈이 앱의 `.env` 를 내려 주는 자리가 이미 있다(HWAXPortal `setup_requests.yaml`).
그래서 스위치는 환경변수 하나다 — 새 프로토콜을 만들지 않았다.

여기서 지키는 것 셋.
① **명시가 추론을 이긴다** — 옵션을 켰으면 허브가 없어도 켜진다(개정 잇기는 허브 없이도 돈다)
② **오타를 조용히 꺼짐으로 접지 않는다** — 오타가 기능을 없애는 일이다
③ ★**꺼지면 API 도 거절한다** — 화면에서만 숨기고 API 가 답하면 그것은 꺼진 것이 아니라
   **숨긴 것**이다. 그리고 거절은 **사유를 말한다**(꺼짐과 고장을 같은 모양으로 만들지 않는다)
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.config import settings
from app.modules.ontology.routes import require_ontology
from app.shared.features import ontology_enabled, ontology_state


@pytest.fixture()
def hub(monkeypatch):
    """허브 설정이 있는 박스."""
    monkeypatch.setattr(settings, "sp_core_url", "http://hub.test/api")
    monkeypatch.setattr(settings, "sp_core_token", "tok")
    monkeypatch.setattr(settings, "ontology", "")
    return settings


@pytest.fixture()
def bare(monkeypatch):
    """허브 설정이 없는 박스(지금 이 박스가 그렇다)."""
    monkeypatch.setattr(settings, "sp_core_url", "")
    monkeypatch.setattr(settings, "sp_core_token", "")
    monkeypatch.setattr(settings, "ontology", "")
    return settings


# ── ② 있는 것으로 정한다 ─────────────────────────────────────────────────

def test_with_a_hub_it_turns_itself_on(hub):
    st = ontology_state()
    assert st["enabled"] is True and st["source"] == "inferred"


def test_without_a_hub_it_stays_off_and_says_what_is_missing(bare):
    st = ontology_state()
    assert st["enabled"] is False and st["source"] == "inferred"
    assert st["missing"] == ["KOORM_SP_CORE_URL", "KOORM_SP_CORE_TOKEN"]
    assert "포탈" in st["reason"], "어디서 고치는지 말해야 한다"


def test_half_a_hub_is_still_off(monkeypatch, bare):
    """주소만 있고 토큰이 없으면 꺼진 것이다 — 반쪽으로 돌면 "받았는데 비어 있다" 가 된다."""
    monkeypatch.setattr(settings, "sp_core_url", "http://hub.test/api")
    st = ontology_state()
    assert st["enabled"] is False and st["missing"] == ["KOORM_SP_CORE_TOKEN"]


# ── ① 명시가 추론을 이긴다 ───────────────────────────────────────────────

@pytest.mark.parametrize("raw", ["1", "true", "YES", "on", "y"])
def test_the_option_turns_it_on_even_without_a_hub(monkeypatch, bare, raw):
    """★개정 잇기는 허브 없이도 돈다(과제 확인만 못 한다) — 켜라고 했으면 켠다."""
    monkeypatch.setattr(settings, "ontology", raw)
    st = ontology_state()
    assert st["enabled"] is True and st["source"] == "option"
    assert "허브 설정이 없어" in st["reason"], "못 하는 것을 함께 말해야 한다"


@pytest.mark.parametrize("raw", ["0", "false", "NO", "off", "n"])
def test_the_option_turns_it_off_even_with_a_hub(monkeypatch, hub, raw):
    monkeypatch.setattr(settings, "ontology", raw)
    st = ontology_state()
    assert st["enabled"] is False and st["source"] == "option"
    assert "옵션에서 껐다" in st["reason"]


# ── ② 오타 ───────────────────────────────────────────────────────────────

def test_a_typo_is_not_silently_read_as_off(monkeypatch, hub):
    """★오타가 기능을 없애면 안 된다 — 있는 것으로 정하고 **못 읽었다고 말한다.**"""
    monkeypatch.setattr(settings, "ontology", "ture")
    st = ontology_state()
    assert st["enabled"] is True and st["source"] == "inferred"
    assert "못 읽었다" in st["reason"]


def test_a_typo_on_a_bare_box_stays_off_but_still_says_so(monkeypatch, bare):
    monkeypatch.setattr(settings, "ontology", "ture")
    st = ontology_state()
    assert st["enabled"] is False and "못 읽었다" in st["reason"]


# ── ③ 꺼지면 API 도 거절한다 ─────────────────────────────────────────────

def test_the_api_refuses_when_off_with_a_reason(bare):
    """화면에서만 숨기고 API 가 답하면 그것은 꺼진 것이 아니라 **숨긴 것**이다."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as caught:
        require_ontology()
    assert caught.value.status_code == 409, "404 는 「그런 길이 없다」로 읽힌다"
    assert "꺼져 있습니다" in caught.value.detail
    assert "KOORM_SP_CORE_URL" in caught.value.detail, "왜 꺼졌는지 말해야 한다"


def test_the_api_allows_when_on(hub):
    st = require_ontology()
    assert st["enabled"] is True


def test_every_ontology_route_carries_the_switch():
    """★한 길만 빠뜨리면 그 길로 꺼진 기능이 샌다 — 라우터 단위로 달았는지 본다."""
    from app.main import app
    paths = [r for r in app.routes
             if "/ontology" in getattr(r, "path", "") or getattr(r, "path", "").endswith("/revision")]
    assert paths, "라우트를 못 찾았다"
    for r in paths:
        names = set()
        for d in r.dependant.dependencies:
            names.add(getattr(d.call, "__name__", type(d.call).__name__))
            for sub in d.dependencies:
                names.add(getattr(sub.call, "__name__", type(sub.call).__name__))
        assert "require_ontology" in names, (r.path, sorted(names))


# ── 한 자리에서만 판정한다 ───────────────────────────────────────────────

def test_the_judgement_lives_in_one_place():
    """두 곳에서 판정하면 화면과 API 가 갈린다 — 그러면 "보이는데 안 된다" 가 된다."""
    import subprocess
    root = Path(__file__).resolve().parents[1]
    out = subprocess.run(["git", "-C", str(root), "grep", "-n", "sp_core_token",
                          "--", "app/"], capture_output=True, text=True).stdout
    users = {l.split(":")[0] for l in out.splitlines() if l.strip()}
    assert users <= {"app/config.py", "app/shared/features.py", "app/worker/plm_sync.py",
                     "app/runner/sp_core.py"}, users


def test_capabilities_carries_the_state(bare):
    """화면이 이것으로 숨긴다 — 응답에서 빠지면 화면이 영영 못 숨긴다."""
    src = (Path(__file__).resolve().parents[1] / "app" / "modules" / "system"
           / "routes.py").read_text(encoding="utf-8")
    assert '"ontology": ontology_state(),' in src, "capabilities 응답에 상태가 없다"
    from app.modules.system import routes as sysr
    assert sysr.ontology_state()["enabled"] is False


def test_the_sync_interval_has_a_working_default(hub):
    """주소·토큰을 넣은 사람이 **간격까지 또 설정해야 하면** 그 둘째를 잊는다."""
    from app.worker import plm_sync
    assert settings.sp_core_sync_sec > 0
    assert plm_sync.enabled() is True


def test_clearing_the_interval_stops_only_the_scheduler(monkeypatch, hub):
    """기능은 켜 두고 주기 수신만 끌 수 있어야 한다 — 둘은 다른 것이다."""
    from app.worker import plm_sync
    monkeypatch.setattr(settings, "sp_core_sync_sec", 0)
    assert plm_sync.enabled() is False
    assert ontology_enabled() is True
