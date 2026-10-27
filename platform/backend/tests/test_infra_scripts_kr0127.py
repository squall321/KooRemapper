# cae00 요청 KR-05(_common.sh 세션 버스 자동 채움)·KR-09(install-autostart crontab 실패 안전) 셸 시험.
import os
import shutil
import subprocess
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
PLATFORM = BACKEND.parent
SCRIPTS = PLATFORM / "infra" / "scripts"


def _stub(path: Path, body: str) -> Path:
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "repo"
    scripts = root / "platform" / "infra" / "scripts"
    scripts.mkdir(parents=True)
    (root / "platform" / "infra" / "data").mkdir(parents=True)
    (root / "platform" / "infra" / "apptainer").mkdir(parents=True)
    for f in ("_common.sh", "install-autostart.sh"):
        shutil.copy(SCRIPTS / f, scripts / f)
    shutil.copy(PLATFORM / ".env.example", root / "platform" / ".env")
    _stub(scripts / "supervisor.sh", 'exit 0\n')   # install 끝의 즉시 점검을 통과시킨다
    return root, scripts


# ── KR-05 — 세션 버스 자동 채움 ───────────────────────────────────────


def test_common_fills_session_bus_when_socket_exists(repo):
    root, _ = repo
    uid = os.getuid()
    bus = Path(f"/run/user/{uid}/bus")
    # 두 변수를 지운 상태로 소싱한다
    r = subprocess.run(
        ["bash", "-c",
         f'unset DBUS_SESSION_BUS_ADDRESS XDG_RUNTIME_DIR; source "{root}/platform/infra/scripts/_common.sh"; '
         f'echo "BUS=${{DBUS_SESSION_BUS_ADDRESS:-}}"'],
        capture_output=True, text=True, cwd=str(root),
        env={"PATH": "/usr/bin:/bin", "HOME": str(root), "ALLOW_PLACEHOLDER_SECRETS": "1"}, timeout=60)
    assert r.returncode == 0, r.stderr[-400:]
    if not bus.exists():
        pytest.skip(f"{bus} 가 없다(세션 버스 없는 환경) — 자동 채움은 소켓이 있을 때만")
    assert f"BUS=unix:path=/run/user/{uid}/bus" in r.stdout, r.stdout


def test_common_keeps_explicit_session_bus(repo):
    root, _ = repo
    r = subprocess.run(
        ["bash", "-c",
         f'source "{root}/platform/infra/scripts/_common.sh"; echo "BUS=${{DBUS_SESSION_BUS_ADDRESS:-}}"'],
        capture_output=True, text=True, cwd=str(root),
        env={"PATH": "/usr/bin:/bin", "HOME": str(root), "ALLOW_PLACEHOLDER_SECRETS": "1",
             "DBUS_SESSION_BUS_ADDRESS": "unix:path=/custom/bus"}, timeout=60)
    assert "BUS=unix:path=/custom/bus" in r.stdout, r.stdout   # 이미 있는 값은 안 건드린다


# ── KR-09 — crontab -l 실패 안전 ──────────────────────────────────────
def _run_install(root, scripts, mode):
    rec = root / "crontab_stdin.txt"
    bindir = root / "bin"
    bindir.mkdir(exist_ok=True)
    # crontab 스텁 — `-l` 은 mode 에 따라, `-`(설치)는 stdin 을 rec 에 적는다
    _stub(bindir / "crontab", f'''if [ "$1" = "-l" ]; then
  case "{mode}" in
    none)      echo "no crontab for tester" >&2; exit 1 ;;
    transient) echo "crontab: cannot read /var/spool/cron/crontabs/tester: Permission denied" >&2; exit 1 ;;
    ok)        exit 0 ;;
  esac
elif [ "$1" = "-" ]; then
  cat > "{rec}"
fi
''')
    env = {"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(root), "ALLOW_PLACEHOLDER_SECRETS": "1"}
    r = subprocess.run(["bash", str(scripts / "install-autostart.sh")],
                       capture_output=True, text=True, cwd=str(root), env=env, timeout=60)
    return r, (rec.read_text() if rec.exists() else None)


def test_install_stops_on_transient_crontab_failure(repo):
    """일시 실패(「크론 없음」이 아님)에는 crontab 을 덮어쓰지 않고 멈춘다 — 백업·감시 줄을 날리지 않는다."""
    root, scripts = repo
    r, written = _run_install(root, scripts, "transient")
    assert r.returncode != 0, r.stdout
    assert written is None, f"일시 실패인데 crontab 을 다시 썼다: {written!r}"
    assert "덮어쓰지 않고 멈춘다" in (r.stdout + r.stderr)


def test_install_proceeds_when_no_crontab(repo):
    """「no crontab for <user>」 는 빈 목록이 맞다 — 설치가 진행된다."""
    root, scripts = repo
    r, written = _run_install(root, scripts, "none")
    assert r.returncode == 0, (r.stdout + r.stderr)[-500:]
    assert written is not None and "koorm-autostart" in written and "koorm-backup" in written, written
