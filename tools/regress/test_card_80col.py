#!/usr/bin/env python3
# 출력기가 새로 쓰는 고정폭 카드가 80열·10칸 경계를 지키는가 — TIED 접촉 카드 2 와 DR 종료 카드
"""카드 80열 · 칸 경계 (2026-11-03).

왜 이 시험이 있나.
  pykoocae-53 이 KMM 을 고치다 찾았다 — TIED 접촉 카드 2(fs…dt)의 DT 를 `  1.0000E+20`(12칸)으로 써 줄이
  82자였다. R16 은 「characters beyond column 80 of each line are ignored」 라서 LS-DYNA 는 71~80열
  `  1.0000E+` 만 읽는다(DT 가 1.0 이 되거나 읽기 오류). 같은 자리를 훑다 DR 종료 카드도 찾았다 —
  `       0.0         0       0.0       0.0       0.01e+20         0` 는 10칸으로 읽으면 ENDMAS 가 0.0 이고
  **정수 칸 NOSOL** 에 `1e+20` 이 앉는다. NOSOL 은 「non-solution run(초기화 직후 정상 종료)」 깃발이다
  (Vol_I `*CONTROL_TERMINATION`, Type I · 기본 0).
  i10 폭 훑기(`test_i10_width_sweep.py`)는 op 예제가 이 경로를 안 지나서 못 잡았다 — 여기서 직접 지난다.

무엇을 본다(LS-DYNA 처럼 고정 창으로).
  · restack(tied·czm 셸 층) · offset(셸 + tied) · assemble(DR + *CONTROL_TERMINATION) 의 산출에서
    **op 이 쓴 줄**(입력에 없던 줄)이 80열을 넘지 않는다.
  · 접촉 카드 2 의 71~80열(DT)이 1e20 으로 읽힌다.
  · DR 종료 카드 — ENDTIM 0 · ENDMAS 1e20 · NOSOL 0(정수).

usage: test_card_80col.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
EX = os.path.join(REPO, "examples")
FAILS = []
BIN = ""


def check(name, cond, detail=""):
    print("  %-70s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:300]) if detail else ""))
    return cond


def run(d, *args):
    p = subprocess.run([BIN, *args], cwd=d, capture_output=True, text=True, timeout=300,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def fld(line, k):
    """고정 10칸의 k번째(0-기준) 칸 글자 — LS-DYNA 가 읽는 창 그대로(80열 밖은 버린다)."""
    return line[:80][10 * k:10 * k + 10].strip() if line is not None else ""


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def lines(p):
    return open(p, encoding="utf-8", errors="replace").read().splitlines()


def long_op_lines(out, inputs):
    """op 이 쓴(입력에 그대로 없던) 데이터 줄 중 80열을 넘는 것. `$` 주석·키워드·자유형식은 뺀다."""
    seen = set()
    for p in inputs:
        seen |= {x.rstrip() for x in lines(p)}
    return [x for x in lines(out)
            if x.strip() and not x.startswith(("$", "*")) and "," not in x
            and x.rstrip() not in seen and len(x.rstrip()) > 80]


def cards(path, prefix):
    """`prefix` 로 시작하는 키워드 블록마다 데이터 카드 줄 목록(`$` 주석만 뺀다)."""
    out, cur = [], None
    for x in lines(path):
        if x.startswith("*"):
            cur = [] if x.upper().startswith(prefix) else None
            if cur is not None:
                out.append(cur)
            continue
        if cur is not None and not x.startswith("$"):
            cur.append(x)
    return out


def restack_yaml(mode):
    def layer(title, t, mid, e, shell=False):
        return ("      - title: %s\n        thickness: %s\n%s        num_elements: 1\n"
                "        material_card: |\n          *MAT_ELASTIC_TITLE\n          %s\n"
                "                  %2d 7.850E-09 %s 3.000E-01       0.0       0.0       0.0\n"
                % (title, t, "        element_type: shell\n" if shell else "", title, mid, e))
    return ("base_model: base_model.k\noutput: rs_%s\noperations:\n  - type: restack\n    target_pid: 1\n"
            "    direction: z\n    element_type: solid\n    interface_contact: %s\n    layers:\n" % (mode, mode)
            + layer("LOWER", 0.4, 7, "2.100E+05") + layer("SKIN", 0.2, 8, "3.000E+03", shell=True)
            + layer("UPPER", 0.4, 9, "2.100E+05"))


def check_contact(tag, out, inputs, kw):
    blocks = cards(out, kw)
    check("%s 접촉 카드가 생긴다 (%s)" % (tag, kw), bool(blocks), "블록 0")
    long_ = long_op_lines(out, inputs)
    check("%s op 이 쓴 줄이 80열을 넘지 않는다" % tag, not long_,
          "%d줄 — 첫 %d자 %r" % (len(long_), len(long_[0].rstrip()), long_[0]) if long_ else "")
    bad = [b[1] for b in blocks if len(b) < 2 or num(fld(b[1], 7)) != 1.0e20]
    check("%s 카드 2 의 DT(71~80열)가 1e20 으로 읽힌다" % tag, not bad, bad[:1])


def main():
    global BIN
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    BIN = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="col80_")
    try:
        print("[A restack — 셸 층 양쪽의 접촉(tied · czm)]")
        shutil.copy(os.path.join(EX, "replace_test", "base_model.k"), d)
        for mode, kw in (("tied", "*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET"),
                         ("czm", "*CONTACT_TIED_SURFACE_TO_SURFACE_FAILURE")):
            open(os.path.join(d, "rs_%s.yaml" % mode), "w").write(restack_yaml(mode))
            rc, log = run(d, "assemble", "rs_%s.yaml" % mode)
            if check("A-%s restack rc 0" % mode, rc == 0, log[-300:]):
                check_contact("A-%s" % mode, os.path.join(d, "rs_%s.k" % mode),
                              [os.path.join(d, "base_model.k")], kw)

        print("[B offset — 셸 층 + tied 묶음 접촉]")
        os.makedirs(os.path.join(d, "off"))
        os.makedirs(os.path.join(d, "arc30"))
        shutil.copy(os.path.join(EX, "offset", "04_shell_offset.yaml"), os.path.join(d, "off"))
        shutil.copy(os.path.join(EX, "arc30", "arc30_flat.k"), os.path.join(d, "arc30"))
        rc, log = run(os.path.join(d, "off"), "assemble", "04_shell_offset.yaml")
        if check("B offset rc 0", rc == 0, log[-300:]):
            check_contact("B", os.path.join(d, "off", "04_shell_result.k"),
                          [os.path.join(d, "arc30", "arc30_flat.k")], "*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET")

        print("[C DR — *CONTROL_TERMINATION 을 DR 전용으로 바꿔 쓴다]")
        shutil.copy(os.path.join(EX, "replace_test", "base_model_with_term.k"), d)
        y = open(os.path.join(EX, "replace_test", "assemble_dr_test.yaml"), encoding="utf-8").read()
        y = y.replace("base_model: base_model.k", "base_model: base_model_with_term.k")
        y = y.replace("output: assembled_dr_result", "output: dr_out")
        open(os.path.join(d, "dr.yaml"), "w").write(y)
        rc, log = run(d, "assemble", "dr.yaml")
        if check("C assemble(DR) rc 0", rc == 0, log[-300:]):
            out = os.path.join(d, "dr_out.k")
            term = cards(out, "*CONTROL_TERMINATION")
            c1 = term[0][0] if term and term[0] else ""
            check("C 종료 카드가 하나다", len(term) == 1, len(term))
            check("C ENDTIM = 0 (DR 만 돈다)", num(fld(c1, 0)) == 0.0, repr(c1))
            check("C ENDMAS(5번째 칸) = 1e20", num(fld(c1, 4)) == 1.0e20, repr(c1))
            nosol = fld(c1, 5)
            check("C NOSOL(6번째 칸)은 정수 0 — 1 이면 해석 없이 초기화만 하고 끝난다",
                  nosol in ("", "0"), repr(nosol))
            long_ = long_op_lines(out, [os.path.join(d, "base_model_with_term.k")])
            check("C op 이 쓴 줄이 80열을 넘지 않는다", not long_, long_[:1])
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print()
    if FAILS:
        print("FAIL %d" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
