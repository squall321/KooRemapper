# 레시피 정적 검사와 샌드박스 격리 — 겹마다 탈출을 시도해 막히는지 본다(DB 불필요).
"""Static check + sandbox isolation tests. No DB — pure function + subprocess.

Kernel layers (Landlock/seccomp) may be absent on some kernels/CI; those tests
assert the block only when the layer engaged (``result.layers``), else skip.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.recipes import sandbox
from app.recipes.check import check_recipe, RecipeCheckError

GOOD = '''
def run(reports, params):
    return {"n": len(reports), "sum": sum(params.get("xs", []))}

def test_ok():
    import recipe_kit
    r = recipe_kit.make_report(kind="sphere", cases=[{"case_key": "a", "max_stress": 2.0}])
    out = run([r], {"xs": [1, 2, 3]})
    assert out["n"] == 1
    assert out["sum"] == 6
'''


# ── 정적 검사 ─────────────────────────────────────────────────────────
def test_check_good_passes():
    info = check_recipe(GOOD)
    assert info["ok"] is True
    assert info["tests"] == ["test_ok"]


@pytest.mark.parametrize("code, needle", [
    ("import os\ndef run(r,p):\n return 1\ndef test_x():\n assert run([],{})", "import"),
    ("def run(r,p):\n return open('/x').read()\ndef test_x():\n assert run([],{})", "open"),
    ("def run(r,p):\n return [].__class__\ndef test_x():\n assert run([],{})", "속성"),
    ("def run(r,p):\n return getattr(r,'x')\ndef test_x():\n assert run([],{})", "getattr"),
    ("from math import *\ndef run(r,p):\n return 1\ndef test_x():\n assert run([],{})", "*"),
    ("def go(r,p):\n return 1\ndef test_x():\n assert go([],{})", "run"),
    ("def run(r,p):\n return 1", "test_"),
    ("def run(r,p):\n return 1\ndef test_x():\n x=1", "assert"),
])
def test_check_rejects(code, needle):
    with pytest.raises(RecipeCheckError) as exc:
        check_recipe(code)
    assert needle in str(exc.value)


# ── 샌드박스 — 정상 ───────────────────────────────────────────────────
async def test_sandbox_selftest_passes():
    r = await sandbox.run_in_sandbox(code=GOOD, mode="selftest")
    assert r.ok, r.error
    assert r.tests_passed == ["test_ok"]
    assert r.layers.get("limits") is True
    assert r.layers.get("audit") is True


async def test_sandbox_run_returns_result():
    r = await sandbox.run_in_sandbox(code=GOOD, mode="run", params={"xs": [10, 20]})
    assert r.ok, r.error
    assert r.result == {"n": 0, "sum": 30}


async def test_sandbox_nan_becomes_null():
    code = (
        "def run(reports, params):\n"
        "    return {'x': float('nan'), 'y': float('inf'), 'z': 1.5}\n"
        "def test_x():\n assert run([], {}) is not None\n"
    )
    r = await sandbox.run_in_sandbox(code=code, mode="run")
    assert r.ok, r.error
    assert r.result == {"x": None, "y": None, "z": 1.5}


# ── 샌드박스 — 상한(커널 불필요) ──────────────────────────────────────
async def test_sandbox_memory_limit():
    code = (
        "def run(reports, params):\n"
        "    x = bytearray(4 * 1024 * 1024 * 1024)\n"
        "    return {'len': len(x)}\n"
        "def test_x():\n assert run([], {}) is not None\n"
    )
    r = await sandbox.run_in_sandbox(code=code, mode="run", mem_mb=1024)
    assert not r.ok
    assert ("MemoryError" in (r.error or "")) or r.returncode not in (0, None)


async def test_sandbox_cpu_or_walltime_limit():
    code = (
        "def run(reports, params):\n"
        "    i = 0\n"
        "    while True:\n"
        "        i += 1\n"
        "def test_x():\n assert run([], {}) is not None\n"
    )
    r = await sandbox.run_in_sandbox(code=code, mode="run", timeout_sec=3)
    assert not r.ok
    assert r.timed_out or (r.returncode is not None and r.returncode < 0)


# ── 샌드박스 — 커널 층(있을 때만) ─────────────────────────────────────
async def test_sandbox_landlock_blocks_outside_read(tmp_path):
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (decoy / "meta.json").write_text('{"id": "SECRET", "kind": "sphere"}', encoding="utf-8")
    code = (
        "def run(reports, params):\n"
        "    import recipe_kit\n"
        "    return recipe_kit.Report.from_bundle(params['p']).meta\n"
        "def test_x():\n assert run([], {'p': '/nope'}) is not None\n"
    )
    r = await sandbox.run_in_sandbox(code=code, mode="run", params={"p": str(decoy)})
    if not r.layers.get("landlock"):
        pytest.skip("Landlock 불가 커널")
    assert not r.ok
    assert "SECRET" not in (str(r.result) + (r.error or ""))
    assert "Permission denied" in (r.error or "") or "Errno 13" in (r.error or "")
