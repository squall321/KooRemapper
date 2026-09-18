# 출력 정리·최상위 키·중첩 목록·층 키 대칭 회귀 시험 — 빌드 바이너리로 실제 실행해 확인
"""
사용: python3 tools/regress/test_g1_guards.py <KooRemapper 바이너리>

배경(감사에서 재현된 결함)
  - A18 nan 정리가 <prefix>.k 만 지우고 같이 써진 <prefix>.dynain 은 남겼다. "출력 파일을 지웠습니다"
        라고 말하면서 nan 초기응력이 든 dynain 이 디스크에 남아, 사용자는 그걸 멀쩡한 파일로 오해했다.
  - A20 operations 블록이 끝난 뒤 모르는 최상위 키(notes/tags 등)가 오면 section 이 OPERATIONS 로 남아,
        그 아래 열 0 의 '- ' 줄이 유령 operation 으로 조용히 실행됐다(rc=0 인데 덱이 달라졌다).
        type 없이 만들어진 op 은 초기화되지 않은 채 실행돼 내용 없는 '[ERROR]' 한 줄로 끝났다.
  - A36 목록 항목 안에 중첩 매핑(gauss:)이 있으면 그 다음 형제 항목 대시를 들여쓰기 오류로 보고
        정상 YAML 을 rc=1 로 거부했다(메시지도 'YAML 로 읽을 수 없는 파일' 이라고 단정했다).
  - A16 assemble 의 층 대시 줄 파서가 thickness/title 만 읽어, 단독 restack 과 같은 YAML 이 다른 덱을 냈다
        (대시 줄 '- num_elements: 4', 따옴표 한 줄 material_card).
        카드 값은 키워드 줄만으로는 MID 를 쓸 자리가 없어 이제 rc=1 이므로, 데이터 줄까지 담은
        한 줄 카드로 A16 의 의도(따옴표 한 줄 카드도 층 카드로 들어간다)를 확인한다.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAILS = []

BOX = ("output: flat.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\n"
       "pid: 1\nmid: 1\nsecid: 1\n")

RESTACK_DASH_BODY = """target_pid: 1
direction: z
element_type: solid
layers:
  - num_elements: 4
    thickness: 0.7
    title: Glass_Top
    material_card: |
      *MAT_ELASTIC
               @MID@   2.5E-9     71000      0.23
  - num_elements: 2
    thickness: 0.3
    title: Adhesive
    material_card: "*MAT_ELASTIC\\n           @MID@   1.0E-9      3000      0.35"
"""


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def write(d, name, body):
    open(os.path.join(d, name), "w").write(body)
    return name


def read(d, name):
    return open(os.path.join(d, name)).read()


def exists(d, name):
    return os.path.exists(os.path.join(d, name))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="g1_guards_")
    write(d, "box.yaml", BOX)
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    if rc != 0:
        print("생성 실패:", out[-400:])
        return 2

    # ── A18: nan 이면 .k 도 .dynain 도 만들지 않는다 ───────────────────────────
    print("[A18] nan 결과는 .k·.dynain 어느 쪽도 파일이 되지 않는다")
    bend = ("model: flat.k\noutput: %s\nmaterial:\n  E: 210000\n  nu: 0.3\n"
            "target_pid: 1\nplane: xy\nmode: deform\nsource: formula\nexpression: %s\n")
    write(d, "bok.yaml", bend % ("bok", "0.01*x1"))
    rc, out = run(binary, d, "bend", "bok.yaml")
    check("bend 정상: .k 와 .dynain 이 둘 다 나온다 (rc=0)",
          rc == 0 and exists(d, "bok.k") and exists(d, "bok.dynain"), f"rc={rc} {out[-200:]}")
    # 그물이 '쓰기 전' 으로 올라간 뒤로는 나쁜 결과가 파일이 된 적이 없다 — 새 이름으로 돌리면
    # .k 도 .dynain 도 만들어지지 않고(A18 이 막으려던 'nan 초기응력이 든 dynain' 이 애초에 없다),
    # 같은 이름으로 돌려도 이번 실행이 쓰지 않은 지난 결과는 지우지 않는다.
    write(d, "bnan.yaml", bend % ("bnan", "sqrt(-x1)"))
    rc, out = run(binary, d, "bend", "bnan.yaml")
    check("bend nan: rc=1", rc == 1, f"rc={rc} {out[-250:]}")
    check("bend nan: .k 가 만들어지지 않는다", not exists(d, "bnan.k"))
    check("bend nan: nan 초기응력이 든 .dynain 도 만들어지지 않는다", not exists(d, "bnan.dynain"),
          "dynain 이 만들어졌다")
    check("bend nan: 쓰지 않은 파일 이름을 메시지에 적는다", "bnan.dynain" in out and "bnan.k" in out,
          out[-250:])
    prev_k, prev_dyn = read(d, "bok.k"), read(d, "bok.dynain")
    write(d, "bnan2.yaml", bend % ("bok", "sqrt(-x1)"))
    rc, out = run(binary, d, "bend", "bnan2.yaml")
    check("bend nan: 같은 이름의 지난 결과는 지우지 않는다",
          rc == 1 and read(d, "bok.k") == prev_k and read(d, "bok.dynain") == prev_dyn,
          f"rc={rc} {out[-250:]}")

    # 이번에 쓰지 않은 남의 파일은 건드리지 않는다
    write(d, "cv.yaml", "model: flat.k\noutput: cv\ntype: hex20\ntarget_pid: 1\n")
    write(d, "cv.dynain", "USER DATA\n")
    rc, out = run(binary, d, "convert", "cv.yaml")
    check("convert: dynain 을 쓰지 않는 op 은 옆의 .dynain 을 건드리지 않는다",
          rc == 0 and read(d, "cv.dynain") == "USER DATA\n", f"rc={rc} {out[-200:]}")

    # ── A36: 목록 항목 안의 중첩 매핑 ────────────────────────────────────────
    print("[A36] 목록 항목 안에 중첩 매핑이 있어도 정상 YAML 로 읽는다")
    shutil.copy(os.path.join(ROOT, "examples", "iga", "block_2x2x1.k"), d)
    write(d, "nest.yaml", """model: block_2x2x1.k
output: nest_out
operations:
  - type: iga
    targets:
      - target_pid: 1
        element_size: 4.0
        gauss:
          ir: 0
      - target_pid: 2
        element_size: 4.0
""")
    rc, out = run(binary, d, "iga", "nest.yaml")
    check("iga: 중첩 매핑이 든 targets 목록을 거부하지 않는다 (rc=0)", rc == 0, f"rc={rc} {out[-250:]}")
    check("iga: 두 타겟이 모두 살아 패치 파일 2개",
          exists(d, "nest_out_iga_p1.k") and exists(d, "nest_out_iga_p2.k"), out[-250:])
    check("iga: 성공한 실행의 부수 파일은 지워지지 않는다",
          exists(d, "nest_out.k") and exists(d, "nest_out_iga_p1.k"))
    # 진짜로 어긋난 대시는 그대로 거부하되 'YAML 로 읽을 수 없다' 고 단정하지 않는다
    write(d, "mixed.yaml", "model: flat.k\noutput: mixedout\noperations:\n"
                           "  - type: quad8\n    target_pid: 1\n"
                           "    - type: tria6\n      target_pid: 1\n")
    rc, out = run(binary, d, "convert", "mixed.yaml")
    check("convert: 정말 어긋난 대시는 여전히 rc=1", rc == 1 and "들여쓰기" in out, f"rc={rc} {out[-250:]}")
    check("convert: 'YAML 로 읽을 수 없는 파일' 이라는 단정은 하지 않는다",
          "YAML 로 읽을 수 없는" not in out, out[-250:])

    # ── A20: operations 뒤의 모르는 최상위 키 ────────────────────────────────
    print("[A20] operations 가 끝난 뒤의 열 0 대시는 operation 이 아니다")
    plain = "base_model: flat.k\noutput: %s\n\noperations:\n  - type: tet10\n"
    write(d, "plain.yaml", plain % "plain_out")
    rc, out = run(binary, d, "assemble", "plain.yaml")
    check("assemble: 기준 설정 실행 (rc=0)", rc == 0, f"rc={rc} {out[-250:]}")
    write(d, "ghost.yaml", (plain % "ghost_out") + "\ntags:\n- type: hex20\n")
    rc, out = run(binary, d, "assemble", "ghost.yaml")
    check("assemble: 모르는 최상위 키 뒤 대시는 실행되지 않는다 (Operation 1/1)",
          rc == 0 and "Operation 1/1" in out and "Operation 2/" not in out, f"rc={rc} {out[-300:]}")
    check("assemble: 유령 op 이 없으니 덱이 기준과 같다",
          exists(d, "ghost_out.k") and read(d, "ghost_out.k") == read(d, "plain_out.k"),
          "덱이 달라졌다")

    # type 없는 항목은 빈 [ERROR] 가 아니라 내용 있는 메시지로 거절한다
    write(d, "notype.yaml", "base_model: flat.k\noutput: notype_out\noperations:\n  - thickness: 99.0\n")
    rc, out = run(binary, d, "assemble", "notype.yaml")
    err = [ln for ln in out.splitlines() if "[ERROR]" in ln]
    check("assemble: type 없는 operations 항목은 rc=1", rc == 1, f"rc={rc} {out[-250:]}")
    check("assemble: [ERROR] 줄에 내용이 있다",
          bool(err) and err[-1].split("[ERROR]", 1)[1].strip() != "", str(err))
    check("assemble: 반쪽 출력이 남지 않는다", not exists(d, "notype_out.k"))

    # ── A16: 층 대시 줄 키가 단독·assemble 에서 같다 ─────────────────────────
    print("[A16] 층 대시 줄의 키를 두 경로가 같게 읽는다")
    write(d, "rs_sa.yaml", "model: flat.k\noutput: rs_sa\n" + RESTACK_DASH_BODY)
    write(d, "rs_asm.yaml", "base_model: flat.k\noutput: rs_asm\noperations:\n  - type: restack\n" +
          "".join("    " + ln + "\n" for ln in RESTACK_DASH_BODY.splitlines()))
    rc1, o1 = run(binary, d, "restack", "rs_sa.yaml")
    rc2, o2 = run(binary, d, "assemble", "rs_asm.yaml")
    ok = rc1 == 0 and rc2 == 0 and exists(d, "rs_sa.k") and exists(d, "rs_asm.k")
    check("restack 단독·assemble 둘 다 rc=0 (대시 줄 첫 키가 num_elements)", ok,
          f"rc={rc1}/{rc2} {o1[-200:]} {o2[-200:]}")
    if ok:
        check("두 덱이 완전히 같다 (num_elements·한 줄 material_card 포함)",
              read(d, "rs_sa.k") == read(d, "rs_asm.k"), "덱이 다르다")
        check("한 줄 material_card 도 층 카드로 들어간다",
              read(d, "rs_sa.k").count("*MAT_ELASTIC") >= 2,
              str(read(d, "rs_sa.k").count("*MAT_ELASTIC")))

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
