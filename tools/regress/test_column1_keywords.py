#!/usr/bin/env python3
# 들여쓴 `*` 줄(`*COMMENT` 글 속의 「  *END」 · 「  *INCLUDE」)이 어느 op 에서도 덱을 끝내거나 키워드가 되지 않는지 보는 회귀 시험
"""1열 키워드 규칙 (2026-11-08 재검토).

왜 이 시험이 있나.

  LS-DYNA 는 `*` 가 1열인 줄만 키워드로 읽는다(「키워드 앞 `*` 는 1열」 · Vol_I 17940). 리더(`KFileReader::isKeywordLine`)도 1열 `*` +
  글자만 키워드로 치고, 들여쓴 `*` 줄은 앞 블록의 데이터로 읽는다. 그런데 덱을 걷는 여러 걸음이 들여쓴 줄도 키워드로 보았다.
    · 첫 `*END` 앞에 덧붙이는 자리 — `kw_insertBeforeEnd`(relax · stabilize · implicit · modal · ale · optimize · cclip) · 단독 matswap ·
      cnrb2spring · meshfix · assemble 의 쓰기(writeOutput) · applyMatswap · applyMatdb · applyLoad 가 `*COMMENT` 글 속의 「  *END」 앞에
      카드를 넣었다(그 줄이 넣은 블록의 데이터가 된다)
    · 「*END 에서 멈춤」 — 인클루드 닫힘(`include_closure`) · cleanup-nodes · extract-parts 의 훑기 · 이월 조각 읽기가 거기서 덱을 끝냈다
    · 인클루드 닫힘이 글 속의 「  *INCLUDE」 를 따라가 없는 파일로 거절했다
  이제 다 공용 술어 하나(`deckscan::isKeywordLine` — 리더의 규칙)를 쓴다.

무엇을 보나.
  op 마다 같은 덱을 두 번 돌린다 — 그대로 · 맨 앞 `*KEYWORD` 뒤에 들여쓴 키워드 줄만 든 `*COMMENT` 블록을 끼운 덱. 둘 다 rc 0 이고,
  끼운 덱의 산출에서 그 블록 줄을 빼면 그대로 덱의 산출과 **바이트까지** 같다(덧붙인 카드 · 남긴 절점 · 실은 줄이 다 같다 —
  쓴 시각 머리줄 `$ Date:` 만 빼고 견준다).
  인클루드 파일 안에 끼운 덱도 본다(닫힘이 그 파일을 끝까지 읽는다).

usage: test_column1_keywords.py <KooRemapper 바이너리>
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples")
FAILS, OKS = [], []

# 들여쓴 키워드 줄만 든 `*COMMENT` 블록 — 1열이 아니라 글이다(닫힘이 따라가거나 덱이 끝나면 산출이 갈린다)
BLOCK = ["*COMMENT", "  *INCLUDE", "  ghost_include_not_here.k", "  *END", "  *NODE"]
BOX = "output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\nmid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n"


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-500:]))
    print("  %-90s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args, env=None):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, p.stdout + p.stderr


def read(path):
    with open(path, "rb") as f:
        return f.read()


def inject(path):
    """맨 앞 1열 `*KEYWORD` 줄 뒤(없으면 맨 앞)에 BLOCK 을 끼운다 — 그 파일의 개행을 따른다."""
    raw = read(path).decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    L = raw.split(nl)
    at = next((i + 1 for i, l in enumerate(L) if l.upper().startswith("*KEYWORD")), 0)
    L[at:at] = BLOCK
    with open(path, "wb") as f:
        f.write(nl.join(L).encode("utf-8"))


def undated(data):
    """쓴 시각 머리줄(`$ Date: …` — 메시 쓰기 · 생성기)만 뺀다 — 같은 덱을 두 번 쓰면 초가 갈릴 수 있다."""
    return b"\n".join(l for l in data.split(b"\n") if not l.startswith(b"$ Date:"))


def strip_block(data):
    """산출에서 BLOCK 줄(연달아 든 것)을 뺀다 — 개행은 그대로."""
    text = data.decode("utf-8", errors="replace")
    nl = "\r\n" if "\r\n" in text else "\n"
    L = text.split(nl)
    for i in range(len(L) - len(BLOCK) + 1):
        if L[i:i + len(BLOCK)] == BLOCK:
            del L[i:i + len(BLOCK)]
            break
    return nl.join(L).encode("utf-8")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    gmsh = os.environ.get("KOOREMAPPER_GMSH") or os.environ.get("KOOREMAPPER_TEST_GMSH") or \
        os.path.join(REPO, "dist", "gmsh", "gmsh")
    top = tempfile.mkdtemp(prefix="col1kw_")
    try:
        base = os.path.join(top, "base")
        os.makedirs(base)
        with open(os.path.join(base, "box.yaml"), "w") as f:
            f.write(BOX)
        run(binary, base, "generate", "box", "box.yaml")
        run(binary, base, "generate", "arc", "--dim-i", "6", "--dim-j", "3", "--dim-k", "2", "g")
        box = os.path.join(base, "box.k")

        # (이름, 깔 파일 {이름: 원본}, 끼울 파일, 명령, 산출, 설정 {이름: 글})
        cases = [
            ("relax", {"box.k": box}, ["box.k"], ["relax", "c.yaml"], ["box_relaxed.k"],
             {"c.yaml": "model: box.k\noutput: box_relaxed.k\nlevel: 2\nmode: explicit\ndrterm: 100.0\nendtime: 1.0\n"}),
            ("stabilize", {"box.k": box}, ["box.k"], ["stabilize", "c.yaml"], ["box_lv03.k"],
             {"c.yaml": "model: box.k\noutput: box_lv03.k\nstabilize: explicit\nlevel: 3\n"}),
            ("implicit", {"box.k": box}, ["box.k"], ["implicit", "c.yaml"], ["box_implicit.k"],
             {"c.yaml": "model: box.k\noutput: box_implicit.k\nmode: static\nlevel: 2\nendtime: 1.0\n"}),
            ("modal", {"box.k": box}, ["box.k"], ["modal", "c.yaml"], ["box_modal.k"],
             {"c.yaml": "model: box.k\noutput: box_modal.k\nnmode: 10\nfmax: 2000.0\n"}),
            ("ale", {"box.k": box}, ["box.k"], ["ale", "c.yaml"], ["box_ale.k"],
             {"c.yaml": "model: box.k\noutput: box_ale.k\nale_parts:\n  - pid: 1\n    material: air\n"}),
            ("optimize", {"box.k": box}, ["box.k"], ["optimize", "c.yaml"], ["box_opt.k"],
             {"c.yaml": "model: box.k\noutput: box_opt.k\noptimize: rubber\npids: [1]\ntssfac: 0.67\n"}),
            ("database", {"box.k": box}, ["box.k"], ["database", "c.yaml"], ["box_db.k"],
             {"c.yaml": "model: box.k\noutput: box_db.k\npreset: drop\ndt: 0.0001\ndt_plot: 0.005\n"}),
            ("matdb", {"box.k": box, "materials/material_db.json": os.path.join(REPO, "materials", "material_db.json")}, ["box.k"],
             ["matdb", "c.yaml"], ["box_matdb.k"],
             {"c.yaml": "model: box.k\noutput: box_matdb.k\nmat_type: MAT_ELASTIC\nmaterials:\n  - mid: 1\n    match: \"SUS304\"\n"}),
            ("load", {"box.k": box}, ["box.k"], ["load", "c.yaml"], ["box_loaded.k"],
             {"c.yaml": "model: box.k\noutput: box_loaded.k\nloads:\n  - part: 1\n    mode: pressure\n    value: 1.0\n"
                         "    direction: [0, 0, 1]\n"}),
            ("assemble-contact", {"box.k": box}, ["box.k"], ["assemble", "c.yaml"], ["out.k"],
             {"c.yaml": "base_model: box.k\noutput: out\noperations:\n  - type: contact\n    contacts:\n      - action: create\n"
                         "        type: tied\n        slave:\n          pid: 1\n        master:\n          pid: 1\n"}),
            ("matswap", {"two_cubes.k": os.path.join(EX, "matswap", "two_cubes.k"), "rubber.k": os.path.join(EX, "matswap", "rubber.k")},
             ["two_cubes.k"], ["matswap", "c.yaml"], ["swapped.k"],
             {"c.yaml": "model: two_cubes.k\noutput: swapped.k\nswaps:\n  - bundle: rubber.k\n    pid: 1\n"}),
            ("assemble-matswap", {"two_cubes.k": os.path.join(EX, "matswap", "two_cubes.k"), "rubber.k": os.path.join(EX, "matswap", "rubber.k")},
             ["two_cubes.k"], ["assemble", "c.yaml"], ["asm_swap.k"],
             {"c.yaml": "base_model: two_cubes.k\noutput: asm_swap\noperations:\n  - type: matswap\n    bundle: rubber.k\n    pid: 1\n"}),
            ("cnrb2spring", {"two_plate_bolt.k": os.path.join(EX, "cnrb2spring", "two_plate_bolt.k"),
                             "c.yaml": os.path.join(EX, "cnrb2spring", "two_plate_bolt.yaml")},
             ["two_plate_bolt.k"], ["cnrb2spring", "c.yaml"], ["two_plate_bolt_spring.k"], {}),
            ("cleanup-nodes", {"cleanup_demo.k": os.path.join(EX, "cleanup-nodes", "cleanup_demo.k")}, ["cleanup_demo.k"],
             ["cleanup-nodes", "c.yaml"], ["clean.k"],
             {"c.yaml": "model: cleanup_demo.k\noutput: clean.k\nmode: safe\nprune_sets: true\n"}),
            ("extract-parts", {"assembly.k": os.path.join(EX, "extract-parts", "assembly.k"),
                               "part2_include.k": os.path.join(EX, "extract-parts", "part2_include.k")}, ["assembly.k"],
             ["extract-parts", "c.yaml"], ["extracted.k"], {"c.yaml": "model: assembly.k\noutput: extracted.k\nparts: [1, 2]\n"}),
            ("extract-parts-include", {"assembly.k": os.path.join(EX, "extract-parts", "assembly.k"),
                                       "part2_include.k": os.path.join(EX, "extract-parts", "part2_include.k")}, ["part2_include.k"],
             ["extract-parts", "c.yaml"], ["extracted.k"], {"c.yaml": "model: assembly.k\noutput: extracted.k\nparts: [1, 2]\n"}),
            ("cleanup-nodes-include", {"assembly.k": os.path.join(EX, "extract-parts", "assembly.k"),
                                       "part2_include.k": os.path.join(EX, "extract-parts", "part2_include.k")}, ["part2_include.k"],
             ["cleanup-nodes", "c.yaml"], ["clean.k"], {"c.yaml": "model: assembly.k\noutput: clean.k\nmode: safe\n"}),
            ("map", {"g_bent.k": os.path.join(base, "g_bent.k"), "f.k": os.path.join(base, "g_flat.k")}, ["f.k"],
             ["map", "g_bent.k", "f.k", "out.k"], ["out.k"], {}),
        ]
        if os.path.exists(gmsh):
            cases.append(("meshfix", {"t.k": os.path.join(base, "g_flat_tet.k")}, ["t.k"], ["meshfix", "c.yaml"], ["remeshed.k"],
                          {"c.yaml": "model: t.k\noutput: remeshed.k\npid: 1\nlc_target: 6.0\n"}))
        carry = os.path.join(EX, "apply_carryover_plan")
        cases.append(("apply_carryover_plan", {n: os.path.join(carry, n) for n in os.listdir(carry)}, ["deck.k"],
                      ["apply_carryover_plan", "c.yaml"], ["out.k"], {"c.yaml": "model: deck.k\nplan: plan.json\noutput: out.k\n"}))

        env = dict(os.environ)
        if os.path.exists(gmsh):
            env["KOOREMAPPER_GMSH"] = gmsh
        print("[op 마다 — 들여쓴 키워드 줄만 든 *COMMENT 를 끼워도 산출이 같다(그 블록 줄만 더해진다)]")
        for name, files, targets, argv, outs, cfg in cases:
            res = {}
            for variant in ("plain", "cmt"):
                d = os.path.join(top, name, variant)
                os.makedirs(d)
                for dst, src in files.items():
                    os.makedirs(os.path.dirname(os.path.join(d, dst)) or d, exist_ok=True)
                    shutil.copy(src, os.path.join(d, dst))
                for dst, text in cfg.items():
                    with open(os.path.join(d, dst), "w") as f:
                        f.write(text)
                if variant == "cmt":
                    for t in targets:
                        inject(os.path.join(d, t))
                    if name == "apply_carryover_plan":   # 계획은 덱의 sha256 을 잰다
                        pp = os.path.join(d, "plan.json")
                        plan = json.load(open(pp, encoding="utf-8"))
                        plan["deck"]["sha256"] = hashlib.sha256(read(os.path.join(d, "deck.k"))).hexdigest()
                        with open(pp, "w", encoding="utf-8") as f:
                            f.write(json.dumps(plan, ensure_ascii=False, indent=1))
                rc, out = run(binary, d, *argv, env=env)
                res[variant] = (rc, out, [read(os.path.join(d, o)) if os.path.exists(os.path.join(d, o)) else None for o in outs])
            rc0, out0, o0 = res["plain"]
            rc1, out1, o1 = res["cmt"]
            same = all(a is not None and b is not None and undated(strip_block(b)) == undated(a) for a, b in zip(o0, o1))
            check("%s — rc 0 · 끼운 덱의 산출 − 그 블록 = 그대로 덱의 산출(바이트)" % name, rc0 == 0 and rc1 == 0 and same,
                  (rc0, rc1, [x is None for x in o0], [x is None for x in o1], out1[-400:]))
    finally:
        shutil.rmtree(top, ignore_errors=True)

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
