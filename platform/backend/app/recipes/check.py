# 레시피 코드 정적 검사 — 돌리기 전에 AST 로 import·금지 이름·던더 속성·run/test 규칙을 본다.
"""AST gate for recipe code. Runs in the API process *before* any sandbox spawn,
so obviously-bad code never reaches execution. This is the first of several
layers — the sandbox (restricted builtins, audit hook, Landlock, seccomp,
rlimits) is the backstop, not this.

The rules are deliberately strict and simple:
  * imports: only the allow-listed top-level packages
  * no dynamic-eval / introspection builtins (eval, exec, getattr, globals, …)
  * no attribute access to dunder/underscore names (``x.__class__``, ``f.__globals__``)
  * no ``import *``
  * must define ``run(...)`` at top level
  * must define at least one ``test_*`` that calls ``run`` and has an ``assert``
"""
from __future__ import annotations

import ast

# import 를 허용하는 top-level 패키지. 하위 모듈은 top-level 이 여기 있으면 허용(numpy.linalg 등).
ALLOWED_IMPORTS = frozenset({
    "math", "cmath", "statistics", "json", "collections", "itertools", "functools",
    "re", "bisect", "heapq", "random", "datetime", "typing", "dataclasses", "enum",
    "numbers", "fractions", "decimal", "string", "operator", "copy",
    "numpy", "scipy", "recipe_kit",
})

# 이 이름들은 호출·참조 자체를 막는다 — 동적 실행·내성(introspection)·파일·환경 통로다.
FORBIDDEN_NAMES = frozenset({
    "eval", "exec", "compile", "open", "input", "__import__", "globals", "locals",
    "vars", "getattr", "setattr", "delattr", "memoryview", "breakpoint", "help",
    "exit", "quit", "object", "super", "classmethod", "staticmethod", "property",
    "copyright", "credits", "license",
})


class RecipeCheckError(Exception):
    """정적 검사 실패 — message 는 사람이 읽는 까닭이다."""


def _attr_is_private(name: str) -> bool:
    # `__x__` · `__x` · `_x` 전부 막는다. `gi_frame`·`f_back`·`tb_frame` 은 밑줄이 없으니 아래 집합으로.
    return name.startswith("_")


_PRIVATE_ATTR_EXTRA = frozenset({
    "gi_frame", "gi_code", "cr_frame", "ag_frame", "tb_frame", "tb_next",
    "f_locals", "f_globals", "f_back", "f_builtins", "func_globals",
})


class _Visitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.errors: list[str] = []

    def _bad(self, node: ast.AST, msg: str) -> None:
        self.errors.append(f"{msg} (line {getattr(node, 'lineno', '?')})")

    def visit_Import(self, node: ast.Import) -> None:
        for a in node.names:
            top = a.name.split(".")[0]
            if top not in ALLOWED_IMPORTS:
                self._bad(node, f"허용되지 않은 import: {a.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level and node.level > 0:
            self._bad(node, "상대 import 는 허용되지 않는다")
        top = (node.module or "").split(".")[0]
        if top not in ALLOWED_IMPORTS:
            self._bad(node, f"허용되지 않은 import: {node.module}")
        for a in node.names:
            if a.name == "*":
                self._bad(node, "from … import * 는 허용되지 않는다")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id in FORBIDDEN_NAMES:
            self._bad(node, f"금지된 이름: {node.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if _attr_is_private(node.attr) or node.attr in _PRIVATE_ATTR_EXTRA:
            self._bad(node, f"밑줄/던더 속성 접근은 금지: .{node.attr}")
        self.generic_visit(node)


def _calls_run(fn: ast.FunctionDef) -> bool:
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "run":
            return True
    return False


def _has_assert(fn: ast.FunctionDef) -> bool:
    return any(isinstance(n, ast.Assert) for n in ast.walk(fn))


def check_recipe(code: str) -> dict:
    """레시피 코드를 정적 검사한다. 통과면 {"ok": True, "tests": [...]}, 아니면 RecipeCheckError.

    돌려주는 tests 는 발견한 ``test_*`` 이름 목록이다(샌드박스가 이것들을 부른다).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise RecipeCheckError(f"문법 오류: {exc}") from exc

    v = _Visitor()
    v.visit(tree)

    top_funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    if "run" not in top_funcs:
        v.errors.append("최상위에 run(...) 함수가 없다")
    else:
        args = top_funcs["run"].args
        n_pos = len(args.posonlyargs) + len(args.args)
        if n_pos < 2 and not args.vararg:
            v.errors.append("run 은 reports · params 두 인자를 받아야 한다")

    tests = sorted(name for name in top_funcs if name.startswith("test_"))
    if not tests:
        v.errors.append("test_ 로 시작하는 자기 시험 함수가 하나도 없다")
    else:
        for t in tests:
            fn = top_funcs[t]
            if not _calls_run(fn):
                v.errors.append(f"{t} 가 run 을 부르지 않는다")
            if not _has_assert(fn):
                v.errors.append(f"{t} 에 assert 가 없다")

    if v.errors:
        raise RecipeCheckError("; ".join(v.errors))
    return {"ok": True, "tests": tests}
