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


def session_rel_dir(user_id: int, session_id: str) -> str:
    return f"{user_id}/{session_id}"


def session_abs_dir(user_id: int, session_id: str) -> Path:
    return settings.storage_dir / session_rel_dir(user_id, session_id)


def ensure_session_dir(user_id: int, session_id: str) -> Path:
    d = session_abs_dir(user_id, session_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def abs_path(rel_path: str) -> Path:
    return settings.storage_dir / rel_path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
