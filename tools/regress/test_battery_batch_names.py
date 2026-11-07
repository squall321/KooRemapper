#!/usr/bin/env python3
# battery 배치의 덱 이름(모델 종류가 둘 이상이면 종류를 넣는다)과, 그래도 겹치는 조합을 쓰기 전에 짚어 거절하는지 보는 회귀 시험
"""battery 배치의 덱 이름 (2026-11-07 셋째 묶음 · 사용자 결정).

왜 이 시험이 있나.

  battery 덱 이름은 `<output><tier>_phase{1|2}.k` 다(카탈로그 · 매뉴얼에 적힌 규칙). 모델 종류가 이름에 없어 batch 의
  model_types: [stacked, wound] 가 같은 덱에 차례로 써 앞 덱을 잃고 rc 0 이었다. tier 는 다섯 칸(_tier-1 · _tier0 · _tier0_5 ·
  _tier1 · _tier2)으로 묶이고 phase 2 가 아니면 모두 _phase1 이라 tiers: [0, 0.2] · phases: [1, 3] 도 겹쳤다.
  사용자 결정 — 종류가 **둘 이상**이면 이름에 넣는다: `<output>_<model_type><tier>_phase{1|2}.k`. 하나뿐이면 예전 이름 그대로.
  그래도 겹치면 쓰기 전에 rc 1 로 그 조합들을 짚는다.

무엇을 보나.
  B-1 [stacked, wound] × phases [1, 2] · use_dynain → 덱 넷 bt_stacked_tier0_phase{1,2}.k · bt_wound_tier0_phase{1,2}.k, phase 2 덱의
      *INCLUDE_DYNAIN 이 같은 종류의 phase 1 이름(bt_<종류>_tier0_phase1.dynain)을 가리킨다
  B-2 · B-3 겹치는 tier · phase → rc 1 · 덱 없음 · 겹친 이름을 말한다   B-5 종류가 둘이어도 tier 가 겹치면 거절
  B-4 대조 — 종류 하나 · tiers [0, 1] 은 예전 이름 그대로(bt_tier0_phase1.k · bt_tier1_phase1.k)

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
    print("  %-96s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def include_dynain(path):
    """덱의 *INCLUDE_DYNAIN 다음 줄(없으면 None)."""
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    for i, l in enumerate(lines[:-1]):
        if l.strip().upper() == "*INCLUDE_DYNAIN":
            return lines[i + 1].strip()
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    src = open(os.path.join(REPO, "examples", "battery", "swell", "stacked", "stacked_swell.yaml"),
               encoding="utf-8").read()
    root = tempfile.mkdtemp(prefix="batb_")
    try:
        def case(k, batch, extra=""):
            d = os.path.join(root, "c%d" % k)
            os.makedirs(d)
            cfg = src.replace("output: battery_stacked_swell", "output: bt") + extra + "\nbatch:\n" + batch
            with open(os.path.join(d, "b.yaml"), "w", encoding="utf-8") as f:
                f.write(cfg)
            rc, out = run(binary, d, "battery", "b.yaml")
            return d, rc, out, sorted(f for f in os.listdir(d) if f.endswith(".k"))

        d, rc, out, made = case(1, "  model_types: [stacked, wound]\n  phases: [1, 2]\n", "\nuse_dynain: true\n")
        want = ["bt_stacked_tier0_phase1.k", "bt_stacked_tier0_phase2.k", "bt_wound_tier0_phase1.k", "bt_wound_tier0_phase2.k"]
        check("B-1 ★model_types [stacked, wound] → 종류를 이름에 넣는다(예전엔 같은 덱에 차례로 써 앞 덱을 잃었다)",
              rc == 0 and made == want, (rc, made, out[-300:]))
        if made == want:
            check("B-1   └ phase 2 덱의 *INCLUDE_DYNAIN 이 같은 종류의 phase 1 이름을 가리킨다",
                  include_dynain(os.path.join(d, "bt_stacked_tier0_phase2.k")) == "bt_stacked_tier0_phase1.dynain"
                  and include_dynain(os.path.join(d, "bt_wound_tier0_phase2.k")) == "bt_wound_tier0_phase1.dynain",
                  (include_dynain(os.path.join(d, "bt_stacked_tier0_phase2.k")),
                   include_dynain(os.path.join(d, "bt_wound_tier0_phase2.k"))))
        for k, (what, batch, name) in enumerate((
                ("B-2 tiers [0, 0.2] — 둘 다 _tier0", "  tiers: [0, 0.2]\n", "bt_tier0_phase1.k"),
                ("B-3 phases [1, 3] — phase 2 가 아니면 _phase1", "  phases: [1, 3]\n", "bt_tier0_phase1.k"),
                ("B-5 종류가 둘이어도 tiers [0, 0.2] 는 겹친다", "  model_types: [stacked, wound]\n  tiers: [0, 0.2]\n",
                 "bt_stacked_tier0_phase1.k")), 2):
            d, rc, out, made = case(k, batch)
            check("★%s → rc 1 · 덱을 쓰지 않는다 · 겹친 이름(%s)을 말한다" % (what, name),
                  rc == 1 and not made and name in out and "같은 파일 이름" in out, (rc, made, out[-400:]))
        d, rc, out, made = case(9, "  tiers: [0, 1]\n")
        check("B-4 대조 — 종류 하나 · tiers [0, 1] 은 예전 이름 그대로",
              rc == 0 and made == ["bt_tier0_phase1.k", "bt_tier1_phase1.k"], (rc, made, out[-300:]))
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
