#!/usr/bin/env python3
# 열 재질(*MAT_THERMAL_* · 번호 이름 *MAT_T01~T18)의 TMID 를 모든 재질 훑기가 구조 MID 와 다른 번호 공간으로 보는지 보는 회귀 시험
"""열 재질 번호 이름(`*MAT_T01`~`*MAT_T18`)은 구조 재질이 아니다.

왜 이 시험이 있나 (2026-11-08).

  Vol II *MAT_THERMAL — 열 재질 번호(TMID)는 다른 *MAT_ 카드의 MID 와 독립이고 같은 수가 있어도 된다. 11-07 밤에 공용 MID 커서가
  번호 이름도 빼게 되었는데(c50e54c) 다른 훑기는 여전히 `*MAT_THERMAL_` 만 뺐다 — 적대적 검토(11-08 #3)가 어긋남을 찾았다:
  상자(MID 1) + `*MAT_T01 2` 에 assemble offset(재질 카드)을 돌리면 커서는 맞게 `*MAT_ELASTIC 2` 를 내는데 `info --strict` 가 같은
  번호의 겹침(망가진 카드)이라 했고, 거꾸로 구조 재질이 없는 `*PART` MID 2 를 `*MAT_T01 2` 덕에 「정의됨」 으로 지나보냈다(참조 쪽은
  `*MAT_ADD_` 만 빼서 이름 꼴 `*MAT_THERMAL_*` 도 같았다 — 재질 카드 없는 offset 이 쓰는 빈 MID 를 TMID 가 가렸다).
  matdb 는 `*MAT_T01` 을 재질 블록으로 보아 구조 재질 카드로 바꿔 쓰고(같은 MID 둘) 열 카드를 두 벌 넣었고, merge 는 그 Card 1
  (TMID TRO TGRLC …)을 MID RO E 로 읽어 E 를 TGRLC(99)로 덮었고, hfdamp 는 그 카드로 RO · E 를 덮어 시간 간격을 못 쟀고, 조각 넣기는
  그 키워드를 계약 안으로 받았다. 이제 모두 한 판정(`cards::isThermalMaterialKeyword`)을 쓴다.

무엇을 보나.
  A info --strict 겹침 — `*MAT_ELASTIC 2` + `*MAT_T01 2` 는 겹침이 아니다
  B info --strict 참조 — `*PART` MID 2 를 `*MAT_T01 2` 도 `*MAT_THERMAL_ISOTROPIC 2` 도 정의하지 않는다(미정의 — 이름 꼴도 예전엔
    정의로 셌다. Vol I *PART 비고 7: MID 는 *MAT 의, TMID 는 *MAT_THERMAL 의 번호다)
  C assemble offset(재질 카드) 산출이 --strict 를 지난다(검토자의 재현)
  D matdb — `*MAT_T01` 은 재질 블록이 아니다(구조 MID 1 카드가 하나 · thermal 이면 열 카드도 한 벌)
  E merge — `*MAT_T01` Card 1 을 재질로 읽지 않는다(MID 1 의 E 210000 그대로)
  F hfdamp — `*MAT_T01` 을 재질로 읽지 않는다(selective 가 강철 파트를 고른다)
  G cad_solid_merge_to_deck — 조각의 `*MAT_T01` 은 계약 밖이다

usage: test_thermal_mat_ids.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS, OKS = [], []
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
OFFSET = """base_model: box.k
output: out
operations:
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


def t01(tmid, tgrlc="0.0"):
    """*MAT_T01(= *MAT_THERMAL_ISOTROPIC) — Card 1 TMID TRO TGRLC TGMULT · Card 2 HC TC."""
    return "*MAT_T01\n%10d       0.0%10s       0.0\n       1.0       1.0\n" % (tmid, tgrlc)


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:500]))
    print("  %-70s %s" % (name[:70], "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def box(binary, d, before_end="", edit=None):
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    assert rc == 0, out[-400:]
    p = os.path.join(d, "box.k")
    body = open(p, encoding="utf-8").read()
    if edit:
        body = edit(body)
    open(p, "w", encoding="utf-8").write(body.replace("*END", before_end + "*END"))


def keywords(path, prefix):
    if not os.path.exists(path):
        return []
    return [l.strip() for l in open(path, encoding="utf-8").read().split("\n") if l.upper().startswith(prefix)]


def fresh(tmp, name):
    d = os.path.join(tmp, name)
    os.makedirs(d)
    return d


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    tmp = tempfile.mkdtemp(prefix="thermal_ids_")
    try:
        print("[A · B info --strict — 열 재질 TMID 는 구조 MID 와 다른 번호 공간]")
        d = fresh(tmp, "a")
        box(binary, d, "*MAT_ELASTIC\n         2   7.85E-9    210000       0.3\n" + t01(2))
        rc, out = run(binary, d, "info", "--strict", "box.k")
        check("A-1 *MAT_ELASTIC 2 + *MAT_T01 2 — 겹침(망가진 카드)이 아니다(--strict rc 0)", rc == 0 and "망가진 카드" not in out, out[-300:])
        d = fresh(tmp, "b")
        box(binary, d, t01(2), edit=lambda b: b.replace("         1         1         1\n", "         1         1         2\n", 1))
        rc, out = run(binary, d, "info", "--strict", "box.k")
        check("B-1 *PART MID 2 · 구조 재질 없이 *MAT_T01 2 뿐 — 재질 2 가 정의되지 않았다(--strict rc 1)",
              rc == 1 and "재질 2" in out, out[-300:])
        d = fresh(tmp, "b2")
        box(binary, d, t01(2).replace("*MAT_T01", "*MAT_THERMAL_ISOTROPIC"),
            edit=lambda b: b.replace("         1         1         1\n", "         1         1         2\n", 1))
        rc, out = run(binary, d, "info", "--strict", "box.k")
        check("B-2 이름 꼴 *MAT_THERMAL_ISOTROPIC 2 도 *PART MID 2 를 정의하지 않는다(Vol I *PART 비고 7 — MID 는 *MAT · TMID 는 *MAT_THERMAL)",
              rc == 1 and "재질 2" in out, out[-300:])

        print("[C assemble offset(재질 카드) — 검토자의 재현 · 산출이 --strict 를 지난다]")
        d = fresh(tmp, "c")
        box(binary, d, t01(2))
        open(os.path.join(d, "off.yaml"), "w").write(OFFSET)
        rc, out = run(binary, d, "assemble", "off.yaml")
        rc2, out2 = run(binary, d, "info", "--strict", "out.k") if rc == 0 else (None, out)
        check("C-1 새 재질은 *MAT_ELASTIC 2(TMID 2 와 같은 수 — Vol II 가 허락한다) · --strict rc 0",
              rc == 0 and rc2 == 0 and "망가진 카드" not in out2, (rc, rc2, out2[-300:]))

        print("[D matdb — *MAT_T01 은 재질 블록이 아니다]")
        for tag, extra in (("d", ""), ("d2", "thermal: true\n")):
            d = fresh(tmp, tag)
            box(binary, d, t01(1))
            os.makedirs(os.path.join(d, "materials"))
            shutil.copy(os.path.join(REPO, "materials", "material_db.json"), os.path.join(d, "materials"))
            open(os.path.join(d, "m.yaml"), "w").write("model: box.k\noutput: o.k\nmat_type: MAT_ELASTIC\n" + extra +
                                                      "materials:\n  - mid: 1\n    match: \"SUS304\"\n")
            rc, out = run(binary, d, "matdb", "m.yaml")
            o = os.path.join(d, "o.k")
            el, th = keywords(o, "*MAT_ELASTIC"), [k for k in keywords(o, "*MAT_") if k.upper().startswith(("*MAT_THERMAL_", "*MAT_T0", "*MAT_T1"))]
            if tag == "d":
                check("D-1 matdb — 구조 재질 카드가 한 장(예전엔 *MAT_T01 을 재질로 바꿔 써 MID 1 이 둘)", rc == 0 and len(el) == 1, (rc, el, out[-300:]))
            else:
                check("D-2 matdb thermal — 구조 · 열 카드가 한 벌씩(예전엔 둘씩)", rc == 0 and len(el) == 1 and len(th) == 1, (rc, el, th))

        print("[E merge — *MAT_T01 의 Card 1 을 재질로 읽지 않는다]")
        d = fresh(tmp, "e")
        src = open(os.path.join(REPO, "examples", "merge", "three_layer.k"), encoding="utf-8").read()
        open(os.path.join(d, "base.k"), "w", encoding="utf-8").write(src.replace("*END", t01(1, "99.0") + "*END"))
        open(os.path.join(d, "a.yaml"), "w").write("base_model: base.k\noutput: out\noperations:\n  - type: merge\n    direction: z\n"
                                                  "    method: voigt\n    target_pids: [1, 3]\n")
        rc, out = run(binary, d, "assemble", "a.yaml")
        check("E-1 merge — MID 1 은 *MAT_ELASTIC(E 210000) 그대로 · *MAT_T01 은 건너뛴다(예전엔 E 99 로 덮었다)",
              rc == 0 and "MID 1 (GENERIC)" not in out and "SKIP: *MAT_T01" in out, out[-500:])

        print("[F hfdamp — *MAT_T01 을 재질로 읽지 않는다]")
        d = fresh(tmp, "f")
        box(binary, d, t01(1))
        open(os.path.join(d, "hf.yaml"), "w").write("model: box.k\noutput: o.k\ndt_target: 3.0e-7\ncdamp: 0.99\nfhigh_ratio: 100.0\n"
                                                   "mode: selective\n")
        rc, out = run(binary, d, "hfdamp", "hf.yaml")
        check("F-1 hfdamp selective — 강철 파트를 고른다(예전엔 *MAT_T01 의 TRO 0 · TGRLC 0 으로 MID 1 의 RO · E 를 덮어 시간 간격을 못 쟀다)",
              rc == 0 and "1 part(s) targeted" in out, out[-300:])

        print("[G cad_solid_merge_to_deck — 조각의 *MAT_T01 은 계약 밖]")
        d = fresh(tmp, "g")
        ex = os.path.join(REPO, "examples", "cad_solid_merge_to_deck")
        for f in ("deck.k", "stepforge_fragment.k", "stepforge_fragment.json"):
            shutil.copy(os.path.join(ex, f), d)
        fp = os.path.join(d, "stepforge_fragment.k")
        fr = open(fp, encoding="utf-8").read()
        open(fp, "w", encoding="utf-8").write(fr.replace("*END", t01(901) + "*END"))
        open(os.path.join(d, "m.yaml"), "w").write("model: deck.k\noutput: merged.k\nfragment: stepforge_fragment.k\n"
                                                  "fragment_map: stepforge_fragment.json\n")
        rc, out = run(binary, d, "cad_solid_merge_to_deck", "m.yaml")
        check("G-1 조각에 *MAT_T01 — 계약(§3-3) 밖 키워드로 거절(rc 1 · 산출 없음)",
              rc == 1 and "*MAT_T01" in out and not os.path.exists(os.path.join(d, "merged.k")), out[-300:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
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
