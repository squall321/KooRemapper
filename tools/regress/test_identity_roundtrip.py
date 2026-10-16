#!/usr/bin/env python3
"""무편집 진입점(`assemble` 의 `type: identity`)이 덱을 **바이트 그대로** 내는가 — 픽스처 5종.

왜 이 시험이 있나 (2026-10-16, plan2 P1-1 ③ · 장부 P1-2 「무편집 진입점」).

  plan2 가 요구했다 — "무편집 진입점 출력이 입력과 sha256 동일. 진입점은 `cat` 복사가 아니라 각 op 의
  read→write 를 태운다". 그런 진입점이 **없었다**(`assemble` 은 연산이 없으면 거절한다 — 오타 난 설정이
  복사본을 내지 않게 지키는 그 거절은 그대로 둔다). 그래서 명시적인 연산 `identity` 를 더했다 —
  `ModelAssembler` 의 읽기(`loadBaseModel`)→쓰기(`writeOutput`)를 아무 편집 없이 지난다. 대부분의 yaml
  op 이 이 길을 쓴다.

  ★만들자마자 결함 하나가 드러났다 — **말미 개행이 없던 덱에 개행이 하나 생겼다.** 리더(`getline`)는
  마지막 줄에 개행이 있었는지를 잃고 쓰는 쪽은 줄마다 `\\n` 을 붙인다. LS-DYNA 는 상관없지만 sha256
  계보·3자 대조가 깨진다. CR 을 기억했다 되붙이는 것과 같은 규율로, 말미 개행도 기억했다 따르게 고쳤다.

픽스처 5종(plan2 P1-1 이 정한 그대로).
  F1 LF · F2 CRLF · F3 무-말미개행 — `examples/contact/model.k`
  F4 `*KEYWORD I10=Y LONG=S` — `examples/load/mesh.k`(i10) 의 머리를 바꿨다. 읽기 폭은 10이다
     (`LONG=S` 는 「표준을 읽고 long 으로 쓴다」라 읽기 폭을 바꾸지 않는다 — Vol_I 19308)
  F5 2줄 요소 카드 — `examples/mesh/tetramesh.k`(WB-LSDYNA 산출 실덱, 요소 카드가 두 줄)

무엇을 보나.
  ① 산출이 입력과 **sha256 동일**(5종 전부)
  ② 같은 덱의 CRLF 판 산출을 개행 치환하면 LF 판 산출과 같다(F4 · F5 로도 — 칸 폭·2줄 카드와 개행이
     섞일 때도 내용이 개행에 따라 갈리지 않는다)
  ③ 연산 없는 설정은 **여전히 거절**한다 — 무편집 진입점은 명시해야만 탄다

usage: test_identity_roundtrip.py <KooRemapper 바이너리>
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail)[:300]))
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def sha(b):
    return hashlib.sha256(b).hexdigest()


def fixtures():
    lf = open(os.path.join(REPO, "examples", "contact", "model.k"), "rb").read().replace(b"\r\n", b"\n")
    i10 = open(os.path.join(REPO, "examples", "load", "mesh.k"), "rb").read().replace(b"\r\n", b"\n")
    assert b"*KEYWORD i10=y" in i10, "i10 픽스처 원본이 바뀌었다 — 이 시험을 다른 i10 덱으로 옮겨라"
    two = open(os.path.join(REPO, "examples", "mesh", "tetramesh.k"), "rb").read().replace(b"\r\n", b"\n")
    return [
        ("F1 LF", lf),
        ("F2 CRLF", lf.replace(b"\n", b"\r\n")),
        ("F3 무-말미개행", lf.rstrip(b"\n")),
        ("F4 I10=Y LONG=S", i10.replace(b"*KEYWORD i10=y", b"*KEYWORD I10=Y LONG=S", 1)),
        ("F5 2줄 요소 카드", two),
    ]


def identity(binary, d, name, body):
    open(os.path.join(d, name + ".k"), "wb").write(body)
    open(os.path.join(d, name + ".yaml"), "w", encoding="utf-8").write(
        "base_model: %s.k\noutput: %s_out\noperations:\n  - type: identity\n" % (name, name))
    r = subprocess.run([binary, "assemble", name + ".yaml"], cwd=d, capture_output=True, text=True,
                       timeout=300, encoding="utf-8", errors="replace")
    p = os.path.join(d, name + "_out.k")
    return r.returncode, (open(p, "rb").read() if os.path.exists(p) else None), r.stdout + r.stderr


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="idrt_")
    try:
        print("[① 산출 = 입력 (sha256)]")
        for k, (label, body) in enumerate(fixtures(), 1):
            rc, out, log = identity(binary, d, "f%d" % k, body)
            if not check("%s — rc 0" % label, rc == 0 and out is not None, log[-300:]):
                continue
            same = out == body
            detail = ""
            if not same:
                detail = "바이트 %d → %d · 말미 개행 %s → %s · CRLF %d → %d" % (
                    len(body), len(out), body.endswith(b"\n"), out.endswith(b"\n"),
                    body.count(b"\r\n"), out.count(b"\r\n"))
            check("%s — sha256 동일" % label, same, detail)

        print("[② CRLF 판 산출 = LF 판 산출의 개행 치환]")
        for k, (label, body) in enumerate(fixtures(), 1):
            if label.startswith(("F2", "F3")):
                continue                      # F1 이 LF 판이고 F2 가 그 CRLF 판이다 — 아래에서 함께 본다
            lf = body.replace(b"\r\n", b"\n")
            rc1, o1, _ = identity(binary, d, "lf%d" % k, lf)
            rc2, o2, _ = identity(binary, d, "cr%d" % k, lf.replace(b"\n", b"\r\n"))
            ok = rc1 == 0 and rc2 == 0 and o1 is not None and o2 is not None
            check("%s — CRLF 판 = LF 판(개행 치환)" % label,
                  ok and sha(o2.replace(b"\r\n", b"\n")) == sha(o1) and o2.count(b"\r\n") == o1.count(b"\n"),
                  "" if ok else "rc %s/%s" % (rc1, rc2))

        print("[③ 연산 없는 설정은 여전히 거절]")
        open(os.path.join(d, "empty.yaml"), "w", encoding="utf-8").write(
            "base_model: f1.k\noutput: e_out\noperations: []\n")
        r = subprocess.run([binary, "assemble", "empty.yaml"], cwd=d, capture_output=True, text=True,
                           timeout=60, encoding="utf-8", errors="replace")
        check("③ 연산이 없으면 rc≠0 · 산출 없음",
              r.returncode != 0 and not os.path.exists(os.path.join(d, "e_out.k")), r.returncode)
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
