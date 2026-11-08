#!/usr/bin/env python3
# assemble 이 덧붙인 battery 덱을 실행 내내 통째로 들고 있지 않는지(battery 둘의 최고 RSS ≈ 하나) · 뒤 op 번호는 그대로인지 보는 회귀 시험
"""assemble battery 의 메모리 (2026-11-08 · 사용자 결정 「놓는다」).

왜 이 시험이 있나.

  assemble 의 battery 는 뒤 op 의 번호 발급(`inclMax`)이 battery 덱의 번호를 세도록 덱의 줄을 `addedDecks_` 에 남겼다 — **덱
  통째로**, 실행이 끝날 때까지. battery 를 둘 얹으면 첫 덱을 든 채로 둘째 덱을 지어 최고 RSS 가 덱 하나만큼(tier 1 · 29 MB 덱에서
  +54 MB) 더 올랐다. 이제 번호 발급이 읽는 정의 카드 머리만 남기고(절점 · 요소 번호는 커서로 지킨다) 짓는 동안의 사본도 줄였다.
  산출은 바이트까지 같다(battery 하나 · 둘 · 뒤 contact · load · 펼치기 — 고치기 전 바이너리와 대조함).

무엇을 보나.
  M-1 tier 1 battery 둘을 얹은 assemble 의 최고 RSS − 하나를 얹은 것 < 덱 크기의 절반(예전엔 덱 하나만큼 넘게 올랐다)
  M-2 battery 둘 뒤의 contact 가 낸 번호까지 주 덱 + 두 battery 덱에 겹친 정의 · 끊긴 참조가 없다(뒤 op 번호가 그대로)

usage: test_assemble_battery_memory.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "tools", "help"))
from ops_help import OPS  # noqa: E402
from test_assemble_battery_ids import deck_facts, integrity  # noqa: E402  (같은 덱 읽기 · 판정)

FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-96s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def peak_mb(binary, cwd, *args):
    """그 실행 하나의 최고 RSS(MB) · rc — os.wait4 가 그 자식의 rusage 만 준다."""
    p = subprocess.Popen([binary, *args], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _, status, ru = os.wait4(p.pid, 0)
    return os.waitstatus_to_exitcode(status), ru.ru_maxrss / 1024.0


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="abmem_")
    try:
        d = os.path.join(root, "m")
        os.makedirs(d)
        with open(os.path.join(d, "box.yaml"), "w", encoding="utf-8") as f:
            f.write({o["name"]: o for o in OPS}["warpage"]["files"]["box.yaml"])
        subprocess.run([binary, "generate", "box", "box.yaml"], cwd=d, capture_output=True)
        bat = open(os.path.join(REPO, "examples", "battery", "swell", "stacked", "stacked_swell.yaml"), encoding="utf-8").read()
        bat = re.sub(r"^tier:.*$", "tier: 1", bat, count=1, flags=re.M)
        for n in ("a", "b"):
            with open(os.path.join(d, "bat_%s.yaml" % n), "w", encoding="utf-8") as f:
                f.write(re.sub(r"^output:.*$", "output: bt_" + n, bat, count=1, flags=re.M))
        with open(os.path.join(d, "one.yaml"), "w", encoding="utf-8") as f:
            f.write("base_model: box.k\noutput: one\noperations:\n  - type: battery\n    config: bat_a.yaml\n")
        with open(os.path.join(d, "two.yaml"), "w", encoding="utf-8") as f:
            f.write("base_model: box.k\noutput: two\noperations:\n  - type: battery\n    config: bat_a.yaml\n"
                    "  - type: battery\n    config: bat_b.yaml\n"
                    "  - type: contact\n    contacts:\n      - action: create\n        type: automatic_single_surface\n"
                    "        slave:\n          pid: 1\n        title: AfterBatteries\n")
        rc1, one = peak_mb(binary, d, "assemble", "one.yaml")
        deck_mb = os.path.getsize(os.path.join(d, "bt_a_tier1_phase1.k")) / 2**20 if rc1 == 0 else 0
        rc2, two = peak_mb(binary, d, "assemble", "two.yaml")
        check("★M-1 battery 둘의 최고 RSS − 하나 < 덱의 절반(%.0f MB 덱 · 하나 %.0f MB · 둘 %.0f MB · 예전엔 덱 하나만큼 넘게 올랐다)"
              % (deck_mb, one, two), rc1 == 0 and rc2 == 0 and deck_mb > 10 and two - one < 0.5 * deck_mb,
              (rc1, rc2, deck_mb, one, two))
        if rc2 == 0:
            defs, refs, _, _, incs = deck_facts(os.path.join(d, "two.k"))
            dup, dangling = integrity(defs, refs)
            check("M-2 battery 둘 뒤 contact 의 번호까지 겹친 정의 · 끊긴 참조 없음(뒤 op 번호 그대로)",
                  len(incs) == 2 and not dup and not dangling, (incs, dup, dangling))
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
