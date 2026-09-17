# KooRemapper help 사례를 실제 바이너리로 돌려 검증 — spec 직접 실행 또는 `help <op>` 출력 파싱
"""
사용
  python3 tools/help/run_help_examples.py <KooRemapper 바이너리> [--from-help] [op ...]

  기본        tools/help/ops_help.py 의 사례를 그대로 실행 (C++ 반영 전 사례 자체 검증)
  --from-help 바이너리의 `help <op>` 출력에서 사례 블록을 파싱해 실행 (help 에 찍힌 그대로 돌아가는지)
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from ops_help import OPS  # noqa: E402


def parse_help_example(text):
    """help 출력의 사례 블록 → (files, cmds). `--- 파일: name ---` 뒤 내용, `$ KooRemapper ...` 명령."""
    files, cmds, cur, in_ex = {}, [], None, False
    for line in text.splitlines():
        if line.startswith("-----8<----- 여기부터"):
            in_ex = True
            continue
        if line.startswith("-----8<----- 여기까지"):
            in_ex = False
            cur = None
            continue
        if not in_ex:
            continue
        if line.startswith("--- 파일: ") and line.endswith(" ---"):
            cur = line[len("--- 파일: "):-4]
            files[cur] = ""
            continue
        if line.startswith("$ "):
            cur = None
            cmds.append(line[2:])
            continue
        if cur is not None:
            files[cur] += line + "\n"
    return files, cmds


def _part_mid_zero(path):
    """*PART 카드의 MID 칸(21~30)이 0/공백인 파트가 있으면 True — 해석 불가 덱을 '성공'으로 넘기지 않기 위함."""
    lines = open(path, errors="replace").read().splitlines()
    i = 0
    while i < len(lines):
        if lines[i].upper().startswith("*PART") and not lines[i].upper().startswith("*PART_"):
            j = i + 2 if not lines[i].upper().startswith("*PART_") else i + 1
            while j < len(lines) and lines[j].startswith("$"):
                j += 1
            if j < len(lines) and not lines[j].startswith("*"):
                card = lines[j]
                mid = card[20:30].strip() if "," not in card else (card.split(",") + ["", "", ""])[2].strip()
                if mid in ("", "0"):
                    return True
        i += 1
    return False


def run_case(binary, spec, files, cmds, keep):
    tmp = tempfile.mkdtemp(prefix=f"krhelp_{spec['name']}_")
    for need in spec["needs"]:
        dst = os.path.join(tmp, need)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        src_dir = os.path.dirname(os.path.join(ROOT, need))
        # 필요한 파일이 속한 예제 폴더 통째로 (참조 파일 동반)
        shutil.copytree(src_dir, os.path.dirname(dst), dirs_exist_ok=True)
    # 사례의 SIF 경로(/opt/kooremapper)를 검증 대상 바이너리 설치 위치로 바꿔 쓴다
    prefix = os.path.dirname(os.path.dirname(binary))
    for name, content in files.items():
        with open(os.path.join(tmp, name), "w") as f:
            f.write(content.replace("/opt/kooremapper/", prefix + "/"))
    log = []
    for c in cmds:
        argv = c.split()
        assert argv[0] == "KooRemapper", c
        p = subprocess.run([binary] + argv[1:], cwd=tmp, capture_output=True, text=True, timeout=600)
        log.append((c, p.returncode, (p.stdout + p.stderr)[-600:]))
        if p.returncode != 0:
            return False, f"rc={p.returncode} @ {c}\n{log[-1][2]}", tmp
        errs = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("[ERROR]")]
        if errs:
            return False, f"[ERROR] 출력 @ {c}: {errs[:2]}", tmp
    missing = [o for o in spec["outputs"] if not os.path.exists(os.path.join(tmp, o))]
    if missing:
        return False, f"산출물 없음 {missing}; 폴더={sorted(os.listdir(tmp))[:15]}", tmp
    bad = [o for o in spec["outputs"] if o.endswith(".k") and _part_mid_zero(os.path.join(tmp, o))]
    if bad:
        return False, f"*PART mid=0 (재질 없음) {bad}", tmp
    if not keep:
        shutil.rmtree(tmp, ignore_errors=True)
    return True, "", tmp


def _gmsh_available(binary):
    """meshfix 사례 실행 가능 여부 — KOOREMAPPER_GMSH, 바이너리 옆 gmsh/gmsh(.exe), /opt 의 gmsh.
    바이너리 옆 번들을 보지 않아 플랫폼 배치(bin/gmsh/gmsh.exe)에서 meshfix 가 조용히 건너뛰어졌다."""
    env = os.environ.get("KOOREMAPPER_GMSH")
    if env and os.path.isfile(env):
        return True
    bindir = os.path.dirname(os.path.realpath(binary))
    if any(os.path.isfile(os.path.join(bindir, "gmsh", n)) for n in ("gmsh", "gmsh.exe")):
        return True
    import glob
    return bool(glob.glob("/opt/gmsh-*/bin/gmsh"))


def main():
    args = sys.argv[1:]
    binary = os.path.abspath(args.pop(0))
    from_help = "--from-help" in args
    keep = "--keep" in args
    only = [a for a in args if not a.startswith("--")]
    fails, skipped = [], []
    for spec in OPS:
        if only and spec["name"] not in only:
            continue
        if spec["name"] == "meshfix" and not _gmsh_available(binary):
            skipped.append(spec["name"])
            continue
        if from_help:
            out = subprocess.run([binary, "help", spec["name"]], capture_output=True, text=True).stdout
            files, cmds = parse_help_example(out)
            if spec["cmds"] and not cmds:
                fails.append((spec["name"], "help 출력에 사례 블록 없음"))
                print(f"  {spec['name']:16s} FAIL help 사례 없음")
                continue
        else:
            files, cmds = spec["files"], spec["cmds"]
        if not cmds:
            print(f"  {spec['name']:16s} (사례 없음)")
            continue
        ok, why, tmp = run_case(binary, spec, files, cmds, keep)
        print(f"  {spec['name']:16s} {'OK' if ok else 'FAIL'} {'' if ok else why[:300]}")
        if not ok:
            fails.append((spec["name"], why))
    print(f"\n건너뜀(실행 환경 의존): {skipped}")
    if fails:
        print(f"FAIL {len(fails)} 건: {[f[0] for f in fails]}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
