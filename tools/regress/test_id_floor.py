#!/usr/bin/env python3
# id_floor 가 덱(인클루드 닫힘)의 번호 바닥을 StepForge 시작 번호 인자 이름으로 내고 대응표를 대조하는지 보는 회귀 시험
"""`id_floor` — 요청 때 발행 (2026-10-16 · 사용자 결정 「요청 때 발행」).

왜 이 시험이 있나.

  번호 대역표를 두지 않기로 했다. StepForge 조각을 요청할 때 대상 덱의 최대값 위 번호를 시작 번호로 주면
  (`export_part_fragment` 의 `node_start`·`elem_start`·`pid_start`·`sid_start`), 조각이 그 번호로 쓰이고
  `cad_solid_merge_to_deck` 가 옮기지 않고 넣는다 — 대응표 번호가 곧 덱 번호다. 경계 문서의 `id_floor`(Q7 — 대응표의
  `ranges` 를 읽어 대조한다)가 이 op 이다.

신탁.
  · 바닥 = assemble 과 같은 커서(인클루드 닫힘까지)의 최대값 + 1 · pid_start 는 PID·SECID·MID 셋의 최대값 위
  · 대응표 `ranges` 의 아래끝이 바닥 이상이면 "above"(rc 0) · 아래면 "below"(rc 1) — 경계값(아래끝 = 바닥)은 above
  · `id_floor` 가 above 라고 한 조각을 넣으면 옮기지 않는다(같은 바닥을 두 op 이 같이 본다)
  · 요소 바닥은 **모든 족**이다 — 보 · 질량 · 이산 요소의 EID 까지(2026-11-07). 리더(`KFileReader`)는 그 셋을 메시에
    담지 않아 예전 바닥은 솔리드 · 셸 최대 위였다(11-07 답신이 StepForge 에 「빔 · 이산 · 질량까지 센다」고 했다)
  · 리더가 안 읽는 솔리드 · 티쉘 변형(`_ORTHO` · `_H8TOH20` · `_DOF` · `_H20` · `*ELEMENT_TSHELL_BETA`)의 EID 도 —
    키워드 접미사 `%` 의 폭 · 인클루드 닫힘까지 · 삽입이 같은 바닥으로 옮긴다(F · 2026-11-07)

usage: test_id_floor.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples", "cad_solid_merge_to_deck")
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:300]))
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def shifted_map(m, dn, de, dp):
    """대응표의 번호를 옮긴 사본 — 칸 집합은 그대로(StepForge 가 다른 시작 번호로 쓴 꼴)."""
    m = json.loads(json.dumps(m))
    for k, dlt in (("node", dn), ("elem", de), ("pid", dp)):
        if m["ranges"][k] is not None:
            m["ranges"][k] = [v + dlt for v in m["ranges"][k]]
    for p in m["parts"]:
        p["pid"] += dp
        p["node_start"] += dn
        p["elem_start"] += de
    return m


def shift_elem_ids(text, de):
    """조각의 요소 번호(첫 칸 · 8칸)만 de 만큼 옮긴다 — 저쪽이 다른 요소 시작 번호로 쓴 조각의 꼴."""
    out, sect = [], ""
    for l in text.splitlines(keepends=True):
        s = l.strip()
        if s.startswith("*"):
            sect = s.upper()
        elif sect.startswith("*ELEMENT") and s and not s.startswith("$"):
            l = "%8d" % (int(l[:8]) + de) + l[8:]
        out.append(l)
    return "".join(out)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="idf_")
    try:
        shutil.copy(os.path.join(EX, "deck.k"), d)
        shutil.copy(os.path.join(EX, "stepforge_fragment.k"), d)
        real = json.load(open(os.path.join(EX, "stepforge_fragment.json"), encoding="utf-8"))
        write(os.path.join(d, "real.json"), json.dumps(real, ensure_ascii=False, indent=2))

        print("[A 바닥 — 덱 최대값 + 1, 인자 이름 그대로]")
        write(os.path.join(d, "a.yaml"), "model: deck.k\noutput: floor_a.json\n")
        rc, out = run(binary, d, "id_floor", "a.yaml")
        fa = json.load(open(os.path.join(d, "floor_a.json"), encoding="utf-8")) if rc == 0 else {}
        check("A-1 rc 0 · 칸은 deck·basis·node_start·elem_start·pid_start·sid_start",
              rc == 0 and set(fa) == {"deck", "basis", "node_start", "elem_start", "pid_start", "sid_start"}, (rc, fa))
        check("A-2 덱 최대 12 · 2 · 2 → 13 · 3 · 3 · 세트 없음 → sid 1",
              [fa.get(k) for k in ("node_start", "elem_start", "pid_start", "sid_start")] == [13, 3, 3, 1], fa)

        print("[B 인클루드 닫힘까지 센다 — 셋 중 가장 큰 SECID·MID 위로 PID]")
        inc = ("*KEYWORD\n*NODE\n%8d%16.9e%16.9e%16.9e\n*PART\nfar part\n%10d%10d%10d\n"
               "*SECTION_SOLID\n%10d%10d\n*MAT_ELASTIC\n%10d%10s%10s%10s\n*ELEMENT_SOLID\n%8d%8d" % (
                   550000, 9e3, 9e3, 9e3, 950, 960, 970, 960, 1, 970, "7.85E-9", "210000.", "0.3", 650000, 950) +
               "%8d" * 8 % ((550000,) * 8) + "\n*SET_NODE_LIST\n%10d\n%10d\n*END\n" % (77, 550000))
        write(os.path.join(d, "far.k"), inc)
        write(os.path.join(d, "deck_b.k"), open(os.path.join(d, "deck.k"), encoding="utf-8").read().replace(
            "*END", "*INCLUDE\nfar.k\n*END"))
        write(os.path.join(d, "b.yaml"), "model: deck_b.k\noutput: floor_b.json\nfragment_map: real.json\n")
        rc, out = run(binary, d, "id_floor", "b.yaml")
        fb = json.load(open(os.path.join(d, "floor_b.json"), encoding="utf-8")) \
            if os.path.exists(os.path.join(d, "floor_b.json")) else {}
        check("B-1 인클루드의 550000 · 650000 · MID 970 · SID 77 위", [fb.get(k) for k in
              ("node_start", "elem_start", "pid_start", "sid_start")] == [550001, 650001, 971, 78], fb)
        check("B-2 그 바닥 아래에 걸친 대응표(500001…) → below · rc 1", rc == 1 and
              (fb.get("check") or {}).get("node") == "below" and "아래에 걸친다" in out, (rc, fb.get("check")))

        print("[C 대조 — 위면 above · 경계값 · 넣으면 옮기지 않는다]")
        write(os.path.join(d, "c.yaml"), "model: deck.k\noutput: floor_c.json\nfragment_map: real.json\n")
        rc, out = run(binary, d, "id_floor", "c.yaml")
        fc = json.load(open(os.path.join(d, "floor_c.json"), encoding="utf-8")) if rc == 0 else {}
        check("C-1 실물 조각(500001/600001/900)은 바닥 위 → above · rc 0 · sid unused",
              rc == 0 and fc.get("check", {}).get("node") == "above" and fc["check"].get("pid") == "above" and
              fc["check"].get("sid") == "unused", (rc, fc.get("check")))
        # 경계값 — 저쪽이 우리 바닥(13 · 3 · 3)을 그대로 시작 번호로 썼다면
        edge = shifted_map(real, 13 - real["ranges"]["node"][0], 3 - real["ranges"]["elem"][0],
                           3 - real["ranges"]["pid"][0])
        write(os.path.join(d, "edge.json"), json.dumps(edge, ensure_ascii=False, indent=2))
        write(os.path.join(d, "e.yaml"), "model: deck.k\noutput: floor_e.json\nfragment_map: edge.json\n")
        rc, out = run(binary, d, "id_floor", "e.yaml")
        check("C-2 아래끝 = 바닥(바닥으로 발행한 조각) → above · rc 0", rc == 0 and "바닥 위" in out, out[-300:])
        low = shifted_map(edge, -1, 0, 0)
        write(os.path.join(d, "low.json"), json.dumps(low, ensure_ascii=False, indent=2))
        write(os.path.join(d, "l.yaml"), "model: deck.k\noutput: floor_l.json\nfragment_map: low.json\n")
        rc, out = run(binary, d, "id_floor", "l.yaml")
        check("C-3 절점 아래끝이 바닥 - 1 → below · rc 1", rc == 1 and "아래에 걸친다" in out, out[-300:])
        write(os.path.join(d, "m.yaml"), "model: deck.k\noutput: merged\nfragment: stepforge_fragment.k\n"
              "fragment_map: real.json\n")
        rc, out = run(binary, d, "cad_solid_merge_to_deck", "m.yaml")
        check("C-4 id_floor 가 above 라 한 조각은 삽입이 옮기지 않는다(같은 바닥)", rc == 0 and "옮기지 않았다" in out,
              out[-300:])

        print("[E 바닥은 모든 요소 족을 센다 — 보 · 질량 · 이산 요소의 EID 까지(2026-11-07 · 11-07 답신이 약속했다)]")
        # 덱의 솔리드 최대 EID 는 2 — 그 위에 보(777) · 질량(888) · 이산(555)을 둔다. 리더는 이 셋을 메시에 담지 않는다
        aux = ("*ELEMENT_BEAM\n%8d%8d%8d%8d\n*ELEMENT_MASS\n%8d%8d%16s%8d\n*ELEMENT_DISCRETE\n%8d%8d%8d%8d\n*END" % (
            777, 1, 1, 2, 888, 3, "1.0", 0, 555, 1, 3, 4))
        write(os.path.join(d, "deck_aux.k"), open(os.path.join(d, "deck.k"), encoding="utf-8").read().replace("*END", aux))
        write(os.path.join(d, "ea.yaml"), "model: deck_aux.k\noutput: floor_aux.json\n")
        rc, out = run(binary, d, "id_floor", "ea.yaml")
        fx = json.load(open(os.path.join(d, "floor_aux.json"), encoding="utf-8")) if rc == 0 else {}
        check("E-1 elem_start 889 — 질량 888 위(솔리드 · 셸 최대 2 가 아니다) · 절점 바닥은 그대로 13",
              rc == 0 and fx.get("elem_start") == 889 and fx.get("node_start") == 13, (rc, fx))
        # 그 바닥 아래(요소 3…)로 쓴 대응표를 넣으면 삽입이 바닥(888) 위로 옮긴다 — id_floor 와 같은 바닥
        de = 3 - real["ranges"]["elem"][0]
        lowe = shifted_map(real, 0, de, 0)
        write(os.path.join(d, "lowe.json"), json.dumps(lowe, ensure_ascii=False, indent=2))
        write(os.path.join(d, "lowe_frag.k"),
              shift_elem_ids(open(os.path.join(d, "stepforge_fragment.k"), encoding="utf-8").read(), de))
        write(os.path.join(d, "em.yaml"), "model: deck_aux.k\noutput: merged_aux\nfragment: lowe_frag.k\nfragment_map: lowe.json\n")
        rc, out = run(binary, d, "cad_solid_merge_to_deck", "em.yaml")
        mm = json.load(open(os.path.join(d, "merged_aux_fragment_map.json"), encoding="utf-8")) if rc == 0 else {}
        check("E-2 cad_solid_merge_to_deck 이 요소를 바닥 888 위(889~)로 옮긴다", rc == 0 and
              (mm.get("ranges") or {}).get("elem", [0])[0] == 889, (rc, mm.get("ranges"), out[-300:]))

        print("[F 리더가 안 읽는 솔리드 · 티쉘 변형의 EID 도 센다 — _ORTHO · _H8TOH20 · _DOF · _H20 · *ELEMENT_TSHELL_BETA(2026-11-07)]")
        # 리더(KFileReader)는 *ELEMENT_SOLID · *ELEMENT_TSHELL 맨 이름만 메시에 담는다. 격자 밖 걸음은 「줄 수를 알면 리더가
        # 담는다」고 보아 이 변형들을 아무도 세지 않았다 — 바닥이 덱의 솔리드 최대 2 위(elem_start 3)로 나왔다.
        # 가장 큰 EID 를 **마지막** 요소에 둔다 — 카드 줄 수를 잘못 세어 둘째 Card 1 을 삼키면 그 번호를 놓친다.
        hexn = "%8d" * 8 % (1, 2, 3, 4, 5, 6, 7, 8)
        avec = "%16s%16s%16s" % ("1.0", "0.0", "0.0")
        dvec = "%16s%16s%16s" % ("0.0", "1.0", "0.0")
        n10 = "%8d" * 10 % (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
        n20 = "%8d" * 10 % (11, 12, 1, 2, 3, 4, 5, 6, 7, 8)

        def card1(eid, pid=1):
            return "%8d%8d" % (eid, pid)

        variants = [
            ("F-1", "*ELEMENT_SOLID_ORTHO", [card1(98000), hexn, avec, dvec, card1(99000), hexn, avec, dvec]),
            ("F-2", "*ELEMENT_SOLID_H8TOH20", [card1(98000), hexn, card1(99000), hexn]),
            ("F-3", "*ELEMENT_TSHELL_BETA", [card1(98000) + hexn, "%16s" % "30.0", card1(99000) + hexn, "%16s" % "30.0"]),
            ("F-4", "*ELEMENT_SOLID_DOF", [card1(98000), hexn, hexn, card1(99000), hexn, hexn]),
            ("F-5", "*ELEMENT_SOLID_H20", [card1(98000), n10, n20, card1(99000), n10, n20]),
        ]
        base = open(os.path.join(d, "deck.k"), encoding="utf-8").read()
        for label, kw, rows in variants:
            name = "deck_%s.k" % label.replace("-", "")
            write(os.path.join(d, name), base.replace("*END", kw + "\n" + "\n".join(rows) + "\n*END"))
            write(os.path.join(d, "f.yaml"), "model: %s\noutput: floor_f.json\n" % name)
            rc, out = run(binary, d, "id_floor", "f.yaml")
            ff = json.load(open(os.path.join(d, "floor_f.json"), encoding="utf-8")) if rc == 0 else {}
            check("%s %s 의 EID 99000 → elem_start 99001 · 절점 바닥 13 그대로" % (label, kw),
                  rc == 0 and ff.get("elem_start") == 99001 and ff.get("node_start") == 13, (rc, ff, out[-200:]))
        # 키워드 접미사 `%` 는 그 블록만 10칸이다 — 8칸으로 자르면 9900000 을 99000 으로 읽는다
        write(os.path.join(d, "deck_F6.k"), base.replace("*END", "*ELEMENT_SOLID_ORTHO %\n" + "\n".join(
            ["%10d%10d" % (9900000, 1), "%10d" * 8 % (1, 2, 3, 4, 5, 6, 7, 8), avec, dvec]) + "\n*END"))
        write(os.path.join(d, "f6.yaml"), "model: deck_F6.k\noutput: floor_f6.json\n")
        rc, out = run(binary, d, "id_floor", "f6.yaml")
        ff = json.load(open(os.path.join(d, "floor_f6.json"), encoding="utf-8")) if rc == 0 else {}
        check("F-6 `*ELEMENT_SOLID_ORTHO %`(10칸)의 EID 9900000 → elem_start 9900001", rc == 0 and
              ff.get("elem_start") == 9900001, (rc, ff, out[-200:]))
        # 인클루드 닫힘까지 — 기존 바닥 훑기와 같은 길(파일마다 같은 걸음)
        write(os.path.join(d, "orth.k"), "*KEYWORD\n*ELEMENT_SOLID_ORTHO\n" + "\n".join(
            [card1(99500), hexn, avec, dvec]) + "\n*END\n")
        write(os.path.join(d, "deck_F7.k"), base.replace("*END", "*INCLUDE\n" + "orth.k" + "\n*END"))
        write(os.path.join(d, "f7.yaml"), "model: deck_F7.k\noutput: floor_f7.json\n")
        rc, out = run(binary, d, "id_floor", "f7.yaml")
        ff = json.load(open(os.path.join(d, "floor_f7.json"), encoding="utf-8")) if rc == 0 else {}
        check("F-7 인클루드 안의 *ELEMENT_SOLID_ORTHO EID 99500 → elem_start 99501", rc == 0 and
              ff.get("elem_start") == 99501, (rc, ff, out[-200:]))
        # 삽입도 같은 바닥으로 옮긴다 — 요소 3… 으로 쓴 조각(E-2 의 것)을 ORTHO 덱(F-1)에 넣으면 99001~ 로
        write(os.path.join(d, "fm.yaml"), "model: deck_F1.k\noutput: merged_f1\nfragment: lowe_frag.k\n"
              "fragment_map: lowe.json\n")
        rc, out = run(binary, d, "cad_solid_merge_to_deck", "fm.yaml")
        mf = json.load(open(os.path.join(d, "merged_f1_fragment_map.json"), encoding="utf-8")) if rc == 0 else {}
        check("F-8 cad_solid_merge_to_deck 이 ORTHO 덱에서 요소를 바닥 99000 위(99001~)로 옮긴다", rc == 0 and
              (mf.get("ranges") or {}).get("elem", [0])[0] == 99001, (rc, mf.get("ranges"), out[-300:]))

        print("[D 잘못된 YAML]")
        write(os.path.join(d, "x.yaml"), "model: deck.k\noutput: x.json\nfragment: stepforge_fragment.k\n")
        rc, out = run(binary, d, "id_floor", "x.yaml")
        check("D-1 모르는 키(fragment)는 거절", rc == 1 and "모르는 키" in out, out[-200:])
        write(os.path.join(d, "y.yaml"), "model: deck.k\n")
        rc, out = run(binary, d, "id_floor", "y.yaml")
        check("D-2 output 이 없으면 거절", rc == 1, out[-200:])
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
