#!/usr/bin/env python3
# 보 옵션 카드 절점의 칸 읽기 · cleanup-nodes 되읽기의 지킨 절점 · battery 탭이 셀 끝을 넘을 때의 경고를 보는 회귀 시험
"""옵션 카드 절점 · 지킨 절점 되읽기 · 탭 경고 (2026-11-22 · 3차 5판 L-14).

왜 이 시험이 있나.

  - 보 옵션 카드(`_WARPAGE` 의 SN1 · SN2 · `_ELBOW` 의 MN)의 절점을 칸이 어긋난 줄에서 공백 토큰 차례로만 읽었다. Card 1 은 칸
    읽기(LS-DYNA 가 읽는 칸)와 다른 읽기를 갈라 둘 다 지키는데 옵션 카드만 토큰 차례였다 — 칸 0 에 「1 2」 가 끼면 칸 1 의 SN2 202 를
    놓쳐 extract-parts 가 그 스칼라 절점을 싣지 않았다. 이제 Card 1 과 같다 — 칸 읽기는 싣고, 다른 읽기만 말하는 절점은 덱에 있으면
    싣는다. 칸으로 못 읽은 줄은 cleanup-nodes 가 [WARN] 으로 댄다.
  - cleanup-nodes 의 되읽기(verify)가 요소 · 세트 멤버만 보았다 — keep 키워드 · 모르는 키워드 · 못 읽는 세트 변종 · 못 읽은 보 족 줄로
    지킨 절점이 산출에서 없어져도 몰랐다. 이제 그 넷도 잰다(보고 `verify.undefined_kept`).
  - 적층 battery 탭이 셀 끝(0 · cell_width)을 넘으면 셀 안 격자 열로 좁혀 지으면서 말이 없었다. 이제 [WARN] 이 지은 범위를 댄다.

usage: test_option_card_readings.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-96s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def nodes_of(path):
    """*NODE · *NODE_SCALAR(_VALUE) 의 번호."""
    out, kw = set(), None
    for l in open(path, encoding="utf-8", errors="replace").read().splitlines():
        if l.startswith("*"):
            kw = l.split()[0].upper()
            continue
        if l.startswith("$") or not l.strip():
            continue
        if kw in ("*NODE", "*NODE_SCALAR", "*NODE_SCALAR_VALUE"):
            out.add(int(l[0:8]))
    return out


TAIL = ["*PART", "beam", "%10d%10d%10d" % (9, 9, 9), "*SECTION_BEAM", "%10d%10d" % (9, 1),
        "*MAT_ELASTIC", "%10d%10s%10s%10s" % (9, "7.85E-9", "210000.", "0.3"), "*END"]


def node_lines(ids):
    return ["*NODE"] + ["%8d%16.6f%16.6f%16.6f" % (n, float(n), 0.0, 0.0) for n in ids]


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="ocr_")
    try:
        print("[extract-parts — _WARPAGE 옵션 카드의 칸이 깨진 줄]")
        for tag, opt, what in (("w1", "%10s%10d" % ("1 2", 202), "칸 1 의 SN2 202(칸 읽기)"),
                               ("w2", "%10s" % "1 2 3  202", "칸 0 에 낀 202(다른 읽기 — 덱에 있다)")):
            L = ["*KEYWORD"] + node_lines((101, 102, 103))
            L += ["*NODE_SCALAR", "%8d%8d" % (201, 1), "%8d%8d" % (202, 1)]
            L += ["*ELEMENT_BEAM_WARPAGE", "%8d%8d%8d%8d%8d" % (21, 9, 101, 102, 103), opt] + TAIL
            write(os.path.join(d, tag + ".k"), "\n".join(L) + "\n")
            write(os.path.join(d, tag + ".yaml"), "model: %s.k\noutput: %s_out.k\nparts: [9]\n" % (tag, tag))
            rc, out = run(binary, d, "extract-parts", tag + ".yaml")
            o = os.path.join(d, tag + "_out.k")
            got = nodes_of(o) if os.path.exists(o) else set()
            check("★extract-parts %s → rc 0 · %s 를 싣고 없는 1 · 2 · 3 은 싣지 않는다(예전엔 토큰 차례 「1」 「2」 만 읽었다)"
                  % (tag, what), rc == 0 and 202 in got and {101, 102, 103} <= got and not ({1, 2, 3} & got),
                  (rc, sorted(got), out[-300:]))

        print("[cleanup-nodes — _ELBOW 옵션 카드의 MN 칸을 칸으로 못 읽는 줄]")
        L = ["*KEYWORD"] + node_lines((101, 102, 103, 104, 105))
        L += ["*ELEMENT_BEAM_ELBOW", "%8d%8d%8d%8d%8d" % (21, 9, 101, 102, 103), "%-10s" % "1 2 3  104"] + TAIL
        write(os.path.join(d, "e.k"), "\n".join(L) + "\n")
        write(os.path.join(d, "e.yaml"), "model: e.k\noutput: e_out.k\nmode: safe\nreport: e.json\n")
        rc, out = run(binary, d, "cleanup-nodes", "e.yaml")
        got = nodes_of(os.path.join(d, "e_out.k")) if os.path.exists(os.path.join(d, "e_out.k")) else set()
        check("★cleanup-nodes → rc 0 · MN 칸에 낀 104 를 지키고 고아 105 만 지운다(예전엔 토큰 차례 「1」 만 읽어 104 를 지웠다)",
              rc == 0 and 104 in got and 105 not in got,
              (rc, sorted(got), out[-300:]))
        warned = [l for l in out.splitlines() if "e.k:" in l and "*ELEMENT_BEAM_ELBOW" in l and "칸으로 읽지 못했다" in l]
        check("★cleanup-nodes → 칸으로 못 읽은 MN 줄을 [WARN] 으로 댄다(예전엔 토큰으로 읽고 말이 없었다)", bool(warned), out[-400:])

        print("[cleanup-nodes verify — 모르는 키워드가 지킨 절점]")
        L = ["*KEYWORD"] + node_lines((101, 102, 103, 106, 107))
        L += ["*ELEMENT_BEAM", "%8d%8d%8d%8d%8d" % (21, 9, 101, 102, 103)]
        L += ["*KR_TEST_UNKNOWN_CARD", "%10d" % 106] + TAIL
        write(os.path.join(d, "u.k"), "\n".join(L) + "\n")
        write(os.path.join(d, "u.yaml"), "model: u.k\noutput: u_out.k\nmode: safe\nreport: u.json\n")
        rc, out = run(binary, d, "cleanup-nodes", "u.yaml")
        try:
            rep = json.load(open(os.path.join(d, "u.json"), encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            rep = {"_err": str(e)}
        got = nodes_of(os.path.join(d, "u_out.k")) if os.path.exists(os.path.join(d, "u_out.k")) else set()
        check("cleanup-nodes → rc 0 · 모르는 키워드의 106 을 지키고 107 을 지운다", rc == 0 and 106 in got and 107 not in got,
              (rc, sorted(got), out[-300:]))
        v = rep.get("verify") or {}
        check("★verify 보고에 undefined_kept 0 · 성공 줄이 「그 밖에 지킨 절점」 까지 쟀다고 말한다(예전엔 요소 · 세트만)",
              v.get("undefined_kept") == 0 and "그 밖에 지킨 절점 전수" in out, (v, out[-300:]))

        print("[battery — 탭이 셀 끝을 넘는다]")
        for tag, c, warn in (("in", 52.5, False), ("edge", 69, True)):
            dd = os.path.join(d, "bt_" + tag)
            os.makedirs(dd)
            write(os.path.join(dd, "b.yaml"), "output: bt\nmodel_type: stacked\ntier: -1\nmode: dent\ntabs:\n  pos_x_center: 30\n"
                                              "  neg_x_center: %s\n" % c)
            rc, out = run(binary, dd, "battery", "b.yaml")
            w = [l for l in out.splitlines() if "[WARN]" in l and "탭" in l and "좁혀" in l]
            if warn:
                check("★neg_x_center 69(x 64~74 · 셀 0~66.4) → rc 0 · [WARN] 한 번 · 음극 · 지은 범위 x 61.29~66.40",
                      rc == 0 and len(w) == 1 and "음극" in w[0] and "61.29~66.40" in w[0], (rc, w, out[-300:]))
            else:
                check("대조 — neg_x_center 52.5(셀 안) → rc 0 · 탭 경고 없음", rc == 0 and not w, (rc, w))
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
