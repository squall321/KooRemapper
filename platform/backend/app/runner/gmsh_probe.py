# gmsh 가 진짜로 실행되나 — 큐에 넣기 전에 확인하고 /api/health 에 싣는다
"""왜 이 모듈이 있나 (2026-09-25, 덱 계약 2차 P1-9).

`meshfix` 는 `requires_gmsh` 인 유일한 op 인데, 플랫폼은 그 사실을 **보지 않고** 큐에 넣었다.
gmsh 가 없거나 망가져 있으면 잡이 한참 돌다 `Gmsh failed (exit 32512)` 로 죽는다 — 사람은
자기 덱이 잘못된 줄 안다.

⚠ **파일이 있다고 gmsh 인 것은 아니다.** 이 박스의 `~/.local/bin/gmsh` 는 깨진 파이썬 래퍼이고,
실사용 컨테이너에서도 홈 바인드로 같은 것이 보인다(회신 §1②). 그래서 여기서도 바이너리와
똑같이 **`--version` 을 실제로 돌려** 판정한다.

⚠ 탐색 순서는 `src/commands/meshfix.cpp` 의 `findGmshExe` 를 **그대로 따라간다.** 두 구현이
갈리면 한쪽이 틀린 채로 초록이 된다 — 이 리포가 `*INCLUDE` 판정에서 이미 당한 모양이라,
`tests/test_gmsh_probe.py` 가 둘이 같은 답을 내는지 못 박는다.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

_cache: dict | None = None
_cache_key: tuple | None = None

# ⚠ 줄 **어딘가에** 판번호가 있으면 받아들인다. "첫 글자가 숫자여야 한다" 로 못 박으면
# **정상 래퍼**가 걸린다 — 회귀 시험의 gmsh 래퍼는 `cp "$1" …` 를 먼저 해서 `--version` 이
# `cp --version` 이 되고 `cp (GNU coreutils) 8.32` 를 낸다. 깨진 래퍼는 rc≠0 이라 이 느슨한
# 판정으로도 걸러진다.
_VERSION = re.compile(r"\d+\.\d+")


def _responds(path: Path) -> str | None:
    """`--version` 을 돌려 버전 문자열을 얻는다. gmsh 가 아니면 None."""
    try:
        p = subprocess.run([str(path), "--version"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    first = (p.stdout or "").strip().splitlines()
    if not first or not _VERSION.search(first[0]):
        return None
    return first[0].strip()


def _candidates(binary: Path) -> list[Path]:
    """`findGmshExe` 와 같은 순서 — 환경변수 · 바이너리 옆 · PATH · /opt."""
    out: list[Path] = []
    env = os.environ.get("KOOREMAPPER_GMSH")
    if env:
        # ⚠ 명시 지정이 있으면 **그것 하나만** 본다. 망가졌다고 몰래 다른 것으로 갈아타면
        # 무엇이 돌았는지 알 수 없게 된다(바이너리도 같은 규율이다).
        #
        # 다만 바이너리는 명시 지정을 **검증하지 않는다**(지목한 명령을 시험 삼아 돌리면
        # 부작용이 난다 — gmsh 래퍼가 `cp "$1" …` 를 먼저 하는 실제 사례가 있다). 여기서는
        # 큐에 넣기 전 판정이 목적이라 한 번 돌려 보되, 실패해도 **다른 것으로 갈아타지 않는다.**
        return [Path(env)]
    d = binary.parent
    for name in ("gmsh", "gmsh.exe"):
        out.append(d / "gmsh" / name)
    try:
        for entry in sorted(d.iterdir()):
            if entry.is_dir() and entry.name.startswith("gmsh"):
                for name in ("gmsh", "gmsh.exe"):
                    out.append(entry / name)
                    out.append(entry / "bin" / name)
    except OSError:
        pass
    which = shutil.which("gmsh")
    if which:
        out.append(Path(which))
    opt = Path("/opt")
    try:
        for entry in sorted(opt.iterdir()):
            if entry.is_dir() and entry.name.startswith("gmsh"):
                out.append(entry / "bin" / "gmsh")
    except OSError:
        pass
    return out


def _sig(path: Path) -> tuple:
    """(크기, mtime_ns) — 파일이 갈렸나를 재는 서명.

    ⚠ **mtime 만으로는 부족하다.** 리눅스의 inode 시각은 타이머 틱 해상도라, 같은 틱 안에서
    두 번 쓰면 `st_mtime_ns` 가 **똑같다**(실측으로 확인했다 — 시험이 그것에 걸렸다).
    크기를 함께 본다.
    """
    try:
        st = path.stat()
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return ()


def probe(binary: Path) -> dict:
    """{available, version, path, rejected[]}.

    ⚠ **찾았을 때만 캐시한다.** 못 찾은 답을 캐시하면, 운영자가 gmsh 를 깔아도 프로세스를
    재기동하기 전까지 계속 "없다" 고 말한다 — 이 기능이 막으려던 종류의 거짓말이다.
    못 찾는 경우는 후보가 몇 개 안 되므로 매번 재도 싸다.

    찾았을 때의 열쇠는 (바이너리 서명, **고른 gmsh 의 서명**) 이다. 배포가 바이너리를 갈면
    옆 gmsh 번들도 함께 갈리지만(`koorm-bin.tar.gz` 가 `bin/` 통째다), gmsh 만 갈리는 경우도
    있으므로 둘 다 본다.
    """
    global _cache, _cache_key
    env = os.environ.get("KOOREMAPPER_GMSH") or ""
    # ⚠ `available` 인 답만 캐시에서 꺼낸다. 이 조건을 빼면 "없다" 는 답이 살아남아, 운영자가
    # gmsh 를 깔아도 재기동 전까지 계속 없다고 말한다. 아래 쓰기 쪽에서도 막지만 **읽는 쪽에서
    # 명시적으로** 막는다 — 예전 판은 `Path("")` 가 현재 폴더로 풀려 서명이 안 맞는다는
    # **우연**에 기대고 있었다.
    if _cache is not None and _cache_key is not None and _cache.get("available"):
        b_sig, g_path, g_sig, c_env = _cache_key
        if c_env == env and b_sig == _sig(binary) and g_sig == _sig(Path(g_path)):
            return _cache

    rejected: list[str] = []
    found, version = None, None
    for c in _candidates(binary):
        if not c.is_file():
            continue
        v = _responds(c)
        if v:
            found, version = str(c), v
            break
        rejected.append("%s (--version 이 실패했다 — gmsh 가 아니거나 망가졌다)" % c)
    info = {
        "available": found is not None,
        "version": version,
        "path": found,
        "rejected": rejected[:5],
    }
    if found is not None:
        _cache = info
        _cache_key = (_sig(binary), found, _sig(Path(found)), env)
    else:
        _cache, _cache_key = None, None
    return info


def reset_cache() -> None:
    """시험용 — 캐시가 시험 사이에 새면 다음 케이스가 앞 케이스의 답을 본다."""
    global _cache, _cache_key
    _cache, _cache_key = None, None
