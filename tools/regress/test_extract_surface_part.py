#!/usr/bin/env python3
# extract_surface 의 output_pid — 있는 번호는 거절, 새 번호엔 *PART · *SECTION_SHELL(두께 필수)을 짓는지 보는 회귀 시험(3차 2판)
"""extract_surface 의 새 셸 파트 (2026-11-22 · 미룬 결함 3차 2판 · 사용자 결정 「셸 섹션까지 지어 넣는다」 ·
「thickness · --thickness · 새 번호면 필수」).

왜 이 시험이 있나.

  11-22 설치된 판(d1e2ce96)에서 assemble 의 extract_surface 는 새 `output_pid` 에 `*PART` 를 쓰지 않아 셸 50 개가 정의 안 된 파트를
  가리켰고(rc 0), `output_pid` 가 이미 있는 파트(battery 파트 11 · 솔리드 파트 1)면 셸을 그 파트에 rc 0 으로 넣었다. 단독 extract-surface 는
  `*PART` 를 쓰되 SECID 칸에 PID 를, MID 칸에 1 을 박아 정의 안 된 섹션 · 엉뚱한 재질을 가리켰다. 이제 있는 번호면 rc 1 로 아무것도 쓰지
  않고, 새 번호에는 `*PART`(새 SECID · MID 는 셸을 뽑은 솔리드 파트의 것)와 `*SECTION_SHELL`(ELFORM 2 · SHRF 1.0 · NIP 2 · T1~T4 = 두께)을
  짓는다. 두께가 없으면 rc 1. 셸을 뽑은 파트들의 MID 가 서로 다르면 rc 1.

무엇을 보나(상자 — 아래층 PID 1 · MID 1, 위층 PID 2 · MID 2 · SECID 1).
  S  단독 — S-1 기본(PID 1 — 있다) rc 1 · 산출 없음 · S-2 새 번호 · 두께 없음 rc 1 · S-3 `--thickness` 가 0 · 음수 · 글이면 rc 1 ·
     S-4 윗면(PID 2 만) → *PART 10 · SECID 2 · MID 2 · *SECTION_SHELL 2 · 2 · 1.0 · 2 · 0.5 넷 · 셸 PID 10 · S-5 모든 면(MID 1 · 2) rc 1 ·
     S-6 인클루드에만 있는 PID 7 rc 1 · S-7 가운데 면 · S-8 LONG=Y 덱 — 같은 값을 20 칸으로 · S-9 `*PART` 가 없는 메시(generate arc) →
     MID 0 · 경고
  A  assemble — A-1 output_pid 1 rc 1 · A-2 두께 없음 rc 1 · A-3 새 번호 101 → *PART · *SECTION_SHELL · info --strict rc 0 · A-4 output_pid
     없음 → 최대값 위 새 번호 · A-5 모든 면 rc 1 · A-6 가운데 면 · A-7 LONG=Y 덱은 요소를 더하는 assemble op 의 설계된 거절 그대로 ·
     A-8 battery 파트 번호 rc 1 · A-9 `*PART` 가 없는 메시 → MID 0 · 경고

usage: test_extract_surface_part.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "tools", "help"))
import test_long_readers as L  # noqa: E402 — 선언된 폭으로 읽기 · 표준 → LONG
import test_battery_deck_width as B  # noqa: E402 — battery 설정
from ops_help import OPS  # noqa: E402

FAILS, OKS = [], []
BOX = {o["name"]: o for o in OPS}["warpage"]["files"]["box.yaml"]


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-600:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def two_part_box(binary, d, long_=False):
    """상자 100 요소 — 위층(51~100)을 PID 2 · MID 2 로. long_ 이면 LONG=Y 로 다시 쓴다."""
    with open(os.path.join(d, "box.yaml"), "w", encoding="utf-8") as f:
        f.write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    p = os.path.join(d, "box.k")
    with open(p, encoding="utf-8") as f:
        t = f.read()
    out, kw = [], ""
    for line in t.split("\n"):
        if line.startswith("*"):
            kw = line.split()[0].upper()
        elif kw == "*ELEMENT_SOLID" and line.strip() and not line.startswith("$") and int(line[0:8]) > 50:
            line = line[0:8] + "%8d" % 2 + line[16:]
        out.append(line)
    t = "\n".join(out)
    mat = t[t.index("*MAT_ELASTIC"):t.index("*SECTION_SOLID")]
    mat2 = mat.split("\n")
    mat2 = "\n".join(l if l.startswith(("*", "$")) or not l.strip() else "%10d" % 2 + l[10:] for l in mat2)
    t = t.replace("*NODE", mat2 + "*PART\nUPPER\n         2         1         2\n*NODE", 1)
    if long_:
        t = L.to_long(t)
    with open(p, "w", encoding="utf-8") as f:
        f.write(t)


def blocks(text, fw_default=8):
    """[(키워드, 값 줄들)] — 선언된 폭으로(test_long_readers.values)."""
    return L.values(text, inherit=fw_default)


def block(vals, kw):
    return [rows for k, rows in vals if k == kw]


def shell_part_ok(label, text, pid, secid, mid, thick):
    v = blocks(text)
    parts = [r for rows in block(v, "*PART") for r in rows if not (isinstance(r, tuple) and r and r[0] == "T")]
    hit = [r for r in parts if r and r[0] == pid]
    got = tuple(hit[0][1:3]) + (0.0,) * (3 - len(hit[0])) if len(hit) == 1 else None   # 끝의 0 칸은 읽기가 뗀다(MID 0)
    check(label + " — *PART %d · SECID %d · MID %d" % (pid, secid, mid), got == (secid, mid), parts)
    secs = [rows for rows in block(v, "*SECTION_SHELL")]
    ok = False
    for rows in secs:
        if len(rows) >= 2 and rows[0][:4] == (secid, 2, 1.0, 2) and len(rows[1]) == 4 and all(abs(x - thick) < 1e-6 for x in rows[1]):
            ok = True
    check(label + " — *SECTION_SHELL %d · ELFORM 2 · SHRF 1.0 · NIP 2 · T1~T4 %g" % (secid, thick), ok, secs)
    shells = [r for rows in block(v, "*ELEMENT_SHELL") for r in rows]
    check(label + " — 셸 %d 개가 다 PID %d" % (len(shells), pid), shells and all(r[1] == pid for r in shells), shells[:3])


def main():
    binary = os.path.abspath(sys.argv[1])
    top = tempfile.mkdtemp(prefix="kr_espart_")
    try:
        print("[S — 단독 extract-surface]")
        d = os.path.join(top, "s")
        os.makedirs(d)
        two_part_box(binary, d)
        rc, out = run(binary, d, "extract-surface", "box.k", "s1.k", "--face", "top")
        check("S-1 기본 --output-pid 1(있다) → rc 1 · 산출 없음", rc == 1 and not os.path.exists(os.path.join(d, "s1.k"))
              and "이미 있는 파트 번호" in out, out[-300:])
        rc, out = run(binary, d, "extract-surface", "box.k", "s2.k", "--face", "top", "--output-pid", "10")
        check("S-2 새 번호 · 두께 없음 → rc 1 · 산출 없음", rc == 1 and not os.path.exists(os.path.join(d, "s2.k")) and "--thickness" in out,
              out[-300:])
        for bad in ("0", "-1", "abc", "nan"):
            rc, out = run(binary, d, "extract-surface", "box.k", "s3.k", "--face", "top", "--output-pid", "10", "--thickness", bad)
            check("S-3 --thickness %s → rc 1" % bad, rc == 1 and not os.path.exists(os.path.join(d, "s3.k")), out[-200:])
        rc, out = run(binary, d, "extract-surface", "box.k", "s4.k", "--face", "top", "--output-pid", "10", "--thickness", "0.5")
        if check("S-4 윗면 · 새 번호 10 · 두께 0.5 → rc 0", rc == 0, out[-300:]):
            shell_part_ok("S-4", open(os.path.join(d, "s4.k"), encoding="utf-8").read(), 10, 2, 2, 0.5)
        rc, out = run(binary, d, "extract-surface", "box.k", "s5.k", "--face", "all", "--output-pid", "10", "--thickness", "0.5")
        check("S-5 모든 면(PID 1 · 2 — MID 1 · 2) → rc 1 · 산출 없음", rc == 1 and "MID 가 서로 다르다" in out
              and not os.path.exists(os.path.join(d, "s5.k")), out[-300:])
        rc, out = run(binary, d, "extract-surface", "box.k", "s5b.k", "--face", "all", "--pid", "1", "--output-pid", "10",
                      "--thickness", "0.5")
        if check("S-5b --pid 1 의 모든 면 → rc 0 · MID 1", rc == 0, out[-300:]):
            shell_part_ok("S-5b", open(os.path.join(d, "s5b.k"), encoding="utf-8").read(), 10, 2, 1, 0.5)
        with open(os.path.join(d, "inc7.k"), "w", encoding="utf-8") as f:
            f.write("*KEYWORD\n*PART\ninc\n         7         1         1\n*END\n")
        t = open(os.path.join(d, "box.k"), encoding="utf-8").read()
        with open(os.path.join(d, "boxi.k"), "w", encoding="utf-8") as f:
            f.write(t.replace("*END", "*INCLUDE\ninc7.k\n*END"))
        rc, out = run(binary, d, "extract-surface", "boxi.k", "s6.k", "--face", "top", "--output-pid", "7", "--thickness", "0.5")
        check("S-6 인클루드에만 있는 PID 7 → rc 1", rc == 1 and not os.path.exists(os.path.join(d, "s6.k")), out[-300:])
        rc, out = run(binary, d, "extract-surface", "box.k", "s7.k", "--mid-surface", "--pid", "2", "--output-pid", "12",
                      "--thickness", "0.25")
        if check("S-7 가운데 면(--pid 2) → rc 0", rc == 0, out[-300:]):
            shell_part_ok("S-7", open(os.path.join(d, "s7.k"), encoding="utf-8").read(), 12, 2, 2, 0.25)
        dl = os.path.join(top, "sl")
        os.makedirs(dl)
        two_part_box(binary, dl, long_=True)
        rc, out = run(binary, dl, "extract-surface", "box.k", "s8.k", "--face", "top", "--output-pid", "10", "--thickness", "0.5")
        if check("S-8 LONG=Y 덱 → rc 0", rc == 0, out[-300:]):
            t = open(os.path.join(dl, "s8.k"), encoding="utf-8").read()
            check("S-8 — 산출이 LONG=Y 를 밝힌다", L.deck_width(t) == 20, t[:200])
            shell_part_ok("S-8", t, 10, 2, 2, 0.5)

        db = os.path.join(top, "sb")
        os.makedirs(db)
        run(binary, db, "generate", "--dim-i", "20", "--dim-j", "5", "arc", "demo")
        rc, out = run(binary, db, "extract-surface", "demo_bent.k", "s9.k", "--face", "top", "--output-pid", "99", "--thickness", "0.5")
        if check("S-9 *PART 가 없는 메시(generate arc) → rc 0 · MID 0 경고", rc == 0 and "MID 가 없다" in out, out[-300:]):
            shell_part_ok("S-9", open(os.path.join(db, "s9.k"), encoding="utf-8").read(), 99, 1, 0, 0.5)

        print("[A — assemble 의 extract_surface]")

        def asm(name, ops, long_=False, extra_files=None):
            dd = os.path.join(top, name)
            os.makedirs(dd)
            two_part_box(binary, dd, long_)
            for fn, content in (extra_files or {}).items():
                with open(os.path.join(dd, fn), "w", encoding="utf-8") as f:
                    f.write(content)
            with open(os.path.join(dd, "a.yaml"), "w", encoding="utf-8") as f:
                f.write("base_model: box.k\noutput: out\noperations:\n" + ops)
            rc, out = run(binary, dd, "assemble", "a.yaml")
            return dd, rc, out

        es = "  - type: extract_surface\n    face: top\n"
        dd, rc, out = asm("a1", es + "    output_pid: 1\n    thickness: 0.5\n")
        check("A-1 output_pid 1(있다) → rc 1 · 산출 없음", rc != 0 and "이미 있는" in out and not os.path.exists(os.path.join(dd, "out.k")),
              out[-300:])
        dd, rc, out = asm("a2", es + "    output_pid: 101\n")
        check("A-2 두께 없음 → rc 1 · 산출 없음", rc != 0 and "thickness" in out and not os.path.exists(os.path.join(dd, "out.k")), out[-300:])
        dd, rc, out = asm("a3", es + "    output_pid: 101\n    thickness: 0.5\n")
        if check("A-3 새 번호 101 · 두께 0.5 → rc 0", rc == 0, out[-300:]):
            t = open(os.path.join(dd, "out.k"), encoding="utf-8").read()
            shell_part_ok("A-3", t, 101, 2, 2, 0.5)
            rc2, o2 = run(binary, dd, "info", "--strict", "out.k")
            check("A-3 — info --strict rc 0(정의 안 된 파트 · 섹션 · 재질 없음)", rc2 == 0, o2[-300:])
        dd, rc, out = asm("a4", es + "    thickness: 0.5\n")
        if check("A-4 output_pid 없음 → rc 0", rc == 0, out[-300:]):
            shell_part_ok("A-4", open(os.path.join(dd, "out.k"), encoding="utf-8").read(), 3, 2, 2, 0.5)
        dd, rc, out = asm("a5", "  - type: extract_surface\n    face: all\n    output_pid: 101\n    thickness: 0.5\n")
        check("A-5 모든 면(MID 1 · 2) → rc 1", rc != 0 and "MID 가 서로 다르다" in out, out[-300:])
        dd, rc, out = asm("a6", "  - type: extract_surface\n    target_pid: 2\n    mid_surface: true\n    output_pid: 101\n    thickness: 0.25\n")
        if check("A-6 가운데 면(target_pid 2) → rc 0", rc == 0, out[-300:]):
            shell_part_ok("A-6", open(os.path.join(dd, "out.k"), encoding="utf-8").read(), 101, 2, 2, 0.25)
        dd, rc, out = asm("a7", es + "    output_pid: 101\n    thickness: 0.5\n", long_=True)
        check("A-7 LONG=Y 덱 → 설계된 거절(요소를 더하는 assemble op — 20 칸 서식을 확정하지 못했다) · 산출 없음",
              rc != 0 and "20 칸 서식" in out and not os.path.exists(os.path.join(dd, "out.k")), out[-300:])
        bat = B.battery_yaml("stacked", {"mode": "dent"})
        dd, rc, out = asm("a8", "  - type: battery\n    config: bat.yaml\n" + es + "    output_pid: 11\n    thickness: 0.5\n",
                          extra_files={"bat.yaml": bat})
        check("A-8 battery 파트 번호 11 → rc 1", rc != 0 and "이미 있는" in out, out[-300:])
        dd = os.path.join(top, "a9")
        os.makedirs(dd)
        run(binary, dd, "generate", "--dim-i", "20", "--dim-j", "5", "arc", "demo")
        with open(os.path.join(dd, "a.yaml"), "w", encoding="utf-8") as f:
            f.write("base_model: demo_bent.k\noutput: out\noperations:\n" + es + "    thickness: 0.5\n")
        rc, out = run(binary, dd, "assemble", "a.yaml")
        if check("A-9 *PART 가 없는 메시 → rc 0 · MID 0 경고", rc == 0 and "MID 가 없다" in out, out[-300:]):
            shell_part_ok("A-9", open(os.path.join(dd, "out.k"), encoding="utf-8").read(), 2, 1, 0, 0.5)
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
