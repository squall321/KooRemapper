#!/usr/bin/env python3
# stackdiagram 이 층을 갈라 그리는지 — 포개진 AABB 를 층처럼 그리면 가장 나쁜 거짓이다
"""`stackdiagram` 의 계약 (2026-10-04).

왜 이 시험이 있나.

  이 op 은 파트별 **축 범위**(사실상 AABB)만 쓰는 **모식도**다. `section` 과 달리 평면을 고를
  필요가 없고 중립축을 함께 긋지만, 그 대가로 **AABB 로 갈리지 않는 적층에서는 쓸 수 없다.**
  포개진 범위를 층처럼 쌓아 그리면 층 순서가 거짓이 되고, 그림은 그럴듯해 보인다.

  그래서 이 시험이 보는 것은 "그려졌나" 가 아니라 **"거짓을 거절하나"** 다.

    ① 평평한 적층 → 그린다. 중립축·기하중심면·굽힘강성이 `neutralaxis` 와 **같은 값**이어야 한다.
    ② 감긴 적층(세 파트의 범위가 **같다**) → **거절**하고 `section` 을 쓰라고 말한다.
    ③ 적층 전체를 감싸는 파트가 섞이면 → 그것을 **갈라내고** 나머지를 층으로 그린다.
       ⚠ 분수 문턱("전체의 90% 이상")으로 가르면 안 된다 — 실측으로 배터리 덱의 케이스가
       88.4% 라 빗나갔고 그 분모는 셸 띠가 삐져나와 늘어난 값이었다. **품는가**가 기준이다.
    ④ `*MAT` 이 없으면(포함 파일에 있는 실제 과제가 그렇다) 층은 그리고 **중립축만 생략**한다.
    ⑤ 바닥 처리한 층은 두께가 과장되므로 **그렇다고 적는다.**

usage: test_stackdiagram.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

FAILS = []


def check(name, cond, detail=""):
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:300]) if detail else ""))


def kv(out, key):
    for line in out.splitlines():
        if line.startswith(key + ":"):
            return line[len(key) + 1:].strip()
    return None


def run(binary, cwd, cfg, op="stackdiagram"):
    p = subprocess.run([binary, op, cfg], capture_output=True, text=True, timeout=600, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def write_cfg(path, **kw):
    with open(path, "w", newline="\n") as f:
        for k, v in kw.items():
            f.write("%s: %s\n" % (k, v))


def stack_deck(path, layers, with_mat=True, enclose=None, same_range=False):
    """layers = [(두께, E)]. enclose 를 주면 적층 전체를 감싸는 파트를 하나 더 넣는다.
    same_range=True 면 모든 파트가 **같은 범위**를 갖는다(감긴 적층 흉내)."""
    LX, LY = 10.0, 4.0
    zs = [0.0]
    for t, E in layers:
        zs.append(zs[-1] + t)
    total = zs[-1]
    nid, nodes, elems, idx = 1, [], [], {}

    def block(z0, z1, pid):
        nonlocal nid
        loc = {}
        for k, z in ((0, z0), (1, z1)):
            for j in (0, 1):
                for i in (0, 1):
                    nodes.append((nid, i * LX, j * LY, z))
                    loc[(i, j, k)] = nid
                    nid += 1
        elems.append((pid, [loc[(0,0,0)], loc[(1,0,0)], loc[(1,1,0)], loc[(0,1,0)],
                            loc[(0,0,1)], loc[(1,0,1)], loc[(1,1,1)], loc[(0,1,1)]]))

    pids = []
    for k, (t, E) in enumerate(layers, start=1):
        if same_range:
            block(0.0, total, k)
        else:
            block(zs[k - 1], zs[k], k)
        pids.append((k, E))
    if enclose is not None:
        block(0.0, total, 99)
        pids.append((99, enclose))

    L = ["*KEYWORD", "*NODE"]
    for n, x, y, z in nodes:
        L.append("%8d%16.9f%16.9f%16.9f" % (n, x, y, z))
    L.append("*ELEMENT_SOLID")
    for e, (pid, c) in enumerate(elems, start=1):
        L.append("%8d%8d" % (e, pid) + "".join("%8d" % v for v in c))
    for pid, E in pids:
        L += ["*PART", "layer%d" % pid, "%10d%10d%10d" % (pid, pid, pid),
              "*SECTION_SOLID", "%10d%10d" % (pid, 1)]
        if with_mat:
            L += ["*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (pid, 7.85e-9, E, 0.3)]
    L.append("*END")
    open(path, "w", newline="\n").write("\n".join(L) + "\n")


def main():
    if len(sys.argv) < 2:
        print("usage: test_stackdiagram.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found")
        return 2

    d = tempfile.mkdtemp(prefix="sdia_")
    LAYERS = [(0.2, 1000.0), (0.3, 70000.0), (0.1, 3000.0)]
    try:
        # ── A: 평평한 적층 — 그린다. 숫자는 neutralaxis 와 **같아야** 한다 ──
        stack_deck(os.path.join(d, "flat.k"), LAYERS)
        write_cfg(os.path.join(d, "a.yaml"), model="flat.k", output="a", axis="z")
        rc, out = run(binary, d, "a.yaml")
        check("A-1 rc=0", rc == 0, out[-300:])
        check("A-2 층 3개", (kv(out, "Layers drawn") or "").startswith("3"),
              kv(out, "Layers drawn"))
        check("A-3 겹침 0", kv(out, "Overlapping (solid-solid)") == "0",
              kv(out, "Overlapping (solid-solid)"))
        check("A-4 중립축 = 0.350465116279", kv(out, "Neutral axis") == "0.350465116279",
              kv(out, "Neutral axis"))
        # ★`neutralaxis` 와 같은 값이어야 한다 — 두 op 이 같은 계산을 쓴다
        write_cfg(os.path.join(d, "na.yaml"))
        p = subprocess.run([binary, "neutralaxis", "flat.k"], capture_output=True, text=True,
                           timeout=300, cwd=d)
        naout = p.stdout + p.stderr
        check("A-5 ★`neutralaxis` 와 **같은** 중립축·굽힘강성 (한 계산을 쓴다)",
              kv(naout, "Neutral axis") == kv(out, "Neutral axis")
              and (kv(naout, "Bending stiffness D") or "").split()[0]
                  == (kv(out, "Bending stiffness D") or "").split()[0],
              (kv(naout, "Neutral axis"), kv(out, "Neutral axis")))
        svg = open(os.path.join(d, "a_stackdiagram.svg"), encoding="utf-8").read()
        for need in ("중립축", "기하 중심면", "모식도", "단위 없음", "총두께"):
            check("A-6 그림 안에 '%s'" % need, need in svg)
        check("A-7 층 바를 그렸다", svg.count("<rect") >= 4, svg.count("<rect"))
        import xml.etree.ElementTree as ET
        try:
            ET.fromstring(svg.encode("utf-8")); xok, why = True, ""
        except Exception as e:
            xok, why = False, str(e)
        check("A-8 SVG 가 XML 로 파싱된다", xok, why)

        # ── B: ★감긴 적층(범위가 같다) — **거절**해야 한다 ──
        stack_deck(os.path.join(d, "wound.k"), LAYERS, same_range=True)
        write_cfg(os.path.join(d, "b.yaml"), model="wound.k", output="b", axis="z")
        rc, out = run(binary, d, "b.yaml")
        check("B-1 ★포개진 적층은 rc=1", rc == 1, out[-300:])
        check("B-2 솔리드끼리 겹친다고 말한다", "솔리드끼리" in out, out[-400:])
        check("B-3 `section` 을 쓰라고 안내한다", "section" in out, out[-400:])
        check("B-4 그림을 쓰지 않는다",
              not os.path.exists(os.path.join(d, "b_stackdiagram.svg")))
        # force 로는 그릴 수 있고, 믿지 말라고 말한다
        write_cfg(os.path.join(d, "bf.yaml"), model="wound.k", output="bf", axis="z", force="true")
        rc, outf = run(binary, d, "bf.yaml")
        check("B-5 force: true 면 그리고 **믿지 말라고** 경고한다",
              rc == 0 and "믿지 말라" in outf, outf[-300:])

        # ── C: ★감싸는 파트를 갈라낸다 (분수 문턱이 아니라 '품는가') ──
        stack_deck(os.path.join(d, "encl.k"), LAYERS, enclose=5000.0)
        write_cfg(os.path.join(d, "c.yaml"), model="encl.k", output="c", axis="z")
        rc, out = run(binary, d, "c.yaml")
        check("C-1 rc=0 (감싸는 파트가 있어도 그린다)", rc == 0, out[-400:])
        check("C-2 감싸는 파트를 1개 갈라냈다 (PID 99)",
              (kv(out, "Enclosing parts") or "").startswith("1") and "99" in (kv(out, "Enclosing parts") or ""),
              kv(out, "Enclosing parts"))
        check("C-3 남은 층은 3개", (kv(out, "Layers drawn") or "").startswith("3"),
              kv(out, "Layers drawn"))
        check("C-4 갈라낸 뒤 솔리드 겹침 0", kv(out, "Overlapping (solid-solid)") == "0",
              kv(out, "Overlapping (solid-solid)"))
        sc = open(os.path.join(d, "c_stackdiagram.svg"), encoding="utf-8").read()
        check("C-5 그림에 '감싸는 파트' 를 적는다", "감싸는 파트" in sc)

        # ── D: ★`*MAT` 이 없으면 층은 그리고 중립축만 생략 ──
        stack_deck(os.path.join(d, "nomat.k"), LAYERS, with_mat=False)
        write_cfg(os.path.join(d, "e.yaml"), model="nomat.k", output="e", axis="z")
        rc, out = run(binary, d, "e.yaml")
        check("D-1 rc=0 (E 가 없어도 층 구조는 그린다)", rc == 0, out[-400:])
        check("D-2 층 3개를 '두께만' 으로 센다",
              "두께만 3" in (kv(out, "Layers drawn") or ""), kv(out, "Layers drawn"))
        check("D-3 중립축을 긋지 않는다고 **말한다**", "중립축을 긋지 않는다" in out, out[-400:])
        check("D-4 중립축 값을 내지 않는다", kv(out, "Neutral axis") is None,
              kv(out, "Neutral axis"))
        se = open(os.path.join(d, "e_stackdiagram.svg"), encoding="utf-8").read()
        check("D-5 그림에도 그 사실을 적는다", "중립축을 긋지 않았다" in se,
              [l for l in se.splitlines() if "중립축" in l][:1])
        check("D-6 그래도 층 바는 그렸다", se.count("<rect") >= 4, se.count("<rect"))

        # ── E: ★바닥 처리를 적는다 (얇은 층이 과장된다) ──
        thin = [(1.0, 1000.0), (0.0005, 70000.0), (1.0, 3000.0)]
        stack_deck(os.path.join(d, "thin.k"), thin)
        write_cfg(os.path.join(d, "f.yaml"), model="thin.k", output="f", axis="z",
                  height=300, min_bar_px=3)
        rc, out = run(binary, d, "f.yaml")
        check("E-1 rc=0", rc == 0, out[-300:])
        check("E-2 바닥 처리한 층을 센다", (kv(out, "Floored layers") or "0") != "0",
              kv(out, "Floored layers"))
        check("E-3 그 사실을 경고한다", "바닥 처리" in out, out[-300:])
        sf = open(os.path.join(d, "f_stackdiagram.svg"), encoding="utf-8").read()
        check("E-4 ★그림에 '두께는 그림이 아니라 옆 숫자가 참' 이라고 적는다",
              "바닥 처리" in sf and "숫자" in sf,
              [l for l in sf.splitlines() if "바닥" in l][:1])

        # ── F: 잘못된 입력 ──
        for name, args in (("F-1 model 누락은 rc=1", dict(output="x")),
                           ("F-2 output 누락은 rc=1", dict(model="flat.k")),
                           ("F-3 모르는 axis 는 rc=1", dict(model="flat.k", output="x", axis="q")),
                           ("F-4 캔버스가 작으면 rc=1", dict(model="flat.k", output="x",
                                                        width=300, height=300)),
                           ("F-5 enclosure_min_inside<1 은 rc=1",
                            dict(model="flat.k", output="x", enclosure_min_inside=0))):
            write_cfg(os.path.join(d, "g.yaml"), **args)
            rc, outg = run(binary, d, "g.yaml")
            check(name, rc == 1, outg[-200:])
        open(os.path.join(d, "noel.k"), "w", newline="\n").write("*KEYWORD\n*INCLUDE\nm.k\n*END\n")
        write_cfg(os.path.join(d, "h.yaml"), model="noel.k", output="h")
        rc, outh = run(binary, d, "h.yaml")
        check("F-6 기하가 없으면 rc=1 · 빈 그림을 내지 않는다",
              rc == 1 and "빈 그림" in outh, outh[-200:])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    if FAILS:
        print("--- 실패 %d건 ---" % len(FAILS))
        for f in FAILS:
            print("  " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
