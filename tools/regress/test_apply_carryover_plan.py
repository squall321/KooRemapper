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
  · 거절 — rc 1 · 보고 ok false · output_written false · 그 갈래(kind)가 있다 · 산출 덱이 없다 · 임시 파일이 남지 않는다 ·
    다른 줄도 적용하지 않았다
  · 개행 — CRLF 덱은 CRLF 로 나간다 · CRLF 로 바뀐 조각은 값 대조로 받고 경고한다

무엇을 보나.
  A 진리값 판(examples/apply_carryover_plan) · B 12 파트 덱(mesh12) · C 거절 · D 개행 · E YAML · F 바닥(보 요소) · G 품질 관문
  H 덱이 숨긴 것(리뷰 11-07) — 리더가 담지 않는 요소 블록 · 정본 밖 참조 · 풀 수 없는 세트 · EID 겹침 · *END 없음
  I 계획의 실제 꼴(리뷰 11-07) — 돌린 강체의 반올림 · 셸 회전 · 셸 새 섹션 T1 · 못 지은 조각 · check 없는 transform · 이름 주입
  J 산출 자리(리뷰 11-07) — 확장자가 아닌 몫으로 가른 동반 파일 · 거절해도 앞 산출은 그대로다(11-07 밤)
  K 출력 규칙(사용자 결정 11-07 밤) — 임시 파일 + 바꿔 넣기 · 거절 · 실패면 앞 파일 그대로 · 설정 YAML · 폴더는 쓰지도 지우지도 않는다
  L StepForge 권고 넷(그쪽 591d5b5 · D-681 — 사용자 결정 11-07 밤) — 요소 _TITLE 블록 · 정수 칸의 실수 꼴 · 열 재질 MID · 두 번 정의된 SECID · MID
    · L-5 보 _ELBOW · _WARPAGE 를 다른 보처럼(공용 걸음이 MN · SN1 · SN2 를 읽는다)

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


def tmp_left(d):
    """이번 실행이 남긴 임시 파일(`.<이름>.kr_tmp_…`) — 거절 · 성공 어느 쪽이든 남으면 안 된다."""
    return sorted(n for n in os.listdir(d) if n.startswith(".") and ".kr_tmp_" in n)


def refused(name, rc, out, rep, d, kind, pid=None, out_name="deck_applied.k"):
    ok = (rc == 1 and rep.get("ok") is False and rep.get("output_written") is False and kind in kinds(rep, pid) and
          not os.path.exists(os.path.join(d, out_name)) and rep.get("deck", {}).get("sha256_out") is None and not tmp_left(d))
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
        part_h(binary)
        part_i(binary)
        part_j(binary)
        part_k(binary)
        part_l(binary)
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
    check("A-11 옮기기만 한 PID(회전 없음)에는 orientation_not_rotated 경고가 없다",
          "orientation_not_rotated" not in {x["kind"] for x in rep["warnings"]}, rep["warnings"])


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


# ── 리뷰 11-07 — 덱이 숨긴 것 · 계획의 실제 꼴 · 산출 자리 ─────────────────────────────────────

def add_before_end(d, text):
    """덱의 *END 앞에 블록을 넣고 계획의 deck.sha256 을 다시 박는다."""
    p = os.path.join(d, "deck.k")
    write(p, open(p, encoding="utf-8").read().replace("*END", text + "*END"))
    reseal(d)


def deck_line(d, keyword):
    """그 키워드 줄의 1-기반 줄 번호(첫 것)."""
    for i, ln in enumerate(open(os.path.join(d, "deck.k"), encoding="utf-8").read().split("\n")):
        if ln.strip().upper() == keyword:
            return i + 1
    return -1


def details(rep, kind):
    return " ".join(x["detail"] for x in rep.get("problems", []) if x["kind"] == kind)


def keep_only(d, but=()):
    """계획의 줄을 keep 으로(but 의 PID 는 그대로) · 새 파트의 조각은 null 로."""
    p = plan_load(d)
    for r in p["parts"]:
        if r["pid"] in but:
            continue
        for k in ("transform", "translation", "rotation_deg", "check", "field", "instead", "fragment", "shared_nodes"):
            r.pop(k, None)
        r["action"] = "keep"
    for a in p["added"]:
        a["fragment"] = None
    plan_save(d, p)


def solid_eid_of(e0, pid):
    return min(eid for eid, (p, ns) in e0.items() if p == pid and len(ns) == 8)


def part_h(binary):
    print("[H 덱이 숨긴 것 — 리더가 담지 않는 요소 블록 · 정본 밖 참조 · 풀 수 없는 세트 · EID 겹침 · *END 없음]")
    _n, e0, _p, _s, _m = read_deck(os.path.join(EX, "deck.k"))
    pn = pid_nodes(e0)
    n1, n4, n7 = sorted(pn[1]), sorted(pn[4]), sorted(pn[7])
    ortho = ("*ELEMENT_SOLID_ORTHO\n" + "%8d%8d" % (9000, 8) + "".join("%8d" % n for n in n7[:8]) + "\n" +
             "%16.6e%16.6e%16.6e\n%16.6e%16.6e%16.6e\n" % (1.0, 0.0, 0.0, 0.0, 1.0, 0.0))
    d = stage(EX, "h1")
    add_before_end(d, ortho)
    rc, out, rep = apply_case(binary, d)
    refused("H-1 *ELEMENT_SOLID_ORTHO(리더가 담지 않는 변형)가 지우는 PID 7 의 절점을 쓴다 → opaque_elements", rc, out, rep, d,
            "opaque_elements")
    det = details(rep, "opaque_elements")
    check("H-1b 그 키워드와 줄을 말한다", "*ELEMENT_SOLID_ORTHO(줄 %d" % deck_line(d, "*ELEMENT_SOLID_ORTHO") in det, det[:300])
    keep_only(d)
    rc, out, rep = apply_case(binary, d)
    check("H-1c keep 뿐인 계획은 같은 덱도 받는다(덱을 고치는 줄이 없다)", rc == 0 and rep.get("ok") is True, (rc, sorted(kinds(rep))))

    d = stage(EX, "h2")
    blocks = (ortho +
              "*ELEMENT_TSHELL_BETA\n" + "%8d%8d" % (9001, 1) + "".join("%8d" % n for n in n1[:8]) + "\n%16.6e\n" % 0.0 +
              "*ELEMENT_SOLID_H8TOH20\n%8d%8d\n" % (9002, 1) + "".join("%8d" % n for n in n1[:8]) + "\n" +
              "*ELEMENT_BEAM_WARPAGE\n%8d%8d%8d%8d%8d\n%8d%8d\n" % (9003, 1, n1[0], n1[1], 0, n1[2], n1[3]))
    add_before_end(d, blocks)
    keep_only(d, but=(3,))
    rc, out, rep = apply_case(binary, d)
    det = details(rep, "opaque_elements")
    refused("H-2 옮기기 하나만 있어도 거절 → opaque_elements", rc, out, rep, d, "opaque_elements")
    check("H-2b 키워드 셋(ORTHO · TSHELL_BETA · H8TOH20)을 모두 말하고 BEAM_WARPAGE 는 말하지 않는다(SN 까지 읽는다 · 11-07 밤)",
          all(k + "(줄 " in det for k in ("*ELEMENT_SOLID_ORTHO", "*ELEMENT_TSHELL_BETA", "*ELEMENT_SOLID_H8TOH20")) and
          "*ELEMENT_BEAM_WARPAGE" not in det, det[:500])
    d = stage(EX, "h2c")
    add_before_end(d, "*ELEMENT_MASS_PART\n%8d%16.6e%16.6e\n" % (7, 0.001, 0.0))   # 절점 칸이 없다(ID ADDMASS FINMASS …)
    rc, out, rep = apply_case(binary, d)
    refused("H-2c *ELEMENT_MASS_PART 가 지우는 PID 7 을 가리킨다 → 거절(파트 칸)", rc, out, rep, d, "ref_unscanned")
    check("H-2d 그것은 절점 칸이 없는 블록이다 — opaque_elements 가 아니다", "opaque_elements" not in kinds(rep), sorted(kinds(rep)))
    keep_only(d, but=(3,))
    rc, out, rep = apply_case(binary, d)
    check("H-2e 같은 덱에 옮기기만 하면 받는다", rc == 0 and rep.get("ok") is True, (rc, sorted(kinds(rep))))

    d = stage(EX, "h3")
    lines = open(os.path.join(d, "deck.k"), encoding="utf-8").read().split("\n")
    se = solid_eid_of(e0, 1)
    kw = ""
    for i, ln in enumerate(lines):
        if ln.startswith("*"):
            kw = ln.strip().upper()
        elif kw == "*ELEMENT_SHELL" and ln.strip() and not ln.startswith("$"):
            lines[i] = "%8d" % se + ln[8:]                 # 셸(PID 4 — remesh) 하나가 솔리드(PID 1 — keep)의 EID 를 쓴다
            break
    write(os.path.join(d, "deck.k"), "\n".join(lines))
    reseal(d)
    rc, out, rep = apply_case(binary, d)
    det = details(rep, "eid_collision")
    refused("H-3 셸과 솔리드가 EID 하나를 나눠 쓴다 → eid_collision", rc, out, rep, d, "eid_collision")
    check("H-3b 겹친 EID 와 두 키워드를 말한다", ("EID %d(" % se) in det and "*ELEMENT_SOLID 줄" in det and "*ELEMENT_SHELL 줄" in det,
          det[:300])
    d = stage(EX, "h3c")
    add_before_end(d, "*ELEMENT_BEAM\n%8d%8d%8d%8d\n" % (se, 1, 1, 2))
    rc, out, rep = apply_case(binary, d)
    refused("H-3c 보가 솔리드의 EID 를 쓴다 → eid_collision(*ELEMENT_BEAM)", rc, out, rep, d, "eid_collision")
    check("H-3d 보고에 *ELEMENT_BEAM 이 있다", "*ELEMENT_BEAM" in details(rep, "eid_collision"), details(rep, "eid_collision")[:300])

    d = stage(EX, "h4")
    add_before_end(d, "*SET_NODE_LIST\n%10d\n%10d%10d\n*CONSTRAINED_SHELL_TO_SOLID\n%10d%10d\n" % (91, 1, 2, n7[0], 91))
    rc, out, rep = apply_case(binary, d)
    refused("H-4 *CONSTRAINED_SHELL_TO_SOLID 가 지우는 PID 7 의 절점을 가리킨다(정본 밖) → ref_unscanned", rc, out, rep, d,
            "ref_unscanned")
    det = details(rep, "ref_unscanned")
    check("H-4b 키워드와 줄을 한 번 말한다", det.count("*CONSTRAINED_SHELL_TO_SOLID(줄 %d" % deck_line(d, "*CONSTRAINED_SHELL_TO_SOLID")) == 1,
          det[:300])

    d = stage(EX, "h5")
    add_before_end(d, "*INITIAL_VELOCITY_RIGID_BODY\n%10d%10.1f%10.1f%10.1f\n" % (7, 1.0, 0.0, 0.0))
    rc, out, rep = apply_case(binary, d)
    refused("H-5 *INITIAL_VELOCITY_RIGID_BODY 가 지우는 PID 7 을 가리킨다(파트 칸) → ref_unscanned", rc, out, rep, d, "ref_unscanned")
    p = plan_load(d)
    for r in p["parts"]:
        if r["pid"] == 7:
            r["action"] = "keep"
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    check("H-5b 지우지 않으면(바꿔 넣기 · 옮기기만) PID 로 건 참조는 산다 → rc 0", rc == 0 and rep.get("ok") is True, (rc, sorted(kinds(rep))))

    d = stage(EX, "h6")
    add_before_end(d, "*SET_NODE_GENERAL\n%10d\nPART      %10d\n" % (92, 7))
    rc, out, rep = apply_case(binary, d)
    refused("H-6 *SET_NODE_GENERAL(PART 7 — 풀 수 없는 방언) → set_unresolved", rc, out, rep, d, "set_unresolved")
    d = stage(EX, "h6b")
    add_before_end(d, "*SET_DISCRETE_LIST\n%10d\n%10d\n" % (93, 1))
    rc, out, rep = apply_case(binary, d)
    refused("H-6b 종류를 모르는 세트(*SET_DISCRETE_LIST) → ref_unscanned", rc, out, rep, d, "ref_unscanned")

    curve = "*DEFINE_CURVE\n%10d\n%20.6e%20.6e\n%20.6e%20.6e\n" % (9, 0.0, 1.0, 1.0, 1.0)
    d = stage(EX, "h7")
    add_before_end(d, curve + "*LOAD_NODE_POINT\n%10d%10d%10d%10.1f%10d%10d%10d%10d\n" % (n1[0], 4, 9, 1.0, 0, n4[0], n4[1], n4[2]))
    rc, out, rep = apply_case(binary, d)
    refused("H-7 *LOAD_NODE_POINT 의 M1-M3(따름 힘 절점)이 바꿔 넣는 PID 4 의 절점 → ref_unscanned", rc, out, rep, d, "ref_unscanned")
    d = stage(EX, "h7b")
    add_before_end(d, curve + "*LOAD_NODE_POINT\n%10d%10d%10d%10.1f\n" % (n1[0], 3, 9, 1.0))
    rc, out, rep = apply_case(binary, d)
    check("H-7b M1-M3 가 비면 정본이 읽는다 → rc 0", rc == 0 and rep.get("ok") is True, (rc, sorted(kinds(rep))))

    d = stage(EX, "h8")
    typical = ("*CONTROL_TERMINATION\n%10.4f\n*CONTROL_TIMESTEP\n%10.1f%10.2f\n*CONTROL_ENERGY\n%10d%10d%10d%10d\n" % (0.01, 0.0, 0.9, 2, 2, 2, 2) +
               "*DATABASE_GLSTAT\n%10.1e\n*DATABASE_MATSUM\n%10.1e\n*DATABASE_BINARY_D3PLOT\n%10.1e\n" % (1e-4, 1e-4, 1e-3) +
               curve + "*HOURGLASS\n%10d%10d\n*DAMPING_GLOBAL\n%10d%10.3f\n" % (1, 4, 0, 0.001) +
               "*SET_NODE_LIST\n%10d\n%10d%10d\n*BOUNDARY_SPC_SET\n%10d%10d%10d%10d%10d%10d%10d%10d\n" % (95, 1, 2, 95, 0, 1, 1, 1, 0, 0, 0) +
               "*INITIAL_VELOCITY\n%10d\n%10.1f%10.1f%10.1f\n" % (95, 0.0, 0.0, -1000.0) +
               "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n%10d%10d%10d%10d\n\n\n" % (1, 8, 3, 3))
    add_before_end(d, typical)
    rc, out, rep = apply_case(binary, d)
    check("H-8 흔한 제어 · 출력 · 곡선 · 세트 구속 · 초기 속도 · PID 접촉(지우지 않는 파트)은 받는다 → rc 0",
          rc == 0 and rep.get("ok") is True and not kinds(rep), (rc, sorted(kinds(rep)), details(rep, "ref_unscanned")[:300]))

    d = stage(EX, "h9")
    write(os.path.join(d, "deck.k"), open(os.path.join(d, "deck.k"), encoding="utf-8").read().replace("*END\n", ""))
    reseal(d)
    rc, out, rep = apply_case(binary, d)
    refused("H-9 *END 가 없는 덱에 조각을 넣는다 → deck_no_end", rc, out, rep, d, "deck_no_end")
    keep_only(d, but=(3,))
    rc, out, rep = apply_case(binary, d)
    check("H-9b 조각이 없으면(옮기기만) *END 가 없어도 받는다", rc == 0 and rep.get("ok") is True, (rc, sorted(kinds(rep))))


def part_i(binary):
    print("[I 계획의 실제 꼴 — 돌린 강체의 반올림 · 셸 회전 · 셸 새 섹션 T1 · 못 지은 조각 · check 없는 transform · 이름 주입]")
    c, s = 0.920504853, 0.390731128          # z 축 23° — StepForge 가 round(x, 9) 로 싣는 꼴(max|RᵀR − I| ≈ 1.2e-9)
    m = [c, -s, 0.0, 4.70226275, s, c, 0.0, -3.112359819, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    d = stage(EX, "i1")
    p = plan_load(d)
    for r in p["parts"]:
        if r["pid"] == 3:
            r.update({"transform": m, "translation": [m[3], m[7], m[11]], "rotation_deg": 23.0})
            r.pop("check", None)                 # StepForge 는 확인 재료가 없으면 check 를 쓰지 않는다
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    n0 = read_deck(os.path.join(d, "deck.k"))[0]
    n1 = read_deck(os.path.join(d, "deck_applied.k"))[0] if rc == 0 else {}
    pn = pid_nodes(read_deck(os.path.join(d, "deck.k"))[1])
    worst = max((abs(n1[n][1][k] - (m[4 * k] * n0[n][1][0] + m[4 * k + 1] * n0[n][1][1] + m[4 * k + 2] * n0[n][1][2] + m[4 * k + 3]))
                 for n in pn[3] for k in range(3)), default=9) if rc == 0 else 9
    warn = {(x.get("pid"), x["kind"]) for x in rep.get("warnings", [])}
    # 1e-7 — 돌린 좌표는 16 칸 글자(유효 10 자리 남짓)로 쓰여 ~5e-9 까지 반올림된다(옮기기만 한 A-4 는 글자가 정확하다)
    check("I-1 z 축 23° 강체(칸 반올림 9 자리 · check 없음) → rc 0 · 절점 = R x + t(1e-7)", rc == 0 and worst < 1e-7, (rc, worst, out[-300:]))
    check("I-1b 돌린 PID 에 orientation_not_rotated 경고(PID 3)", (3, "orientation_not_rotated") in warn, warn)

    d = stage(EX, "i2")
    p = plan_load(d)
    for r in p["parts"]:
        if r["pid"] == 3:
            r["transform"][0] = 1.0000123456789
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    refused("I-2 늘린 4×4(1.0000123456789 — 허용 1e-6 밖) → transform_not_rigid", rc, out, rep, d, "transform_not_rigid", 3)
    check("I-2b det 을 유효 12 자리로 말한다", "det(R) = 1.00001234568" in details(rep, "transform_not_rigid"),
          details(rep, "transform_not_rigid")[:300])

    d = stage(EX, "i3")
    p = plan_load(d)
    for r in p["parts"]:
        if r["pid"] == 4:                        # CAN(셸) — x 축 180° 강체(y=10 · z=5 둘레)
            r.pop("fragment")
            r.update({"action": "transform", "transform": [1.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 20.0, 0.0, 0.0, -1.0, 10.0, 0.0, 0.0, 0.0, 1.0],
                      "translation": [0.0, 20.0, 10.0], "rotation_deg": 180.0})
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    pr = {r["pid"]: r for r in rep.get("parts", [])}
    check("I-3 셸 PID 를 180° 돌린다 → rc 0 · quality_flipped 없음 · applied(옮기기는 법선을 뒤집지 못한다)",
          rc == 0 and pr.get(4, {}).get("result") == "applied" and "quality_flipped" not in kinds(rep), (rc, sorted(kinds(rep))))

    def shell_section(d, t_plan, t1_text):
        fp = os.path.join(d, "fragment_4.k")
        txt = open(fp, encoding="utf-8").read()
        txt = txt.replace("         4         4         4\n", "         4        10         4\n*SECTION_SHELL_TITLE\nCAN#4_sec\n"
                          "        10         2         1         2\n" + ("%10s" % t1_text) * 4 + "\n", 1)
        write(fp, txt)
        p = plan_load(d)
        for r in p["parts"]:
            if r["pid"] == 4:
                r["fragment"].update({"secid": 10, "new_section": {"secid": 10, "elform": 2, "nip": 2, "t": t_plan, "why": "두께가 바뀌었다"},
                                      "bytes": os.path.getsize(fp)})
        plan_save(d, p)
        reseal(d, files=["fragment_4.k"])

    d = stage(EX, "i4")
    shell_section(d, 0.612345678, "0.61235")     # StepForge 는 T1 을 %10.5g 로 쓴다
    rc, out, rep = apply_case(binary, d)
    p1, s1 = read_deck(os.path.join(d, "deck_applied.k"))[2:4] if rc == 0 else ({}, {})
    check("I-4 셸 새 섹션 T1 0.61235(%10.5g) 대 계획 t 0.612345678 → rc 0 · *PART 4 → SECID 10",
          rc == 0 and p1.get(4, (0,))[0] == 10 and s1.get(10, ("",))[0] == "*SECTION_SHELL_TITLE", (rc, sorted(kinds(rep)), out[-300:]))
    d = stage(EX, "i4b")
    shell_section(d, 0.6125, "0.61235")
    rc, out, rep = apply_case(binary, d)
    refused("I-4b T1 이 상대 1e-4 밖(0.61235 대 0.6125) → fragment", rc, out, rep, d, "fragment", 4)

    d = stage(EX, "i5")
    p = plan_load(d)
    for r in p["parts"]:
        if r["pid"] == 5:                        # StepForge `target_shape` 실패 — why 가 null 이고 notes 에 까닭
            r["fragment"] = {"ok": False, "why": None, "notes": {"why": "새 CAD 에서 대상 형상을 못 찾았다", "defeatured": []}}
        if r["pid"] == 6:                        # 지었으나 확인을 못 지났다 — why 없이 check.problems
            r["fragment"]["ok"] = False
            r["fragment"]["check"] = {"ok": False, "problems": ["요소 수 898 가 쓴 수 899 와 다르다"]}
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    f5 = " ".join(x["detail"] for x in rep.get("problems", []) if x.get("pid") == 5 and x["kind"] == "fragment_failed")
    f6 = " ".join(x["detail"] for x in rep.get("problems", []) if x.get("pid") == 6 and x["kind"] == "fragment_failed")
    check("I-5 못 지은 조각의 실제 꼴(notes · why null · check.problems) → fragment_failed 에 그 까닭 · plan_schema 없음",
          rc == 1 and "대상 형상을 못 찾았다" in f5 and "쓴 수 899" in f6 and "plan_schema" not in kinds(rep), (sorted(kinds(rep)), f5, f6))

    d = stage(EX, "i6")
    p = plan_load(d)
    for r in p["parts"]:
        if r["pid"] == 4:
            r["name"] = "CAN\n*BOUNDARY_SPC_NODE\n       1       0       1       1       1       1       1       1\n$"
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    body = open(os.path.join(d, "deck_applied.k"), encoding="utf-8").read().split("\n") if rc == 0 else []
    live = [ln for ln in body if ln.strip().upper().startswith("*BOUNDARY_SPC_NODE")]
    head = [ln for ln in body if ln.startswith("$ === apply_carryover_plan") and "*BOUNDARY_SPC_NODE" in ln]
    check("I-6 이름의 개행은 주석 줄을 끊지 못한다 — 살아 있는 *BOUNDARY_SPC_NODE 가 없고 머리 주석 한 줄에 남는다",
          rc == 0 and not live and len(head) == 1, (rc, live[:2], head[:1]))


def part_j(binary):
    print("[J 산출 자리 — 확장자가 아닌 몫으로 가른 동반 파일 · 거절하면 옛 산출을 지운다]")
    def rename_field(d):
        os.rename(os.path.join(d, "field_2.bin"), os.path.join(d, "field_2.k"))
        p = plan_load(d)
        p["files"]["field_2.k"] = p["files"].pop("field_2.bin")
        for r in p["parts"]:
            if r["pid"] == 2:
                r["field"]["file"] = "field_2.k"
        plan_save(d, p)

    d = stage(EX, "j1")
    rename_field(d)
    rc, out, rep = apply_case(binary, d)
    check("J-1 .k 로 이름 지은 변위장(바이트 그대로) → 변위장으로 읽고 rc 0", rc == 0 and rep.get("ok") is True, (rc, sorted(kinds(rep))))
    d = stage(EX, "j1b")
    rename_field(d)
    fp = os.path.join(d, "field_2.k")
    b = bytearray(open(fp, "rb").read())
    b[800] ^= 0x01
    open(fp, "wb").write(bytes(b))
    rc, out, rep = apply_case(binary, d)
    refused("J-1b .k 이름 변위장의 바이트가 다르다 → file_mismatch · 보고가 있다(예외로 끝나지 않는다)", rc, out, rep, d, "file_mismatch")

    d = stage(EX, "j2")
    write(os.path.join(d, "spare.bin"), "x")
    p = plan_load(d)
    p["files"]["spare.bin"] = {"sha256": "0" * 64, "bytes": 1}
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    check("J-2 어느 줄도 안 쓰는 .bin 의 지문이 다르다 → 확장자가 아니라 몫(없음)으로 — 적용하고 file_mismatch_unused 경고",
          rc == 0 and "file_mismatch_unused" in {x["kind"] for x in rep.get("warnings", [])}, (rc, sorted(kinds(rep))))

    d = stage(EX, "j3")
    old = "*KEYWORD\n$ 앞선 실행이 남긴 덱\n*END\n"
    write(os.path.join(d, "deck_applied.k"), old)
    p = plan_load(d)
    p["deck"]["sha256"] = "0" * 64
    plan_save(d, p)
    rc, out, rep = apply_case(binary, d)
    check("J-3 거절해도 출력 자리의 앞 파일은 그대로다(사용자 결정 11-07 밤 — extract-parts 와 같은 규칙) · ok false · output_written false",
          rc == 1 and rep.get("ok") is False and rep.get("output_written") is False and "deck_sha" in kinds(rep) and
          open(os.path.join(d, "deck_applied.k"), encoding="utf-8").read() == old and not tmp_left(d), (rc, sorted(kinds(rep)), tmp_left(d)))
    check("J-3b 지우지 않았으니 stale_output_removed 경고도 없다", "stale_output_removed" not in {x["kind"] for x in rep.get("warnings", [])},
          rep.get("warnings"))


def part_k(binary):
    print("[K 출력 규칙 — 임시 파일에 쓰고 끝까지 지나면 바꿔 넣는다 · 거절 · 실패면 앞 파일 그대로(사용자 결정 11-07 밤)]")
    base = "model: deck.k\nplan: plan.json\n"
    old = "*KEYWORD\n$ 앞선 실행이 남긴 덱\n*END\n"
    # K-1 report 가 설정 YAML — 보고 자리가 없다 · 콘솔로만 거절하고 아무것도 쓰지 않는다(예전엔 설정을 보고로 덮고 rc 0)
    d = stage(EX, "k1")
    yaml = base + "output: out.k\nreport: a.yaml\n"
    rc, out, _rep = apply_case(binary, d, yaml=yaml, report="no_report.json")
    check("K-1 report 가 설정 YAML → rc 1 · 설정 그대로 · 덱 · 보고 둘 다 쓰지 않는다",
          rc == 1 and open(os.path.join(d, "a.yaml"), encoding="utf-8").read() == yaml and not os.path.exists(os.path.join(d, "out.k")) and
          not tmp_left(d), (rc, out[-300:]))
    # K-2 output 이 설정 파일(이름이 c.k) — 보고에 output_clobber · 설정 그대로(예전엔 쓰기 관문에 걸린 뒤 「옛 산출」로 지웠다)
    d = stage(EX, "k2")
    yaml = base + "output: c.k\n"
    write(os.path.join(d, "c.k"), yaml)
    rc, out = run(binary, d, OP, "c.k")
    rp = os.path.join(d, "c_carryover.json")
    rep = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}
    check("K-2 output 이 설정 파일 → rc 1 · output_clobber · 설정이 그대로 있다 · output_written false",
          rc == 1 and "output_clobber" in kinds(rep) and rep.get("output_written") is False and os.path.exists(os.path.join(d, "c.k")) and
          open(os.path.join(d, "c.k"), encoding="utf-8").read() == yaml and not tmp_left(d), (rc, sorted(kinds(rep)), out[-300:]))
    # K-3 output 자리가 빈 폴더 — 폴더는 쓰지도 지우지도 않는다(예전엔 「옛 산출」로 rmdir 했다)
    d = stage(EX, "k3")
    os.makedirs(os.path.join(d, "deck_applied.k"))
    rc, out, rep = apply_case(binary, d)
    check("K-3 output 자리가 폴더 → rc 1 · output_clobber · 폴더가 그대로 있다",
          rc == 1 and "output_clobber" in kinds(rep) and os.path.isdir(os.path.join(d, "deck_applied.k")) and not tmp_left(d),
          (rc, sorted(kinds(rep)), out[-300:]))
    # K-4 쓴 뒤 품질 관문에서 걸린다(G-1 의 뒤집는 모프) — 앞 파일 그대로 · 임시 파일 없음(예전엔 덮어쓴 뒤 지웠다)
    d = stage(EX, "k4")
    write(os.path.join(d, "deck_applied.k"), old)
    p = plan_load(d)
    head = next(r for r in p["parts"] if r["pid"] == 2)["field"]
    lay = {e["name"]: e for e in head["layout"]}
    fp = os.path.join(d, head["file"])
    b = bytearray(open(fp, "rb").read())
    ids, disp = read_field(d, head)
    i = next(k for k in range(len(ids)) if disp[3 * k + 1] > 0)
    struct.pack_into("<d", b, lay["disp"]["offset"] + 8 * (3 * i + 1), -50.0)
    open(fp, "wb").write(bytes(b))
    reseal(d, files=[head["file"]])
    rc, out, rep = apply_case(binary, d)
    check("K-4 쓴 뒤 품질 관문에서 걸렸다 → rc 1 · quality_inverted · 앞 파일 그대로 · output_written false · 임시 파일 없음",
          rc == 1 and "quality_inverted" in kinds(rep) and rep.get("output_written") is False and
          open(os.path.join(d, "deck_applied.k"), encoding="utf-8").read() == old and not tmp_left(d), (rc, sorted(kinds(rep)), tmp_left(d)))
    # K-5 성공 — 앞 파일을 바꿔 넣는다 · 보고의 sha256_out 이 그 자리의 바이트 · output_written true · 임시 파일 없음
    d = stage(EX, "k5")
    write(os.path.join(d, "deck_applied.k"), old)
    rc, out, rep = apply_case(binary, d)
    check("K-5 성공 → 바꿔 넣었다(sha256_out = 산출 바이트) · output_written true · 임시 파일 없음",
          rc == 0 and rep.get("output_written") is True and rep.get("deck", {}).get("sha256_out") == sha(os.path.join(d, "deck_applied.k")) and
          not tmp_left(d), (rc, rep.get("output_written"), tmp_left(d)))


def titled_block(d, pid, title, kw="*ELEMENT_SOLID_TITLE"):
    """PID 의 솔리드 요소 줄을 *ELEMENT_SOLID 에서 빼 `kw` 블록(제목 줄 하나)으로 옮기고 계획의 덱 지문을 맞춘다."""
    lines = open(os.path.join(d, "deck.k"), encoding="utf-8").read().split("\n")
    s0 = lines.index("*ELEMENT_SOLID")
    e0 = next(i for i in range(s0 + 1, len(lines)) if lines[i].startswith("*"))
    moved, kept = [], []
    for l in lines[s0 + 1:e0]:
        (moved if (l.strip() and not l.startswith("$") and int(l[8:16]) == pid) else kept).append(l)
    assert moved
    write(os.path.join(d, "deck.k"), "\n".join(lines[:s0 + 1] + kept + [kw, title] + moved + lines[e0:]))
    reseal(d)
    return len(moved)


def part_l(binary):
    print("[L StepForge 권고 넷(D-681) — LS-DYNA 가 덱을 읽는 꼴로 가른다]")
    # L-1 요소 `_TITLE` 블록 — TITLE 은 설명서 옵션이 아니어서 첫 줄이 제목 카드인지 근거가 없다(우리 리더는 숫자꼴 제목을 요소로 읽는다)
    d = stage(EX, "l1")
    n = titled_block(d, 3, "bracket solids")
    rc, out, rep = apply_case(binary, d)
    refused("L-1 고치는 PID 3(transform)의 요소 %d 개가 *ELEMENT_SOLID_TITLE 블록에 → opaque_elements(PID 3)" % n, rc, out, rep, d,
            "opaque_elements", 3)
    d = stage(EX, "l1b")
    titled_block(d, 1, "housing solids")
    rc, out, rep = apply_case(binary, d)
    pr = {r["pid"]: r for r in rep.get("parts", [])}
    check("L-1b keep PID 1 의 요소가 _TITLE 블록에 → 받는다(rc 0 · PID 1 은 손대지 않는다 · 다른 줄은 적용)",
          rc == 0 and pr.get(1, {}).get("result") == "skipped" and pr.get(3, {}).get("result") == "applied", (rc, sorted(kinds(rep)), out[-300:]))
    # L-3 열 재질의 번호 이름 *MAT_T01~T18 — TMID 는 MID 와 독립된 번호다(Vol II 2-9 · 3-1) · 공용 MID 훑기가 뺀다
    t01 = ("*MAT_T01\n$#    tmid       tro     tgrlc    tgmult      tlat      hlat\n        50       0.0       0.0       0.0\n"
           "$#      hc        tc\n       1.0       1.0\n")
    d = stage(EX, "l3")
    add_before_end(d, t01)
    write(os.path.join(d, "fl.yaml"), "model: deck.k\noutput: floor.json\n")
    rc2, o2 = run(binary, d, "id_floor", "fl.yaml")
    fl = json.load(open(os.path.join(d, "floor.json"), encoding="utf-8")) if rc2 == 0 else {}
    check("L-3 id_floor — *MAT_T01 의 TMID 50 은 PID · SECID · MID 바닥을 올리지 않는다(pid_start 9 · 예전 51)",
          fl.get("pid_start") == 9, (rc2, fl, o2[-300:]))
    # L-3c 경계 — *MAT_T18_TITLE(제목 줄 뒤 TMID 90 — 예전엔 바닥 91)도 빼고, *MAT_T 로 시작하는 구조 재질(*MAT_TABULATED_JOHNSON_COOK 70)은 센다
    d = stage(EX, "l3c")
    add_before_end(d, "*MAT_T18_TITLE\nispg heat\n        90       0.0\n*MAT_TABULATED_JOHNSON_COOK\n        70       1.0     1.0e5       0.3\n")
    write(os.path.join(d, "fl.yaml"), "model: deck.k\noutput: floor.json\n")
    rc2, o2 = run(binary, d, "id_floor", "fl.yaml")
    fl = json.load(open(os.path.join(d, "floor.json"), encoding="utf-8")) if rc2 == 0 else {}
    check("L-3c *MAT_T18_TITLE 은 빼고 *MAT_TABULATED_JOHNSON_COOK 70 은 센다(pid_start 71)", fl.get("pid_start") == 71, (rc2, fl, o2[-300:]))
    # L-3b 이월 적용 — 바꿔 넣는 BATTERY(PID 6)의 MID 6 이 열 재질로만 있다(*MAT_T01 TMID 6) → 조각의 MID 가 덱에 없다
    d = stage(EX, "l3b")
    deck = os.path.join(d, "deck.k")
    body = open(deck, encoding="utf-8").read()
    old6 = "*MAT_ELASTIC_TITLE\nBATTERY#6_PLACEHOLDER\n$#     mid        ro         e        pr\n         6         1         1       0.3\n"
    assert body.count(old6) == 1
    write(deck, body.replace(old6, t01.replace("        50", "         6")))
    reseal(d)
    rc, out, rep = apply_case(binary, d)
    refused("L-3b 조각(PID 6)의 MID 6 이 *MAT_T01 의 TMID 로만 있다 → fragment(MID 가 덱에 없다)", rc, out, rep, d, "fragment", 6)
    # L-4 손대는 PID 의 SECID · MID 를 두 블록이 정의한다 — LS-DYNA 는 둘째 정의에서 멈춘다(StepForge 도 그 줄에서) · part_duplicate
    d = stage(EX, "l4")
    add_before_end(d, "*SECTION_SOLID\n         3         2\n")
    rc, out, rep = apply_case(binary, d)
    refused("L-4 옮기는 PID 3 의 SECID 3 이 두 번 정의됐다 → part_duplicate(PID 3)", rc, out, rep, d, "part_duplicate", 3)
    check("L-4 보고가 두 정의의 자리를 댄다", "SECID 3 의 정의가 2 개" in details(rep, "part_duplicate"), details(rep, "part_duplicate")[:300])
    d = stage(EX, "l4b")
    add_before_end(d, "*MAT_RIGID\n         2   7.8e-09   2.1e+05       0.3\n")
    rc, out, rep = apply_case(binary, d)
    refused("L-4b 모프하는 PID 2 의 MID 2 가 두 번 정의됐다(*MAT_ELASTIC_TITLE · *MAT_RIGID) → part_duplicate(PID 2)", rc, out, rep, d,
            "part_duplicate", 2)
    d = stage(EX, "l4c")
    add_before_end(d, "*SECTION_SOLID\n         1         2\n")
    rc, out, rep = apply_case(binary, d)
    check("L-4c keep PID 1 의 SECID 1 이 두 번이면 그 줄은 손대지 않으니 거절하지 않는다(rc 0)", rc == 0 and "part_duplicate" not in kinds(rep),
          (rc, sorted(kinds(rep)), out[-300:]))
    # L-4d `_TITLE` 섹션의 빈 제목 줄 — 그 줄이 제목이다(LS-DYNA · StepForge 는 빈 줄도 카드). 예전 첫 카드 훑기는 빈 줄을 건너뛰어 SECID
    #      카드를 제목으로, 두께 3.0 을 SECID 3 으로 읽어 옮기는 PID 3(BRACKET · SECID 3)을 part_duplicate 로 거짓 거절했다(11-08 #4)
    can = ("*SECTION_SHELL_TITLE\nCAN#4_sec\n$#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp\n"
           "         4         2         1         2\n$#      t1        t2        t3        t4\n       0.4       0.4       0.4       0.4\n")
    d = stage(EX, "l4d")
    deck = os.path.join(d, "deck.k")
    body = open(deck, encoding="utf-8").read()
    assert body.count(can) == 1
    write(deck, body.replace(can, can.replace("CAN#4_sec\n", "\n").replace("       0.4       0.4       0.4       0.4", "       3.0       3.0       3.0       3.0")))
    reseal(d)
    rc, out, rep = apply_case(binary, d)
    check("L-4d 셸 섹션의 빈 제목 줄 · 두께 3.0 — SECID 3 이 두 번이 아니다(rc 0 · part_duplicate 없음)",
          rc == 0 and "part_duplicate" not in kinds(rep), (rc, sorted(kinds(rep)), details(rep, "part_duplicate")[:200]))
    # L-4e 한 키워드 아래 쌓인 둘째 묶음이 옮기는 PID 3 의 SECID 3 을 또 정의한다 — 카드 묶음 셈은 그것도 센다(예전 첫 카드 셈은 놓쳤다)
    d = stage(EX, "l4e")
    add_before_end(d, "*SECTION_SOLID\n         7         1\n         3         2\n")
    rc, out, rep = apply_case(binary, d)
    refused("L-4e 쌓인 둘째 묶음의 SECID 3 → part_duplicate(PID 3 — 쌓인 묶음끼리도 센다)", rc, out, rep, d, "part_duplicate", 3)

    # L-5 보 _ELBOW(MN · Card 10) · _WARPAGE(SN1 · SN2 · Card 9) — 공용 걸음이 그 절점을 읽어 다른 보처럼 다룬다(92f50fe · 6341aac).
    #     예전엔 그 블록이 있으면 덱을 고치는 줄을 다 거절했다(opaque_elements)
    _n, e0, _p, _s, _m = read_deck(os.path.join(EX, "deck.k"))
    pn = pid_nodes(e0)
    only1 = sorted(pn[1] - set().union(*(v for k, v in pn.items() if k != 1)))
    n3 = sorted(pn[3])
    elbow = "*ELEMENT_BEAM_ELBOW\n%8d%8d%8d%8d%8d\n%10d\n"
    warp = "*NODE_SCALAR\n%8d%8d\n%8d%8d\n*ELEMENT_BEAM_WARPAGE\n%8d%8d%8d%8d%8d\n%10d%10d\n"
    for tag, block, shared in (
            ("l5", elbow % (9101, 1, only1[0], only1[1], 0, only1[2]), False),
            ("l5b", elbow % (9101, 1, only1[0], only1[1], 0, n3[0]), True),
            ("l5c", warp % (900001, 1, 900002, 1, 9102, 1, only1[0], only1[1], 0, 900001, 900002), False),
            ("l5d", warp % (900001, 1, 900002, 1, 9102, 1, only1[0], only1[1], 0, n3[0], 900002), True)):
        d = stage(EX, tag)
        add_before_end(d, block)
        keep_only(d, but=(3,))
        rc, out, rep = apply_case(binary, d)
        what = "ELBOW 의 MN" if "ELBOW" in block else "WARPAGE 의 SN1"
        if shared:
            refused("%s %s 이 옮기는 PID 3 의 절점 → shared_nodes(PID 3 · 옵션 카드 절점까지 읽는다)" % (("L-" + tag[1:]), what),
                    rc, out, rep, d, "shared_nodes", 3)
        else:
            check("%s %s 이 손대지 않는 절점 → 받는다(그 블록은 다 읽은 블록이다)" % (("L-" + tag[1:]), what),
                  rc == 0 and "opaque_elements" not in kinds(rep), (rc, sorted(kinds(rep)), details(rep, "opaque_elements")[:200]))


if __name__ == "__main__":
    sys.exit(main())
