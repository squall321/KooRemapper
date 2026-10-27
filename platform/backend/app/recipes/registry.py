# 등록된 레시피를 파일로 내보내고(platform/recipes/<이름>/) 기동 때 다시 읽어 들이는 자리.
"""Export registered recipe versions to ``platform/recipes/<name>/`` and load them
back at startup, so a recipe that moved to git runs on other boxes (prod) too.

Export writes ``recipe.py`` (the code) and ``recipe.json`` (meta + code sha256 +
gate result). Load upserts any version not already in the DB, matching by
``(name, code_sha256)``; a sha mismatch is skipped with a warning (the file was
edited by hand — we do not silently trust it).

★ We never commit/push here. A separate tool (tools/recipes_publish.sh) does that,
so an LLM registration can't push to GitHub without a human (context-notes §3).
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger("koorm.recipes")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def export_version(name: str, version: int, code: str, meta: dict, gate: dict | None) -> Path:
    """등록 판을 파일로 내보낸다. 돌려주는 것은 recipe.json 경로."""
    d = settings.recipe_export_path / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "recipe.py").write_text(code, encoding="utf-8")
    doc = {
        "name": name,
        "version": version,
        "code_sha256": sha256_text(code),
        "meta": meta,
        "gate": gate or {},
    }
    p = d / "recipe.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def iter_exported() -> list[dict]:
    """platform/recipes/*/recipe.json 을 읽어 목록으로. 코드 sha 가 안 맞으면 건너뛰고 경고."""
    root = settings.recipe_export_path
    out: list[dict] = []
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir()):
        man = d / "recipe.json"
        code_f = d / "recipe.py"
        if not (man.is_file() and code_f.is_file()):
            continue
        try:
            doc = json.loads(man.read_text(encoding="utf-8"))
            code = code_f.read_text(encoding="utf-8")
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("recipe export %s 읽기 실패: %s", d.name, exc)
            continue
        if sha256_text(code) != doc.get("code_sha256"):
            logger.warning("recipe export %s 의 code sha 불일치 — 손으로 고친 것 같다, 건너뛴다", d.name)
            continue
        doc["code"] = code
        out.append(doc)
    return out
