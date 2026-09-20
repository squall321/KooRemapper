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


# postgres·mcp 는 있고 **api 만** 목록에서 빠진 거짓 음성 — ① 이 만들던 모양 그대로다
_LIST_WITHOUT_API = (
    'printf \'{"instances":[{"instance": "koorm_postgres"},'
    '{"instance": "koorm_mcp"}]}\\n\'\n'
)


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


def test_it_does_not_restart_a_healthy_api_when_the_listing_says_gone(fake_stack, tmp_path):
    """09-18 의 `restart 성공` 106회가 **정확히 이 모양**이다 — 목록은 "없다", 헬스는 200.

    원인(SIGPIPE)을 고쳤어도 판정 순서가 목록 먼저면 같은 꼴의 오판이 또 재기동으로 번진다.
    헬스 200 은 API 가 실제로 일하고 있다는 직접 증거다 — 그때는 목록이 무어라 하든 손대지 않는다."""
    root, scripts, marker, bin_dir = fake_stack
    appt = _stub(tmp_path / "apptainer", _LIST_WITHOUT_API)
    r = _run_once(root, scripts, bin_dir, appt, FAKE_HTTP_CODE="200")
    assert not marker.exists(), f"헬스 200 인 API 를 목록만 믿고 재기동했다 — {r.stdout!r}"


def test_a_truly_dead_api_is_still_restarted_with_the_right_reason(fake_stack, tmp_path):
    """반대로 망가뜨리지 않았는지 — 정말 죽었으면 되살리고, 이유도 정확히 적는다."""
    root, scripts, marker, bin_dir = fake_stack
    appt = _stub(tmp_path / "apptainer", _LIST_WITHOUT_API)
    r = _run_once(root, scripts, bin_dir, appt, FAKE_HTTP_CODE="000")
    assert marker.exists(), f"죽은 API 를 안 살렸다 — {r.stdout!r}"
    assert "인스턴스 없음" in r.stdout, f"이유를 목록에서 가져오지 않았다 — {r.stdout!r}"


def test_it_still_restarts_when_the_listing_is_unknown_and_health_is_bad(fake_stack, tmp_path):
    """모른다고 손을 놓지는 않는다 — 헬스가 독립적으로 나쁘면 그것이 근거다."""
    root, scripts, marker, bin_dir = fake_stack
    appt = _stub(tmp_path / "apptainer", 'echo "lock busy" >&2\nexit 255\n')
    r = _run_once(root, scripts, bin_dir, appt, FAKE_HTTP_CODE="503")
    assert marker.exists(), f"헬스가 503 인데 아무것도 안 했다 — {r.stdout!r}"


def test_the_restart_failure_logs_the_real_exit_code(fake_stack, tmp_path):
    """`$(date)` 가 `$?` 를 덮어써 436줄이 전부 `rc=0` 이었다 — 실패 가지인데 0 일 수는 없다."""
    root, scripts, marker, bin_dir = fake_stack
    appt = _stub(tmp_path / "apptainer",
                 'if [ "${1:-}" = "instance" ] && [ "${2:-}" = "start" ]; then exit 0; fi\n'
                 'printf \'{"instances":[{"instance": "koorm_postgres"},{"instance": "koorm_mcp"}]}\\n\'\n')
    # 헬스가 나빠야 재기동 가지에 닿는다 — 헬스 200 이면 (이제) 아무것도 안 한다
    r = _run_once(root, scripts, bin_dir, appt, FAKE_RESTART_RC="7", FAKE_HTTP_CODE="000")
    assert "api restart 실패(rc=7)" in r.stdout, f"진짜 종료코드를 안 남겼다 — {r.stdout!r}"


# ── ③ 감시에 공백이 없다 ───────────────────────────────────────────────────
def _install_tree(tmp_path):
    """install-autostart.sh 를 **스크립트째** 돌릴 수 있는 트리 — 크론과 감독자는 가짜다.

    함수만 떼어 돌리면 호출부를 지워도 시험이 초록이라 ③ 전체를 원복해도 못 잡는다."""
    root = tmp_path / "repo"
    scripts = root / "platform" / "infra" / "scripts"
    scripts.mkdir(parents=True)
    (root / "platform" / "infra" / "data").mkdir(parents=True)
    shutil.copy(SCRIPTS / "_common.sh", scripts / "_common.sh")
    shutil.copy(SCRIPTS / "install-autostart.sh", scripts / "install-autostart.sh")
    shutil.copy(PLATFORM / ".env.example", root / "platform" / ".env")
    sup_log = tmp_path / "sup.calls"
    _stub(scripts / "supervisor.sh", f'echo "$*" >> "{sup_log}"\nexit ${{SUP_RC:-0}}\n')
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    cron_file = tmp_path / "crontab.txt"
    _stub(bin_dir / "crontab",
          f'[ "${{1:-}}" = "-l" ] && {{ cat "{cron_file}" 2>/dev/null; exit $?; }}\n'
          f'[ "${{1:-}}" = "-" ] && {{ cat > "{cron_file}"; exit 0; }}\nexit 0\n')
    return root, scripts, bin_dir, cron_file, sup_log


def _run_install(root, scripts, bin_dir, *args, **extra):
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "ALLOW_PLACEHOLDER_SECRETS": "1",
           "HOME": str(root), **extra}
    return subprocess.run(["bash", str(scripts / "install-autostart.sh"), *args],
                          capture_output=True, text=True, cwd=str(root), env=env)


def test_install_leaves_no_supervision_gap(tmp_path):
    """설치는 보통 "지금 스택이 이상하다" 에서 하는 일이다 — 다음 재부팅까지 기다리면 안 된다.

    그리고 **루프가 죽어도 되살아나야** 한다. 매분 도는 `--once` 가 둘 다 해결한다
    (요청서 ③ 의 둘째 안). 겹쳐 도는 것은 supervisor.sh 의 파일 잠금이 막는다."""
    root, scripts, bin_dir, cron_file, sup_log = _install_tree(tmp_path)
    # 옛 @reboot 줄 + 남의 크론 줄이 있는 상태에서 설치한다(이관도 함께 본다)
    cron_file.write_text(
        "@reboot cd /repo && nohup bash /repo/platform/infra/scripts/supervisor.sh >> /log 2>&1 &"
        "  # koorm-autostart\n0 3 * * * /some/other/job\n", encoding="utf-8")

    r = _run_install(root, scripts, bin_dir)
    assert r.returncode == 0, f"{r.stdout!r} {r.stderr!r}"
    cron = cron_file.read_text(encoding="utf-8")
    assert "@reboot" not in cron, f"옛 @reboot 루프가 남았다 — 이관이 안 됐다\n{cron}"
    assert "* * * * *" in cron and "--once" in cron, f"매분 감시가 없다 — 루프가 죽으면 끝이다\n{cron}"
    assert "/some/other/job" in cron, "남의 크론 줄을 지웠다"
    # 설치한 그 자리에서 한 번 돌아야 한다(다음 정각까지 최대 1분을 비워 두지 않는다)
    assert sup_log.read_text(encoding="utf-8").strip() == "--once", "설치가 지금 점검하지 않았다"


def test_install_reports_a_failed_immediate_check(tmp_path):
    """즉시 점검이 실패했는데 ✓ 로 끝나면, 사람은 감시가 선 줄 안다."""
    root, scripts, bin_dir, cron_file, _ = _install_tree(tmp_path)
    cron_file.write_text("", encoding="utf-8")
    r = _run_install(root, scripts, bin_dir, SUP_RC="7")
    assert r.returncode != 0, f"실패를 성공으로 끝냈다 — {r.stdout!r}"
    assert "rc=7" in r.stderr, f"진짜 종료코드를 안 남겼다 — {r.stderr!r}"


def test_a_second_supervisor_does_nothing(fake_stack, tmp_path):
    """감독자가 둘이면 서로의 재기동을 밟는다 — 한쪽이 stop 한 것을 다른 쪽이 또 start 한다.

    ⚠ 프로세스 이름으로는 못 막는다(실측): 크론은 `bash /abs/…/supervisor.sh`, README 가 권하는
    방식은 `bash ./infra/scripts/supervisor.sh` 라 절대경로 패턴이 빗나간다. 파일 잠금으로 막는다."""
    root, scripts, marker, bin_dir = fake_stack
    appt = _stub(tmp_path / "apptainer", _LIST_WITHOUT_API)
    lock = root / "platform" / "infra" / "data" / "supervisor.lock"
    holder = subprocess.Popen(["bash", "-c", f'exec 8>"{lock}"; flock 8; sleep 30'])
    try:
        time.sleep(0.5)
        r = _run_once(root, scripts, bin_dir, appt, FAKE_HTTP_CODE="000")
        assert "이미 감독자가 돌고 있다" in r.stdout, f"둘째 감독자가 그냥 일했다 — {r.stdout!r}"
        assert not marker.exists(), "둘째 감독자가 재기동까지 했다"
    finally:
        holder.kill()
        holder.wait()


# ── ① 의 규율이 감독자 밖에서도 도나 ──────────────────────────────────────
def _script_tree(tmp_path, *names):
    root = tmp_path / "repo"
    scripts = root / "platform" / "infra" / "scripts"
    scripts.mkdir(parents=True)
    (root / "platform" / "infra" / "data" / "postgres" / "pgdata").mkdir(parents=True)
    (root / "platform" / "infra" / "data" / "postgres-run").mkdir(parents=True)
    (root / "platform" / "infra" / "data" / "postgres" / "pgdata" / "PG_VERSION").write_text("16\n")
    shutil.copy(PLATFORM / ".env.example", root / "platform" / ".env")
    for n in ("_common.sh", *names):
        shutil.copy(SCRIPTS / n, scripts / n)
    return root, scripts


def _run_script(root, scripts, name, appt, stdin="", **extra):
    env = {"PATH": "/usr/bin:/bin", "APPTAINER": str(appt),
           "ALLOW_PLACEHOLDER_SECRETS": "1", "HOME": str(root), **extra}
    return subprocess.run(["bash", str(scripts / name)], input=stdin,
                          capture_output=True, text=True, cwd=str(root), env=env)


# 목록 조회만 실패하는 apptainer — "모름(2)" 을 만드는 최소 스텁
_LIST_FAILS = ('echo "$*" >> "$STUB_LOG"\n'
               '[ "${1:-} ${2:-}" = "instance list" ] && exit 255\nexit 0\n')


def test_reset_db_refuses_to_wipe_when_it_cannot_tell(tmp_path):
    """**모름을 없음으로 읽으면 살아 있는 postmaster 위에서 pgdata 를 지운다.**

    그러면 인스턴스는 삭제된 inode 로 계속 돌고, 안내대로 start.sh 를 돌려도
    `✓ already running` 으로 돌아와 겉보기엔 멀쩡한데 내용이 없는 DB 가 된다."""
    root, scripts = _script_tree(tmp_path, "reset-db.sh")
    appt = _stub(tmp_path / "apptainer", _LIST_FAILS)
    pgdata = root / "platform" / "infra" / "data" / "postgres" / "pgdata" / "PG_VERSION"
    r = _run_script(root, scripts, "reset-db.sh", appt, stdin="yes\n",
                    STUB_LOG=str(tmp_path / "s.log"))
    assert r.returncode != 0, f"모르는 채로 지웠다 — {r.stdout!r}"
    assert pgdata.exists(), "살아 있을지 모르는 postgres 의 데이터를 지웠다"


def test_restart_api_only_stops_when_it_cannot_tell(tmp_path):
    """모름에서 stop 을 건너뛰면 곧바로 `already exists` 로 실패한다 — 09-18 의 62회가 그것이다.

    stop 은 없는 인스턴스에 무해하므로(이미 `|| true`), 모를 때는 시도하는 쪽으로 기운다."""
    root, scripts = _script_tree(tmp_path, "restart-api-only.sh")
    (root / "platform" / "infra" / "apptainer").mkdir(parents=True)
    (root / "platform" / "infra" / "apptainer" / "api.sif").write_text("")
    log = tmp_path / "s.log"
    appt = _stub(tmp_path / "apptainer", _LIST_FAILS)
    _run_script(root, scripts, "restart-api-only.sh", appt, STUB_LOG=str(log))
    assert "instance stop koorm_api" in log.read_text(encoding="utf-8"), "모른다고 stop 을 건너뛰었다"


def test_stop_does_not_report_false_success_when_it_cannot_tell(tmp_path):
    """살아 있는 것을 `✓ not running` 으로 넘기면 배포가 옛 인스턴스 위에서 계속된다."""
    root, scripts = _script_tree(tmp_path, "stop.sh")
    log = tmp_path / "s.log"
    appt = _stub(tmp_path / "apptainer", _LIST_FAILS)
    r = _run_script(root, scripts, "stop.sh", appt, STUB_LOG=str(log))
    assert "not running" not in r.stdout, f"모르는 것을 '안 돌고 있다'고 단정했다 — {r.stdout!r}"
    assert "instance stop" in log.read_text(encoding="utf-8"), "모르는데 stop 도 안 해 봤다"
