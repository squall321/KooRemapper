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
