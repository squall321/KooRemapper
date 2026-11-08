#!/usr/bin/env python3
# warpage debug: true 의 진단 셋 — 없는 폴더를 만들고, 못 쓰면 덱을 쓰기 전에 rc 1, 쓴 것만 「Exported」 로 알리는지 보는 회귀 시험
"""warpage 진단 셋(2026-11-08 · 사용자 결정 「고친다」).

왜 이 시험이 있나.

  `debug: true` 는 `<debug_prefix>_raw.dat` · `_curvature.dat` · `_warpage.vtk` 를 쓴다. 기본 접두사는 `debug/warp` 인데 쓰기가
  폴더를 만들지 않고 스트림 실패도 보지 않아, debug/ 가 없으면(없는 것이 보통이다) **아무것도 쓰지 않고 rc 0 에
  「[DEBUG] Exported: debug/warp_{raw,curvature,warpage.vtk}」** 를 찍었다. 이제 접두사의 폴더가 없으면 만들고, 폴더를 못 만들거나
  파일 하나라도 못 쓰면 덱을 쓰기 전에 rc 1 이다. 「Exported」 는 셋을 다 쓴 뒤에만 찍는다.

무엇을 보나(도움말의 warpage 사례를 cfg/ 아래에 두고 그 위 폴더에서 돈다 — 접두사는 YAML 폴더 기준).
  D-1 단독 warpage · 기본 접두사(debug/ 없음) → rc 0 · cfg/debug/warp_* 셋 · 「Exported」
  D-2 assemble 로 같은 설정 → 같다
  D-3 접두사의 폴더 자리에 파일이 있다(blocker/w) → rc 1 · 그 폴더를 말한다 · 「Exported」 없음 · 덱을 쓰지 않는다
  D-4 진단 파일 자리(dbgdir/w_raw.dat)가 폴더다 → rc 1 · 그 파일을 말한다 · 「Exported」 없음 · 덱을 쓰지 않는다
  D-5 대조 — 있는 폴더의 접두사(dbg) → rc 0 · 셋 · 「Exported」(예전과 같다)

usage: test_warpage_debug_export.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "help"))
from ops_help import OPS  # noqa: E402

SPEC = {o["name"]: o for o in OPS}
FAILS, OKS = [], []
SUFFIXES = ("_raw.dat", "_curvature.dat", "_warpage.vtk")


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-96s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, args):
    p = subprocess.run([binary] + list(args), cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def setup(root, name, debug_lines, binary):
    d = os.path.join(root, name)
    cfg = os.path.join(d, "cfg")
    os.makedirs(cfg)
    files = dict(SPEC["warpage"]["files"])
    files["warpage.yaml"] = files["warpage.yaml"].replace("    mode: deform\n", "    mode: deform\n" + debug_lines)
    for n, c in files.items():
        with open(os.path.join(cfg, n), "w", encoding="utf-8") as f:
            f.write(c)
    run(binary, cfg, ["generate", "box", "box.yaml"])
    return d, cfg


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="wdbg_")
    try:
        for name, op in (("D-1 단독 warpage", "warpage"), ("D-2 assemble", "assemble")):
            d, cfg = setup(root, name[:3], "    debug: true\n", binary)
            rc, out = run(binary, d, [op, "cfg/warpage.yaml"])
            made = [s for s in SUFFIXES if os.path.isfile(os.path.join(cfg, "debug", "warp" + s))]
            check("★%s · 기본 debug/warp(debug/ 없음) → rc 0 · cfg/debug/warp_* 셋을 쓰고 「Exported」(예전엔 아무것도 안 쓰고 Exported)"
                  % name, rc == 0 and len(made) == 3 and "Exported" in out, (rc, made, out[-300:]))
        for name, prep, prefix, says in (
                ("D-3 접두사의 폴더 자리에 파일", lambda c: open(os.path.join(c, "blocker"), "w").write("x"),
                 "blocker/w", "blocker"),
                ("D-4 진단 파일 자리가 폴더", lambda c: os.makedirs(os.path.join(c, "dbgdir", "w_raw.dat")),
                 "dbgdir/w", "w_raw.dat")):
            d, cfg = setup(root, name[:3], "    debug: true\n    debug_prefix: %s\n" % prefix, binary)
            prep(cfg)
            rc, out = run(binary, d, ["warpage", "cfg/warpage.yaml"])
            check("★%s(%s) → rc 1 · 그 자리를 말한다 · 「Exported」 없음 · 덱을 쓰지 않는다(예전엔 rc 0 에 Exported)" % (name, prefix),
                  rc == 1 and says in out and "Exported" not in out and not os.path.exists(os.path.join(cfg, "box_warp.k")),
                  (rc, out[-300:]))
        d, cfg = setup(root, "D-5", "    debug: true\n    debug_prefix: dbg\n", binary)
        rc, out = run(binary, d, ["warpage", "cfg/warpage.yaml"])
        made = [s for s in SUFFIXES if os.path.isfile(os.path.join(cfg, "dbg" + s))]
        check("D-5 대조 — 있는 폴더의 접두사 dbg → rc 0 · 셋 · 「Exported」", rc == 0 and len(made) == 3 and "Exported" in out,
              (rc, made, out[-300:]))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print()
    if FAILS:
        print("FAIL %d  (OK %d)" % (len(FAILS), len(OKS)))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
