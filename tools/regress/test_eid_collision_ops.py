#!/usr/bin/env python3
# 솔리드 · 셸 요소 번호가 겹친 덱에서 modelmeta 가 잃은 수를 싣고 덱을 쓰는 op 이 거절하는지(DF-14) 보는 회귀 시험
"""요소 번호 겹침 — modelmeta 의 잃은 수 · 덱을 쓰는 op 의 거절 (2026-11-17 · DF-14 · 사용자 결정 「감지 · 경고 · 쓰기 거절」).

왜 이 시험이 있나.

  리더는 요소를 번호 하나로 한 표(`Mesh::elements`)에 담는다. 솔리드 1 과 셸 1 처럼 족을 건넌 번호는 LS-DYNA 가 족마다 따로 받아
  정상으로 도는데, 이 도구는 뒤 정의만 남기고 앞 정의를 말없이 잃었다. 실제 덱(겹친 요소 3만여 개)에서 modelmeta 파트 목록이
  944 파트 줄었고, 덱을 쓰는 op 은 그 요소가 빠진 덱을 냈다. 이제 리더가 잃은 것을 PID 별로 적고(`Mesh::readerLostElements`),
  modelmeta 는 `model.element_id_collisions` · `model.parts_missing` 을 싣고, 덱을 쓰는 `KFileWriter` 는 거절한다.

무엇을 보나(상자 덱 — 절점 1~198 · 솔리드 1~100 · PID 1 — 에 셸 파트 PID 2 를 덧붙인다).
  M-1 셸 1~20 이 솔리드 뒤 → 잃은 20 · 빠진 파트 0(PID 1 은 80 남는다) · 콘솔 경고
  M-2 셸 1~100 이 솔리드 뒤 → 잃은 100 · 빠진 파트 1(PID 1 이 목록에서 빠진다)
  M-3 셸 블록이 솔리드 앞 → 솔리드가 셸 20 을 덮어 잃은 PID 는 2 · 빠진 파트 1
  M-4 대조 셸 1001~1020 → 0 · 0 · 경고 없음
  W-* 덱을 쓰는 op 이 겹친 덱이면 거절(rc ≠ 0 · 거절 글 · 산출 없음), 대조 덱이면 산출을 낸다.
      map · unfold 는 굽은 덱이 육면체만 받으므로 두께 셸(`*ELEMENT_TSHELL` — 리더가 솔리드와 같은 칸으로 읽는다) 1~20 이
      솔리드 1~20 을 덮는 덱으로 잰다(map 은 평판 쪽 · 굽은 쪽 둘 다 — 굽은 쪽은 remap 결과가 표를 옮겨 받아야 거절된다).
      대조는 상자 그대로. squeeze · shellmap · tetremesh 는 M-1 대 M-4. tetremesh 는 gmsh 가 없으면 건너뛴다

usage: test_eid_collision_ops.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

FAILS, OKS = [], []
REFUSE = "요소 번호가 겹쳐 리더가 앞 정의"

BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\n"
       "mid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-500:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def shell_block(eids, quads):
    """셸 파트 PID 2(단면 2 · 재질 1)와 `*ELEMENT_SHELL` — eids[i] 에 quads[i] 의 네 절점."""
    s = ("*SECTION_SHELL\n$#   secid    elform\n         2         2\n       0.1       0.1       0.1       0.1\n"
         "*PART\nSKIN\n$#     pid     secid       mid\n         2         2         1\n*ELEMENT_SHELL\n")
    for e, q in zip(eids, quads):
        s += "%8d%8d%8d%8d%8d%8d\n" % ((e, 2) + tuple(q))
    return s


def face_quads():
    """상자 밑면(k=0) 50 · 윗면(k=2) 50 의 사각형 — 절점 = 1 + i + 11 j + 66 k."""
    qs = []
    for k in (0, 2):
        for j in range(5):
            for i in range(10):
                n = 1 + i + 11 * j + 66 * k
                qs.append((n, n + 1, n + 12, n + 11))
    return qs


def make_deck(binary, root, name, eids, shells_first=False):
    d = os.path.join(root, name)
    os.makedirs(d)
    with open(os.path.join(d, "box.yaml"), "w", encoding="utf-8") as f:
        f.write(BOX)
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    if rc != 0:
        raise RuntimeError("generate box 실패: " + out[-300:])
    p = os.path.join(d, "box.k")
    s = open(p, encoding="utf-8").read()
    blk = shell_block(eids, face_quads()[:len(eids)]) if eids else ""
    if shells_first:
        s = s.replace("*NODE", blk + "*NODE", 1)
    else:
        s = s.replace("*END", blk + "*END", 1)
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)
    return d


def make_tshell_deck(binary, root, name):
    """상자 + 두께 셸 PID 3 — 솔리드 1~20 과 같은 번호 · 같은 절점(솔리드가 앞이라 두께 셸이 덮는다)."""
    d = make_deck(binary, root, name, [])
    p = os.path.join(d, "box.k")
    s = open(p, encoding="utf-8").read()
    sol = s.split("*ELEMENT_SOLID", 1)[1].split("*", 1)[0].splitlines()
    rows = [l.split() for l in sol if l.strip() and not l.startswith("$")][:20]
    blk = "*SECTION_TSHELL\n         3         1\n*PART\nTSH\n         3         3         1\n*ELEMENT_TSHELL\n"
    for f in rows:
        blk += "%8d%8d" % (int(f[0]), 3) + "".join("%8d" % int(x) for x in f[2:10]) + "\n"
    with open(p, "w", encoding="utf-8") as f:
        f.write(s.replace("*END", blk + "*END", 1))
    return d


def modelmeta(binary, d):
    with open(os.path.join(d, "mm.yaml"), "w", encoding="utf-8") as f:
        f.write("model: box.k\noutput: mm\ndetect: false\ngap_tol: 0.05\n")
    rc, out = run(binary, d, "modelmeta", "mm.yaml")
    try:
        data = json.load(open(os.path.join(d, "mm_modelmeta.json"), encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return rc, out, data.get("model") or {}, [p.get("pid") for p in data.get("parts") or []]


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="eidc_")
    try:
        cases = [
            ("M-1 셸 1~20 이 솔리드 뒤 — 잃은 20 · 빠진 파트 0 · 경고", "m1", list(range(1, 21)), False, 20, 0, [1, 2]),
            ("M-2 셸 1~100 이 솔리드 뒤 — 잃은 100 · 빠진 파트 1(PID 1)", "m2", list(range(1, 101)), False, 100, 1, [2]),
            ("M-3 셸 블록이 솔리드 앞 — 솔리드가 셸 20 을 덮는다 · 빠진 파트 1(PID 2)", "m3", list(range(1, 21)), True, 20, 1, [1]),
            ("M-4 대조 셸 1001~1020 — 0 · 0 · 경고 없음", "m4", list(range(1001, 1021)), False, 0, 0, [1, 2]),
        ]
        dirs = {}
        for name, key, eids, first, lost, missing, pids in cases:
            d = make_deck(binary, root, key, eids, first)
            dirs[key] = d
            rc, out, model, got_pids = modelmeta(binary, d)
            warned = "요소 번호가 겹쳐 리더가 앞 정의" in out
            check(name, rc == 0 and model.get("element_id_collisions") == lost and model.get("parts_missing") == missing
                  and sorted(got_pids) == pids and warned == (lost > 0),
                  (rc, model.get("element_id_collisions"), model.get("parts_missing"), got_pids, warned, out[-300:]))

        # 덱을 쓰는 op — 겹친 덱은 거절, 대조 덱은 산출
        gmsh = os.environ.get("KOOREMAPPER_TEST_GMSH", "")
        dirs["ts"] = make_tshell_deck(binary, root, "ts")
        dirs["pure"] = make_deck(binary, root, "pure", [])
        for key in ("m1", "m4", "ts", "pure"):
            d = dirs[key]
            shutil.copy(os.path.join(dirs["pure"], "box.k"), os.path.join(d, "pure.k"))
            with open(os.path.join(d, "sq.yaml"), "w", encoding="utf-8") as f:
                f.write("parts:\n  - pid: 1\n    eps_x: -0.01\n    eps_y: -0.01\n    eps_z: 0.0\nmaterial:\n  E: 210000.0\n  nu: 0.3\n")
            with open(os.path.join(d, "tet.yaml"), "w", encoding="utf-8") as f:
                f.write("model: box.k\noutput: tet_out.k\nbackend: localimprove\ntarget_pids: [1]\n")
            # shellmap 의 굽은 셸 — 상자 밑면 셸만 담은 덱(겹침 없음)
            nodes = open(os.path.join(d, "box.k"), encoding="utf-8").read().split("*NODE", 1)[1].split("*", 1)[0]
            with open(os.path.join(d, "skin.k"), "w", encoding="utf-8") as f:
                f.write("*KEYWORD\n*NODE" + nodes + shell_block(range(5001, 5051), face_quads()[:50]).replace(
                    "*SECTION_SHELL", "*MAT_ELASTIC\n         1  7.85e-09   2.1e+05       0.3\n*SECTION_SHELL", 1) + "*END\n")
        # (이름, 겹친 덱 자리, 대조 덱 자리, 인자, 산출 파일)
        ops = [
            ("map 평판 쪽", "ts", "pure", ("map", "pure.k", "box.k", "out.k"), "out.k"),
            ("map 굽은 쪽", "ts", "pure", ("map", "box.k", "pure.k", "out.k"), "out.k"),
            ("unfold", "ts", "pure", ("unfold", "box.k", "out.k"), "out.k"),
            ("squeeze", "m1", "m4", ("squeeze", "box.k", "sq.yaml", "sq"), "sq.k"),
            ("shellmap", "m1", "m4", ("shellmap", "--thickness", "2.0", "skin.k", "box.k", "out.k"), "out.k"),
            ("tetremesh", "m1", "m4", ("tetremesh", "tet.yaml"), "tet_out.k"),
        ]
        for op, bad, good, args, out_name in ops:
            if op == "tetremesh" and not gmsh:
                print("  %-100s SKIP" % ("W-%s gmsh 경로가 없다(KOOREMAPPER_TEST_GMSH)" % op))
                continue
            for k in (bad, good):
                out_path = os.path.join(dirs[k], out_name)
                if os.path.exists(out_path):
                    os.remove(out_path)
            rc1, out1 = run(binary, dirs[bad], *args)
            made1 = os.path.exists(os.path.join(dirs[bad], out_name))
            rc4, out4 = run(binary, dirs[good], *args)
            made4 = os.path.exists(os.path.join(dirs[good], out_name))
            check("W-%s 겹친 덱이면 거절(rc ≠ 0 · 거절 글 · 산출 없음), 대조 덱이면 산출" % op,
                  rc1 != 0 and REFUSE in out1 and not made1 and rc4 == 0 and made4,
                  (rc1, made1, out1[-300:], rc4, made4, out4[-300:]))
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
