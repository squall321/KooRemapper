#!/usr/bin/env python3
# 공용 SECID 번호 커서가 한 키워드 아래 쌓인 둘째 섹션 카드의 SECID 까지 세는지 — 새 섹션을 내는 op 이 그 번호를 다시 내지 않는지 보는 회귀 시험
"""공용 SECID 커서(`maxSectionId_` · `idMaxima().section`)와 쌓인 섹션 카드.

왜 이 시험이 있나 (2026-11-07 밤).

  번호 커서는 `*SECTION_*` 블록마다 **첫 카드**의 SECID 만 읽었다. 한 키워드 아래 쌓인 둘째 카드(`*SECTION_SOLID` 밑에 카드 둘)의
  SECID 를 몰라, 새 섹션을 내는 op(offset · restack · merge …)이 그 번호를 **다시** 냈다 — rc 0 · 같은 SECID 둘(LS-DYNA 는 둘째
  정의에서 멈춘다). 이월 적용의 적대적 검토(11-07 #1)가 같은 틈을 찾았고, 사용자가 공용 커서도 이번 판에 고치기로 했다(셋째 묶음).
  커서는 이제 섹션 블록을 카드 묶음으로 갈라 센다(11-08 · StepForge 591d5b5 와 같은 규칙 — SOLID · SHELL · TSHELL 은 쌓인 묶음까지
  정확히 · 줄 수를 모르는 꼴은 행마다 넉넉히). 11-07 밤 판은 모든 행을 세어 제목 · 두께 · 각도의 숫자로 부풀었다. 있나 · 종류를 보는 표는
  첫 카드 그대로다.

신탁(이 시험이 따로 잰다).
  · 산출 덱의 섹션 블록마다 데이터 줄 첫 칸을 세어 같은 SECID 가 두 번 정의됐는지 본다(쌓인 카드는 이 시험이 지은 꼴이라 자리를 안다)

무엇을 보나.
  A offset(새 솔리드 층 · 새 섹션) — 쌓인 둘째 카드의 SECID 2 를 다시 내지 않는다
  B id_floor — pid_start 가 쌓인 카드의 SECID 위다
  C 커서는 카드 묶음으로 센다 — 숫자 제목은 SECID 가 아니고(예전 2025) · 실수 꼴 SECID(2.0)는 옛 첫 카드 셈처럼 센다(11-08)

usage: test_section_cursor_stacked.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

FAILS, OKS = [], []

BOX = """output: box.k
lx: 20.0
ly: 10.0
lz: 2.0
nx: 4
ny: 2
nz: 1
rho: 7.85e-9
E: 210000.0
nu: 0.3
mid: 1
secid: 1
pid: 1
part_title: PLATE
"""

OFFSET = """base_model: box.k
output: out
operations:
  - type: offset
    source_pid: 1
    element_type: solid
    thickness: 1.0
    num_layers: 1
    offset_direction: +z
    connection_mode: tied
    new_pid: 10
    material_card: |
      *MAT_ELASTIC
           @MID@  7.85E-09  2.10E+05       0.3
"""


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:500]))
    print("  %-70s %s" % (name[:70], "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def stacked_box(binary, d):
    """generate box 덱의 `*SECTION_SOLID` 밑에 둘째 카드(SECID 2 · 아무 파트도 안 쓴다)를 쌓는다."""
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    assert rc == 0, out[-400:]
    p = os.path.join(d, "box.k")
    L = open(p, encoding="utf-8").read().split("\n")
    i = next(k for k, l in enumerate(L) if l.strip().upper().startswith("*SECTION_SOLID"))
    j = next(k for k in range(i + 1, len(L)) if L[k].strip() and not L[k].lstrip().startswith("$"))
    assert int(L[j][:10]) == 1, L[j]
    L.insert(j + 1, "%10d%10s" % (2, L[j][10:20].strip() or "1"))
    open(p, "w", encoding="utf-8").write("\n".join(L))


def section_defs(path):
    """섹션 블록의 데이터 줄 첫 칸 SECID → 정의 수(블록의 카드마다 · `_TITLE` 제목 줄은 뺀다)."""
    out = {}
    L = open(path, encoding="utf-8").read().split("\n")
    i = 0
    while i < len(L):
        u = L[i].strip().upper()
        if u.startswith("*SECTION_"):
            title = "_TITLE" in u
            j = i + 1
            first = True
            while j < len(L) and not L[j].lstrip().startswith("*"):
                s = L[j]
                if s.strip() and not s.lstrip().startswith("$"):
                    if title and first:
                        first = False
                    else:
                        first = False
                        try:
                            v = int(s[:10])
                            out[v] = out.get(v, 0) + 1
                        except ValueError:
                            pass
                j += 1
            i = j
            continue
        i += 1
    return out


def box_with(binary, d, edit):
    """generate box 덱을 짓고 줄 목록을 `edit` 로 고친다(끝 줄은 *END)."""
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    assert rc == 0, out[-400:]
    p = os.path.join(d, "box.k")
    L = open(p, encoding="utf-8").read().rstrip("\n").split("\n")
    assert L[-1].strip().upper() == "*END", L[-1]
    open(p, "w", encoding="utf-8").write("\n".join(edit(L)) + "\n")


def retitle(L, title):
    """`*SECTION_SOLID` 를 `*SECTION_SOLID_TITLE` 로 — 제목 줄 하나를 키워드 바로 밑에."""
    i = next(k for k, l in enumerate(L) if l.strip().upper() == "*SECTION_SOLID")
    return L[:i] + ["*SECTION_SOLID_TITLE", title] + L[i + 1:]


def part_secid(path, pid):
    """`*PART` 블록에서 PID 의 SECID(제목 · 카드 짝)."""
    L = open(path, encoding="utf-8").read().split("\n")
    for i, l in enumerate(L):
        if l.strip().upper().startswith("*PART"):
            data = []
            for m in L[i + 1:]:
                if m.lstrip().startswith("*"):
                    break
                if m.strip() and not m.lstrip().startswith("$"):
                    data.append(m)
            for k in range(0, len(data) - 1, 2):
                c = data[k + 1]
                try:
                    if int(c[:10]) == pid:
                        return int(c[10:20])
                except ValueError:
                    pass
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    tmp = tempfile.mkdtemp(prefix="secur_")
    try:
        print("[A offset — 새 섹션이 쌓인 카드의 SECID 를 다시 내지 않는다]")
        d = os.path.join(tmp, "a")
        os.makedirs(d)
        stacked_box(binary, d)
        open(os.path.join(d, "off.yaml"), "w").write(OFFSET)
        rc, out = run(binary, d, "offset", "off.yaml")
        defs = section_defs(os.path.join(d, "out.k")) if rc == 0 else {}
        check("A-1 offset rc 0 · 쌓인 카드 SECID 2 가 한 번만 정의됐다(새 섹션은 그 위 번호)",
              rc == 0 and defs.get(2) == 1 and max(defs) >= 3, (rc, defs, out[-400:]))
        print("[B id_floor — 바닥이 쌓인 카드의 SECID 위다]")
        d = os.path.join(tmp, "b")
        os.makedirs(d)
        stacked_box(binary, d)
        open(os.path.join(d, "fl.yaml"), "w").write("model: box.k\noutput: floor.json\n")
        rc, out = run(binary, d, "id_floor", "fl.yaml")
        fl = json.load(open(os.path.join(d, "floor.json"), encoding="utf-8")) if rc == 0 else {}
        check("B-1 id_floor pid_start 3(PID · MID 1 · 쌓인 SECID 2 위 — 예전 2)", fl.get("pid_start") == 3, (rc, fl, out[-300:]))

        print("[C 커서는 제목 · 두께로 부풀지 않고 옛 첫 카드 셈 밑으로 내려가지 않는다(적대적 검토 11-08 #2)]")
        # C-1 섹션 제목이 숫자(2024) — 예전 「모든 행」 셈은 그것을 SECID 로 세어 새 섹션이 2025 가 되었다
        d = os.path.join(tmp, "c1")
        os.makedirs(d)
        box_with(binary, d, lambda L: retitle(L, "2024"))
        open(os.path.join(d, "off.yaml"), "w").write(OFFSET)
        rc, out = run(binary, d, "offset", "off.yaml")
        sec = part_secid(os.path.join(d, "out.k"), 10) if rc == 0 else None
        check("C-1 섹션 제목 2024 — offset 의 새 섹션은 SECID 2(제목은 SECID 가 아니다 · 예전 2025)", sec == 2, (rc, sec, out[-300:]))
        open(os.path.join(d, "fl.yaml"), "w").write("model: box.k\noutput: floor.json\n")
        rc, out = run(binary, d, "id_floor", "fl.yaml")
        fl = json.load(open(os.path.join(d, "floor.json"), encoding="utf-8")) if rc == 0 else {}
        check("C-1b id_floor pid_start 2(예전 2025)", fl.get("pid_start") == 2, (rc, fl, out[-300:]))
        # C-2 SECID 를 실수 꼴(2.0)로 쓴 둘째 블록 — 옛 첫 카드 셈은 2 로 읽었고 카드 묶음 셈은 숫자가 아니라 못 읽는다. 커서는 둘 중 큰 쪽
        d = os.path.join(tmp, "c2")
        os.makedirs(d)
        box_with(binary, d, lambda L: L[:-1] + ["*SECTION_SOLID", "       2.0         1"] + L[-1:])
        open(os.path.join(d, "off.yaml"), "w").write(OFFSET)
        rc, out = run(binary, d, "offset", "off.yaml")
        sec = part_secid(os.path.join(d, "out.k"), 10) if rc == 0 else None
        check("C-2 SECID 2.0 블록 — 새 섹션은 2 를 다시 내지 않는다(SECID 3)", sec == 3, (rc, sec, out[-300:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
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
