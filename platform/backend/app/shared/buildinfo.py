# 지금 도는 것이 어느 커밋·어느 바이너리인지 — 배포가 내려놓은 BUILD_INFO.txt 를 읽는다
"""왜 이 모듈이 있나 (2026-09-25, 덱 계약 2차 P0-4).

운영에서 "지금 도는 바이너리가 어느 커밋인가" 를 물을 곳이 없었다. 바이너리는 넷이 다
`version 1.8.0` 만 찍고, `/api/health` 는 `binary_present` 만 냈다. 게시본이 21커밋 뒤에
멈춰 있었는데도 **밖에서 볼 방법이 없었다.**

⚠ 런타임에 `git` 을 부르지 않는다. 이유를 바로잡아 둔다 — 컨테이너에 `.git` 이 **없는 것이
아니라**(작업 트리 바인드로 읽힌다) `git` **실행 파일**이 없다. 그러니 `.git` 을 손으로 파싱할
수도 있지만, 그러면 detached HEAD·packed-refs 두 갈래를 여기서 다뤄야 하고 폐쇄망 운영
서버에는 애초에 리포가 없다. 그래서 출처는 **배포가 내려놓은 파일** 하나로 고정한다
(`dist-to-drive.sh` 가 만들고 `dist-from-drive.sh` 가 `bin/BUILD_INFO.txt` 로 내려놓는다).
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

_cache: dict | None = None
_cache_key: tuple | None = None

_FIELD = re.compile(r"^(\w+)\s*:\s*(.*)$")
# BUILD_INFO 에서 이만큼만 꺼낸다. 파일 전체를 health 에 실으면 커밋 제목·remote URL 까지
# 인증 없이 나간다 — `/api/health` 는 공개 엔드포인트다.
_WANTED = ("commit", "branch", "describe", "published_utc", "sha256", "build_method")


def _sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _parse(path: Path) -> dict:
    """BUILD_INFO.txt 를 얕게 읽는다. `[binary]` 절의 sha256 과 `[source]` 절의 commit 만 쓴다."""
    out: dict = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        m = _FIELD.match(line.strip())
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if key in _WANTED and key not in out and val and not val.startswith("알 수 없음"):
            out[key] = val
    return out


def build_info(binary: Path) -> dict:
    """리비전·바이너리 해시·mtime. 바이너리가 바뀌면(크기·mtime) 다시 계산한다.

    ⚠ 프로세스 수명 동안 캐시한다 — sha256 은 5.6MB 를 읽으므로 health 마다 하면 안 된다.
    무효화 열쇠는 (경로, 크기, mtime_ns) 다. 배포가 파일을 갈면 다음 호출에서 갱신된다.
    """
    global _cache, _cache_key
    # ⚠ 열쇠에 **BUILD_INFO 까지** 넣는다. 바이너리만 보면, 배포가 BUILD_INFO 만 갈았을 때
    # (반입 스크립트를 두 번 돌리거나 운영자가 파일만 내려놓는 경우) 재기동 전까지 낡은
    # 리비전을 낸다 — 이 기능이 막으려던 바로 그 종류의 거짓말이다.
    info_path = binary.parent / "BUILD_INFO.txt"
    try:
        ist = info_path.stat()
        ikey: tuple = (ist.st_size, ist.st_mtime_ns)
    except OSError:
        ikey = ()
    try:
        st = binary.stat()
        key = (str(binary), st.st_size, st.st_mtime_ns, ikey)
    except OSError:
        # 바이너리가 없으면 캐시하지 않는다 — 나중에 생기면 바로 보여야 한다.
        return {"binary_present": False, "revision": None, "binary_sha256": None,
                "binary_mtime_utc": None}
    if _cache is not None and _cache_key == key:
        return _cache

    meta = _parse(info_path)
    recorded = meta.get("sha256")
    actual = _sha256(binary)
    info = {
        "binary_present": True,
        "revision": meta.get("commit"),
        "revision_branch": meta.get("branch"),
        "revision_describe": meta.get("describe"),
        "published_utc": meta.get("published_utc"),
        "build_method": meta.get("build_method"),
        "binary_sha256": actual,
        "binary_mtime_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc)
        .isoformat(timespec="seconds").replace("+00:00", "Z"),
        # ⚠ 기록과 실물이 어긋나면 **리비전을 믿을 수 없다.** 누가 BUILD_INFO 를 안 갈고
        # 바이너리만 바꿨거나(호스트 빌드로 덮어쓴 09-24 사고가 그 모양이다) 그 반대다.
        # 그 경우 revision 을 그대로 내보내면 거짓말이 되므로 어긋났다는 사실을 함께 낸다.
        "revision_matches_binary": (recorded == actual) if (recorded and actual) else None,
    }
    _cache, _cache_key = info, key
    return info
