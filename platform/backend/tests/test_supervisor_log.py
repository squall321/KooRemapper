# 감독자 로그가 **언제** 를 말하고 끝없이 자라지 않는가 (P1-10 ②)
"""왜 이 시험이 있나 (2026-09-27).

크론이 매분 `supervisor.sh --once` 를 돌려 로그에 `>>` 로 붙이는데, 그 마지막 줄
`✓ supervise check done` 에 **시각이 없었다.** 실측 — 로그 18,216줄 중 **10,695줄(59%)** 이
그 한 문장이고 전부 같은 글자였다. "언제 죽었나" 를 로그에서 읽을 수 없었다.
회전 장치도 없어 712KB 까지 자라 있었다.

⚠ 시각을 붙여야 하는 것은 **감독자 자신의 줄**뿐이다. 들여쓴 apptainer 출력(`INFO:` 994줄 ·
`FATAL:` 994줄)은 그쪽 프로그램의 것이므로 건드리면 안 된다.

⚠ 줄 수를 단언하지 않는다 — 오늘 10,695 이고 내일 다르다. 계약은 "감독자가 내는 줄은 시각으로
시작한다" 와 "임계를 넘으면 회전한다" 두 개다.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SUP = REPO / "platform/infra/scripts/supervisor.sh"
_TS = re.compile(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] ")


def _run(log: Path, *, max_bytes: int | None = None):
    env = dict(os.environ, KOORM_SUPERVISE_LOG=str(log))
    if max_bytes is not None:
        env["KOORM_SUPERVISE_LOG_MAX"] = str(max_bytes)
    with log.open("a") as fh:
        return subprocess.run(["bash", str(SUP), "--once"], stdout=fh, stderr=fh,
                              env=env, timeout=300, cwd=str(REPO)).returncode


@pytest.mark.skipif(not SUP.exists(), reason="supervisor.sh 없음")
def test_heartbeat_line_carries_a_timestamp():
    """심장박동 줄이 시각으로 시작해야 한다 — 이것이 로그의 대부분을 차지하는 줄이다."""
    d = Path(tempfile.mkdtemp(prefix="suplog_"))
    log = d / "supervisor.log"
    assert _run(log) == 0
    lines = [l for l in log.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    own = [l for l in lines if not l.startswith((" ", "\t"))]
    assert own, lines
    beat = [l for l in own if "supervise check done" in l]
    assert beat, own
    assert _TS.match(beat[-1]), beat[-1]


@pytest.mark.skipif(not SUP.exists(), reason="supervisor.sh 없음")
def test_every_own_line_is_timestamped():
    """감독자 자신의 줄은 전부 시각으로 시작한다. 들여쓴 apptainer 출력은 제외한다."""
    d = Path(tempfile.mkdtemp(prefix="suplog_"))
    log = d / "supervisor.log"
    _run(log)
    bad = [
        l for l in log.read_text(encoding="utf-8", errors="replace").splitlines()
        if l.strip() and not l.startswith((" ", "\t")) and not _TS.match(l)
        # apptainer 가 줄머리 없이 내는 것들 — 그쪽 프로그램의 출력이다.
        and not l.startswith(("INFO:", "FATAL:", "WARNING:", "ERROR:"))
    ]
    assert not bad, bad


@pytest.mark.skipif(not SUP.exists(), reason="supervisor.sh 없음")
def test_rotates_above_threshold_and_keeps_the_tail():
    """임계를 넘으면 회전하고 옛 내용을 `.1` 로 보존한다.

    ⚠ `mv` 가 아니라 `cp`+truncate 여야 한다 — 크론의 `>>` 가 이미 파일을 열고 있으므로 `mv`
    하면 옛 inode 에 계속 쓰이고 새 파일이 비어 있게 된다.
    """
    d = Path(tempfile.mkdtemp(prefix="suplog_"))
    log = d / "supervisor.log"
    log.write_text("x" * 3000 + "\n", encoding="utf-8")
    assert _run(log, max_bytes=1000) == 0
    assert (d / "supervisor.log.1").exists(), "옛 내용을 보존해야 한다"
    assert (d / "supervisor.log.1").stat().st_size > 3000
    assert log.stat().st_size < 3000, "회전 뒤 본 파일은 줄어 있어야 한다"
    assert "회전" in log.read_text(encoding="utf-8", errors="replace"), "회전했다고 말해야 한다"


@pytest.mark.skipif(not SUP.exists(), reason="supervisor.sh 없음")
def test_does_not_rotate_below_threshold():
    """임계 아래에서는 건드리지 않는다 — 매분 도는 것이 매분 파일을 갈면 안 된다."""
    d = Path(tempfile.mkdtemp(prefix="suplog_"))
    log = d / "supervisor.log"
    log.write_text("keep\n", encoding="utf-8")
    assert _run(log, max_bytes=1_000_000) == 0
    assert not (d / "supervisor.log.1").exists()
    assert log.read_text(encoding="utf-8", errors="replace").startswith("keep\n")
