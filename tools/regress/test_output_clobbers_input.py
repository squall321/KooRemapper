#!/usr/bin/env python3
# 흘려 읽는 op(extract-parts · cleanup-nodes · strip)이 입력 덱(주 덱 · 인클루드)과 같은 파일에 쓰려 하면 입력에 손대지 않고 거절하는지 보는 회귀 시험
"""쓸 파일이 입력 덱을 덮는가 (2026-11-07 적대적 검토 #6).

왜 이 시험이 있나.

  extract-parts · cleanup-nodes · strip 은 산출을 열어(잘라 비워) 놓고 주 덱(extract-parts 는 인클루드까지)을 **흘려 읽는다**.
  output 이 model 과 같은 파일이면 입력이 0 바이트가 된다 — 검토 재현: extract-parts 는 rc 1 로 끝나도 입력이 사라졌고, cleanup-nodes ·
  strip 은 빈 입력을 읽어 rc 0 이었다(되읽기도 빈 덱을 보았다). 보고 · 인클루드도 다 읽은 뒤에 쓰면 그 입력을 덮는다.
  이제 산출을 열기 전에 쓸 파일(output · report · 번호 지도)을 읽는 파일과 견주어(정규 경로 · 하드 링크) 같으면 거절한다.

무엇을 보나(op 마다).
  output 이 model 과 같은 이름 · 다른 철자(./ · 절대 경로) · 하드 링크 · 인클루드 파일 · report 가 model → rc 1 · 입력 바이트 그대로 ·
  다른 이름이면 rc 0(대조).

usage: test_output_clobbers_input.py <KooRemapper 바이너리>
"""
import hashlib
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


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else None


def node(n, x):
    return "%8d%16.6f%16.6f%16.6f" % (n, x, 0.0, 0.0)


def deck(include=None):
    """절점 101-105 · 보 21(101 102) · 22(102 103) 파트 9 · 105 는 고아. `include` 가 있으면 그 파일을 맨 *INCLUDE 로 끌어온다."""
    L = ["*KEYWORD", "*NODE"] + [node(n, float(n)) for n in (101, 102, 103, 104, 105)]
    L += ["*ELEMENT_BEAM", "%8d%8d%8d%8d" % (21, 9, 101, 102), "%8d%8d%8d%8d" % (22, 9, 102, 103)]
    if include:
        L += ["*INCLUDE", include]
    L += ["*PART", "cable", "%10d%10d%10d" % (9, 9, 9), "*SECTION_BEAM", "%10d%10d" % (9, 3),
          "*MAT_ELASTIC", "%10d%10s%10s%10s" % (9, "7.85E-9", "210000.", "0.3"), "*END"]
    return "\n".join(L) + "\n"


INC = "*KEYWORD\n*ELEMENT_BEAM\n%8d%8d%8d%8d\n*END\n" % (23, 9, 103, 104)


def stage(root, tag):
    d = os.path.join(root, tag)
    os.makedirs(d)
    write(os.path.join(d, "in.k"), deck(include="inc.k"))
    write(os.path.join(d, "inc.k"), INC)
    return d


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="oci_")
    try:
        ops = {
            "extract-parts": lambda out, extra="": "model: in.k\noutput: %s\nparts: [9]\n%s" % (out, extra),
            "cleanup-nodes": lambda out, extra="": "model: in.k\noutput: %s\nmode: safe\n%s" % (out, extra),
            "strip": lambda out, extra="": "model: in.k\noutput: %s\nkeywords:\n  - *MAT_ELASTIC\n%s" % (out, extra),
        }
        for op, cfg in ops.items():
            print("[%s]" % op)
            k = 0
            cases = [("output 이 model 과 같은 이름", "in.k", "", True),
                     ("output 이 model 의 다른 철자(./in.k)", "./in.k", "", True),
                     ("output 이 model 의 절대 경로", None, "", True),
                     ("output 이 model 의 하드 링크", "hard.k", "", True),
                     ("output 이 인클루드 파일", "inc.k", "", True)]
            if op != "strip":
                cases.append(("report 가 model", "out.k", "report: in.k\n", True))
            cases.append(("대조 — 다른 이름이면 rc 0", "out.k", "", False))
            for what, out, extra, refuse in cases:
                k += 1
                d = stage(root, "%s_%d" % (op, k))
                if out is None:
                    out = os.path.join(d, "in.k")
                if out == "hard.k":
                    os.link(os.path.join(d, "in.k"), os.path.join(d, "hard.k"))
                write(os.path.join(d, "c.yaml"), cfg(out, extra))
                before = (sha(os.path.join(d, "in.k")), sha(os.path.join(d, "inc.k")))
                rc, text = run(binary, d, op, "c.yaml")
                after = (sha(os.path.join(d, "in.k")), sha(os.path.join(d, "inc.k")))
                if refuse:
                    check("%s-%d ★%s → rc 1 · 입력(주 덱 · 인클루드) 바이트 그대로" % (op, k, what),
                          rc == 1 and before == after and "같은 파일" in text, (rc, before == after, text[-400:]))
                else:
                    check("%s-%d %s" % (op, k, what), rc == 0 and before == after and os.path.exists(os.path.join(d, "out.k")),
                          (rc, text[-400:]))
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
