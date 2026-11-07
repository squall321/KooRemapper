#!/usr/bin/env python3
# 작업 폴더 기준이던 YAML op 여덟이 YAML 안의 상대 경로를 그 YAML 파일이 있는 폴더 기준으로 푸는지 보는 회귀 시험
"""YAML 폴더 기준 경로 — 남았던 여덟 op (2026-11-07 셋째 묶음).

왜 이 시험이 있나.

  매뉴얼 §3.1(a) 는 「YAML 안의 상대 경로는 그 YAML 파일이 있는 폴더 기준 — 남은 예외는 map 하나」라고 적지만
  foldsurface · refshell · stackwrap · linkage-fit · applyfold · section · surfview · stackdiagram 은 YAML 값을 그대로 열어
  작업 폴더 기준이었다. `KooRemapper section cfg/sec.yaml` 이 cfg/ 옆의 모델을 못 찾거나 산출을 작업 폴더에 썼다.
  (플랫폼은 설정을 세션 폴더 = 작업 폴더에 두므로 바뀌는 것이 없다.)

무엇을 보나(op 마다 — 도움말 사례를 cfg/ 아래에 두고 그 위 폴더에서 `<op> cfg/<설정>` 을 돈다).
  rc 0 · 도움말이 말한 산출이 cfg/ 아래에 나오고 작업 폴더에는 없다.
  대조 — 설정이 작업 폴더에 있으면 예전과 같다(도움말 사례 그대로 · 회귀 run_help_examples).

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
