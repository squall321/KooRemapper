#!/usr/bin/env python3
# apply_carryover_plan 이 StepForge 이월 계획을 처리마다 맞게 적용하고 계약 밖은 전부 모아 거절하는지 보는 회귀 시험
"""`apply_carryover_plan` — StepForge 이월 계획(plan.json v1 · field_<PID>.bin · fragment_<PID>.k)을 덱에 적용한다.

왜 이 시험이 있나 (2026-11-07).

  StepForge 가 CAD 개정을 해석 덱으로 이월하는 재료를 내고(그쪽 `docs/REQUEST-2026-11-06-carryover.md`), 덱을 고치는
  일은 우리 몫이다. 처리 꼴은 우리 답신(`docs/requests/stepforge-carryover-reply-2026-11-07.md`)과 사용자 결정(11-07 —
  나눠 쓴 절점 거절 · 절점/세그먼트/요소로 건 참조 거절 · 사전 검사는 전부 아니면 전무)이 정했다.

신탁(이 시험이 따로 잰다 — 바이너리의 보고를 믿지 않는다).
  · morph — 산출 좌표 = 덱 좌표 + 변위장(이 시험이 field_2.bin 을 계획의 layout 대로 읽는다) · RIB 의 y 변위는 ±0.2
  · transform — BRACKET 은 x + 2 · 손대지 않은 파트의 절점 줄은 좌표 글자가 그대로다
  · remesh — 조각의 절점 · 요소가 그 번호 · 그 좌표 글자로 들어가고 옛 요소는 없다 · 새 섹션(SECID 9 · ELFORM 10)을 *PART 가 가리킨다
  · delete — 요소 · *PART 가 없고 *SECTION · *MAT 은 남는다(mesh12 의 새 파트가 지운 PID 의 SECID · MID 를 가리킨다)
  · 거절 — rc 1 · 보고 ok false · 그 갈래(kind)가 있다 · 산출 덱이 없다 · 다른 줄도 적용하지 않았다
  · 개행 — CRLF 덱은 CRLF 로 나간다 · CRLF 로 바뀐 조각은 값 대조로 받고 경고한다

무엇을 보나.
  A 진리값 판(examples/apply_carryover_plan) · B 12 파트 덱(mesh12) · C 거절 · D 개행 · E YAML · F 바닥(보 요소) · G 품질 관문

usage: test_apply_carryover_plan.py <KooRemapper 바이너리>
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
M12 = os.path.join(HERE, "data", "apply_carryover_plan", "mesh12")
FAILS, OKS = [], []
OP = "apply_carryover_plan"


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:400]))
    print("  %-70s %s" % (name[:70], "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def write(path, text, newline="\n"):
    with open(path, "w", newline=newline, encoding="utf-8") as f:
        f.write(text)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def stage(src, name):
    d = os.path.join(TMP, name)
    shutil.copytree(src, d)
    return d


def plan_load(d):
    return json.load(open(os.path.join(d, "plan.json"), encoding="utf-8"))


def plan_save(d, p):
    write(os.path.join(d, "plan.json"), json.dumps(p, ensure_ascii=False, indent=1))


def reseal(d, files=()):
    """덱을 고친 시험 — 계획의 deck.sha256(과 고친 동반 파일의 files 칸)을 새 바이트로 맞춘다."""
    p = plan_load(d)
    p["deck"]["sha256"] = sha(os.path.join(d, "deck.k"))
    for f in files:
        fp = os.path.join(d, f)
        p["files"][f] = {"sha256": sha(fp), "bytes": os.path.getsize(fp)}
    plan_save(d, p)


def read_deck(path):
    """절점(번호 → 좌표 글자 · 값) · 요소(번호 → PID · 절점) · *PART(PID → SECID · MID) · 섹션(SECID → 키워드 · ELFORM)."""
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


def read_field(d, head):
    b = open(os.path.join(d, head["file"]), "rb").read()
    lay = {e["name"]: e for e in head["layout"]}
    n = head["nodes"]
    ids = struct.unpack_from("<%dI" % n, b, lay["node"]["offset"])
    disp = struct.unpack_from("<%dd" % (3 * n), b, lay["disp"]["offset"])
    return ids, disp


def apply_case(binary, d, yaml="model: deck.k\nplan: plan.json\noutput: deck_applied.k\n", report="deck_applied_carryover.json"):
    write(os.path.join(d, "a.yaml"), yaml)
    rc, out = run(binary, d, OP, "a.yaml")
    rp = os.path.join(d, report)
    rep = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}
    return rc, out, rep


def kinds(rep, pid=None):
    return {p["kind"] for p in rep.get("problems", []) if pid is None or p.get("pid") == pid}


def refused(name, rc, out, rep, d, kind, pid=None, out_name="deck_applied.k"):
    ok = (rc == 1 and rep.get("ok") is False and kind in kinds(rep, pid) and
          not os.path.exists(os.path.join(d, out_name)) and rep.get("deck", {}).get("sha256_out") is None)
    return check(name, ok, (rc, sorted(kinds(rep)), out[-400:]))


def frag_lines(path):
    """조각의 절점 줄(번호 → 좌표 글자)과 요소(번호 → PID)."""
    nodes, elems, kw = {}, {}, ""
    for ln in open(path, encoding="utf-8", newline=""):
        ln = ln.rstrip("\r\n")
        if ln.startswith("*"):
            kw = ln.strip().upper()
            continue
        if ln.startswith("$") or not ln.strip():
            continue
        if kw == "*NODE":
            nodes[int(ln[:8])] = ln[8:56]
        elif kw.startswith("*ELEMENT"):
            elems[int(ln[:8])] = int(ln[8:16])
    return nodes, elems


def main():
    global TMP
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    TMP = tempfile.mkdtemp(prefix="carry_")
    try:
        part_a(binary)
        part_b(binary)
        part_c(binary)
        part_d(binary)
        part_e(binary)
        part_f(binary)
        part_g(binary)
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
    print("[A 진리값 판 — keep 2 · morph 1 · transform 1 · remesh 3(새 섹션 하나) · delete 1 · 새 파트 1(조각 없음)]")
    d = stage(EX, "a")
    plan = plan_load(d)
    rc, out, rep = apply_case(binary, d)
    outk = os.path.join(d, "deck_applied.k")
    check("A-1 rc 0 · 보고 ok · 계획 · 덱 지문(sha256 in = 계획 · out = 산출)",
          rc == 0 and rep.get("ok") is True and rep["plan"]["sha256"] == sha(os.path.join(d, "plan.json")) and
          rep["plan"]["version"] == 1 and rep["plan"]["report_key"] == plan["report_key"] and
          rep["deck"]["sha256_in"] == plan["deck"]["sha256"] and rep["deck"]["sha256_out"] == sha(outk) and
          rep["problems"] == [] and rep["shift"] is None, (rc, out[-600:]))
    if rc != 0:
        return
    n0, e0, p0, s0, m0 = read_deck(os.path.join(d, "deck.k"))
    n1, e1, p1, s1, m1 = read_deck(outk)
    pn = pid_nodes(e0)
    row = {r["pid"]: r for r in plan["parts"]}
    ids, disp = read_field(d, row[2]["field"])
    worst = max(abs(n1[nid][1][k] - (n0[nid][1][k] + disp[3 * i + k])) for i, nid in enumerate(ids) for k in range(3))
    check("A-2 morph PID 2 — 산출 = 덱 + 변위장(1e-9 안) · 변위장 절점 = RIB 요소 절점 전부",
          worst < 1e-9 and set(ids) == pn[2], (worst, len(ids), len(pn[2])))
    dys = {round(n1[n][1][1] - n0[n][1][1], 9) for n in pn[2]}
    dxz = max(max(abs(n1[n][1][0] - n0[n][1][0]), abs(n1[n][1][2] - n0[n][1][2])) for n in pn[2])
    check("A-3 RIB 의 y 변위는 ±0.2 (x · z 그대로)", dys == {-0.2, 0.2} and dxz < 1e-12, (dys, dxz))
    w3 = max(max(abs(n1[n][1][0] - n0[n][1][0] - 2.0), abs(n1[n][1][1] - n0[n][1][1]), abs(n1[n][1][2] - n0[n][1][2]))
             for n in pn[3])
    check("A-4 transform PID 3 — 절점 전부 x + 2", w3 < 1e-9, w3)
    same = all(n1[n][0] == n0[n][0] for p in (1, 8) for n in pn[p])
    check("A-5 손대지 않은 PID 1 · 8 의 절점 좌표 글자가 그대로", same)
    cnt = count_by_pid(e1)
    okr = cnt.get(4) == 268 and cnt.get(5) == 707 and cnt.get(6) == 898
    gone = all(eid not in e1 for eid, (pid, _n) in e0.items() if pid in (4, 5, 6, 7))
    fragok = True
    for pid in (4, 5, 6):
        fn, fe = frag_lines(os.path.join(d, row[pid]["fragment"]["file"]))
        fragok = fragok and all(n1.get(nid, ("",))[0] == txt for nid, txt in fn.items()) and \
            all(e1.get(eid, (0,))[0] == pid for eid in fe)
    check("A-6 remesh 4/5/6 — 요소 268 · 707 · 898 · 옛 요소 없음 · 조각 절점이 그 번호 · 그 좌표 글자로", okr and gone and fragok,
          (cnt, gone, fragok))
    check("A-7 BATTERY 새 섹션 SECID 9 ELFORM 10 · *PART 6 이 SECID 9 를 가리킨다 · 옛 SECID 6 은 남는다",
          s1.get(9) == ("*SECTION_SOLID_TITLE", 10) and p1.get(6, (0,))[0] == 9 and 6 in s1, (s1.get(9), p1.get(6)))
    check("A-8 delete PID 7 — 요소 · *PART 가 없고 SECTION 7 · MAT 7 은 남는다 · 그 절점도 없다",
          cnt.get(7) is None and 7 not in p1 and 7 in s1 and 7 in m1 and not any(n in n1 for n in pn[7]), (cnt.get(7), 7 in p1))
    pr = {r["pid"]: r for r in rep["parts"]}
    fr = {p: row[p]["fragment"]["ranges"] for p in (4, 5, 6)}
    check("A-9 보고 — 처리마다 결과 · 옮긴 수 · 넣은 구간 = 계획 · 새 섹션 · 지운 수 · 새 파트 · touches_changed",
          pr[1]["result"] == "skipped" and pr[2]["result"] == "applied" and pr[2]["nodes_moved"] == 178 and
          pr[3]["nodes_moved"] == 204 and abs(pr[3]["max_disp"] - 2.0) < 1e-9 and
          all(pr[p]["inserted"] == fr[p] and pr[p]["result"] == "applied" for p in (4, 5, 6)) and
          pr[6]["new_section"] == {"secid": 9, "elform": 10} and pr[7]["removed"]["elements"] == 21 and
          pr[8]["result"] == "skipped" and rep["added"][0]["result"] == "skipped" and rep["added"][0].get("why") and
          rep["touches_changed"] == [{"pid": 8, "with": [3]}], json.dumps(rep["parts"], ensure_ascii=False)[:500])
    rc2, out2 = run(binary, d, "info", "--strict", "deck_applied.k")
    check("A-10 info --strict 가 산출 덱을 받는다(미정의 참조 0)", rc2 == 0 and "참조 무결성 OK" in out2, out2[-300:])


def part_b(binary):
    print("[B 12 파트 덱 — remesh 1/4/11 · delete 2/8/12 · transform 3/10 · 새 파트 13/14(지운 PID 2 의 SECID · MID)]")
    d = stage(M12, "b")
    rc, out, rep = apply_case(binary, d)
    check("B-1 rc 0 · 보고 ok", rc == 0 and rep.get("ok") is True, out[-600:])
    if rc != 0:
        return
    n0, e0, p0, s0, m0 = read_deck(os.path.join(d, "deck.k"))
    n1, e1, p1, s1, m1 = read_deck(os.path.join(d, "deck_applied.k"))
    cnt = count_by_pid(e1)
    check("B-2 요소 수 — 1:1678 · 4:268 · 11:898 · 13:68 · 14:145 · 지운 2/8/12 는 0",
          [cnt.get(p) for p in (1, 4, 11, 13, 14)] == [1678, 268, 898, 68, 145] and
          all(cnt.get(p) is None for p in (2, 8, 12)), cnt)
    check("B-3 *PART 2/8/12 없음 · SECTION/MAT 2 남음 · 13 → SECID 2 MID 2 · 14 → 6/6 · 11 → SECID 13",
          all(p not in p1 for p in (2, 8, 12)) and 2 in s1 and 2 in m1 and p1.get(13, (0, 0))[:2] == (2, 2) and
          p1.get(14, (0, 0))[:2] == (6, 6) and p1.get(11, (0,))[0] == 13 and s1.get(13, ("", 0))[1] == 10,
          (p1.get(13), p1.get(14), p1.get(11), s1.get(13)))
    pn = pid_nodes(e0)
    w = max([abs(n1[n][1][0] - n0[n][1][0] - 2.0) for n in pn[3]] + [abs(n1[n][1][1] - n0[n][1][1] - 1.0) for n in pn[10]])
    check("B-4 transform 3 은 x + 2 · 10 은 y + 1", w < 1e-9, w)
    warn = {(x.get("pid"), x["kind"]) for x in rep["warnings"]}
    check("B-5 보고 — 새 파트 둘 applied · 「물성 확인」 경고 둘",
          [a["result"] for a in rep["added"]] == ["applied", "applied"] and
          {(13, "new_part_material"), (14, "new_part_material")} <= warn, (rep["added"], warn))
    rc2, out2 = run(binary, d, "info", "--strict", "deck_applied.k")
    check("B-6 info --strict 가 산출 덱을 받는다", rc2 == 0 and "참조 무결성 OK" in out2, out2[-300:])


def part_c(binary):
    print("[C 거절 — 전부 모아 거절 · 덱을 쓰지 않는다]")
    d = stage(EX, "c1")
    p = plan_load(d)
    p["deck"]["sha256"] = "0" * 64
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    refused("C-1 계획의 deck.sha256 이 덱과 다르다 → deck_sha", rc, out, rep, d, "deck_sha")

    d = stage(EX, "c2")
    os.remove(os.path.join(d, "fragment_5.k"))
    rc, out, rep = apply_case(binary, d)
    refused("C-2 동반 파일(fragment_5.k)이 없다 → file_missing", rc, out, rep, d, "file_missing")

    d = stage(EX, "c3")
    fp = os.path.join(d, "field_2.bin")
    b = bytearray(open(fp, "rb").read())
    b[800] ^= 0x01
    open(fp, "wb").write(bytes(b))
    rc, out, rep = apply_case(binary, d)
    refused("C-3 변위장 바이트를 고쳤다 → file_mismatch", rc, out, rep, d, "file_mismatch")

    d = stage(EX, "c4")
    p = plan_load(d)
    p["extra_top"] = 1
    p["parts"][2]["foo"] = 1
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    det = " ".join(x["detail"] for x in rep.get("problems", []))
    check("C-4 모르는 칸(맨 위 · 줄 안) 둘 다 말한다 → plan_schema",
          rc == 1 and "'extra_top'" in det and "'foo'" in det and not os.path.exists(os.path.join(d, "deck_applied.k")), det[:300])

    d = stage(M12, "c5")
    _n, e0, _p, _s, _m = read_deck(os.path.join(d, "deck.k"))
    pn = pid_nodes(e0)
    target = min(pn[1])                                   # HOUSING(PID 1 — remesh) 의 절점 하나를
    rib = min(eid for eid, (pid, _x) in e0.items() if pid == 2)   # RIB(PID 2 — delete) 요소 하나가 쓴다
    lines = open(os.path.join(d, "deck.k"), encoding="utf-8").read().split("\n")
    for i, ln in enumerate(lines):
        if ln[:8].strip() == str(rib) and ln[8:16].strip() == "2":
            lines[i] = ln[:16] + "%8d" % target + ln[24:]
            break
    write(os.path.join(d, "deck.k"), "\n".join(lines))
    reseal(d)
    rc, out, rep = apply_case(binary, d)
    det = " ".join(x["detail"] for x in rep.get("problems", []) if x["kind"] == "shared_nodes")
    refused("C-5 PID 2 가 PID 1 의 절점을 나눠 쓴다 → shared_nodes(PID 1)", rc, out, rep, d, "shared_nodes", 1)
    check("C-5b PID 2 도 걸리고 그 절점 번호 · 상대 PID 를 말한다",
          "shared_nodes" in kinds(rep, 2) and str(target) in det and "PID 1" in det and "PID 2" in det, det[:300])

    d = stage(EX, "c6")
    _n, e0, _p, _s, _m = read_deck(os.path.join(d, "deck.k"))
    n4 = min(pid_nodes(e0)[4])
    txt = open(os.path.join(d, "deck.k"), encoding="utf-8").read()
    write(os.path.join(d, "deck.k"), txt.replace("*END", "*SET_NODE_LIST\n%10d\n%10d\n*END" % (1, n4)))
    reseal(d)
    rc, out, rep = apply_case(binary, d)
    refused("C-6 *SET_NODE 가 바꿔 넣는 PID 4 의 절점을 가리킨다 → node_ref(PID 4)", rc, out, rep, d, "node_ref", 4)
    res = {r["pid"]: r["result"] for r in rep.get("parts", [])}
    check("C-7 전부 아니면 전무 — PID 4 refused · 나머지는 적용하지 않았다(skipped)",
          res.get(4) == "refused" and all(v == "skipped" for k, v in res.items() if k != 4), res)

    d = stage(EX, "c8")
    txt = open(os.path.join(d, "deck.k"), encoding="utf-8").read()
    write(os.path.join(d, "deck.k"), txt.replace("*END", "*SET_PART_LIST\n%10d\n%10d\n*END" % (2, 7)))
    reseal(d)
    rc, out, rep = apply_case(binary, d)
    refused("C-8 *SET_PART 가 지우는 PID 7 을 가리킨다 → part_ref(PID 7)", rc, out, rep, d, "part_ref", 7)

    d = stage(EX, "c9")
    p = plan_load(d)
    for r in p["parts"]:
        if r["pid"] == 3:
            r["transform"][0] = 1.01
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    refused("C-9 강체가 아닌 4×4(늘림 1.01) → transform_not_rigid(PID 3)", rc, out, rep, d, "transform_not_rigid", 3)

    d = stage(EX, "c10")
    _n, e0, _p, _s, _m = read_deck(os.path.join(d, "deck.k"))
    rib = min(eid for eid, (pid, _x) in e0.items() if pid == 2)
    lines = open(os.path.join(d, "deck.k"), encoding="utf-8").read().split("\n")
    lines.insert(lines.index("*NODE") + 2, "%8d%16.9e%16.9e%16.9e" % (99999, 5.0, 15.5, 1.0))
    for i, ln in enumerate(lines):
        if ln[:8].strip() == str(rib) and ln[8:16].strip() == "2":
            lines[i] = ln[:16] + "%8d" % 99999 + ln[24:]
            break
    write(os.path.join(d, "deck.k"), "\n".join(lines))
    reseal(d)
    rc, out, rep = apply_case(binary, d)
    refused("C-10 변위장 절점 ≠ PID 2 요소가 쓰는 절점 → field_nodes(PID 2)", rc, out, rep, d, "field_nodes", 2)

    d = stage(EX, "c11")
    p = plan_load(d)
    p["deck"]["sha256"] = "1" * 64
    for r in p["parts"]:
        if r["pid"] == 3:
            r["transform"][5] = 0.5
        if r["pid"] == 2:
            r["instead"] = {"ok": False, "why": "x"}
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    check("C-11 걸린 것을 전부 모은다 — deck_sha · transform_not_rigid · morph_instead 가 한 보고에",
          rc == 1 and {"deck_sha", "transform_not_rigid", "morph_instead"} <= kinds(rep), sorted(kinds(rep)))

    d = stage(EX, "c12")
    _n, e0, _p, _s, _m = read_deck(os.path.join(d, "deck.k"))
    n3 = sorted(pid_nodes(e0)[3])[:2]
    txt = open(os.path.join(d, "deck.k"), encoding="utf-8").read()
    write(os.path.join(d, "deck.k"), txt.replace("*END", "*ELEMENT_BEAM\n%8d%8d%8d%8d\n*END" % (9001, 1, n3[0], n3[1])))
    reseal(d)
    rc, out, rep = apply_case(binary, d)
    det = " ".join(x["detail"] for x in rep.get("problems", []) if x.get("pid") == 3)
    check("C-12 보 요소가 옮기는 PID 3 의 절점을 쓴다 → shared_nodes(PID 3 · *ELEMENT_BEAM)",
          rc == 1 and "shared_nodes" in kinds(rep, 3) and "*ELEMENT_BEAM" in det and
          not os.path.exists(os.path.join(d, "deck_applied.k")), (sorted(kinds(rep)), det[:300]))

    d = stage(EX, "c13")
    p = plan_load(d)
    for r in p["parts"]:
        if r["pid"] == 5:
            r["fragment"] = {"ok": False, "why": "OCC 피처 지우기 실패"}
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    refused("C-13 remesh 줄의 조각이 ok false → fragment_failed(PID 5)", rc, out, rep, d, "fragment_failed", 5)

    d = stage(EX, "c14")
    _n, e0, _p, _s, _m = read_deck(os.path.join(d, "deck.k"))
    n4 = sorted(pid_nodes(e0)[4])
    txt = open(os.path.join(d, "deck.k"), encoding="utf-8").read()
    add = ("*SET_NODE_GENERATE\n%10d\n%10d%10d\n*CONTACT_AUTOMATIC_NODES_TO_SURFACE\n%10d%10d%10d%10d\n\n\n*END" %
           (3, n4[0], n4[-1], 3, 1, 4, 3))
    write(os.path.join(d, "deck.k"), txt.replace("*END", add))
    reseal(d)
    rc, out, rep = apply_case(binary, d)
    check("C-14 _GENERATE 절점 세트(정본 칸 표 밖)와 그 세트를 면으로 쓰는 접촉 → set_member · contact_side(PID 4)",
          rc == 1 and {"set_member", "contact_side"} <= kinds(rep, 4) and
          not os.path.exists(os.path.join(d, "deck_applied.k")), sorted(kinds(rep)))

    d = stage(EX, "c15")
    txt = open(os.path.join(d, "deck.k"), encoding="utf-8").read()
    old = "*PART\n$# SPACER_OLD#7\nSPACER_OLD#7\n$#     pid     secid       mid     eosid      hgid      grav    adpopt      tmid\n         7         7         7\n"
    inertia = ("*PART_INERTIA\nSPACER_OLD#7\n         7         7         7\n"
               "       1.0       1.0       1.0     1.0e-6\n       1.0       0.0       0.0       1.0       0.0       1.0\n"
               "       0.0       0.0       0.0       0.0       0.0       0.0\n")
    write(os.path.join(d, "deck.k"), txt.replace(old, inertia))
    reseal(d)
    rc, out, rep = apply_case(binary, d)
    refused("C-15 지우는 PID 7 이 *PART_INERTIA 로 정의됐다 → part_variant(PID 7)", rc, out, rep, d, "part_variant", 7)

    d = stage(EX, "c16")
    txt = open(os.path.join(d, "deck.k"), encoding="utf-8").read()
    write(os.path.join(d, "deck.k"), txt.replace("*END", "*INCLUDE\nextra_loads.k\n*END"))
    write(os.path.join(d, "extra_loads.k"), "*KEYWORD\n*END\n")
    reseal(d)
    rc, out, rep = apply_case(binary, d)
    refused("C-16 *INCLUDE 가 있는 덱 → deck_include(v1 에는 deck.includes 가 없다)", rc, out, rep, d, "deck_include")


def part_d(binary):
    print("[D 개행 — CRLF 덱은 CRLF 로 · CRLF 로 바뀐 조각은 값 대조로 받고 경고]")
    d = stage(EX, "d1")
    txt = open(os.path.join(d, "deck.k"), encoding="utf-8").read()
    write(os.path.join(d, "deck.k"), txt, newline="\r\n")
    reseal(d)
    rc, out, rep = apply_case(binary, d)
    body = open(os.path.join(d, "deck_applied.k"), "rb").read() if rc == 0 else b""
    lone = body.count(b"\n") - body.count(b"\r\n")
    check("D-1 CRLF 덱 → rc 0 · 산출에 LF 단독 줄이 없다", rc == 0 and body.count(b"\r\n") > 1000 and lone == 0,
          (rc, lone, out[-300:]))

    d = stage(EX, "d2")
    fp = os.path.join(d, "fragment_4.k")
    write(fp, open(fp, encoding="utf-8").read(), newline="\r\n")
    rc, out, rep = apply_case(binary, d)
    warn = {(x.get("pid"), x["kind"]) for x in rep.get("warnings", [])}
    pr = {r["pid"]: r for r in rep.get("parts", [])}
    fn, _fe = frag_lines(fp)
    n1 = read_deck(os.path.join(d, "deck_applied.k"))[0] if rc == 0 else {}
    check("D-2 LF→CRLF 로 바뀐 조각 → 값 대조로 받는다 · fragment_bytes 경고 · 좌표 글자 그대로",
          rc == 0 and (4, "fragment_bytes") in warn and pr[4]["result"] == "applied" and
          all(n1.get(n, ("",))[0] == t for n, t in fn.items()), (rc, warn, out[-300:]))

    d = stage(EX, "d3")
    write(os.path.join(d, "spare.k"), "*KEYWORD\n*END\n")
    p = plan_load(d)
    p["files"]["spare.k"] = {"sha256": "0" * 64, "bytes": 15}
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    check("D-3 어느 줄도 안 쓰는 조각 파일의 바이트가 다르다 → 적용하되 file_mismatch_unused 경고",
          rc == 0 and "file_mismatch_unused" in {x["kind"] for x in rep.get("warnings", [])}, (rc, out[-300:]))


def part_e(binary):
    print("[E YAML]")
    d = stage(EX, "e")
    rc, out, _rep = apply_case(binary, d, "model: deck.k\nplan: plan.json\noutput: x.k\nflatten_includes: true\n", "x_carryover.json")
    check("E-1 모르는 키(flatten_includes)는 거절", rc == 1 and "모르는 키" in out and not os.path.exists(os.path.join(d, "x.k")),
          out[-200:])
    before = sha(os.path.join(d, "deck.k"))
    rc, out, _rep = apply_case(binary, d, "model: deck.k\nplan: plan.json\noutput: deck.k\n", "deck_carryover.json")
    check("E-2 output 이 model 과 같으면 거절 — 입력 덱이 그대로", rc == 1 and sha(os.path.join(d, "deck.k")) == before, out[-200:])
    rc, out, rep = apply_case(binary, d, "model: deck.k\nplan: plan.json\noutput: y.k\nreport: my_report.json\n", "my_report.json")
    check("E-3 report 를 주면 그 이름으로 쓴다", rc == 0 and rep.get("ok") is True, out[-200:])


def part_f(binary):
    print("[F 바닥 — 보 요소(EID 2600)가 솔리드 · 셸 최대(2578) 위에 있으면 조각 요소를 그 위로 옮긴다]")
    d = stage(EX, "f")
    txt = open(os.path.join(d, "deck.k"), encoding="utf-8").read()
    write(os.path.join(d, "deck.k"), txt.replace("*END", "*ELEMENT_BEAM\n%8d%8d%8d%8d\n*END" % (2600, 1, 1, 2)))
    reseal(d)
    rc, out, rep = apply_case(binary, d)
    pr = {r["pid"]: r for r in rep.get("parts", [])}
    warn = {x["kind"] for x in rep.get("warnings", [])}
    check("F-1 rc 0 · shift {node 0, elem 22} · shift 경고 · 넣은 요소 2601~ · not_checked 없음(보는 칸 자리를 안다)",
          rc == 0 and rep.get("shift") == {"node": 0, "elem": 22} and "shift" in warn and
          pr[4]["inserted"]["elem"] == [2601, 2868] and pr[4]["inserted"]["node"] == [3421, 3712], (rc, rep.get("shift"), out[-400:]))
    e1 = read_deck(os.path.join(d, "deck_applied.k"))[1] if rc == 0 else {}
    check("F-2 산출 — 보 EID 2600 과 넣은 요소(2601~4473)가 겹치지 않는다",
          rc == 0 and 2600 not in e1 and e1.get(2601, (0,))[0] == 4 and e1.get(4473, (0,))[0] == 6, (e1.get(2601), e1.get(4473)))
    write(os.path.join(d, "fl.yaml"), "model: deck.k\noutput: floor.json\n")
    rc2, _o = run(binary, d, "id_floor", "fl.yaml")
    fl = json.load(open(os.path.join(d, "floor.json"), encoding="utf-8")) if rc2 == 0 else {}
    check("F-3 id_floor 도 같은 바닥(elem_start 2601)", fl.get("elem_start") == 2601, fl)


def part_g(binary):
    print("[G 품질 관문 — 새로 뒤집힌 솔리드 · 법선이 뒤집힌 셸이면 쓴 덱을 지운다]")
    d = stage(EX, "g1")
    p = plan_load(d)
    head = next(r for r in p["parts"] if r["pid"] == 2)["field"]
    lay = {e["name"]: e for e in head["layout"]}
    fp = os.path.join(d, head["file"])
    b = bytearray(open(fp, "rb").read())
    ids, disp = read_field(d, head)
    i = next(k for k in range(len(ids)) if disp[3 * k + 1] > 0)      # y = 16.5 면의 절점 하나를
    struct.pack_into("<d", b, lay["disp"]["offset"] + 8 * (3 * i + 1), -50.0)   # 반대 면 너머로
    open(fp, "wb").write(bytes(b))
    reseal(d, files=[head["file"]])
    rc, out, rep = apply_case(binary, d)
    refused("G-1 morph 이 솔리드를 뒤집는다 → quality_inverted(PID 2) · 산출을 지웠다", rc, out, rep, d, "quality_inverted", 2)

    d = stage(EX, "g2")
    n0, e0, _p, _s, _m = read_deck(os.path.join(d, "deck.k"))
    can = sorted(pid_nodes(e0)[4])
    q = next(ns for _eid, (pid, ns) in sorted(e0.items()) if pid == 4 and ns[2] != ns[3])
    a, c = q[0], q[2]
    disp = []
    for n in can:
        if n == a:
            disp += [2 * (n0[c][1][k] - n0[a][1][k]) for k in range(3)]   # a 를 c 너머로 — 대각선 a→c 가 뒤집힌다
        else:
            disp += [0.0, 0.0, 0.0]
    N = len(can)
    off_d = (4 * N + 7) // 8 * 8
    off_k = off_d + 24 * N
    blob = struct.pack("<%dI" % N, *can) + b"\0" * (off_d - 4 * N) + struct.pack("<%dd" % (3 * N), *disp) + bytes([1] * N)
    open(os.path.join(d, "field_4.bin"), "wb").write(blob)
    p = plan_load(d)
    tpl = next(r for r in p["parts"] if r["pid"] == 2)["field"]
    for r in p["parts"]:
        if r["pid"] == 4:
            r.pop("fragment")
            r["action"] = "morph"
            f = json.loads(json.dumps(tpl))
            f.update({"file": "field_4.bin", "nodes": N, "bytes": len(blob), "surface_nodes": N})
            f["layout"] = [{"name": "node", "dtype": "<u4", "offset": 0, "count": N},
                           {"name": "disp", "dtype": "<f8", "offset": off_d, "shape": [N, 3], "unit": "mm"},
                           {"name": "kind", "dtype": "<u1", "offset": off_k, "count": N, "shared_bit": 8}]
            r["field"] = f
    plan_save(d, p)
    reseal(d, files=["field_4.bin"])
    rc, out, rep = apply_case(binary, d)
    refused("G-2 셸 모프가 법선을 뒤집는다 → quality_flipped(PID 4) · 산출을 지웠다", rc, out, rep, d, "quality_flipped", 4)
    fl = next((r for r in rep.get("parts", []) if r["pid"] == 4), {})
    check("G-3 보고에 그 PID 의 flipped 수가 있다", fl.get("flipped", 0) >= 1 and fl.get("result") == "refused", fl)


if __name__ == "__main__":
    sys.exit(main())
