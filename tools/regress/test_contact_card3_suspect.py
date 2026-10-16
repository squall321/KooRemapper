#!/usr/bin/env python3
"""접촉의 Card 3 자리에 선택 카드 Card A 가 **밀려 올라온** 손상을 `info` 가 의심으로 말하는가.

왜 이 시험이 있나 (2026-10-16, 장부 P1-6 「남은 한계 — Card 3 가 Card A 로 치환된 손상」).

  옛 `contact modify` 가 필수 Card 3 을 지우며 선택 카드를 다시 썼다(P1-4 가 그 쓰기를 고쳤다). 그렇게
  망가진 덱은 **줄 수가 그대로라** 「필수 카드 3장」 규칙이 못 잡고, LS-DYNA 는 Card A 의 값(SOFT·DEPTH…)을
  Card 3(SFS·SFM…)으로 읽는다. 문법 오류가 안 나므로(정수 꼴도 실수 칸에서 받는다) **표기**가 유일한 실마리다.

  신호 — Card A 의 **정수 칸 자리**(1 SOFT · 3 LCIDAB · 6 DEPTH · 7 BSORT · 8 FRCFRQ)에 0 아닌 정수 표기.
  실측(2026-10-16) — 실사용 덱의 접촉 93,435개에서 오탐 **0**(걸린 6개는 전부 `*PARAMETER` 참조 줄이라
  건너뛴다) · 리포 덱 106개도 0. 사람이 SFS 를 `2` 로 쓸 수도 있으므로 **단정하지 않는다** — 경고만 한다.

무엇을 보나.
  A 정수만 있는 Card A → 의심 1
  B ★실제 꼴의 Card A(SOFSCL `0.1`·MAXPAR `1.025` 처럼 실수 칸은 소수점) → 의심 1
     (첫 판은 「줄 전체에 소수점이 없다」를 봐서 이것을 **놓쳤다**)
  C 정상 Card 3 — 소수점 표기 · 「정수 0 뿐」 · 빈 줄 → 조용하다
  D `*PARAMETER` 참조 줄은 건너뛴다
  E 의심은 **rc·`--strict` 와 무관**하다(단정이 아니다)
  F 플랫폼 파서(`kfile_inspect._parse_ref_dangling`)가 의심 줄을 미정의 참조로 **집어 가지 않는다**
  G 리포의 추적 덱 전수에서 의심 0(오탐 표면)

usage: test_contact_card3_suspect.py <KooRemapper 바이너리>
"""
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


DECK = """*KEYWORD
*SET_PART_LIST
         1
         1
*SET_PART_LIST
         2
         2
*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID
         1shift_test
         1         2         2         2         0         0         0         0
       0.2       0.2       0.0       0.0       0.0         0       0.0    1.0E20
%s
*END
"""

CASES = [
    ("A 정수만 있는 Card A", "         2         0         0         0         1         5        10         1", 1),
    ("B 실제 꼴의 Card A", "         2       0.1         0     1.025       2.0         5        10         1", 1),
    ("C1 소수점 표기 Card 3", "       1.0       1.0       0.0       0.0       1.0       1.0       1.0       1.0", 0),
    ("C2 「정수 0 뿐」 Card 3", "         0         0         0         0         0         0         0         0", 0),
    ("C3 빈 줄 Card 3", "", 0),
    ("D *PARAMETER 참조 줄", "&SFS            1.0       0.0       0.0       1.0       1.0       1.0         5", 0),
]


def info(binary, path, strict=False):
    argv = [binary, "info", path] + (["--strict"] if strict else [])
    r = subprocess.run(argv, capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace")
    out = r.stdout + r.stderr
    return r.returncode, out, [l for l in out.splitlines() if l.startswith("  의심 line")]


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="c3s_")
    try:
        print("[A~D 합성 덱]")
        for label, card3, want in CASES:
            p = os.path.join(d, "x.k")
            body = DECK % card3
            if label.startswith("D"):
                body = body.replace("*KEYWORD\n", "*KEYWORD\n*PARAMETER\nRSFS     1.0\n", 1)
            open(p, "w", encoding="utf-8").write(body)
            rc, out, sus = info(binary, p)
            check("%s — 의심 %d" % (label, want), len(sus) == want, sus or out[-200:])
            if label.startswith("A"):
                rc_s, out_s, _ = info(binary, p, strict=True)
                check("E 의심만 있으면 --strict 도 rc 0", rc_s == 0, out_s[-200:])
                sys.path.insert(0, os.path.join(REPO, "platform", "backend"))
                try:
                    from app.runner.kfile_inspect import _parse_ref_dangling
                except Exception as exc:                         # noqa: BLE001
                    check("F 플랫폼 파서를 불러온다", False, exc)
                else:
                    check("F 플랫폼 파서가 의심 줄을 집어 가지 않는다", _parse_ref_dangling(out) is None,
                          _parse_ref_dangling(out))

        print("[G 리포 추적 덱 전수 — 오탐 표면]")
        files = subprocess.run(["git", "ls-files", "*.k", "*.key", "*.dyn"], cwd=REPO, capture_output=True,
                               text=True).stdout.split()
        with_contact = []
        for f in files:
            p = os.path.join(REPO, f)
            try:
                if any(l.startswith("*CONTACT_") for l in open(p, encoding="utf-8", errors="replace")):
                    with_contact.append(p)
            except OSError:
                pass
        hits = []
        for p in with_contact:
            _rc, _out, sus = info(binary, p)
            if sus:
                hits.append((os.path.relpath(p, REPO), sus[0][:100]))
        check("G 접촉이 있는 추적 덱을 찾았다(%d 장)" % len(with_contact), len(with_contact) >= 10, len(with_contact))
        check("G 그 전수에서 의심 0", not hits, hits[:3])
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
