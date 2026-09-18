# cnrb2spring 회귀 시험 — 덱 구조(칸 폭·칸 수·좌표계·곡선·분할·삭제·충돌·멱등)를 문자열로 직접 못 박는다
"""
사용: python3 tools/regress/test_cnrb2spring.py <KooRemapper 바이너리>

배경
  - LS-DYNA 라이선스가 없어 솔버로 검증할 수 없다. 그래서 이 시험은 산출 덱의 칸 폭·칸 수·참조 정합성을
    직접 읽어 확인한다. 현장에서 실제로 당한 함정이 그대로 단언이 된다.
      *ELEMENT_BEAM 은 8칸이다(다른 카드는 10칸) — 10칸으로 쓰면 7자리 EID 가 잘려
      'beam element ... has an undefined PID' 가 난다.
      *SECTION_BEAM 은 ELFORM=6 일 때 Card 2f(VOL,INER,CID)가 필수다. VOL·INER 가 0 이면
      type 6 빔의 시간증분 계산이 무너진다.
      *MAT_NONLINEAR_ELASTIC_DISCRETE_BEAM 은 Card 1~3 이 전부 필수다 — 빼면 다음 키워드 줄을 먹는다.
      블록 사이에 빈 줄이 들어가면 *ELEMENT_BEAM 이 빈 줄을 요소로 읽는다.
      곡선 ID 0 은 '그 자유도 자유' 다 — 회전을 묶으려면 LCIDRR/RS/RT 에 곡선을 줘야 한다.
  - 축 분리는 노드 간격이 아니라 *SECTION_BEAM 의 CID(로컬 좌표계)가 세운다. 그래서 두 팬텀 노드를
    같은 자리에 둘 수 있고(제로길이 빔), 상대변위가 아무리 커도 r/s/t 가 섞이지 않는다.
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


def curve_map(text):
    """LCID -> [(a,o), ...]. 헤더 줄(80자)과 점 줄(40자)을 고정폭으로 가른다."""
    out, cur, lc = {}, None, None
    for ln in text.splitlines():
        if ln.startswith("*"):
            cur = "C" if ln.strip().upper() == "*DEFINE_CURVE" else None
            lc = None
            continue
        if cur != "C" or ln.startswith("$") or not is_data(ln):
            continue
        if len(ln) == 80:
            lc = int(ln[:10])
            out[lc] = []
        elif lc is not None:
            out[lc].append((float(ln[:20]), float(ln[20:])))
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
    check("Side A 세트 = 하판 노드 4개 + 팬텀 1개", sorted(setmap[sA]) == [1, 2, 4, 5, 90000001],
          str(setmap[sA]))
    check("Side B 세트 = 상판 노드 4개 + 팬텀 1개", sorted(setmap[sB]) == [11, 12, 14, 15, 90000002],
          str(setmap[sB]))

    # ── *NODE 팬텀 좌표: 두 노드가 정확히 같은 자리(제로길이 빔) ──────────
    ph = {}
    for l in B.get("*NODE", []):
        nid = int(l[:8])
        if nid >= 90000000:
            ph[nid] = (float(l[8:24]), float(l[24:40]), float(l[40:56]))
    check("팬텀 노드가 2개다 (스프링 3개 방식의 4개에서 줄었다)", len(ph) == 2, str(ph))
    check("두 팬텀 노드가 정확히 같은 좌표다 — MAT_067 은 zero length beam 을 전제하고 방향은 "
          "CID 가 정한다(eps 개념이 사라졌다)",
          len(ph) == 2 and ph.get(90000001) == ph.get(90000002), str(ph))

    # ── *ELEMENT_BEAM: 8칸 ────────────────────────────────────────────────
    eb = B.get("*ELEMENT_BEAM", [])
    check("*ELEMENT_BEAM 데이터 줄이 1개다 (조인트당 빔 하나)", len(eb) == 1, str(eb))
    parts = {int(l[:10]) for l in B.get("*PART", []) if len(l.rstrip()) <= 30}
    nids = {int(l[:8]) for l in B.get("*NODE", [])}
    ok8 = True
    for l in eb:
        eid, pid, n1, n2 = (int(l[i:i + 8]) for i in range(0, 32, 8))
        if not (eid >= 9900001 and pid in parts and n1 in nids and n2 in nids):
            ok8 = False
    check("*ELEMENT_BEAM 을 8칸으로 잘라 읽으면 EID/PID/N1/N2 가 모두 성립한다 (10칸이면 전부 깨진다)",
          ok8, str(eb))
    check("*ELEMENT_BEAM 줄 길이가 32(=8*4)다 — N3 와 릴리즈 칸(RT1/RR1/RT2/RR2)은 비운다. "
          "릴리즈를 걸면 그 노드를 nodal rigid body 에 넣을 수 없다",
          all(len(l) == 32 for l in eb), str([len(l) for l in eb]))
    n1, n2 = int(eb[0][16:24]), int(eb[0][24:32])
    check("빔의 N1 은 Side A 세트 팬텀, N2 는 Side B 세트 팬텀이다",
          n1 in setmap[sA] and n2 in setmap[sB], f"{n1} {n2}")

    # ── 10칸 카드 ─────────────────────────────────────────────────────────
    sb = B.get("*SECTION_BEAM", [])
    check("*SECTION_BEAM 데이터 줄이 2줄이다 (Card 1 + ELFORM=6 전용 Card 2f)", len(sb) == 2, str(sb))
    check("*SECTION_BEAM Card 1 의 SECID 가 10칸 첫 칸이고 ELFORM=6(discrete beam)이다",
          len(sb) == 2 and int(sb[0][:10]) == 990001 and int(sb[0][10:20]) == 6, str(sb))
    check("SCOOR 칸이 비어 있다(=0.0) — |SCOOR| <= 1 이어야 제로길이 빔으로 다뤄진다",
          len(sb) == 2 and sb[0][50:60].strip() == "", str(sb[0]))
    vol = float(sb[1][:10]) if len(sb) == 2 else 0.0
    iner = float(sb[1][10:20]) if len(sb) == 2 else 0.0
    secCid = int(sb[1][20:30]) if len(sb) == 2 else 0
    check("Card 2f 의 VOL·INER 가 0 이 아니다 — type 6 빔의 병진·회전 시간증분이 이 값으로 계산된다",
          vol > 0.0 and iner > 0.0, str(sb[-1]))

    cs = B.get("*DEFINE_COORDINATE_SYSTEM", [])
    check("*DEFINE_COORDINATE_SYSTEM 이 Card 1 + Card 2 두 줄이다", len(cs) == 2, str(cs))
    check("*SECTION_BEAM 의 CID 가 그 좌표계를 가리킨다 (CID=0 이면 전역계라 axis 가 무시된다)",
          len(cs) == 2 and secCid == int(cs[0][:10]), f"{secCid} / {cs}")
    xl = tuple(float(cs[0][i:i + 10]) for i in (40, 50, 60)) if len(cs) == 2 else ()
    xp = tuple(float(cs[1][i:i + 10]) for i in (0, 10, 20)) if len(cs) == 2 else ()
    check("axis=z 면 로컬 x(=빔의 r)가 전역 Z 다 — 축 분리를 노드 간격이 아니라 이 좌표계가 세운다",
          xl == (0.0, 0.0, 1.0), str(xl))
    check("로컬 xy평면 점이 전역 X 라 s=X, t=Y 가 된다", xp == (1.0, 0.0, 0.0), str(xp))

    mb = B.get("*MAT_NONLINEAR_ELASTIC_DISCRETE_BEAM", [])
    check("*MAT_067 데이터 줄이 3줄이다 (Card 1~3 전부 필수 — 빈 줄 대신 0 을 적는다)", len(mb) == 3, str(mb))
    check("RO=1.0 이라 *SECTION_BEAM 의 VOL 이 곧 요소 질량이다",
          len(mb) == 3 and float(mb[0][10:20]) == 1.0, str(mb[:1]))
    lc = [int(mb[0][i:i + 10]) for i in range(20, 80, 10)] if len(mb) == 3 else [0] * 6
    check("LCIDTR(r)=축 곡선, LCIDTS=LCIDTT(s,t)=전단 곡선 — 자유도마다 다른 곡선이 붙었다",
          lc[0] == 990001 and lc[1] == lc[2] == 990002, str(lc))
    check("회전 3자유도(LCIDRR/RS/RT)에 회전 곡선이 붙었다 — 곡선 ID 0 이면 회전이 자유다",
          lc[3] == lc[4] == lc[5] == 990003, str(lc))
    check("*MAT_067 Card 2(감쇠)·Card 3(프리로드)가 줄로 존재하고 값이 0 이다",
          len(mb) == 3 and set(mb[1].split()) == {"0"} and
          all(float(v) == 0.0 for v in mb[2].split()), str(mb[1:]))
    pt = B.get("*PART", [])
    check("*PART 데이터 줄이 10칸이고 MID 가 0 이 아니다",
          all(int(l[20:30]) != 0 for l in pt if len(l.rstrip()) <= 30), str(pt))
    check("스프링 파트 2개(전단·축)가 빔 파트 1개로 줄었다",
          len([l for l in pt if len(l.rstrip()) <= 30 and int(l[:10]) == 990001]) == 1, str(pt))

    # ── *DEFINE_CURVE ─────────────────────────────────────────────────────
    curves = curve_map(deck)
    check("*DEFINE_CURVE 가 3개(축·전단·회전)다", len(curves) == 3, str(sorted(curves)))
    check("축 곡선 990001 = (-1,-1e7) (1,1e7) — 유격 없이 기울기 k_axial",
          curves.get(990001) == [(-1.0, -1e7), (1.0, 1e7)], str(curves.get(990001)))
    check("전단 곡선 990002 = (-1,-9e4) (-0.1,0) (0.1,0) (1,9e4) — ±gap 구간 힘 0, 밖 기울기 k_engage",
          curves.get(990002) == [(-1.0, -90000.0), (-0.1, 0.0), (0.1, 0.0), (1.0, 90000.0)],
          str(curves.get(990002)))
    check("회전 곡선 990003 = (-1,-1e7) (1,1e7) [rad] — 원 CNRB 의 회전 구속을 되살린다",
          curves.get(990003) == [(-1.0, -1e7), (1.0, 1e7)], str(curves.get(990003)))

    # ── 빈 줄 없음 ────────────────────────────────────────────────────────
    lines = deck.splitlines()
    i0 = next(i for i, l in enumerate(lines) if l.startswith("$ === cnrb2spring"))
    check("삽입 블록 안에 빈 줄이 하나도 없다 (*ELEMENT_BEAM 이 요소로 오인한다)",
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
    axk = open(os.path.join(d, "ax_out.k")).read() if rc == 0 else ""
    csx = blocks(axk).get("*DEFINE_COORDINATE_SYSTEM", [])
    check("axis=x 면 로컬 x(=빔의 r)가 전역 X, xy평면 점이 전역 Y 다 — 좌표계가 axis 를 따라간다",
          len(csx) == 2 and
          tuple(float(csx[0][i:i + 10]) for i in (40, 50, 60)) == (1.0, 0.0, 0.0) and
          tuple(float(csx[1][i:i + 10]) for i in (0, 10, 20)) == (0.0, 1.0, 0.0), str(csx))

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
    # 좌표계는 이번 방식에서 새로 생긴 네임스페이스다 — 겹치면 LS-DYNA 가 먼저 읽은 CID 를 써
    # 빔의 r 축이 엉뚱한 방향으로 서고, 축 분리가 조용히 무너진다.
    cdc = ("*DEFINE_COORDINATE_SYSTEM\n"
           "%10d%10.1f%10.1f%10.1f%10.1f%10.1f%10.1f%10d\n%10.1f%10.1f%10.1f"
           % (990001, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0, 0.0, 1.0, 0.0))
    w(os.path.join(d, "cs.k"), shell_deck(extra_cards=cdc))
    w(os.path.join(d, "cs.yaml"), "model: cs.k\noutput: cs_out.k\naxis: z\n")
    rc, out = run(binary, d, "cnrb2spring", "cs.yaml")
    check("좌표계(CID) 충돌도 rc=1 로 잡는다",
          rc == 1 and "좌표계 ID 가 원본 덱과 겹칩니다" in out and "990001" in out and
          not os.path.exists(os.path.join(d, "cs_out.k")), f"rc={rc} {out[-300:]}")
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

    for key, val, why in (("gap", "0", "0 이하"), ("k_rot", "-1", "음수"), ("k_axial", "-1", "음수"),
                          ("gap", "nan", "nan"), ("k_engage", "inf", "inf"),
                          ("k_rot", "nan", "nan"),
                          ("curve_range", "0.05", "gap 보다 작음")):
        w(os.path.join(d, "v.yaml"), f"model: m.k\noutput: v.k\naxis: z\n{key}: {val}\n")
        rc, out = run(binary, d, "cnrb2spring", "v.yaml")
        check(f"{key}={val} ({why}) 는 덱을 쓰기 전에 rc=1",
              rc == 1 and not os.path.exists(os.path.join(d, "v.k")), f"rc={rc} {out[-250:]}")

    # k_rot=0 만은 값 검증을 통과한다 — '회전 3자유도를 풀어 둔다' 는 뜻이기 때문이다.
    # MAT_067 은 곡선 ID 0 인 자유도에 힘을 만들지 않으므로 회전 곡선을 아예 내지 않는다.
    w(os.path.join(d, "kr0.yaml"), "model: m.k\noutput: kr0.k\naxis: z\nk_rot: 0\n")
    rc, out = run(binary, d, "cnrb2spring", "kr0.yaml")
    kr0 = open(os.path.join(d, "kr0.k")).read() if rc == 0 else ""
    mb0 = blocks(kr0).get("*MAT_NONLINEAR_ELASTIC_DISCRETE_BEAM", [])
    lc0 = [int(mb0[0][i:i + 10]) for i in range(50, 80, 10)] if mb0 else [-1]
    check("k_rot=0 은 rc=0 이고 LCIDRR/RS/RT 를 0(=자유)으로 두며 회전 곡선을 내지 않는다",
          rc == 0 and lc0 == [0, 0, 0] and len(curve_map(kr0)) == 2, f"rc={rc} {lc0}")
    check("k_rot=0 이면 '회전 3자유도를 풀었습니다' 를 [WARN] 로 알린다",
          "회전 3자유도를 풀었습니다" in out, out[-300:])

    # eps 는 스프링 3개 시절 키다 — 제로길이 빔에는 쓰이지 않으니 조용히 먹지 않고 그 사실을 알린다
    w(os.path.join(d, "eps.yaml"), "model: m.k\noutput: eps.k\naxis: z\neps: 0.001\n")
    rc, out = run(binary, d, "cnrb2spring", "eps.yaml")
    check("옛 키 eps 는 rc=0 으로 무시하되 '더 이상 쓰지 않습니다' 를 [WARN] 로 알린다",
          rc == 0 and "'eps' 는 더 이상 쓰지 않습니다" in out, f"rc={rc} {out[-300:]}")

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
