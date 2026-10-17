# 감독자가 인스턴스 목록만이 아니라 postgres 가 접속을 받는지 보는지 — 빈 셸 · 겹친 셸 · DB 가 죽은 503(HWAX 포털 수정 제안서 K1, 2026-10-18)
"""왜 — 10-17 09:32 ~ 10-18 03:53, 같은 이름의 셸이 겹친 뒤 postgres 없는 셸이 목록에 남아 감독자가 18시간 동안 매분 ✓ 를 찍었다.
:5436 은 비어 있었고 사람별 로그인(/api/v1/auth/sso)이 500 이었다.

  · 인스턴스는 있는데 pg_isready 가 두 번 응답 없음(2) → stop → start.sh, 그 뒤 접속을 받아야 '복구 성공'.
  · 기동 · 종료 중(1) · 판정 불가(127 등)는 손대지 않는다 — '모름' 으로 파괴적 행동을 하지 않는다(_common.sh 의 규율).
  · 같은 이름의 셸이 둘이면 알리고 손대지 않는다.
  · 헬스가 DB 때문에 503(database.ok=false)이면 API 를 다시 띄우지 않는다.
  · start.sh 가 rc 0 이어도 postgres 가 받지 않으면 '복구 실패' 다.

감독자를 실제로 한 번(--once) 돌린다 — apptainer · curl · pgrep · start.sh · restart-api-only.sh 는 스텁이다(test_deploy_defects_20260919 와 같은 꼴).
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


_LIST = 'printf \'{"instances":[{"instance": "koorm_postgres"},{"instance": "koorm_api"},{"instance": "koorm_mcp"}]}\\n\''
_LIST_NO_PG = 'printf \'{"instances":[{"instance": "koorm_api"},{"instance": "koorm_mcp"}]}\\n\''


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
    _stub(scripts / "start.sh", f'echo start.sh >> "{calls}"\nexit ${{FAKE_START_RC:-0}}\n')
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # 헬스 — `-w '%{http_code}'` 이면 코드, 아니면 본문
    _stub(bin_dir / "curl", 'case "$*" in *http_code*) printf "%s" "${FAKE_HTTP_CODE:-200}" ;; *) printf "%s" "${FAKE_HTTP_BODY:-{}}" ;; esac\n')
    _stub(bin_dir / "pgrep", 'printf "%s\\n" "${FAKE_PG_SHELLS:-1}"; [ "${FAKE_PG_SHELLS:-1}" -gt 0 ]\n')
    # pg_isready 결과를 차례로 — FAKE_PG_SEQ="2 2 0" 이면 첫 번째 2, 두 번째 2, 그다음부터 0
    seq = tmp_path / "pg_seq"
    appt = _stub(tmp_path / "apptainer", f'''case "$1" in
  instance)
    case "$2" in
      list) {{ if [ -f "{tmp_path}/no_pg" ]; then {_LIST_NO_PG}; else {_LIST}; fi; }} ;;
      stop) echo "stop $3" >> "{calls}" ;;
    esac ;;
  exec)
    read -r -a s < "{seq}" 2>/dev/null || s=()
    rc="${{s[0]:-0}}"; [ "${{#s[@]}}" -gt 1 ] && printf '%s\\n' "${{s[*]:1}}" > "{seq}"
    exit "$rc" ;;
esac
''')

    def run(pg_seq="0", **env):
        seq.write_text(pg_seq + "\n")
        full = {"PATH": f"{bin_dir}:/usr/bin:/bin", "APPTAINER": str(appt), "ALLOW_PLACEHOLDER_SECRETS": "1",
                "HOME": str(root), "KOORM_PG_RECHECK_S": "0", **env}
        r = subprocess.run(["bash", str(scripts / "supervisor.sh"), "--once"], capture_output=True, text=True,
                           cwd=str(root), env=full, timeout=120)
        return r, (calls.read_text().split() if calls.exists() else [])
    return run, tmp_path


def test_살아_있으면_손대지_않는다(stack):
    run, _ = stack
    r, calls = run("0")
    assert calls == [] and "✓ supervise check done" in r.stdout, r.stdout


def test_인스턴스는_있는데_두_번_응답_없음이면_내리고_다시_띄운다(stack):
    run, _ = stack
    r, calls = run("2 2 0")
    assert calls[:3] == ["stop", "koorm_postgres", "start.sh"], (calls, r.stdout)
    assert "postgres 무응답(인스턴스는 있다" in r.stdout and "postgres 복구 성공(인스턴스는 있는데 무응답 — 접속 확인)" in r.stdout


def test_한_번의_깜박임으로는_내리지_않는다(stack):
    run, _ = stack
    r, calls = run("2 0")
    assert "start.sh" not in calls and "stop" not in calls, (calls, r.stdout)


def test_기동_중이나_판정_불가는_손대지_않는다(stack):
    run, _ = stack
    r, calls = run("1")
    assert calls == [] and "기동·종료 중" in r.stdout
    r, calls = run("127")
    assert calls == [] and "판정 보류" in r.stdout


def test_같은_이름의_셸이_둘이면_알리고_손대지_않는다(stack):
    run, _ = stack
    r, calls = run("2 2 2", FAKE_PG_SHELLS="2")
    assert "start.sh" not in calls and "stop" not in calls, calls
    assert "인스턴스 셸이 2개다 — 손대지 않는다" in r.stdout


def test_DB_가_죽은_503_이면_API_를_다시_띄우지_않는다(stack):
    run, _ = stack
    r, calls = run("1", FAKE_HTTP_CODE="503",
                   FAKE_HTTP_BODY='{"success":false,"data":{"status":"degraded","database":{"ok":false,"error":"X"}}}')
    assert "restart-api" not in calls, (calls, r.stdout)
    assert "api 는 떠 있고 DB 가 응답하지 않는다" in r.stdout
    r, calls = run("0", FAKE_HTTP_CODE="503", FAKE_HTTP_BODY="{}")       # DB 아닌 503 — 종전대로 다시 띄운다
    assert "restart-api" in calls


def test_start_sh_가_rc_0_이어도_postgres_가_안_받으면_복구_실패다(stack):
    run, tmp = stack
    (tmp / "no_pg").write_text("")                                      # 인스턴스 없음 → start.sh
    r, calls = run("2 2 2 2 2 2 2")
    assert calls == ["start.sh"], calls
    assert "start.sh 는 rc 0 인데 postgres 가 접속을 받지 않는다" in r.stdout and "복구 성공" not in r.stdout
