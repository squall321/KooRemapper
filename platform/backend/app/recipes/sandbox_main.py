# 격리 부트스트랩 — 자식 프로세스 안에서 상한·Landlock·seccomp·감사 훅·제한 builtins 를 걸고 레시피를 돌린다.
"""Runs INSIDE the sandboxed child (``python3 -I sandbox_main.py <spec.json>``).

Sequence (order matters):
  1. read spec, pre-import the pure parser + kit + heavy libs (numpy/scipy) while
     imports and threads are still allowed;
  2. ``PR_SET_NO_NEW_PRIVS``;
  3. rlimits (AS, CPU, FSIZE, NOFILE, then NPROC=0 — blocks fork & new threads);
  4. Landlock (read-only: python + site-packages + the input bundle; no write anywhere);
  5. seccomp (deny socket/connect/kill/ptrace/io_uring/mount/…);
  6. audit hook (backstop: deny subprocess/socket/ctypes/… + sensitive attribute reads);
  7. restricted builtins + import guard;
  8. exec the recipe, run tests or ``run(reports, params)``, write the result envelope.

Layers 4–5 are kernel-enforced and may be unavailable on some kernels; the sandbox
records which engaged (``_layers``) and proceeds with the Python-level layers. See
docs/01-plan/features/recipes-1026.context-notes.md §6.

This file must stay import-light at module load — it adds the backend root to
sys.path only long enough to pre-import the pure parser.
"""
import ctypes
import json
import math
import os
import resource
import struct
import sys
import time
import traceback

_layers = {"landlock": False, "seccomp": False, "audit": False, "limits": False, "nnp": False}


# ── 0. spec 과 사전 import(잠그기 전) ──────────────────────────────────
def _preimport():
    # `python -I` 는 스크립트 디렉터리를 sys.path 에 넣지 않는다(격리 모드). 그래서 직접 넣는다 —
    # app/recipes(recipe_kit · check)와 backend(app.reports.parser). 사전 import 가 끝나면 둘 다
    # 걷는다. 뒤의 레시피 import 는 캐시(sys.modules)로 풀리므로 경로가 필요 없다.
    here = os.path.dirname(os.path.abspath(__file__))        # app/recipes
    backend_root = os.path.dirname(os.path.dirname(here))    # backend
    added = [here, backend_root]
    for p in added:
        sys.path.insert(0, p)
    try:
        import app.reports.parser  # noqa: F401 — kit 가 쓴다(순수 · stdlib 만)
        import recipe_kit  # noqa: F401
        import check  # noqa: F401 — 허용 목록 단일 소스
    finally:
        for p in added:
            try:
                sys.path.remove(p)
            except ValueError:
                pass
    libs = {}
    for name in ("numpy", "scipy", "scipy.stats", "scipy.signal", "scipy.interpolate",
                 "scipy.spatial", "scipy.optimize", "scipy.linalg", "scipy.ndimage",
                 "scipy.special", "scipy.cluster"):
        try:
            __import__(name)
            libs[name] = True
        except Exception:
            libs[name] = False
    return libs


# ── 2·3. no_new_privs + rlimits ───────────────────────────────────────
def _set_limits(mem_mb, fsize_mb, cpu_sec):
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) == 0:   # PR_SET_NO_NEW_PRIVS
        _layers["nnp"] = True
    resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_mb << 20, fsize_mb << 20))
    try:
        resource.setrlimit(resource.RLIMIT_AS, (mem_mb << 20, mem_mb << 20))
    except (ValueError, OSError):
        pass
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_sec, cpu_sec + 2))
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    except (ValueError, OSError):
        pass
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # 맨 마지막 — fork · 새 스레드를 막는다. 사전 import 가 끝난 뒤라야 한다.
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    except (ValueError, OSError):
        pass
    _layers["limits"] = True


# ── 4. Landlock v1 — 읽기 뿌리만, 쓰기 0 ───────────────────────────────
def _landlock(read_roots):
    libc = ctypes.CDLL(None, use_errno=True)
    sc = libc.syscall
    sc.restype = ctypes.c_long
    SYS_create, SYS_add, SYS_restrict = 444, 445, 446
    abi = sc(SYS_create, None, 0, 1)
    if abi < 1:
        return False
    handled = (1 << 13) - 1                       # v1 의 13 권한 전부를 다룬다
    read_access = (1 << 2) | (1 << 3)             # READ_FILE | READ_DIR

    class RulesetAttr(ctypes.Structure):
        _fields_ = [("handled_access_fs", ctypes.c_uint64)]

    class PathBeneath(ctypes.Structure):
        _pack_ = 1
        _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]

    attr = RulesetAttr(handled)
    rfd = sc(SYS_create, ctypes.byref(attr), ctypes.sizeof(attr), 0)
    if rfd < 0:
        return False
    for root in read_roots:
        if not os.path.isdir(root):
            continue
        try:
            fd = os.open(root, os.O_PATH | os.O_CLOEXEC)
        except OSError:
            continue
        pb = PathBeneath(read_access, fd)
        sc(SYS_add, rfd, 1, ctypes.byref(pb), 0)   # LANDLOCK_RULE_PATH_BENEATH
        os.close(fd)
    ok = sc(SYS_restrict, rfd, 0) == 0
    os.close(rfd)
    return ok


# ── 5. seccomp — 거부 목록(x86_64) ─────────────────────────────────────
def _seccomp():
    if struct.calcsize("P") != 8:
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    AUDIT_ARCH_X86_64 = 0xC000003E
    # socket connect accept bind listen socketpair accept4 · kill tkill tgkill pidfd_send_signal ·
    # ptrace process_vm_readv/writev · io_uring · unshare setns mount umount2 pivot_root ·
    # bpf perf_event_open userfaultfd keyctl · gethostname sethostname · reboot
    deny = [41, 42, 43, 49, 50, 53, 288, 62, 200, 234, 424, 101, 310, 311,
            425, 426, 427, 272, 308, 165, 166, 155, 321, 298, 323, 250, 169]

    def ins(code, jt, jf, k):
        return struct.pack("=HBBI", code, jt, jf, k)

    LD_W_ABS, JEQ, JGE, RET = 0x20, 0x15, 0x35, 0x06
    ALLOW, EPERM, KILL = 0x7FFF0000, 0x00050000 | 1, 0x80000000
    prog = [ins(LD_W_ABS, 0, 0, 4), ins(JEQ, 1, 0, AUDIT_ARCH_X86_64), ins(RET, 0, 0, KILL),
            ins(LD_W_ABS, 0, 0, 0), ins(JGE, 0, 1, 0x40000000), ins(RET, 0, 0, EPERM)]
    for nr in deny:
        prog.append(ins(JEQ, 0, 1, nr))
        prog.append(ins(RET, 0, 0, EPERM))
    prog.append(ins(RET, 0, 0, ALLOW))
    buf = ctypes.create_string_buffer(b"".join(prog))

    class SockFprog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]

    fp = SockFprog(len(prog), ctypes.addressof(buf))
    return libc.prctl(22, 2, ctypes.byref(fp), 0, 0) == 0   # PR_SET_SECCOMP, FILTER


# ── 6. 감사 훅(파이썬 층 백스톱) ───────────────────────────────────────
_AUDIT_DENY_PREFIX = (
    "subprocess.", "socket.", "ctypes.dlopen", "ctypes.dlsym", "ctypes.cdata",
    "os.exec", "os.fork", "os.posix_spawn", "os.spawn", "os.system",
    "os.putenv", "os.unsetenv", "os.remove", "os.unlink", "os.rename", "os.rmdir",
    "os.mkdir", "os.chmod", "os.chown", "os.chdir", "os.setuid", "os.setgid",
    "shutil.", "glob.glob", "pickle.find_class", "marshal.load", "webbrowser.",
    "urllib.request", "http.client", "ftplib.", "pty.spawn", "winreg.",
)
_SENSITIVE_ATTR = frozenset({
    "__globals__", "__code__", "__closure__", "__builtins__", "__subclasses__",
    "__bases__", "__mro__", "__class__", "__dict__", "__self__", "__func__",
    "gi_frame", "cr_frame", "f_back", "f_globals", "f_locals", "tb_frame",
})


def _install_audit():
    def hook(event, args):
        for p in _AUDIT_DENY_PREFIX:
            if event.startswith(p):
                raise PermissionError(f"샌드박스: 금지된 동작 {event}")
        if event == "open" and len(args) >= 2:
            mode = args[1] or ""
            if any(c in str(mode) for c in ("w", "a", "x", "+")):
                raise PermissionError("샌드박스: 파일 쓰기 금지")
        if event == "object.__getattr__" and len(args) >= 2 and args[1] in _SENSITIVE_ATTR:
            raise PermissionError(f"샌드박스: 민감 속성 접근 금지 .{args[1]}")
    sys.addaudithook(hook)
    _layers["audit"] = True


# ── 7. 제한 builtins + import 관문 ─────────────────────────────────────
def _restricted_builtins(allowed_imports):
    import builtins as _b
    real_import = _b.__import__
    safe_names = (
        "abs min max sum len range enumerate zip map filter sorted reversed list dict "
        "set tuple frozenset str int float bool bytes bytearray round divmod pow print "
        "repr ascii isinstance issubclass all any next iter slice complex format chr ord "
        "hex oct bin hash type callable id sorted True False None NotImplemented Ellipsis "
        "Exception ValueError TypeError KeyError IndexError ZeroDivisionError "
        "ArithmeticError RuntimeError StopIteration AttributeError NotImplementedError "
        "OverflowError FloatingPointError AssertionError LookupError Warning "
        "abs zip".split()
    )
    bd = {}
    for n in set(safe_names):
        if hasattr(_b, n):
            bd[n] = getattr(_b, n)

    def guard_import(name, g=None, loc=None, fromlist=(), level=0):
        if level != 0:
            raise ImportError("샌드박스: 상대 import 금지")
        top = name.split(".")[0]
        if top not in allowed_imports:
            raise ImportError(f"샌드박스: 허용되지 않은 import {name}")
        return real_import(name, g, loc, fromlist, level)

    bd["__import__"] = guard_import
    return bd


# ── 결과 직렬화 — NaN/Inf → null, numpy → python, 상한 ─────────────────
def _sanitize(obj, depth=0):
    if depth > 40:
        return "<깊이 상한>"
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    np = sys.modules.get("numpy")
    if np is not None:
        if isinstance(obj, np.generic):
            return _sanitize(obj.item(), depth)
        if isinstance(obj, np.ndarray):
            return _sanitize(obj.tolist(), depth)
    if isinstance(obj, dict):
        return {str(k): _sanitize(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_sanitize(v, depth + 1) for v in obj]
    return str(obj)


def _emit(fd, payload, fsize_cap):
    try:
        text = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        payload = {"ok": False, "error": "결과를 직렬화할 수 없다"}
        text = json.dumps(payload, ensure_ascii=False)
    data = text.encode("utf-8")
    if len(data) > int(fsize_cap * 0.9):
        trimmed = {"ok": payload.get("ok", False), "result_truncated": True,
                   "note": "결과가 파일 상한에 가까워 잘렸다 — 레시피가 더 작게 요약해야 한다"}
        data = json.dumps(trimmed, ensure_ascii=False).encode("utf-8")
    os.write(fd, data)
    os.close(fd)


def main():
    spec = json.loads(open(sys.argv[1], encoding="utf-8").read())
    result_fd = int(os.environ.get("RECIPE_RESULT_FD", spec.get("result_fd", 1)))
    fsize_cap = (spec["limits"]["fsize_mb"]) << 20
    t0 = time.time()
    try:
        libs = _preimport()
        import recipe_kit
        from check import check_recipe, ALLOWED_IMPORTS, RecipeCheckError

        # 코드가 여기까지 왔다는 것은 라우트에서 정적 검사를 이미 통과했다는 뜻이지만,
        # 샌드박스 안에서도 한 번 더 본다(파일로 들어온 git 레시피는 라우트를 안 거친다).
        try:
            info = check_recipe(spec["code"])
        except RecipeCheckError as exc:
            _emit(result_fd, {"ok": False, "error": f"정적 검사 실패: {exc}", "layers": _layers}, fsize_cap)
            return

        read_roots = [p for p in sys.path if p and os.path.isdir(p)]
        read_roots += [sys.prefix, sys.base_prefix, os.path.dirname(os.__file__), spec["bundle_dir"]]

        _set_limits(spec["limits"]["mem_mb"], spec["limits"]["fsize_mb"], spec["limits"]["cpu_sec"])
        _layers["landlock"] = _landlock(sorted(set(read_roots)))
        _layers["seccomp"] = _seccomp()
        _install_audit()
        bd = _restricted_builtins(ALLOWED_IMPORTS)

        ns = {"__builtins__": bd, "__name__": "recipe"}
        exec(compile(spec["code"], "<recipe>", "exec"), ns)  # noqa: S102 — 의도된 실행(관문 통과 후)

        mode = spec.get("mode", "selftest")
        if mode == "selftest":
            passed = []
            for t in info["tests"]:
                ns[t]()
                passed.append(t)
            payload = {"ok": True, "mode": "selftest", "tests_passed": passed, "layers": _layers}
        else:
            reports = [recipe_kit.Report.from_bundle(d) for d in spec["report_dirs"]]
            raw = ns["run"](reports, spec.get("params") or {})
            payload = {"ok": True, "mode": "run", "result": _sanitize(recipe_kit.as_result(raw)),
                       "layers": _layers}
        payload["elapsed_ms"] = int((time.time() - t0) * 1000)
        _emit(result_fd, payload, fsize_cap)
    except BaseException as exc:  # noqa: BLE001 — 무엇이든 결과 봉투로 돌려준다
        tb = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        _emit(result_fd, {"ok": False, "error": tb[:4000], "layers": _layers,
                          "elapsed_ms": int((time.time() - t0) * 1000)}, fsize_cap)


if __name__ == "__main__":
    main()
