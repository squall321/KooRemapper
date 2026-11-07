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
  ★output 이 설정 YAML · 따라가지 않는 변형 인클루드(`*INCLUDE_TRANSFORM`)의 파일 → rc 1 · 그 파일 그대로 — 세 op 이 같은 목록이다
  (셋째 묶음 — strip 은 주 덱 · 인클루드만 견주어 설정과 변형 인클루드의 파일을 덮고 rc 0 이었다. 거절은 공용 관문 `output_guard`)
  ★공용 관문을 쓰는 다른 op(database · convert)도 변형 인클루드의 파일에 쓰지 않는다 — 관문의 모델 입력이 닫힘의 파일만 보았다

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
TR = "*INCLUDE_TRANSFORM\ntr.k\n0,0,0,0,0,0,0\n0,0,0,0,0,0,0\n1.0,1.0,1.0,1.0\n0\n"


def stage(root, tag, transform=False):
    d = os.path.join(root, tag)
    os.makedirs(d)
    text = deck(include="inc.k")
    if transform:   # 따라가지 않는 변형 인클루드 — 그 파일은 산출 덱이 그대로 가리킨다
        text = text.replace("*END", TR + "*END")
        write(os.path.join(d, "tr.k"), "*KEYWORD\n*NODE\n" + node(201, 9.0) + "\n*END\n")
    write(os.path.join(d, "in.k"), text)
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
            cases = [("output 이 model 과 같은 이름", "in.k", "", True, False),
                     ("output 이 model 의 다른 철자(./in.k)", "./in.k", "", True, False),
                     ("output 이 model 의 절대 경로", None, "", True, False),
                     ("output 이 model 의 하드 링크", "hard.k", "", True, False),
                     ("output 이 인클루드 파일", "inc.k", "", True, False),
                     ("output 이 설정 YAML", "c.yaml", "", True, False),
                     ("output 이 따라가지 않는 *INCLUDE_TRANSFORM 의 파일", "tr.k", "", True, True)]
            if op != "strip":
                cases.append(("report 가 model", "out.k", "report: in.k\n", True, False))
            cases.append(("대조 — 다른 이름이면 rc 0", "out.k", "", False, False))
            for what, out, extra, refuse, transform in cases:
                k += 1
                d = stage(root, "%s_%d" % (op, k), transform)
                if out is None:
                    out = os.path.join(d, "in.k")
                if out == "hard.k":
                    os.link(os.path.join(d, "in.k"), os.path.join(d, "hard.k"))
                write(os.path.join(d, "c.yaml"), cfg(out, extra))
                files = ("in.k", "inc.k", "c.yaml", "tr.k")
                before = tuple(sha(os.path.join(d, f)) for f in files)
                rc, text = run(binary, d, op, "c.yaml")
                after = tuple(sha(os.path.join(d, f)) for f in files)
                if refuse:
                    check("%s-%d ★%s → rc 1 · 입력(설정 · 주 덱 · 인클루드 · 변형 인클루드의 파일) 바이트 그대로" % (op, k, what),
                          rc == 1 and before == after and "같은 파일" in text, (rc, before == after, text[-400:]))
                else:
                    check("%s-%d %s" % (op, k, what), rc == 0 and before == after and os.path.exists(os.path.join(d, "out.k")),
                          (rc, text[-400:]))

        # ★공용 관문(`output_guard::modelInputs`)을 쓰는 다른 op 도 — 따라가지 않는 변형 인클루드의 파일에 쓰지 않는다. 그 관문은 모델과
        #   인클루드 닫힘만 보아 database(자기 쓰기) · convert(`ModelAssembler::writeOutput`)가 output 을 그 파일로 주면 rc 0 으로 덮었다 —
        #   산출 덱은 그 `*INCLUDE_TRANSFORM` 카드를 그대로 실어 자기 자신을 가리켰다(셋째 묶음)
        print("[공용 관문을 쓰는 다른 op — 변형 인클루드의 파일]")
        d = os.path.join(root, "og")
        os.makedirs(d)
        write(os.path.join(d, "box.yaml"), "output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 2\nny: 2\nnz: 1\nrho: 7.85e-9\n"
                                           "E: 210000.0\nnu: 0.3\nmid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")
        run(binary, d, "generate", "box", "box.yaml")
        box = open(os.path.join(d, "box.k"), encoding="utf-8").read()
        write(os.path.join(d, "in.k"), box.replace("*END", TR + "*END", 1))
        others = (("database", "db.yaml", "model: in.k\noutput: %s\npreset: drop\ndt: 0.0001\ndt_plot: 0.005\n"),
                  ("convert", "cv.yaml", "base_model: in.k\noutput: %s\noperations:\n  - type: hex20\n    elform: 23\n"))
        for op, y, body in others:
            for out, refuse in (("tr.k", True), ("other.k", False)):
                write(os.path.join(d, "tr.k"), "*KEYWORD\n*NODE\n" + node(201, 9.0) + "\n*END\n")
                write(os.path.join(d, y), body % out)
                before = (sha(os.path.join(d, "in.k")), sha(os.path.join(d, "tr.k")))
                rc, text = run(binary, d, op, y)
                after = (sha(os.path.join(d, "in.k")), sha(os.path.join(d, "tr.k")))
                if refuse:
                    check("%s ★output 이 모델의 *INCLUDE_TRANSFORM 파일 → rc 1 · 그 파일 바이트 그대로" % op,
                          rc == 1 and before == after and "같은 파일" in text, (rc, before == after, text[-400:]))
                else:
                    check("%s 대조 — 다른 이름이면 rc 0" % op, rc == 0 and before == after and os.path.exists(os.path.join(d, out)),
                          (rc, text[-300:]))
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
