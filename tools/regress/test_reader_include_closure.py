#!/usr/bin/env python3
# 분석 op(info·modelmeta·그림 셋)이 인클루드 닫힘까지 읽어 마스터 덱의 기하를 보는지 보는 회귀 시험
"""리더가 `*INCLUDE` 를 읽는다 — 분석 전용 (2026-10-16).

왜 이 시험이 있나.

  `KFileReader::readFile` 은 주 덱만 읽었다. 그래서 메시를 인클루드로 나눈 마스터 덱에서
    · `info` 가 절점·요소·파트 0 · 「Mesh has no nodes」를 냈다(실사용 마스터 737바이트 · INCLUDE 7 · PART 0)
    · `modelmeta` 는 재질·접촉 원문은 닫힘까지 모았는데 **메시만** 주 덱이라 파트가 비었다
    · `section`·`surfview`·`stackdiagram` 은 「요소가 없다」로 거절했다
  지금은 `readFileWithIncludes` 가 닫힘을 정본(`include_closure`)으로 펼쳐 **같은 파서로** 읽는다. 덱을 고쳐 쓰는
  op 은 그대로 주 덱만 읽는다(인클루드 안의 카드를 고쳐 쓸 길이 없다).

신탁.
  · 마스터 덱의 절점·요소·파트 수 = 같은 기하를 한 파일에 둔 덱의 수
  · 인클루드가 없는 덱은 예전과 같다(저장소 500장 info 출력 — 465장 글자 그대로 · 다른 35장은 모두 인클루드 덱)
  · 닫힘을 다 못 읽으면 그렇다고 말하고, `*INCLUDE ±`(폭을 바꾸는 인클루드)는 펼치지 않는다
  · `--strict` 의 「없는 노드를 가리키는 요소」는 닫힘을 다 읽었으면 인클루드가 있어도 단정한다

usage: test_reader_include_closure.py <KooRemapper 바이너리>
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
FAILS, OKS = [], []
BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\n"
       "mid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:300]))
    print("  %-68s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def kv(out, key):
    m = re.search(r"^%s:\s+(\S+)" % re.escape(key), out, re.M)
    return m.group(1) if m else None


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="rcl_")
    try:
        write(os.path.join(d, "box.yaml"), BOX)
        run(binary, d, "generate", "box", "box.yaml")
        box = open(os.path.join(d, "box.k"), encoding="utf-8").read()
        # 기하를 둘로 — 절점은 nodes.k, 요소·파트·섹션·재질은 elems.k. 마스터는 인클루드만 든다.
        L = box.splitlines()
        ni = next(i for i, l in enumerate(L) if l.strip().upper() == "*NODE")
        nj = next(i for i in range(ni + 1, len(L)) if L[i].startswith("*"))
        end = max(i for i, l in enumerate(L) if l.strip().upper() == "*END")
        # `generate box` 덱은 *MAT·*SECTION·*PART 가 *NODE 앞에 온다 — 그것도 elems.k 로
        write(os.path.join(d, "nodes.k"), "*KEYWORD\n" + "\n".join(L[ni:nj]) + "\n*END\n")
        write(os.path.join(d, "elems.k"), "*KEYWORD\n" + "\n".join(L[1:ni] + L[nj:end]) + "\n*END\n")
        write(os.path.join(d, "master.k"), "*KEYWORD\n*INCLUDE\nnodes.k\n*INCLUDE\nelems.k\n*END\n")

        print("[A info — 마스터 덱의 기하를 본다]")
        rc0, one = run(binary, d, "info", "box.k")
        rc, out = run(binary, d, "info", "master.k", "--strict")
        check("A-1 절점·요소·파트 수가 한 파일 덱과 같다", all(kv(out, k) == kv(one, k) and kv(one, k) not in (None, "0")
              for k in ("Nodes", "Elements", "Parts")), [(k, kv(out, k), kv(one, k)) for k in ("Nodes", "Elements", "Parts")])
        check("A-2 bbox 가 한 파일 덱과 같다", kv(out, "Min bound") == kv(one, "Min bound") and
              kv(out, "Max bound") == kv(one, "Max bound"), (kv(out, "Max bound"), kv(one, "Max bound")))
        check("A-3 「인클루드 2개를 함께 읽었다」 · 「Mesh has no nodes」 없음 · rc 0",
              rc == 0 and "인클루드 2개를 함께 읽었다" in out and "Mesh has no nodes" not in out, out[-300:])

        print("[B modelmeta — 파트가 비지 않는다]")
        for name, model in (("one", "box.k"), ("master", "master.k")):
            write(os.path.join(d, "%s.yaml" % name), "model: %s\noutput: mm_%s\ndetect: false\n" % (model, name))
            run(binary, d, "modelmeta", "%s.yaml" % name)
        mo = json.load(open(os.path.join(d, "mm_one_modelmeta.json"), encoding="utf-8"))
        mm = json.load(open(os.path.join(d, "mm_master_modelmeta.json"), encoding="utf-8"))
        check("B-1 마스터 덱의 파트·요소 수·부피가 한 파일 덱과 같다",
              [(p["pid"], p["n_elems"], p["volume"]) for p in mm["parts"]] ==
              [(p["pid"], p["n_elems"], p["volume"]) for p in mo["parts"]] and mm["parts"], mm["parts"][:1])

        print("[C 그림 셋 — 마스터 덱도 그린다]")
        write(os.path.join(d, "sec.yaml"), "model: master.k\noutput: sec\naxis: z\n")
        rc, out = run(binary, d, "section", "sec.yaml")
        check("C-1 section rc 0 · 그림이 나온다", rc == 0 and os.path.exists(os.path.join(d, "sec_section.svg")), out[-300:])
        write(os.path.join(d, "sv.yaml"), "model: master.k\noutput: sv\n")
        rc, out = run(binary, d, "surfview", "sv.yaml")
        check("C-2 surfview rc 0 · 그림이 나온다", rc == 0 and os.path.exists(os.path.join(d, "sv_surface.svg")), out[-300:])
        write(os.path.join(d, "sd.yaml"), "model: master.k\noutput: sd\n")
        rc, out = run(binary, d, "stackdiagram", "sd.yaml")
        check("C-3 stackdiagram rc 0 · 그림이 나온다", rc == 0 and os.path.exists(os.path.join(d, "sd_stackdiagram.svg")),
              out[-300:])

        print("[D 못 읽은 것 · 폭을 바꾸는 인클루드 · --strict]")
        write(os.path.join(d, "master_miss.k"), "*KEYWORD\n*INCLUDE\nnodes.k\n*INCLUDE\nelems.k\n*INCLUDE\nnot_here.k\n*END\n")
        rc, out = run(binary, d, "info", "master_miss.k")
        check("D-1 일부를 못 읽으면 그렇다고 말한다(읽은 것은 본다)",
              "일부를 못 읽었다" in out and kv(out, "Nodes") == kv(one, "Nodes"), out[-300:])
        write(os.path.join(d, "master_pm.k"), "*KEYWORD\n*INCLUDE +\nnodes.k\n*INCLUDE\nelems.k\n*END\n")
        rc, out = run(binary, d, "info", "master_pm.k")
        check("D-2 `*INCLUDE +`(폭을 바꾼다)면 펼치지 않고 주 덱만 읽었다고 말한다",
              "펼치지 않고 주 덱만" in out and kv(out, "Nodes") == "0", out[-300:])
        # 요소가 없는 절점을 가리킨다 — 인클루드에 나뉘어 있어도 닫힘을 다 읽었으면 단정한다
        bad = open(os.path.join(d, "elems.k"), encoding="utf-8").read().splitlines()
        ei = next(i for i, l in enumerate(bad) if l.strip().upper().startswith("*ELEMENT_SOLID"))
        row = next(i for i in range(ei + 1, len(bad)) if bad[i].strip() and not bad[i].startswith("$"))
        f = bad[row]
        bad[row] = f[:16] + "%8d" % 999999 + f[24:]
        write(os.path.join(d, "elems_bad.k"), "\n".join(bad) + "\n")
        write(os.path.join(d, "master_bad.k"), "*KEYWORD\n*INCLUDE\nnodes.k\n*INCLUDE\nelems_bad.k\n*END\n")
        rc, out = run(binary, d, "info", "master_bad.k", "--strict")
        check("D-3 ★닫힘을 다 읽었으면 「없는 노드를 가리키는 요소」를 단정한다(rc 1)",
              rc == 1 and "없는 노드를 가리키는 요소" in out, (rc, out[-300:]))
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
