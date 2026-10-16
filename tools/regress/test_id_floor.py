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
