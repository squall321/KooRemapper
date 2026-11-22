#!/usr/bin/env python3
# meshfix 가 gmsh 앞 단계(.geo 쓰기)에서 멈추면 이 실행의 임시 파일(`.kr_tmp_mf.*`)을 치우는지 보는 회귀 시험(3차 4판 L-20)
"""meshfix gmsh 앞 실패의 임시 파일 (2026-11-22 · 미룬 결함 3차 4판 L-20).

왜 이 시험이 있나.

  meshfix 는 경계 STL · 다듬기 · 쪼개기 · .geo 를 `<줄기>.kr_tmp_mf.*` 에 쓰고 gmsh 를 돌린다. gmsh 가 실패하면 살펴보라고 보이는 이름
  (`<줄기>__mf.*`)으로 남기지만, 그 앞 단계에서 멈추면 아무도 치우지 않아 `.kr_tmp_mf.stl` 이 숨은 채 남았다(정확성 문제는 아니다 — 쌓인다).
  .geo 자리를 폴더로 막아 그 단계에서 멈추게 하고(STL 은 이미 썼다) 남은 임시 파일을 센다. gmsh 는 돌기 전이라 판번호만 답하는 대역을 쓴다.

usage: test_meshfix_temp_cleanup.py <KooRemapper 바이너리>
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-80s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="kr_mf_tmp_")
    try:
        shutil.copy(os.path.join(REPO, "examples", "mesh", "tetramesh.k"), d)
        stub = os.path.join(d, "gmsh_stub.sh")   # 판번호만 답한다 — 이 시험은 gmsh 를 돌리기 전에 멈춘다
        with open(stub, "w") as f:
            f.write("#!/bin/sh\n[ \"$1\" = --version ] && { echo 4.14.1; exit 0; }\nexit 3\n")
        os.chmod(stub, 0o755)
        with open(os.path.join(d, "mf.yaml"), "w") as f:
            f.write("model: tetramesh.k\noutput: mf_out.k\npid: 1\n")
        os.makedirs(os.path.join(d, "mf_out.kr_tmp_mf.geo"))   # .geo 쓰기를 막는다
        env = dict(os.environ, KOOREMAPPER_GMSH=stub)
        p = subprocess.run(["prlimit", "--as=4294967296", "timeout", "300", binary, "meshfix", "mf.yaml"], cwd=d, env=env,
                           capture_output=True, text=True, errors="replace")
        out = p.stdout + p.stderr
        check("meshfix — .geo 를 못 쓰면 rc 1 · 까닭", p.returncode == 1 and "geo" in out, (p.returncode, out[-300:]))
        left = sorted(os.path.basename(x) for x in glob.glob(os.path.join(d, "*.kr_tmp_mf*")))
        check("이 실행의 임시 파일(.kr_tmp_mf.*)을 치웠다 — 남은 것 %s" % left, not left, left)
        check("gmsh 실패 때 남기는 `__mf.*` 도 없다(gmsh 앞에서 멈췄다)", not glob.glob(os.path.join(d, "*__mf.*")), os.listdir(d))
    finally:
        shutil.rmtree(d, ignore_errors=True)
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
