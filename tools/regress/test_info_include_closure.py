#!/usr/bin/env python3
"""`info --strict` 가 주 덱을 **인클루드 닫힘까지 읽어** 판정하는가.

왜 이 시험이 있나 (2026-10-15).

  `info` 는 `*INCLUDE` 가 하나라도 있으면 「미정의 참조 0건 — 다만 *INCLUDE 를 읽지 않았으므로 단정할
  수 없습니다」로 끝냈다. 그래서 `--strict` 가 **인클루드 조각은 막으면서 주 덱은 한 장도 안 봤다.**
  실사용 study 덱 1,683장 실측 — `--strict` 가 막은 142장의 92% 가 주 덱에 인클루드되는 조각이었고,
  인클루드를 가진 주 덱 88장은 **전부** 「단정 불가」였다.

  이제 닫힘(`include_closure`)을 읽어 정의를 모두 모은다. 같은 88장이 **87장 단정 통과 · 1장 단정
  불가**(보관하면서 `02_mesh` 를 뺀 폴더 — LS-DYNA 도 못 돈다) · **막힌 덱 0장**으로 갈렸다.

무엇을 보나.
  A 인클루드에 정의가 있으면 주 덱이 **단정 통과**한다(rc 0, --strict 여도)
  B 인클루드 **안의** 미정의 참조는 단정 — rc 1, 그 파일 안의 줄 번호, 끝에 파일 이름
  C 파일을 **건너뛴** 같은 종류 SID 중복을 잡는다(LS-DYNA 는 모델 전체에서 유일해야 한다)
  D 못 읽은 인클루드가 있으면 예전처럼 단정하지 않고 **그 파일만** 이름으로 말한다
  E `*INCLUDE_TRANSFORM` 은 따라가지 않고 그렇다고 말한다(단정 불가)
  F 인클루드 없는 덱은 예전 그대로 — 인클루드 이야기를 안 하고, 단정 미정의면 rc 1
  G ★**메시 축은 예전 그대로 단정하지 않는다.** 「없는 노드를 가리키는 요소」 검사는 `KFileReader`
    의 메시를 쓰는데 그 리더는 인클루드를 안 읽는다. 노드가 인클루드에 있는 덱을 그 검사가 막으면
    오탐이다 — 참조 축을 단정하게 됐다고 그 축까지 단정하면 안 된다
  H 플랫폼 파서(`kfile_inspect._parse_ref_dangling`)가 새 출력을 **그대로 읽는다** — 줄 꼴은 계약이다

usage: test_info_include_closure.py <KooRemapper 바이너리>
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
    print("  %-64s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def info(binary, path):
    r = subprocess.run([binary, "info", path, "--strict"], capture_output=True, text=True,
                       timeout=120, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout + r.stderr


def write(d, name, body):
    p = os.path.join(d, name)
    open(p, "w", encoding="utf-8").write(body)
    return p


SET10 = "*SET_PART_LIST\n        10       0.0       0.0       0.0       0.0\n         1\n"
SPC = "*BOUNDARY_SPC_SET\n%10d         0         1         1         1         0         0         0\n"


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="iic_")
    try:
        print("[A 인클루드에 정의가 있으면 주 덱이 단정 통과]")
        write(d, "a_def.k", "*KEYWORD\n" + SET10 + "*END\n")
        m = write(d, "a_main.k", "*KEYWORD\n" + SPC % 10 + "*INCLUDE\na_def.k\n*END\n")
        rc, out = info(binary, m)
        check("A rc 0", rc == 0, out[-300:])
        check("A 단정 통과라고 말한다", "인클루드 1개를 함께 읽었습니다" in out, out[-300:])
        check("A 단정 불가라고 하지 않는다", "단정할 수 없습니다" not in out)

        print("[B 인클루드 안의 미정의 참조]")
        write(d, "b_inc.k", "*KEYWORD\n" + SPC % 99 + "*END\n")
        m = write(d, "b_main.k", "*KEYWORD\n" + SET10 + "*INCLUDE\nb_inc.k\n*END\n")
        rc, out = info(binary, m)
        check("B rc 1(단정 + --strict)", rc == 1, out[-300:])
        check("B 단정 등급으로 말한다", "[ERROR] 정의되지 않은 것을 가리키는 카드 1건" in out, out[-300:])
        # 줄 번호는 참조가 든 **데이터 줄**이다(키워드 줄 아님) — 인클루드 없는 덱과 같은 규칙.
        check("B 그 파일 안의 줄 번호와 파일 이름",
              "  line 3 *BOUNDARY_SPC_SET: 세트 99 이 정의되지 않았습니다 — 인클루드 b_inc.k" in out,
              [l for l in out.splitlines() if l.startswith("  line")][:2])

        print("[C 파일을 건너뛴 같은 종류 SID 중복]")
        write(d, "c_inc.k", "*KEYWORD\n" + SET10 + "*END\n")
        m = write(d, "c_main.k", "*KEYWORD\n" + SET10 + "*INCLUDE\nc_inc.k\n*END\n")
        rc, out = info(binary, m)
        check("C rc 1", rc == 1, out[-300:])
        check("C 겹침을 잡고 상대가 주 덱이라고 말한다",
              "SID 10 가 line 3(주 덱) 과 겹칩니다" in out and "— 인클루드 c_inc.k" in out,
              [l for l in out.splitlines() if "겹칩" in l][:2])

        print("[D 못 읽은 인클루드]")
        write(d, "d_ok.k", "*KEYWORD\n" + SET10 + "*END\n")
        m = write(d, "d_main.k", "*KEYWORD\n" + SPC % 77 + "*INCLUDE\nd_ok.k\nd_gone.k\n*END\n")
        rc, out = info(binary, m)
        check("D rc 0(단정하지 않는다)", rc == 0, out[-300:])
        check("D 못 읽은 파일만 이름으로", "*INCLUDE 안은 보지 않았습니다: d_gone.k(없다)" in out,
              [l for l in out.splitlines() if "INCLUDE 안은" in l])

        print("[E *INCLUDE_TRANSFORM]")
        write(d, "e_t.k", "*KEYWORD\n" + SET10 + "*END\n")
        m = write(d, "e_main.k", "*KEYWORD\n" + SPC % 10 +
                  "*INCLUDE_TRANSFORM\ne_t.k\n         0         0         0         0         0\n*END\n")
        rc, out = info(binary, m)
        check("E rc 0(단정하지 않는다)", rc == 0, out[-300:])
        check("E 따라가지 않았다고 말한다", "*INCLUDE_TRANSFORM e_t.k(따라가지 않았다)" in out,
              [l for l in out.splitlines() if "INCLUDE 안은" in l])

        print("[F 인클루드 없는 덱은 예전 그대로]")
        m = write(d, "f_main.k", "*KEYWORD\n" + SPC % 55 + "*END\n")
        rc, out = info(binary, m)
        check("F rc 1(단정 미정의)", rc == 1, out[-300:])
        check("F 인클루드 이야기를 하지 않는다", "인클루드" not in out and "INCLUDE" not in out, out[-200:])

        print("[G 메시 축은 단정하지 않는다 — 노드가 인클루드에 있다]")
        write(d, "g_nodes.k", "*KEYWORD\n*NODE\n" + "".join(
            "%8d%16.6f%16.6f%16.6f\n" % (i + 1, x, y, z) for i, (x, y, z) in enumerate(
                [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]))
              + "*END\n")
        m = write(d, "g_main.k", "*KEYWORD\n*PART\npart\n         1         1         1\n"
                  "*SECTION_SOLID\n         1         1\n*MAT_ELASTIC\n         1    7.8E-9  210000.0       0.3\n"
                  "*ELEMENT_SOLID\n       1       1       1       2       3       4       5       6       7       8\n"
                  "*INCLUDE\ng_nodes.k\n*END\n")
        rc, out = info(binary, m)
        check("G 없는 노드로 막지 않는다(rc 0)", rc == 0, [l for l in out.splitlines() if "strict" in l][:2])

        print("[H 플랫폼 파서가 그대로 읽는다]")
        sys.path.insert(0, os.path.join(REPO, "platform", "backend"))
        try:
            from app.runner.kfile_inspect import _parse_ref_dangling
        except Exception as exc:                                 # noqa: BLE001
            check("H 플랫폼 파서를 불러온다", False, exc)
        else:
            rc, out = info(binary, os.path.join(d, "b_main.k"))
            ref = _parse_ref_dangling(out) or {}
            check("H 단정 등급", ref.get("grade") == "certain", ref)
            top = (ref.get("top") or [{}])[0]
            check("H 항목의 줄·키워드를 읽는다", top.get("line") == 3 and
                  top.get("keyword") == "*BOUNDARY_SPC_SET", top)
            rc, out = info(binary, os.path.join(d, "d_main.k"))
            ref = _parse_ref_dangling(out) or {}
            check("H 못 읽은 인클루드를 읽는다", ref.get("grade") == "uncertain" and
                  ref.get("unread_includes") == ["d_gone.k(없다)"], ref)
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
