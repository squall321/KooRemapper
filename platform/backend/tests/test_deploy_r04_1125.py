# 포털 요청 R-04 — SIF 설치가 도는 인스턴스 밑을 덮지 않고, stop 뒤 인스턴스가 정말 사라질 때까지 기다리는지 셸을 실제로 돌려 본다
"""계획 docs/01-plan/features/hwax-request-1125.plan.md 2절.

① `dist-from-drive.sh` 의 `_install_if_changed` — 같은 디렉터리 임시 파일 + 이름 바꾸기(포털 `11874eb9` 와 같은 넷을 잰다).
   열린 파일 서술자가 「그 SIF 로 도는 인스턴스」 다.
② `_common.sh` 의 `wait_instance_gone` · `stop.sh` · `restart-api-only.sh` — stop 이 돌아와도 목록에 몇 번 더 남는 가짜
   apptainer 로 돈다. 내려가는 중인 인스턴스 위에 start 를 걸던 것이 10-28 의 52분 멈춤이다.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
PLATFORM = BACKEND.parent
SCRIPTS = PLATFORM / "infra" / "scripts"
NOT_ROOT = pytest.mark.skipif(os.geteuid() == 0, reason="root 는 권한을 무시한다")


def _func(name: str, path: Path) -> str:
    src = path.read_text(encoding="utf-8")
    i = src.index(f"{name}() {{")
    j = src.index("\n}\n", i)
    return src[i:j + 3]


def _stub(path: Path, body: str) -> Path:
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


# ── ① 원자적 설치 ──────────────────────────────────────────────────────────
_INSTALL = _func("_install_if_changed", SCRIPTS / "dist-from-drive.sh")


def _install(src, dst) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", f'set -euo pipefail\n{_INSTALL}\n'
                                         f'_install_if_changed "{src}" "{dst}" && rc=0 || rc=$?\necho "rc=$rc"'],
                          capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})


def test_install_never_rewrites_the_file_a_running_instance_has_open(tmp_path):
    src = tmp_path / "cache/api.sif"; src.parent.mkdir(); src.write_bytes(b"NEW-IMAGE" * 1000)
    os.utime(src, (1_600_000_000, 1_600_000_000))
    dst = tmp_path / "apptainer/api.sif"; dst.parent.mkdir(); dst.write_bytes(b"OLD-IMAGE" * 1000)
    ino0 = dst.stat().st_ino
    with open(dst, "rb") as running:
        r = _install(src, dst)
        assert "rc=0" in r.stdout, r.stdout + r.stderr
        assert running.read() == b"OLD-IMAGE" * 1000, "도는 인스턴스 밑의 내용이 바뀌었다(제자리 덮어쓰기)"
    assert dst.read_bytes() == b"NEW-IMAGE" * 1000 and dst.stat().st_ino != ino0, "새 파일은 새 inode 다"
    assert int(dst.stat().st_mtime) == 1_600_000_000, "mtime 은 원본 그대로 — 포털 재기동 판정 지문이 안정된다"
    assert sorted(p.name for p in dst.parent.iterdir()) == ["api.sif"], "임시 파일이 남지 않는다"


def test_install_leaves_the_same_content_untouched(tmp_path):
    src = tmp_path / "new.sif"; src.write_bytes(b"same")
    dst = tmp_path / "live.sif"; dst.write_bytes(b"same")
    ino0, m0 = dst.stat().st_ino, dst.stat().st_mtime_ns
    r = _install(src, dst)
    assert "rc=0" in r.stdout and "같음" in r.stdout
    assert (dst.stat().st_ino, dst.stat().st_mtime_ns) == (ino0, m0)


def test_install_keeps_a_symlinked_destination(tmp_path):
    """/data 이관의 심링크 브리지 — 링크에 이름 바꾸기를 하면 링크가 파일이 되어 브리지가 끊긴다. 가리키는 파일을 바꾼다."""
    src = tmp_path / "new.sif"; src.write_bytes(b"new")
    real = tmp_path / "data/api.sif"; real.parent.mkdir(); real.write_bytes(b"old")
    link = tmp_path / "apptainer/api.sif"; link.parent.mkdir(); link.symlink_to(real)
    assert "rc=0" in _install(src, link).stdout
    assert link.is_symlink() and real.read_bytes() == b"new"
    assert sorted(p.name for p in real.parent.iterdir()) == ["api.sif"]


@NOT_ROOT
def test_install_fails_without_touching_the_old_file_when_the_directory_is_not_writable(tmp_path):
    src = tmp_path / "new.sif"; src.write_bytes(b"new")
    dst = tmp_path / "live/x.sif"; dst.parent.mkdir(); dst.write_bytes(b"old"); dst.parent.chmod(0o555)
    try:
        r = _install(src, dst)
    finally:
        dst.parent.chmod(0o755)
    assert "rc=2" in r.stdout and "설치 실패" in r.stderr and dst.read_bytes() == b"old", r.stdout + r.stderr
    assert sorted(p.name for p in dst.parent.iterdir()) == ["x.sif"]


@NOT_ROOT
def test_install_refuses_a_read_only_file_in_a_writable_directory(tmp_path):
    """이름 바꾸기는 디렉터리 권한만 본다 — 먼저 보지 않으면 읽기 전용(다른 소유자) 파일도 갈아 끼운다."""
    src = tmp_path / "new.sif"; src.write_bytes(b"new")
    dst = tmp_path / "x.sif"; dst.write_bytes(b"old"); dst.chmod(0o444)
    r = _install(src, dst)
    assert "rc=2" in r.stdout and dst.read_bytes() == b"old"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["new.sif", "x.sif"]


@NOT_ROOT
def test_install_leaves_no_temp_file_when_the_copy_fails(tmp_path):
    """임시 파일을 만든 뒤 복사가 깨지면(원본을 못 읽음 · 디스크) 옛 파일 그대로 · 임시 파일을 치운다."""
    src = tmp_path / "src/new.sif"; src.parent.mkdir(); src.write_bytes(b"new"); src.chmod(0o000)
    dst = tmp_path / "live/x.sif"; dst.parent.mkdir(); dst.write_bytes(b"old")
    try:
        r = _install(src, dst)
    finally:
        src.chmod(0o644)
    assert "rc=2" in r.stdout and dst.read_bytes() == b"old", r.stdout + r.stderr
    assert sorted(p.name for p in dst.parent.iterdir()) == ["x.sif"], "임시 파일이 남았다"


# ── ② stop 뒤 기다리기 ─────────────────────────────────────────────────────
# 가짜 apptainer — 인스턴스마다 상태 파일 하나. stop 은 돌아오지만 목록에서 LINGER 번 더 보인다(`run` 이면 끝내 안 사라진다).
# start 는 아직 목록에 있으면 `already exists` 로 실패한다(실물과 같다). LIST_FAILS=1 이면 목록 조회가 실패한다(모름).
_APPT = r'''
echo "$*" >> "$STUB_LOG"
case "${1:-} ${2:-}" in
  "instance list")
    [ "${LIST_FAILS:-0}" = "1" ] && exit 255
    out='{"instances":['; sep=''
    for f in "$STATE"/*; do
      [ -e "$f" ] || continue
      name=$(basename "$f"); c=$(cat "$f")
      if [ "$c" != "run" ]; then
        if [ "$c" -le 0 ]; then rm -f "$f"; continue; fi
        echo $((c - 1)) > "$f"
      fi
      out="$out$sep{\"instance\": \"$name\"}"; sep=','
    done
    echo "$out]}"; exit 0 ;;
  "instance stop")
    [ -e "$STATE/$3" ] && echo "${LINGER:-2}" > "$STATE/$3"; exit 0 ;;
  "instance start")
    name="${@: -1}"
    [ -e "$STATE/$name" ] && { echo "FATAL: instance $name already exists" >&2; exit 255; }
    echo run > "$STATE/$name"; exit 0 ;;
esac
exit 0
'''


@pytest.fixture()
def stack(tmp_path):
    root = tmp_path / "repo"
    scripts = root / "platform" / "infra" / "scripts"
    scripts.mkdir(parents=True)
    (root / "platform" / "infra" / "data").mkdir(parents=True)
    (root / "platform" / "infra" / "apptainer").mkdir(parents=True)
    (root / "platform" / "infra" / "apptainer" / "api.sif").write_text("")
    pgdata = root / "platform" / "infra" / "data" / "postgres" / "pgdata"
    pgdata.mkdir(parents=True)
    (pgdata / "PG_VERSION").write_text("16\n")
    (root / "platform" / "infra" / "data" / "postgres-run").mkdir(parents=True)
    shutil.copy(PLATFORM / ".env.example", root / "platform" / ".env")
    for n in ("_common.sh", "stop.sh", "restart-api-only.sh", "restart.sh", "reset-db.sh"):
        shutil.copy(SCRIPTS / n, scripts / n)
    _stub(scripts / "start.sh", f'echo start.sh >> "{tmp_path / "s.log"}"\n')   # restart.sh 가 부르는 것 — 불렸는지만 본다
    state = tmp_path / "state"
    state.mkdir()
    appt = _stub(tmp_path / "apptainer", _APPT)
    return root, scripts, state, appt, tmp_path / "s.log"


def _run(stack, name, *running, stdin="", **extra):
    root, scripts, state, appt, log = stack
    for inst in running:
        (state / inst).write_text("run")
    env = {"PATH": "/usr/bin:/bin", "APPTAINER": str(appt), "ALLOW_PLACEHOLDER_SECRETS": "1", "HOME": str(root),
           "STUB_LOG": str(log), "STATE": str(state), "KOORM_STOP_WAIT_S": "5", **extra}
    r = subprocess.run(["bash", str(scripts / name)], input=stdin, capture_output=True, text=True, cwd=str(root),
                       env=env, timeout=60)
    return r, (log.read_text(encoding="utf-8").splitlines() if log.exists() else [])


def _first(lines, text):
    return next(i for i, l in enumerate(lines) if l.startswith(text))


def test_restart_waits_until_the_old_api_is_gone_before_starting(stack):
    r, calls = _run(stack, "restart-api-only.sh", "koorm_api", LINGER="3")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "already exists" not in r.stderr, "내려가는 중인 인스턴스 위에 start 를 걸었다"
    stop, start = _first(calls, "instance stop koorm_api"), _first(calls, "instance start")
    assert sum(c == "instance list --json" for c in calls[stop:start]) >= 4, "사라질 때까지 목록을 다시 보지 않았다"


def test_restart_gives_up_without_starting_when_the_old_api_never_goes(stack):
    r, calls = _run(stack, "restart-api-only.sh", "koorm_api", LINGER="run", KOORM_STOP_WAIT_S="1")
    assert r.returncode != 0, "상한을 넘겼는데 성공으로 끝났다"
    assert "사라지지 않았다" in r.stderr
    assert not any(c.startswith("instance start") for c in calls), "안 사라진 인스턴스 위에 start 를 걸었다"


def test_restart_does_not_take_unknown_for_gone(stack):
    r, calls = _run(stack, "restart-api-only.sh", "koorm_api", LIST_FAILS="1", KOORM_STOP_WAIT_S="1")
    assert r.returncode != 0
    assert "instance stop koorm_api" in calls, "모른다고 stop 을 건너뛰었다(09-18 의 62회)"
    assert not any(c.startswith("instance start") for c in calls), "모르는 것을 사라졌다고 보고 start 를 걸었다"


def test_stop_waits_for_each_instance_in_order(stack):
    r, calls = _run(stack, "stop.sh", "koorm_nginx", "koorm_mcp", "koorm_api", "koorm_postgres", LINGER="2")
    assert r.returncode == 0, r.stdout + r.stderr
    stops = [c for c in calls if c.startswith("instance stop")]
    assert stops == [f"instance stop {n}" for n in ("koorm_nginx", "koorm_mcp", "koorm_api", "koorm_postgres")]
    api, pg = _first(calls, "instance stop koorm_api"), _first(calls, "instance stop koorm_postgres")
    assert sum(c == "instance list --json" for c in calls[api:pg]) >= 3, "api 가 사라지기 전에 postgres 를 내렸다"
    assert not list(stack[2].iterdir()), "다 내려가지 않았다"


def test_stop_tries_every_instance_and_fails_when_one_never_goes(stack):
    root, scripts, state, appt, log = stack
    (state / "koorm_mcp").write_text("run")
    # mcp 만 끝내 안 사라진다 — stop 이 와도 상태를 `run` 으로 되돌리는 덧칠
    _stub(appt, _APPT.replace('[ -e "$STATE/$3" ] && echo "${LINGER:-2}" > "$STATE/$3"',
                              '[ -e "$STATE/$3" ] && { [ "$3" = koorm_mcp ] && echo run > "$STATE/$3" || echo 1 > "$STATE/$3"; }'))
    r, calls = _run(stack, "stop.sh", "koorm_api", "koorm_postgres", KOORM_STOP_WAIT_S="1")
    assert r.returncode != 0, "하나가 안 사라졌는데 성공으로 끝났다"
    assert "koorm_mcp" in r.stderr and "사라지지 않았다" in r.stderr
    assert "instance stop koorm_postgres" in calls, "하나가 막혔다고 나머지를 시도하지 않았다"


def test_stop_skips_what_is_surely_absent(stack):
    r, calls = _run(stack, "stop.sh")
    assert r.returncode == 0 and r.stdout.count("not running") == 4
    assert not any(c.startswith("instance stop") for c in calls)


# ── ③ 같은 뿌리 다섯(사용자 「다섯도 기다리게」, 11-25) ─────────────────────────────

def test_restart_sh_does_not_call_start_over_a_lingering_api(stack):
    r, calls = _run(stack, "restart.sh", "koorm_api", LINGER="run", KOORM_STOP_WAIT_S="1")
    assert r.returncode != 0 and "사라지지 않았다" in r.stderr
    assert "start.sh" not in calls, "안 사라진 인스턴스 위에 start.sh 를 불렀다"


def test_restart_sh_calls_start_once_the_api_is_gone(stack):
    r, calls = _run(stack, "restart.sh", "koorm_api", LINGER="2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert calls.index("start.sh") > _first(calls, "instance stop koorm_api")


def test_reset_db_does_not_wipe_under_a_postgres_that_is_still_going(stack):
    root = stack[0]
    pg = root / "platform" / "infra" / "data" / "postgres" / "pgdata" / "PG_VERSION"
    r, _ = _run(stack, "reset-db.sh", "koorm_postgres", stdin="yes\n", LINGER="run", KOORM_STOP_WAIT_S="1")
    assert r.returncode != 0 and "지우지 않는다" in r.stdout, r.stdout + r.stderr
    assert pg.exists(), "내려가는 중인 postmaster 밑의 데이터를 지웠다"


def test_reset_db_wipes_once_postgres_is_gone(stack):
    root = stack[0]
    r, _ = _run(stack, "reset-db.sh", "koorm_postgres", stdin="yes\n", LINGER="2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (root / "platform" / "infra" / "data" / "postgres" / "pgdata").exists()


# stop 바로 뒤 기다리지 않아도 되는 자리 — 까닭이 있는 것만. 감독자의 mcp 는 사라진 것을 확인한 뒤에만 띄운다(`gone_for_sure`).
_NO_WAIT_NEEDED = {("supervisor.sh", "INST_MCP")}


def test_every_instance_stop_in_the_scripts_is_followed_by_a_wait():
    """start.sh 의 postgres 재기동 두 자리처럼 통째로 돌리기 어려운 자리를 같이 지킨다 — 새 stop 자리가 생겨도 여기서 걸린다."""
    missing = []
    for path in sorted(SCRIPTS.glob("*.sh")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if "instance stop" not in line or line.lstrip().startswith("#") or "echo" in line.split("instance stop")[0]:
                continue
            if any(path.name == name and tag in line for name, tag in _NO_WAIT_NEEDED):
                continue
            if not any("wait_instance_gone" in l for l in lines[i:i + 5]):
                missing.append(f"{path.name}:{i + 1}: {line.strip()}")
    assert not missing, "stop 뒤 기다리지 않는 자리:\n" + "\n".join(missing)

