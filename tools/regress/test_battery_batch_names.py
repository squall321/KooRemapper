#!/usr/bin/env python3
# battery 배치가 두 조합을 같은 파일 이름에 쓰려 하면 아무것도 쓰지 않고 그 조합들을 짚어 거절하는지 보는 회귀 시험
"""battery 배치의 같은 이름 (2026-11-07 셋째 묶음).

왜 이 시험이 있나.

  battery 덱 이름은 `<output><tier>_phase{1|2}.k` 다(카탈로그 · 매뉴얼에 적힌 규칙). 모델 종류는 이름에 없고, tier 는 다섯
  칸(_tier-1 · _tier0 · _tier0_5 · _tier1 · _tier2)으로 묶이고, phase 2 가 아니면 모두 _phase1 이다. 그래서 batch 의
  model_types: [stacked, wound] · tiers: [0, 0.2] · phases: [1, 3] 은 앞 조합의 덱을 조용히 덮고 rc 0 이었다.
  이름 규칙은 그대로 두고, 겹치면 쓰기 전에 rc 1 로 그 조합들을 짚는다.

무엇을 보나 — 겹치는 셋은 rc 1 · 폴더에 새 파일 없음 · 겹친 이름과 조합을 말한다. 대조 — 겹치지 않는 tiers [0, 1] 은 덱 둘.

usage: test_battery_batch_names.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-90s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    src = open(os.path.join(REPO, "examples", "battery", "swell", "stacked", "stacked_swell.yaml"),
               encoding="utf-8").read()
    root = tempfile.mkdtemp(prefix="batb_")
    try:
        cases = [("B-1 model_types [stacked, wound] — 이름에 모델 종류가 없다", "  model_types: [stacked, wound]\n", True,
                  "bt_tier0_phase1.k"),
                 ("B-2 tiers [0, 0.2] — 둘 다 _tier0", "  tiers: [0, 0.2]\n", True, "bt_tier0_phase1.k"),
                 ("B-3 phases [1, 3] — phase 2 가 아니면 _phase1", "  phases: [1, 3]\n", True, "bt_tier0_phase1.k"),
                 ("B-4 대조 — tiers [0, 1] 은 이름이 갈린다", "  tiers: [0, 1]\n", False, None)]
        for k, (what, batch, clash, name) in enumerate(cases, 1):
            d = os.path.join(root, "c%d" % k)
            os.makedirs(d)
            cfg = src.replace("output: battery_stacked_swell", "output: bt") + "\nbatch:\n" + batch
            with open(os.path.join(d, "b.yaml"), "w", encoding="utf-8") as f:
                f.write(cfg)
            rc, out = run(binary, d, "battery", "b.yaml")
            made = sorted(f for f in os.listdir(d) if f.endswith(".k"))
            if clash:
                check("★%s → rc 1 · 덱을 쓰지 않는다 · 겹친 이름(%s)을 말한다" % (what, name),
                      rc == 1 and not made and name in out and "같은 파일 이름" in out, (rc, made, out[-400:]))
            else:
                check(what + " → rc 0 · 덱 둘", rc == 0 and made == ["bt_tier0_phase1.k", "bt_tier1_phase1.k"],
                      (rc, made, out[-300:]))
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
