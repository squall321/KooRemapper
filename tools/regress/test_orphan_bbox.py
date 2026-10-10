#!/usr/bin/env python3
# 고아 절점이 bbox 를 부풀린 것을 info·modelmeta 가 말하는지 — 말하지 않으면 낙하판이 기기 밖에 생긴다
"""두 bbox 기준을 말하는 계약 (2026-10-10).

왜 이 시험이 있나.

  현장 보고(CAE그룹 요청서 v1.0) — Q8 Close 덱에서 **기기 두께가 14.55 mm 인데 bbox 가
  67.50 mm** 로 나와 낙하판이 기기에서 **53 mm 밖**에 생겼다. 충돌이 아예 없으니 전각도 낙하가
  통째로 무효다. 고아 절점(요소가 안 쓰는 절점)이 118,568개였다.

  ★그런데 그 67.50 은 **이 도구가 낸 값이 아니다.** `Mesh::calculateBoundingBox()` 는 고아를
  **이미 뺀다**(그래야 `map`·`shellmap` 의 파라메트릭 비율이 안 틀어진다 — Mesh.h 주석).
  하류가 `*NODE` 에서 직접 뽑은 값이었다. 즉 **이 도구는 함정을 피하는데 그 사실을 말하지
  않아서** 자기 bbox 를 계산하는 하류가 그대로 빠졌다.

  그래서 이 시험이 보는 것은 "bbox 가 맞나" 가 아니라 **"기준을 말하나"** 다.

    · `info` 가 **기준을 적는다**(항상).
    · 고아가 있으면 **두 bbox 와 고아 수**를 보이고 축을 지목해 경고한다.
    · 고아가 없으면 그 블록을 **내지 않는다** — 정상 출력에 네 줄을 더하면 비정상 신호가 묻힌다.
    · ★`Min bound`·`Max bound`·`Size` **라벨이 그대로**다.
      `platform/backend/app/runner/kfile_inspect.py:22-24` 와 `test_packed_node.py:51` 이
      정규식으로 파싱한다 — 이름을 바꾸면 플랫폼의 bbox 가 조용히 사라진다.
    · `modelmeta` 가 **두 기준을 다** 내고 어느 쪽인지 적는다. 한 JSON 안에서
      `model.bbox_*`(전체)과 `parts[].bbox_*`(요소)이 같은 이름으로 다른 기준이었다.

usage: test_orphan_bbox.py <KooRemapper 바이너리>
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

FAILS = []


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:300]) if detail else ""))


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], capture_output=True, text=True, timeout=600, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    with open(path, "w", newline="\n") as f:
        f.write(text)


def deck(path, orphans=()):
    """단위 육면체 하나 + `orphans` 에 준 x 좌표마다 고아 절점 하나.

    고아는 **전 절점 세트**에만 들어간다 — 요청서가 "전 절점 세트에만 있음 → 삭제 가능
    118,529개" 로 분류한 그 모양이다."""
    L = ["*KEYWORD", "*NODE"]
    nid = 1
    idx = {}
    for k in (0, 1):
        for j in (0, 1):
            for i in (0, 1):
                idx[(i, j, k)] = nid
                L.append("%8d%16.9f%16.9f%16.9f" % (nid, i * 10.0, j * 5.0, k * 2.0))
                nid += 1
    for ox in orphans:
        L.append("%8d%16.9f%16.9f%16.9f" % (nid, float(ox), 0.0, 0.0))
        nid += 1
    c = [idx[(0, 0, 0)], idx[(1, 0, 0)], idx[(1, 1, 0)], idx[(0, 1, 0)],
         idx[(0, 0, 1)], idx[(1, 0, 1)], idx[(1, 1, 1)], idx[(0, 1, 1)]]
    L += ["*ELEMENT_SOLID", "%8d%8d" % (1, 1) + "".join("%8d" % v for v in c)]
    if orphans:
        L += ["*SET_NODE_LIST", "%10d" % 4,
              "".join("%10d" % n for n in range(1, nid))]
    L += ["*PART", "body", "%10d%10d%10d" % (1, 1, 1),
          "*SECTION_SOLID", "%10d%10d" % (1, 1),
          "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
    write(path, "\n".join(L) + "\n")


def kv(out, key):
    for line in out.splitlines():
        s = line.strip()
        if s.startswith(key + ":"):
            return s[len(key) + 1:].strip()
    return None


def main():
    if len(sys.argv) < 2:
        print("usage: test_orphan_bbox.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found")
        return 2

    d = tempfile.mkdtemp(prefix="obox_")
    try:
        # ── A: 고아가 있는 덱 — Q8 상황 (요소 x 0~10, 고아 x=-40 과 28) ──
        deck(os.path.join(d, "orph.k"), orphans=(-40.0, 28.0))
        rc, out = run(binary, d, "info", "orph.k")
        check("A-1 info rc=0", rc == 0, out[-250:])
        check("A-2 절점 10개를 다 읽었다 (고아를 버리지 않는다)", kv(out, "Nodes") == "10",
              kv(out, "Nodes"))
        check("A-3 ★`Min bound` 가 **요소 기준**이다 (고아를 안 쓴다)",
              kv(out, "Min bound") == "(0.000000, 0.000000, 0.000000)", kv(out, "Min bound"))
        check("A-4 ★기준을 **말한다** (`bbox basis`)",
              "요소가 쓰는 절점만" in (kv(out, "bbox basis") or ""), kv(out, "bbox basis"))
        check("A-5 전체 절점 bbox 를 함께 낸다",
              kv(out, "All-node min") == "(-40.000000, 0.000000, 0.000000)"
              and kv(out, "All-node max") == "(28.000000, 5.000000, 2.000000)",
              (kv(out, "All-node min"), kv(out, "All-node max")))
        check("A-6 고아 수와 비율을 낸다", (kv(out, "Orphan nodes") or "").startswith("2")
              and "20.00" in (kv(out, "Orphan nodes") or ""), kv(out, "Orphan nodes"))
        check("A-7 ★축을 지목해 경고한다 (x 로 58 다르다)",
              "WARN" in out and "x 로 58" in out,
              [l for l in out.splitlines() if "WARN" in l][:1])
        check("A-8 ★어느 기준을 쓰라고 말한다",
              "요소 사용 절점 기준" in out and "Min bound" in out.split("WARN")[-1],
              [l for l in out.splitlines() if "WARN" in l][:1])

        # ── B: ★고아가 없으면 **거짓 경보가 없다** ──
        deck(os.path.join(d, "clean.k"))
        rc, out = run(binary, d, "info", "clean.k")
        check("B-1 info rc=0", rc == 0, out[-250:])
        check("B-2 기준은 그래도 말한다", "bbox basis" in out)
        check("B-3 ★전체 절점 블록을 내지 않는다 (정상 출력을 더럽히지 않는다)",
              "All-node min" not in out and "Orphan nodes" not in out,
              [l for l in out.splitlines() if "All-node" in l or "Orphan" in l][:2])
        check("B-4 ★경고하지 않는다", "두 bbox 가" not in out,
              [l for l in out.splitlines() if "WARN" in l][:2])

        # ── C: ★플랫폼 정규식이 계속 맞는다 ──
        #    kfile_inspect.py:22-24 이 쓰는 그 패턴을 **그대로** 복사해 맞춰 본다.
        rc, out = run(binary, d, "info", "orph.k")
        NUM = r"(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
        for label, pat in (("Min bound", rf"^Min bound:\s+\({NUM},\s*{NUM},\s*{NUM}\)"),
                           ("Max bound", rf"^Max bound:\s+\({NUM},\s*{NUM},\s*{NUM}\)"),
                           ("Size", rf"^Size:\s+\({NUM},\s*{NUM},\s*{NUM}\)")):
            m = re.search(pat, out, re.M)
            check("C-1 ★플랫폼 정규식이 `%s` 를 찾는다 (kfile_inspect.py)" % label, m is not None)
        # 그 값이 요소 기준이어야 한다 — 플랫폼·프런트가 그 값을 쓴다
        m = re.search(rf"^Size:\s+\({NUM},\s*{NUM},\s*{NUM}\)", out, re.M)
        check("C-2 ★플랫폼이 받는 Size 가 **요소 기준**이다 (10, 아니고 68 이면 사고다)",
              m is not None and abs(float(m.group(1)) - 10.0) < 1e-6,
              m.group(1) if m else None)

        # ── D: modelmeta 가 두 기준을 다 내고 어느 쪽인지 적는다 ──
        write(os.path.join(d, "mm.yaml"), "model: orph.k\noutput: mm\n")
        rc, out = run(binary, d, "modelmeta", "mm.yaml")
        check("D-1 modelmeta rc=0", rc == 0, out[-250:])
        md = None
        for fn in sorted(os.listdir(d)):
            if fn.startswith("mm") and fn.endswith(".json"):
                try:
                    md = json.load(open(os.path.join(d, fn), encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if isinstance(md, dict) and md.get("model"):
                    break
                md = None
        if md is None:
            check("D-2 modelmeta JSON 을 읽었다", False, sorted(os.listdir(d)))
        else:
            m = md["model"]
            check("D-2 `bbox_basis` 가 전체 절점이라고 적는다", m.get("bbox_basis") == "all_nodes",
                  m.get("bbox_basis"))
            check("D-3 `bbox_min` 이 전체 절점 값이다", m.get("bbox_min") == [-40, 0, 0],
                  m.get("bbox_min"))
            check("D-4 ★요소 기준 값을 **함께** 낸다", m.get("bbox_used_min") == [0, 0, 0]
                  and m.get("bbox_used_max") == [10, 5, 2],
                  (m.get("bbox_used_min"), m.get("bbox_used_max")))
            check("D-5 요소 기준의 이름을 적는다",
                  m.get("bbox_used_basis") == "nodes_referenced_by_elements",
                  m.get("bbox_used_basis"))
            check("D-6 고아 수를 낸다", m.get("orphan_nodes") == 2, m.get("orphan_nodes"))
            conv = (md.get("conventions") or {}).get("bbox") or ""
            check("D-7 ★conventions 가 `*NODE` 전체임을 말한다 "
                  "(전에 '고립 절점은 들어오지 않는다' 고 **거짓**을 적었다)",
                  "전체" in conv and "고아" in conv, conv[:150])
            check("D-8 파트별 bbox 는 요소 기준 그대로다 (손대지 않았다)",
                  md["parts"][0]["bbox_min"] == [0, 0, 0], md["parts"][0].get("bbox_min"))

        # ── E: 요소가 없는 덱 — 기준을 가릴 수 없다고 말한다 ──
        write(os.path.join(d, "noel.k"), "*KEYWORD\n*NODE\n"
              "       1     0.000000000     0.000000000     0.000000000\n"
              "       2     1.000000000     0.000000000     0.000000000\n*END\n")
        rc, out = run(binary, d, "info", "noel.k")
        check("E-1 요소가 없으면 그 사실을 기준에 적는다",
              "요소가 없어" in (kv(out, "bbox basis") or ""), kv(out, "bbox basis"))
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
