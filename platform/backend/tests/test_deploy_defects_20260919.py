# 배포 결함 넷(2026-09-19 요청서)이 되돌아오지 못하게 막는다 — 셸 세 자리를 **실제로 돌려** 본다
"""왜 파이썬 시험이 셸을 돌리나 — 이 리포의 회귀는 pytest 하나로 돈다. 스크립트의 **실제 텍스트**를
떼어 가짜 apptainer 로 돌리면, 누가 그 스크립트를 고치는 순간 이 시험이 고친 것을 돈다.

무엇을 막나(요청서 ①~④, dev 실측으로 재현한 것만):
 ① `instance_running` 이 떠 있는 인스턴스를 "없다"로 읽어 감독자가 멀쩡한 API 를 재기동(09-18 하루 168회).
    기구는 `… | grep -q` + `pipefail`(조기 종료 → apptainer SIGPIPE 141). 경합 중 600회 중 81회 재현.
 ② 재기동 실패 rc 가 늘 0(`$(date)` 가 `$?` 를 덮어씀) — 로그 436줄이 전부 거짓.
 ③ 설치가 크론만 넣고 감독자를 지금 띄우지 않아 재부팅 전까지 감시 공백.
 ④ MCP 접속 힌트가 공개 주소를 지어냄(원격 사용자에게 127.0.0.1 을 건넴).
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
PLATFORM = BACKEND.parent
SCRIPTS = PLATFORM / "infra" / "scripts"
sys.path.insert(0, str(BACKEND))


def _func(name: str, path: Path) -> str:
    """셸 파일에서 함수 하나의 실제 텍스트를 떼어 온다."""
    src = path.read_text(encoding="utf-8")
    i = src.index(f"{name}() {{")
    j = src.index("\n}\n", i)
    return src[i:j + 3]


def _sh(script: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin", **(env or {})})


def _stub(path: Path, body: str) -> Path:
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


# ── ① instance_running ─────────────────────────────────────────────────────
# 호출부는 전부 조건문 안이라(`if ! instance_running …`) `set -e` 가 함수 안에서 꺼진다 —
# 시험도 같은 자리에서 부른다. 바로 부르면 `set -e` 가 rc 를 읽기 전에 스크립트를 끝낸다.
_RC_PROBE = '\ninstance_running koorm_api && rc=0 || rc=$?\necho "rc=$rc"\n'

_BIG_LIST = (
    'printf \'{"instances":[\\n\'\n'
    # 찾는 인스턴스가 **맨 앞**이다 — 옛 구현의 `grep -q` 는 여기서 끝나고 뒤를 안 읽는다
    'printf \'  {"instance": "koorm_api", "pid": 1},\\n\'\n'
    'for i in $(seq 1 4000); do printf \'  {"instance": "filler%04d", "pid": 2},\\n\' "$i"; done\n'
    'printf \'  {"instance": "koorm_last", "pid": 3}]}\\n\'\n'
)


def test_a_running_instance_is_not_reported_as_gone(tmp_path):
    """목록이 파이프 버퍼(64KiB)보다 크면 옛 구현은 **떠 있는 것을 '없다'** 로 읽었다."""
    appt = _stub(tmp_path / "apptainer", _BIG_LIST)
    r = _sh(f"set -euo pipefail\nAPPTAINER={appt}\n"
            + _func("instance_running", SCRIPTS / "_common.sh")
            + _RC_PROBE)
    assert "rc=0" in r.stdout, f"떠 있는 인스턴스를 못 봤다 — {r.stdout!r} {r.stderr!r}"


def test_a_failed_listing_is_unknown_not_absent(tmp_path):
    """조회 실패(2)와 부재(1)를 가른다 — 뭉개면 '모른다' 가 재기동의 근거가 된다."""
    appt = _stub(tmp_path / "apptainer", 'echo "cannot read instance dir" >&2\nexit 255\n')
    r = _sh(f"set -euo pipefail\nAPPTAINER={appt}\n"
            + _func("instance_running", SCRIPTS / "_common.sh")
            + _RC_PROBE)
    assert "rc=2" in r.stdout, f"조회 실패를 부재로 읽었다 — {r.stdout!r}"


def test_an_absent_instance_is_still_absent(tmp_path):
    """고치면서 반대로 망가뜨리지 않았는지 — 정말 없으면 1 이어야 감독자가 되살린다."""
    appt = _stub(tmp_path / "apptainer", 'printf \'{"instances":[{"instance": "other"}]}\\n\'\n')
    r = _sh(f"set -euo pipefail\nAPPTAINER={appt}\n"
            + _func("instance_running", SCRIPTS / "_common.sh")
            + _RC_PROBE)
    assert "rc=1" in r.stdout, r.stdout


# ── ②·감독자 판정 ──────────────────────────────────────────────────────────
@pytest.fixture()
def fake_stack(tmp_path):
    """감독자를 실제로 한 번(--once) 돌릴 수 있는 최소 트리 — 재기동 스크립트는 스텁이다."""
    root = tmp_path / "repo"
    scripts = root / "platform" / "infra" / "scripts"
    scripts.mkdir(parents=True)
    (root / "platform" / "infra" / "data").mkdir(parents=True)
    (root / "platform" / "infra" / "apptainer").mkdir(parents=True)
    for f in ("_common.sh", "supervisor.sh"):
        shutil.copy(SCRIPTS / f, scripts / f)
    shutil.copy(PLATFORM / ".env.example", root / "platform" / ".env")
    marker = tmp_path / "restart_called"
    _stub(scripts / "restart-api-only.sh", f'echo called >> "{marker}"\nexit ${{FAKE_RESTART_RC:-0}}\n')
    _stub(scripts / "start.sh", f'echo start >> "{marker}"\n')
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub(bin_dir / "curl", 'printf "%s" "${FAKE_HTTP_CODE:-200}"\n')   # 헬스 응답을 시험이 정한다
    return root, scripts, marker, bin_dir


def _run_once(root, scripts, bin_dir, appt, **extra):
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "APPTAINER": str(appt),
           "ALLOW_PLACEHOLDER_SECRETS": "1", "HOME": str(root), **extra}
    return subprocess.run(["bash", str(scripts / "supervisor.sh"), "--once"],
                          capture_output=True, text=True, cwd=str(root), env=env)


def test_it_does_not_restart_a_healthy_api_when_the_listing_fails(fake_stack, tmp_path):
    """**이 라운드의 본체** — 목록을 못 읽었는데 헬스가 멀쩡하면 손대지 않는다."""
    root, scripts, marker, bin_dir = fake_stack
    appt = _stub(tmp_path / "apptainer", 'echo "lock busy" >&2\nexit 255\n')
    r = _run_once(root, scripts, bin_dir, appt, FAKE_HTTP_CODE="200")
    assert not marker.exists(), f"멀쩡한 API 를 재기동했다 — {r.stdout!r}"
    assert "판정 보류" in r.stdout, f"보류를 말하지 않았다(보이지 않으면 없는 것이다) — {r.stdout!r}"


def test_it_still_restarts_when_health_is_bad(fake_stack, tmp_path):
    """모른다고 손을 놓지는 않는다 — 헬스가 독립적으로 나쁘면 그것이 근거다."""
    root, scripts, marker, bin_dir = fake_stack
    appt = _stub(tmp_path / "apptainer", 'echo "lock busy" >&2\nexit 255\n')
    _run_once(root, scripts, bin_dir, appt, FAKE_HTTP_CODE="503")
    assert marker.exists(), "헬스가 503 인데 아무것도 안 했다"


def test_the_restart_failure_logs_the_real_exit_code(fake_stack, tmp_path):
    """`$(date)` 가 `$?` 를 덮어써 436줄이 전부 `rc=0` 이었다 — 실패 가지인데 0 일 수는 없다."""
    root, scripts, marker, bin_dir = fake_stack
    appt = _stub(tmp_path / "apptainer",
                 'if [ "${1:-}" = "instance" ] && [ "${2:-}" = "start" ]; then exit 0; fi\n'
                 'printf \'{"instances":[{"instance": "koorm_postgres"},{"instance": "koorm_mcp"}]}\\n\'\n')
    r = _run_once(root, scripts, bin_dir, appt, FAKE_RESTART_RC="7")
    assert "api restart 실패(rc=7)" in r.stdout, f"진짜 종료코드를 안 남겼다 — {r.stdout!r}"


# ── ③ 설치가 감독자를 지금 띄운다 ──────────────────────────────────────────
def test_install_starts_the_supervisor_now_and_only_once(tmp_path):
    """크론만 넣으면 **재부팅 전까지 감시가 없다.** 그리고 둘 띄우면 서로의 재기동을 밟는다."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    _stub(scripts / "supervisor.sh", "sleep 20\n")
    body = (f'SCRIPT_DIR="{scripts}"\nREPO_ROOT="{tmp_path}"\nDATA_DIR="{data}"\n'
            f'LOG="{data}/supervisor.log"\n'
            + _func("start_supervisor_now", SCRIPTS / "install-autostart.sh"))
    try:
        t0 = time.time()
        first = _sh(body + "\nstart_supervisor_now\n", env={"HOME": str(tmp_path)})
        elapsed = time.time() - t0
        assert "지금 띄웠다" in first.stdout, f"{first.stdout!r} {first.stderr!r}"
        # ⚠ **바로 돌아와야 한다.** `( … & )` 서브셸로 띄우면 호출자가 감독자 수명만큼 매달린다
        # (실측: 스텁 sleep 4 에 4.0초). 설치를 감싸는 자동화에서는 영영 안 끝난다는 뜻이다.
        assert elapsed < 5, f"설치 호출이 {elapsed:.1f}초 매달렸다 — 감독자가 살아 있는 동안 계속된다"
        time.sleep(0.3)
        second = _sh(body + "\nstart_supervisor_now\n", env={"HOME": str(tmp_path)})
        assert "이미 실행 중" in second.stdout, f"감독자를 둘 띄웠다 — {second.stdout!r}"
        n = subprocess.run(["pgrep", "-fc", f"bash {scripts}/supervisor.sh"],
                           capture_output=True, text=True).stdout.strip()
        assert n == "1", f"감독자 프로세스가 {n}개다"
    finally:
        subprocess.run(["pkill", "-f", f"bash {scripts}/supervisor.sh"], capture_output=True)


# ── ④ 주소를 지어내지 않는다 ───────────────────────────────────────────────
class _Req:
    def __init__(self, headers=None, client_host="10.1.2.3"):
        self.headers = headers or {}
        self.client = type("C", (), {"host": client_host})()


def test_the_hint_says_unknown_instead_of_handing_out_loopback(monkeypatch):
    """원격 사용자에게 `127.0.0.1:8701` 을 주면 **틀렸는데 맞아 보인다** — 자기 PC 를 찌른다."""
    from app.config import settings
    from app.modules.users import routes

    monkeypatch.setattr(settings, "mcp_public_url", "", raising=False)
    assert routes.mcp_public_url(_Req()) == ""
    snippet = routes._mcp_add_snippet("kr_secret_token", _Req())
    assert snippet == routes.MCP_URL_UNKNOWN
    assert "kr_secret_token" not in snippet, "반쯤 맞는 명령을 주면 그대로 붙여넣는다"
    assert "MCP_PUBLIC_URL" in snippet, "무엇을 하면 되는지 말해야 한다"


def test_the_hint_uses_config_then_proxy_then_loopback(monkeypatch):
    """아는 경우는 그대로 낸다 — 설정 > 프록시 경로 > (호출자가 루프백일 때만) 루프백."""
    from app.config import settings
    from app.modules.users import routes

    monkeypatch.setattr(settings, "mcp_public_url", "https://set.example/mcp", raising=False)
    assert routes.mcp_public_url(_Req()) == "https://set.example/mcp"

    monkeypatch.setattr(settings, "mcp_public_url", "", raising=False)
    fwd = _Req({"x-forwarded-host": "portal.example", "x-forwarded-proto": "https"})
    assert routes.mcp_public_url(fwd) == "https://portal.example/apps/kooremapper_mcp/mcp"

    local = _Req(client_host="127.0.0.1")
    assert routes.mcp_public_url(local) == f"http://127.0.0.1:{settings.mcp_port}/mcp"
