#!/usr/bin/env python3
"""덱의 개행은 왕복에서 보존된다 — CRLF 덱이 조용히 LF 로 바뀌면 안 된다.

왜 이 시험이 있나 (2026-09-24, 덱 편집 계약 요청서 DF-01 / SYS-02):

  CRLF 578개 덱을 indent 로 돌리면 출력이 **CRLF 0 · LF 579** 였다. 700MB 덱에서 −12MB,
  diff 2,433만 줄이 나는데 **노드·요소·파트 카운트는 전부 정상**이라 아무도 알아볼 수 없었다.
  사건표에서 유일하게 "구조 카운트가 전부 정상"인 사건이다.

  ⚠ 요청서는 원인을 `std::ofstream`의 텍스트 모드로 지목했지만 그건 리눅스에서 성립하지 않는다
  (텍스트 모드 ofstream 은 개행을 변환하지 않는다). 진짜 원인은 **리더가 `line.pop_back()` 으로
  CR 을 떼고 그 사실을 기억하지 않는 것**이다. CR 을 떼는 것 자체는 옳다 — 남기면 `stoi`·
  `substr`·`back()` 분기가 전부 오동작한다. 그래서 고침은 "떼지 않기"가 아니라
  **"뗀 개행을 최종 출력에서 되붙이기"** 다.

무엇을 단언하나:
  A. CRLF 덱 → 출력도 CRLF. LF 단독 줄이 **0** 이어야 한다(한 파일 안에 개행이 섞이면 실패).
  B. LF 덱 → 출력도 LF. CRLF 가 **0**. ← 이것이 안전선이다. 되붙임 로직이 틀리면 여기서 깨진다.

usage: test_deck_newline.py <KooRemapper 바이너리>
"""
import os
import subprocess
import sys
import tempfile

FAILS = []

INDENT_YAML = """base_model: {model}
output: {out}
material:
  E: 210000
  nu: 0.3
operations:
  - type: indent
    target_pid: 1
    plane: xy
    direction: -z
    depth: 0.0001
    r1: 0.5
    r2: 1
    bottom_ratio: 0
    stress: false
    shape:
      type: polygon
      points:
        - [3, 3]
        - [7, 3]
        - [7, 7]
        - [3, 7]
"""


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + detail.strip()[:300]) if detail else ""))


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def base_bytes():
    src = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "examples", "indent", "small", "block.k"))
    return open(src, "rb").read()


def counts(path):
    b = open(path, "rb").read()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n")
    return {"bytes": len(b), "crlf": crlf, "lf": lf, "lone_lf": lf - crlf}


def roundtrip(binary, tag, to_crlf):
    d = tempfile.mkdtemp(prefix="nl_%s_" % tag)
    raw = base_bytes().replace(b"\r\n", b"\n")
    if to_crlf:
        raw = raw.replace(b"\n", b"\r\n")
    open(os.path.join(d, "m.k"), "wb").write(raw)
    open(os.path.join(d, "c.yaml"), "w").write(INDENT_YAML.format(model="m.k", out="o"))
    rc, out = run(binary, d, "indent", "c.yaml")
    check("%s: rc=0" % tag, rc == 0, out[-300:])
    op = os.path.join(d, "o.k")
    if not os.path.exists(op):
        check("%s: 출력이 생겼다" % tag, False, out[-300:])
        return None
    return counts(os.path.join(d, "m.k")), counts(op)


def main():
    if len(sys.argv) < 2:
        print("usage: test_deck_newline.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2

    print("[A CRLF 덱은 CRLF 로 나온다]")
    r = roundtrip(binary, "crlf", to_crlf=True)
    if r:
        src, out = r
        check("입력이 정말 CRLF 였다", src["crlf"] > 0 and src["lone_lf"] == 0, str(src))
        check("출력에 CRLF 가 있다", out["crlf"] > 0, str(out))
        # ⚠ 개행이 섞이면 안 된다 — relax 가 원본 줄은 CRLF, 새 줄은 LF 로 내던 형태가 최악이다
        check("출력에 LF 단독 줄이 없다", out["lone_lf"] == 0, str(out))

    print("[B LF 덱은 LF 로 나온다 — 되붙임 로직의 안전선]")
    r = roundtrip(binary, "lf", to_crlf=False)
    if r:
        src, out = r
        check("입력이 정말 LF 였다", src["crlf"] == 0 and src["lf"] > 0, str(src))
        check("출력에 CRLF 가 없다", out["crlf"] == 0, str(out))
        check("출력에 LF 가 있다", out["lf"] > 0, str(out))

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
