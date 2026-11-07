#!/usr/bin/env python3
# 보 족(격자 밖) 요소 카드를 걷는 소비자들이 카드 경계 · 칸 자리를 맞게 세는지 보는 회귀 시험(cleanup-nodes · extract-parts)
"""보 족 카드 걷기 (2026-11-07 적대적 검토 뒤 고침).

왜 이 시험이 있나.

  보 · 이산 · 질량 · 안전띠 · 플롯 요소는 격자 리더가 메시에 담지 않는다 — cleanup-nodes 와 extract-parts 가 덱 줄을 직접 걸으며
  카드 경계(`auxElementCard` 의 줄 수)와 칸 자리를 센다. 검토가 그 걸음의 결함을 찾았다.

무엇을 보나.
  A 빈 옵션 카드 — `*ELEMENT_BEAM_ORIENTATION` 의 VX VY VZ 카드를 비워 두면 그 빈 줄이 카드다(LS-PrePost 도 그렇게 읽는다).
    두 걸음이 「카드 밖의 빈 줄」 을 격자 셈으로만 판정해 다음 요소의 Card 1 을 그 카드로 삼켰다 — cleanup-nodes 는 그 요소의
    절점을 지우고(rc 0), extract-parts 는 절점을 놓쳐 되읽기에서 rc 1 로 깨진 산출을 냈다.

usage: test_aux_card_walkers.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:400]))
    print("  %-72s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def node(n, x):
    return "%8d%16.6f%16.6f%16.6f" % (n, x, 0.0, 0.0)


def node_ids(path):
    """*NODE 블록의 번호 → x 좌표(이 시험의 절점은 x = 옛 번호)."""
    out, sect = {}, ""
    for ln in open(path, encoding="utf-8").read().split("\n"):
        if ln.startswith("*"):
            sect = ln.split()[0].upper()
        elif sect == "*NODE" and ln.strip() and not ln.startswith("$"):
            out[int(ln[:8])] = int(round(float(ln[8:24])))
    return out


def section_lines(path, kw):
    out, sect = [], ""
    for ln in open(path, encoding="utf-8").read().split("\n"):
        if ln.startswith("*"):
            sect = ln.split()[0].upper().rstrip("%+-")
        elif sect == kw and not ln.startswith("$"):
            out.append(ln)
    return out


def beam_deck(block, nodes=(101, 102, 103, 104, 105)):
    """절점(x = 번호) · 보 블록 · 파트 9(보 단면 · 탄성 재질)."""
    L = ["*KEYWORD", "*NODE"] + [node(n, float(n)) for n in nodes] + block
    L += ["*PART", "cable", "%10d%10d%10d" % (9, 9, 9), "*SECTION_BEAM", "%10d%10d" % (9, 1),
          "*MAT_ELASTIC", "%10d%10s%10s%10s" % (9, "7.85E-9", "210000.", "0.3"), "*END"]
    return "\n".join(L) + "\n"


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="acw_")
    try:
        print("[A 빈 옵션 카드 — `*ELEMENT_BEAM_ORIENTATION` 의 VX VY VZ 를 비운 줄도 카드다]")
        # 보 21(101 · 102) + **빈** Card 2 · 보 22(103 · 104) + 방향 벡터 Card 2. 105 는 아무도 안 쓴다
        blk = ["*ELEMENT_BEAM_ORIENTATION",
               "%8d%8d%8d%8d" % (21, 9, 101, 102), "",
               "%8d%8d%8d%8d" % (22, 9, 103, 104), "%16s%16s%16s" % ("0.0", "1.0", "0.0")]
        write(os.path.join(d, "A.k"), beam_deck(blk))
        write(os.path.join(d, "a.yaml"), "model: A.k\noutput: a_out.k\nmode: safe\nreport: a.json\n")
        rc, out = run(binary, d, "cleanup-nodes", "a.yaml")
        rep = json.load(open(os.path.join(d, "a.json"), encoding="utf-8")) if os.path.exists(os.path.join(d, "a.json")) else {}
        kept = sorted(node_ids(os.path.join(d, "a_out.k")).values()) if rc == 0 else []
        check("A-1 cleanup-nodes safe — rc 0 · ★보 22 의 절점(103 · 104)을 남기고 105 만 지운다",
              rc == 0 and kept == [101, 102, 103, 104] and (rep.get("nodes") or {}).get("deletable") == 1,
              (rc, kept, rep.get("nodes"), out[-300:]))
        write(os.path.join(d, "ax.yaml"), "model: A.k\noutput: ax_out.k\nparts: [9]\nreport: ax.json\n")
        rc, out = run(binary, d, "extract-parts", "ax.yaml")
        rep = json.load(open(os.path.join(d, "ax.json"), encoding="utf-8")) if os.path.exists(os.path.join(d, "ax.json")) else {}
        carried = sorted(node_ids(os.path.join(d, "ax_out.k")).values()) if rc == 0 else []
        check("A-2 extract-parts — rc 0 · ★두 보의 절점 넷을 싣고 되읽기 미정의 0",
              rc == 0 and carried == [101, 102, 103, 104] and (rep.get("verify") or {}).get("undefined_nodes") == 0,
              (rc, carried, rep.get("verify"), out[-300:]))
        rows = section_lines(os.path.join(d, "ax_out.k"), "*ELEMENT_BEAM_ORIENTATION") if rc == 0 else []
        check("A-3 extract-parts — 보 두 장을 빈 카드까지 그대로 실었다(빈 줄을 버리지 않는다)", rows == blk[1:], rows)
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
