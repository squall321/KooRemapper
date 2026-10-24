# 감독자가 MCP 인스턴스의 유무만이 아니라 포트가 연결을 받는지 보는지 — 인스턴스만 남고 서버가 죽은 경우(HWAXPortal followups-1017 FU-D22, 2026-10-19)
"""왜 — 10-18 07:11 UTC dev 의 earlyoom 이 koorm_mcp 인스턴스 안의 서버만 SIGTERM 으로 죽였다. 인스턴스는 남아 감독자가 '있다' 만 보고 14시간
매분 ✓ 를 찍었고 :8701 은 비어 있었다(게이트웨이의 KooRemapper 도구가 통째로 빠졌다).

  · 인스턴스가 확실히 있는데 MCP 가 두 번 연결 안 됨(000) → instance stop → 같은 회차의 '없으면 띄운다' 가 다시 띄운다.
  · HTTP 코드가 오면(406 등) 산 것이다 · 한 번의 깜박임으로는 내리지 않는다 · 목록 조회가 실패한 '모름' 은 손대지 않는다.

감독자를 실제로 한 번(--once) 돌린다 — apptainer · curl · pgrep · start.sh · restart-api-only.sh 는 스텁이다(test_supervisor_pg_liveness 와 같은 꼴).
"""
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
def stack(tmp_path):
    root = tmp_path / "repo"
    scripts = root / "platform" / "infra" / "scripts"
    scripts.mkdir(parents=True)
    (root / "platform" / "infra" / "data").mkdir(parents=True)
    (root / "platform" / "infra" / "apptainer").mkdir(parents=True)
    for f in ("_common.sh", "supervisor.sh"):
        shutil.copy(SCRIPTS / f, scripts / f)
    shutil.copy(PLATFORM / ".env.example", root / "platform" / ".env")
    calls = tmp_path / "calls"
    _stub(scripts / "restart-api-only.sh", f'echo restart-api >> "{calls}"\n')
    _stub(scripts / "start.sh", f'echo start.sh >> "{calls}"\n')
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # MCP 주소(/mcp)는 FAKE_MCP_SEQ 의 코드를 차례로(마지막 값을 계속), 그 밖의 헬스는 200
    mcp_seq = tmp_path / "mcp_seq"
    _stub(bin_dir / "curl", f'''case "$*" in
  */mcp*) read -r -a s < "{mcp_seq}"; printf "%s" "${{s[0]}}"; [ "${{#s[@]}}" -gt 1 ] && printf '%s\\n' "${{s[*]:1}}" > "{mcp_seq}"; exit 0 ;;
  *http_code*) printf "200" ;;
  *) printf "{{}}" ;;
esac
''')
    _stub(bin_dir / "pgrep", 'printf "1\\n"\n')
    # 목록 — koorm_mcp 는 stop 뒤 빠지고 start 뒤 돌아온다. list_fail 이 있으면 조회 실패
    appt = _stub(tmp_path / "apptainer", f'''case "$1" in
  instance)
    case "$2" in
      list)
        [ -f "{tmp_path}/list_fail" ] && exit 1
        m=""; [ -f "{tmp_path}/mcp_gone" ] || m=',{{"instance": "koorm_mcp"}}'
        printf '{{"instances":[{{"instance": "koorm_postgres"}},{{"instance": "koorm_api"}}%s]}}\\n' "$m" ;;
      stop) echo "stop $3" >> "{calls}"; [ "$3" = koorm_mcp ] && : > "{tmp_path}/mcp_gone" ;;
      start) n="${{@: -1}}"; echo "start $n" >> "{calls}"; [ "$n" = koorm_mcp ] && rm -f "{tmp_path}/mcp_gone" ;;
    esac ;;
  exec) exit 0 ;;
esac
''')

    def run(mcp_codes="406", **env):
        mcp_seq.write_text(mcp_codes + "\n")
        full = {"PATH": f"{bin_dir}:/usr/bin:/bin", "APPTAINER": str(appt), "ALLOW_PLACEHOLDER_SECRETS": "1",
                "HOME": str(root), "KOORM_PG_RECHECK_S": "0", "KOORM_MCP_RECHECK_S": "0", **env}
        r = subprocess.run(["bash", str(scripts / "supervisor.sh"), "--once"], capture_output=True, text=True,
                           cwd=str(root), env=full, timeout=120)
        return r, (calls.read_text().split() if calls.exists() else [])
    return run, tmp_path


def test_MCP_가_응답하면_손대지_않는다(stack):
    run, _ = stack
    r, calls = run("406")
    assert calls == [] and "✓ supervise check done" in r.stdout, (calls, r.stdout)


def test_인스턴스는_있는데_MCP_가_두_번_연결_안_되면_내리고_같은_회차에_다시_띄운다(stack):
    run, _ = stack
    r, calls = run("000 000 406")
    assert calls == ["stop", "koorm_mcp", "start", "koorm_mcp"], (calls, r.stdout)
    assert "mcp 무응답(인스턴스는 있다" in r.stdout and "mcp restart 성공" in r.stdout, r.stdout


def test_한_번의_깜박임으로는_내리지_않는다(stack):
    run, _ = stack
    r, calls = run("000 406")
    assert calls == [], (calls, r.stdout)


def test_목록_조회가_실패하면_MCP_는_손대지_않는다(stack):
    run, tmp = stack
    (tmp / "list_fail").write_text("")
    r, calls = run("000")
    assert "koorm_mcp" not in calls, (calls, r.stdout)
    # 손대지 않되 회차는 끝까지 간다 — 종전엔 `instance_running …; _mcp_rc=$?` 가 set -e(_common.sh) 아래서 rc 2 로 스크립트를 끝내
    # 이 시험은 '죽어서' 지나갔다(nginx 확인 · 심장박동 줄이 없었다).
    assert r.returncode == 0 and "✓ supervise check done" in r.stdout, (r.returncode, r.stdout, r.stderr)


def test_MCP_인스턴스가_없으면_같은_회차에_띄우고_끝까지_간다(stack):
    """인스턴스가 통째로 사라진 경우 — 559f582 부터 `instance_running …; _mcp_rc=$?` 가 set -e 아래서 rc 1 로 스크립트를 끝내 아래 '없으면
    띄운다' 에 닿지 못했다. MCP 가 다시 뜨지 않아 게이트웨이의 DynaForge 도구가 빠진 채 남는다(HWAXPortal 10-25 cae00 점검)."""
    run, tmp = stack
    (tmp / "mcp_gone").write_text("")
    r, calls = run("000")
    assert calls == ["start", "koorm_mcp"], (calls, r.stdout, r.stderr)
    assert "mcp down → start" in r.stdout and "mcp restart 성공" in r.stdout, r.stdout
    assert r.returncode == 0 and "✓ supervise check done" in r.stdout, (r.returncode, r.stdout, r.stderr)
