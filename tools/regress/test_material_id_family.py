#!/usr/bin/env python3
# 재질 번호(MID) 가족 — 쌓인 재질 묶음 · 열 재질 TMID · 덧붙임 카드를 새 MID 를 내는 op 마다 같은 셈으로 다루는지 보는 회귀 시험
"""재질 번호(MID)를 세는 · 지우는 · 베끼는 훑기가 한 규칙(`parser/MaterialIds.h`)을 쓰는지 본다.

왜 이 시험이 있나 (2026-11-08 · 사용자 결정 「이번 판에 다 고친다」).

  MID 를 다루는 자리가 op 마다 따로 있었다 — 공용 커서(ModelAssembler) · matswap(단독 · assemble) · cclip · ale · cnrb2solid ·
  cnrb2spring · matdb match_part. 저마다 `*MAT` 블록의 첫 카드 첫 칸을 MID 로 보아
    · 한 키워드 아래 쌓인 재질(매뉴얼 Card Sets)의 둘째 MID 를 못 보고 새 재질이 그 번호를 다시 냈고(같은 MID 둘),
    · 열 재질 `*MAT_T01` 의 TMID(다른 번호 공간)로 커서를 올렸고(TMID 50 → 새 MID 51),
    · cnrb2spring 의 고정 번호대 검사는 TMID 를 MID 로 보아 거짓 겹침으로 거절하고 쌓인 MID 와의 진짜 겹침은 놓쳤다.
  assemble 의 matswap 은 앞 op(offset)이 덧붙인 재질 · 섹션 번호를 못 보고 같은 MID 2 · SECID 2 를 또 냈다.

무엇을 보나.
  G 공용 커서 — 쌓인 묶음(알려진 꼴은 묶음마다 · 모르는 꼴은 행마다 첫 칸 숫자)을 세어 새 MID 가 겹치지 않는다
  D MID 를 내는 op 마다 같은 셈 — 열 재질 TMID 로 커서를 올리지 않고 쌓인 MID 를 다시 내지 않는다
  A matswap(단독 · assemble) — 옛 MID 의 구조 재질 정의만 지운다(같은 번호 TMID 의 열 재질 · PID 꼴 덧붙임 · 쌓인 다른 재질은 둔다 ·
    MID 꼴 덧붙임은 번호를 다시 쓰면 두고 재질이 사라지면 지운다 · 지운 뒤에도 쓰이는 번호는 다시 주지 않는다)
  B cclip — 같은 규칙(클립은 새 MID 를 받아 옛 재질이 사라진다 — MID 꼴 덧붙임도 지운다)

usage: test_material_id_family.py <KooRemapper 바이너리>
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

FAILS, OKS = [], []
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 4\nny: 2\nnz: 1\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\nmid: 1\nsecid: 1\npid: 1\n"
       "part_title: PLATE\n")
OFFSET = ("base_model: box.k\noutput: out\noperations:\n  - type: offset\n    source_pid: 1\n    element_type: solid\n    thickness: 1.0\n"
          "    num_layers: 1\n    offset_direction: +z\n    connection_mode: tied\n    new_pid: 10\n    material_card: |\n      *MAT_ELASTIC\n"
          "      $#     mid        ro         e        pr\n           @MID@  7.85E-09  2.10E+05       0.3\n")
EL = "%10d   7.85E-9    210000       0.3\n"
T01 = "*MAT_T01\n%10d       0.0       0.0       0.0\n       1.0       1.0\n"
STACK = "*MAT_ELASTIC\n" + EL % 2 + EL % 3                    # 한 키워드 아래 MID 2 · 3
SECOND = "*PART\nSECOND\n         2         1         1\n"    # PID 2 가 MID 1 을 나눠 쓴다(요소 없음) — matswap 이 새 MID 를 낸다


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:500]))
    print("  %-70s %s" % (name[:70], "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def fresh(tmp, name):
    d = os.path.join(tmp, name)
    os.makedirs(d)
    return d


def box(binary, d, extra="", name="box.k", yaml=BOX):
    open(os.path.join(d, "box.yaml"), "w").write(yaml.replace("output: box.k", "output: " + name))
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    assert rc == 0, out[-400:]
    p = os.path.join(d, name)
    body = open(p, encoding="utf-8").read()
    open(p, "w", encoding="utf-8").write(body.replace("*END", extra + "*END"))


def card1_mids(path, kw_prefix="*MAT_"):
    """구조 재질 블록마다 (키워드, 첫 카드 MID) — 시험이 따로 센다(제목 줄 · 주석 건넘)."""
    if not os.path.exists(path):
        return []
    L = open(path, encoding="utf-8").read().split("\n")
    out = []
    for i, l in enumerate(L):
        u = l.strip().upper()
        if not u.startswith(kw_prefix) or u.startswith("*MAT_ADD_") or u.startswith("*MAT_THERMAL_") or re.match(r"\*MAT_T\d\d", u):
            continue
        j, title = i + 1, u.endswith("_TITLE")
        while j < len(L) and (L[j].startswith("$") or (not L[j].strip() and not title)):
            j += 1
        if title:
            j += 1
            while j < len(L) and L[j].startswith("$"):
                j += 1
        if j < len(L) and L[j][:10].strip().isdigit():
            out.append((u.split()[0], int(L[j][:10])))
    return out


def elastic_rows(path):
    """`*MAT_ELASTIC` 블록의 데이터 줄 첫 칸(한 묶음 한 줄 — 이 시험의 덱은 E > 0 · 제목 없음) — 같은 MID 가 둘이면 겹침."""
    L = open(path, encoding="utf-8").read().split("\n") if os.path.exists(path) else []
    out, on = [], False
    for l in L:
        if l.startswith("*"):
            on = l.strip().upper() == "*MAT_ELASTIC"
            continue
        if on and l.strip() and not l.startswith("$") and l[:10].strip().isdigit():
            out.append(int(l[:10]))
    return out


def offset_new_mid(out):
    m = re.search(r"New IDs: PID=\d+, SECID=\d+, MID=(\d+)", out)
    return int(m.group(1)) if m else None


def part_g(binary, tmp):
    print("[G 공용 커서 — 쌓인 재질 묶음(Card Sets)을 센다]")
    cases = [
        ("G-1 *MAT_ELASTIC 아래 MID 2 · 3 — 새 MID 4(예전 3 — 쌓인 3 과 겹쳤다)", STACK, 4),
        ("G-2 *MAT_ELASTIC_TITLE 묶음마다 제목 — 새 MID 4", "*MAT_ELASTIC_TITLE\nA\n" + EL % 2 + "B\n" + EL % 3, 4),
        ("G-3 E < 0 이면 Card 1.1(EFUNC 12)이 온다 — MID 로 읽지 않는다 · 새 MID 4(13 이 아니다)",
         "*MAT_ELASTIC\n         2   7.85E-9      -1.0       0.3\n        12         0         0\n" + EL % 3, 4),
        ("G-4 *MAT_RIGID 묶음 셋 줄(빈 Card 2 · 3 도 카드) — 새 MID 4",
         "*MAT_RIGID\n" + EL % 2 + "         1         7         7\n\n" + EL % 3 + "\n\n", 4),
        ("G-5 행 수를 모르는 꼴(*MAT_ORTHOTROPIC_ELASTIC) — 행마다 첫 칸 숫자를 넉넉히 · 새 MID 5",
         "*MAT_ORTHOTROPIC_ELASTIC\n"
         + "".join("%10d   7.85E-9    1000.0    1000.0    1000.0       0.3       0.3       0.3\n" % m +
                   "     500.0     500.0     500.0       0.0\n       0.0       0.0       0.0       1.0       0.0       0.0\n"
                   "       0.0       1.0       0.0       0.0\n" for m in (3, 4)), 5),
    ]
    for k, (name, extra, want) in enumerate(cases):
        d = fresh(tmp, "g%d" % k)
        box(binary, d, extra)
        open(os.path.join(d, "off.yaml"), "w").write(OFFSET)
        rc, out = run(binary, d, "assemble", "off.yaml")
        got = offset_new_mid(out)
        mids = [m for _kw, m in card1_mids(os.path.join(d, "out.k"))]
        check(name, rc == 0 and got == want, (rc, got, mids, out[-300:]))
    d = fresh(tmp, "g6")
    box(binary, d, STACK)
    open(os.path.join(d, "fl.yaml"), "w").write("model: box.k\noutput: fl.json\n")
    rc, out = run(binary, d, "id_floor", "fl.yaml")
    fl = json.load(open(os.path.join(d, "fl.json"))) if os.path.exists(os.path.join(d, "fl.json")) else {}
    check("G-6 id_floor pid_start 4 — 쌓인 MID 3 위(예전 3)", rc == 0 and fl.get("pid_start") == 4, (rc, fl, out[-300:]))


def part_d(binary, tmp):
    print("[D MID 를 내는 op 마다 같은 셈 — 열 재질 TMID · 쌓인 묶음]")
    shutil_bundle = os.path.join(REPO, "examples", "matswap", "rubber.k")
    for tag, extra, want, why in (("t01", SECOND + T01 % 50, 2, "TMID 50 은 MID 가 아니다(예전 51)"),
                                  ("stack", SECOND + STACK, 4, "쌓인 MID 3 위(예전 3 — 겹쳤다)")):
        d = fresh(tmp, "d1" + tag)
        box(binary, d, extra)
        shutil.copy(shutil_bundle, d)
        open(os.path.join(d, "s.yaml"), "w").write("model: box.k\noutput: o.k\nswaps:\n  - bundle: rubber.k\n    pid: 1\n")
        rc, out = run(binary, d, "matswap", "s.yaml")
        m = re.search(r"&MID1 \(MID\) 1 -> (\d+)", out)
        check("D-1%s matswap(단독) 새 MID %d — %s" % (tag[0], want, why), rc == 0 and m and int(m.group(1)) == want,
              (rc, m.group(0) if m else None, out[-300:]))

    d = fresh(tmp, "d2")
    box(binary, d, SECOND)
    shutil.copy(shutil_bundle, d)
    open(os.path.join(d, "a.yaml"), "w").write(OFFSET.replace("operations:\n", "operations:\n", 1) +
                                               "  - type: matswap\n    pid: 1\n    bundle: rubber.k\n")
    rc, out = run(binary, d, "assemble", "a.yaml")
    m = re.search(r"Updated PID 1 -> SECID=(\d+) MID=(\d+)", out)
    rc2, out2 = run(binary, d, "info", "--strict", "out.k") if rc == 0 else (None, "")
    check("D-2 assemble offset 뒤 matswap — 앞 op 이 낸 MID 2 · SECID 2 를 다시 내지 않는다(SECID 3 · MID 3 · --strict rc 0)",
          rc == 0 and m and (int(m.group(1)), int(m.group(2))) == (3, 3) and rc2 == 0, (rc, m.group(0) if m else None, rc2, out2[-200:]))

    board = ("output: clip_board.k\nlx: 3.0\nly: 1.5\nlz: 0.5\nnx: 6\nny: 3\nnz: 1\nrho: 8.36e-9\nE: 131000.0\nnu: 0.3\nmid: 2\nsecid: 2\n"
             "pid: 2\npart_title: CCLIP_ANT_01\n")
    cyaml = ("model: clip_board.k\noutput: clip_board_cclip\nmode: analytic\nattach: none\nstress_output: embed\nfree_output: true\n"
             "calibration:\n  point: {deflection: 0.15, force: 1.2}\n  tolerance: 0.05\nclips:\n  - pid: 2\n    overtravel: 0.15\n")
    for tag, extra, want, why in (("t01", T01 % 50, 3, "TMID 50 은 MID 가 아니다(예전 51)"),
                                  ("stack", "*MAT_ELASTIC\n" + EL % 3 + EL % 4, 5, "쌓인 MID 4 위(예전 4 — 겹쳤다)")):
        d = fresh(tmp, "d3" + tag)
        box(binary, d, extra, name="clip_board.k", yaml=board)
        open(os.path.join(d, "c.yaml"), "w").write(cyaml)
        rc, out = run(binary, d, "cclip", "c.yaml")
        got = [m for kw, m in card1_mids(os.path.join(d, "clip_board_cclip.k")) if kw.startswith("*MAT_ELASTIC_TITLE")]
        check("D-3%s cclip 새 MID %d — %s" % (tag[0], want, why), rc == 0 and got == [want], (rc, got, out[-300:]))

    for tag, extra, want, why in (("t01", T01 % 50, 2, "TMID 50 은 MID 가 아니다(예전 51)"),
                                  ("stack", STACK, 4, "쌓인 MID 3 위(예전 3 — 겹쳤다)")):
        d = fresh(tmp, "d4" + tag)
        box(binary, d, extra)
        open(os.path.join(d, "a.yaml"), "w").write("model: box.k\noutput: o.k\nale_parts:\n  - pid: 1\n    material: air\n")
        rc, out = run(binary, d, "ale", "a.yaml")
        got = [m for kw, m in card1_mids(os.path.join(d, "o.k")) if kw.startswith("*MAT_NULL")]
        check("D-4%s ale 새 MID %d — %s" % (tag[0], want, why), rc == 0 and got == [want], (rc, got, out[-300:]))

    d = fresh(tmp, "d5")
    src = open(os.path.join(REPO, "examples", "cnrb2solid", "bolt_simple.k"), encoding="utf-8").read()
    open(os.path.join(d, "bolt.k"), "w", encoding="utf-8").write(src.replace("*END", T01 % 500 + "*END", 1))
    open(os.path.join(d, "c.yaml"), "w").write("model: bolt.k\noutput: o.k\nE: 200000.0\nPR: 0.3\nRHO: 7.85e-9\nradius_scale: 0.999\n"
                                               "num_circum_nodes: 8\ninner_radius_ratio: 0.3\naxis_direction: auto\nz_tolerance: 0.1\n"
                                               "r_tolerance: 0.5\n")
    rc, out = run(binary, d, "cnrb2solid", "c.yaml")
    got = [m for kw, m in card1_mids(os.path.join(d, "o.k")) if kw.startswith("*MAT_ELASTIC_TITLE")]
    check("D-5 cnrb2solid 새 MID 2 — TMID 500 은 MID 가 아니다(예전 501)", rc == 0 and got == [2], (rc, got, out[-300:]))

    spring = ("model: two.k\noutput: o.k\naxis: z\ngap: 0.1\nk_engage: 1.0e5\nk_axial: 1.0e7\nk_rot: 1.0e7\ncurve_range: 1.0\n"
              "target_pids: [1201]\nnode_id_start: 90000001\nelem_id_start: 9900001\ncard_id_start: 990001\npid_refs: strict\n")
    src = open(os.path.join(REPO, "examples", "cnrb2spring", "two_plate_bolt.k"), encoding="utf-8").read()
    for tag, extra, want_rc, why in (("t01", T01 % 990001, 0, "TMID 990001 은 재질 번호대와 겹치지 않는다(예전 거짓 겹침 rc 1)"),
                                     ("stack", "*MAT_ELASTIC\n" + EL % 30 + EL % 990001, 1,
                                      "쌓인 MID 990001 과 겹친다(예전 못 보고 rc 0)")):
        d = fresh(tmp, "d6" + tag)
        open(os.path.join(d, "two.k"), "w", encoding="utf-8").write(src.replace("*END", extra + "*END", 1))
        open(os.path.join(d, "s.yaml"), "w").write(spring)
        rc, out = run(binary, d, "cnrb2spring", "s.yaml")
        clash = "재질 ID 가 원본 덱과 겹칩니다" in out
        check("D-6%s cnrb2spring 고정 번호대 — %s" % (tag[0], why), rc == want_rc and clash == (want_rc == 1), (rc, clash, out[-300:]))

    d = fresh(tmp, "d7")
    box(binary, d, STACK)
    os.makedirs(os.path.join(d, "materials"))
    shutil.copy(os.path.join(REPO, "materials", "material_db.json"), os.path.join(d, "materials"))
    open(os.path.join(d, "m.yaml"), "w").write("model: box.k\noutput: o.k\nmat_type: MAT_ELASTIC\nmaterials:\n  - match_part: \"PLATE\"\n"
                                               "    match: \"SUS304\"\n")
    rc, out = run(binary, d, "matdb", "m.yaml")
    m = re.search(r"new MID=(\d+)", out)
    check("D-7 matdb match_part 새 MID 4 — 쌓인 MID 3 위(예전 3 — 겹쳤다)", rc == 0 and m and int(m.group(1)) == 4,
          (rc, m.group(0) if m else None, out[-300:]))


def first_ids(path, kw):
    """`kw` 블록(제목 꼴 포함)마다 첫 데이터 줄의 첫 칸 정수."""
    L = open(path, encoding="utf-8").read().split("\n") if os.path.exists(path) else []
    out = []
    for i, l in enumerate(L):
        u = l.strip().upper().split()[0] if l.strip() else ""
        if u not in (kw, kw + "_TITLE"):
            continue
        j, title = i + 1, u.endswith("_TITLE")
        while j < len(L) and L[j].startswith("$"):
            j += 1
        if title:
            j += 1
            while j < len(L) and L[j].startswith("$"):
                j += 1
        if j < len(L) and L[j][:10].strip().isdigit():
            out.append(int(L[j][:10]))
    return out


MAT_STACK9 = (lambda b: re.sub(r"(\*MAT_ELASTIC\n(?:\$.*\n)*)(\s+2\s+\S+.*\n)", lambda m: m.group(1) + m.group(2) + EL % 9, b, count=1))
ADDONS = ("*PART\nSECOND\n         2         1         9\n" + T01 % 2 +
          "*MAT_ADD_THERMAL_EXPANSION\n         2         0       1.0\n*MAT_ADD_EROSION\n         2\n")


def box_mid2(binary, d, extra, name="box.k", edit=MAT_STACK9):
    """상자(PID 1 · MID 2) — 재질 블록에 MID 9 를 쌓고(PID 2 가 쓴다) 열 재질 TMID 2 · PID 2 의 열팽창 · MID 2 의 침식을 더한다."""
    box(binary, d, extra, name=name, yaml=BOX.replace("mid: 1", "mid: 2"))
    p = os.path.join(d, name)
    body = open(p, encoding="utf-8").read()
    open(p, "w", encoding="utf-8").write(edit(body))


def kept(path):
    return {"t01": first_ids(path, "*MAT_T01") == [2], "expansion": first_ids(path, "*MAT_ADD_THERMAL_EXPANSION") == [2],
            "erosion": first_ids(path, "*MAT_ADD_EROSION"), "mid9": elastic_rows(path).count(9) == 1}


def part_a(binary, tmp):
    print("[A matswap — 옛 MID 의 구조 재질 정의만 지운다(열 재질 · PID 꼴 덧붙임 · 쌓인 다른 재질은 둔다)]")
    bundle = os.path.join(REPO, "examples", "matswap", "rubber.k")
    for tag in ("단독", "assemble"):
        d = fresh(tmp, "a1" + ("s" if tag == "단독" else "a"))
        box_mid2(binary, d, ADDONS)
        shutil.copy(bundle, d)
        if tag == "단독":
            open(os.path.join(d, "s.yaml"), "w").write("model: box.k\noutput: o.k\nswaps:\n  - bundle: rubber.k\n    pid: 1\n")
            rc, out = run(binary, d, "matswap", "s.yaml")
            o = "o.k"
        else:
            open(os.path.join(d, "s.yaml"), "w").write("base_model: box.k\noutput: o\noperations:\n  - type: matswap\n    pid: 1\n"
                                                       "    bundle: rubber.k\n")
            rc, out = run(binary, d, "assemble", "s.yaml")
            o = "o.k"
        k = kept(os.path.join(d, o))
        rc2, out2 = run(binary, d, "info", "--strict", o) if rc == 0 else (None, "")
        check("A-1%s matswap(%s) — TMID 2 의 *MAT_T01 · PID 2 의 열팽창 · 쌓인 MID 9 가 남는다 · --strict rc 0" % (tag[0], tag),
              rc == 0 and k["t01"] and k["expansion"] and k["mid9"] and rc2 == 0, (rc, k, rc2, out2[-200:], out[-300:]))
        m = re.search(r"&MID1 \(MID\) \d+ -> (\d+)", out)
        check("A-2%s matswap(%s) — MID 2 를 번들이 다시 받고 MID 꼴 덧붙임(*MAT_ADD_EROSION 2)은 그 번호에 남는다" % (tag[0], tag),
              rc == 0 and k["erosion"] == [2] and m and int(m.group(1)) == 2, (rc, k, m.group(0) if m else None, out[-300:]))

    # 두 파트(MID 2 · 9)를 함께 바꾼다 — 번들은 새 번호를 받고 두 재질은 덱에서 사라진다 · 그 MID 의 덧붙임(EROSION 2)도 지운다
    d = fresh(tmp, "a4")
    box_mid2(binary, d, ADDONS)
    shutil.copy(bundle, d)
    open(os.path.join(d, "s.yaml"), "w").write("base_model: box.k\noutput: o\noperations:\n  - type: matswap\n    pids: [1, 2]\n"
                                               "    bundle: rubber.k\n")
    rc, out = run(binary, d, "assemble", "s.yaml")
    k = kept(os.path.join(d, "o.k"))
    rc2, out2 = run(binary, d, "info", "--strict", "o.k") if rc == 0 else (None, "")
    check("A-4 assemble matswap 두 파트(MID 2 · 9) — 재질이 사라진 MID 2 의 *MAT_ADD_EROSION 도 지우고 열 재질 · 열팽창은 둔다 · --strict rc 0",
          rc == 0 and k["t01"] and k["expansion"] and k["erosion"] == [] and rc2 == 0, (rc, k, rc2, out2[-200:], out[-300:]))

    # 지운 뒤에도 그 번호가 쓰인다 — 길이를 모르는 꼴 블록의 둘째 묶음에 MID 2 가 있다 · 번들은 새 번호를 받는다
    ortho = ("*MAT_ORTHOTROPIC_ELASTIC\n"
             + "".join("%10d   7.85E-9    1000.0    1000.0    1000.0       0.3       0.3       0.3\n" % m +
                       "     500.0     500.0     500.0       0.0\n       0.0       0.0       0.0       1.0       0.0       0.0\n"
                       "       0.0       1.0       0.0       0.0\n" for m in (7, 2)))
    d = fresh(tmp, "a3")
    box_mid2(binary, d, "", edit=lambda b: re.sub(r"\*MAT_ELASTIC\n(?:\$.*\n)*\s+2\s+\S+.*\n", lambda m: ortho, b, count=1))
    shutil.copy(bundle, d)
    open(os.path.join(d, "s.yaml"), "w").write("model: box.k\noutput: o.k\nswaps:\n  - bundle: rubber.k\n    pid: 1\n")
    rc, out = run(binary, d, "matswap", "s.yaml")
    m = re.search(r"&MID1 \(MID\) \d+ -> (\d+)", out)
    body = open(os.path.join(d, "o.k"), encoding="utf-8").read() if os.path.exists(os.path.join(d, "o.k")) else ""
    check("A-3 MID 2 가 묶음을 못 가른 블록에 쌓여 있다 — 지울 수 없어 번들에 새 번호를 준다(예전 2 를 다시 줘 같은 MID 가 둘)",
          rc == 0 and m and int(m.group(1)) != 2 and body.count("*MAT_ORTHOTROPIC_ELASTIC") == 1 and "지운 뒤에도 쓰인다" in out,
          (rc, m.group(0) if m else None, out[-300:]))


def part_b(binary, tmp):
    print("[B cclip — 옛 MID 의 구조 재질 정의만 지운다 · 재질이 사라지면 MID 꼴 덧붙임도]")
    board = ("output: clip_board.k\nlx: 3.0\nly: 1.5\nlz: 0.5\nnx: 6\nny: 3\nnz: 1\nrho: 8.36e-9\nE: 131000.0\nnu: 0.3\nmid: 2\nsecid: 2\n"
             "pid: 2\npart_title: CCLIP_ANT_01\n")
    cyaml = ("model: clip_board.k\noutput: clip_board_cclip\nmode: analytic\nattach: none\nstress_output: embed\nfree_output: true\n"
             "calibration:\n  point: {deflection: 0.15, force: 1.2}\n  tolerance: 0.05\nclips:\n  - pid: 2\n    overtravel: 0.15\n")
    d = fresh(tmp, "b1")
    box(binary, d, "*PART\nSECOND\n         9         2         9\n" + T01 % 2 + "*MAT_ADD_THERMAL_EXPANSION\n         2         0       1.0\n"
        "*MAT_ADD_EROSION\n         2\n", name="clip_board.k", yaml=board)
    p = os.path.join(d, "clip_board.k")
    body = open(p, encoding="utf-8").read()
    open(p, "w", encoding="utf-8").write(MAT_STACK9(body))
    open(os.path.join(d, "c.yaml"), "w").write(cyaml)
    rc, out = run(binary, d, "cclip", "c.yaml")
    o = os.path.join(d, "clip_board_cclip.k")
    k = kept(o)
    rc2, out2 = run(binary, d, "info", "--strict", "clip_board_cclip.k") if rc == 0 else (None, "")
    check("B-1 cclip — TMID 2 의 *MAT_T01 · PID 2 의 열팽창 · 쌓인 MID 9 가 남는다 · --strict rc 0",
          rc == 0 and k["t01"] and k["expansion"] and k["mid9"] and rc2 == 0, (rc, k, rc2, out2[-200:], out[-300:]))
    check("B-2 cclip — 재질 2 가 사라졌다 · 그 MID 의 *MAT_ADD_EROSION 2 도 지운다(남기면 없는 재질을 가리킨다)",
          rc == 0 and k["erosion"] == [], (rc, k))


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    tmp = tempfile.mkdtemp(prefix="mat_id_family_")
    try:
        part_g(binary, tmp)
        part_d(binary, tmp)
        part_a(binary, tmp)
        part_b(binary, tmp)
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
