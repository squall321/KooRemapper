# ale 목록 파싱·meshfix gmsh 호출 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_ale_meshfix_yaml.py <KooRemapper 바이너리> [gmsh 실행 파일]

배경
  - ale: 'ale_parts:' 아래 '-' 만 있는 줄(키는 다음 줄부터 들여쓰기)은 콜론이 없다고 버려져,
    뒤따르는 pid/material 이 앞 항목을 덮어썼다 — 항목 두 개가 하나로 합쳐진 모델이 오류 없이 나왔다.
    'fsi_pids:' 아래 같은 모양은 목록이 통째로 비어 FSI 커플링이 조용히 빠졌다.
  - ale: 항목의 첫 키가 pid 가 아닌 '- material: ...' 순서, 블록형 fsi_pids('- 1'), detonation 블록이
    계속 동작하는지도 함께 묶어 둔다(예전 수정이 지켜지는지 확인).
  - meshfix: 윈도 .bat 분기는 경로를 그냥 "..." 로 감싸 공백·%·& 가 든 경로에서 명령이 어긋났다
    (POSIX 분기는 작은따옴표로 이미 안전). 여기서 윈도를 돌릴 수 없어 소스 점검으로 확인한다.
  - meshfix: bbox 코너가 음수인 모델에서 크기장 식이 '(y--1.000000e+01)' 로 나와 gmsh 가 MathEval 을
    버렸다 — gmsh 래퍼로 .geo 와 로그를 보존해 '--' 와 matheval 파싱 오류가 없는지 본다.
  - gmsh 경로를 주지 않으면 KOOREMAPPER_TEST_GMSH, 저장소 dist/gmsh/gmsh 순으로 찾고 없으면 건너뛴다.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args, env=None):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True,
                       timeout=900, env=env)
    return p.returncode, p.stdout + p.stderr


def ale_run(binary, d, name, body):
    open(os.path.join(d, name + ".yaml"), "w").write(body)
    return run(binary, d, "ale", name + ".yaml")


def test_ale(binary):
    d = tempfile.mkdtemp(prefix="ale_yaml_")
    shutil.copy(os.path.join(REPO, "examples", "ale", "explicit.k"), d)

    print("[ale: '-' 만 있는 목록 항목]")
    rc, out = ale_run(binary, d, "bare", (
        "model: explicit.k\noutput: bare_out.k\n"
        "ale_parts:\n"
        "  -\n    pid: 3\n    material: air\n"
        "  -\n    pid: 4\n    material: water\n"
        "fsi_pids: [1, 2]\n"
        "elform: 12\n"))
    check("ale_parts: '-' 뒤 항목 두 개가 따로 잡힘 (합쳐지지 않음)",
          rc == 0 and "ALE PIDs : 3 (air), 4 (water)" in out, f"rc={rc} {out[-300:]}")
    check("ale_parts: AMMG 그룹 수가 항목 수와 같음 (2 groups)",
          "*ALE_MULTI-MATERIAL_GROUP (2 groups)" in out, out[-300:])
    check("ale_parts: 목록 뒤의 최상위 키(elform)도 그대로 읽힘",
          "ELFORM -> 12" in out, out[-300:])
    check("ale_parts: 같은 YAML 의 fsi_pids 도 유지",
          "FSI PIDs : 1, 2" in out, out[-300:])

    print("[ale: 첫 키가 pid 가 아닌 항목 / 블록형 fsi_pids / detonation]")
    rc, out = ale_run(binary, d, "matfirst", (
        "model: explicit.k\noutput: matfirst_out.k\n"
        "ale_parts:\n"
        "  - material: air\n    pid: 3\n"
        "  - material: water\n    pid: 4\n"))
    check("ale_parts: '- material:' 로 시작한 항목도 받아들임",
          rc == 0 and "ALE PIDs : 3 (air), 4 (water)" in out, f"rc={rc} {out[-300:]}")

    rc, out = ale_run(binary, d, "fsiblock", (
        "model: explicit.k\noutput: fsiblock_out.k\n"
        "ale_parts:\n  - pid: 3\n    material: air\n"
        "fsi_pids:\n  - 1   # 판\n  - 2\n"))
    check("fsi_pids: 블록형 '- 1' 유지 (주석 붙은 항목 포함)",
          rc == 0 and "FSI PIDs : 1, 2" in out, f"rc={rc} {out[-300:]}")
    check("fsi_pids: 블록형에서도 *CONSTRAINED_LAGRANGE_IN_SOLID 생성",
          "*CONSTRAINED_LAGRANGE_IN_SOLID x2" in out, out[-300:])

    rc, out = ale_run(binary, d, "fsibare", (
        "model: explicit.k\noutput: fsibare_out.k\n"
        "ale_parts:\n  - pid: 3\n    material: air\n"
        "fsi_pids:\n  -\n    1\n  -\n    2\n"))
    check("fsi_pids: '-' 만 있는 항목의 값(다음 줄)도 읽음",
          rc == 0 and "FSI PIDs : 1, 2" in out, f"rc={rc} {out[-300:]}")

    rc, out = ale_run(binary, d, "det", (
        "model: explicit.k\noutput: det_out.k\n"
        "ale_parts:\n  -\n    pid: 5\n    material: tnt\n"
        "detonation:\n  pid: 5\n  x: 100.0\n  y: 50.0\n  z: 0.0\n  lt: 0.0\n"))
    check("detonation: '-' 만 있는 목록 뒤에서도 블록이 읽힘",
          rc == 0 and "*INITIAL_DETONATION (PID=5)" in out, f"rc={rc} {out[-300:]}")
    check("detonation: 기폭점이 있으면 HE 경고가 나오지 않음",
          "no 'detonation:' section" not in out, out[-300:])
    shutil.rmtree(d, ignore_errors=True)


def test_meshfix_source():
    """윈도 분기는 여기서 실행할 수 없다 — 소스에서 인용 규칙만 확인한다(바이너리와 무관)."""
    print("[meshfix: 윈도 .bat 인용 규칙 (소스 점검)]")
    src_path = os.path.join(REPO, "src", "commands", "meshfix.cpp")
    if not os.path.isfile(src_path):
        print(f"  SKIP: 소스 없음 ({src_path})")
        return
    src = open(src_path, encoding="utf-8").read()
    bat_body = src[src.find("std::ofstream bat("):src.find("int ret = std::system(cmd.c_str());")]
    check("bat 명령줄이 batQuote 로 감싸짐 (맨손 \" 조립 아님)",
          "batQuote(gmshNative)" in bat_body and "batQuote(geoNative)" in bat_body
          and "batQuote(logNative)" in bat_body and '<< "\\""' not in bat_body,
          bat_body[:200])
    check("배치 안의 % 는 %% 로 escape",
          re.search(r"if \(c == '%'\) q \+= \"%%\";", src) is not None)
    check("\" · 줄바꿈이 든 경로는 실행 전에 거부 (batUnsafe)",
          "batUnsafe(gmshNative)" in src and "batUnsafe(batPath)" in src)
    check("cmd /c 는 따옴표 두 겹으로 호출 (& ( ) ^ 가 든 경로 보호)",
          '"cmd /c \\"\\"" + batPath + "\\"\\""' in src)
    check("POSIX 분기는 그대로 shQuote 사용",
          "shQuote(gmshExe) + \" \" + shQuote(geoPath)" in src)

    print("[meshfix: 크기장 식의 음수 코너 (소스 점검)]")
    # 8코너·박판 4코너 두 분기 모두 mf_axisMinus 로 부호를 접어야 한다
    nx = src.count('mf_axisMinus("x"')
    ny = src.count('mf_axisMinus("y"')
    nz = src.count('mf_axisMinus("z"')
    check("두 크기장 분기 모두 mf_axisMinus 로 코너 좌표를 조립",
          nx == 2 and ny == 2 and nz == 2, f"x={nx} y={ny} z={nz}")


def test_meshfix_gmsh(binary, gmsh):
    print("[meshfix: 음수 bbox 코너 모델의 MathEval 크기장]")
    d = tempfile.mkdtemp(prefix="meshfix_geo_")
    save = os.path.join(d, "save")
    os.makedirs(save)
    # gmsh 래퍼 — meshfix 는 성공하면 .geo/.log 를 지우므로 실행 중에 복사해 둔다
    wrap = os.path.join(d, "wrap.sh")
    open(wrap, "w").write(
        "#!/bin/sh\n"
        f"cp \"$1\" '{save}/saved.geo'\n"
        f"'{gmsh}' \"$@\" 2>&1 | tee -a '{save}/saved.log'\n")
    os.chmod(wrap, 0o755)

    env = dict(os.environ)
    env["KOOREMAPPER_GMSH"] = wrap
    # arc 의 flat tet 모델은 y·z 가 -10 에서 시작한다(= bbox 코너가 음수)
    rc, out = run(binary, d, "generate", "--dim-i", "20", "--dim-j", "5", "arc", "demo")
    open(os.path.join(d, "m.yaml"), "w").write(
        "model: demo_flat_tet.k\noutput: remeshed.k\npid: 1\nlc_target: 5.0\n")
    rc, out = run(binary, d, "meshfix", "m.yaml", env=env)
    check("meshfix: 음수 코너 모델이 정상 종료 (rc=0)",
          rc == 0 and os.path.exists(os.path.join(d, "remeshed.k")), f"rc={rc} {out[-400:]}")

    geo = open(os.path.join(save, "saved.geo"), encoding="utf-8").read() \
        if os.path.exists(os.path.join(save, "saved.geo")) else ""
    field = re.search(r'Field\[1\]\.F = "([^"]*)"', geo)
    check("geo: MathEval 크기장이 실제로 쓰임 (Field[1].F)", field is not None, geo[:200])
    check("geo: 음수 코너가 '+' 로 접힘 ('--' 없음)",
          field is not None and "--" not in field.group(1) and "(y+1.0" in field.group(1),
          (field.group(1)[:200] if field else ""))
    check("geo: 배경 크기장(Field[3])에도 '--' 없음",
          "--" not in geo.replace("// KooRemapper meshfix", ""), geo[:200])

    log = open(os.path.join(save, "saved.log"), encoding="utf-8", errors="replace").read() \
        if os.path.exists(os.path.join(save, "saved.log")) else ""
    bad = [ln for ln in log.splitlines()
           if "matheval" in ln.lower() or "parse error" in ln.lower()]
    check("gmsh 로그에 matheval·parse error 없음", log != "" and not bad, "; ".join(bad[:3]))

    print("[meshfix: 공백·따옴표가 든 경로 (POSIX 셸 인용)]")
    qdir = os.path.join(d, "sp ace's $dir")
    os.makedirs(qdir)
    open(os.path.join(d, "q.yaml"), "w").write(
        "model: %s\noutput: %s\npid: 1\nlc_target: 6.0\n"
        % (os.path.join(d, "demo_flat_tet.k"), os.path.join(qdir, "rm.k")))
    env2 = dict(os.environ)
    env2["KOOREMAPPER_GMSH"] = gmsh
    rc, out = run(binary, d, "meshfix", "q.yaml", env=env2)
    check("meshfix: 출력 폴더 이름에 공백·'·$ 가 있어도 gmsh 실행 성공",
          rc == 0 and os.path.exists(os.path.join(qdir, "rm.k")), f"rc={rc} {out[-400:]}")
    shutil.rmtree(d, ignore_errors=True)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    gmsh = sys.argv[2] if len(sys.argv) > 2 else \
        os.environ.get("KOOREMAPPER_TEST_GMSH") or os.path.join(REPO, "dist", "gmsh", "gmsh")

    test_ale(binary)
    test_meshfix_source()
    if os.path.isfile(gmsh):
        test_meshfix_gmsh(binary, gmsh)
    else:
        print(f"[meshfix] SKIP: gmsh 실행 파일 없음 ({gmsh})")

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
