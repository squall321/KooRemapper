# meshfix 의 gmsh 탐색 회귀 시험 — 플랫폼 배치(bin/gmsh/gmsh.exe)에서 바이너리 옆 gmsh 를 찾는지 실제 실행으로 확인
"""
사용: python3 tools/regress/test_gmsh_discovery.py <KooRemapper 바이너리> [gmsh 실행 파일]

배경
  - 2418c22 에서 리눅스 탐색 이름을 gmsh 로만 바꿔, bin/gmsh/gmsh.exe 만 두는 플랫폼·Drive 아티팩트 배치의
    api 컨테이너에서 meshfix 가 'Gmsh not found' 로 실패했다(예전 바이너리는 성공).
  - gmsh 경로를 주지 않으면 KOOREMAPPER_TEST_GMSH, 저장소 dist/gmsh/gmsh 순으로 찾고 없으면 건너뛴다.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FAILS = []


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    gmsh = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("KOOREMAPPER_TEST_GMSH") or os.path.join(REPO, "dist", "gmsh", "gmsh")
    if not os.path.isfile(gmsh):
        print(f"SKIP: gmsh 실행 파일 없음 ({gmsh})")
        return 0

    env = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", "/tmp")}  # 호스트 PATH 의 다른 gmsh 배제
    for name in ("gmsh.exe", "gmsh"):
        print(f"[bin/gmsh/{name} 배치]")
        d = tempfile.mkdtemp(prefix=f"gmshdisc_{name}_")
        os.makedirs(os.path.join(d, "bin", "gmsh"))
        shutil.copy2(binary, os.path.join(d, "bin", "KooRemapper"))
        shutil.copy2(gmsh, os.path.join(d, "bin", "gmsh", name))
        work = os.path.join(d, "work")
        os.makedirs(work)
        exe = os.path.join(d, "bin", "KooRemapper")
        subprocess.run([exe, "generate", "--dim-i", "20", "--dim-j", "5", "arc", "demo"], cwd=work, env=env, capture_output=True)
        open(os.path.join(work, "m.yaml"), "w").write("model: demo_flat_tet.k\noutput: remeshed.k\npid: 1\nlc_target: 5.0\n")
        p = subprocess.run([exe, "meshfix", "m.yaml"], cwd=work, env=env, capture_output=True, text=True, timeout=600)
        out = p.stdout + p.stderr
        check(f"'Gmsh not found' 없음", "Gmsh not found" not in out, out[-300:])
        check(f"바이너리 옆 gmsh/{name} 를 사용", os.path.join("bin", "gmsh", name) in out, out[-300:])
        shutil.rmtree(d, ignore_errors=True)

    # ── 깨진 후보를 집지 않는다 (2026-09-25, P1-2 곁 P1-9) ────────────────────
    # ⚠ 파일이 있다고 gmsh 인 것은 아니다. 이 박스의 `~/.local/bin/gmsh` 는 깨진 파이썬
    # 래퍼인데, 예전 탐색은 **파일 존재만** 보고 그것을 집었다. 그러면 meshfix 가 한참 뒤에
    # `Gmsh failed (exit 32512)` 라는 뜻 모를 코드로 죽는다. 실사용 컨테이너에서도 홈 바인드로
    # 같은 일이 났다(회신 §1②). 이제 후보마다 `--version` 을 실제로 돌려 거른다.
    print("[깨진 래퍼를 집지 않는다]")
    d = tempfile.mkdtemp(prefix="gmshbad_")
    fake = os.path.join(d, "fakebin")
    real = os.path.join(d, "realbin")
    os.makedirs(fake); os.makedirs(real)
    open(os.path.join(fake, "gmsh"), "w").write("#!/usr/bin/env python\nimport nonexistent_module\n")
    os.chmod(os.path.join(fake, "gmsh"), 0o755)
    os.symlink(gmsh, os.path.join(real, "gmsh"))
    work = os.path.join(d, "work"); os.makedirs(work)
    subprocess.run([binary, "generate", "--dim-i", "20", "--dim-j", "5", "arc", "demo"],
                   cwd=work, env=env, capture_output=True)
    open(os.path.join(work, "m.yaml"), "w").write(
        "model: demo_flat_tet.k\noutput: remeshed.k\npid: 1\nlc_target: 5.0\n")

    def run(extra_env, path):
        e = dict(env); e["PATH"] = path + ":/usr/bin:/bin"; e.update(extra_env)
        p = subprocess.run([binary, "meshfix", "m.yaml"], cwd=work, env=e,
                           capture_output=True, text=True, timeout=600)
        return p.stdout + p.stderr

    out = run({}, fake)
    check("깨진 것만 있으면 'not found' 로 거절한다", "Gmsh not found" in out, out[-300:])
    check("무엇을 왜 건너뛰었는지 말한다", "건너뛴 후보" in out and "fakebin" in out, out[-300:])

    out = run({}, fake + ":" + real)
    check("깨진 것 뒤의 진짜 gmsh 를 집는다", "realbin/gmsh" in out, out[-300:])
    check("집은 gmsh 의 버전을 찍는다", "(v" in out, out[-300:])

    # 명시 지정은 **검증하지 않는다.** `--version` 을 돌려 보는 것은 탐색이 우리 마음대로 고른
    # 후보에만 정당하다 — 사람이 지목한 명령을 시험 삼아 돌리면 부작용이 난다. 실제로
    # `test_ale_meshfix_yaml` 이 `KOOREMAPPER_GMSH` 에 gmsh **래퍼**를 주는데, 그 래퍼는
    # `cp "$1" saved.geo` 를 먼저 해서 `--version` 이 `cp --version` 이 된다.
    # 지킬 것은 하나다 — **몰래 다른 것으로 갈아타지 않는다.**
    out = run({"KOOREMAPPER_GMSH": os.path.join(fake, "gmsh")}, real)
    check("KOOREMAPPER_GMSH 를 준 대로 쓴다(몰래 갈아타지 않는다)",
          "fakebin/gmsh" in out and "realbin/gmsh" not in out, out[-300:])
    shutil.rmtree(d, ignore_errors=True)

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
