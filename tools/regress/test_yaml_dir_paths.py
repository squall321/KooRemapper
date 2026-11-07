#!/usr/bin/env python3
# 작업 폴더 기준이던 YAML op 여덟과 assemble 의 battery 산출 · warpage debug_prefix 가 YAML 폴더 기준으로 풀리는지 보는 회귀 시험
"""YAML 폴더 기준 경로 — 남았던 여덟 op (2026-11-07 셋째 묶음).

왜 이 시험이 있나.

  매뉴얼 §3.1(a) 는 「YAML 안의 상대 경로는 그 YAML 파일이 있는 폴더 기준 — 남은 예외는 map 하나」라고 적지만
  foldsurface · refshell · stackwrap · linkage-fit · applyfold · section · surfview · stackdiagram 은 YAML 값을 그대로 열어
  작업 폴더 기준이었다. `KooRemapper section cfg/sec.yaml` 이 cfg/ 옆의 모델을 못 찾거나 산출을 작업 폴더에 썼다.
  (플랫폼은 설정을 세션 폴더 = 작업 폴더에 두므로 바뀌는 것이 없다.)

무엇을 보나(op 마다 — 도움말 사례를 cfg/ 아래에 두고 그 위 폴더에서 `<op> cfg/<설정>` 을 돈다).
  rc 0 · 도움말이 말한 산출이 cfg/ 아래에 나오고 작업 폴더에는 없다.
  대조 — 설정이 작업 폴더에 있으면 예전과 같다(도움말 사례 그대로 · 회귀 run_help_examples).

남았던 둘(2026-11-07 넷째 묶음) — assemble 안 battery 의 산출 접두사와 warpage 의 debug_prefix(단독 warpage 도 같은 함수)도
  작업 폴더 기준이었다. `assemble cfg/a.yaml` 이 battery 덱을 작업 폴더에 쓰고 cfg/ 의 주 덱에는 `*INCLUDE bt_tier0_phase1.k` 라
  솔버가 찾지 못했다. 이제 값을 적은 YAML 의 폴더 기준(assemble 의 output 은 assemble YAML · battery 설정의 output 은 그 설정)이고
  `*INCLUDE` 는 주 덱 폴더 기준 이름이다.
  A-1 battery 설정의 output · A-2 assemble 의 output · A-3 설정이 아래 폴더 · A-4 주 덱이 다른 폴더(`../`) · A-5 대조(cfg/ 에서)
  A-6 대조 — 설정을 절대 경로로 주고 그 폴더에서 돈다(플랫폼 꼴) → *INCLUDE 는 예전처럼 상대 이름(절대 경로로 바뀌지 않는다)
  A-7 대조 — battery 설정에 절대 output 을 적으면 *INCLUDE 도 적은 그대로 절대 경로
  W-1 · W-2 debug_prefix(단독 warpage · assemble)
  G-1 · G-2 미리 견주기(planRunWrites)도 같은 자리로 — 뒤 update 의 dynain 이 cfg/ 의 그 이름이면 무엇이든 쓰기 전에 rc 1

usage: test_yaml_dir_paths.py <KooRemapper 바이너리>
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
EIGHT = ("foldsurface", "refshell", "stackwrap", "linkage-fit", "applyfold", "section", "surfview", "stackdiagram")


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-90s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, args):
    p = subprocess.run([binary] + list(args), cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def tree(d):
    return sorted(os.path.relpath(os.path.join(r, f), d) for r, _, fs in os.walk(d) for f in fs)


def includes(path):
    ls = open(path, encoding="utf-8", errors="replace").read().splitlines()
    return [ls[i + 1].strip() for i, l in enumerate(ls[:-1]) if l.strip().upper() == "*INCLUDE"]


def assemble_side_files(binary, root):
    print("[assemble 의 battery 산출 · warpage debug_prefix]")
    w = SPEC["warpage"]
    bat = open(os.path.join(REPO, "examples", "battery", "swell", "stacked", "stacked_swell.yaml"),
               encoding="utf-8").read().replace("output: battery_stacked_swell", "output: bt")
    nodes = "*KEYWORD\n*NODE\n       1             0.0             0.0             0.0\n*END\n"
    debug = "    mode: deform\n    debug: true\n    debug_prefix: dbg\n"

    def setup(name, files):
        d = os.path.join(root, name)
        cfg = os.path.join(d, "cfg")
        os.makedirs(cfg)
        with open(os.path.join(cfg, "box.yaml"), "w", encoding="utf-8") as f:
            f.write(w["files"]["box.yaml"])
        run(binary, cfg, ["generate", "box", "box.yaml"])
        for rel, content in files.items():
            os.makedirs(os.path.dirname(os.path.join(cfg, rel)), exist_ok=True)
            with open(os.path.join(cfg, rel), "w", encoding="utf-8") as f:
                f.write(content)
        return d, cfg

    asm = "base_model: box.k\noutput: %s\noperations:\n  - type: battery\n    config: %s\n%s"
    abs_out = os.path.join(root, "A-7", "cfg", "abs_bt")   # A-7 의 battery 설정에 적을 절대 output
    for name, files, cwd_sub, deck, want, abs_inc in (
            ("A-1 battery 설정의 output: bt", {"bat.yaml": bat, "asm.yaml": asm % ("ba", "bat.yaml", "")},
             "", "ba.k", "bt_tier0_phase1.k", False),
            ("A-2 assemble 의 output: bx", {"bat.yaml": bat, "asm.yaml": asm % ("ba", "bat.yaml", "    output: bx\n")},
             "", "ba.k", "bx_tier0_phase1.k", False),
            ("A-3 설정이 cfg/sub/bat.yaml", {"sub/bat.yaml": bat, "asm.yaml": asm % ("ba", "sub/bat.yaml", "")},
             "", "ba.k", "sub/bt_tier0_phase1.k", False),
            ("A-4 주 덱이 cfg/out/ba.k", {"bat.yaml": bat, "out/keep": "", "asm.yaml": asm % ("out/ba", "bat.yaml", "")},
             "", "out/ba.k", "bt_tier0_phase1.k", False),
            ("A-5 대조 — cfg/ 에서 돌리면 예전 그대로", {"bat.yaml": bat, "asm.yaml": asm % ("ba", "bat.yaml", "")},
             "cfg", "ba.k", "bt_tier0_phase1.k", False),
            ("A-6 대조 — 절대 경로 설정 · cfg/ 에서(플랫폼 꼴)", {"bat.yaml": bat, "asm.yaml": asm % ("ba", "bat.yaml", "")},
             "abs", "ba.k", "bt_tier0_phase1.k", False),
            ("A-7 대조 — 절대 output", {"bat.yaml": bat.replace("output: bt", "output: " + abs_out),
                                       "asm.yaml": asm % ("ba", "bat.yaml", "")},
             "", "ba.k", "abs_bt_tier0_phase1.k", True)):
        d, cfg = setup(name[:3], files)
        if cwd_sub == "abs":
            rc, out = run(binary, cfg, ["assemble", os.path.join(cfg, "asm.yaml")])
        else:
            rc, out = run(binary, os.path.join(d, cwd_sub), ["assemble", "asm.yaml" if cwd_sub else "cfg/asm.yaml"])
        main_deck = os.path.join(cfg, deck)
        inc = includes(main_deck) if os.path.exists(main_deck) else []
        made = [t for t in tree(d) if t.endswith("_phase1.k")]
        ok_inc = len(inc) == 1 and os.path.isabs(inc[0]) == abs_inc and \
            os.path.normpath(os.path.join(os.path.dirname(main_deck), inc[0])) == os.path.normpath(os.path.join(cfg, want))
        check("★%s → battery 덱이 cfg/%s · 주 덱의 *INCLUDE(%s)가 그 파일을 가리킨다" % (name, want, "절대" if abs_inc else "상대"),
              rc == 0 and made == ["cfg/" + want] and ok_inc, (rc, made, inc, out[-300:]))
    for opname in ("warpage", "assemble"):
        files = dict(w["files"])
        files["warpage.yaml"] = files["warpage.yaml"].replace("    mode: deform\n", debug)
        del files["box.yaml"]
        d, cfg = setup("W_" + opname, files)
        rc, out = run(binary, d, [opname, "cfg/warpage.yaml"])
        dbg = [t for t in tree(d) if "dbg_" in t]
        check("★W %s cfg/warpage.yaml · debug_prefix: dbg → 진단 셋이 cfg/ 아래에(예전엔 작업 폴더)" % opname,
              rc == 0 and dbg == ["cfg/dbg_curvature.dat", "cfg/dbg_raw.dat", "cfg/dbg_warpage.vtk"], (rc, dbg, out[-300:]))
    warp = w["files"]["warpage.yaml"].split("operations:\n", 1)[1].replace("    mode: deform\n", debug)
    for name, ops, victim in (
            ("G-1 [warpage 진단 · battery output bx · update dynain: bx_tier0_phase1.k]",
             warp + "  - type: battery\n    config: bat.yaml\n    output: bx\n  - type: update\n    dynain: bx_tier0_phase1.k\n",
             "bx_tier0_phase1.k"),
            ("G-2 [battery output bx · warpage 진단 · update dynain: dbg_raw.dat]",
             "  - type: battery\n    config: bat.yaml\n    output: bx\n" + warp + "  - type: update\n    dynain: dbg_raw.dat\n",
             "dbg_raw.dat")):
        head = w["files"]["warpage.yaml"].split("operations:\n", 1)[0]
        d, cfg = setup(name[:3], {"bat.yaml": bat, "warp.dat": w["files"]["warp.dat"], victim: nodes,
                                  "asm.yaml": head.replace("output: box_warp", "output: g") + "operations:\n" + ops})
        before = tree(d)
        rc, out = run(binary, d, ["assemble", "cfg/asm.yaml"])
        check("★%s cfg/ 에서 → 무엇이든 쓰기 전에 rc 1 · 아무 파일도 늘지 않는다" % name,
              rc == 1 and tree(d) == before and open(os.path.join(cfg, victim)).read() == nodes,
              (rc, sorted(set(tree(d)) - set(before)), out[-300:]))


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="ydp_")
    try:
        for op in EIGHT:
            spec = SPEC[op]
            d = os.path.join(root, op)
            cfg = os.path.join(d, "cfg")
            os.makedirs(cfg)
            for need in spec["needs"]:
                src_dir = os.path.dirname(os.path.join(REPO, need))
                shutil.copytree(src_dir, os.path.join(cfg, os.path.dirname(need)), dirs_exist_ok=True)
            for name, content in spec["files"].items():
                with open(os.path.join(cfg, name), "w", encoding="utf-8") as f:
                    f.write(content)
            ok = True
            for c in spec["cmds"][:-1]:   # 준비 명령은 cfg/ 안에서(산출이 cfg/ 에 남는다)
                rc, out = run(binary, cfg, c.split()[1:])
                ok = ok and rc == 0
            if not check("%s 준비" % op, ok):
                continue
            argv = spec["cmds"][-1].split()[1:]
            argv[1] = "cfg/" + argv[1]
            rc, out = run(binary, d, argv)
            outs = spec["outputs"]
            last = [o for o in outs if os.path.exists(os.path.join(cfg, o))]
            stray = [o for o in outs if os.path.exists(os.path.join(d, o))]
            check("★%s cfg/%s — 산출 %s 가 cfg/ 아래에 · 작업 폴더에는 없다" % (op, argv[1][4:], spec["outputs"][-1]),
                  rc == 0 and os.path.exists(os.path.join(cfg, spec["outputs"][-1])) and not stray,
                  (rc, last, stray, out[-300:]))
        assemble_side_files(binary, root)
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
