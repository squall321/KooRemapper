#!/usr/bin/env python3
"""`cclip` 이 새 SECID 를 **인클루드 닫힘 전부**의 번호 위로 내는가.

왜 이 시험이 있나 (2026-10-16).

  `cclip` 은 새 SECID·MID·SET·CNRB 번호가 인클루드의 번호와 겹치지 않게 「충돌 검사 코퍼스」를
  모은다(`cc_collectScanLines`). 그런데 따로 읽었고 셋이 틀렸다. 재현 — 둘 다 새 SECID 를 인클루드에
  이미 있는 것과 **같은 3** 으로 냈다(같은 종류의 SECID 가 둘이면 LS-DYNA 가 키워드 단계에서 멈춘다).
    · 한 `*INCLUDE` 카드의 **첫 이름만** 읽었다 — 매뉴얼은 이름 카드를 여러 장 받는다(Vol_I 179253)
    · 하위 폴더 이름(`sub/x.k`)을 덱 폴더가 아니라 **작업 폴더** 기준으로 풀었다
    · 한 단계만 따라갔고, `*INCLUDE_TRANSFORM` 파일을 오프셋 없이 코퍼스에 넣었다
  지금은 정본(`include_closure`)으로 읽는다.

무엇을 보나(예제 덱 `clip_board.k` 의 SECID 최대 2 → 기준 새 SECID 3).
  A 인클루드 없음 — 3 그대로
  B 한 카드에 이름 둘, 둘째에 SECID 3 → 4
  C 하위 폴더 이름에 SECID 3, **작업 폴더가 덱 폴더가 아닐 때** → 4, 「열지 못함」 0
  D 중첩(a.k → b.k)의 SECID 3 → 4
  E `*INCLUDE_TRANSFORM` → 따라가지 않았다고 경고

usage: test_cclip_include_ids.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples", "cclip")
FAILS, OKS = [], []

SEC3 = ("*KEYWORD\n*SECTION_SHELL\n         3         2       1.0         2       1.0\n"
        "       1.0       1.0       1.0       1.0\n*END\n")


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail)[:300]))
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def first_sec(path):
    L = open(path, encoding="utf-8").read().splitlines()
    for i, l in enumerate(L):
        if l.strip().upper().startswith("*SECTION_SHELL"):
            j = i + 1
            while L[j].lstrip().startswith("$"):
                j += 1
            return int(L[j][:10])
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    base = tempfile.mkdtemp(prefix="cci_base_")
    try:
        shutil.copy2(os.path.join(EX, "gen_board.yaml"), base)
        subprocess.run([binary, "generate", "box", "gen_board.yaml"], cwd=base, capture_output=True,
                       timeout=120)
        board = open(os.path.join(base, "clip_board.k"), encoding="utf-8").read().splitlines()
        yaml = open(os.path.join(EX, "cclip.yaml"), encoding="utf-8").read()
    finally:
        shutil.rmtree(base, ignore_errors=True)
    end = next(i for i, l in enumerate(board) if l.strip().upper() == "*END")

    cases = [
        ("A 인클루드 없음", [], {}, None, 3),
        ("B 한 카드에 이름 둘", ["*INCLUDE", "first.k", "second.k"],
         {"first.k": "*KEYWORD\n*END\n", "second.k": SEC3}, None, 4),
        ("C 하위 폴더 · 작업 폴더가 다르다", ["*INCLUDE", "sub/x.k"], {"sub/x.k": SEC3}, "/", 4),
        ("D 중첩", ["*INCLUDE", "a.k"], {"a.k": "*KEYWORD\n*INCLUDE\nb.k\n*END\n", "b.k": SEC3}, None, 4),
        ("E *INCLUDE_TRANSFORM", ["*INCLUDE_TRANSFORM", "t.k", "         0         0         0"],
         {"t.k": SEC3}, None, None),
    ]
    for label, extra, files, cwd, want in cases:
        print("[%s]" % label)
        d = tempfile.mkdtemp(prefix="cci_")
        try:
            open(os.path.join(d, "deck.k"), "w", encoding="utf-8").write(
                "\n".join(board[:end] + extra + board[end:]) + "\n")
            for name, body in files.items():
                p = os.path.join(d, name)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, "w", encoding="utf-8").write(body)
            y = yaml.replace("model: clip_board.k", "model: deck.k").replace(
                "output: clip_board_cclip", "output: out")
            open(os.path.join(d, "c.yaml"), "w", encoding="utf-8").write(y)
            r = subprocess.run([binary, "cclip", os.path.join(d, "c.yaml")], cwd=cwd or d,
                               capture_output=True, text=True, timeout=300, encoding="utf-8",
                               errors="replace")
            out = r.stdout + r.stderr
            if not check("%s — rc 0" % label, r.returncode == 0, out[-300:]):
                continue
            sec = first_sec(os.path.join(d, "out.k"))
            if want is not None:
                check("%s — 새 SECID %d" % (label, want), sec == want, sec)
            if label.startswith("C"):
                check("C 「열지 못함」이 없다", "열지 못했" not in out, out[-300:])
            if label.startswith("E"):
                check("E 따라가지 않았다고 경고한다", "따라가지 않았다" in out and "INCLUDE_TRANSFORM" in out,
                      out[-300:])
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
