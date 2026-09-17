# iga targets 의 target_pids 목록(여러 PID 에 같은 설정) 회귀 시험 — 빌드 바이너리로 저장소 예제를 실제 실행
"""
사용: python3 tools/regress/test_iga_target_pids.py <KooRemapper 바이너리>

배경
  v1.3.1 에서 추가된 target_pids: [1, 2] 가 리팩터링 때 파싱·펼침이 빠져,
  examples/iga/iga_multipid.yaml 이 'iga target 1 requires either target_pid or target_name' 으로 실패했다.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAILS = []


def check(name, cond, detail=""):
    print("  %-60s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def main():
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="iga_pids_")
    for f in ("iga_multipid.yaml", "block_2x2x1.k"):
        shutil.copy(os.path.join(ROOT, "examples", "iga", f), d)

    open(os.path.join(d, "mixed.yaml"), "w").write("""base_model: block_2x2x1.k
output: mixed
operations:
  - type: iga
    targets:
      - target_pid: 1
        element_size: 4.0
      - element_size: 4.0
        target_pids: 2
""")
    # 단독 iga 명령은 v1.3.1 파서를 그대로 가져 동작했고, assemble 경로 reader 만 빠져 있었다 — 두 경로 모두 본다
    for cmd in ("iga", "assemble"):
        print(f"[iga target_pids — {cmd}]")
        for f in os.listdir(d):
            if f.endswith(".k") and f != "block_2x2x1.k":
                os.remove(os.path.join(d, f))
        p = subprocess.run([binary, cmd, "iga_multipid.yaml"], cwd=d, capture_output=True, text=True, timeout=300)
        check(f"{cmd}: examples/iga/iga_multipid.yaml 실행 성공", p.returncode == 0, (p.stdout + p.stderr)[-400:])
        for pid in (1, 2):
            check(f"{cmd}: target_pids 의 PID {pid} 에 IGA 패치 파일 생성",
                  os.path.exists(os.path.join(d, f"iga_multipid_result_iga_p{pid}.k")))
        p = subprocess.run([binary, cmd, "mixed.yaml"], cwd=d, capture_output=True, text=True, timeout=300)
        check(f"{cmd}: target_pid 단수 항목 + 하위 키 target_pids 항목 혼용", p.returncode == 0 and all(
            os.path.exists(os.path.join(d, f"mixed_iga_p{pid}.k")) for pid in (1, 2)), (p.stdout + p.stderr)[-400:])

    print()
    if FAILS:
        print(f"FAIL {len(FAILS)} 건")
        for f in FAILS:
            print("  -", f)
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
