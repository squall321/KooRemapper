#!/usr/bin/env python3
# 산출 이름이 덱이 끌어오는 인클루드 이름 자리면(산출 덱이 자기를 끌어온다) 쓰기 전에 rc 1 로 멈추는지 보는 회귀 시험(3차 4판 L-06)
"""산출이 인클루드 이름을 가린다 (2026-11-22 · 미룬 결함 3차 4판 L-06).

왜 이 시험이 있나.

  LS-DYNA 는 `*INCLUDE` 이름을 **덱 폴더에서 먼저** 찾고, 경로가 없는 이름만 `*INCLUDE_PATH` 폴더에서 찾는다(Vol_I 181591). 주 덱이
  `*INCLUDE_PATH` 폴더의 `part.k` 를 끌어오는데 산출 이름을 `part.k` 로 주면, 산출 덱이 같은 카드(`*INCLUDE part.k`)를 싣고 그것을 제
  폴더에서 먼저 찾으니 **자기 자신을 끌어온다**. 공용 산출 관문은 「쓸 파일 = 읽는 파일」 만 보아 이 꼴을 rc 0 으로 지나보냈다(산출을
  다른 폴더의 `part.k` 로 주어도 같다). 이제 쓸 파일이 제 폴더에서 덱의 인클루드 이름 자리면 rc 1.

무엇을 보나(주 덱 A/box.k — `*INCLUDE_PATH B` · `*INCLUDE part.k` · part.k 는 B 에만 있다).
  A database(공용 관문) — output part.k · ../C/part.k 는 rc 1 · 아무것도 안 쓴다 / 다른 이름은 rc 0 / 못 찾은 인클루드 이름도 rc 1
  B assemble(조립기 관문) — output part(→ part.k) rc 1 / `flatten_includes: true` 면 산출에 `*INCLUDE` 가 없어 rc 0

usage: test_output_include_shadow.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS, OKS = [], []
BOX = """output: box.k
lx: 20.0
ly: 10.0
lz: 2.0
nx: 4
ny: 2
nz: 1
rho: 7.85e-9
E: 210000.0
nu: 0.3
mid: 1
secid: 1
pid: 1
part_title: PLATE
"""
DB = "model: box.k\noutput: %s\npreset: drop\ndt: 0.0001\ndt_plot: 0.005\n"
OFFSET = """base_model: box.k
output: %s
%soperations:
  - type: offset
    source_pid: 1
    element_type: solid
    thickness: 1.0
    num_layers: 1
    offset_direction: +z
    connection_mode: tied
    new_pid: 10
    material_card: |
      *MAT_ELASTIC
      $#     mid        ro         e        pr
           @MID@  7.85E-09  2.10E+05       0.3
"""


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:500]))
    print("  %-70s %s" % (name[:70], "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    tmp = tempfile.mkdtemp(prefix="output_shadow_")
    try:
        a, b, c = (os.path.join(tmp, x) for x in "ABC")
        for d in (a, b, c):
            os.makedirs(d)
        open(os.path.join(a, "box.yaml"), "w").write(BOX)
        rc, out = run(binary, a, "generate", "box", "box.yaml")
        assert rc == 0, out[-300:]
        open(os.path.join(b, "part.k"), "w").write("*KEYWORD\n*DEFINE_CURVE\n       101\n0.0,0.0\n1.0,1.0\n*END\n")
        p = os.path.join(a, "box.k")
        body = open(p, encoding="utf-8").read()
        open(p, "w", encoding="utf-8").write(body.replace("*END", "*INCLUDE_PATH\n%s\n*INCLUDE\npart.k\n*END" % b))
        print("[A database — 공용 산출 관문]")
        for out_name, where in (("part.k", a), ("../C/part.k", c)):
            open(os.path.join(a, "db.yaml"), "w").write(DB % out_name)
            rc, out = run(binary, a, "database", "db.yaml")
            check("A output %s — rc 1 · 인클루드 이름 자리 · 쓰지 않았다" % out_name,
                  rc == 1 and "인클루드 이름" in out and not os.path.exists(os.path.join(where, "part.k")), (rc, out[-300:]))
        open(os.path.join(a, "db.yaml"), "w").write(DB % "box_db.k")
        rc, out = run(binary, a, "database", "db.yaml")
        check("A output box_db.k — rc 0(대조)", rc == 0 and os.path.exists(os.path.join(a, "box_db.k")), out[-300:])
        # 못 찾은 인클루드 이름(inc.k — 어디에도 없다)을 산출 이름으로 주면 산출 덱의 `*INCLUDE inc.k` 가 자기를 가리킨다
        open(p, "w", encoding="utf-8").write(body.replace("*END", "*INCLUDE\ninc.k\n*END"))
        open(os.path.join(a, "db.yaml"), "w").write(DB % "inc.k")
        rc, out = run(binary, a, "database", "db.yaml")
        check("A 못 찾은 이름 inc.k 를 output 으로 — rc 1", rc == 1 and "찾지 못한 이름" in out and not os.path.exists(os.path.join(a, "inc.k")),
              (rc, out[-300:]))
        open(p, "w", encoding="utf-8").write(body.replace("*END", "*INCLUDE_PATH\n%s\n*INCLUDE\npart.k\n*END" % b))
        print("[B assemble — 조립기 관문]")
        for left in (os.path.join(a, "part.k"), os.path.join(c, "part.k")):   # 옛 판이 A 에서 써 둔 것 — B 의 닫힘을 흐린다
            if os.path.exists(left):
                os.remove(left)
        open(os.path.join(a, "off.yaml"), "w").write(OFFSET % ("part", ""))
        rc, out = run(binary, a, "assemble", "off.yaml")
        check("B output part(→ part.k) — rc 1 · 인클루드 이름 자리", rc == 1 and "인클루드 이름" in out and
              not os.path.exists(os.path.join(a, "part.k")), (rc, out[-300:]))
        open(os.path.join(a, "off.yaml"), "w").write(OFFSET % ("part", "flatten_includes: true\n"))
        rc, out = run(binary, a, "assemble", "off.yaml")
        made = os.path.join(a, "part.k")
        flat = rc == 0 and os.path.exists(made) and "*INCLUDE\n" not in open(made, encoding="utf-8").read()
        check("B flatten_includes: true — 산출에 *INCLUDE 가 없어 rc 0", flat, (rc, out[-300:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("결과: %d 통과 · %d 실패" % (len(OKS), len(FAILS)))
    for f in FAILS:
        print("  FAIL " + f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
