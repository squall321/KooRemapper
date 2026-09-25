#!/usr/bin/env python3
"""고정폭 10칸에 값을 넣을 때 **자르지 않는다** — 자르면 부호·자릿수가 조용히 사라진다.

왜 이 시험이 있나 (2026-09-24, 덱 편집 계약 요청서 DF-03):

  `applyControl` 의 fmt10d 가 `s.substr(s.size() - 10)` 으로 **앞을 버렸다.**
  `dt2ms: -1.0e-7` → `%10.4E` → `-1.0000E-07`(11자) → 앞이 잘려 `1.0000E-07` 이 나갔다.

  dt2ms 는 **음수가 선택적 질량스케일링, 양수가 고정 dt 스케일링**이다. 부호 하나로 해석의
  물리가 뒤바뀌는데 rc=0 · 경고 0 이었고, 구조 카운트(노드·요소·파트)는 전부 정상이라
  아무도 알아볼 수 없었다. 매뉴얼(39.19)이 스스로 `dt2ms: -1.0e-7  # 음수` 를 안내하므로
  문서를 따른 사용자가 정확히 이 함정을 밟는다.

  fmt10i 는 반대로 `substr(0, 10)` 으로 뒤를 버려 자릿수를 줄였다.

지금 규약: 10칸에 들어가는 표기를 **유효자리를 줄여 가며** 찾고, 그래도 안 되면 잘라내지 않고
rc≠0 으로 실패한다.

usage: test_fixed_width_overflow.py <KooRemapper 바이너리>
"""
import os
import subprocess
import sys
import tempfile

FAILS = []


def check(name, cond, detail=""):
    print("  %-70s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + detail.strip()[:300]) if detail else ""))


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def base_deck(d):
    """블록 예제를 그대로 쓴다 — *CONTROL_* 이 없는 최소 덱이면 충분하다."""
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "..", "examples", "indent", "small", "block.k")
    src = os.path.normpath(src)
    dst = os.path.join(d, "base.k")
    open(dst, "wb").write(open(src, "rb").read())
    return dst


def control_fields(path, keyword):
    """키워드 다음 첫 데이터 줄을 10칸씩 잘라 돌려준다."""
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().upper() == keyword:
            for j in range(i + 1, min(i + 8, len(lines))):
                s = lines[j]
                if not s or s[0] in "$*":
                    continue
                return [s[k:k + 10] for k in range(0, len(s), 10)]
    return []


def negative_dt2ms(binary):
    print("[A 음수 dt2ms 의 부호가 살아남는다]")
    d = tempfile.mkdtemp(prefix="fw_dt2ms_")
    base_deck(d)
    open(os.path.join(d, "c.yaml"), "w").write(
        "base_model: base.k\noutput: out\noperations:\n  - type: control\n    dt2ms: -1.0e-7\n")
    rc, out = run(binary, d, "assemble", "c.yaml")
    check("rc=0", rc == 0, out[-300:])

    f = control_fields(os.path.join(d, "out.k"), "*CONTROL_TIMESTEP")
    check("*CONTROL_TIMESTEP 데이터 줄을 찾았다", len(f) >= 5, str(f))
    if len(f) < 5:
        return
    dt2ms = f[4]
    check("dt2ms 칸이 정확히 10자", len(dt2ms) == 10, repr(dt2ms))
    # ⚠ 핵심 — 부호. 값의 정확한 표기는 유효자리에 따라 달라도 되지만 부호는 절대 아니다.
    check("dt2ms 에 음수 부호가 있다", dt2ms.strip().startswith("-"), repr(dt2ms))
    try:
        check("dt2ms 를 실수로 읽으면 음수", float(dt2ms) < 0, repr(dt2ms))
    except ValueError:
        check("dt2ms 를 실수로 읽을 수 있다", False, repr(dt2ms))


def positive_still_works(binary):
    """제대로 들어가던 값을 망가뜨리지 않았나 — 부호를 살리려다 표기를 깨면 안 된다."""
    print("[B 양수·정수 칸은 그대로다]")
    d = tempfile.mkdtemp(prefix="fw_pos_")
    base_deck(d)
    open(os.path.join(d, "c.yaml"), "w").write(
        "base_model: base.k\noutput: out\noperations:\n"
        "  - type: control\n    endtime: 0.001\n    tssfac: 0.9\n    dt2ms: 1.0e-7\n")
    rc, out = run(binary, d, "assemble", "c.yaml")
    check("rc=0", rc == 0, out[-300:])

    ts = control_fields(os.path.join(d, "out.k"), "*CONTROL_TIMESTEP")
    check("모든 칸이 10자", ts and all(len(x) == 10 for x in ts[:-1]), str(ts))
    if len(ts) >= 5:
        try:
            check("양수 dt2ms 가 양수로 남는다", float(ts[4]) > 0, repr(ts[4]))
        except ValueError:
            check("양수 dt2ms 를 읽을 수 있다", False, repr(ts[4]))
        check("tssfac 0.9 보존", abs(float(ts[1]) - 0.9) < 1e-9, repr(ts[1]))

    tm = control_fields(os.path.join(d, "out.k"), "*CONTROL_TERMINATION")
    if tm:
        try:
            check("endtim 0.001 보존", abs(float(tm[0]) - 0.001) < 1e-12, repr(tm[0]))
        except ValueError:
            check("endtim 을 읽을 수 있다", False, repr(tm[0]))



def generate_material_fields(binary):
    """`generate` 가 재료 값을 10칸에 넣을 때 **앞자리를 버리던 것**(2026-09-25, P1-2 곁).

    ⚠ `applyControl` 에서 이미 고친 것(e2281b3)과 **글자 그대로 같은 코드**가
    `applyGenerate` 에 남아 있었다. 실측으로 둘이 깨졌다.
      · `rho: -7.85e-9` → `%10.4E` 가 `-7.8500E-09`(11자) → 앞의 `-` 가 잘려 **부호가 사라진다**
      · `E: 12345678.0` → `%10g` 가 `1.23457e+07`(11자) → `.23457e+07` 가 되어 값이
        12,345,678 에서 약 2,345,700 으로 바뀌고 칸 폭까지 9자로 깨진다
    둘 다 rc=0 이고 경고가 없었다. **같은 결함을 한 곳만 고치면 다른 곳에 남는다.**
    """
    print("[C generate 의 재료 칸도 앞자리를 버리지 않는다]")
    d = tempfile.mkdtemp(prefix="fw_gen_")

    def gen(name, rho, E, nu):
        open(os.path.join(d, name + ".yaml"), "w").write(
            "output: %s\noperations:\n  - type: generate\n    shape: box\n"
            "    lx: 10.0\n    ly: 10.0\n    lz: 10.0\n    nx: 1\n    ny: 1\n    nz: 1\n"
            "    rho: %s\n    E: %s\n    nu: %s\n" % (name, rho, E, nu))
        rc, out = run(binary, d, "assemble", name + ".yaml")
        return rc, out, control_fields(os.path.join(d, name + ".k"), "*MAT_ELASTIC")

    rc, out, f = gen("gneg", "-7.85e-9", "210000.0", "-1.0e-7")
    check("음수 재료 rc=0", rc == 0, out[-250:])
    check("*MAT_ELASTIC 데이터 줄을 찾았다", len(f) >= 4, str(f))
    if len(f) >= 4:
        # 칸 1=mid, 2=ro, 3=e, 4=pr
        check("ro 의 음수 부호가 살아 있다", f[1].strip().startswith("-"), repr(f[1]))
        check("pr 의 음수 부호가 살아 있다", f[3].strip().startswith("-"), repr(f[3]))
        check("각 칸이 정확히 10자다", all(len(x) == 10 for x in f[:4]),
              [len(x) for x in f[:4]])

    rc, out, f = gen("gbig", "-7.85e-9", "12345678.0", "0.3")
    check("큰 E 값 rc=0", rc == 0, out[-250:])
    if len(f) >= 3:
        # `.23457e+07`(앞 1 을 버린 것)이 아니라 값이 보존돼야 한다
        check("E 가 1.2e7 규모로 보존된다(앞자리를 안 버린다)",
              not f[2].strip().startswith("."), repr(f[2]))
        try:
            v = float(f[2].strip())
            check("E 값이 12345678 의 1%% 안에 있다", abs(v - 12345678.0) / 12345678.0 < 0.01,
                  "v=%r" % v)
        except ValueError:
            check("E 칸이 숫자로 읽힌다", False, repr(f[2]))


def main():
    if len(sys.argv) < 2:
        print("usage: test_fixed_width_overflow.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2
    negative_dt2ms(binary)
    positive_still_works(binary)
    generate_material_fields(binary)
    print("")
    if FAILS:
        print("FAIL %d" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
