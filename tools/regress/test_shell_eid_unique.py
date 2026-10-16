#!/usr/bin/env python3
# 새 셸·TSHELL 의 EID 가 덱의 다른 요소 EID 와 겹치지 않는지 보는 회귀 시험
"""새 셸(·TSHELL) 요소의 EID 가 **덱의 다른 요소 EID 와 겹치지 않는가.**

왜 이 시험이 있나 (2026-10-16).

  `extract_surface` · `offset`(element_type: shell · tshell)은 셸 EID 를 `maxShellElementId_` 로 냈는데 그 커서는
  덱에서 **한 번도 채워지지 않아** 0 에서 시작했다. 재현 —
    · `block_2x2x1.k` 에 extract_surface → `*ELEMENT_SOLID 1..4` 와 `*ELEMENT_SHELL 1..4` 가 **같은 번호**(rc 0)
    · 덱에 셸 EID 1 이 이미 있으면 새 셸도 EID 1 — **같은 `*ELEMENT_SHELL` 안의 중복**(해석 여지 없는 불법)
    · 커밋된 예제 `examples/offset/03_tshell_result.k`·`04_shell_result.k` — 솔리드 1..600 과 셸 1..580 이 580개 겹친다
  매뉴얼은 셸 EID 를 「다른 요소들과 겹치지 않는 번호」로 요구한다(Vol_I 162384 *ELEMENT_SHELL 「Chose a unique
  number with respect to other elements」). 그래서 셸도 요소 공용 커서(`maxElementId_`)로 낸다 — restack·refine 이
  이미 그렇게 셸을 낸다. 이 꼴은 「셸·솔리드 번호 공유가 되는가」의 어느 해석에서도 합법이다.
  (솔버로 재려 했으나 2026-10-16 LS-DYNA 라이선스가 만료돼 있었다 — 매뉴얼 문구가 기준이다.)

무엇을 보나 — 산출 덱의 `*ELEMENT_SOLID`·`*ELEMENT_SHELL`·`*ELEMENT_TSHELL` EID 가 전부 서로 다르다.
  A extract_surface(top) · B 덱에 셸이 이미 있다 · C mid_surface(짝 없는 면은 번호를 돌려준다)
  D offset shell · E offset tshell · F 한 실행에서 extract_surface 뒤에 refine(새 솔리드)

usage: test_shell_eid_unique.py <KooRemapper 바이너리>
"""
import collections
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples")
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail)[:300]))
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def element_eids(path):
    """종류 → EID 목록. 요소 카드는 한 줄 꼴만 쓴다(이 시험의 덱이 그렇다)."""
    out = collections.defaultdict(list)
    kw = None
    for l in open(path, encoding="utf-8", errors="replace").read().splitlines():
        if l.startswith("*"):
            kw = l.split()[0].upper().rstrip("%+-")
            continue
        if kw in ("*ELEMENT_SOLID", "*ELEMENT_SHELL", "*ELEMENT_TSHELL") and l.strip() and not l.startswith("$"):
            out[kw].append(int(re.match(r"\s*(\d+)", l).group(1)))
    return out


def run_case(binary, label, deck_src, yaml, extra=(), patch=None, want_kw=("*ELEMENT_SHELL",)):
    print("[%s]" % label)
    d = tempfile.mkdtemp(prefix="seu_")
    try:
        body = open(deck_src, encoding="utf-8").read()
        if patch:
            body = patch(body)
        open(os.path.join(d, "deck.k"), "w", encoding="utf-8").write(body)
        for f in extra:
            shutil.copy2(f, d)
        open(os.path.join(d, "c.yaml"), "w", encoding="utf-8").write(yaml)
        r = subprocess.run([binary, "assemble", "c.yaml"], cwd=d, capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
        out = os.path.join(d, "out.k")
        if not check("%s — rc 0" % label, r.returncode == 0 and os.path.exists(out), (r.stdout + r.stderr)[-300:]):
            return
        before = element_eids(os.path.join(d, "deck.k"))
        after = element_eids(out)
        new = sum(len(after[k]) - len(before.get(k, [])) for k in want_kw)
        check("%s — 새 요소를 냈다(%d)" % (label, new), new > 0, {k: len(v) for k, v in after.items()})
        c = collections.Counter(e for v in after.values() for e in v)
        dup = sorted(e for e, n in c.items() if n > 1)
        check("%s — 모든 요소 EID 가 서로 다르다" % label, not dup, "겹친 EID %d개: %s" % (len(dup), dup[:8]))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    block = os.path.join(EX, "iga", "block_2x2x1.k")
    arc = os.path.join(EX, "arc30", "arc30_flat.k")
    ex_surf = ("base_model: deck.k\noutput: out\noperations:\n  - type: extract_surface\n    target_pid: 2\n"
               "    face: top\n    output_pid: 101\n")
    run_case(binary, "A extract_surface(top)", block, ex_surf)

    def add_shell(body):
        # 솔리드 EID 를 101.. 로 옮겨 **입력에는 겹침이 없게** 한다 — 셸 EID 1 이 솔리드 1 과 겹치면 픽스처가
        # 처음부터 불법이다(첫 판이 그랬다). 옛 커서는 셸을 1 부터 내 이 셸과 **같은 `*ELEMENT_SHELL` 안에서** 겹친다.
        lines, kw = body.splitlines(), None
        for k, l in enumerate(lines):
            if l.startswith("*"):
                kw = l.split()[0].upper()
            elif kw == "*ELEMENT_SOLID" and l.strip() and not l.startswith("$"):
                lines[k] = "%8d" % (int(l[:8]) + 100) + l[8:]
        body = "\n".join(lines) + "\n"
        i = body.upper().rfind("*END")
        return body[:i] + ("*SECTION_SHELL\n         9         2       1.0         2\n"
                           "       1.0       1.0       1.0       1.0\n*PART\nextra shell\n         9         9         1\n"
                           "*ELEMENT_SHELL\n       1       9       1       2       3       4\n") + body[i:]
    run_case(binary, "B 덱에 셸이 이미 있다", block, ex_surf, patch=add_shell)
    run_case(binary, "C mid_surface", block,
             "base_model: deck.k\noutput: out\noperations:\n  - type: extract_surface\n    target_pid: 2\n"
             "    mid_surface: true\n    output_pid: 102\n")
    offset = ("base_model: deck.k\noutput: out\noperations:\n  - type: offset\n    source_pid: 1\n"
              "    element_type: %s\n    thickness: 1.5\n    shell_thickness: 1.5\n    num_layers: 1\n"
              "    offset_direction: +z\n    new_pid: 10\n    part_title: \"Offset\"\n    material_card: |\n"
              "      *MAT_ELASTIC\n      $#     mid        ro         e        pr\n"
              "           @MID@       2.0     12000      0.25\n")
    run_case(binary, "D offset shell", arc, offset % "shell")
    run_case(binary, "E offset tshell", arc, offset % "tshell", want_kw=("*ELEMENT_SHELL", "*ELEMENT_TSHELL"))
    run_case(binary, "F extract_surface 뒤에 refine", block,
             ex_surf + "  - type: refine\n    target_pid: 1\n    ratio: 2\n",
             want_kw=("*ELEMENT_SHELL", "*ELEMENT_SOLID"))

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
