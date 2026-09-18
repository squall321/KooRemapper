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
  - 5절은 '아직 동작이 없다'는 사실 자체를 못으로 박는다. 검증만 하고 값을 버리는 단절(단독 경로)은
    컴파일 오류도 시험 실패도 내지 않아 조용히 남는다 — 동작이 들어오면 5절이 깨져 그 자리를 가리킨다.
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


def asm_restack(name, pid_refs, model="flat.k"):
    key = f"    pid_refs: {pid_refs}\n" if pid_refs is not None else ""
    return (f"base_model: {model}\noutput: o_{name}\noperations:\n"
            "  - type: restack\n    target_pid: 1\n    direction: z\n"
            + key +
            "    layers:\n      - thickness: 1.0\n        num_elements: 1\n" + MAT +
            "      - thickness: 1.0\n        num_elements: 1\n" + MAT)


def asm_merge(name, pid_refs, model="flat.k"):
    key = f"    pid_refs: {pid_refs}\n" if pid_refs is not None else ""
    return (f"base_model: {model}\noutput: o_{name}\noperations:\n"
            "  - type: merge\n    direction: z\n    method: voigt\n    target_pids: [1]\n" + key)


def standalone_merge(name, pid_refs, model="flat.k"):
    key = f"pid_refs: {pid_refs}\n" if pid_refs is not None else ""
    return (f"model: {model}\noutput: sm_{name}.k\ndirection: z\nmethod: voigt\n" + key +
            "merge:\n  - pids: [1]\n")


def standalone_restack(name, pid_refs, model="flat.k"):
    key = f"pid_refs: {pid_refs}\n" if pid_refs is not None else ""
    return (f"model: {model}\noutput: s_{name}\ntarget_pid: 1\ndirection: z\n" + key +
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
        rc, out = write_run(binary, d, "merge", f"sm_{tag}", standalone_merge(f"sm_{tag}", val))
        check(f"단독 merge pid_refs: {label} → rc=0", rc == 0, f"rc={rc} {out[-300:]}")

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
        rc, out = write_run(binary, d, "merge", f"smb_{bad}", standalone_merge(f"smb_{bad}", bad))
        check(f"단독 merge pid_refs: {bad} → rc=1 + 허용값(assemble 과 같은 문구)",
              rc == 1 and f"invalid pid_refs '{bad}'" in out and "strict, warn" in out,
              f"rc={rc} {out[-300:]}")
        check(f"단독 merge pid_refs: {bad} → 덱을 내지 않는다",
              not os.path.exists(os.path.join(d, f"sm_smb_{bad}.k")), "거부했는데 덱이 남았다")

    # ── 3. 주석·따옴표 — 다른 키와 같은 관례 ────────────────────────────────
    print("[값 뒤 주석·따옴표는 다른 키와 같게 벗겨진다]")
    for form, label in (('warn   # 경고만', "인라인 주석"), ('"warn"', "큰따옴표"), ("'warn'", "작은따옴표")):
        rc, out = write_run(binary, d, "assemble", f"ac_{label}", asm_restack(f"ac_{label}", form))
        check(f"assemble restack pid_refs: {label} → rc=0", rc == 0, f"rc={rc} {out[-300:]}")
        rc, out = write_run(binary, d, "restack", f"sc_{label}", standalone_restack(f"sc_{label}", form))
        check(f"단독 restack pid_refs: {label} → rc=0", rc == 0, f"rc={rc} {out[-300:]}")
        rc, out = write_run(binary, d, "merge", f"smc_{label}", standalone_merge(f"smc_{label}", form))
        check(f"단독 merge pid_refs: {label} → rc=0", rc == 0, f"rc={rc} {out[-300:]}")

    # ── 4. 키를 줘도 덱은 달라지지 않는다(아직 동작이 없다) ─────────────────
    print("[pid_refs 는 아직 덱을 바꾸지 않는다 — 키없음과 바이트 동일]")
    base = open(os.path.join(d, "o_ar_none.k")).read()
    sbase = open(os.path.join(d, "s_sr_none.k")).read()
    mbase = open(os.path.join(d, "sm_sm_none.k")).read()
    for val in ("strict", "warn"):
        other = open(os.path.join(d, f"o_ar_{val}.k")).read()
        check(f"assemble restack: pid_refs: {val} 덱 == 키없음 덱", base == other,
              "출력 덱이 달라졌다")
        check(f"단독 restack: pid_refs: {val} 덱 == 키없음 덱",
              sbase == open(os.path.join(d, f"s_sr_{val}.k")).read(), "출력 덱이 달라졌다")
        check(f"단독 merge: pid_refs: {val} 덱 == 키없음 덱",
              mbase == open(os.path.join(d, f"sm_sm_{val}.k")).read(), "출력 덱이 달라졌다")

    # ── 5. 죽은 PID 참조가 있는 덱 — 지금 상태를 못으로 박는다 ──────────────
    # 키는 파싱·검증까지만 되어 있고 값은 어디에도 닿지 않는다. 단독 restack 은 validateOperation 에
    # 넘긴 뒤 원문을 버리고(applyRestack 은 RestackOperation 만 받는다), 단독 merge 도 cfg 에 담아만 둔다.
    # 그래서 죽은 참조가 남은 덱에서도 strict 가 rc=0 이다 — 이게 지금의 사실이고, 아래 단언은 그 사실을
    # 고정한다. 참조 재배치가 들어오면 단언이 깨지고, 그때 단독 경로까지 정책을 배선해야 다시 초록이 된다.
    print("[죽은 PID 참조 덱 — 아직 정책이 rc 를 바꾸지 않는다(동작이 들어오면 이 절이 깨진다)]")
    deck = open(os.path.join(d, "flat.k")).read()
    dead = ("*SET_PART_LIST\n"
            "         1         0         0         0         0\n"
            "         1\n")
    open(os.path.join(d, "flat_ref.k"), "w").write(deck.replace("*END", dead + "*END"))

    rc_ar, _ = write_run(binary, d, "assemble", "xar", asm_restack("xar", "strict", "flat_ref.k"))
    rc_sr, _ = write_run(binary, d, "restack", "xsr", standalone_restack("xsr", "strict", "flat_ref.k"))
    rc_sw, _ = write_run(binary, d, "restack", "xsw", standalone_restack("xsw", "warn", "flat_ref.k"))
    check("단독 restack strict: 죽은 참조가 남아도 아직 rc=0 (동작이 들어오면 1 이어야 한다)",
          rc_sr == 0, f"rc={rc_sr}")
    check("단독 restack: warn 이 아직 rc 를 바꾸지 않는다 (strict 와 같다)",
          rc_sw == rc_sr, f"strict={rc_sr} warn={rc_sw}")
    check("restack strict: assemble rc == 단독 rc (한쪽만 배선되면 깨진다)",
          rc_ar == rc_sr, f"assemble={rc_ar} 단독={rc_sr}")
    check("단독 restack: 죽은 *SET_PART_LIST 가 출력 덱에 그대로 남아 있다",
          "*SET_PART_LIST" in open(os.path.join(d, "s_xsr.k")).read(), "카드가 사라졌다")

    rc_am, _ = write_run(binary, d, "assemble", "xam", asm_merge("xam", "strict", "flat_ref.k"))
    rc_sm, _ = write_run(binary, d, "merge", "xsm", standalone_merge("xsm", "strict", "flat_ref.k"))
    rc_smw, _ = write_run(binary, d, "merge", "xsmw", standalone_merge("xsmw", "warn", "flat_ref.k"))
    check("단독 merge strict: 죽은 참조가 남아도 아직 rc=0 (동작이 들어오면 1 이어야 한다)",
          rc_sm == 0, f"rc={rc_sm}")
    check("단독 merge: warn 이 아직 rc 를 바꾸지 않는다 (strict 와 같다)",
          rc_smw == rc_sm, f"strict={rc_sm} warn={rc_smw}")
    check("merge strict: assemble rc == 단독 rc (한쪽만 배선되면 깨진다)",
          rc_am == rc_sm, f"assemble={rc_am} 단독={rc_sm}")
    check("단독 merge: 죽은 *SET_PART_LIST 가 출력 덱에 그대로 남아 있다",
          "*SET_PART_LIST" in open(os.path.join(d, "sm_xsm.k")).read(), "카드가 사라졌다")

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
