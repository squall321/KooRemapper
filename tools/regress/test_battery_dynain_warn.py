#!/usr/bin/env python3
# battery 의 use_dynain: true 인데 dynain_file 이 비어 *INCLUDE_DYNAIN 이 빠질 때 [WARN] 을 내는지(받는 덱은 조용한지) 보는 회귀 시험
"""use_dynain 인데 dynain 이 없는 덱 (2026-11-08 · 사용자 결정 「알린다」).

왜 이 시험이 있나.

  `use_dynain: true` 는 앞 단계 실행의 dynain 을 `*INCLUDE_DYNAIN` 으로 끌어오라는 뜻이다. 이름을 스스로 짓는 것은 batch 의 phases 에
  1 과 2 가 다 있을 때 뒤 phase 뿐이고(매뉴얼 §43.1), 홑 실행에서 `dynain_file` 을 비우면 **말없이** `*INCLUDE_DYNAIN` 이 빠졌다
  (rc 0 · 경고 없음). 가장 작은 변화로 — 이름을 지어내지 않고 — [WARN] 으로 알린다.

무엇을 보나.
  W-1 홑 실행 phase 2 · use_dynain · dynain_file 없음 → rc 0 · 덱에 *INCLUDE_DYNAIN 없음 · [WARN] 이 그 덱 이름과 dynain_file 을 말한다
  W-2 batch phases [2] 만 · use_dynain → 이어 받을 앞 phase 가 없다 → [WARN]
  W-3 assemble 의 battery(phase 2 · use_dynain · dynain_file 없음) → [WARN]
  대조 C-1 dynain_file 을 주면 *INCLUDE_DYNAIN · 경고 없음   C-2 batch phases [1, 2] → 뒤 phase 는 자동 이름 · 앞 phase 는 사슬 머리 — 경고 없음
       C-3 use_dynain 이 거짓이면 경고 없음

usage: test_battery_dynain_warn.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "help"))
from ops_help import OPS  # noqa: E402

FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-96s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def has_include_dynain(path):
    return any(l.strip().upper() == "*INCLUDE_DYNAIN"
               for l in open(path, encoding="utf-8", errors="replace"))


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    src = open(os.path.join(REPO, "examples", "battery", "swell", "stacked", "stacked_swell.yaml"),
               encoding="utf-8").read().replace("output: battery_stacked_swell", "output: bt")
    phase2 = src.replace("\nphase: 1\n", "\nphase: 2\n")
    assert phase2 != src, "예제의 phase 줄을 찾지 못했다"
    root = tempfile.mkdtemp(prefix="bdyn_")
    try:
        def case(k, text, *argv):
            d = os.path.join(root, "c%d" % k)
            os.makedirs(d)
            with open(os.path.join(d, "b.yaml"), "w", encoding="utf-8") as f:
                f.write(text)
            rc, out = run(binary, d, *(argv or ("battery", "b.yaml")))
            warns = [l for l in out.splitlines() if "[WARN]" in l and "dynain_file" in l]
            return d, rc, out, warns

        d, rc, out, warns = case(1, phase2 + "\nuse_dynain: true\n")
        deck = os.path.join(d, "bt_tier0_phase2.k")
        check("★W-1 홑 실행 phase 2 · use_dynain · dynain_file 없음 → rc 0 · *INCLUDE_DYNAIN 없음 · [WARN] 이 덱 이름을 말한다(예전엔 말없이)",
              rc == 0 and os.path.exists(deck) and not has_include_dynain(deck) and len(warns) == 1
              and "bt_tier0_phase2.k" in warns[0], (rc, warns, out[-300:]))
        d, rc, out, warns = case(2, src + "\nuse_dynain: true\nbatch:\n  phases: [2]\n")
        check("★W-2 batch phases [2] 만 · use_dynain → 이어 받을 앞 phase 가 없다 → [WARN](예전엔 말없이)",
              rc == 0 and len(warns) == 1, (rc, warns, out[-300:]))
        d = os.path.join(root, "c3")
        os.makedirs(d)
        box = {o["name"]: o for o in OPS}["warpage"]["files"]["box.yaml"]
        with open(os.path.join(d, "box.yaml"), "w", encoding="utf-8") as f:
            f.write(box)
        run(binary, d, "generate", "box", "box.yaml")
        with open(os.path.join(d, "bat.yaml"), "w", encoding="utf-8") as f:
            f.write(phase2 + "\nuse_dynain: true\n")
        with open(os.path.join(d, "a.yaml"), "w", encoding="utf-8") as f:
            f.write("base_model: box.k\noutput: ba\noperations:\n  - type: battery\n    config: bat.yaml\n")
        rc, out = run(binary, d, "assemble", "a.yaml")
        warns = [l for l in out.splitlines() if "[WARN]" in l and "dynain_file" in l]
        check("★W-3 assemble 의 battery(phase 2 · use_dynain · dynain_file 없음) → [WARN](예전엔 말없이)",
              len(warns) == 1, (rc, warns, out[-300:]))
        d, rc, out, warns = case(4, phase2 + "\nuse_dynain: true\ndynain_file: p1.dynain\n")
        check("C-1 대조 — dynain_file 을 주면 *INCLUDE_DYNAIN · 경고 없음",
              rc == 0 and has_include_dynain(os.path.join(d, "bt_tier0_phase2.k")) and not warns, (rc, warns))
        d, rc, out, warns = case(5, src + "\nuse_dynain: true\nbatch:\n  phases: [1, 2]\n")
        check("C-2 대조 — batch phases [1, 2] → 뒤 phase 는 자동 이름 · 앞 phase 는 사슬 머리 — 경고 없음",
              rc == 0 and has_include_dynain(os.path.join(d, "bt_tier0_phase2.k")) and not warns, (rc, warns))
        d, rc, out, warns = case(6, phase2)
        check("C-3 대조 — use_dynain 이 거짓이면 경고 없음", rc == 0 and not warns, (rc, warns))
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
