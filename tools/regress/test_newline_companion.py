#!/usr/bin/env python3
"""덱과 **함께 풀리는 파일**(dynain·동반 덱)도 같은 개행이어야 한다 — 매트릭스가 못 보는 갈래.

왜 이 시험이 있나 (2026-09-25, 덱 계약 2차 P0-2 잔여):

  전 op 매트릭스(`test_newline_matrix.py`)는 **카탈로그 예제가 밟는 길만** 돈다. 소스의
  `std::ofstream` 30곳을 전수 분류하니, 예제가 안 밟는 갈래에 같은 결함이 셋 더 있었다.

    cclip.cpp:1659  `stress_output: include` 의 dynain — 본 덱은 CRLF, dynain 은 LF
                    → `*INCLUDE` 로 함께 풀리는 짝의 개행이 갈린다
    cclip.cpp:1684  `free_output: true` 의 `_free.k` — 입력 덱 줄에서 만드는데 CRLF 를 잃는다
    squeeze_assemble.cpp:232  `strain_mode` 의 dynain — 메시 덱이 `*INCLUDE` 로 끌어간다

  카탈로그 예제에 그 세 키가 없어서(cclip 예제는 `stress_output`·`free_output` 을 안 적고,
  squeeze 예제는 응력 모드다) 매트릭스가 전부 통과였다. **예제가 곧 구동기**라는 설계의
  한계다 — 예제가 안 쓰는 옵션은 아무도 안 본다.

  `strip` 은 리눅스에서 우연히 보존됐다(리더가 `\\r` 을 안 뗀다). 그 우연에 기대지 않도록
  여기서 못 박는다 — MSVC 텍스트 모드에서 그 경로는 `\\r\\r\\n` 을 낸다.

usage: test_newline_companion.py <KooRemapper 바이너리>
"""
import os
import subprocess
import sys
import tempfile

FAILS = []

BOARD = ("output: clip_board.k\nlx: 3.0\nly: 1.5\nlz: 0.5\nnx: 6\nny: 3\nnz: 1\n"
         "rho: 8.36e-9\nE: 131000.0\nnu: 0.3\nmid: 2\nsecid: 2\npid: 2\n"
         "part_title: CCLIP_ANT_01\n")
BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\n"
       "rho: 7.85e-9\nE: 210000.0\nnu: 0.3\nmid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")


def check(name, cond, detail=""):
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:250]) if detail else ""))


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr


def write(d, name, text):
    open(os.path.join(d, name), "w", encoding="utf-8").write(text)


def to_crlf(path):
    b = open(path, "rb").read()
    open(path, "wb").write(b.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))


def counts(path):
    b = open(path, "rb").read()
    crlf = b.count(b"\r\n")
    return crlf, b.count(b"\n") - crlf


def assert_crlf(label, path):
    if not os.path.exists(path):
        check("%s 가 생겼다" % label, False, path)
        return
    crlf, lone = counts(path)
    check("%s 가 CRLF 를 지켰다" % label, crlf > 0 and lone == 0,
          "CRLF %d / LF단독 %d" % (crlf, lone))


def test_cclip(binary):
    print("[cclip — stress_output: include 의 dynain, free_output 의 _free.k]")
    d = tempfile.mkdtemp(prefix="nlc_cclip_")
    write(d, "board.yaml", BOARD)
    rc, out = run(binary, d, "generate", "box", "board.yaml")
    check("입력 덱 생성 rc=0", rc == 0, out[-250:])
    board = os.path.join(d, "clip_board.k")
    if not os.path.exists(board):
        check("clip_board.k 가 생겼다", False, out[-250:])
        return
    to_crlf(board)

    # ⚠ 카탈로그 예제가 **안 적는** 두 키를 여기서 켠다 — 그래서 매트릭스가 못 봤다.
    write(d, "cclip.yaml",
          "model: clip_board.k\noutput: out\nmode: analytic\nattach: none\n"
          "stress_output: include\nfree_output: true\n"
          "calibration:\n  point: {deflection: 0.15, force: 1.2}\n  tolerance: 0.05\n"
          "clips:\n  - pid: 2\n    overtravel: 0.15\n")
    rc, out = run(binary, d, "cclip", "cclip.yaml")
    check("cclip rc=0", rc == 0, out[-250:])
    assert_crlf("본 덱 out.k", os.path.join(d, "out.k"))
    assert_crlf("동반 dynain out.dynain", os.path.join(d, "out.dynain"))
    assert_crlf("자유상태 덱 out_free.k", os.path.join(d, "out_free.k"))


def test_squeeze_strain(binary):
    print("[squeeze — strain_mode 의 dynain]")
    d = tempfile.mkdtemp(prefix="nlc_sqz_")
    write(d, "box.yaml", BOX)
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    check("입력 덱 생성 rc=0", rc == 0, out[-250:])
    mesh = os.path.join(d, "box.k")
    if not os.path.exists(mesh):
        check("box.k 가 생겼다", False, out[-250:])
        return
    to_crlf(mesh)

    write(d, "sq.yaml", "strain_mode: true\nparts:\n  - pid: 1\n    eps_x: -0.01\n"
                        "    eps_y: -0.01\n    eps_z: 0.0\n")
    rc, out = run(binary, d, "squeeze", "box.k", "sq.yaml", "sq_out")
    check("squeeze rc=0", rc == 0, out[-250:])
    assert_crlf("메시 덱 sq_out.k", os.path.join(d, "sq_out.k"))
    assert_crlf("동반 dynain sq_out.dynain", os.path.join(d, "sq_out.dynain"))


def test_strip(binary):
    print("[strip — 우연한 보존에 기대지 않는다]")
    d = tempfile.mkdtemp(prefix="nlc_strip_")
    write(d, "box.yaml", BOX)
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    check("입력 덱 생성 rc=0", rc == 0, out[-250:])
    mesh = os.path.join(d, "box.k")
    if not os.path.exists(mesh):
        check("box.k 가 생겼다", False, out[-250:])
        return
    to_crlf(mesh)

    write(d, "st.yaml", 'model: box.k\noutput: stripped.k\nkeywords:\n  - "*NODE"\n'
                        '  - "*ELEMENT_SOLID"\n')
    rc, out = run(binary, d, "strip", "st.yaml")
    check("strip rc=0", rc == 0, out[-250:])
    assert_crlf("stripped.k", os.path.join(d, "stripped.k"))


def main():
    if len(sys.argv) < 2:
        print("usage: test_newline_companion.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2

    test_cclip(binary)
    test_squeeze_strain(binary)
    test_strip(binary)

    print("")
    if FAILS:
        print("FAIL %d" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
