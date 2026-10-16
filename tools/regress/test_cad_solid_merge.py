#!/usr/bin/env python3
# StepForge 조각 삽입(cad_solid_merge_to_deck)이 계약대로 넣고 계약 밖은 거절하는지 보는 회귀 시험
"""`cad_solid_merge_to_deck` — StepForge 조각을 기존 덱에 **계약 그대로** 넣는가.

왜 이 시험이 있나 (2026-10-16).

  경계 합의(StepForge `docs/BOUNDARY-DYNAFORGE.md` §3-3)가 「조각을 쓰는 것은 StepForge, 넣는 것은 우리」로 정했다.
  저쪽이 10-16 에 `export_part_fragment` 를 지었고, 이 시험의 조각은 **그 실물 산출**이다
  (`examples/cad_solid_merge_to_deck/stepforge_fragment.k/.json` — 합성 과제 K2라이브-B, 파트 4).

신탁.
  · 넣은 뒤 산출 덱에서 파트마다 `coord_sha` 를 **이 시험이 따로** 잰다 — 저쪽 식(`f"{v:16.9e}"` 셋 · 사전순 ·
    sha256 앞 16자)을 파이썬으로 그대로 옮겼다. 대응표의 값과 같아야 한다(좌표 글자가 바이트 그대로인가)
  · 조각 번호가 대상 덱(인클루드 닫힘까지)의 최대값 **위에 있으면 그대로**(요청 때 발행 — `id_floor` · 2026-10-16),
    최대값 이하에 걸치면 최대값 바로 위로 옮긴다. 원래 덱의 줄은 차례대로 그대로 남는다
  · `info --strict` 가 산출 덱을 받아들인다(미정의 참조 0)
  · 계약 밖은 rc 1 이고 산출 덱이 없다

무엇을 보나.
  A 표준 폭 덱 — 실물 조각(500001/600001/900)이 덱 위에 있어 **옮기지 않는다** · 원본 줄 보존 · coord_sha ·
    대응표 = 덱 번호 · 자리표시 물성 경고 · info --strict
  B 인클루드에 조각보다 큰 번호가 있는 덱 — 그 위로 옮긴다(과도기 길)
  C i10 덱 — 넣은 절점·요소 번호 칸이 10칸이다
  D 거절 — 모르는 칸 · 빠진 칸 · 단위 불일치 · frame · 옮긴 절점(coord_sha) · sid 비-null · 계약 밖 키워드 ·
    ranges 가 실제와 다름 · long 덱

usage: test_cad_solid_merge.py <KooRemapper 바이너리>
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples", "cad_solid_merge_to_deck")
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail)[:400]))
    print("  %-64s %s" % (name[:64], "OK" if cond else "FAIL"))
    return cond


def coord_sha(xyz):
    """저쪽 `core/remesh_impact.coord_sha` 의 식 그대로."""
    rows = sorted("%s%s%s" % (f"{x:16.9e}", f"{y:16.9e}", f"{z:16.9e}") for x, y, z in xyz)
    return hashlib.sha256("\n".join(rows).encode("ascii")).hexdigest()[:16]


def deck_width(lines):
    for l in lines:
        if l.upper().startswith("*KEYWORD"):
            u = l.upper()
            return 20 if re.search(r"LONG\s*=\s*Y", u) else (10 if re.search(r"I10\s*=\s*Y", u) else 8)
        if l.startswith("*"):
            break
    return 8


def read_mesh(path):
    """절점·요소·파트 — 덱 폭 그대로 고정폭으로 읽는다. 요소 카드는 한 줄 꼴과 두 줄 꼴(EID PID / 절점)을
    다 읽는다 — `examples/load/mesh.k` 가 두 줄 꼴이다(첫 판은 한 줄만 읽어 절점 줄을 요소로 셌다)."""
    L = open(path, encoding="utf-8", errors="replace").read().splitlines()
    fw = deck_width(L)
    nodes, elems, kw, pending = {}, {}, None, None
    for l in L:
        if l.startswith("*"):
            kw = l.split()[0].upper().rstrip("%+-")
            pending = None
            continue
        if not l.strip() or l.lstrip().startswith("$"):
            continue
        if kw == "*NODE":
            nodes[int(l[:fw])] = tuple(float(l[fw + 16 * k: fw + 16 * (k + 1)]) for k in range(3))
        elif kw in ("*ELEMENT_SOLID", "*ELEMENT_SHELL"):
            f = [l[i:i + fw] for i in range(0, len(l.rstrip()), fw)]
            ids = [int(x) for x in f if x.strip()]
            if pending is not None:                       # 두 줄 꼴의 둘째 줄 — 절점
                elems[pending[0]] = (pending[1], [n for n in ids if n])
                pending = None
            elif len(ids) == 2:                           # 두 줄 꼴의 첫 줄 — EID PID
                pending = (ids[0], ids[1])
            else:
                elems[ids[0]] = (ids[1], [n for n in ids[2:] if n])
    return nodes, elems, fw, L


def max_card_ids(text):
    """*PART·*SECTION_*·*MAT_* 의 번호 최대값(셋 중 가장 큰 것) — 삽입은 셋을 한 이동량으로 옮긴다."""
    L = text.splitlines()
    best, kw, pos = 0, None, 0
    for l in L:
        if l.startswith("*"):
            kw, pos = l.split()[0].upper(), 0
            continue
        if not l.strip() or l.lstrip().startswith("$") or kw is None:
            continue
        title = kw == "*PART" or kw.endswith("_TITLE")
        if kw == "*PART" or kw.startswith(("*SECTION_", "*MAT_")):
            if pos == (1 if title else 0):
                m = re.match(r"\s*(\d+)", l[:10])
                if m:
                    best = max(best, int(m.group(1)))
            pos += 1
            if kw == "*PART" and pos == 2:
                pos = 0          # *PART 는 (제목, 카드)가 되풀이된다
    return best


def run(binary, d, yaml_name="m.yaml"):
    p = subprocess.run([binary, "cad_solid_merge_to_deck", yaml_name], cwd=d, capture_output=True, text=True,
                       timeout=600, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def stage(deck_text, frag_text=None, map_obj=None, unit=None, inc=None):
    d = tempfile.mkdtemp(prefix="csm_")
    open(os.path.join(d, "deck.k"), "w", encoding="utf-8").write(deck_text)
    for name, body in (inc or {}).items():
        open(os.path.join(d, name), "w", encoding="utf-8").write(body)
    open(os.path.join(d, "frag.k"), "w", encoding="utf-8").write(
        frag_text if frag_text is not None else open(os.path.join(EX, "stepforge_fragment.k"), encoding="utf-8").read())
    m = map_obj if map_obj is not None else json.load(open(os.path.join(EX, "stepforge_fragment.json"), encoding="utf-8"))
    open(os.path.join(d, "frag.json"), "w", encoding="utf-8").write(json.dumps(m, ensure_ascii=False, indent=2))
    open(os.path.join(d, "m.yaml"), "w", encoding="utf-8").write(
        "model: deck.k\noutput: merged\nfragment: frag.k\nfragment_map: frag.json\n" +
        ("deck_unit: %s\n" % unit if unit else ""))
    return d


def base_map():
    return json.load(open(os.path.join(EX, "stepforge_fragment.json"), encoding="utf-8"))


def verify_merged(label, d, deck_text, want_node_lo, want_elem_lo, want_pid_lo, want_fw):
    m = base_map()
    nodes, elems, fw, L = read_mesh(os.path.join(d, "merged.k"))
    check("%s — 번호 칸 폭 %d" % (label, want_fw), fw == want_fw, fw)
    dn = want_node_lo - m["ranges"]["node"][0]
    de = want_elem_lo - m["ranges"]["elem"][0]
    dp = want_pid_lo - m["ranges"]["pid"][0]
    ok_sha, ok_cnt = [], []
    for p in m["parts"]:
        pid = p["pid"] + dp
        es = [e for e, (epid, _) in elems.items() if epid == pid]
        ok_cnt.append(len(es) == p["elem_count"] and min(es) == p["elem_start"] + de)
        used = sorted({n for e in es for n in elems[e][1]})
        ok_sha.append(len(used) == p["node_count"] and used[0] == p["node_start"] + dn and
                      coord_sha([nodes[n] for n in used]) == p["coord_sha"])
    check("%s — 파트마다 요소 수·시작 번호(옮긴 자리)" % label, all(ok_cnt), ok_cnt)
    check("%s — 산출 덱에서 따로 잰 coord_sha 가 대응표와 같다" % label, all(ok_sha), ok_sha)
    # 원래 덱의 줄이 차례대로 그대로 남았다(*END 앞까지)
    src = deck_text.splitlines()
    end = max(i for i, l in enumerate(src) if l.strip().upper() == "*END")
    k = 0
    kept = True
    for l in src[:end]:
        while k < len(L) and L[k] != l:
            k += 1
        if k >= len(L):
            kept = False
            break
        k += 1
    check("%s — 원래 덱의 줄이 차례대로 그대로 있다" % label, kept)
    # 옮긴 대응표 — 같은 칸 집합 · 덱 번호
    rm = json.load(open(os.path.join(d, "merged_fragment_map.json"), encoding="utf-8"))
    exp = base_map()
    exp["ranges"]["node"] = [x + dn for x in exp["ranges"]["node"]]
    exp["ranges"]["elem"] = [x + de for x in exp["ranges"]["elem"]]
    exp["ranges"]["pid"] = [x + dp for x in exp["ranges"]["pid"]]
    for p in exp["parts"]:
        p["pid"] += dp
        p["node_start"] += dn
        p["elem_start"] += de
    check("%s — 옮긴 대응표가 같은 칸 집합·덱 번호다" % label, rm == exp,
          json.dumps(rm, ensure_ascii=False)[:300])
    return nodes, elems


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    deck = open(os.path.join(EX, "deck.k"), encoding="utf-8").read()

    print("[A 표준 폭 덱 — 실물 조각]")
    d = stage(deck)
    try:
        rc, out = run(binary, d)
        if check("A rc 0", rc == 0 and os.path.exists(os.path.join(d, "merged.k")), out[-500:]):
            verify_merged("A", d, deck, 500001, 600001, 900, 8)   # 덱 최대 12 · 2 · 2 — 조각이 위에 있다
            check("A ★옮기지 않았다고 말한다(대응표 번호 = 덱 번호)", "옮기지 않았다" in out, out[-400:])
            check("A 자리표시 물성을 MID 마다 경고한다", out.count("자리표시 물성") == 4, out.count("자리표시 물성"))
            # 쓰기 뒤 요소 수 대조가 넣은 블록의 파트까지 본다(블록만 넣는 op 은 예전에 이 대조를 건너뛰었다)
            check("A 쓰기 뒤 요소 수 대조가 넣은 파트를 본다", "PID 900: 0 → 100 (신규)" in out and "왕복 검증" in out,
                  out[-400:])
            p = subprocess.run([binary, "info", os.path.join(d, "merged.k"), "--strict"], capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            check("A info --strict 가 받아들인다(미정의 참조 0)", p.returncode == 0 and "참조 무결성 OK" in p.stdout,
                  (p.stdout + p.stderr)[-300:])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("[B 인클루드에 더 큰 번호]")
    # 인클루드의 번호가 조각(500001/600001/900)보다 크다 — 조각이 바닥 아래에 걸치므로 그 위로 옮긴다
    inc = ("*KEYWORD\n*NODE\n%8d%16.9e%16.9e%16.9e\n*PART\nfar part\n%10d%10d%10d\n"
           "*SECTION_SOLID\n%10d%10d\n*MAT_ELASTIC\n%10d%10s%10s%10s\n*ELEMENT_SOLID\n%8d%8d" % (
               550000, 9e3, 9e3, 9e3, 950, 960, 970, 960, 1, 970, "7.85E-9", "210000.", "0.3", 650000, 950) +
           "%8d" * 8 % ((550000,) * 8) + "\n*END\n")
    deck_b = deck.replace("*END", "*INCLUDE\nfar.k\n*END")
    d = stage(deck_b, inc={"far.k": inc})
    try:
        rc, out = run(binary, d)
        if check("B rc 0", rc == 0, out[-500:]):
            verify_merged("B", d, deck_b, 550001, 650001, 971, 8)   # 인클루드 — 절점 550000 · 요소 650000 · PID 950 · SECID 960 · MID 970
            check("B 옮겼다고 말한다(바닥 아래에 걸쳤다)", "옮겼다" in out and "id_floor" in out, out[-400:])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("[C i10 덱]")
    mesh = open(os.path.join(REPO, "examples", "load", "mesh.k"), encoding="utf-8").read()
    d = stage(mesh)
    try:
        rc, out = run(binary, d)
        if check("C rc 0", rc == 0, out[-500:]):
            nodes0, elems0, _fw, _L = read_mesh(os.path.join(d, "deck.k"))
            assert max(nodes0) < 500001 and max(elems0) < 600001 and max_card_ids(mesh) < 900
            verify_merged("C", d, mesh, 500001, 600001, 900, 10)   # i10 덱 — 조각이 위에 있어 그대로 · 칸은 10
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("[D 거절 — rc 1 · 산출 없음]")
    frag = open(os.path.join(EX, "stepforge_fragment.k"), encoding="utf-8").read()
    moved = re.sub(r"^(  500003) 1\.000000000e\+02", r"\1 1.000500000e+02", frag, count=1, flags=re.M)
    assert moved != frag
    cases = []
    m = base_map(); m["extra"] = 1; cases.append(("D1 모르는 칸", None, m, None, "모르는 칸 'extra'"))
    m = base_map(); del m["frame"]; cases.append(("D2 빠진 칸", None, m, None, "'frame'"))
    cases.append(("D3 단위 불일치", None, None, "m-kg-s", "단위"))
    m = base_map(); m["frame"] = "local"; cases.append(("D4 frame 이 world 가 아니다", None, m, None, "frame"))
    cases.append(("D5 절점 하나를 옮겼다(coord_sha)", moved, None, None, "coord_sha"))
    m = base_map(); m["ranges"]["sid"] = [1, 1]; cases.append(("D6 sid 가 null 이 아니다", None, m, None, "sid"))
    withset = frag.replace("*END", "*SET_PART_LIST\n       900\n       900\n*END")
    cases.append(("D7 계약 밖 키워드(*SET_PART_LIST)", withset, None, None, "SID"))
    m = base_map(); m["ranges"]["node"][1] += 1; cases.append(("D8 ranges 가 실제와 다르다", None, m, None, "절점 실제"))
    for label, ftxt, mobj, unit, needle in cases:
        d = stage(deck, ftxt, mobj, unit)
        try:
            rc, out = run(binary, d)
            check("%s — rc 1 · 산출 없음 · 까닭(%s)" % (label, needle),
                  rc == 1 and not os.path.exists(os.path.join(d, "merged.k")) and needle in out, out[-300:])
        finally:
            shutil.rmtree(d, ignore_errors=True)
    d = stage(deck.replace("*KEYWORD", "*KEYWORD long=y", 1))
    try:
        rc, out = run(binary, d)
        check("D9 long 덱 — rc 1 · 산출 없음", rc == 1 and not os.path.exists(os.path.join(d, "merged.k")) and "long" in out,
              out[-300:])
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
