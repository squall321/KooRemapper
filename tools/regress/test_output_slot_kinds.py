#!/usr/bin/env python3
# 산출 자리가 장치(/dev/zero) · 폴더일 때 — 산출을 되읽는 op 이 끝나지 않거나 보고를 조용히 건너뛰지 않는지 보는 회귀 시험(3차 4판 L-19)
"""산출 자리의 꼴 (2026-11-22 · 미룬 결함 3차 4판 L-19 — 회귀가 못 재던 자리).

왜 이 시험이 있나.

  카탈로그 사례의 산출 자리를 /dev/zero 를 가리키는 링크로 바꾸면 squeeze(쓴 덱을 되읽어 고쳐 쓴다) · stackwrap(쓴 `_neutral.k` 를 매핑의
  입력으로 되읽는다)이 /dev/zero 를 끝없이 읽어 시간 한도(60 초)에 걸렸다 — 한도가 없으면 메모리를 끝까지 쓴다(11-08 탐침이 박스 메모리를
  쓴 꼴). 산출 자리를 폴더로 바꾸면 75 자리 가운데 cclip 보고 하나만 rc 0 이었다(못 열면 조용히 건너뛰었다). 회귀는 파일 크기 상한이 큰
  산출 뒤에 걸리지 않아 이 자리를 못 쟀다. 이제 되읽는 자리가 보통 파일이 아니면 쓰기 전에 거절하고, cclip 은 보고를 못 열면 rc 1 이다.
  되읽지 않는 산출은 장치여도 된다 — `/dev/null` 마른 실행(staged_write O-4)은 그대로다.

usage: test_output_slot_kinds.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_deck_bom as T  # noqa: E402

FAILS, OKS = [], []
CASES = (("squeeze", "box_sq.k", "zero", "되읽어"), ("stackwrap", "wrapped_neutral.k", "zero", "되읽으므로"),
         ("cclip", "clip_board_cclip_cclip_report.json", "dir", "보고를 쓸 수 없다"))


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-90s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    top = tempfile.mkdtemp(prefix="kr_slot_kind_")
    try:
        specs = {s["name"]: s for s in T.OPS}
        for op, out, kind, word in CASES:
            case = T.Case(binary, os.path.join(top, op), specs[op])
            shutil.copytree(case.base, case.run)
            p = os.path.join(case.run, out)
            if os.path.lexists(p):
                os.remove(p)
            if kind == "zero":
                os.symlink("/dev/zero", p)
            else:
                os.makedirs(p)
            proc = subprocess.run(["prlimit", "--as=2147483648", "timeout", "60", binary] + case.cmd.split()[1:], cwd=case.run,
                                  capture_output=True)
            text = (proc.stdout + proc.stderr).decode("utf-8", "replace")
            check("%s — %s 가 %s 면 rc 1 · 까닭(끝나지 않거나 조용히 지나가지 않는다)" % (op, out, "/dev/zero" if kind == "zero" else "폴더"),
                  proc.returncode == 1 and word in text, (proc.returncode, text[-300:]))
    finally:
        shutil.rmtree(top, ignore_errors=True)
    print()
    if FAILS:
        print("FAIL — %d 항 실패 / %d" % (len(FAILS), len(FAILS) + len(OKS)))
        for f in FAILS:
            print("  -", f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
