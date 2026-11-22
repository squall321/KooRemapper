#!/usr/bin/env python3
# battery batch.phase_modes 판의 고정구와 phase 1 → 2 사슬의 번호를 재는 회귀 시험
"""battery phase_modes 의 고정구 (2026-11-22 · 3차 6판 · 사용자 결정).

왜 이 시험이 있나.

  phase_modes 가 판의 mode 만 바꾸고 고정구(압입자 · 바닥판 · 탭 · PCM)는 설정을 읽을 때 기본 mode 로 정한 값을 물려받았다.
  - 권취 phase_modes [swell, dent] 의 phase 1(swell)이 옆 압입자 · 바닥판을 경계 없이 실었다(떠다니는 고정구 · rc 0).
  - 기본 mode 가 swell 이면 phase_modes 의 dent 판도 고정구 없이 썼다 — 압입자 · 처방 운동 없는 dent 덱(rc 0).
  사용자 결정 — phase_modes 의 swell · bare 판은 적층 · 권취 모두 압입자 · 바닥판을 짓지 않고 탭 · PCM 은 둔다(사슬의 셀 번호
  그대로). 단독 mode: swell · bare 는 지금처럼 다 뺀다. 권취는 압입자 · 바닥판을 탭 · PCM 앞에 지어, 압입자를 빼면 phase 1 의
  탭 · PCM 번호가 phase 2 의 압입자 번호와 겹쳤다 — 이제 탭 · PCM 을 먼저 짓는다(적층의 차례와 같다).

무엇을 보나.
  적층 · 권취 × phase_modes [swell, dent] · [bare, dent](use_dynain: true · phases [1, 2]) · 권취 나선 판(flat: false) [swell, dent]
    phase 1 — 압입자 · 바닥판 PART 없음 · 탭 · PCM PART 있음 · `info --strict` rc 0
    ★사슬 — phase 1 의 절점 번호가 phase 2 에 모두 같은 자리로 · 요소 번호가 모두 같은 내용으로 있다
    phase 2(dent) — 압입자 · 바닥판 · 탭 · PCM PART 있음 · 처방 운동 있음(dynain 파일이 없어 strict 는 아래 판에서)
  ★기본 mode swell + phase_modes [swell, dent] → phase 2 에 압입자 · 처방 운동이 있다 · 두 판 `info --strict` rc 0
  no_fixture: true + phase_modes [swell, dent] → 두 판 모두 고정구 없음(사용자가 적은 값은 지킨다) · no_impactor · no_pcm 도 그 값대로
  단독 mode: swell → 고정구 PART 없음(그대로)

usage: test_battery_phase_modes.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS, OKS = [], []
FIX = {"stacked": {"imp": {100, 101}, "tabpcm": {20, 21, 30, 31}},
       "wound": {"imp": {100, 101}, "tabpcm": {2020, 2021, 2030}}}   # 권취 PCM 은 한 PART(2030)


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def read_deck(path):
    """요소가 있는 PART 번호 · 키워드 집합 · 절점 {번호: 좌표} · 요소 {번호: (키워드, 칸들)}.

    PART 카드가 아니라 요소의 PART 를 센다 — 적층 단독 swell 은 요소 없는 탭 PART 카드를 쓴다(예전부터).
    """
    kws, nodes, elems = set(), {}, {}
    kw = None
    for l in open(path, encoding="utf-8", errors="replace"):
        if l.startswith("*"):
            kw = l.split()[0].upper()
            kws.add(kw)
            continue
        if l.startswith("$") or not l.strip():
            continue
        if kw == "*NODE":
            nodes[int(l[0:8])] = (float(l[8:24]), float(l[24:40]), float(l[40:56]))
        elif kw and kw.startswith("*ELEMENT_"):
            elems[int(l[0:8])] = (kw, l[8:].split())
    return {int(v[1][0]) for v in elems.values()}, kws, nodes, elems


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="bpm_")

    def gen(tag, text):
        d = os.path.join(root, tag)
        os.makedirs(d)
        with open(os.path.join(d, "b.yaml"), "w", encoding="utf-8") as f:
            f.write(text)
        p = subprocess.run([binary, "battery", "b.yaml"], cwd=d, capture_output=True, text=True, timeout=900,
                           encoding="utf-8", errors="replace")
        ks = sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".k"))
        return p.returncode, p.stdout + p.stderr, ks

    def strict(k):
        q = subprocess.run([binary, "info", k, "--strict"], capture_output=True, text=True, timeout=900,
                           encoding="utf-8", errors="replace")
        qo = q.stdout + q.stderr
        return q.returncode == 0 and "참조 무결성 OK" in qo, [l.strip() for l in qo.splitlines() if "정의되지 않" in l][:3]

    try:
        for mt in ("stacked", "wound"):
            imp, tp = FIX[mt]["imp"], FIX[mt]["tabpcm"]
            # 권취는 평평한 판(기본)과 나선 판(wound.flat: false)이 고정구를 따로 짓는다 — 둘 다 잰다
            for first, extra in (("swell", ""), ("bare", "")) + ((("swell", "wound:\n  flat: false\n"),) if mt == "wound" else ()):
                tag = first + (" · 나선" if extra else "")
                rc, out, ks = gen("%s_%s%s" % (mt, first, "_spiral" if extra else ""),
                                  "output: bt\nmodel_type: %s\ntier: -1\nmode: dent\nuse_dynain: true\n%sbatch:\n  phases: [1, 2]\n"
                                  "  phase_modes: [%s, dent]\n" % (mt, extra, first))
                if not check("%s · phase_modes [%s, dent] → rc 0 · 덱 둘" % (mt, tag), rc == 0 and len(ks) == 2,
                             (rc, ks, out[-300:])):
                    continue
                p1, p2 = read_deck(ks[0]), read_deck(ks[1])
                check("★%s · [%s, dent] phase 1 — 압입자 · 바닥판 PART 없음 · 탭 · PCM 있음(예전 권취는 압입자 · 바닥판을 실었다)"
                      % (mt, tag), not (p1[0] & imp) and tp <= p1[0], sorted(p1[0]))
                ok, bad = strict(ks[0])
                check("%s · [%s, dent] phase 1 → info --strict rc 0" % (mt, tag), ok, bad)
                moved = [n for n, c in p1[2].items() if n not in p2[2] or max(abs(a - b) for a, b in zip(c, p2[2][n])) > 1e-6]
                changed = [e for e, v in p1[3].items() if p2[3].get(e) != v]
                check("★%s · [%s, dent] 사슬 — phase 1 절점 %d · 요소 %d 이 phase 2 에 같은 번호 · 자리 · 내용으로 있다(예전 권취는 "
                      "탭 · PCM 이 압입자 번호와 겹쳤다)" % (mt, tag, len(p1[2]), len(p1[3])), not moved and not changed,
                      ("moved", len(moved), moved[:5], "changed", len(changed), changed[:5]))
                check("%s · [%s, dent] phase 2 — 압입자 · 바닥판 · 탭 · PCM PART · 처방 운동 있음" % (mt, tag),
                      imp <= p2[0] and tp <= p2[0] and "*BOUNDARY_PRESCRIBED_MOTION_SET" in p2[1], (sorted(p2[0]), sorted(p2[1])[:8]))

            rc, out, ks = gen("%s_baseswell" % mt, "output: bt\nmodel_type: %s\ntier: -1\nmode: swell\nbatch:\n  phases: [1, 2]\n"
                              "  phase_modes: [swell, dent]\n" % mt)
            if check("%s · mode swell + phase_modes [swell, dent] → rc 0 · 덱 둘" % mt, rc == 0 and len(ks) == 2, (rc, out[-300:])):
                p2 = read_deck(ks[1])
                check("★%s · 기본 mode swell 의 phase_modes dent 판 — 압입자 · 바닥판 · 처방 운동 있음(예전엔 고정구 없는 dent 덱)" % mt,
                      imp <= p2[0] and "*BOUNDARY_PRESCRIBED_MOTION_SET" in p2[1], (sorted(p2[0]), sorted(p2[1])[:8]))
                for k in ks:
                    ok, bad = strict(k)
                    check("%s · 기본 mode swell 의 %s → info --strict rc 0" % (mt, os.path.basename(k)), ok, bad)

            rc, out, ks = gen("%s_nofix" % mt, "output: bt\nmodel_type: %s\ntier: -1\nmode: dent\nno_fixture: true\nbatch:\n"
                              "  phases: [1, 2]\n  phase_modes: [swell, dent]\n" % mt)
            if check("%s · no_fixture + phase_modes [swell, dent] → rc 0 · 덱 둘" % mt, rc == 0 and len(ks) == 2, (rc, out[-300:])):
                both = read_deck(ks[0])[0] | read_deck(ks[1])[0]
                check("%s · no_fixture + phase_modes → 두 판 모두 압입자 · 바닥판 · 탭 · PCM PART 없음(사용자가 적은 값)" % mt,
                      not (both & (imp | tp)), sorted(both))

            # 사용자가 적은 no_impactor · no_pcm 은 phase_modes 판에서도 지킨다(다시 셈은 mode 에서 더할 뿐)
            for key, gone, kept in (("no_impactor", imp, tp), ("no_pcm", tp, imp)):
                rc, out, ks = gen("%s_%s" % (mt, key), "output: bt\nmodel_type: %s\ntier: -1\nmode: dent\n%s: true\nbatch:\n"
                                  "  phases: [1, 2]\n  phase_modes: [swell, dent]\n" % (mt, key))
                if check("%s · %s + phase_modes [swell, dent] → rc 0 · 덱 둘" % (mt, key), rc == 0 and len(ks) == 2, (rc, out[-300:])):
                    p1, p2 = read_deck(ks[0])[0], read_deck(ks[1])[0]
                    want_p2 = kept <= p2 and not (p2 & gone)
                    want_p1 = not (p1 & gone) and (key == "no_pcm" or tp <= p1)
                    check("%s · %s + phase_modes → 두 판 모두 %s 없음(사용자가 적은 값) · dent 판의 다른 고정구는 있다"
                          % (mt, key, "압입자 · 바닥판" if key == "no_impactor" else "탭 · PCM"), want_p1 and want_p2,
                          (sorted(p1 & (imp | tp)), sorted(p2 & (imp | tp))))

            rc, out, ks = gen("%s_single" % mt, "output: bt\nmodel_type: %s\ntier: -1\nmode: swell\n" % mt)
            if check("%s · 단독 mode: swell → rc 0 · 덱 하나" % mt, rc == 0 and len(ks) == 1, (rc, out[-300:])):
                parts = read_deck(ks[0])[0]
                check("%s · 단독 mode: swell → 고정구 PART 없음(그대로)" % mt, not (parts & (imp | tp)), sorted(parts))
    finally:
        shutil.rmtree(root, ignore_errors=True)
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
