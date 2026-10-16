#!/usr/bin/env python3
"""`modelmeta` 가 인클루드를 **정본 규칙대로** 읽는가 — 중첩 · `_TRANSFORM` · `_PATH` · 못 읽은 이름.

왜 이 시험이 있나 (2026-10-16).

  `modelmeta` 는 인클루드를 따로 읽었다(`mm_collectLines`). **한 단계만** 따라갔고 `*INCLUDE_*` 를 전부
  맨 `*INCLUDE` 처럼 읽었다 —
    · `*INCLUDE_TRANSFORM` 파일을 **ID 오프셋 없이** 읽어 그 안의 재질·섹션을 그럴듯하게 틀린 번호로 셌다
      (이 산출은 DataHub 적재로 나간다)
    · `*INCLUDE_PATH` 의 디렉터리 이름을 파일로 열려 했다(조용히 실패)
    · 중첩 인클루드 안의 재질을 **못 봤다**
    · 못 연 파일을 말하지 않았다
  지금은 정본(`include_closure`)으로 읽고 LS-DYNA 가 읽는 차례대로 펼친다.

무엇을 보나.
  A 중첩 인클루드(주 → a.k → mat.k)의 `*MAT_ELASTIC` 카드를 찾는다(옛 판은 한 단계라 못 찾았다)
  B `*INCLUDE_TRANSFORM` 안의 재질은 **쓰지 않고**, 따라가지 않았다고 경고한다
  C `*INCLUDE_PATH` 는 탐색 경로일 뿐 — 경고하지 않는다
  D 못 읽은 인클루드는 이름으로 경고한다(rc 0)

usage: test_modelmeta_includes.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail)[:300]))
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    return cond


MESH = """*KEYWORD
*PART
plate
         1         1         7
*SECTION_SOLID
         1         1
*NODE
       1       0.0       0.0       0.0
       2       1.0       0.0       0.0
       3       1.0       1.0       0.0
       4       0.0       1.0       0.0
       5       0.0       0.0       1.0
       6       1.0       0.0       1.0
       7       1.0       1.0       1.0
       8       0.0       1.0       1.0
*ELEMENT_SOLID
       1       1       1       2       3       4       5       6       7       8
"""
MAT7 = "*KEYWORD\n*MAT_ELASTIC\n         7    7.8E-9  123456.0       0.3\n*END\n"


def run(binary, d, main_tail, files):
    open(os.path.join(d, "main.k"), "w", encoding="utf-8").write(MESH + main_tail + "*END\n")
    for name, body in files.items():
        p = os.path.join(d, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(body)
    open(os.path.join(d, "m.yaml"), "w", encoding="utf-8").write("model: main.k\noutput: o\n")
    r = subprocess.run([binary, "modelmeta", "m.yaml"], cwd=d, capture_output=True, text=True,
                       timeout=120, encoding="utf-8", errors="replace")
    p = os.path.join(d, "o_modelmeta.json")
    j = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
    return r.returncode, j, r.stdout + r.stderr


def kfile_kw(j):
    """파트 재질의 **키워드** — 펼친 줄(`mm_scanMatCards`)에서 온다. 이 시험이 보는 것은 이것이다.

    ⚠ 재질 **값**(E·nu·rho)은 여기서 보지 않는다. 그 값은 `KFileReader` 의 메시에서 오는데
    (`modelmeta.cpp:775-781`) 그 리더는 **주 덱만** 읽는다 — 인클루드 안 재질은 옛 판도 새 판도
    키워드만 있고 값은 없다. 이번 변경과 무관한 기존 한계라 장부에 따로 올렸다.
    """
    try:
        return ((j["parts"][0]["material"] or {}).get("kfile") or {}).get("keyword")
    except (KeyError, IndexError, TypeError):
        return None


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    cases = [
        ("A 중첩 인클루드의 재질", "*INCLUDE\na.k\n",
         {"a.k": "*KEYWORD\n*INCLUDE\nmat.k\n*END\n", "mat.k": MAT7}),
        ("B *INCLUDE_TRANSFORM", "*INCLUDE_TRANSFORM\nt.k\n         0         0         0         0\n",
         {"t.k": MAT7}),
        ("C *INCLUDE_PATH", "*INCLUDE_PATH\nlibdir\n*INCLUDE\nmat.k\n", {"libdir/mat.k": MAT7}),
        ("D 못 읽은 인클루드", "*INCLUDE\ngone.k\n", {}),
    ]
    for label, tail, files in cases:
        print("[%s]" % label)
        d = tempfile.mkdtemp(prefix="mmi_")
        try:
            rc, j, out = run(binary, d, tail, files)
            if not check("%s — rc 0 · JSON" % label, rc == 0 and j is not None, out[-300:]):
                continue
            kw = kfile_kw(j)
            if label.startswith("A"):
                check("A 중첩 인클루드의 재질 카드를 찾았다", kw == "*MAT_ELASTIC", kw)
                check("A 경고가 없다", "못 본 인클루드" not in out, out[-200:])
            elif label.startswith("B"):
                check("B 오프셋 모르는 파일의 재질 카드를 쓰지 않는다", kw is None, kw)
                check("B 따라가지 않았다고 경고한다",
                      "못 본 인클루드" in out and "*INCLUDE_TRANSFORM" in out, out[-300:])
            elif label.startswith("C"):
                check("C 탐색 경로에서 재질 카드를 찾았다", kw == "*MAT_ELASTIC", kw)
                check("C 경로를 파일로 다루지 않는다(경고 없음)", "못 본 인클루드" not in out, out[-300:])
            elif label.startswith("D"):
                check("D 못 읽은 이름을 경고한다", "못 본 인클루드" in out and "gone.k" in out, out[-300:])
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
