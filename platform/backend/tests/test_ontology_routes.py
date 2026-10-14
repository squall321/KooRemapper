"""온톨로지 라우트의 **배선과 관문** — 이 리포는 서비스를 직접 시험한다(HTTP 하네스가 없다).

그래서 라우트에서 정말 위험한 것은 로직이 아니라 둘이다.
① **등록 누락** — 서비스가 맞아도 길이 없으면 아무도 못 쓴다
② ★**관리자 게이트 누락** — 전사 데이터를 움직이는 길이 로그인만으로 열리면 그것은 결함이다.
   그리고 그 결함은 **아무 시험도 빨개지지 않는다**(동작은 되니까)

그리고 ③ **과제를 고치는 길이 열려 있지 않은지** 본다 — 과제의 정본은 허브다.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.main import app
from app.shared.auth import get_current_user, require_system_admin

P = "/api/v1"


def _routes():
    out = {}
    for r in app.routes:
        path = getattr(r, "path", "")
        if "/ontology" in path or path.endswith("/revision"):
            for m in sorted(getattr(r, "methods", set()) - {"HEAD", "OPTIONS"}):
                out[(m, path)] = r
    return out


def _dep_names(route) -> set:
    """의존 이름들. 보안 스키마(`HTTPBearer`)는 함수가 아니라 **객체**라 `__name__` 이 없다 —
    클래스 이름으로 떨어진다."""
    calls = {d.call for d in route.dependant.dependencies if d.call is not None}
    calls |= {s.call for d in route.dependant.dependencies for s in d.dependencies
              if s.call is not None}
    return {getattr(c, "__name__", type(c).__name__) for c in calls}


# ── ① 등록 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("method,path", [
    ("GET", f"{P}/ontology/tasks"),
    ("GET", f"{P}/ontology/tasks/{{task_key}}/revisions"),
    ("GET", f"{P}/reports/{{report_id}}/revision"),
    ("PUT", f"{P}/reports/{{report_id}}/revision"),
    ("GET", f"{P}/ontology/task-links"),
    ("POST", f"{P}/ontology/task-links/apply"),
    ("GET", f"{P}/ontology/aliases"),
    ("POST", f"{P}/ontology/aliases"),
    ("GET", f"{P}/ontology/sync"),
    ("POST", f"{P}/ontology/sync"),
])
def test_the_route_exists(method, path):
    assert (method, path) in _routes(), sorted(k[1] for k in _routes())


# ── ② 관문 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("method,path", [
    ("GET", f"{P}/ontology/task-links"),
    ("POST", f"{P}/ontology/task-links/apply"),
    ("GET", f"{P}/ontology/aliases"),
    ("POST", f"{P}/ontology/aliases"),
    ("GET", f"{P}/ontology/sync"),
    ("POST", f"{P}/ontology/sync"),
])
def test_the_whole_fleet_paths_need_a_system_admin(method, path):
    """★전사 데이터를 움직이는 길이다 — 로그인만으로 열리면 결함이고, 그 결함은
    **아무 시험도 빨개지지 않는다**(동작은 되니까). 그래서 여기서 못박는다."""
    names = _dep_names(_routes()[(method, path)])
    assert require_system_admin.__name__ in names, sorted(names)


@pytest.mark.parametrize("method,path", [
    ("GET", f"{P}/ontology/tasks"),
    ("GET", f"{P}/ontology/tasks/{{task_key}}/revisions"),
    ("GET", f"{P}/reports/{{report_id}}/revision"),
    ("PUT", f"{P}/reports/{{report_id}}/revision"),
])
def test_the_rest_still_needs_a_login(method, path):
    names = _dep_names(_routes()[(method, path)])
    assert names & {get_current_user.__name__, require_system_admin.__name__}, sorted(names)


# ── ③ 과제를 고치는 길은 없다 ─────────────────────────────────────────────

def test_there_is_no_way_to_create_or_edit_a_task():
    """★과제의 정본은 **허브**다. 우리 화면에서 고치면 다음 받기가 덮어쓰고 그 사실은
    고친 사람에게 안 보인다(SP `ontology/managed.py`). 그래서 길 자체를 열지 않는다."""
    writes = [(m, p) for (m, p) in _routes()
              if m in {"POST", "PUT", "PATCH", "DELETE"}]
    for m, p in writes:
        assert "/ontology/tasks" not in p, f"과제를 쓰는 길이 생겼다: {m} {p}"


def test_the_write_paths_are_only_our_own_things():
    """쓰기는 **우리 것**에만 닿는다 — 개정 · 별칭 · 수신 실행."""
    writes = sorted(p for (m, p) in _routes() if m in {"POST", "PUT", "PATCH", "DELETE"})
    allowed = {f"{P}/reports/{{report_id}}/revision",
               f"{P}/ontology/task-links/apply",
               f"{P}/ontology/aliases",
               f"{P}/ontology/sync"}
    assert set(writes) == allowed, writes


def test_the_gate_check_actually_discriminates():
    """판별력 — 읽기 길에는 관리자 관문이 **없어야** 한다. 없는 것을 확인하지 않으면
    `_dep_names` 가 전부 참을 돌려줘도 위 시험들이 초록이다."""
    read = _dep_names(_routes()[("GET", f"{P}/ontology/tasks")])
    assert require_system_admin.__name__ not in read, sorted(read)
    admin = _dep_names(_routes()[("GET", f"{P}/ontology/sync")])
    assert require_system_admin.__name__ in admin
    assert read != admin, "두 길의 의존이 같다 — 관문을 못 가리고 있다"
