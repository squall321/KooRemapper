#!/usr/bin/env python3
# 덱 · 보고가 아닌 산출(CSV · JSON · SVG · 곁 덱)도 쓰기가 실패하면(디스크 참) rc 1 로 말하는지 /dev/full 로 보는 회귀 시험(3차 4판 L-18)
"""덱 아닌 쓰기의 실패 (2026-11-22 · 미룬 결함 3차 4판 L-18).

왜 이 시험이 있나.

  덱 쓰기는 여섯째 검토(S2) 때 잘린 덱을 rc 0 으로 내지 않게 고쳤지만, 덱 · 보고가 아닌 쓰기(strain CSV · modelmeta · section ·
  id_floor JSON · surfview · stackdiagram SVG · cclip 보고 · generate 의 덱 · cleanup-nodes 보고 · 이월 조각 대응표 · foldsurface CSV)는
  `out << …; close()` 를 보지 않아 디스크가 차면 잘린(빈) 파일을 rc 0 으로 냈다. 카탈로그 사례를 한 번 돌려 새 산출을 알아내고 산출
  자리마다 /dev/full(쓰면 ENOSPC)을 가리키는 심볼릭 링크를 둔 채 다시 돌리면 75 자리 가운데 12 자리가 rc 0 이었다. 이제 다 rc 1 이고
  「… 쓰기가 멈췄다」 · 「파일을 쓰다 멈췄다」 로 까닭을 댄다.

usage: test_write_errors.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import test_deck_bom as T  # noqa: E402  (카탈로그 사례를 차리는 도우미)

OPS = ("generate", "cclip", "strain", "modelmeta", "foldsurface", "section", "surfview", "stackdiagram", "id_floor",
       "cad_solid_merge_to_deck", "cleanup-nodes",
       # 이미 rc 1 이던 자리도 회귀가 지킨다(3차 4판 L-19 — 잘린 map 산출 · 보고 파일 경로는 회귀가 못 쟀다)
       "map", "extract-parts")
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-90s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, cmd):
    p = subprocess.run(["prlimit", "--as=4294967296", "timeout", "120", binary] + cmd.split()[1:], cwd=cwd, capture_output=True)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    if not os.path.exists("/dev/full"):
        print("SKIP — /dev/full 이 없다")
        return 0
    binary = os.path.abspath(sys.argv[1])
    top = tempfile.mkdtemp(prefix="kr_write_err_")
    try:
        for spec in T.OPS:
            if spec["name"] not in OPS:
                continue
            root = os.path.join(top, re.sub(r"[^A-Za-z0-9]+", "_", spec["name"]))
            case = T.Case(binary, root, spec)
            rc0, text0, outs = case.go()
            outs = sorted(o for o in outs if ".kr_tmp_" not in o and not o.endswith((".yaml", ".yml")))
            if not check("%s — 대조 rc 0 · 산출 %d" % (spec["name"], len(outs)), rc0 == 0 and outs, text0[-300:]):
                continue
            for o in outs:
                shutil.rmtree(case.run, ignore_errors=True)
                shutil.copytree(case.base, case.run)
                p = os.path.join(case.run, o)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                if os.path.lexists(p):
                    os.remove(p)
                os.symlink("/dev/full", p)
                rc, text = run(binary, case.run, case.cmd)
                check("%s — %s 가 /dev/full 이면 rc 1 · 까닭" % (spec["name"], o), rc == 1 and ("멈췄다" in text or "Cannot write" in text), (rc, text[-300:]))
            shutil.rmtree(root, ignore_errors=True)
    finally:
        shutil.rmtree(top, ignore_errors=True)
    print()
    if FAILS:
        print("FAIL — %d 항 실패 / %d" % (len(FAILS), len(FAILS) + len(OKS)))
        for f in FAILS:
            print("  -", f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
