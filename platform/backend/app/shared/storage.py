"""Filesystem layout for session files.

  storage_dir / {user_id} / {session_id} / <files>

Paths stored in the DB are relative to storage_dir so the data dir can be
relocated / bind-mounted without rewriting rows.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.config import settings

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def safe_filename(name: str) -> str:
    """Strip path components and unsafe chars from an uploaded filename."""
    base = Path(name).name  # drop any directory parts
    cleaned = _SAFE.sub("_", base).lstrip(".") or "file"
    return cleaned[:255]


# 하위 경로 깊이·전체 길이 상한. filename 컬럼이 String(512) 이고 rel_path 는 String(1024) 인데
# rel_path 는 "<user>/<session>/<name>" 이라 여유가 더 적다 — 400 으로 잡아 둔다.
_MAX_DEPTH = 8
_MAX_RELPATH = 400


def safe_relpath(name: str) -> str:
    """업로드 이름을 **하위 경로를 살린** 안전한 상대 경로로 바꾼다.

    ⚠ 왜 평탄화(`safe_filename`)로는 안 되는가 — KooRemapper 는 `*INCLUDE` 를 **읽지는 않지만
    출력 덱에 그 줄을 그대로 보존한다**(실측: indent 산출물 4-5행에 입력의 `*INCLUDE sub/extra.k`
    가 남는다). 업로드가 `sub/part.k` 를 `part.k` 로 눕혀 버리면, 산출물은 `sub/part.k` 를
    가리키는데 세션에는 그 경로가 없다. 내려받아 LS-DYNA 에 넣으면 — LS-DYNA 는 인클루드를
    따라가므로 — 실패하거나 조용히 파트가 빠진다.

    안전 규칙(트래버설):
      · 구분자는 `/`·`\\` 둘 다 받는다(윈도 클라이언트가 `sub\\part.k` 로 보낸다).
      · `..` 과 `.` 구성요소는 **버린다**(올려 주지 않는다 — 남기면 탈출 경로가 된다).
      · 절대경로·드라이브 문자(`C:`)는 접두를 떼어 상대로 만든다.
      · 구성요소마다 `safe_filename` 과 같은 문자 규칙을 적용하고, 비면 버린다.
      · 깊이·길이 상한을 넘으면 뒤쪽(파일명)을 살리고 앞쪽을 버린다.
    결과는 항상 `..` 없는 순수 상대 경로다. 쓰는 쪽은 그래도 목적지를 한 번 더 확인한다.
    """
    raw = (name or "").replace("\\", "/")
    parts: list[str] = []
    for comp in raw.split("/"):
        comp = comp.strip()
        if not comp or comp == "." or comp == "..":
            continue
        if ":" in comp and not parts:      # 드라이브 문자(C:) 또는 UNC 잔재
            comp = comp.split(":", 1)[-1]
        cleaned = _SAFE.sub("_", comp).lstrip(".")
        if cleaned:
            parts.append(_clip(cleaned, 255))
    if not parts:
        return "file"
    # 깊이 상한 — 파일명 쪽을 살린다
    if len(parts) > _MAX_DEPTH:
        parts = parts[-_MAX_DEPTH:]
    # 길이 상한 — 앞쪽 디렉터리부터 버리고, 그래도 넘으면 파일명 자체를 줄인다
    while len("/".join(parts)) > _MAX_RELPATH and len(parts) > 1:
        parts.pop(0)
    if len("/".join(parts)) > _MAX_RELPATH:
        parts = [_clip(parts[-1], _MAX_RELPATH)]
    return "/".join(parts)


def _clip(comp: str, limit: int) -> str:
    """길이를 줄이되 **확장자는 살린다** — 꼬리를 그냥 자르면 `.k` 가 날아가 파일 형식 판정이 달라진다."""
    if len(comp) <= limit:
        return comp
    stem, dot, suffix = comp.rpartition(".")
    if dot and 0 < len(suffix) <= 16:
        keep = limit - len(suffix) - 1
        if keep > 0:
            return f"{stem[:keep]}.{suffix}"
    return comp[:limit]


def resolve_within(base: Path, rel: str) -> Path:
    """`base/rel` 을 풀되 base 밖으로 나가면 거부한다 — 쓰기 직전의 두 번째 방어."""
    base_r = base.resolve()
    dest = (base_r / rel).resolve()
    if dest != base_r and base_r not in dest.parents:
        raise ValueError(f"path escapes session dir: {rel}")
    return dest


def session_rel_dir(user_id: int, session_id: str) -> str:
    return f"{user_id}/{session_id}"


def session_abs_dir(user_id: int, session_id: str) -> Path:
    return settings.storage_dir / session_rel_dir(user_id, session_id)


def ensure_session_dir(user_id: int, session_id: str) -> Path:
    d = session_abs_dir(user_id, session_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def abs_path(rel_path: str) -> Path:
    """Resolve a stored relative path, refusing anything that escapes storage_dir."""
    root = settings.storage_dir.resolve()
    resolved = (root / rel_path).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"path escapes storage dir: {rel_path}")
    return resolved


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
