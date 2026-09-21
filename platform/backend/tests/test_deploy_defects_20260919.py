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


def _endpoint_data(coro):
    """라우트 코루틴을 돌려 응답 봉투에서 data 만 꺼낸다(의존성 주입 없이 직접 부른다)."""
    import asyncio
    import json

    return json.loads(asyncio.run(coro).body)["data"]


# ── ④ 주소를 지어내지 않는다 ───────────────────────────────────────────────
class _Req:
    def __init__(self, headers=None, client_host="10.1.2.3"):
        self.headers = headers or {}
        self.client = type("C", (), {"host": client_host})()


def test_the_hint_says_unknown_instead_of_making_an_address_up(monkeypatch):
    """모르면 **명령을 만들지 않는다** — 반쯤 맞는 명령은 그대로 붙여넣어지고 "연결 안 된다"로 돌아온다."""
    from app.config import MCP_PUBLIC_URL_ENV, settings
    from app.modules.users import routes

    monkeypatch.setattr(settings, "mcp_public_url", "", raising=False)
    assert routes.mcp_public_url(_Req()) == ""
    snippet = routes.mcp_add_command(_Req(), "kr_secret_token")
    assert snippet == routes.MCP_URL_UNKNOWN
    assert "kr_secret_token" not in snippet
    # 그대로 붙여넣어도 **아무 일도 안 나야** 한다 — 주석 한 줄이고 인자가 없다
    assert snippet.lstrip().startswith("#"), f"명령처럼 보이면 붙여넣는다 — {snippet!r}"
    assert "--header" not in snippet and "--transport" not in snippet
    # ⚠ 안내가 **실제로 읽히는 키 이름**을 말해야 한다. 접두사 없는 MCP_PUBLIC_URL 은 무시되므로,
    # 그 이름을 안내하면 운영자가 시키는 대로 하고도 화면이 그대로인 닫힌 고리가 된다.
    assert MCP_PUBLIC_URL_ENV == "KOORM_MCP_PUBLIC_URL"
    assert MCP_PUBLIC_URL_ENV in snippet, "무엇을 설정해야 하는지 — 진짜 키 이름으로 말해야 한다"


def test_the_address_comes_only_from_config(monkeypatch):
    """프록시 헤더로 **지어내지 않는다** — 실측 세 경로 중 둘이 틀린 값을 냈다(포트 유실·내부 주소).

    루프백 폴백도 없앴다: request.client 는 TCP 상대라, MCP 경유 호출은 사람이 어디 있든
    늘 127.0.0.1 로 보인다 — 원격 사용자에게 자기 PC 주소를 건네게 된다."""
    from app.config import settings
    from app.modules.users import routes

    monkeypatch.setattr(settings, "mcp_public_url",
                        "https://set.example:8088/apps/kooremapper_mcp/mcp", raising=False)
    assert routes.mcp_public_url(_Req()) == "https://set.example:8088/apps/kooremapper_mcp/mcp"

    monkeypatch.setattr(settings, "mcp_public_url", "", raising=False)
    fwd = _Req({"x-forwarded-host": "portal.example", "x-forwarded-proto": "https"})
    assert routes.mcp_public_url(fwd) == "", "X-Forwarded-Host 로 만들면 포트가 빠진다"
    assert routes.mcp_public_url(_Req(client_host="127.0.0.1")) == "", "루프백 상대는 사람의 위치가 아니다"


def test_no_screen_hands_out_a_command_with_an_empty_url(monkeypatch):
    """세 자리가 **같은 함수**를 써야 한 요청에서 서로 다른 답이 안 나온다(요청서 ④ 고침 2).

    f-string 에 빈 주소를 끼우면 URL 칸만 빈 `claude mcp add … --header …` 가 나오고,
    화면이 그것을 복사 버튼과 함께 그린다 — claude 는 `--header` 값을 URL 로 먹는다."""
    from app.config import settings
    from app.modules.system import routes as system_routes
    from app.modules.users import routes as user_routes

    monkeypatch.setattr(settings, "mcp_public_url", "", raising=False)
    req = _Req()

    # ⚠ **엔드포인트를 실제로 부른다.** 임포트한 함수만 부르면 엔드포인트가 f-string 으로 되돌아가도
    # 시험이 초록이다(그 거짓 초록을 한 번 만들었다).
    caps = _endpoint_data(system_routes.capabilities(req, _user=None))
    for name, produced in (
        ("토큰 화면", user_routes.mcp_add_command(req, "kr_x")),
        ("capabilities", caps["mcp_add_hint"]),
    ):
        assert produced.lstrip().startswith("#"), f"{name}: 주소를 모르는데 명령을 만들었다 — {produced!r}"
        assert "--header" not in produced, f"{name}: URL 칸만 빈 명령이다 — {produced!r}"
    assert caps["mcp_url"] is None, "모르는데 주소가 있다고 한다"

    monkeypatch.setattr(settings, "mcp_public_url", "https://ok.example/mcp", raising=False)
    caps = _endpoint_data(system_routes.capabilities(req, _user=None))
    assert caps["mcp_url"] == "https://ok.example/mcp"
    assert "https://ok.example/mcp" in caps["mcp_add_hint"]
    assert "kooremapper  --header" not in caps["mcp_add_hint"]


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


def test_remove_also_stops_a_running_supervisor(tmp_path):
    """해제라고 말했으면 실제로 멈춘다 — 크론만 떼면 돌고 있는 루프가 남아 감시가 계속된다."""
    root, scripts, bin_dir, cron_file, _ = _install_tree(tmp_path)
    cron_file.write_text("* * * * * something  # koorm-autostart\n", encoding="utf-8")
    data = root / "platform" / "infra" / "data"
    # 돌고 있는 감독자를 흉내내고, pid 를 supervisor.sh 가 적는 자리에 적어 둔다
    _stub(scripts / "supervisor.sh", "sleep 30\n")
    holder = subprocess.Popen(["bash", str(scripts / "supervisor.sh")])
    try:
        (data / "supervisor.lock.d").mkdir(parents=True, exist_ok=True)
        (data / "supervisor.lock.d" / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
        r = _run_install(root, scripts, bin_dir, "--remove")
        assert "감독자도 멈췄다" in r.stdout, f"돌고 있는 감독자를 남겼다 — {r.stdout!r}"
        holder.wait(timeout=5)
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait()


def test_a_second_supervisor_does_nothing(fake_stack, tmp_path):
    """감독자가 둘이면 서로의 재기동을 밟는다 — 한쪽이 stop 한 것을 다른 쪽이 또 start 한다.

    ⚠ 프로세스 이름으로는 못 막는다(실측): 크론은 `bash /abs/…/supervisor.sh`, README 가 권하는
    방식은 `bash ./infra/scripts/supervisor.sh` 라 절대경로 패턴이 빗나간다. 파일 잠금으로 막는다."""
    root, scripts, marker, bin_dir = fake_stack
    appt = _stub(tmp_path / "apptainer", _LIST_WITHOUT_API)
    lock_dir = root / "platform" / "infra" / "data" / "supervisor.lock.d"
    lock_dir.mkdir(parents=True)
    # 살아 있는 '감독자' 를 흉내낸다 — 잠금의 근거는 우리가 적은 pid 다
    holder = subprocess.Popen(["bash", str(scripts / "supervisor.sh"), "--hold"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              env={"PATH": "/usr/bin:/bin", "KOORM_SUPERVISE_INTERVAL": "300",
                                   "APPTAINER": str(appt), "ALLOW_PLACEHOLDER_SECRETS": "1",
                                   "HOME": str(root)})
    try:
        (lock_dir / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
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


def test_status_does_not_report_unknown_as_not_running(tmp_path):
    """status.sh 는 사람이 보고 판단하는 자리다 — 모르는 것을 '안 돌고 있다' 로 적으면
    그 오해 위에서 다음 행동이 결정된다."""
    root, scripts = _script_tree(tmp_path, "status.sh")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub(bin_dir / "curl", 'echo 000\nexit 0\n')
    _stub(bin_dir / "ss", "exit 0\n")
    appt = _stub(tmp_path / "apptainer", _LIST_FAILS)
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "APPTAINER": str(appt),
           "ALLOW_PLACEHOLDER_SECRETS": "1", "HOME": str(root), "STUB_LOG": str(tmp_path / "s.log"),
           "KOORM_ENABLE_NGINX": "1"}
    r = subprocess.run(["bash", str(scripts / "status.sh")], capture_output=True, text=True,
                       cwd=str(root), env=env)
    assert "판정 불가" in r.stdout, f"모르는 것을 단정했다 — {r.stdout!r}"
    assert "nginx not running" not in r.stdout, f"모르는데 '안 돌고 있다' 고 적었다 — {r.stdout!r}"


def test_stop_does_not_report_false_success_when_it_cannot_tell(tmp_path):
    """살아 있는 것을 `✓ not running` 으로 넘기면 배포가 옛 인스턴스 위에서 계속된다."""
    root, scripts = _script_tree(tmp_path, "stop.sh")
    log = tmp_path / "s.log"
    appt = _stub(tmp_path / "apptainer", _LIST_FAILS)
    r = _run_script(root, scripts, "stop.sh", appt, STUB_LOG=str(log))
    assert "not running" not in r.stdout, f"모르는 것을 '안 돌고 있다'고 단정했다 — {r.stdout!r}"
    assert "instance stop" in log.read_text(encoding="utf-8"), "모르는데 stop 도 안 해 봤다"


# ── ① 에서 함께 고친 나머지 판정도 옛 grep 과 의미가 같나 ────────────────────
def _block(path, first, last):
    """스크립트에서 연속된 줄 묶음의 **실제 텍스트**를 떼어 온다(함수가 아닌 블록용)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    i = next(n for n, l in enumerate(lines) if first in l)
    j = next(n for n, l in enumerate(lines[i:], i) if last in l)
    return "\n".join(lines[i:j + 1]) + "\n"


def test_the_drive_listing_check_keeps_line_exact_matching(tmp_path):
    """옛 판정은 `grep -q '^koorm-bin\\.tar\\.gz$'` 였다 — **행 전체** 일치다.

    부분 일치로 느슨해지면 `koorm-bin.tar.gz.part`(전송 중 파일)을 완성본으로 읽어
    반쪽 아티팩트를 배포한다. 반대로 조기 종료가 남아 있으면 목록이 클 때 SIGPIPE 로
    거짓 음성이 나서 **조용히 낡은 dist 로 강등**된다. 둘 다 본다."""
    root = tmp_path / "repo"
    scripts = root / "platform" / "infra" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(SCRIPTS / "dist-from-drive.sh", scripts / "dist-from-drive.sh")
    (root / "platform" / ".env").write_text("KOORM_DRIVE_REMOTE=Stub:KooRemapper/dist\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    listing = tmp_path / "listing.txt"
    _stub(bin_dir / "rclone",
          'case "$*" in\n'
          f'  *--dirs-only*) echo "dist-20260101/"; echo "dist-20260202/" ;;\n'
          f'  lsf*) cat "{listing}" ;;\n'
          '  *) exit 0 ;;\n'
          'esac\n')

    def _source_for(text):
        listing.write_text(text, encoding="utf-8")
        r = subprocess.run(["bash", str(scripts / "dist-from-drive.sh")],
                           capture_output=True, text=True, cwd=str(root),
                           env={"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(root)})
        line = [l for l in r.stdout.splitlines() if l.startswith("→ source:")]
        assert line, f"source 를 못 정했다 — {r.stdout!r} {r.stderr!r}"
        return line[0].split("source:", 1)[1].strip()

    # 정확히 그 이름이 있으면 latest 를 쓴다
    assert _source_for("SHA256SUMS\nkoorm-bin.tar.gz\n").endswith("/latest")
    # 닮은 이름만 있으면 latest 가 아니다 — 행 전체 일치여야 한다
    assert _source_for("koorm-bin.tar.gz.part\nxkoorm-bin.tar.gz\n").endswith("/dist-20260202")
    # 목록이 파이프 버퍼보다 커도 거짓 음성이 없다(찾는 이름을 맨 앞에 둔다)
    big = "koorm-bin.tar.gz\n" + "".join(f"filler-{i:05d}.bin\n" for i in range(5000))
    assert _source_for(big).endswith("/latest"), "큰 목록에서 조용히 낡은 dist 로 강등했다"


def test_the_socket_owner_check_keeps_its_meaning(tmp_path):
    """`users:(` 가 보이면 소유자를 안 것이다 — 보일 때 경고하면 거짓 경보,
    안 보일 때 잠자면 사람이 ss 를 아무리 돌려도 범인 이름을 못 본다."""
    # 닫는 `fi` 까지 떼어야 온전한 블록이다
    block = _block(SCRIPTS / "start.sh", '_sock="$(ss -lptnH', 'fi')
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    def _warns(ss_output):
        _stub(bin_dir / "ss", f'cat <<\'EOF\'\n{ss_output}\nEOF\n')
        r = _sh("set -euo pipefail\nPOSTGRES_PORT=5436\n" + block,
                env={"PATH": f"{bin_dir}:/usr/bin:/bin"})
        assert r.returncode == 0, f"{r.stdout!r} {r.stderr!r}"
        return "소유자가 안 보인다" in r.stdout

    assert not _warns('LISTEN 0 244 127.0.0.1:5436 0.0.0.0:* users:(("postgres",pid=1,fd=7))')
    assert _warns("LISTEN 0 244 127.0.0.1:5436 0.0.0.0:*")
    assert _warns(""), "빈 출력은 소유자를 못 본 것이다"


def test_the_lock_is_not_inherited_by_a_long_lived_child(fake_stack, tmp_path):
    """⚠ 이 결함으로 **운영 감시가 실제로 멈췄다**(2026-09-21 01:26).

    `exec 9>파일` + flock 으로 잡으면 그 fd 를 **자식이 물려받는다.** 감독자가 띄운 apptainer
    인스턴스는 영원히 살아 있으므로 잠금을 놓지 않고, 이후 모든 회차가 "이미 돌고 있다" 로
    물러난다 — 잠금 하나 잘못 잡아 감시를 죽이는 것이다.

    그래서 첫 회차가 오래 사는 자식을 남기고 끝난 뒤, 다음 회차가 **정상으로 일해야** 한다."""
    root, scripts, marker, bin_dir = fake_stack
    appt = _stub(tmp_path / "apptainer", _LIST_WITHOUT_API)
    child_pid = tmp_path / "child.pid"
    # 재기동 스텁이 '인스턴스처럼' 오래 사는 자식을 남긴다(감독자가 죽어도 살아 있다)
    _stub(scripts / "restart-api-only.sh",
          f'echo called >> "{marker}"\nnohup sleep 120 >/dev/null 2>&1 &\n'
          f'echo $! > "{child_pid}"\ndisown\n')
    try:
        first = _run_once(root, scripts, bin_dir, appt, FAKE_HTTP_CODE="000")
        assert marker.exists(), f"첫 회차가 일하지 않았다 — {first.stdout!r}"
        marker.unlink()

        second = _run_once(root, scripts, bin_dir, appt, FAKE_HTTP_CODE="000")
        assert "이미 감독자가 돌고 있다" not in second.stdout, (
            f"오래 사는 자식이 잠금을 물려받아 감시가 멈췄다 — {second.stdout!r}")
        assert marker.exists(), f"둘째 회차가 일하지 않았다 — {second.stdout!r}"
    finally:
        pid = child_pid.read_text(encoding="utf-8").strip() if child_pid.exists() else ""
        if pid.isdigit():
            subprocess.run(["kill", pid], capture_output=True)


def test_a_dead_supervisors_lock_is_cleared(fake_stack, tmp_path):
    """잠금만 남기고 죽은 감독자가 있으면(kill -9 등) 다음 회차가 걷어내고 일해야 한다 —
    안 그러면 한 번의 사고가 영구 정지가 된다."""
    root, scripts, marker, bin_dir = fake_stack
    appt = _stub(tmp_path / "apptainer", _LIST_WITHOUT_API)
    lock_dir = root / "platform" / "infra" / "data" / "supervisor.lock.d"
    lock_dir.mkdir(parents=True)
    (lock_dir / "pid").write_text("999999\n", encoding="utf-8")   # 살아 있지 않은 pid

    r = _run_once(root, scripts, bin_dir, appt, FAKE_HTTP_CODE="000")
    assert "죽은 감독자가 남긴 잠금을 걷어낸다" in r.stdout, f"{r.stdout!r}"
    assert marker.exists(), f"걷어내고도 일하지 않았다 — {r.stdout!r}"
