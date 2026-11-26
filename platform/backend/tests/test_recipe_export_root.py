# 포털 요청 R-09 (나) — 등록 레시피는 데이터 뿌리에 내보내고, 기동 때 리포 씨앗과 함께 읽어 들이는지 본다
"""사용자 결정 2026-11-25 「데이터 뿌리 아래로」 — 계획 docs/01-plan/features/hwax-request-1125.plan.md · 맥락 4절.

예전에는 리포의 추적 폴더 platform/recipes 에 내보내서, 추적 밖 새 폴더를 포털 update 의 `git stash -u` 가 쓸어 갔다(DB 에는
남았다). 이제 비워 두면 `<HWAX_DATA_ROOT|/data>/svc/kooremapper/recipes`(그 자리가 없거나 못 쓰면 storage 아래 `.recipes` — 11-26 운영
노드에서 예전 마지막 자리 platform/infra/data/recipes 가 읽기 전용 묶음이라 실패했다)다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete

from app.config import Settings, settings
from app.models import Recipe, RecipeVersion
from app.modules.recipes import services as rsvc
from app.recipes import registry

PLATFORM = Path(__file__).resolve().parents[2]
CODE = "def run(reports, params):\n    return {'n': len(reports)}\n\n\ndef test_run():\n    assert run([], {}) == {'n': 0}\n"


def _path(monkeypatch, export_dir="", data_root=None):
    if data_root is None:
        monkeypatch.delenv("HWAX_DATA_ROOT", raising=False)
    else:
        monkeypatch.setenv("HWAX_DATA_ROOT", str(data_root))
    return Settings(recipe_export_dir=export_dir).recipe_export_path


def test_by_default_it_exports_under_the_data_root(monkeypatch, tmp_path):
    (tmp_path / "svc" / "kooremapper").mkdir(parents=True)
    assert _path(monkeypatch, data_root=tmp_path) == tmp_path / "svc" / "kooremapper" / "recipes"
    monkeypatch.delenv("KOORM_RECIPE_EXPORT_DIR", raising=False)
    assert Settings(_env_file=None).recipe_export_path == tmp_path / "svc" / "kooremapper" / "recipes", \
        "기본값(아무것도 적지 않음)이 데이터 뿌리가 아니다"


def _storage_fallback():
    return Path(Settings(_env_file=None).storage_dir) / ".recipes"


def test_without_a_data_root_it_falls_back_under_storage(monkeypatch, tmp_path):
    """11-26 운영 노드 — 컨테이너에 데이터 뿌리가 없고 리포 묶음이 읽기 전용이었다. 쓸 수 있는 묶음은 storage 하나다."""
    got = _path(monkeypatch, data_root=tmp_path)          # svc/kooremapper 가 없다
    assert got == _storage_fallback()
    assert PLATFORM / "recipes" != got and not str(got).startswith(str(PLATFORM / "infra")), \
        "리포 묶음 안에 내보냈다 — 추적 폴더면 update 의 stash 가, 읽기 전용 묶음이면 쓰기가 막는다"


@pytest.mark.skipif(os.geteuid() == 0, reason="root 는 권한을 무시한다")
def test_a_data_root_it_cannot_write_also_falls_back_under_storage(monkeypatch, tmp_path):
    svc = tmp_path / "svc" / "kooremapper"
    svc.mkdir(parents=True)
    svc.chmod(0o555)
    try:
        assert _path(monkeypatch, data_root=tmp_path) == _storage_fallback(), "못 쓰는 데이터 뿌리를 골랐다"
        svc.chmod(0o755)
        (svc / "recipes").mkdir()
        svc.chmod(0o555)
        assert _path(monkeypatch, data_root=tmp_path) == svc / "recipes", "이미 있는 쓸 수 있는 recipes 폴더는 부모를 못 써도 쓴다"
    finally:
        svc.chmod(0o755)


def test_a_relative_data_root_follows_the_start_script_rule(monkeypatch):
    d = Path("/data/svc/kooremapper")
    here = d / "recipes" if (d / "recipes").exists() else d
    want = d / "recipes" if here.is_dir() and os.access(here, os.W_OK) else _storage_fallback()
    assert _path(monkeypatch, data_root="rel/path") == want, "상대값이면 /data(start.sh 와 같다)"


def test_an_explicit_dir_still_wins(monkeypatch, tmp_path):
    assert _path(monkeypatch, export_dir=str(tmp_path / "x"), data_root=tmp_path) == tmp_path / "x"
    assert _path(monkeypatch, export_dir="somewhere", data_root=tmp_path) == PLATFORM / "somewhere"


def test_the_seed_folder_is_the_tracked_one():
    assert settings.recipe_seed_path == PLATFORM / "recipes"


@pytest.mark.asyncio(loop_scope="session")
async def test_startup_loads_both_the_seeds_and_the_data_root(db, monkeypatch, tmp_path):
    seeds, exports = tmp_path / "seeds", tmp_path / "exports"
    a, b = f"t_seed_{ulid.new().str.lower()[:10]}", f"t_exp_{ulid.new().str.lower()[:10]}"
    old = settings.recipe_export_dir
    try:
        settings.recipe_export_dir = str(seeds)
        registry.export_version(a, 1, CODE, {"title": "씨앗"}, None)
        settings.recipe_export_dir = str(exports)
        registry.export_version(b, 1, CODE, {"title": "내보낸 것"}, None)
        monkeypatch.setattr(type(settings), "recipe_seed_path", property(lambda self: seeds))
        assert await rsvc.load_exported(db) == 2
        for name in (a, b):
            r = await rsvc.get_recipe(db, name)
            assert r is not None and r.current_version == 1, name
        assert await rsvc.load_exported(db) == 0, "두 번째 기동은 아무것도 더하지 않는다"
        settings.recipe_export_dir = str(seeds)                      # 씨앗 자리와 내보내는 자리가 같아도 한 번만 읽는다
        assert rsvc._load_roots() == [seeds]
    finally:
        settings.recipe_export_dir = old
        for name in (a, b):
            r = await rsvc.get_recipe(db, name)
            if r is not None:
                await db.execute(delete(RecipeVersion).where(RecipeVersion.recipe_id == r.id))
                await db.execute(delete(Recipe).where(Recipe.id == r.id))
        await db.commit()
