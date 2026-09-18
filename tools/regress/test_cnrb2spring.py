# cnrb2spring 회귀 시험 — 덱 구조(칸 폭·칸 수·좌표·곡선·분할·삭제·충돌·멱등)를 문자열로 직접 못 박는다
"""
사용: python3 tools/regress/test_cnrb2spring.py <KooRemapper 바이너리>

배경
  - LS-DYNA 라이선스가 없어 솔버로 검증할 수 없다. 그래서 이 시험은 산출 덱의 칸 폭·칸 수·참조 정합성을
    직접 읽어 확인한다. 현장에서 실제로 당한 함정이 그대로 단언이 된다.
      *ELEMENT_DISCRETE 는 8칸이다(다른 카드는 10칸) — 10칸으로 쓰면 7자리 EID 가 잘려
      'beam element ... has an undefined PID' 가 난다.
      *SECTION_DISCRETE 는 2번째 줄(CDL,TDL)이 필수다 — 빼면 다음 키워드 줄을 그 줄로 먹는다.
      *MAT_SPRING_GENERAL_NONLINEAR 은 MID LCDL LCDU 세 칸만 쓴다 — 7칸으로 쓰면 'MAT n is not found'.
      블록 사이에 빈 줄이 들어가면 *ELEMENT_DISCRETE 가 빈 줄을 요소로 읽어
      'discrete element id 0 is invalid' 가 난다.
      *ELEMENT_DISCRETE 의 S 칸을 비우면 0.0 으로 읽혀 스프링이 에러 없이 무력화될 수 있다 — 1.0 을 명시한다.
  - 파트 판정은 요소 연결성으로만 한다. *ELEMENT_SOLID 의 ten nodes format 은 한 요소가 두 줄이라
    한 줄짜리로 읽으면 노드 ID 를 PID 로 읽는다. CNRB 노드가 TET10 의 9·10번 중간절점일 수 있으므로
    둘째 줄 전체를 읽어야 한다.
  - 세트 안의 '실제 노드가 아닌 ID' 는 '100 이하' 가 아니라 '*NODE 목록에 없는 ID' 로 거른다.
  - 새 ID(노드 9000만·요소 990만·카드 99만)는 원본과 겹칠 수 있다 — 조용히 밀지 않고 rc=1 이다.
"""
import os
import re
import subprocess
import sys
import tempfile

FAILS = []


def check(name, cond, detail=""):
    print("  %-72s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def w(path, text):
    with open(path, "w") as f:
        f.write(text)


def node(nid, x, y, z):
    return "%8d%16.8e%16.8e%16.8e       0       0" % (nid, x, y, z)


def shell_deck(nsid=9001, cnrb_pid=1201, title=True, set_extra=(), cnrb_nsid=None,
               pnode=0, drflag=0, extra_cards="", set_kw="*SET_NODE_LIST_TITLE"):
    """PID 500 하판(z=0) + PID 700 상판(z=2) 셸 3x3 격자, CNRB 하나."""
    L = ["*KEYWORD", "*NODE"]
    n = 1
    for j in range(3):
        for i in range(3):
            L.append(node(n, i * 10.0, j * 10.0, 0.0)); n += 1
    n = 11
    for j in range(3):
        for i in range(3):
            L.append(node(n, i * 10.0, j * 10.0, 2.0)); n += 1
    L.append("*ELEMENT_SHELL")
    e = 1
    for j in range(2):
        for i in range(2):
            a = 1 + j * 3 + i
            L.append("%8d%8d%8d%8d%8d%8d" % (e, 500, a, a + 1, a + 4, a + 3)); e += 1
    e = 11
    for j in range(2):
        for i in range(2):
            a = 11 + j * 3 + i
            L.append("%8d%8d%8d%8d%8d%8d" % (e, 700, a, a + 1, a + 4, a + 3)); e += 1
    for pid in (500, 700):
        L += ["*PART", "PLATE %d" % pid, "%10d%10d%10d" % (pid, pid, pid),
              "*SECTION_SHELL", "%10d%10d" % (pid, 2), "%10s%10s%10s%10s" % ("1.0", "1.0", "1.0", "1.0"),
              "*MAT_ELASTIC", "%10d%10s%10s%10s" % (pid, "7.85E-9", "210000.0", "0.3")]
    L.append(set_kw)
    if "_TITLE" in set_kw:
        L.append("hole nodes")
    L.append("%10d" % nsid)
    members = [1, 2, 4, 5, 11, 12, 14, 15] + list(set_extra)
    for i in range(0, len(members), 8):
        L.append("".join("%10d" % v for v in members[i:i + 8]))
    L.append("*CONSTRAINED_NODAL_RIGID_BODY_TITLE" if title else "*CONSTRAINED_NODAL_RIGID_BODY")
    if title:
        L.append("bolt %d" % cnrb_pid)
    L.append("%10d%10d%10d%10d%10d%10d%10d" %
             (cnrb_pid, 0, nsid if cnrb_nsid is None else cnrb_nsid, pnode, 0, drflag, 0))
    if extra_cards:
        L.append(extra_cards.rstrip("\n"))
    L.append("*END")
    return "\n".join(L) + "\n"


def tet10_deck():
    """CNRB 노드가 TET10 의 9·10번 중간절점인 덱 — 둘째 줄 전체를 읽어야 파트를 찾는다."""
    L = ["*KEYWORD", "*NODE"]
    base = [(0, 0), (10, 0), (5, 10), (5, 5), (5, 0), (7.5, 5), (2.5, 5), (2.5, 2.5), (7.5, 2.5), (5, 7.5)]
    for k, (x, y) in enumerate(base):
        L.append(node(1 + k, x, y, 0.0))
    for k, (x, y) in enumerate(base):
        L.append(node(11 + k, x, y, 2.0))
    L.append("*ELEMENT_SOLID")
    L.append("%8d%8d" % (1, 500))
    L.append("".join("%8d" % (1 + k) for k in range(10)))
    L.append("%8d%8d" % (2, 700))
    L.append("".join("%8d" % (11 + k) for k in range(10)))
    for pid in (500, 700):
        L += ["*PART", "TET10 %d" % pid, "%10d%10d%10d" % (pid, pid, pid),
              "*SECTION_SOLID", "%10d%10d" % (pid, 16),
              "*MAT_ELASTIC", "%10d%10s%10s%10s" % (pid, "7.85E-9", "210000.0", "0.3")]
    L += ["*SET_NODE_LIST", "%10d" % 9001,
          "".join("%10d" % v for v in (9, 10, 19, 20)),
          "*CONSTRAINED_NODAL_RIGID_BODY", "%10d%10d%10d%10d%10d%10d%10d" % (1201, 0, 9001, 0, 0, 0, 0),
          "*END"]
    return "\n".join(L) + "\n"


def is_data(ln):
    """제목 줄과 데이터 줄을 가른다 — 데이터 줄은 숫자·부호·공백만으로 이뤄진다."""
    return bool(ln.strip()) and re.fullmatch(r"[0-9 .eE+\-]+", ln.rstrip()) is not None


def blocks(text):
    """키워드 → 그 블록의 데이터 줄 목록('$'·빈 줄·제목 줄 제외). 같은 키워드가 여러 번이면 이어 붙인다."""
    out, kw = {}, None
    for ln in text.splitlines():
        if ln.startswith("*"):
            kw = ln.strip().upper()
            out.setdefault(kw, [])
            continue
        if kw is None or ln.startswith("$") or not is_data(ln):
            continue
        out[kw].append(ln)
    return out


def body(binary, tmp):
    d = tmp
    w(os.path.join(d, "m.k"), shell_deck())
    w(os.path.join(d, "c.yaml"), "model: m.k\noutput: out.k\naxis: z\ntarget_pids: [1201]\n")
    rc, out = run(binary, d, "cnrb2spring", "c.yaml")
    deck = open(os.path.join(d, "out.k")).read() if os.path.exists(os.path.join(d, "out.k")) else ""
    check("정상 변환 rc=0 + 산출 덱", rc == 0 and deck, f"rc={rc} {out[-300:]}")
    B = blocks(deck)

    # ── 삭제 ──────────────────────────────────────────────────────────────
    check("원 CNRB 의 데이터 줄이 사라졌다 (PID 1201)",
          not any(l[:10].strip() == "1201" for l in B.get("*CONSTRAINED_NODAL_RIGID_BODY_TITLE", [])),
          str(B.get("*CONSTRAINED_NODAL_RIGID_BODY_TITLE"))[:200])
    check("원 CNRB 의 제목 줄('bolt 1201')이 사라졌다", "bolt 1201" not in deck)
    sids = [l[:10].strip() for l in B.get("*SET_NODE_LIST_TITLE", [])
            if l.strip() and len(l.strip()) <= 10]
    check("원 *SET_NODE_LIST(SID 9001)이 통째로 사라졌다", "9001" not in sids, str(sids))
    check("원 세트의 제목 줄('hole nodes')도 사라졌다", "hole nodes" not in deck)

    # ── 분할 ──────────────────────────────────────────────────────────────
    cn = B.get("*CONSTRAINED_NODAL_RIGID_BODY_TITLE", [])
    check("새 CNRB 가 정확히 2개다", len(cn) == 2, str(cn))
    newsids = [int(l[20:30]) for l in cn]
    setsids = {int(l[:10]) for l in B.get("*SET_NODE_LIST_TITLE", []) if len(l.strip()) <= 10}
    check("두 새 CNRB 의 NSID 가 실제로 있는 *SET_NODE_LIST SID 를 가리킨다",
          all(s in setsids for s in newsids), f"{newsids} / {sorted(setsids)}")
    check("새 CNRB 의 PID 와 NSID 가 같다(NSID=PID 규약)",
          all(int(l[:10]) == int(l[20:30]) for l in cn), str(cn))

    setmap = {}
    cur = None
    for ln in deck.splitlines():
        if ln.startswith("*"):
            cur = "SET" if ln.strip().upper() == "*SET_NODE_LIST_TITLE" else None
            sid = None
            continue
        if cur != "SET" or ln.startswith("$") or not is_data(ln):
            continue
        if len(ln.strip()) <= 10:
            sid = int(ln[:10]); setmap[sid] = []
        else:
            setmap[sid] += [int(ln[i:i + 10]) for i in range(0, len(ln.rstrip()), 10)]
    sA, sB = sorted(setmap)[-2:]
    check("Side A 세트 = 하판 노드 4개 + 팬텀 3개", sorted(setmap[sA]) == [1, 2, 4, 5, 90000001, 90000002, 90000003],
          str(setmap[sA]))
    check("Side B 세트 = 상판 노드 4개 + 팬텀 1개", sorted(setmap[sB]) == [11, 12, 14, 15, 90000004],
          str(setmap[sB]))

    # ── *NODE 팬텀 좌표: 차이가 정확히 eps, 나머지 두 성분은 같다 ─────────
    ph = {}
    for l in B.get("*NODE", []):
        nid = int(l[:8])
        if nid >= 90000000:
            ph[nid] = (float(l[8:24]), float(l[24:40]), float(l[40:56]))
    check("팬텀 노드가 4개다", len(ph) == 4, str(ph))
    rb = ph[90000004]
    for k, nid in enumerate((90000001, 90000002, 90000003)):
        ra = ph[nid]
        diffs = [round(ra[i] - rb[i], 12) for i in range(3)]
        want = [0.0, 0.0, 0.0]
        want[k] = 0.001
        check(f"팬텀 {nid} 은 {'XYZ'[k]} 축으로만 eps=0.001 떨어져 있다", diffs == want, str(diffs))

    # ── *ELEMENT_DISCRETE: 8칸 ────────────────────────────────────────────
    ed = B.get("*ELEMENT_DISCRETE", [])
    check("*ELEMENT_DISCRETE 데이터 줄이 3개다", len(ed) == 3, str(ed))
    parts = {int(l[:10]) for l in B.get("*PART", []) if len(l.rstrip()) <= 30}
    nids = {int(l[:8]) for l in B.get("*NODE", [])}
    ok8 = True
    for l in ed:
        eid, pid, n1, n2, vid = (int(l[i:i + 8]) for i in range(0, 40, 8))
        s = float(l[40:56])
        if not (eid >= 9900001 and pid in parts and n1 in nids and n2 in nids and vid == 0 and s == 1.0):
            ok8 = False
    check("*ELEMENT_DISCRETE 를 8칸으로 잘라 읽으면 EID/PID/N1/N2/VID/S 가 모두 성립한다 "
          "(10칸이면 전부 깨진다)", ok8, str(ed))
    check("*ELEMENT_DISCRETE 줄 길이가 56(=8*5+16)이다", all(len(l) == 56 for l in ed), str([len(l) for l in ed]))
    check("*ELEMENT_DISCRETE 의 S 칸(41-56)이 1.0 이다 — 비우면 0.0 으로 읽혀 스프링이 죽는다",
          all(abs(float(l[40:56]) - 1.0) < 1e-12 for l in ed), str(ed))
    axial = [l for l in ed if int(l[8:16]) == 990002]
    check("축(Z) 스프링 1개만 축 파트(990002)에 붙고 N1 이 RA_z(90000003)다",
          len(axial) == 1 and int(axial[0][16:24]) == 90000003, str(axial))

    # ── 10칸 카드 ─────────────────────────────────────────────────────────
    sd = B.get("*SECTION_DISCRETE", [])
    check("*SECTION_DISCRETE 의 데이터 줄이 2줄이다 (Card 2 = CDL,TDL 필수)", len(sd) == 2, str(sd))
    check("*SECTION_DISCRETE Card 1 의 SECID 가 10칸 첫 칸이다", sd and int(sd[0][:10]) == 990001, str(sd))
    ms = B.get("*MAT_SPRING_GENERAL_NONLINEAR", [])
    check("*MAT_SPRING_GENERAL_NONLINEAR 이 2개(전단·축)다", len(ms) == 2, str(ms))
    check("*MAT_SPRING_GENERAL_NONLINEAR 은 MID LCDL LCDU 세 칸만 쓴다(줄 길이 30)",
          all(len(l) == 30 for l in ms), str([len(l) for l in ms]))
    check("*MAT_SPRING_GENERAL_NONLINEAR 의 LCDL=LCDU (대칭 로딩/언로딩)",
          all(int(l[10:20]) == int(l[20:30]) for l in ms), str(ms))
    pt = B.get("*PART", [])
    check("*PART 데이터 줄이 10칸이고 MID 가 0 이 아니다",
          all(int(l[20:30]) != 0 for l in pt if len(l.rstrip()) <= 30), str(pt))

    # ── *DEFINE_CURVE ─────────────────────────────────────────────────────
    dc = B.get("*DEFINE_CURVE", [])
    hdr = [l for l in dc if len(l) == 80]
    pts = [l for l in dc if len(l) == 40]
    check("*DEFINE_CURVE 헤더 2줄(10칸*8=80) + 점 6줄(20칸*2=40)",
          len(hdr) == 2 and len(pts) == 6, f"hdr={len(hdr)} pts={len(pts)}")
    shear = [(float(l[:20]), float(l[20:])) for l in pts[:4]]
    ax = [(float(l[:20]), float(l[20:])) for l in pts[4:]]
    check("전단 곡선 = (-1,-9e4) (-0.1,0) (0.1,0) (1,9e4) — ±gap 구간 힘 0, 밖 기울기 k_engage",
          shear == [(-1.0, -90000.0), (-0.1, 0.0), (0.1, 0.0), (1.0, 90000.0)], str(shear))
    check("축 곡선 = (-1,-1e7) (1,1e7) — 기울기 k_axial", ax == [(-1.0, -1e7), (1.0, 1e7)], str(ax))

    # ── 빈 줄 없음 ────────────────────────────────────────────────────────
    lines = deck.splitlines()
    i0 = next(i for i, l in enumerate(lines) if l.startswith("$ === cnrb2spring"))
    check("삽입 블록 안에 빈 줄이 하나도 없다 (*ELEMENT_DISCRETE 가 요소로 오인한다)",
          all(l.strip() for l in lines[i0:]), str([l for l in lines[i0:] if not l.strip()]))
    check("삽입 블록이 *END 바로 앞까지 이어진다", lines[-1].strip().upper() == "*END", lines[-1])
    return d


def body2(binary, d):
    # ── TET10 두 줄 형식 ──────────────────────────────────────────────────
    w(os.path.join(d, "tet.k"), tet10_deck())
    w(os.path.join(d, "tet.yaml"), "model: tet.k\noutput: tet_out.k\naxis: z\n")
    rc, out = run(binary, d, "cnrb2spring", "tet.yaml")
    check("TET10(두 줄 형식)의 9·10번 중간절점만 든 CNRB 도 두 파트를 찾는다",
          rc == 0 and "PART 500(노드 2) <-> PART 700(노드 2)" in out, f"rc={rc} {out[-300:]}")

    # ── 세트 안 가짜 ID ───────────────────────────────────────────────────
    w(os.path.join(d, "gh.k"), shell_deck(set_extra=(5, 19, 777777)))
    w(os.path.join(d, "gh.yaml"), "model: gh.k\noutput: gh_out.k\naxis: z\n")
    rc, out = run(binary, d, "cnrb2spring", "gh.yaml")
    check("세트 안 '*NODE 에 없는 ID' 만 걸러 개수를 보고한다 (777777 하나 — 5·19 는 실재 노드다)",
          rc == 0 and "*NODE 에 없는 ID 1개를 세트에서 제외했습니다" in out, f"rc={rc} {out[-400:]}")
    gh = open(os.path.join(d, "gh_out.k")).read()
    check("실재 노드 5·19 는 '100 이하' 규칙으로 버려지지 않고 새 세트에 남는다",
          "         5" in gh and "        19" in gh, "")

    # ── NSID=0 → NSID=PID ─────────────────────────────────────────────────
    w(os.path.join(d, "z.k"), shell_deck(nsid=1201, cnrb_nsid=0))
    w(os.path.join(d, "z.yaml"), "model: z.k\noutput: z_out.k\naxis: z\n")
    rc, out = run(binary, d, "cnrb2spring", "z.yaml")
    check("NSID=0 은 LS-DYNA 규칙대로 NSID=PID 로 읽는다", rc == 0, f"rc={rc} {out[-300:]}")

    # ── _TITLE 인데 제목 줄이 빠진 덱 ─────────────────────────────────────
    bad = shell_deck().replace("*CONSTRAINED_NODAL_RIGID_BODY_TITLE\nbolt 1201\n",
                               "*CONSTRAINED_NODAL_RIGID_BODY_TITLE\n")
    w(os.path.join(d, "nt.k"), bad)
    w(os.path.join(d, "nt.yaml"), "model: nt.k\noutput: nt_out.k\naxis: z\ntarget_pids: [1201]\n")
    rc, out = run(binary, d, "cnrb2spring", "nt.yaml")
    check("_TITLE 인데 제목 줄이 빠진 덱에서도 PID/NSID 를 한 줄 밀려 읽지 않는다",
          rc == 0 and "PID 1201:" in out, f"rc={rc} {out[-300:]}")

    # ── PNODE 는 '소속된 쪽' 강체에만 ─────────────────────────────────────
    # 양쪽에 다 넘기면 한 노드가 두 강체에 들어가고 LS-DYNA 가 PNODE 좌표를 무게중심으로 옮긴다.
    # 노드 5 는 하판(PID 500=side A) 세트 멤버, 노드 11 은 상판(PID 700=side B) 세트 멤버,
    # 노드 9 는 세트 멤버가 아니다.
    for pn_node, sideA, sideB, why in ((5, 5, 0, "side A 노드"), (11, 0, 11, "side B 노드")):
        w(os.path.join(d, "pn.k"), shell_deck(pnode=pn_node))
        w(os.path.join(d, "pn.yaml"), "model: pn.k\noutput: pn_out.k\naxis: z\n")
        rc, out = run(binary, d, "cnrb2spring", "pn.yaml")
        pn = open(os.path.join(d, "pn_out.k")).read() if rc == 0 else ""
        cn = blocks(pn).get("*CONSTRAINED_NODAL_RIGID_BODY_TITLE", [])
        check(f"PNODE 가 {why}면 그 쪽 CNRB 에만 붙고 반대쪽은 0 이다 (노드는 지우지 않는다)",
              rc == 0 and len(cn) == 2 and int(cn[0][30:40]) == sideA and int(cn[1][30:40]) == sideB,
              f"rc={rc} {cn}")
    w(os.path.join(d, "pnx.k"), shell_deck(pnode=9))
    w(os.path.join(d, "pnx.yaml"), "model: pnx.k\noutput: pnx_out.k\naxis: z\n")
    rc, out = run(binary, d, "cnrb2spring", "pnx.yaml")
    pn = open(os.path.join(d, "pnx_out.k")).read() if rc == 0 else ""
    cn = blocks(pn).get("*CONSTRAINED_NODAL_RIGID_BODY_TITLE", [])
    check("세트 멤버가 아닌 PNODE 는 양쪽 다 0 으로 두고 [WARN] 로 알린다",
          rc == 0 and len(cn) == 2 and int(cn[0][30:40]) == 0 and int(cn[1][30:40]) == 0 and
          "PNODE 9 은 어느 강체에 속하는지 정할 수 없어" in out, f"rc={rc} {cn}")

    # ── 축 교차검증 [WARN] ────────────────────────────────────────────────
    w(os.path.join(d, "ax.yaml"), "model: m.k\noutput: ax_out.k\naxis: x\n")
    rc, out = run(binary, d, "cnrb2spring", "ax.yaml")
    check("선언한 axis 가 두 파트 간격의 최대 성분과 다르면 [WARN] 한 줄 (rc 는 그대로 0)",
          rc == 0 and "최대 성분은 Z 입니다" in out, f"rc={rc} {out[-300:]}")

    # ── ID 충돌 ───────────────────────────────────────────────────────────
    for key, start, kw in (("node_id_start", 1, "노드"), ("elem_id_start", 1, "요소"),
                           ("card_id_start", 500, "파트")):
        w(os.path.join(d, "cl.yaml"), f"model: m.k\noutput: cl_out.k\naxis: z\n{key}: {start}\n")
        rc, out = run(binary, d, "cnrb2spring", "cl.yaml")
        check(f"ID 충돌({kw})은 조용히 밀지 않고 rc=1 + 바꿀 키 이름을 알린다",
              rc == 1 and f"{kw} ID 가 원본 덱과 겹칩니다" in out and key in out and
              not os.path.exists(os.path.join(d, "cl_out.k")), f"rc={rc} {out[-300:]}")
    # 세트·곡선 축은 헤더 줄이 칸 하나뿐인 형식(LS-PrePost 가 내는 세 가지)에서도 충돌을 잡아야 한다 —
    # 놓치면 SID 가 중복된 덱이 rc=0 으로 나가고 LS-DYNA 가 먼저 읽은 세트를 써 새 강체가 엉뚱한 노드를 묶는다.
    sid_forms = (("한 칸", "%10d" % 990011),
                 ("DA1..DA4", "%10d%10s%10s%10s%10s" % (990011, "0.0", "0.0", "0.0", "0.0")),
                 ("DA1..DA4+SOLVER",
                  "%10d%10s%10s%10s%10s%s" % (990011, "0.0", "0.0", "0.0", "0.0", "MECH")))
    for form, hdr in sid_forms:
        card = "*SET_NODE_LIST_TITLE\nunrelated\n%s\n%s" % (hdr, "%10d%10d" % (1, 2))
        w(os.path.join(d, "sc.k"), shell_deck(extra_cards=card))
        w(os.path.join(d, "sc.yaml"), "model: sc.k\noutput: sc_out.k\naxis: z\n")
        if os.path.exists(os.path.join(d, "sc_out.k")):
            os.remove(os.path.join(d, "sc_out.k"))
        rc, out = run(binary, d, "cnrb2spring", "sc.yaml")
        check(f"세트 SID 충돌을 '{form}' 형식 SID 줄에서도 rc=1 로 잡는다",
              rc == 1 and "세트 ID 가 원본 덱과 겹칩니다" in out and "990011" in out and
              not os.path.exists(os.path.join(d, "sc_out.k")), f"rc={rc} {out[-300:]}")
    cv = ("*DEFINE_CURVE_TITLE\nexisting curve\n%10d\n%20.1f%20.1f\n%20.1f%20.1f" %
          (990001, 0.0, 0.0, 1.0, 100.0))
    w(os.path.join(d, "cc.k"), shell_deck(extra_cards=cv))
    w(os.path.join(d, "cc.yaml"), "model: cc.k\noutput: cc_out.k\naxis: z\n")
    rc, out = run(binary, d, "cnrb2spring", "cc.yaml")
    check("성긴 *DEFINE_CURVE 헤더(LCID 한 칸)의 곡선 ID 충돌도 rc=1 로 잡는다",
          rc == 1 and "곡선 ID 가 원본 덱과 겹칩니다" in out and "990001" in out and
          not os.path.exists(os.path.join(d, "cc_out.k")), f"rc={rc} {out[-300:]}")
    w(os.path.join(d, "hi.yaml"), "model: m.k\noutput: hi_out.k\naxis: z\nnode_id_start: 99999999\n")
    rc, out = run(binary, d, "cnrb2spring", "hi.yaml")
    check("마지막 할당 ID 가 I8 상한(99999999)을 넘으면 rc=1",
          rc == 1 and "I8 상한" in out, f"rc={rc} {out[-200:]}")

    # ── 멱등 대신 명시적 실패 ─────────────────────────────────────────────
    w(os.path.join(d, "re.yaml"), "model: out.k\noutput: re_out.k\naxis: z\n")
    rc, out = run(binary, d, "cnrb2spring", "re.yaml")
    check("이미 변환한 덱에 다시 돌리면 rc=1 로 멈춘다(조용한 중복 생성 없음)",
          rc == 1 and not os.path.exists(os.path.join(d, "re_out.k")), f"rc={rc} {out[-300:]}")

    # ── 죽은 참조 ─────────────────────────────────────────────────────────
    ref = ("*DATABASE_HISTORY_PART\n      1201\n"
           "*BOUNDARY_SPC_SET\n      9001         0         1         1         1         1         1         1")
    w(os.path.join(d, "rf.k"), shell_deck(extra_cards=ref))
    w(os.path.join(d, "rf.yaml"), "model: rf.k\noutput: rf_out.k\naxis: z\n")
    rc, out = run(binary, d, "cnrb2spring", "rf.yaml")
    check("지운 CNRB PID 를 가리키는 카드가 남으면 strict 에서 rc=1",
          rc == 1 and "*DATABASE_HISTORY_PART" in out and "PID 를 가리키는 자리가 남았습니다" in out,
          f"rc={rc} {out[-400:]}")
    check("지운 *SET_NODE_LIST 의 SID 를 가리키는 카드도 같이 보고한다(공용 스캐너에 없는 축)",
          "*BOUNDARY_SPC_SET" in out and "지운 *SET_NODE_LIST 를 가리키는 자리 [manual]" in out,
          out[-400:])
    src = open(os.path.join(d, "rf.k")).read().splitlines()
    want = next(i + 1 for i, l in enumerate(src) if l.strip().startswith("9001") and "1         1" in l)
    check("보고의 줄 번호가 입력 덱 기준이다(지운 블록만큼 밀리지 않는다)",
          f"line {want} *BOUNDARY_SPC_SET" in out, f"want line {want}; {out[-400:]}")
    w(os.path.join(d, "rfw.yaml"), "model: rf.k\noutput: rfw_out.k\naxis: z\npid_refs: warn\n")
    rc, out = run(binary, d, "cnrb2spring", "rfw.yaml")
    check("pid_refs: warn 은 두 축 모두 rc=0 으로 낮추고 덱을 쓴다",
          rc == 0 and os.path.exists(os.path.join(d, "rfw_out.k")), f"rc={rc} {out[-300:]}")
    rfw = open(os.path.join(d, "rfw_out.k")).read()
    check("덱 머리에 공용 PIDREF 블록과 이 op 의 SETREF 블록이 함께 남는다",
          "$ KOOREMAPPER-PIDREF" in rfw and "$ KOOREMAPPER-SETREF" in rfw, rfw[:600])
    check("공용 스캐너 문구가 restack/merge 라는 사실을 $ 한 줄로 알린다",
          "$ cnrb2spring: 아래 KOOREMAPPER-PIDREF 보고는" in rfw, rfw[:600])
    return d


def body3(binary, d):
    # ── enum·값 검증 ──────────────────────────────────────────────────────
    w(os.path.join(d, "noax.yaml"), "model: m.k\noutput: na.k\n")
    rc, out = run(binary, d, "cnrb2spring", "noax.yaml")
    check("axis 누락은 rc=1 + 허용값 출력(조용히 auto 로 떨어지지 않는다)",
          rc == 1 and "허용값: x, y, z" in out and not os.path.exists(os.path.join(d, "na.k")),
          f"rc={rc} {out[-300:]}")
    w(os.path.join(d, "ba.yaml"), "model: m.k\noutput: ba.k\naxis: auto\n")
    rc, out = run(binary, d, "cnrb2spring", "ba.yaml")
    check("모르는 axis 값은 rc=1 + 허용값 출력",
          rc == 1 and "axis 값 'auto' 를 모릅니다" in out and "허용값: x, y, z" in out, f"rc={rc} {out[-200:]}")
    w(os.path.join(d, "bp.yaml"), "model: m.k\noutput: bp.k\naxis: z\npid_refs: loose\n")
    rc, out = run(binary, d, "cnrb2spring", "bp.yaml")
    check("모르는 pid_refs 값은 rc=1 + 허용값 출력",
          rc == 1 and "허용값: strict, warn" in out, f"rc={rc} {out[-200:]}")

    for key, val, why in (("gap", "0", "0 이하"), ("eps", "0", "0 이하"), ("k_axial", "-1", "음수"),
                          ("gap", "nan", "nan"), ("k_engage", "inf", "inf"),
                          ("curve_range", "0.05", "gap 보다 작음")):
        w(os.path.join(d, "v.yaml"), f"model: m.k\noutput: v.k\naxis: z\n{key}: {val}\n")
        rc, out = run(binary, d, "cnrb2spring", "v.yaml")
        check(f"{key}={val} ({why}) 는 덱을 쓰기 전에 rc=1",
              rc == 1 and not os.path.exists(os.path.join(d, "v.k")), f"rc={rc} {out[-250:]}")
    w(os.path.join(d, "e0.yaml"), "model: m.k\noutput: e0.k\naxis: z\neps: 0\n")
    rc, out = run(binary, d, "cnrb2spring", "e0.yaml")
    check("eps=0 은 '작동축 N1->N2 가 정의되지 않습니다' 를 알린다", "N1->N2" in out, out[-250:])

    w(os.path.join(d, "nn.yaml"), "model: m.k\noutput: nn.k\naxis: z\ngap: 없음\n")
    rc, out = run(binary, d, "cnrb2spring", "nn.yaml")
    check("수가 아닌 값은 조용히 무시하지 않고 rc=1", rc == 1 and "수로 읽을 수 없습니다" in out,
          f"rc={rc} {out[-250:]}")
    w(os.path.join(d, "tp.yaml"), "model: m.k\noutput: tp.k\naxis: z\ntarget_pids: [1201, 9999]\n")
    rc, out = run(binary, d, "cnrb2spring", "tp.yaml")
    check("덱에 없는 target_pids 는 rc=1", rc == 1 and "9999" in out, f"rc={rc} {out[-250:]}")
    w(os.path.join(d, "bl.yaml"), "model: m.k\noutput: bl.k\naxis: z\ntarget_pids:\n  - 1201\n")
    rc, out = run(binary, d, "cnrb2spring", "bl.yaml")
    check("블록 목록 target_pids('- 1201')도 읽는다 (플랫폼 yaml.dump 가 내는 꼴)",
          rc == 0 and "PID 1201:" in out, f"rc={rc} {out[-250:]}")
    w(os.path.join(d, "blx.yaml"), "model: m.k\noutput: blx.k\naxis: z\ntarget_pids:\n  - 9999\n")
    rc, out = run(binary, d, "cnrb2spring", "blx.yaml")
    check("블록 목록이 조용히 버려지지 않는다 — 덱에 없는 PID 면 rc=1",
          rc == 1 and "9999" in out, f"rc={rc} {out[-250:]}")

    w(os.path.join(d, "op.yaml"), "model: m.k\noutput: op.k\naxis: z\noperations:\n  - type: restack\n")
    rc, out = run(binary, d, "cnrb2spring", "op.yaml")
    check("assemble 설정(operations:)을 붙여넣으면 rc=1 로 알린다",
          rc == 1 and "flat 설정 op" in out, f"rc={rc} {out[-250:]}")
    w(os.path.join(d, "uk.yaml"), "model: m.k\noutput: uk.k\naxis: z\nk_shear: 1.0\n")
    rc, out = run(binary, d, "cnrb2spring", "uk.yaml")
    check("모르는 키는 [WARN] 만 내고 계속한다", rc == 0 and "알 수 없는 키 'k_shear'" in out,
          f"rc={rc} {out[-250:]}")
    w(os.path.join(d, "noout.yaml"), "model: m.k\naxis: z\n")
    rc, out = run(binary, d, "cnrb2spring", "noout.yaml")
    check("output 이 비면 rc=1", rc == 1 and "'output' 이 없습니다" in out, f"rc={rc} {out[-200:]}")

    # ── 쪼갤 수 없는 CNRB ─────────────────────────────────────────────────
    one = shell_deck().replace("".join("%10d" % v for v in (1, 2, 4, 5, 11, 12, 14, 15)),
                               "".join("%10d" % v for v in (1, 2, 4, 5)))
    w(os.path.join(d, "one.k"), one)
    w(os.path.join(d, "one_x.yaml"), "model: one.k\noutput: one_x.k\naxis: z\ntarget_pids: [1201]\n")
    rc, out = run(binary, d, "cnrb2spring", "one_x.yaml")
    check("한 파트만 잇는 CNRB 를 target_pids 로 명시하면 rc=1 + 파트 목록",
          rc == 1 and "잇는 파트가 1개입니다" in out and "파트: 500" in out, f"rc={rc} {out[-300:]}")
    w(os.path.join(d, "one_a.yaml"), "model: one.k\noutput: one_a.k\naxis: z\n")
    rc, out = run(binary, d, "cnrb2spring", "one_a.yaml")
    check("자동 선택이면 [WARN] 로 건너뛰고, 변환이 0개면 rc=1 (조용한 성공 없음)",
          rc == 1 and "건너뜁니다" in out and "변환할 CNRB 가 없습니다" in out, f"rc={rc} {out[-300:]}")

    w(os.path.join(d, "dr.k"), shell_deck(drflag=7))
    w(os.path.join(d, "dr.yaml"), "model: dr.k\noutput: dr.k.out\naxis: z\ntarget_pids: [1201]\n")
    rc, out = run(binary, d, "cnrb2spring", "dr.yaml")
    check("DRFLAG/RRFLAG 가 0 이 아니면 rc=1 (DOF 해제를 두 강체에 나눌 근거가 없다)",
          rc == 1 and "DRFLAG/RRFLAG" in out, f"rc={rc} {out[-250:]}")

    gen = shell_deck(set_kw="*SET_NODE_LIST_GENERATE")
    w(os.path.join(d, "ge.k"), gen)
    w(os.path.join(d, "ge.yaml"), "model: ge.k\noutput: ge.k.out\naxis: z\ntarget_pids: [1201]\n")
    rc, out = run(binary, d, "cnrb2spring", "ge.yaml")
    check("_GENERATE 세트는 조용히 틀리게 읽지 않고 rc=1", rc == 1 and "_GENERATE/_COLUMN" in out,
          f"rc={rc} {out[-250:]}")

    sh = shell_deck().replace("%8d%8d%8d%8d%8d%8d" % (11, 700, 11, 12, 15, 14),
                              "%8d%8d%8d%8d%8d%8d" % (11, 700, 1, 2, 5, 4))
    w(os.path.join(d, "sh.k"), sh)
    w(os.path.join(d, "sh.yaml"), "model: sh.k\noutput: sh.k.out\naxis: z\ntarget_pids: [1201]\n")
    rc, out = run(binary, d, "cnrb2spring", "sh.yaml")
    check("두 파트가 공유절점으로 이미 붙어 있으면 rc=1 (유격이 물리적으로 불가능하다)",
          rc == 1 and "공유절점" in out, f"rc={rc} {out[-300:]}")

    cm = shell_deck().replace("*SET_NODE_LIST_TITLE\nhole nodes\n%10d" % 9001,
                              "*SET_NODE_LIST_TITLE\nhole nodes\n9001,0.0,0.0,0.0,0.0")
    w(os.path.join(d, "cm.k"), cm)
    w(os.path.join(d, "cm.yaml"), "model: cm.k\noutput: cm.k.out\naxis: z\n")
    rc, out = run(binary, d, "cnrb2spring", "cm.yaml")
    check("콤마 자유형식 줄은 조용히 칸을 어긋나게 읽지 않고 rc=1",
          rc == 1 and "콤마 자유형식" in out, f"rc={rc} {out[-250:]}")

    # ── 상대 경로는 YAML 폴더 기준 ────────────────────────────────────────
    sub = os.path.join(d, "sub")
    os.makedirs(sub, exist_ok=True)
    w(os.path.join(sub, "s.yaml"), "model: ../m.k\noutput: ../sub_out.k\naxis: z\n")
    rc, out = run(binary, d, "cnrb2spring", "sub/s.yaml")
    check("YAML 안 상대 경로는 YAML 폴더 기준이다",
          rc == 0 and os.path.exists(os.path.join(d, "sub_out.k")), f"rc={rc} {out[-250:]}")

    # ── 기본값 고지 ───────────────────────────────────────────────────────
    w(os.path.join(d, "df.yaml"), "model: m.k\noutput: df.k\naxis: z\n")
    rc, out = run(binary, d, "cnrb2spring", "df.yaml")
    check("기본값을 쓰면 실측이 아니라는 사실을 콘솔 한 줄로 알린다",
          "기본값 사용:" in out and "labeled assumption" in out, out[-300:])
    check("[ERROR] 를 찍지 않았으면 rc=0 이다", rc == 0 and "[ERROR]" not in out, f"rc={rc}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    with tempfile.TemporaryDirectory() as tmp:
        print("[덱 구조 — 칸 폭·칸 수·분할·삭제]")
        d = body(binary, tmp)
        print("[파싱 함정·ID 충돌·죽은 참조]")
        body2(binary, d)
        print("[값 검증·쪼갤 수 없는 CNRB·경로]")
        body3(binary, d)
    print()
    if FAILS:
        print(f"FAIL {len(FAILS)}")
        for f in FAILS:
            print("  -", str(f)[:300])
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
