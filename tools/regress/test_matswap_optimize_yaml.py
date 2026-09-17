# matswap·optimize YAML 파서 회귀 시험(블록 목록·YAML 폴더 상대 경로·pid 숫자 검증) — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_matswap_optimize_yaml.py <KooRemapper 바이너리>

배경
  - matswap 의 swap 항목 안에서 'pids:'/'mids:' 뒤에 오는 '- 1' 블록 목록이 읽히지 않았다. 그 줄이 새 swap
    항목으로 세어져 'Swaps : 3' 이 찍히고, 정작 첫 항목은 대상이 비어 'no target PIDs' 로 끝났다.
  - matswap 은 configDir(YAML 폴더)를 bundle 에만 썼다. 저장소 루트에서
    'KooRemapper matswap examples/matswap/01_single_pid.yaml' 을 돌리면 model 을 현재 폴더에서 찾아 실패했다.
  - matswap·optimize 의 단수 'pid:'(matswap 은 'mid:' 도) 는 try/catch 밖 stoi 라, 숫자가 아니면
    '[ERROR] Unhandled error: stoi' 라는 뜻 모를 메시지로 끝났다.
  - optimize 의 목록 키는 'pids' 하나뿐이며 블록·인라인 둘 다 되는지 함께 지킨다.
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
MATSWAP_DIR = os.path.join(REPO, "examples", "matswap")


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def workdir(prefix):
    """examples/matswap 의 two_cubes.k(PID 1,2)·rubber.k 번들을 복사한 임시 폴더."""
    d = tempfile.mkdtemp(prefix=prefix)
    for f in ("two_cubes.k", "rubber.k"):
        shutil.copy(os.path.join(MATSWAP_DIR, f), d)
    return d


def write(d, name, body):
    path = os.path.join(d, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(body)
    return path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])

    print("[matswap: swap 항목 안의 블록 목록]")
    d = workdir("matswap_block_")
    write(d, "blk_pids.yaml",
          "model: two_cubes.k\noutput: blk_pids.k\nswaps:\n  - bundle: rubber.k\n    pids:\n      - 1\n      - 2\n")
    rc, out = run(binary, d, "matswap", "blk_pids.yaml")
    check("matswap: 'pids:' 블록 목록이 새 swap 항목으로 세어지지 않음 (Swaps : 1)",
          "[matswap] Swaps  : 1" in out, f"rc={rc} {out[-300:]}")
    check("matswap: 'pids:' 블록 목록의 PID 2개가 실제로 교체됨 (rc=0)",
          rc == 0 and "2 part(s) swapped" in out and os.path.exists(os.path.join(d, "blk_pids.k")),
          f"rc={rc} {out[-300:]}")

    write(d, "blk_mids.yaml",
          "model: two_cubes.k\noutput: blk_mids.k\nswaps:\n  - bundle: rubber.k\n    mids:\n      - 1\n      - 2\n")
    rc, out = run(binary, d, "matswap", "blk_mids.yaml")
    check("matswap: 'mids:' 블록 목록도 같은 항목의 대상으로 읽힘 (rc=0, 2 part)",
          rc == 0 and "2 part(s) swapped" in out, f"rc={rc} {out[-300:]}")

    write(d, "blk_cmt.yaml",
          "model: two_cubes.k\noutput: blk_cmt.k\nswaps:\n  - bundle: rubber.k\n    pids:\n"
          "      - 1   # 첫 파트\n      - 2   # 둘째 파트\n")
    rc, out = run(binary, d, "matswap", "blk_cmt.yaml")
    check("matswap: 블록 목록 항목의 인라인 '#' 주석 무시 (rc=0, 2 part)",
          rc == 0 and "2 part(s) swapped" in out, f"rc={rc} {out[-300:]}")

    write(d, "blk_two.yaml",
          "model: two_cubes.k\noutput: blk_two.k\nswaps:\n  - bundle: rubber.k\n    pids:\n      - 1\n"
          "  - bundle: rubber.k\n    pids:\n      - 2\n")
    rc, out = run(binary, d, "matswap", "blk_two.yaml")
    check("matswap: 블록 목록 뒤의 다음 swap 항목은 그대로 항목으로 읽힘 (Swaps : 2)",
          rc == 0 and "[matswap] Swaps  : 2" in out, f"rc={rc} {out[-300:]}")

    print("[matswap: 인라인 목록 유지]")
    write(d, "inl_pids.yaml",
          "model: two_cubes.k\noutput: inl_pids.k\nswaps:\n  - bundle: rubber.k\n    pids: [1, 2]\n")
    rc, out = run(binary, d, "matswap", "inl_pids.yaml")
    check("matswap: 인라인 'pids: [1, 2]' 여전히 동작 (rc=0, 2 part)",
          rc == 0 and "2 part(s) swapped" in out, f"rc={rc} {out[-300:]}")

    print("[matswap: YAML 폴더 기준 상대 경로]")
    r = tempfile.mkdtemp(prefix="matswap_dir_")
    sub = os.path.join(r, "sub")
    os.makedirs(sub)
    for f in ("two_cubes.k", "rubber.k"):
        shutil.copy(os.path.join(MATSWAP_DIR, f), sub)
    write(r, os.path.join("sub", "rel.yaml"),
          "model: two_cubes.k\noutput: rel_out.k\nswaps:\n  - bundle: rubber.k\n    pid: 1\n")
    rc, out = run(binary, r, "matswap", "sub/rel.yaml")
    check("matswap: model/output 을 YAML 폴더 기준으로 해석 (bundle 과 동일)",
          rc == 0 and os.path.exists(os.path.join(sub, "rel_out.k")), f"rc={rc} {out[-300:]}")

    write(r, os.path.join("sub", "abs.yaml"),
          "model: " + os.path.join(sub, "two_cubes.k") + "\noutput: " + os.path.join(r, "abs_out.k") +
          "\nswaps:\n  - bundle: rubber.k\n    pid: 1\n")
    rc, out = run(binary, r, "matswap", "sub/abs.yaml")
    check("matswap: 절대 경로 model/output 은 configDir 를 붙이지 않음",
          rc == 0 and os.path.exists(os.path.join(r, "abs_out.k")), f"rc={rc} {out[-300:]}")

    print("[matswap: 숫자가 아닌 pid/mid]")
    for name, body in (
        ("dash", "model: two_cubes.k\noutput: bad_dash.k\nswaps:\n  - pid: abc\n    bundle: rubber.k\n"),
        ("sub",  "model: two_cubes.k\noutput: bad_sub.k\nswaps:\n  - bundle: rubber.k\n    pid: abc\n"),
        ("top",  "model: two_cubes.k\noutput: bad_top.k\nbundle: rubber.k\npid: abc\n"),
    ):
        write(d, f"bad_{name}.yaml", body)
        rc, out = run(binary, d, "matswap", f"bad_{name}.yaml")
        check(f"matswap: 'pid: abc' ({name}) 가 키 이름을 밝히는 오류 (stoi 아님)",
              rc == 1 and "'pid' must be an integer" in out and "Unhandled error" not in out,
              f"rc={rc} {out[-300:]}")

    write(d, "bad_mid.yaml",
          "model: two_cubes.k\noutput: bad_mid.k\nswaps:\n  - bundle: rubber.k\n    mid: xyz\n")
    rc, out = run(binary, d, "matswap", "bad_mid.yaml")
    check("matswap: 'mid: xyz' 도 키 이름을 밝히는 오류 (stoi 아님)",
          rc == 1 and "'mid' must be an integer" in out and "Unhandled error" not in out,
          f"rc={rc} {out[-300:]}")

    print("[optimize: 목록 키(pids)와 pid 숫자 검증]")
    write(d, "opt_blk.yaml",
          "model: two_cubes.k\noutput: opt_blk.k\noptimize: rubber\npids:\n  - 1\n  - 2\n")
    rc, out = run(binary, d, "optimize", "opt_blk.yaml")
    check("optimize: 'pids:' 블록 목록 (PIDs : 1, 2)",
          rc == 0 and "[optimize] PIDs   : 1, 2" in out, f"rc={rc} {out[-300:]}")

    write(d, "opt_inl.yaml",
          "model: two_cubes.k\noutput: opt_inl.k\noptimize: rubber\npids: [1, 2]\n")
    rc, out = run(binary, d, "optimize", "opt_inl.yaml")
    check("optimize: 인라인 'pids: [1, 2]' 여전히 동작 (PIDs : 1, 2)",
          rc == 0 and "[optimize] PIDs   : 1, 2" in out, f"rc={rc} {out[-300:]}")

    write(d, "opt_bad.yaml",
          "model: two_cubes.k\noutput: opt_bad.k\noptimize: rubber\npid: abc\n")
    rc, out = run(binary, d, "optimize", "opt_bad.yaml")
    check("optimize: 'pid: abc' 가 키 이름을 밝히는 오류 (stoi 아님)",
          rc == 1 and "'pid' must be an integer" in out and "Unhandled error" not in out,
          f"rc={rc} {out[-300:]}")

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
