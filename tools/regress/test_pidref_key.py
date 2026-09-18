# pid_refs 키(strict|warn) 파싱·검증 회귀 시험 — assemble(restack·merge)과 단독 restack 이 같은 규칙인지 실제 실행으로 본다
"""
사용: python3 tools/regress/test_pidref_key.py <KooRemapper 바이너리>

배경
  - restack·merge 는 원 *PART 를 비워 두고 새 PID 를 발급한다. 그 PID 를 가리키던 *SET_PART_LIST·
    *CONTACT_* 같은 카드는 바이트 그대로 남아 죽은 참조가 된다.
  - 옮기지 못한 참조가 남으면 rc=1 로 끝내는 게 기본(strict)이고, 탈출구는 pid_refs: warn 하나다.
    파이프라인(Runner·플랫폼 워커)은 종료 코드로만 성공을 판정하므로 rc=0 이면 경고가 보이지 않는다.
  - 이 시험은 '키가 파싱되고 검증된다' 까지만 본다. strict/warn 의 동작 차이는 참조 재배치 구현이
    들어온 뒤 그쪽 시험이 맡는다.
"""
import os
import subprocess
import sys
import tempfile

FAILS = []

BOX = "output: flat.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\npid: 1\nmid: 1\nsecid: 1\n"

# assemble 의 층 항목은 operations[] 안이라 단독보다 네 칸 깊다
MAT = ("        material_card: |\n"
       "          *MAT_ELASTIC\n"
       "               @MID@       2.0     12000      0.25\n")

MAT_STANDALONE = ("    material_card: |\n"
                  "      *MAT_ELASTIC\n"
                  "           @MID@       2.0     12000      0.25\n")


def check(name, cond, detail=""):
    print("  %-70s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def write_run(binary, d, cmd, name, body):
    open(os.path.join(d, name + ".yaml"), "w").write(body)
    return run(binary, d, cmd, name + ".yaml")


def asm_restack(name, pid_refs):
    key = f"    pid_refs: {pid_refs}\n" if pid_refs is not None else ""
    return (f"base_model: flat.k\noutput: o_{name}\noperations:\n"
            "  - type: restack\n    target_pid: 1\n    direction: z\n"
            + key +
            "    layers:\n      - thickness: 1.0\n        num_elements: 1\n" + MAT +
            "      - thickness: 1.0\n        num_elements: 1\n" + MAT)


def asm_merge(name, pid_refs):
    key = f"    pid_refs: {pid_refs}\n" if pid_refs is not None else ""
    return (f"base_model: flat.k\noutput: o_{name}\noperations:\n"
            "  - type: merge\n    direction: z\n    method: voigt\n    target_pids: [1]\n" + key)


def standalone_restack(name, pid_refs):
    key = f"pid_refs: {pid_refs}\n" if pid_refs is not None else ""
    return (f"model: flat.k\noutput: s_{name}\ntarget_pid: 1\ndirection: z\n" + key +
            "layers:\n  - thickness: 1.0\n    num_elements: 1\n" + MAT_STANDALONE +
            "  - thickness: 1.0\n    num_elements: 1\n" + MAT_STANDALONE)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="pidref_key_")
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    if rc != 0:
        print("생성 실패:", out[-400:])
        return 1

    # ── 1. 허용값은 실행된다 ────────────────────────────────────────────────
    print("[허용값 strict|warn — assemble restack / merge / 단독 restack]")
    for val in ("strict", "warn", None):
        tag = val if val else "none"
        label = val if val else "키없음"
        rc, out = write_run(binary, d, "assemble", f"ar_{tag}", asm_restack(f"ar_{tag}", val))
        check(f"assemble restack pid_refs: {label} → rc=0", rc == 0, f"rc={rc} {out[-300:]}")
        rc, out = write_run(binary, d, "assemble", f"am_{tag}", asm_merge(f"am_{tag}", val))
        check(f"assemble merge pid_refs: {label} → rc=0", rc == 0, f"rc={rc} {out[-300:]}")
        rc, out = write_run(binary, d, "restack", f"sr_{tag}", standalone_restack(f"sr_{tag}", val))
        check(f"단독 restack pid_refs: {label} → rc=0", rc == 0, f"rc={rc} {out[-300:]}")

    # ── 2. 허용값 밖은 조용히 기본값으로 떨어지지 않는다 ────────────────────
    print("[허용값 밖 — rc=1 + 허용값 안내(D1)]")
    for bad in ("strictly", "WARN", "off", "1"):
        rc, out = write_run(binary, d, "assemble", f"ab_{bad}", asm_restack(f"ab_{bad}", bad))
        check(f"assemble restack pid_refs: {bad} → rc=1 + 허용값",
              rc == 1 and f"invalid pid_refs '{bad}'" in out and "strict, warn" in out,
              f"rc={rc} {out[-300:]}")
        rc, out = write_run(binary, d, "assemble", f"mb_{bad}", asm_merge(f"mb_{bad}", bad))
        check(f"assemble merge pid_refs: {bad} → rc=1 + 허용값",
              rc == 1 and f"invalid pid_refs '{bad}'" in out and "strict, warn" in out,
              f"rc={rc} {out[-300:]}")
        rc, out = write_run(binary, d, "restack", f"sb_{bad}", standalone_restack(f"sb_{bad}", bad))
        check(f"단독 restack pid_refs: {bad} → rc=1 + 허용값(assemble 과 같은 문구)",
              rc == 1 and f"invalid pid_refs '{bad}'" in out and "strict, warn" in out,
              f"rc={rc} {out[-300:]}")

    # ── 3. 주석·따옴표 — 다른 키와 같은 관례 ────────────────────────────────
    print("[값 뒤 주석·따옴표는 다른 키와 같게 벗겨진다]")
    for form, label in (('warn   # 경고만', "인라인 주석"), ('"warn"', "큰따옴표"), ("'warn'", "작은따옴표")):
        rc, out = write_run(binary, d, "assemble", f"ac_{label}", asm_restack(f"ac_{label}", form))
        check(f"assemble restack pid_refs: {label} → rc=0", rc == 0, f"rc={rc} {out[-300:]}")
        rc, out = write_run(binary, d, "restack", f"sc_{label}", standalone_restack(f"sc_{label}", form))
        check(f"단독 restack pid_refs: {label} → rc=0", rc == 0, f"rc={rc} {out[-300:]}")

    # ── 4. 키를 줘도 덱은 달라지지 않는다(아직 동작이 없다) ─────────────────
    print("[pid_refs 는 아직 덱을 바꾸지 않는다 — 키없음과 바이트 동일]")
    base = open(os.path.join(d, "o_ar_none.k")).read()
    for val in ("strict", "warn"):
        other = open(os.path.join(d, f"o_ar_{val}.k")).read()
        check(f"assemble restack: pid_refs: {val} 덱 == 키없음 덱", base == other,
              "출력 덱이 달라졌다")

    print()
    if FAILS:
        print(f"FAIL {len(FAILS)}")
        for f in FAILS:
            print("  -", f[:300])
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
