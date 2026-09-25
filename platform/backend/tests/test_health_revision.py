# /api/health 가 지금 도는 것이 어느 커밋·어느 바이너리인지 말한다 (P0-4)
"""왜 이 시험이 있나 (2026-09-25, 덱 계약 2차 P0-4).

게시본이 21커밋 뒤에 멈춰 있었는데 **밖에서 볼 방법이 없었다.** 바이너리는 넷이 다
`version 1.8.0` 만 찍고 `/api/health` 는 `binary_present` 만 냈다. 그래서 "09-24 수정이
실사용에 갔나" 를 사람이 파일 mtime 으로 추측하고 있었다.

출처는 배포가 내려놓은 `bin/BUILD_INFO.txt` 하나다. 런타임에 `git` 을 부르지 않는다 —
컨테이너에 `.git` 이 없는 것이 아니라(바인드로 읽힌다) `git` **실행 파일**이 없다.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hashlib

import pytest

from app.shared import buildinfo


@pytest.fixture(autouse=True)
def _clear_cache():
    # 캐시가 시험 사이에 새면 다음 케이스가 앞 케이스의 답을 본다.
    buildinfo._cache = None
    buildinfo._cache_key = None
    yield
    buildinfo._cache = None
    buildinfo._cache_key = None


def _mk(tmp_path, body: bytes = b"fake-binary", info: str | None = None) -> Path:
    b = tmp_path / "KooRemapper"
    b.write_bytes(body)
    if info is not None:
        (tmp_path / "BUILD_INFO.txt").write_text(info, encoding="utf-8")
    return b


_INFO = """KooRemapper 배포 아티팩트 빌드 정보
published_utc : 2026-09-25T04:00:00Z
stage         : dist-20260925-040000Z

[source]
commit        : 1234567890abcdef1234567890abcdef12345678
subject       : 무엇을 고쳤나
branch        : main
describe      : v1.8.0-21-g1234567
remote        : git@example:koorm.git
worktree      : clean

[binary] platform/backend/bin/KooRemapper
size          : 11 bytes
mtime_utc     : 2026-09-25T03:21:19Z
md5           : ffff
sha256        : {sha}
build_method  : scripts/build_linux_compat.sh (이 실행의 --build)
"""


def test_without_build_info_it_says_nothing_rather_than_guessing(tmp_path):
    """BUILD_INFO 가 없으면 revision 은 None 이다 — 지어내지 않는다(개발 트리가 그 상태다)."""
    b = _mk(tmp_path)
    info = buildinfo.build_info(b)
    assert info["binary_present"] is True
    assert info["revision"] is None
    assert info["binary_sha256"] == hashlib.sha256(b"fake-binary").hexdigest()
    assert info["binary_mtime_utc"].endswith("Z")
    assert info["revision_matches_binary"] is None


def test_it_reads_the_revision_the_deploy_left(tmp_path):
    body = b"fake-binary"
    sha = hashlib.sha256(body).hexdigest()
    b = _mk(tmp_path, body, _INFO.format(sha=sha))
    info = buildinfo.build_info(b)
    assert info["revision"] == "1234567890abcdef1234567890abcdef12345678"
    assert info["revision_branch"] == "main"
    assert info["published_utc"] == "2026-09-25T04:00:00Z"
    assert info["binary_sha256"] == sha
    assert info["revision_matches_binary"] is True


def test_a_binary_swapped_without_updating_build_info_is_flagged(tmp_path):
    """⚠ 09-24 사고가 정확히 이 모양이다 — 다른 세션이 바이너리만 호스트 빌드로 덮어썼다.
    그때 revision 을 그대로 내보내면 **거짓말**이 된다. 어긋났다는 사실을 함께 낸다."""
    b = _mk(tmp_path, b"OTHER-binary", _INFO.format(sha=hashlib.sha256(b"orig").hexdigest()))
    info = buildinfo.build_info(b)
    assert info["revision"] == "1234567890abcdef1234567890abcdef12345678"
    assert info["revision_matches_binary"] is False, "어긋났는데 맞다고 했다"


def test_unknown_values_are_not_echoed_as_revisions(tmp_path):
    """BUILD_INFO 가 '알 수 없음' 을 적었으면 그 문자열을 리비전으로 내보내면 안 된다."""
    b = _mk(tmp_path, b"x", "[source]\ncommit        : 알 수 없음\nbranch        : 알 수 없음\n")
    info = buildinfo.build_info(b)
    assert info["revision"] is None and info["revision_branch"] is None


def test_the_secret_ish_fields_do_not_leak(tmp_path):
    """`/api/health` 는 인증 없이 열린다 — 커밋 제목·remote URL 을 실으면 안 된다."""
    body = b"fake-binary"
    b = _mk(tmp_path, body, _INFO.format(sha=hashlib.sha256(body).hexdigest()))
    blob = repr(buildinfo.build_info(b))
    assert "무엇을 고쳤나" not in blob, "커밋 제목이 새 나갔다"
    assert "git@example" not in blob, "remote URL 이 새 나갔다"


def test_the_cache_refreshes_when_the_binary_changes(tmp_path):
    """배포가 파일을 갈면 다음 호출에서 갱신돼야 한다 — 안 그러면 재기동 전까지 옛 해시를 낸다."""
    b = _mk(tmp_path, b"aaaa")
    first = buildinfo.build_info(b)["binary_sha256"]
    b.write_bytes(b"bbbbbb")          # 크기까지 달라진다
    second = buildinfo.build_info(b)["binary_sha256"]
    assert first != second, "바이너리가 갈렸는데 옛 해시를 냈다"
    assert second == hashlib.sha256(b"bbbbbb").hexdigest()


def test_a_missing_binary_is_not_cached(tmp_path):
    """바이너리가 아직 없을 수 있다(배포 중) — 그 상태를 캐시하면 생겨도 안 보인다."""
    b = tmp_path / "nope"
    assert buildinfo.build_info(b)["binary_present"] is False
    b.write_bytes(b"now-here")
    assert buildinfo.build_info(b)["binary_present"] is True


def test_the_endpoint_actually_carries_the_fields(tmp_path, monkeypatch):
    """모듈만 시험하면 엔드포인트에서 빼먹어도 초록이다 — 실제 응답을 본다."""
    from app.config import settings
    from app.main import create_app

    body = b"fake-binary"
    b = _mk(tmp_path, body, _INFO.format(sha=hashlib.sha256(body).hexdigest()))
    monkeypatch.setattr(settings, "kooremapper_bin", b)

    app = create_app()
    route = next(r for r in app.routes if getattr(r, "path", None) == "/api/health")
    data = route.endpoint()["data"]
    # 기존 네 칸이 그대로 있어야 한다 — 소비자가 셋 있다(supervisor.sh·start.sh·nginx).
    for k in ("status", "env", "name", "binary_present"):
        assert k in data, f"{k} 칸이 사라졌다 — {sorted(data)}"
    assert data["revision"] == "1234567890abcdef1234567890abcdef12345678", data
    assert data["binary_sha256"] == hashlib.sha256(body).hexdigest()
    assert data["revision_matches_binary"] is True


def test_the_cache_refreshes_when_only_build_info_changes(tmp_path):
    """⚠ 바이너리만 열쇠로 쓰면, 배포가 BUILD_INFO 만 갈았을 때 재기동 전까지 **낡은 리비전**을
    낸다 — 이 기능이 막으려던 바로 그 종류의 거짓말이다. 바이너리는 그대로 두고 확인한다."""
    body = b"fake-binary"
    sha = hashlib.sha256(body).hexdigest()
    b = _mk(tmp_path, body)                       # BUILD_INFO 없음
    assert buildinfo.build_info(b)["revision"] is None
    (tmp_path / "BUILD_INFO.txt").write_text(_INFO.format(sha=sha), encoding="utf-8")
    info = buildinfo.build_info(b)
    assert info["revision"] == "1234567890abcdef1234567890abcdef12345678", (
        "BUILD_INFO 가 내려앉았는데 여전히 모른다고 한다")
    assert info["revision_matches_binary"] is True
