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


def _mesh_facts(path):
    """k 파일 → (bbox 크기 [dx,dy,dz], 요소 수, 키워드 집합). *NODE 는 고정폭/콤마 둘 다 읽는다."""
    xs, ys, zs, nelem, kws, sect = [], [], [], 0, set(), ""
    for line in open(path, errors="replace"):
        line = line.rstrip("\n")
        if line.startswith("*"):
            sect = line.strip().upper()
            kws.add(sect)
            continue
        if not line.strip() or line.startswith("$"):
            continue
        if sect == "*NODE":
            try:
                f = [t for t in line.split(",")] if "," in line else [line[8:24], line[24:40], line[40:56]]
                if "," in line:
                    f = f[1:4]
                xs.append(float(f[0])); ys.append(float(f[1])); zs.append(float(f[2]))
            except (ValueError, IndexError):
                pass
        elif sect.startswith("*ELEMENT"):
            nelem += 1
    bbox = [max(v) - min(v) for v in (xs, ys, zs)] if xs else None
    return bbox, nelem, kws


def check_invariants(path, inv):
    """선언된 불변식 위반 목록 — rc=0 이어도 결과가 틀린 사례(퇴화 메시 등)를 잡는다."""
    if not os.path.exists(path):
        return ["파일 없음"]
    bbox, nelem, kws = _mesh_facts(path)
    bad = []
    want = inv.get("bbox")
    if want is not None:
        if bbox is None:
            bad.append("절점 없음")
        elif any(abs(g - w) > max(1e-6, abs(w) * 1e-3) for g, w in zip(bbox, want)):
            bad.append("bbox %s != %s" % ([round(v, 4) for v in bbox], want))
    if "elements" in inv and nelem != inv["elements"]:
        bad.append("요소 수 %d != %d" % (nelem, inv["elements"]))
    for kw in inv.get("keywords", []):
        if not any(k.startswith(kw.upper()) for k in kws):
            bad.append("키워드 없음 %s" % kw)
    return bad


def run_case(binary, spec, files, cmds, keep):
    tmp = tempfile.mkdtemp(prefix=f"krhelp_{spec['name']}_")
    for need in spec["needs"]:
        dst = os.path.join(tmp, need)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        src_dir = os.path.dirname(os.path.join(ROOT, need))
        # 필요한 파일이 속한 예제 폴더 통째로 (참조 파일 동반)
        shutil.copytree(src_dir, os.path.dirname(dst), dirs_exist_ok=True)
    # 사례는 컨테이너 밖에서도 그대로 돌아야 한다 — SIF 절대경로(/opt/kooremapper/...)를 치환해 주지
    # 않는다. matdb 사례가 그 경로를 박아 두고 이 치환에 기대 겨우 넘어가고 있었다(지금은 database 생략).
    for name, content in files.items():
        with open(os.path.join(tmp, name), "w") as f:
            f.write(content)
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
    for name, inv in spec.get("invariants", {}).items():
        viol = check_invariants(os.path.join(tmp, name), inv)
        if viol:
            return False, f"불변식 위반 {name}: {'; '.join(viol)}", tmp
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
