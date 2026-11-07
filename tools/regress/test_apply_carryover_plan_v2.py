#!/usr/bin/env python3
# apply_carryover_plan 이 StepForge 이월 계획 판 2(덱 자리 · 인클루드 닫힘 · 새 셸 섹션 · refused_transform)를 받고 계약 밖은 거절하는지 보는 회귀 시험
"""`apply_carryover_plan` 판 2 — StepForge 요청서 §10(그쪽 main 60f8969 · 코드 4295f7d).

왜 이 시험이 있나 (2026-11-07).

  StepForge 가 계획 파일을 판 2 로 올렸다 — 줄마다 그 PID 의 덱 자리(`parts[].deck`) · 덱의 `*INCLUDE` 닫힘(`deck.includes`) ·
  셸 두께가 바뀐 모프의 새 섹션(`field.new_section` + `section_<PID>.k`) · 강체가 아닌 옮김은 review(`refused_transform`) ·
  `deck.deck_from` · `summary.sections`. 배포 판(752fa2b)은 실물 둘을 판 2 · 모르는 칸으로 거절했다(엄격 읽기가 설계대로).
  사용자 결정 둘(11-07) — ① 인클루드 덱은 deck.includes 를 대조해 받되 **주 덱만 고친다**(고칠 자리가 인클루드에 있으면 거절하고
  목록) ② 줄의 덱 자리가 우리 셈과 다르면 **손대는 줄은 거절 · keep/review 는 경고**.

신탁(이 시험이 따로 잰다 — 바이너리의 보고를 믿지 않는다).
  · 덱 자리 — 그쪽 `KDeck.part_ranges()` · `deck_ranges()` 의 정의를 이 시험이 덱 글자에서 다시 센다(`places`). 실물 판의 값과
    이 셈이 같은지도 본다(B-0)
  · 새 셸 섹션 — §10.5 의 `section_4.k` 전문(329 바이트)을 손으로 짓고, 산출의 `*PART` SECID · 새 카드 · 옛 카드가 남는지 본다
  · 인클루드 — 진리값 판 덱에서 파트를 `inc/*.k` 로 뺀 덱을 짓는다(그쪽 회귀 `test_a89_plan_v2.py` 의 꼴)

무엇을 보나.
  A 실물 둘(바깥 덱 fc160119a36e · 메시 덱 f8ff42845904) · B 진리값 판을 판 2 로 · C 칸 표(판마다) · D 덱 자리 ·
  E 새 셸 섹션(§10.5) · F 인클루드(주 덱만 고침) · G refused_transform

usage: test_apply_carryover_plan_v2.py <KooRemapper 바이너리>
"""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples", "apply_carryover_plan")
DATA = os.path.join(HERE, "data", "apply_carryover_plan")
LIVE_RAW = os.path.join(DATA, "live_v2_raw")      # plan.json 만 — 덱 · 변위장은 진리값 판(EX)과 바이트가 같다(계획의 지문이 지킨다)
LIVE_MESH = os.path.join(DATA, "live_v2_mesh")
FAILS, OKS = [], []
OP = "apply_carryover_plan"
TMP = ""

# 요청서 §10.5 의 `section_4.k` 전문 — 진리값 판 CAN(SECID 4 · 두께 0.4)의 옛 카드를 옮겨 SECID 10 · T1~T4 0.6 만 바꾼 카드
SECTION_4 = ("*KEYWORD\n"
             "$# StepForge — 이월 모프 PID 4 의 새 셸 섹션(옛 SECID 4) — deck.k\n"
             "*SECTION_SHELL_TITLE\n"
             "CAN#4_sec\n"
             "$#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp\n"
             "        10         2         1         2\n"
             "$#      t1        t2        t3        t4\n"
             "       0.6       0.6       0.6       0.6\n"
             "*END\n")


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:500]))
    print("  %-70s %s" % (name[:70], "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def write(path, text, newline="\n"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline=newline, encoding="utf-8") as f:
        f.write(text)


def read(path):
    return open(path, encoding="utf-8", newline="").read()


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def stage(name, src=EX, extra=()):
    d = os.path.join(TMP, name)
    shutil.copytree(src, d)
    for f in extra:
        shutil.copy(f, d)
    return d


def plan_load(d):
    return json.load(open(os.path.join(d, "plan.json"), encoding="utf-8"))


def plan_save(d, p):
    write(os.path.join(d, "plan.json"), json.dumps(p, ensure_ascii=False, indent=1))


def put_file(d, p, name):
    fp = os.path.join(d, name)
    p["files"][name] = {"sha256": sha(fp), "bytes": os.path.getsize(fp)}


def apply_case(binary, d, output="deck_applied.k", report="deck_applied_carryover.json"):
    write(os.path.join(d, "a.yaml"), "model: deck.k\nplan: plan.json\noutput: %s\n" % output)
    rc, out = run(binary, d, OP, "a.yaml")
    rp = os.path.join(d, report)
    rep = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}
    return rc, out, rep


def kinds(rep, pid=None):
    return {p["kind"] for p in rep.get("problems", []) if pid is None or p.get("pid") == pid}


def details(rep, kind, pid=None):
    return " ".join(x["detail"] for x in rep.get("problems", []) if x["kind"] == kind and (pid is None or x.get("pid") == pid))


def warn_kinds(rep):
    return {(w.get("pid"), w["kind"]) for w in rep.get("warnings", [])}


def refused(name, rc, out, rep, d, kind, pid=None, out_name="deck_applied.k"):
    ok = (rc == 1 and rep.get("ok") is False and kind in kinds(rep, pid) and
          not os.path.exists(os.path.join(d, out_name)) and rep.get("deck", {}).get("sha256_out") is None)
    return check(name, ok, (rc, sorted(kinds(rep)), out[-500:]))


def read_deck(path):
    """절점(번호 → 좌표 글자 · 값) · 요소(번호 → PID · 절점) · *PART(PID → SECID · MID · 제목) · 섹션(SECID → 키워드 · ELFORM)."""
    nodes, elems, parts, secs, mats = {}, {}, {}, {}, set()
    kw, data = "", []

    def flush():
        if kw in ("*PART", "*PART_TITLE"):
            for k in range(0, len(data) - 1, 2):
                c = data[k + 1]
                parts[int(c[0:10])] = (int(c[10:20]), int(c[20:30]), data[k].strip())
        elif kw.startswith("*SECTION_"):
            t = 1 if "_TITLE" in kw else 0
            if len(data) > t:
                secs[int(data[t][0:10])] = (kw, int(data[t][10:20]))
        elif kw.startswith("*MAT_"):
            t = 1 if "_TITLE" in kw else 0
            if len(data) > t:
                mats.add(int(data[t][0:10]))

    for ln in open(path, encoding="utf-8", newline=""):
        ln = ln.rstrip("\r\n")
        if ln.startswith("*"):
            flush()
            kw, data = ln.strip().split()[0].upper(), []
            continue
        if ln.startswith("$"):
            continue
        if kw == "*NODE" and ln.strip():
            nodes[int(ln[:8])] = (ln[8:56], tuple(float(ln[8 + 16 * k:24 + 16 * k]) for k in range(3)))
        elif kw in ("*ELEMENT_SOLID", "*ELEMENT_SHELL") and ln.strip():
            f = [int(ln[i:i + 8]) for i in range(0, len(ln), 8) if ln[i:i + 8].strip()]
            elems[f[0]] = (f[1], f[2:])
        elif kw.startswith("*PART") or kw.startswith("*SECTION_") or kw.startswith("*MAT_"):
            data.append(ln)
    flush()
    return nodes, elems, parts, secs, mats


def read_closure(main, files):
    """주 덱 + 인클루드 파일(이 시험이 지은 것 — 이름 그대로)을 합친 읽기(닫힘 차례 · 같은 번호면 뒤의 것)."""
    acc = [{}, {}, {}, {}, set()]
    for p in [main] + list(files):
        got = read_deck(p)
        for a, b in zip(acc[:4], got[:4]):
            a.update(b)
        acc[4] |= got[4]
    return tuple(acc)


def places(elems, parts):
    """그쪽 `KDeck.part_ranges()` · `carryover_build.deck_ranges()` 의 정의 — 요소가 가리킨 **서로 다른** 절점(0 제외)의 최소 · 최대 · 수 ·
    요소 번호의 최소 · 최대 · 수 · 둘 다 빈 데가 없나 · `*PART` SECID · MID(없으면 null · 요소가 없으면 범위 null)."""
    acc = {}
    for eid, (pid, ns) in elems.items():
        a = acc.setdefault(pid, [set(), []])
        a[0].update(n for n in ns if n)
        a[1].append(eid)
    out = {}
    for pid in set(acc) | set(parts):
        sec, mid = (parts[pid][0], parts[pid][1]) if pid in parts else (None, None)
        if pid not in acc:
            out[pid] = {"node": None, "node_count": 0, "elem": None, "elem_count": 0, "contiguous": None, "secid": sec, "mid": mid}
            continue
        ns, es = acc[pid]
        node = [min(ns), max(ns)] if ns else None
        out[pid] = {"node": node, "node_count": len(ns), "elem": [min(es), max(es)], "elem_count": len(es),
                    "contiguous": bool(node is not None and node[1] - node[0] + 1 == len(ns) and max(es) - min(es) + 1 == len(es)),
                    "secid": sec, "mid": mid}
    return out


def failed_of(row):
    """그쪽 `carryover_build._failed` 와 같은 셈."""
    n = sum(1 for k in ("fragment", "instead") if isinstance(row.get(k), dict) and row[k].get("ok") is False)
    fld = row.get("field")
    if isinstance(fld, dict) and (not fld.get("file") or not (fld.get("check") or {}).get("ok", False)):
        n += 1
    if isinstance(fld, dict) and isinstance(fld.get("new_section"), dict) and not fld["new_section"].get("file"):
        n += 1
    return n


def resummarize(p):
    """그쪽 `build` 의 summary 셈(actions · added · fields · fragments · sections · failed)으로 다시 적는다."""
    counts = {}
    for r in p["parts"]:
        counts[r["action"]] = counts.get(r["action"], 0) + 1
    rows = p["parts"] + p["added"]
    p["summary"] = {"actions": counts, "added": len(p["added"]),
                    "fields": sum(1 for r in p["parts"] if (r.get("field") or {}).get("file")),
                    "fragments": sum(1 for r in rows for k in ("fragment", "instead") if (r.get(k) or {}).get("file")),
                    "sections": sum(1 for r in p["parts"] if ((r.get("field") or {}).get("new_section") or {}).get("file")),
                    "failed": sum(failed_of(r) for r in rows)}


def to_v2(d, include_files=(), deck_from="raw"):
    """진리값 판(판 1) 계획을 판 2 로 — deck_from · includes(이 시험이 지은 인클루드) · 줄마다 덱 자리(닫힘째 센 신탁) · 모프 줄 new_section
    null · summary(여섯 칸). 덱 · 동반 파일 지문도 다시 박는다."""
    p = plan_load(d)
    main = os.path.join(d, "deck.k")
    _n, elems, parts, _s, _m = read_closure(main, [os.path.join(d, f) for f in include_files])
    pl = places(elems, parts)
    p["version"] = 2
    dk = p["deck"]
    p["deck"] = {"project_id": dk["project_id"], "relpath": dk["relpath"], "deck_from": deck_from, "sha256": sha(main),
                 "includes": [{"relpath": f, "sha256": sha(os.path.join(d, f))} for f in include_files],
                 "max": dk["max"], "unread_cards": dk["unread_cards"]}
    for r in p["parts"]:
        r["deck"] = pl[r["pid"]]
        if r["action"] == "morph":
            r["field"].setdefault("new_section", None)
    resummarize(p)
    plan_save(d, p)
    return p


def reseal_deck(d, p=None):
    p = p or plan_load(d)
    p["deck"]["sha256"] = sha(os.path.join(d, "deck.k"))
    plan_save(d, p)
    return p


def read_field(d, head):
    b = open(os.path.join(d, head["file"]), "rb").read()
    lay = {e["name"]: e for e in head["layout"]}
    n = head["nodes"]
    ids = struct.unpack_from("<%dI" % n, b, lay["node"]["offset"])
    disp = struct.unpack_from("<%dd" % (3 * n), b, lay["disp"]["offset"])
    return ids, disp


def pid_nodes(elems):
    out = {}
    for _eid, (pid, ns) in elems.items():
        out.setdefault(pid, set()).update(n for n in ns if n > 0)
    return out


def count_by_pid(elems):
    out = {}
    for _eid, (pid, _ns) in elems.items():
        out[pid] = out.get(pid, 0) + 1
    return out


def blocks(lines):
    """키워드 줄마다 [시작, 끝) — 끝은 다음 키워드 줄."""
    ks = [i for i, ln in enumerate(lines) if ln.startswith("*")]
    return [(a, ks[k + 1] if k + 1 < len(ks) else len(lines), lines[a].strip().upper()) for k, a in enumerate(ks)]


def split_include(d, name, pid, move_defs=False, extra=""):
    """덱에서 PID 의 요소(와 move_defs 면 그 절점 · *PART · *SECTION · *MAT)를 `name` 으로 빼고 주 덱 *END 앞에 *INCLUDE 를 둔다."""
    main = os.path.join(d, "deck.k")
    lines = read(main).split("\n")
    _n, elems, _p, _s, _m = read_deck(main)
    mine_e = {e for e, (p, _ns) in elems.items() if p == pid}
    mine_n = pid_nodes(elems)[pid] if move_defs else set()
    keep, inc_nodes, inc_elems, inc_defs = [], [], [], []
    for a, b, kw in blocks(lines):
        body = lines[a:b]
        if kw.startswith("*NODE") or kw.startswith("*ELEMENT_"):
            keep.append(body[0])
            for ln in body[1:]:
                if ln.strip() and not ln.startswith("$"):
                    ident = int(ln[:8])
                    if kw.startswith("*NODE") and ident in mine_n:
                        inc_nodes.append(ln)
                        continue
                    if kw.startswith("*ELEMENT_") and ident in mine_e:
                        inc_elems.append(ln)
                        continue
                keep.append(ln)
            continue
        if move_defs and kw.split()[0] in ("*PART", "*SECTION_SOLID_TITLE", "*MAT_ELASTIC_TITLE"):
            data = [ln for ln in body[1:] if not ln.startswith("$")]
            first = data[1] if kw.split()[0] in ("*PART", "*SECTION_SOLID_TITLE", "*MAT_ELASTIC_TITLE") else data[0]
            if int(first[:10]) == pid:
                inc_defs += body
                continue
        if kw.split()[0] == "*END":
            keep.append("*INCLUDE")
            keep.append(name)
        keep += body
    inc = ["*KEYWORD"]
    if inc_nodes:
        inc += ["*NODE"] + inc_nodes
    if inc_elems:
        inc += ["*ELEMENT_SOLID"] + inc_elems
    inc += inc_defs
    if extra:
        inc += extra.rstrip("\n").split("\n")
    inc.append("*END")
    write(os.path.join(d, name), "\n".join(inc) + "\n")
    write(main, "\n".join(keep))
    return len(inc_elems), len(inc_nodes)


def can_morph(d, p, new_section, thickness=(0.4, 0.6)):
    """CAN(PID 4 · 셸)을 remesh 에서 morph 로 — 그 PID 요소 절점 전부의 변위장(0 변위)과 new_section."""
    _n, e0, _p, _s, _m = read_deck(os.path.join(d, "deck.k"))
    can = sorted(pid_nodes(e0)[4])
    N = len(can)
    off_d = (4 * N + 7) // 8 * 8
    off_k = off_d + 24 * N
    blob = struct.pack("<%dI" % N, *can) + b"\0" * (off_d - 4 * N) + struct.pack("<%dd" % (3 * N), *([0.0] * 3 * N)) + bytes([1] * N)
    open(os.path.join(d, "field_4.bin"), "wb").write(blob)
    tpl = next(r for r in p["parts"] if r["pid"] == 2)["field"]
    for r in p["parts"]:
        if r["pid"] == 4:
            r.pop("fragment", None)
            r["action"] = "morph"
            f = json.loads(json.dumps(tpl))
            f.update({"file": "field_4.bin", "nodes": N, "bytes": len(blob), "surface_nodes": N, "max_disp": 0.0})
            f["layout"] = [{"name": "node", "dtype": "<u4", "offset": 0, "count": N},
                           {"name": "disp", "dtype": "<f8", "offset": off_d, "shape": [N, 3], "unit": "mm"},
                           {"name": "kind", "dtype": "<u1", "offset": off_k, "count": N, "shared_bit": 8}]
            if thickness:
                f["thickness"] = {"old": thickness[0], "new": thickness[1]}
            f["new_section"] = new_section
            r["field"] = f
    put_file(d, p, "field_4.bin")


def new_section_case(name, secid=10, card=SECTION_4, element_thickness=False):
    d = stage(name)
    p = to_v2(d)
    write(os.path.join(d, "section_4.k"), card)
    can_morph(d, p, {"secid": secid, "thickness": 0.6, "file": "section_4.k",
                     "why": "셸 두께 0.4 → 0.6(새 CAD 잰 두께 — 옛 섹션 SECID 4 두께 0.4 가 옛 CAD 두께였다) — 옛 섹션 카드를 그대로 옮겨 SECID 와 T1~T4 만 바꿨다"})
    if element_thickness:
        next(r for r in p["parts"] if r["pid"] == 4)["field"]["element_thickness"] = {"elements": 215, "why": "요소마다 두께"}
    put_file(d, p, "section_4.k")
    resummarize(p)
    plan_save(d, p)
    return d, p


def main():
    global TMP
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    TMP = tempfile.mkdtemp(prefix="carry2_")
    try:
        part_a(binary)
        part_b(binary)
        part_c(binary)
        part_d(binary)
        part_e(binary)
        part_f(binary)
        part_g(binary)
        part_r1(binary)
        part_r2(binary)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print()
    if FAILS:
        print("FAIL %d  (OK %d)" % (len(FAILS), len(OKS)))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


def part_a(binary):
    print("[A 실물 둘 — 바깥 덱(fc160119a36e · RIB morph + keep 7) · 메시 덱(f8ff42845904 · HOUSING remesh + RIB morph + keep 10)]")
    d = stage("a_raw", LIVE_RAW, [os.path.join(EX, "deck.k"), os.path.join(EX, "field_2.bin")])
    plan = plan_load(d)
    rc, out, rep = apply_case(binary, d)
    check("A-1 바깥 덱 — rc 0 · ok · 문제 0 · 경고 0 · 판 2 · deck_from raw · includes [] · 덱 지문",
          rc == 0 and rep.get("ok") is True and rep["problems"] == [] and rep["warnings"] == [] and rep["plan"]["version"] == 2 and
          rep["plan"]["deck_from"] == "raw" and rep["deck"]["includes"] == [] and rep["deck"]["sha256_in"] == plan["deck"]["sha256"] and
          rep["deck"]["sha256_out"] == sha(os.path.join(d, "deck_applied.k")), (rc, out[-600:]))
    if rc == 0:
        n0, e0, _p, _s, _m = read_deck(os.path.join(d, "deck.k"))
        n1 = read_deck(os.path.join(d, "deck_applied.k"))[0]
        ids, disp = read_field(d, next(r for r in plan["parts"] if r["pid"] == 2)["field"])
        worst = max(abs(n1[nid][1][k] - (n0[nid][1][k] + disp[3 * i + k])) for i, nid in enumerate(ids) for k in range(3))
        same = all(n1[n][0] == n0[n][0] for pid, ns in pid_nodes(e0).items() if pid != 2 for n in ns)
        check("A-2 RIB = 덱 + 변위장(1e-9) · 나머지 일곱 PID 의 좌표 글자 그대로", worst < 1e-9 and same, (worst, same))

    d = stage("a_mesh", LIVE_MESH)
    plan = plan_load(d)
    rc, out, rep = apply_case(binary, d)
    check("A-3 메시 덱 — rc 0 · ok · 문제 0 · 경고 0 · deck_from mesh · HOUSING remesh · RIB morph applied",
          rc == 0 and rep.get("ok") is True and rep["problems"] == [] and rep["warnings"] == [] and rep["plan"]["deck_from"] == "mesh" and
          {p["pid"]: p["result"] for p in rep["parts"]}.get(1) == "applied" and
          {p["pid"]: p["result"] for p in rep["parts"]}.get(2) == "applied", (rc, out[-600:]))
    if rc == 0:
        _n, e1, _p, _s, _m = read_deck(os.path.join(d, "deck_applied.k"))
        cnt = count_by_pid(e1)
        frag = plan["parts"][0]["fragment"]
        check("A-4 HOUSING 요소 = 조각 1678 · 넣은 구간 = 계획 · 나머지 PID 요소 수 그대로",
              cnt.get(1) == 1678 and rep["parts"][0]["inserted"] == frag["ranges"] and
              all(cnt.get(r["pid"]) == r["deck"]["elem_count"] for r in plan["parts"] if r["pid"] != 1), (cnt, rep["parts"][0]))
        rc2, out2 = run(binary, d, "info", "--strict", "deck_applied.k")
        check("A-5 info --strict 가 산출을 받는다", rc2 == 0 and "참조 무결성 OK" in out2, out2[-300:])


def part_b(binary):
    print("[B 진리값 판을 판 2 로 — 덱 자리 신탁 · 같은 적용]")
    live = {r["pid"]: r["deck"] for r in plan_load(LIVE_RAW)["parts"]}
    _n, e0, p0, _s, _m = read_deck(os.path.join(EX, "deck.k"))
    ours = places(e0, p0)
    check("B-0 이 시험의 덱 자리 셈 = 실물 판 계획의 값(같은 덱 0713a659 · PID 여덟)", all(ours[k] == v for k, v in live.items()) and len(live) == 8,
          [(k, ours.get(k), v) for k, v in live.items() if ours.get(k) != v][:3])
    d = stage("b")
    to_v2(d)
    rc, out, rep = apply_case(binary, d)
    check("B-1 rc 0 · ok · 판 2 · 문제 0", rc == 0 and rep.get("ok") is True and rep["plan"]["version"] == 2 and rep["problems"] == [], (rc, out[-600:]))
    if rc == 0:
        _n, e1, p1, s1, _m = read_deck(os.path.join(d, "deck_applied.k"))
        cnt = count_by_pid(e1)
        check("B-2 remesh 4/5/6 요소 268 · 707 · 898 · delete 7 없음 · BATTERY 새 섹션 SECID 9(조각) — 판 1 과 같은 덱",
              (cnt.get(4), cnt.get(5), cnt.get(6), cnt.get(7)) == (268, 707, 898, None) and p1.get(6, (0,))[0] == 9 and
              s1.get(9) == ("*SECTION_SOLID_TITLE", 10), (cnt, p1.get(6), s1.get(9)))


def part_c(binary):
    print("[C 칸 표 — 판마다 모르는 칸 · 빠진 칸 · summary 대조]")
    def mutate(name, fn, kind, needle, v1=False):
        d = stage(name)
        p = plan_load(d) if v1 else to_v2(d)
        fn(p)
        plan_save(d, p)
        rc, out, rep = apply_case(binary, d)
        ok = refused(name + " → " + kind, rc, out, rep, d, kind)
        if ok and needle:
            check(name + " 그 칸을 말한다", needle in details(rep, kind), details(rep, kind)[:300])

    mutate("C-1 덱 자리에 모르는 칸(gap)", lambda p: p["parts"][0]["deck"].update(gap=0), "plan_schema", "'gap'")
    mutate("C-2 줄의 deck 이 없다", lambda p: p["parts"][3].pop("deck"), "plan_schema", "칸 'deck' 가 없다")
    mutate("C-3 deck.includes 가 없다", lambda p: p["deck"].pop("includes"), "plan_schema", "칸 'includes' 가 없다")
    mutate("C-4 모프 줄 field.new_section 이 없다", lambda p: p["parts"][1]["field"].pop("new_section"), "plan_schema", "칸 'new_section' 가 없다")
    mutate("C-5 deck_from 이 raw · mesh 밖", lambda p: p["deck"].update(deck_from="job"), "plan_schema", "raw · mesh 만")
    mutate("C-6 새 파트 줄에 deck", lambda p: p["added"][0].update(deck={}), "plan_schema", "모르는 칸 'deck'")
    mutate("C-7 판 1 계획에 판 2 칸(deck_from)", lambda p: p["deck"].update(deck_from="raw"), "plan_schema", "계획 판 1 에 없는 칸", v1=True)
    mutate("C-8 summary.actions 가 줄과 다르다", lambda p: p["summary"]["actions"].update(transform=2), "plan_inconsistent",
           "summary.actions.transform")
    mutate("C-9 summary.sections 가 줄과 다르다", lambda p: p["summary"].update(sections=1), "plan_inconsistent", "summary.sections")
    mutate("C-10 판 3", lambda p: p.update(version=3), "plan_format", "판 1 · 2 만")


def part_d(binary):
    print("[D 덱 자리 — 손대는 줄은 거절 · keep/review 는 경고 · 번호 목록은 요소에서]")
    d = stage("d1")
    p = to_v2(d)
    p["parts"][1]["deck"]["node_count"] += 1          # RIB(morph)
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    refused("D-1 morph 줄의 node_count 가 우리 셈과 다르다 → deck_range(PID 2)", rc, out, rep, d, "deck_range", 2)
    check("D-1b 칸 · 계획 값 · 우리 값을 말한다", "node_count 계획 179 · 우리 178" in details(rep, "deck_range", 2), details(rep, "deck_range")[:300])

    d = stage("d2")
    p = to_v2(d)
    p["parts"][0]["deck"]["elem"] = [1, 1375]         # HOUSING(keep)
    p["parts"][7]["deck"]["secid"] = 9                # MASS_LUMP(keep)
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    check("D-2 keep 줄의 덱 자리가 다르다 → 적용하고 경고만(PID 1 · 8 deck_range)",
          rc == 0 and rep.get("ok") is True and {(1, "deck_range"), (8, "deck_range")} <= warn_kinds(rep) and "deck_range" not in kinds(rep),
          (rc, sorted(kinds(rep)), warn_kinds(rep)))

    d = stage("d3")
    p = to_v2(d)
    p["parts"][3]["deck"]["secid"] = 5                # CAN(remesh)
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    refused("D-3 remesh 줄의 secid 가 다르다 → deck_range(PID 4)", rc, out, rep, d, "deck_range", 4)

    # 손으로 매긴 덱 — SPACER_OLD(7 · delete) 의 EID 2550 과 MASS_LUMP(8 · keep) 의 EID 2570 을 맞바꾼다(두 PID 다 이어짐이 깨진다)
    d = stage("d4")
    lines = read(os.path.join(d, "deck.k")).split("\n")
    a0, b0, _kw = next(bl for bl in blocks(lines) if bl[2] == "*ELEMENT_SOLID")
    at = {int(lines[i][:8]): i for i in range(a0 + 1, b0) if lines[i][:8].strip() in ("2550", "2570")}
    a, b = at[2550], at[2570]
    lines[a], lines[b] = "%8d" % 2570 + lines[a][8:], "%8d" % 2550 + lines[b][8:]
    write(os.path.join(d, "deck.k"), "\n".join(lines))
    p = to_v2(d)
    rc, out, rep = apply_case(binary, d)
    _n, e1, _p, _s, _m = read_deck(os.path.join(d, "deck_applied.k")) if rc == 0 else ({}, {}, {}, {}, set())
    check("D-4 이어짐이 깨진 PID(contiguous false) — 지우기 번호는 그 PID 요소에서: 2570(7) 없음 · 2550(8) 남음 · PID 8 요소 12",
          rc == 0 and p["parts"][6]["deck"]["contiguous"] is False and 2570 not in e1 and e1.get(2550, (0,))[0] == 8 and
          count_by_pid(e1).get(8) == 12 and count_by_pid(e1).get(7) is None, (rc, sorted(kinds(rep)), out[-300:]))


def part_e(binary):
    print("[E 새 셸 섹션 — §10.5 CAN 0.4 → 0.6(section_4.k) · 옛 카드 대조 · SECID · 조각으로 물러선 줄]")
    check("E-0 §10.5 의 section_4.k 는 329 바이트", len(SECTION_4.encode("utf-8")) == 329, len(SECTION_4.encode("utf-8")))
    d, p = new_section_case("e1")
    rc, out, rep = apply_case(binary, d)
    check("E-1 rc 0 · ok · summary(morph 2 · remesh 2 · sections 1)", rc == 0 and rep.get("ok") is True and
          p["summary"]["sections"] == 1 and p["summary"]["actions"].get("morph") == 2, (rc, sorted(kinds(rep)), out[-600:]))
    if rc == 0:
        _n, _e, p1, s1, _m = read_deck(os.path.join(d, "deck_applied.k"))
        body = read(os.path.join(d, "deck_applied.k"))
        pr = {r["pid"]: r for r in rep["parts"]}
        check("E-2 *PART 4 → SECID 10 · 새 *SECTION_SHELL_TITLE 10(ELFORM 2) · 옛 SECID 4 는 남는다 · BATTERY 9 그대로",
              p1.get(4, (0,))[0] == 10 and s1.get(10) == ("*SECTION_SHELL_TITLE", 2) and s1.get(4) == ("*SECTION_SHELL_TITLE", 2) and
              p1.get(6, (0,))[0] == 9, (p1.get(4), s1.get(10), s1.get(4)))
        check("E-3 넣은 카드 글자 — 옛 카드 그대로 · SECID 10 · T1~T4 0.6(그 아래 옛 카드 0.4 도 있다)",
              "        10         2         1         2\n$#      t1        t2        t3        t4\n       0.6       0.6       0.6       0.6\n" in body and
              "         4         2         1         2\n$#      t1        t2        t3        t4\n       0.4       0.4       0.4       0.4\n" in body)
        check("E-4 보고 — PID 4 morph applied · new_section {secid 10, thickness 0.6}",
              pr[4]["result"] == "applied" and pr[4].get("new_section") == {"secid": 10, "thickness": 0.6}, pr.get(4))
        rc2, out2 = run(binary, d, "info", "--strict", "deck_applied.k")
        check("E-5 info --strict 가 산출을 받는다", rc2 == 0 and "참조 무결성 OK" in out2, out2[-300:])

    d, p = new_section_case("e6", card=SECTION_4.replace("CAN#4_sec", "CAN#4_new"))
    rc, out, rep = apply_case(binary, d)
    refused("E-6 옛 카드와 다른 카드(제목을 바꿨다) → new_section(PID 4)", rc, out, rep, d, "new_section", 4)
    check("E-6b 그 줄을 말한다(블록 2째 줄)", "블록 2째 줄이 덱의 옛 카드와 다르다" in details(rep, "new_section", 4), details(rep, "new_section")[:300])
    d, p = new_section_case("e7", card=SECTION_4.replace("        10         2         1         2", "        10         2       0.8         2"))
    rc, out, rep = apply_case(binary, d)
    refused("E-7 SHRF 를 바꾼 카드 → new_section(Card 1 의 SECID 밖 칸)", rc, out, rep, d, "new_section", 4)

    d, p = new_section_case("e8", secid=9, card=SECTION_4.replace("        10         2", "         9         2"))
    rc, out, rep = apply_case(binary, d)
    refused("E-8 SECID 9 — BATTERY 조각의 새 섹션과 겹친다 → secid_collision", rc, out, rep, d, "secid_collision", 4)
    check("E-8b 조각의 새 섹션을 먼저 매긴다(secid_order)", "secid_order" in kinds(rep, 4), sorted(kinds(rep)))
    d, p = new_section_case("e9", secid=3, card=SECTION_4.replace("        10         2", "         3         2"))
    rc, out, rep = apply_case(binary, d)
    refused("E-9 SECID 3 — 덱에 이미 있다 → secid_collision", rc, out, rep, d, "secid_collision", 4)
    d, p = new_section_case("e10", secid=11)
    rc, out, rep = apply_case(binary, d)
    refused("E-10 계획 secid 11 · 카드 SECID 10 → new_section", rc, out, rep, d, "new_section", 4)

    def instead_case(name, failed_fix):
        d = stage(name)
        p = to_v2(d)
        frag = next(r for r in p["parts"] if r["pid"] == 4)["fragment"]
        can_morph(d, p, {"secid": None, "thickness": 0.6, "file": None,
                         "why": "이 PID 셸 요소 215개가 요소마다 두께(0 이 아닌 THIC)를 싣는다 — 섹션 두께를 덮어 새 섹션으로는 두께가 안 바뀐다"})
        row = next(r for r in p["parts"] if r["pid"] == 4)
        row["field"]["element_thickness"] = {"elements": 215, "why": "요소마다 두께"}
        row["instead"] = frag
        resummarize(p)
        if failed_fix is not None:
            p["summary"]["failed"] = failed_fix
        plan_save(d, p)
        return d, p
    d, p = instead_case("e11", None)
    rc, out, rep = apply_case(binary, d)
    refused("E-11 새 섹션을 못 지은 줄(secid null · instead) → morph_instead · new_section · summary.failed 1 은 맞다", rc, out, rep, d,
            "morph_instead", 4)
    check("E-11b new_section 이 그 까닭을 싣고 plan_inconsistent 는 없다(failed " + str(p["summary"]["failed"]) + ")",
          "new_section" in kinds(rep, 4) and "요소마다 두께" in details(rep, "new_section", 4) and "plan_inconsistent" not in kinds(rep) and
          p["summary"]["failed"] == 1, (sorted(kinds(rep)), details(rep, "new_section")[:200]))
    d, p = instead_case("e12", 0)
    rc, out, rep = apply_case(binary, d)
    refused("E-12 그 줄을 summary.failed 가 세지 않았다 → plan_inconsistent", rc, out, rep, d, "plan_inconsistent")

    d = stage("e13")
    p = to_v2(d)
    can_morph(d, p, None, thickness=(0.4, 0.6))     # 두께는 바뀌었으나 새 섹션 null — 사람이 정한 두께 · 섹션 그대로(§10.2)
    resummarize(p)
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    p1 = read_deck(os.path.join(d, "deck_applied.k"))[2] if rc == 0 else {}
    check("E-13 판 2 — thickness 가 있고 new_section null 이면 섹션을 그대로 두고 적용한다(판 1 의 field_thickness 거절이 아니다)",
          rc == 0 and p1.get(4, (0,))[0] == 4 and "field_thickness" not in kinds(rep), (rc, sorted(kinds(rep)), out[-300:]))

    d, p = new_section_case("e14", element_thickness=True)
    rc, out, rep = apply_case(binary, d)
    refused("E-14 계획이 element_thickness 를 실은 줄에 새 섹션 → element_thickness", rc, out, rep, d, "element_thickness", 4)
    # 덱이 요소마다 두께를 싣는다(계획은 말하지 않았다) — 우리가 덱에서 센다
    d, p = new_section_case("e15")
    lines = read(os.path.join(d, "deck.k")).split("\n")
    out_l, kw = [], ""
    for ln in lines:
        if ln.startswith("*"):
            kw = ln.strip().upper()
            out_l.append("*ELEMENT_SHELL_THICKNESS" if kw == "*ELEMENT_SHELL" else ln)
            continue
        out_l.append(ln)
        if kw == "*ELEMENT_SHELL" and ln.strip() and not ln.startswith("$"):
            out_l.append("%16.4f%16.4f%16.4f%16.4f" % (0.4, 0.4, 0.4, 0.4))
    write(os.path.join(d, "deck.k"), "\n".join(out_l))
    reseal_deck(d, p)
    rc, out, rep = apply_case(binary, d)
    refused("E-15 덱의 *ELEMENT_SHELL_THICKNESS(THIC 0.4)가 섹션 두께를 덮는다 → element_thickness(우리가 센 215)", rc, out, rep, d,
            "element_thickness", 4)
    check("E-15b 그 수를 말한다", "셸 요소 215 개" in details(rep, "element_thickness", 4), details(rep, "element_thickness")[:300])


def part_f(binary):
    print("[F 인클루드 — deck.includes 대조 · 닫힘 전체를 읽고 주 덱만 고친다]")
    # F-1 keep 파트(MASS_LUMP · PID 8)가 통째로 inc/part8.k 에 있다 — 받는다
    d = stage("f1")
    ne, nn = split_include(d, "inc/part8.k", 8, move_defs=True)
    inc_sha = sha(os.path.join(d, "inc", "part8.k"))
    p = to_v2(d, include_files=["inc/part8.k"])
    rc, out, rep = apply_case(binary, d)
    check("F-1 keep PID 8 만 인클루드에 — rc 0 · ok · deck.includes 를 되돌려 준다(요소 %d · 절점 %d 을 뺐다)" % (ne, nn),
          ne == 12 and nn == 38 and rc == 0 and rep.get("ok") is True and
          rep["deck"]["includes"] == [{"relpath": "inc/part8.k", "sha256": inc_sha}], (rc, sorted(kinds(rep)), out[-600:]))
    if rc == 0:
        body = read(os.path.join(d, "deck_applied.k"))
        _n, e1, p1, _s, _m = read_closure(os.path.join(d, "deck_applied.k"), [os.path.join(d, "inc", "part8.k")])
        cnt = count_by_pid(e1)
        check("F-2 인클루드 파일 그대로 · 산출에 *INCLUDE inc/part8.k 가 그대로 · 산출 + 인클루드 = 기대 요소 수",
              sha(os.path.join(d, "inc", "part8.k")) == inc_sha and "\n*INCLUDE\ninc/part8.k\n" in body and
              (cnt.get(4), cnt.get(5), cnt.get(6), cnt.get(7), cnt.get(8)) == (268, 707, 898, None, 12) and 8 in p1, (cnt, 8 in p1))
        rc2, out2 = run(binary, d, "info", "--strict", "deck_applied.k")
        check("F-3 info --strict 가 산출을 닫힘째 받는다", rc2 == 0 and "참조 무결성 OK" in out2, out2[-300:])

    d = stage("f4")
    split_include(d, "inc/part8.k", 8, move_defs=True)
    p = to_v2(d, include_files=["inc/part8.k"])
    p["deck"]["includes"][0]["sha256"] = "0" * 64
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    refused("F-4 deck.includes 의 sha256 이 다르다 → include_mismatch", rc, out, rep, d, "include_mismatch")
    p["deck"]["includes"] = []
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    refused("F-4b deck.includes 가 빈 목록인데 덱에 *INCLUDE → include_mismatch", rc, out, rep, d, "include_mismatch")
    check("F-4c 우리 닫힘을 말한다", "inc/part8.k(" in details(rep, "include_mismatch"), details(rep, "include_mismatch")[:300])

    # F-5 §10.4 — BATTERY(PID 6 · remesh) 요소와 그 파일에만 있는 물성 MID 99 가 inc/part6.k 에 있다 — 거절하고 목록
    d = stage("f5")
    mat99 = "*MAT_ELASTIC_TITLE\nEXTRA_99\n$#     mid        ro         e        pr\n        99         1         1       0.3"
    ne, _nn = split_include(d, "inc/part6.k", 6, extra=mat99)
    p = to_v2(d, include_files=["inc/part6.k"])
    p["deck"]["max"]["mid"] = 99
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    refused("F-5 BATTERY(remesh) 요소가 inc/part6.k 에 있다 → include_edit(PID 6)", rc, out, rep, d, "include_edit", 6)
    check("F-5b 목록 — 파일 · PID · 무엇(요소 %d 개)" % ne, ne == 126 and "inc/part6.k: 요소 126 개" in details(rep, "include_edit", 6),
          details(rep, "include_edit")[:300])
    check("F-5c 덱 자리는 닫힘째 센다 — deck_range 가 없다(한 덱과 같은 PID 자리)", "deck_range" not in kinds(rep), sorted(kinds(rep)))

    # F-6 인클루드 파일의 세트가 바꿔 넣는 CAN(PID 4)의 절점을 가리킨다 — 주 덱에서와 똑같이 거절
    d = stage("f6")
    n4 = min(pid_nodes(read_deck(os.path.join(d, "deck.k"))[1])[4])
    split_include(d, "inc/sets.k", 99, extra="*SET_NODE_LIST\n        77\n%10d" % n4)
    p = to_v2(d, include_files=["inc/sets.k"])
    rc, out, rep = apply_case(binary, d)
    refused("F-6 inc/sets.k 의 *SET_NODE_LIST 가 PID 4 의 절점 → node_ref(PID 4)", rc, out, rep, d, "node_ref", 4)
    check("F-6b 그 파일 · 줄을 말한다(inc/sets.k 줄 2)", "inc/sets.k 줄 2" in details(rep, "node_ref", 4), details(rep, "node_ref")[:300])

    d = stage("f7")
    split_include(d, "inc/part8.k", 8, move_defs=True)
    to_v2(d, include_files=["inc/part8.k"])
    os.makedirs(os.path.join(d, "out"))
    rc, out, rep = apply_case(binary, d, output="out/deck_applied.k", report="out/deck_applied_carryover.json")
    refused("F-7 산출이 덱과 다른 폴더 → include_output(산출의 *INCLUDE 가 다른 파일을 가리킨다)", rc, out, rep, d, "include_output",
            out_name="out/deck_applied.k")

    d = stage("f8")
    split_include(d, "inc/part8.k", 8, move_defs=True)
    to_v2(d, include_files=["inc/part8.k"])
    before = sha(os.path.join(d, "inc", "part8.k"))
    rc, out, _rep = apply_case(binary, d, output="inc/part8.k", report="inc/part8_carryover.json")
    check("F-8 산출이 인클루드 파일 자리 → rc 1 · 그 파일 그대로(읽기 전에 거절)", rc == 1 and sha(os.path.join(d, "inc", "part8.k")) == before and
          "읽는 파일" in out, out[-300:])


def part_g(binary):
    print("[G refused_transform — 강체가 아닌 옮김을 계획이 review 로 돌렸다]")
    d = stage("g1")
    p = to_v2(d)
    row = next(r for r in p["parts"] if r["pid"] == 3)
    for k in ("transform", "translation", "rotation_deg", "check"):
        row.pop(k, None)
    row.update({"action": "review", "why": "옮김 4×4 가 강체가 아니다 — 축척 1.01",
                "refused_transform": {"transform": [1.01, 0, 0, 2, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], "det": 1.01, "scale": 1.003322,
                                      "orthogonality_error": 0.0201}})
    resummarize(p)
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    pr = {r["pid"]: r for r in rep.get("parts", [])}
    n0 = read_deck(os.path.join(d, "deck.k"))
    n1 = read_deck(os.path.join(d, "deck_applied.k"))[0] if rc == 0 else {}
    same = rc == 0 and all(n1[n][0] == n0[0][n][0] for n in pid_nodes(n0[1])[3])
    check("G-1 rc 0 · BRACKET 은 옮기지 않는다(좌표 글자 그대로) · 보고에 refused_transform 을 되돌려 준다 · review 2",
          rc == 0 and same and pr.get(3, {}).get("result") == "skipped" and
          pr.get(3, {}).get("refused_transform", {}).get("transform", [0])[0] == 1.01 and p["summary"]["actions"].get("review") == 1,
          (rc, pr.get(3), out[-300:]))


# ── 적대적 검토 11-07 고침(R) — 검토가 rc 0 으로 내보낸 덱 · 입력을 덮은 길 ─────────────────────────────────────────────

HOUSING_SEC = "*SECTION_SOLID_TITLE\nHOUSING#1_sec\n$#   secid    elform\n         1         1\n"


def stacked_secid(d, hidden):
    """HOUSING 섹션을 한 키워드 아래 두 카드로 — 둘째 카드(SECID hidden)는 아무 *PART 도 안 쓴다(그쪽 리더는 「쌓인 카드 — 안 읽는다」 고 경고만)."""
    body = read(os.path.join(d, "deck.k"))
    assert HOUSING_SEC in body
    write(os.path.join(d, "deck.k"), body.replace(HOUSING_SEC, "*SECTION_SOLID\n$#   secid    elform\n         1         1\n%10d         1\n" % hidden))


def part_r1(binary):
    print("[R-1 쌓인 둘째 카드의 SECID — 번호 커서가 첫 카드만 읽어 새 섹션이 같은 SECID 를 다시 냈다(검토 S5)]")
    d = stage("r1")
    stacked_secid(d, 10)
    p = to_v2(d)
    write(os.path.join(d, "section_4.k"), SECTION_4)
    can_morph(d, p, {"secid": 10, "thickness": 0.6, "file": "section_4.k", "why": "0.4 → 0.6"})
    put_file(d, p, "section_4.k")
    resummarize(p)
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    refused("R-1 모프의 새 셸 섹션 10 이 *SECTION_SOLID 둘째 카드의 10 과 겹친다 → secid_collision(PID 4)", rc, out, rep, d,
            "secid_collision", 4)
    check("R-1b 쌓인 카드라고 말하고 차례(덱의 가장 큰 SECID 10)도 본다", "쌓인 카드" in details(rep, "secid_collision", 4) and
          "secid_order" in kinds(rep, 4), (details(rep, "secid_collision")[:200], sorted(kinds(rep))))
    d = stage("r1c")
    stacked_secid(d, 9)
    p = plan_load(d)                       # 판 1 계획 그대로 — 조각의 새 섹션(BATTERY SECID 9)도 같은 틈이 있었다
    p["deck"]["sha256"] = sha(os.path.join(d, "deck.k"))
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    refused("R-1c 판 1 — BATTERY 조각의 새 섹션 9 가 쌓인 카드의 9 와 겹친다 → fragment(PID 6)", rc, out, rep, d, "fragment", 6)
    check("R-1d 그 까닭(쌓인 카드)을 말한다", "쌓인 카드" in details(rep, "fragment", 6), details(rep, "fragment")[:300])



def part_r2(binary):
    print("[R-2 인클루드 파일 맨 앞 UTF-8 BOM — 첫 키워드가 데이터 줄로 보여 그 세트를 닫힘 검사가 못 보았다(검토 B2)]")
    d = stage("r2")
    n4 = min(pid_nodes(read_deck(os.path.join(d, "deck.k"))[1])[4])
    split_include(d, "inc/s.k", 12345)
    open(os.path.join(d, "inc", "s.k"), "wb").write(b"\xef\xbb\xbf" + ("*SET_NODE_LIST\n        77\n%10d\n*END\n" % n4).encode())
    to_v2(d, include_files=["inc/s.k"])
    rc, out, rep = apply_case(binary, d)
    refused("R-2 BOM 으로 시작하는 inc/s.k 의 *SET_NODE_LIST 가 바꿔 넣는 PID 4 의 절점 → node_ref(PID 4)", rc, out, rep, d, "node_ref", 4)
    check("R-2b 그 파일 · 줄(inc/s.k 줄 1)을 말한다", "inc/s.k 줄 1" in details(rep, "node_ref", 4), details(rep, "node_ref")[:200])


if __name__ == "__main__":
    sys.exit(main())
