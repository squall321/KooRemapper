#!/usr/bin/env python3
"""`modelmeta` 재고 확장 — 질량·두께·고유절점·에지 길이와 **그 기준** (P1-7).

왜 이 시험이 있나 (2026-09-28):

  `parts[]` 에 `n_node`·`thickness`·`mass`·`mass_basis`·`edge_len` 이 **한 항목도 없었다**(추적
  489장 · 652 파트 전수 실측). 셸 파트의 `volume` 은 **50/50 전부 0** 이고, plan2 가
  "**mass 를 0 이나 어림값으로 채우지 마라**" 를 명시로 금지한 이유가 그 전례다.

이 시험이 지키는 계약 넷.

  ① **기존 10키 값 불변.** 하류 파서(DataHub 업로더·HEAXHub)가 첨자로 읽는다. 새 키만 더한다.
     (전수 증명은 별도로 했다 — 옛/새 바이너리로 489장을 키별 대조, 달라짐 0.)
  ② **`mass` 는 0 으로 채우지 않는다.** 유도할 수 없으면 `null` 과 **이유**를 낸다.
  ③ **TSHELL 은 두께를 내지 않는다.** `*SECTION_TSHELL` 에 두께 칸이 **없다** — 그 자리를
     따라가면 이 리포가 만든 골든에서 다음 섹션 세트의 Card 1 을 두께로 읽는다.
  ④ **`conventions` 가 기준을 적는다.** 같은 파일을 두고 `info` 와 `modelmeta` 가 파트 수를
     다르게 말하던 것이 **정의 차이**였다 — 값이 아니라 기준을 적어야 닫힌다.

⚠ BEAM/DISCRETE/SEATBELT 는 **세지 않는다.** plan2 가 그것을 요구했지만 추적 489장 + 실사용
1,303장 **전수에서 0장**이다(같은 grep 하네스가 `*ELEMENT_SHELL` 551장을 찾는 양성 대조로
반증했다). 덱이 없는 카드 배치를 구현하면 검증할 수 없는 코드가 된다.

usage: test_modelmeta_inventory.py <KooRemapper 바이너리>
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))

OLD_PART_KEYS = ["pid", "title", "elem_class", "n_elems", "bbox_min", "bbox_max",
                 "area_ext", "volume", "proj", "material"]
NEW_PART_KEYS = ["n_node", "thickness", "thickness_reason", "mass", "mass_basis",
                 "mass_reason", "edge_len"]


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:400]) if detail else ""))


def run(binary, deck_rel):
    d = tempfile.mkdtemp(prefix="mmi_")
    shutil.copy(os.path.join(REPO, deck_rel), d)
    b = os.path.basename(deck_rel)
    open(os.path.join(d, "cfg.yaml"), "w").write("model: %s\ndetect: false\n" % b)
    p = subprocess.run([binary, "modelmeta", "cfg.yaml"], capture_output=True, text=True,
                       timeout=900, cwd=d)
    j = glob.glob(os.path.join(d, "*_modelmeta.json"))
    out = json.load(open(j[0], encoding="utf-8")) if j else None
    shutil.rmtree(d, ignore_errors=True)
    return p.returncode, out


# 두 갈래를 **관찰 가능하게** 만드는 합성 덱. 리포 예제로는 닿지 않는다.
#   · pid 1 — 솔리드인데 SECID 1 을 `*SECTION_SHELL`(T1=2.0)과 **공유**한다. SECID 네임스페이스는
#     섹션 종류끼리 공유되므로 이것은 합법인 덱이다. 두께 조회에 `elem_class` 빗장이 없으면
#     솔리드 파트에 2.0 이 붙는다.
#   · pid 2 — 부피 0(축퇴 요소)인데 **밀도를 안다**. 부피 빗장이 없으면 `mass: 0.0` 이 나간다.
PROBE = """*KEYWORD
*PART
solid sharing SECID 1 with a shell section
         1         1         1
*PART
zero-volume cohesive with known rho
         2         2         1
*SECTION_SHELL
         1         2       1.0         2
       2.0       2.0       2.0       2.0
*SECTION_SOLID
         2        20
*MAT_ELASTIC
         1 7.850E-09 2.100E+05       0.3
*NODE
       1     0.0     0.0     0.0
       2     1.0     0.0     0.0
       3     1.0     1.0     0.0
       4     0.0     1.0     0.0
       5     0.0     0.0     1.0
       6     1.0     0.0     1.0
       7     1.0     1.0     1.0
       8     0.0     1.0     1.0
*ELEMENT_SOLID
       1       1       1       2       3       4       5       6       7       8
       2       2       1       2       3       4       1       2       3       4
*END
"""


def run_text(binary, text):
    d = tempfile.mkdtemp(prefix="mmi_")
    open(os.path.join(d, "probe.k"), "w", newline="\n").write(text)
    open(os.path.join(d, "cfg.yaml"), "w").write("model: probe.k\ndetect: false\n")
    p = subprocess.run([binary, "modelmeta", "cfg.yaml"], capture_output=True, text=True,
                       timeout=900, cwd=d)
    j = glob.glob(os.path.join(d, "*_modelmeta.json"))
    out = json.load(open(j[0], encoding="utf-8")) if j else None
    shutil.rmtree(d, ignore_errors=True)
    return p.returncode, out


def main():
    if len(sys.argv) < 2:
        print("usage: test_modelmeta_inventory.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2

    SHELL = "examples/offset/04_shell_result.k"       # 셸 파트 + *SECTION_SHELL T1=0.8
    TSHELL = "examples/replace_test/tshell_base.k"    # TSHELL 파트(기하상 solid)
    BLOCK = "examples/indent/small/block.k"           # 평범한 솔리드
    CZM = "examples/offset/06_czm_result.k"           # 제로두께 코히시브 → 부피 0

    print("[A 키가 다 있고 기존 키가 남아 있다]")
    rc, d = run(binary, BLOCK)
    check("A-1 rc=0", rc == 0)
    if d:
        p = d["parts"][0]
        check("A-2 기존 10키가 그대로 있다", all(k in p for k in OLD_PART_KEYS),
              "없는 키=%r" % [k for k in OLD_PART_KEYS if k not in p])
        check("A-3 새 키 7개가 있다", all(k in p for k in NEW_PART_KEYS),
              "없는 키=%r" % [k for k in NEW_PART_KEYS if k not in p])
        check("A-4 최상위는 4키 그대로(새 키를 위에 넣지 않았다)",
              set(d) == {"model", "conventions", "parts", "connectivity"}, sorted(d))
    else:
        check("A 산출물", False)

    print("[B 고유 절점 수 — n_elems*8 이 아니다]")
    if d:
        p = d["parts"][0]
        check("B-1 n_node 가 요소당 8 보다 작다(절점을 공유한다)",
              0 < p["n_node"] < p["n_elems"] * 8, "n_node=%r n_elems=%r" % (p["n_node"], p["n_elems"]))

    print("[C 질량 — 0 으로 채우지 않는다]")
    rc, d = run(binary, SHELL)
    if d:
        sh = [p for p in d["parts"] if p["elem_class"] == "shell"]
        check("C-1 셸 파트가 있다", bool(sh), [p["elem_class"] for p in d["parts"]])
        if sh:
            p = sh[0]
            check("C-2 셸 두께를 *SECTION_SHELL 에서 찾는다", p["thickness"] is not None,
                  "thickness_reason=%r" % p.get("thickness_reason"))
            check("C-3 질량 기준이 area*t*rho 다", p["mass_basis"] == "area*t*rho", p.get("mass_basis"))
            check("C-4 질량이 0 이 아니다", p["mass"] and p["mass"] > 0, p.get("mass"))
        # 유도 못 한 파트는 null + 이유
        nm = [p for p in d["parts"] if p["mass"] is None]
        check("C-5 유도 못 한 질량은 null 이고 이유가 붙는다",
              all(p["mass_reason"] for p in nm), [p.get("mass_reason") for p in nm])
        check("C-6 질량이 0.0 인 파트가 없다(0 으로 채우지 않는다)",
              not [p for p in d["parts"] if p["mass"] == 0], [p["pid"] for p in d["parts"] if p["mass"] == 0])

    print("[D TSHELL 은 두께를 내지 않는다]")
    rc, d = run(binary, TSHELL)
    if d:
        # ⚠ TSHELL 요소는 육면체라 `elem_class` 가 solid 다 — 그것이 기하 기준이고
        # `conventions.elem_class` 에 적혀 있다. 두께는 그래서 null 이다.
        solids = [p for p in d["parts"] if p["elem_class"] == "solid"]
        check("D-1 TSHELL 파트는 두께가 null 이다", all(p["thickness"] is None for p in solids),
              [(p["pid"], p["thickness"]) for p in solids])
        check("D-2 그 이유를 말한다", all(p["thickness_reason"] for p in solids),
              [p.get("thickness_reason") for p in solids])

    print("[E 제로두께 코히시브 — 부피 0 이면 질량을 만들지 않는다]")
    rc, d = run(binary, CZM)
    if d:
        z = [p for p in d["parts"] if p["volume"] == 0 and p["elem_class"] == "solid"]
        check("E-1 부피 0 인 솔리드 파트가 있다(코히시브)", bool(z), [p["pid"] for p in d["parts"]])
        if z:
            check("E-2 그 파트의 질량은 null 이다", all(p["mass"] is None for p in z),
                  [(p["pid"], p["mass"]) for p in z])

    print("[F conventions 가 기준을 적는다]")
    rc, d = run(binary, BLOCK)
    if d:
        c = d["conventions"]
        for k in ("parts_basis", "bbox", "elem_class", "n_node", "thickness", "mass",
                  "edge_len", "element_kinds"):
            check("F %s 기준이 적혀 있다" % k, k in c and len(c[k]) > 10, c.get(k))
        check("F-9 element_kinds 가 '왜 세지 않는가' 를 적는다",
              "0장" in c.get("element_kinds", ""), c.get("element_kinds"))
        check("F-10 parts_basis 가 info 와의 차이를 적는다",
              "info" in c.get("parts_basis", ""), c.get("parts_basis"))

    print("[G 에지 길이]")
    if d:
        p = d["parts"][0]
        e = p["edge_len"]
        check("G-1 edge_len 이 세 값을 낸다", e and {"min", "p50", "max"} <= set(e), e)
        if e:
            check("G-2 min <= p50 <= max", e["min"] <= e["p50"] <= e["max"], e)
            check("G-3 min 이 0 보다 크다(축퇴 에지를 뺐다)", e["min"] > 0, e)

    print("[H 두 빗장 — 리포 예제로는 닿지 않는 갈래]")
    rc, d = run_text(binary, PROBE)
    check("H-1 rc=0", rc == 0)
    if d:
        by = {p["pid"]: p for p in d["parts"]}
        # SECID 를 셸 섹션과 공유하는 **솔리드** 파트에 두께가 붙으면 안 된다.
        check("H-2 솔리드가 셸 섹션과 SECID 를 공유해도 두께는 null",
              by.get(1, {}).get("thickness") is None,
              "pid1.thickness=%r" % by.get(1, {}).get("thickness"))
        # 부피 0 인데 밀도를 아는 파트 — `0.0` 이 아니라 null + 이유여야 한다.
        p2 = by.get(2, {})
        check("H-3 부피 0 이면 밀도를 알아도 질량은 null", p2.get("mass") is None,
              "pid2.mass=%r" % p2.get("mass"))
        check("H-4 그 이유가 부피를 말한다", "부피" in (p2.get("mass_reason") or ""),
              p2.get("mass_reason"))

    print()
    if FAILS:
        print("--- 실패 %d건 ---" % len(FAILS))
        for f in FAILS:
            print("  " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
