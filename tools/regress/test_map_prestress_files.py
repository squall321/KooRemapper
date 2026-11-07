#!/usr/bin/env python3
# map · prestress 가 쓰는 곁 파일(메시 사본 · CSV · 앞처리 평판 임시 파일)의 이름과 뒷정리가 문서대로인지 보는 회귀 시험
"""map · prestress 의 곁 파일 (2026-11-07 셋째 묶음).

왜 이 시험이 있나.

  · prestress 의 메시 사본 · CSV 이름을 경로 전체의 마지막 `.` 으로 만들어 `./pre` 가 `.k`, `a.d/pre` 가 `a.k` 를 썼다
    (파일 이름의 확장자가 아니라 폴더 이름의 점을 잘랐다). 이제 파일 이름의 확장자만 바꾼다.

무엇을 보나.
  P — prestress 의 메시 사본 · CSV 가 `<output 에서 파일 이름의 확장자를 뗀 이름>.k` · `.csv` 로 나가고, 폴더 이름의 점이나
      `./` 의 점을 확장자로 보지 않는다.

usage: test_map_prestress_files.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-92s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def exists(d, rel):
    return os.path.exists(os.path.join(d, rel))


def prestress_names(binary, root):
    print("[P] prestress 곁 이름은 파일 이름의 확장자만 바꾼다")
    d = os.path.join(root, "p")
    os.makedirs(os.path.join(d, "a.d"))
    rc, out = run(binary, d, "generate", "--dim-i", "10", "--dim-j", "4", "arc", "demo")
    if not check("P-0 준비 — generate arc", rc == 0, out[-300:]):
        return
    pre = ["prestress", "--E", "210000", "--nu", "0.3"]
    rc, out = run(binary, d, *pre, "demo_flat.k", "demo_bent.k", "./pre")
    check("P-1 output ./pre → 메시 사본 pre.k (예전엔 `.k`)", rc == 0 and exists(d, "pre.k") and not exists(d, ".k"),
          (rc, sorted(os.listdir(d)), out[-300:]))
    check("P-2   └ dynain 은 output 그대로(./pre)", exists(d, "pre"))
    rc, out = run(binary, d, *pre, "demo_flat.k", "demo_bent.k", "a.d/pre")
    check("P-3 output a.d/pre → a.d/pre.k (예전엔 폴더 이름의 점을 잘라 a.k)",
          rc == 0 and exists(d, "a.d/pre.k") and not exists(d, "a.k"), (rc, sorted(os.listdir(d)), out[-300:]))
    rc, out = run(binary, d, *pre, "--csv", "demo_flat.k", "demo_bent.k", "a.d/q")
    check("P-4 --csv output a.d/q → a.d/q.csv · a.d/q.k (예전엔 a.csv · a.k)",
          rc == 0 and exists(d, "a.d/q.csv") and exists(d, "a.d/q.k") and not exists(d, "a.csv"),
          (rc, sorted(os.listdir(d)), out[-300:]))
    rc, out = run(binary, d, *pre, "demo_flat.k", "demo_bent.k", "r.dynain")
    check("P-5 대조 — output r.dynain → r.dynain · r.k (예전과 같다)",
          rc == 0 and exists(d, "r.dynain") and exists(d, "r.k"), (rc, out[-300:]))
    rc, out = run(binary, d, *pre, "demo_flat.k", "demo_bent.k", ".hidden")
    check("P-6 이름 첫 글자의 점은 확장자가 아니다 — output .hidden → .hidden.k",
          rc == 0 and exists(d, ".hidden.k"), (rc, sorted(os.listdir(d)), out[-300:]))


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="mpf_")
    try:
        prestress_names(binary, root)
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
