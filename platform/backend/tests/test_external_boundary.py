# 받아 둔 바깥 리포(external/ — StandardPlatform submodule)를 런타임이 import 하지 않는다는 구조 시험
"""왜 — `external/StandardPlatform` 은 **읽는 참고본**이다
(`docs/01-plan/features/ontology-graft.plan.md` §2). 옮긴 코드는 DynaForge 파일이 되고 출처를
머리 주석에 단다. 런타임이 submodule 을 import 하면 ① 배포가 submodule 을 안 받는 순간 앱이
죽고(Drive 아티팩트 경로는 submodule 을 안 가져온다) ② 그쪽 커밋을 올리는 것만으로 우리 동작이
바뀐다. 출처 주석에 이름이 나오는 것은 괜찮다 — 보는 것은 **import 와 `sys.path`** 다.

★StepForge `tests/test_external_boundary.py` 와 같은 규율이다(그쪽은 `app`·`core`·`scripts`·
`fixtures`). 두 쌍둥이가 같은 참고본을 받으므로 경계도 같은 모양으로 지킨다.

**훑는 대상은 `git ls-files` 다** — `rglob` 은 `platform/backend/.venv`·`mcp_server/venv` 를
걸어 들어가 느리고, 거기 있는 남의 코드까지 우리 것으로 센다. 추적되는 것이 곧 우리 코드다.
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ("platform", "tools", "scripts", "materials")
BANNED = ("external", "StandardPlatform", "standardplatform")


def _py_files():
    # `--cached --others --exclude-standard` — 추적된 것 **과** 아직 add 안 한 것 둘 다.
    # ★`--cached` 만 쓰면 방금 쓴 파일을 안 보므로, 위반을 심어도 초록이다(실측으로 걸렸다).
    # `--exclude-standard` 가 `.gitignore` 를 존중하므로 `.venv`·`venv` 는 안 걸어 들어간다.
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--cached", "--others",
                          "--exclude-standard", "*.py"],
                         capture_output=True, text=True, check=True).stdout.split()
    for rel in sorted(out):
        parts = Path(rel).parts
        if parts[0] not in RUNTIME:
            continue
        if "tests" in parts:        # 시험은 나쁜 꼴을 **문자열로** 들고 있어야 한다
            continue
        yield ROOT / rel


def _bad_import(node: ast.AST) -> str | None:
    names = []
    if isinstance(node, ast.Import):
        names = [a.name for a in node.names]
    elif isinstance(node, ast.ImportFrom) and node.module:
        names = [node.module]
    for n in names:
        if n.split(".")[0] in BANNED:
            return n
    return None


def _bad_path_call(node: ast.AST) -> str | None:
    """`sys.path.insert/append(...)` 의 인자에 external 이 들어가면 — 경로로 우회한 import."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    f = node.func
    if f.attr not in ("insert", "append") or ast.unparse(f.value) != "sys.path":
        return None
    text = " ".join(ast.unparse(a) for a in node.args)
    return text if any(b in text for b in BANNED) else None


def test_runtime_never_imports_the_external_reference_repo() -> None:
    found = []
    for f in _py_files():
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            hit = _bad_import(node) or _bad_path_call(node)
            if hit:
                found.append(f"{f.relative_to(ROOT)}:{node.lineno} {hit}")
    assert not found, found


def test_the_guard_catches_both_ways_in() -> None:
    """판별력 — import 와 `sys.path` 우회 둘 다 잡는다(무력화 대신 같은 판별 함수에 나쁜 꼴을 넣는다)."""
    bad = ast.parse("import external.StandardPlatform\nfrom standardplatform.x import y\n"
                    "import sys\nsys.path.insert(0, 'external/StandardPlatform/backend')\n")
    hits = [h for n in ast.walk(bad) if (h := _bad_import(n) or _bad_path_call(n))]
    assert len(hits) == 3, hits
    ok = ast.parse("# 출처: StandardPlatform backend/app/modules/coreapi/kit/sp_core_pull.py@f7485c0\n"
                   "import json\n")
    assert not [n for n in ast.walk(ok) if _bad_import(n) or _bad_path_call(n)]


def test_the_scan_actually_covers_the_runtime() -> None:
    """빈 목록을 훑고 「깨끗하다」 고 말하는 것을 막는다 — 세는 관문이 0을 세면 언제나 초록이다."""
    files = list(_py_files())
    assert len(files) > 50, f"런타임 파이썬이 {len(files)}개뿐 — 훑는 범위가 깨졌다"
    assert any(f.parts[-3:][:1] == ("app",) or "platform" in f.parts for f in files)


def test_submodule_is_pinned_and_declared() -> None:
    """`.gitmodules` 에 경로·주소가 있고 gitlink 가 한 커밋에 고정돼 있다(브랜치를 따라가지 않는다)."""
    text = (ROOT / ".gitmodules").read_text(encoding="utf-8")
    assert "path = external/StandardPlatform" in text
    assert "url = https://github.com/4leaf321-nox321/StandardPlatform.git" in text
    assert "branch" not in text   # 브랜치 추적이면 `submodule update --remote` 한 번에 판이 바뀐다
    # ★StepForge 와 **같은 커밋**에 고정돼 있어야 한다 — 같은 참고본을 봐야 결이 맞는다.
    #   10-30 f7485c0(v0.4.52) → 778db2f(v0.4.67) — 받는 쪽 키트 2026-10-21 판(규칙 16 · 시험장)을 받으려고.
    #   StepForge 도 10-31 같은 커밋으로 올렸다(그쪽 525be5c — 확인함). 올릴 때마다 서로 알린다(리포 CLAUDE.md).
    status = subprocess.run(["git", "-C", str(ROOT), "submodule", "status"],
                            capture_output=True, text=True, check=True).stdout
    assert "778db2f0bf7b932917268e2e635f9e45b28a25ab" in status, status
