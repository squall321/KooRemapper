# 게시가 컨테이너에서 못 도는 바이너리를 내보내지 않는다 — glibc 관문(P0-4)
"""왜 이 시험이 있나 (2026-09-25, 덱 계약 2차 P0-4).

09-24 에 다른 세션이 호스트 cmake 로 빌드해 `platform/backend/bin/KooRemapper` 가 GLIBC_2.38 을
요구하고 있었다. 그대로 게시했으면 폐쇄망 운영에 **실행 자체가 안 되는** 바이너리가 나갔다.
예전 `dist-to-drive.sh` 는 그 값을 BUILD_INFO 에 **적기만** 했다 — 거절 분기가 한 줄도 없었다.

상한이 2.36 이 아니라 **2.35** 인 이유(2026-09-25 실측 `ldd --version`).
  SmartTwinPreprocessor.sif  2.35   ← pyKooCAE REMAP 체인이 돌리는 그것. 가장 낮다
  cli.sif                    2.36
  api.sif / mcp.sif          2.41
계획서의 "2.37 이상 거절" 은 두 칸 느슨하다 — 2.36 을 요구하는 바이너리는 그 관문을 통과하고도
REMAP 체인에서 죽는다. 그래서 **2.36 도 거절**하는지를 여기서 못 박는다.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
PLATFORM = BACKEND.parent
SCRIPTS = PLATFORM / "infra" / "scripts"


def _stub(path: Path, body: str) -> Path:
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _tree(tmp_path, *, glibc: str | None):
    """dist-to-drive.sh 를 **스크립트째** 돌릴 수 있는 가짜 리포. objdump·rclone 만 가짜다."""
    root = tmp_path / "repo"
    scripts = root / "platform" / "infra" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(SCRIPTS / "dist-to-drive.sh", scripts / "dist-to-drive.sh")
    (root / "platform" / ".env").write_text("KOORM_DRIVE_REMOTE=Stub:KooRemapper/dist\n",
                                            encoding="utf-8")
    binp = root / "platform" / "backend" / "bin" / "KooRemapper"
    binp.parent.mkdir(parents=True)
    binp.write_bytes(b"\x7fELF fake binary\n")
    dist = root / "platform" / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    (dist / "index.portal.html").write_text("<html></html>", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    rclone_log = tmp_path / "rclone.calls"
    # ⚠ 스텁이 스테이지를 **떠 둔다.** dist-to-drive.sh 는 mktemp + trap 으로 스테이지를 지우므로,
    # 올라간 tar 안을 열어 보려면 rclone 이 불린 그 순간에 사본을 남겨야 한다.
    capture = tmp_path / "uploaded"
    _stub(bin_dir / "rclone",
          f'echo "$*" >> "{rclone_log}"\n'
          f'if [ "${{1:-}}" = "copy" ]; then\n'
          f'  for a in "$@"; do case "$a" in /*/) [ -d "$a" ] && mkdir -p "{capture}" && cp -a "$a". "{capture}/" ;; esac; done\n'
          f'fi\nexit 0\n')
    if glibc is not None:
        # objdump -T 의 실제 출력 모양을 흉내낸다(심볼 여러 개 + 여러 버전).
        _stub(bin_dir / "objdump",
              'cat <<EOF\n'
              '0000000000000000      DF *UND*  0000000000000000  GLIBC_2.2.5 memcpy\n'
              '0000000000000000      DF *UND*  0000000000000000  GLIBC_2.14  memmove\n'
              f'0000000000000000      DF *UND*  0000000000000000  GLIBC_{glibc}  someSym\n'
              'EOF\n')
    return root, scripts, bin_dir, rclone_log, capture


def _run(root, scripts, bin_dir, *args):
    # ⚠ PATH 에서 실제 objdump 를 가린다 — 가짜를 앞에 두는 것으로는 부족하고, 스텁을 안 만든
    # 경우(glibc=None)에 진짜가 잡히면 '알 수 없음' 갈래를 시험할 수 없다.
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(root)}
    return subprocess.run(["bash", str(scripts / "dist-to-drive.sh"), *args],
                          capture_output=True, text=True, cwd=str(root), env=env, timeout=300)


@pytest.mark.parametrize("glibc,ok", [
    ("2.34", True),    # compat 빌더(debian:12) 산출물의 실제 값
    ("2.35", True),    # 상한과 같다 — 통과해야 한다
    ("2.36", False),   # ⚠ cli.sif 는 되지만 SmartTwinPreprocessor.sif(2.35)에서 죽는다
    ("2.38", False),   # 09-24 사고의 그 값(호스트 cmake)
    ("2.41", False),
])
def test_the_gate_uses_the_lowest_consumer_not_cli_sif(tmp_path, glibc, ok):
    root, scripts, bin_dir, rclone_log, _cap = _tree(tmp_path, glibc=glibc)
    r = _run(root, scripts, bin_dir)
    if ok:
        assert r.returncode == 0, f"GLIBC_{glibc} 를 거절했다 — {r.stdout[-400:]} {r.stderr[-300:]}"
        assert f"GLIBC_{glibc} <= 2.35" in r.stdout, r.stdout[-300:]
    else:
        assert r.returncode != 0, f"GLIBC_{glibc} 를 통과시켰다 — {r.stdout[-400:]}"
        assert f"GLIBC_{glibc} 를 요구한다" in r.stdout, r.stdout[-300:]
        # ⚠ 거절이 **업로드 전**이어야 의미가 있다. 올린 뒤 거절하면 이미 나간 것이다.
        assert not rclone_log.exists(), f"거절했는데 rclone 을 불렀다 — {rclone_log.read_text()}"


def test_an_unknown_glibc_is_refused_by_default(tmp_path):
    """확인 못 한 것을 게시하지 않는다. 폐쇄망(binutils 없음)에서 조용히 통과하면 관문이 없는 것과 같다."""
    root, scripts, bin_dir, rclone_log, _cap = _tree(tmp_path, glibc=None)
    r = _run(root, scripts, bin_dir)
    assert r.returncode != 0, f"확인 못 한 채 게시했다 — {r.stdout[-400:]}"
    assert "확인할 수 없다" in r.stdout, r.stdout[-300:]
    assert not rclone_log.exists(), "거절했는데 rclone 을 불렀다"


def test_the_escape_hatch_is_explicit(tmp_path):
    """알고 넘기는 길은 있어야 한다 — 다만 **게시 명령에 흔적이 남는** 플래그여야 한다."""
    root, scripts, bin_dir, rclone_log, _cap = _tree(tmp_path, glibc=None)
    r = _run(root, scripts, bin_dir, "--allow-unknown-glibc")
    assert r.returncode == 0, f"{r.stdout[-400:]} {r.stderr[-300:]}"
    assert "--allow-unknown-glibc 로 넘어간다" in r.stdout, r.stdout[-300:]
    assert rclone_log.exists(), "통과했는데 업로드하지 않았다"


def test_the_build_info_records_the_limit_it_used(tmp_path):
    """BUILD_INFO 가 '컨테이너 허용' 을 적는데 그 숫자가 관문과 달라지면 다음 사람이 속는다."""
    root, scripts, bin_dir, _log, capture = _tree(tmp_path, glibc="2.34")
    r = _run(root, scripts, bin_dir, "--dry-run")
    assert r.returncode == 0, f"{r.stdout[-400:]} {r.stderr[-300:]}"
    assert "실사용 상한: <= GLIBC_2.35" in r.stdout, r.stdout[-600:]
    assert "SmartTwinPreprocessor.sif" in r.stdout, "어느 컨테이너 기준인지 안 적었다"


def test_build_info_is_not_duplicated_inside_the_binary_tar(tmp_path):
    """받는 쪽은 BUILD_INFO 를 bin/ 에 내려놓는다 — 그것이 tar 에도 실리면 **옛 것**이 섞인다.

    ⚠ `--dry-run` 으로는 못 본다(tar 의 **내용**을 찍지 않는다 — 처음에 그렇게 써서 헛통과했다).
    실제로 업로드를 태우고 rclone 스텁이 떠 둔 tar 를 열어 본다."""
    import tarfile

    root, scripts, bin_dir, _log, capture = _tree(tmp_path, glibc="2.34")
    stale = root / "platform" / "backend" / "bin" / "BUILD_INFO.txt"
    stale.write_text("commit        : deadbeef_STALE\n", encoding="utf-8")
    r = _run(root, scripts, bin_dir)
    assert r.returncode == 0, f"{r.stdout[-400:]} {r.stderr[-300:]}"
    tgz = capture / "koorm-bin.tar.gz"
    assert tgz.is_file(), f"업로드된 tar 를 못 떠 왔다 — {sorted(p.name for p in capture.glob('*')) if capture.exists() else '없음'}"
    with tarfile.open(tgz) as tf:
        names = tf.getnames()
    assert "bin/KooRemapper" in names, names
    assert "bin/BUILD_INFO.txt" not in names, f"옛 BUILD_INFO 가 tar 에 실렸다 — {names}"
    # 그리고 게시물에는 **새로 만든** BUILD_INFO 가 따로 올라가 있어야 한다
    published = capture / "BUILD_INFO.txt"
    assert published.is_file(), "BUILD_INFO.txt 가 게시물에 없다"
    assert "deadbeef_STALE" not in published.read_text(encoding="utf-8")
