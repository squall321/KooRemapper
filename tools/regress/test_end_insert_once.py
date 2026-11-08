#!/usr/bin/env python3
# contact · boundary · rbe · battery 가 *END 가 둘인 덱에 카드를 한 벌만, 주 덱의 첫 *END 앞에 넣는지 보는 회귀 시험
"""덧붙인 카드는 주 덱의 첫 `*END` 앞에 한 벌만 (2026-11-07 · 셋째 묶음 #3 · #4).

왜 이 시험이 있나.

  LS-DYNA 는 첫 `*END` 에서 읽기를 멈춘다. 쓰기(`ModelAssembler::writeOutput`)의 덧붙임은 첫 `*END` 앞에만 넣게 고쳤지만(1dfa555 ·
  `endInsertsDone`), 쓰기 밖에서 `rawLines_` 를 고치는 넷은 그대로였다.
    · applyContact · applyBoundary · applyRbe — `*END` 를 만날 때마다 넣어 `*END` 가 둘인 덱에 같은 접촉 · SPC · 구속이 **두 벌**
      나갔고(둘째 벌은 해석에 안 든다), `*END` 가 없는 덱에서는 아무 데도 넣지 않아 카드가 **조용히 빠졌다**.
    · applyBattery — `*INCLUDE` 를 **마지막** `*END` 앞에 넣어 `*END` 가 둘인 덱에서는 LS-DYNA 가 그 인클루드를 읽지 않았다.
  이제 넷 다 주 덱의 첫 `*END` 앞에(없으면 끝에) 한 번 넣는다. 같은 꼴을 단독 op 에서도 찾아 고쳤다(공용 `deckscan::insertBeforeFirstEnd`).
    · 단독 database · cnrb2solid(assemble 도 같은 함수) — `*END` 마다 넣었다(cnrb2solid 는 `*END` 가 없으면 넣지 않아 CNRB 만 지워졌다).
    · hfdamp(assemble 도 같은 함수) · 단독 contact — **마지막** `*END` 앞에 넣었다.
    · map · shellmap · squeeze 의 메시 쓰기(KFileWriter) — 원본의 `*END` 를 모두 지우고 끝에 하나만 써 첫 `*END` 뒤의(읽히지 않던) 카드가
      산출에서 살아났다. 이제 첫 `*END` 에서 끝내고 남은 원본 줄은 그 뒤에 그대로 둔다.
    · 단독 squeeze 의 덧붙임(dynain `*INCLUDE` · `*MAT_ADD_THERMAL_EXPANSION` · `*INITIAL_TEMPERATURE_NODE` · DR · `*CONTROL_TERMINATION` ·
      `*DATABASE_BINARY_D3DRLF`) · map 의 prestress 훅(`*INCLUDE <dynain>`) — `*END` 마다 넣었다. 메시 쓰기가 첫 `*END` 뒤를 남기게 된 뒤로
      `*END` 가 둘인 덱에 두 벌이 나갔다(2026-11-08 재검토). 이제 공용 `deckscan` 으로 첫 `*END` 앞에 한 번.
    · cnrb2solid — 덱 전체를 읽어 첫 `*END` 뒤의(읽히지 않는) CNRB 를 산 솔리드로 바꿨다(그 PNODE 도 지웠다). 이제 첫 `*END` 앞만 읽는다.
    · 들여쓴 `  *END` — 키워드의 `*` 는 1열이다(Vol_I 17940 · 리더 `KFileReader::isKeywordLine`). 첫 `*END` 찾기(`deckscan::firstEndLine`)와
      메시 쓰기(KFileWriter)가 들여쓴 줄도 `*END` 로 보아, `*COMMENT` 글 속의 「  *END」 앞에 카드를 넣고(그 줄이 넣은 블록의 데이터가
      됐다) 메시 쓰기는 거기서 `*END` 를 쓰고 원본 `*END` 를 또 베꼈다(2026-11-08 재검토).

무엇을 보나.
  `*END` 가 둘인 덱 — 넣은 카드 수가 `*END` 하나인 덱과 같고, 넣은 카드가 다 첫 `*END` 앞에 있다(contact · boundary · rbe) ·
  배터리 `*INCLUDE` 가 첫 `*END` 앞에 있다 · `*END` 가 없는 덱에도 카드가 들어간다(contact · boundary · rbe) · squeeze 의 덧붙임과
  map prestress 훅의 `*INCLUDE` 도 `*END` 가 둘인 덱에 한 벌 · 첫 `*END` 앞 · `*END` 가 없으면 끝에 붙이고 `*END` 를 쓴다.

usage: test_end_insert_once.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
FAILS, OKS = [], []

BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 4\nny: 2\nnz: 1\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\nmid: 1\n"
       "secid: 1\npid: 1\npart_title: PLATE\n")
TAIL = "*COMMENT\nLS-DYNA 는 첫 *END 에서 멈춘다 — 아래는 읽지 않는다\n*END\n"
BAT = ("output: bat\nmodel_type: stacked\ntier: -1\nphase: 1\ngeometry:\n  cell_width: 30\n  cell_height: 30\n"
       "  n_unit_cells: 1\n")


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-84s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def lines_of(path):
    return open(path, encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(path) else []


def first_end(L):
    return next((i for i, l in enumerate(L) if l.upper().startswith("*END")), len(L))


def kw_rows(L, prefix):
    return [i for i, l in enumerate(L) if l.upper().startswith(prefix)]


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="endins_")
    try:
        write(os.path.join(d, "box.yaml"), BOX)
        run(binary, d, "generate", "box", "box.yaml")
        box = open(os.path.join(d, "box.k"), encoding="utf-8").read()
        write(os.path.join(d, "one.k"), box)                                   # *END 하나
        write(os.path.join(d, "two.k"), box + TAIL)                            # *END 둘
        write(os.path.join(d, "none.k"), box.replace("*END\n", ""))            # *END 없음

        cases = (
            ("contact", "*CONTACT", lambda m, o: ("assemble", "base_model: %s\noutput: %s\noperations:\n  - type: contact\n"
                                                  "    contacts:\n      - action: create\n        type: tied\n"
                                                  "        slave:\n          pid: 1\n        master:\n          pid: 1\n" % (m, o[:-2]))),
            ("boundary", "*BOUNDARY_SPC", lambda m, o: ("boundary", "model: %s\noutput: %s\nboundaries:\n  - part: 1\n    dof: xyz\n"
                                                        "    direction: [0, 0, -1]\n    select: direction\n    angle: 45.0\n" % (m, o))),
            ("rbe", "*CONSTRAINED", lambda m, o: ("rbe", "model: %s\noutput: %s\nrbe:\n  - part: 1\n    select: direction\n"
                                                  "    direction: [0, 0, 1]\n    angle: 45.0\n    type: rbe3\n    mode: spider\n" % (m, o))),
        )
        for name, prefix, mk in cases:
            print("[%s]" % name)
            counts = {}
            for deck in ("one", "two", "none"):
                out = "%s_%s_out.k" % (name, deck)
                op, body = mk(deck + ".k", out)
                write(os.path.join(d, "%s_%s.yaml" % (name, deck)), body)
                rc, text = run(binary, d, op, "%s_%s.yaml" % (name, deck))
                L = lines_of(os.path.join(d, out))
                counts[deck] = (rc, len(kw_rows(L, prefix)), all(i < first_end(L) for i in kw_rows(L, prefix)), text)
            rc1, n1, _, t1 = counts["one"]
            rc2, n2, before2, t2 = counts["two"]
            rc0, n0, _, t0 = counts["none"]
            check("%s-1 기준 — *END 하나인 덱에 %s 카드가 들어간다" % (name, prefix), rc1 == 0 and n1 > 0, (rc1, n1, t1[-300:]))
            check("%s-2 ★*END 가 둘인 덱 — %s 카드가 한 벌(%d)이고 다 첫 *END 앞이다" % (name, prefix, n1),
                  rc2 == 0 and n2 == n1 and before2, (rc2, n2, before2, t2[-300:]))
            check("%s-3 ★*END 가 없는 덱에도 %s 카드가 들어간다(예전엔 넣을 자리가 없어 빠졌다)" % (name, prefix),
                  rc0 == 0 and n0 == n1, (rc0, n0, t0[-300:]))

        print("[battery]")
        write(os.path.join(d, "bat.yaml"), BAT)
        for deck in ("one", "two"):
            write(os.path.join(d, "b_%s.yaml" % deck), "base_model: %s.k\noutput: b_%s_out\noperations:\n  - type: battery\n"
                                                      "    config: bat.yaml\n" % (deck, deck))
            rc, text = run(binary, d, "assemble", "b_%s.yaml" % deck)
            L = lines_of(os.path.join(d, "b_%s_out.k" % deck))
            inc = kw_rows(L, "*INCLUDE")
            ok = rc == 0 and len(inc) == 1 and inc[0] < first_end(L)
            if deck == "one":
                check("battery-1 기준 — *END 하나인 덱에 배터리 *INCLUDE 가 첫 *END 앞에 들어간다", ok, (rc, inc, text[-300:]))
            else:
                check("battery-2 ★*END 가 둘인 덱 — 배터리 *INCLUDE 가 첫 *END 앞이다(예전엔 마지막 *END 앞이라 읽히지 않았다)",
                      ok, (rc, inc, first_end(L), text[-300:]))

        # 단독 op — 같은 규칙(첫 *END 앞에 한 번 · 없으면 끝에)
        cnrb_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "examples", "cnrb2solid", "bolt_simple.k")
        bolt = open(cnrb_src, encoding="utf-8").read()
        write(os.path.join(d, "bolt_one.k"), bolt)
        write(os.path.join(d, "bolt_two.k"), bolt.rstrip("\n") + "\n" + TAIL)
        write(os.path.join(d, "bolt_none.k"), "\n".join(l for l in bolt.splitlines() if l.strip().upper() != "*END") + "\n")
        solo = (
            ("database", "*DATABASE_BINARY_D3PLOT", "%s.k", lambda m, o: ("database", "model: %s\noutput: %s\npreset: drop\ndt: 0.0001\n"
                                                                         "dt_plot: 0.005\n" % (m, o))),
            ("hfdamp", "*DAMPING_FREQUENCY_RANGE", "%s.k", lambda m, o: ("hfdamp", "model: %s\noutput: %s\ndt_target: 3.0e-7\ncdamp: 0.99\n"
                                                                         "fhigh_ratio: 100.0\nmode: global\n" % (m, o))),
            ("contact-solo", "*CONTACT", "%s.k", lambda m, o: ("contact", "model: %s\noutput: %s\ncontacts:\n  - action: create\n"
                                                              "    type: automatic_single_surface\n    slave: { pid: 1 }\n" % (m, o))),
            ("cnrb2solid", "*CONTACT_TIED", "bolt_%s.k", lambda m, o: ("cnrb2solid", "model: %s\noutput: %s\nE: 200000.0\nPR: 0.3\n"
                                                                       "RHO: 7.85e-9\nradius_scale: 0.999\nnum_circum_nodes: 8\n"
                                                                       "inner_radius_ratio: 0.3\naxis_direction: auto\nz_tolerance: 0.1\n"
                                                                       "r_tolerance: 0.5\n" % (m, o))),
        )
        for name, prefix, model, mk in solo:
            print("[%s]" % name)
            counts = {}
            for deck in ("one", "two", "none"):
                out = "%s_%s_out.k" % (name, deck)
                op, body = mk(model % deck, out)
                write(os.path.join(d, "%s_%s.yaml" % (name, deck)), body)
                rc, text = run(binary, d, op, "%s_%s.yaml" % (name, deck))
                L = lines_of(os.path.join(d, out))
                counts[deck] = (rc, len(kw_rows(L, prefix)), all(i < first_end(L) for i in kw_rows(L, prefix)), text)
            rc1, n1, _, t1 = counts["one"]
            rc2, n2, before2, t2 = counts["two"]
            rc0, n0, _, t0 = counts["none"]
            check("%s-1 기준 — *END 하나인 덱에 %s 카드가 들어간다" % (name, prefix), rc1 == 0 and n1 > 0, (rc1, n1, t1[-300:]))
            check("%s-2 ★*END 가 둘인 덱 — %s 카드가 한 벌(%d)이고 다 첫 *END 앞이다" % (name, prefix, n1),
                  rc2 == 0 and n2 == n1 and before2, (rc2, n2, before2, t2[-300:]))
            check("%s-3 *END 가 없는 덱에도 %s 카드가 들어간다" % (name, prefix), rc0 == 0 and n0 == n1, (rc0, n0, t0[-300:]))

        # 단독 squeeze — 덧붙이는 카드(응력 dynain 의 *INCLUDE · 열팽창 · DR)는 첫 *END 앞에 한 벌(예전엔 *END 마다 — 2026-11-08 재검토)
        sq_cases = (
            ("squeeze-eps", "parts:\n  - pid: 1\n    eps_x: -0.01\n    eps_y: 0.0\n    eps_z: 0.0\nmaterial:\n  E: 210000.0\n  nu: 0.3\n"
                            "relax:\n  level: 2\n  mode: explicit\n  drterm: 0.0\n  endtime: 1.0\n  d3drlf: true\n",
             ("*INCLUDE", "*CONTROL_TERMINATION", "*CONTROL_DYNAMIC_RELAXATION", "*DATABASE_BINARY_D3DRLF")),
            ("squeeze-swell", "parts:\n  - pid: 1\n    swelling: 0.04\nrelax:\n  level: 2\n  mode: explicit\n  endtime: 1.0\n",
             ("*MAT_ADD_THERMAL_EXPANSION", "*INITIAL_TEMPERATURE_NODE", "*CONTROL_DYNAMIC_RELAXATION")),
        )
        for name, ycfg, kws in sq_cases:
            print("[%s]" % name)
            write(os.path.join(d, name + ".yaml"), ycfg)
            got = {}
            for deck in ("one", "two", "none"):
                out = "%s_%s_out.k" % (name, deck)
                rc, text = run(binary, d, "squeeze", deck + ".k", name + ".yaml", out)
                L = lines_of(os.path.join(d, out))
                rows = {k: kw_rows(L, k) for k in kws}
                ends = [i for i, l in enumerate(L) if l.upper().startswith("*END")]
                got[deck] = (rc, {k: len(v) for k, v in rows.items()}, all(i < first_end(L) for v in rows.values() for i in v), ends, text)
            rc1, n1, _, _, t1 = got["one"]
            rc2, n2, before2, ends2, t2 = got["two"]
            rc0, n0, before0, ends0, t0 = got["none"]
            check("%s-1 기준 — *END 하나인 덱에 덧붙임 %s 가 하나씩 들어간다" % (name, "/".join(kws)),
                  rc1 == 0 and all(v == 1 for v in n1.values()), (rc1, n1, t1[-300:]))
            check("%s-2 ★*END 가 둘인 덱 — 덧붙임이 한 벌이고 다 첫 *END 앞이다 · *END 둘이 그대로" % name,
                  rc2 == 0 and n2 == n1 and before2 and len(ends2) == 2, (rc2, n2, before2, ends2, t2[-300:]))
            check("%s-3 *END 가 없는 덱 — 덧붙임을 끝에 붙이고 *END 를 쓴다" % name,
                  rc0 == 0 and n0 == n1 and before0 and len(ends0) == 1, (rc0, n0, before0, ends0, t0[-300:]))

        # cnrb2solid — 첫 *END 뒤의 CNRB 는 읽히지 않는다: 바꾸지 않고(PNODE 도 그대로) 그 자리에 둔다(2026-11-08 재검토 TCN_dead)
        print("[cnrb2solid — 첫 *END 뒤의 죽은 CNRB]")

        def node_lines(Ls):
            """첫 *END 앞 *NODE 블록의 데이터 줄 수."""
            n, on = 0, False
            for l in Ls:
                if l.startswith("*"):
                    if l.upper().startswith("*END"):
                        break
                    on = l.upper().split()[0] == "*NODE"
                    continue
                if on and l.strip() and not l.lstrip().startswith("$"):
                    n += 1
            return n
        bl = bolt.splitlines()
        c0 = next(i for i, l in enumerate(bl) if l.upper().startswith("*CONSTRAINED_NODAL_RIGID_BODY"))
        c1 = next(i for i in range(c0 + 1, len(bl)) if bl[i].startswith("*"))
        cnrb_blk, rest = bl[c0:c1], bl[:c0] + bl[c1:]
        e0 = next(i for i, l in enumerate(rest) if l.upper().startswith("*END"))
        dead_only = rest[:e0 + 1] + cnrb_blk + ["*END"]
        live_dead = bl[:next(i for i, l in enumerate(bl) if l.upper().startswith("*END")) + 1] + \
            [cnrb_blk[0], cnrb_blk[1]] + [cnrb_blk[2].replace(cnrb_blk[2][:10], "%10d" % 777, 1)] + cnrb_blk[3:] + ["*END"]
        for tag, deck_lines, want_solids in (("dead", dead_only, 0), ("live_dead", live_dead, 1)):
            write(os.path.join(d, "cn_%s.k" % tag), "\n".join(deck_lines) + "\n")
            write(os.path.join(d, "cn_%s.yaml" % tag), "model: cn_%s.k\noutput: cn_%s_out.k\nE: 200000.0\nPR: 0.3\nRHO: 7.85e-9\n"
                                                         "radius_scale: 0.999\nnum_circum_nodes: 8\ninner_radius_ratio: 0.3\n"
                                                         "axis_direction: auto\nz_tolerance: 0.1\nr_tolerance: 0.5\n" % (tag, tag))
            rc, text = run(binary, d, "cnrb2solid", "cn_%s.yaml" % tag)
            L = lines_of(os.path.join(d, "cn_%s_out.k" % tag))
            fe = first_end(L)
            solids = [i for i in kw_rows(L, "*ELEMENT_SOLID") if i < fe]
            cn_after = [i for i in kw_rows(L, "*CONSTRAINED_NODAL_RIGID_BODY") if i > fe]
            src_nodes, out_nodes = node_lines(deck_lines), node_lines(L)
            if tag == "dead":
                check("cnrb2solid-dead ★첫 *END 뒤의 CNRB 만 있는 덱 — 바꾸지 않는다(솔리드 0 · PNODE 그대로 · CNRB 는 첫 *END 뒤에 그대로)",
                      rc == 0 and not solids and out_nodes == src_nodes and len(cn_after) == 1, (rc, solids, src_nodes, out_nodes, cn_after, text[-300:]))
            else:
                check("cnrb2solid-live_dead ★산 CNRB 만 바꾸고 첫 *END 뒤의 CNRB(PID 777)는 그 자리에 둔다",
                      rc == 0 and len(solids) == want_solids and len(cn_after) == 1 and "       777" in L[cn_after[0] + 2],
                      (rc, solids, cn_after, text[-300:]))

        # map(KFileWriter) — 첫 *END 뒤의 카드는 산출에서도 첫 *END 뒤에 남는다(읽히지 않던 것을 살리지 않는다)
        print("[map — 메시 쓰기(KFileWriter)]")
        run(binary, d, "generate", "arc", "--dim-i", "6", "--dim-j", "3", "--dim-k", "2", "g")
        flat = open(os.path.join(d, "g_flat.k"), encoding="utf-8").read()
        dead = "*COMMENT\n첫 *END 뒤 — 읽히지 않는다\n*PART\ndead part\n%10d%10d%10d\n*END\n" % (99, 1, 1)
        write(os.path.join(d, "flat_dead.k"), flat + dead)
        rc, text = run(binary, d, "map", "g_bent.k", "flat_dead.k", "map_out.k")
        L = lines_of(os.path.join(d, "map_out.k"))
        ends = [i for i, l in enumerate(L) if l.upper().startswith("*END")]
        dp = [i for i, l in enumerate(L) if l == "dead part"]
        check("map ★원본의 첫 *END 뒤 카드(죽은 *PART 99)가 산출에서도 첫 *END 뒤다 · *END 둘이 그대로",
              rc == 0 and len(ends) == 2 and len(dp) == 1 and dp[0] > ends[0], (rc, ends, dp, text[-300:]))

        # 들여쓴 「  *END」(*COMMENT 글 속) 는 끝이 아니다 — 1열 규칙(Vol_I 17940 · 리더와 같다). 덧붙임은 그 뒤 1열 *END 앞, 메시 쓰기는 *END 하나
        print("[들여쓴 *END — *COMMENT 글 속의 「  *END」 는 끝이 아니다]")
        cmt_end = "*COMMENT\n  *END\n*END\n"
        write(os.path.join(d, "ind_box.k"), box.replace("*END\n", "") + cmt_end)
        write(os.path.join(d, "ind_flat.k"), flat.replace("*END\n", "") + cmt_end)

        def ind_rows(L, prefixes):
            ind = [i for i, l in enumerate(L) if l == "  *END"]
            ends = [i for i, l in enumerate(L) if l.upper().startswith("*END")]
            rows = [i for p in prefixes for i in kw_rows(L, p)]
            return ind, ends, rows
        write(os.path.join(d, "ind_db.yaml"), "model: ind_box.k\noutput: ind_db_out.k\npreset: drop\ndt: 0.0001\ndt_plot: 0.005\n")
        rc, text = run(binary, d, "database", "ind_db.yaml")
        ind, ends, rows = ind_rows(lines_of(os.path.join(d, "ind_db_out.k")), ("*DATABASE_BINARY_D3PLOT",))
        check("indent-database ★*DATABASE 카드가 「  *END」 뒤 · 1열 *END 앞이다(예전엔 「  *END」 앞 — 그 줄이 넣은 블록의 데이터가 됐다)",
              rc == 0 and len(ind) == 1 and len(ends) == 1 and rows and all(ind[0] < i < ends[0] for i in rows), (rc, ind, ends, rows, text[-300:]))
        rc, text = run(binary, d, "map", "g_bent.k", "ind_flat.k", "ind_map_out.k")
        ind, ends, rows = ind_rows(lines_of(os.path.join(d, "ind_map_out.k")), ("*NODE", "*ELEMENT_SOLID"))
        check("indent-map ★메시 쓰기 — *END 하나 · 「  *END」 는 *COMMENT 글로 그대로(예전엔 거기서 *END 를 쓰고 원본 *END 를 또 베꼈다)",
              rc == 0 and len(ind) == 1 and len(ends) == 1 and ind[0] < ends[0] and rows and max(rows) < ind[0], (rc, ind, ends, rows, text[-300:]))
        rc, text = run(binary, d, "squeeze", "ind_box.k", "squeeze-eps.yaml", "ind_sq_out.k")
        ind, ends, rows = ind_rows(lines_of(os.path.join(d, "ind_sq_out.k")), ("*INCLUDE", "*CONTROL_DYNAMIC_RELAXATION"))
        check("indent-squeeze ★덧붙임이 「  *END」 뒤 · 1열 *END 앞 · *END 하나",
              rc == 0 and len(ind) == 1 and len(ends) == 1 and len(rows) == 2 and all(ind[0] < i < ends[0] for i in rows),
              (rc, ind, ends, rows, text[-300:]))

        # map prestress 훅 — 동반 덱의 *INCLUDE <dynain> 은 첫 *END 앞에 한 번(예전엔 *END 마다 — 2026-11-08 재검토)
        print("[map prestress 훅]")
        write(os.path.join(d, "flat_one.k"), flat)
        write(os.path.join(d, "flat_two.k"), flat + TAIL)
        write(os.path.join(d, "flat_none.k"), flat.replace("*END\n", ""))
        hook = {}
        for deck in ("one", "two", "none"):
            write(os.path.join(d, "mh_%s.yaml" % deck), "bent: g_bent.k\nflat: flat_%s.k\noutput: mh_%s.k\nprestress:\n  enabled: true\n"
                                                        "  output: mh_%s.dynain\n  E: 210000.0\n  nu: 0.3\n" % (deck, deck, deck))
            rc, text = run(binary, d, "map", "mh_%s.yaml" % deck)
            L = lines_of(os.path.join(d, "mh_%s.k" % deck))
            inc = kw_rows(L, "*INCLUDE")
            ends = [i for i, l in enumerate(L) if l.upper().startswith("*END")]
            hook[deck] = (rc, inc, ends, text)
        rc, inc, ends, text = hook["one"]
        check("map-hook-1 기준 — *END 하나인 덱에 *INCLUDE 하나가 첫 *END 앞이다", rc == 0 and len(inc) == 1 and ends and inc[0] < ends[0],
              (rc, inc, ends, text[-300:]))
        rc, inc, ends, text = hook["two"]
        check("map-hook-2 ★*END 가 둘인 덱 — *INCLUDE 가 한 번이고 첫 *END 앞이다 · *END 둘이 그대로",
              rc == 0 and len(inc) == 1 and len(ends) == 2 and inc[0] < ends[0], (rc, inc, ends, text[-300:]))
        rc, inc, ends, text = hook["none"]
        check("map-hook-3 *END 가 없는 덱 — *INCLUDE 를 끝에 붙이고 *END 를 쓴다",
              rc == 0 and len(inc) == 1 and len(ends) == 1 and inc[0] < ends[0], (rc, inc, ends, text[-300:]))
    finally:
        shutil.rmtree(d, ignore_errors=True)

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
