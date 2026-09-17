# help 사례를 원본 YAML 과 '값 뒤 인라인 # 주석' 을 붙인 YAML 로 각각 실행해 출력이 같은지 보는 회귀 시험
"""
사용: python3 tools/regress/test_yaml_inline_comments.py <KooRemapper 바이너리> [op ...]

배경
  대부분의 명령 파서가 'key: value   # 주석' 의 주석까지 값으로 읽었다 — 'box.k   # 모델' 파일을 찾거나
  (generate box 는 그 이름으로 파일을 만듦), '- type: squeeze  # …' 를 모르는 op 로 보거나, merge 는 'vrh  # …' 를
  모르는 값으로 보고 조용히 기본값으로 계산했다. 모든 op 사례에서 주석 유무와 무관하게 출력이 같아야 한다.
  원본 사례부터 실패하는 op(번들 DB·gmsh 등 실행 환경 의존)는 건너뛴다.
"""
import os, re, shutil, subprocess, sys, tempfile

KR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KR, "tools", "help"))
from ops_help import OPS  # noqa: E402

BIN = os.path.abspath(sys.argv[1])
only = set(sys.argv[2:])
KV = re.compile(r"^(\s*(?:-\s+)?[A-Za-z_][\w.\-]*\s*:\s*)(\S.*)$")


def inject(text):
    out, block_indent = [], None
    for ln in text.split("\n"):
        ind = len(ln) - len(ln.lstrip())
        if block_indent is not None:
            if ln.strip() == "" or ind > block_indent:
                out.append(ln)
                continue
            block_indent = None
        m = KV.match(ln)
        if m and " #" not in ln:
            val = m.group(2).rstrip()
            if val in ("|", ">"):
                block_indent = ind
            out.append(f"{m.group(1)}{val}      # note")
        else:
            out.append(ln)
    return "\n".join(out)


def run(spec, files):
    tmp = tempfile.mkdtemp(prefix=f"cp_{spec['name']}_")
    for need in spec["needs"]:
        dst = os.path.join(tmp, need)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(os.path.join(KR, need), dst)
    for name, content in files.items():
        p = os.path.join(tmp, name)
        os.makedirs(os.path.dirname(p) or tmp, exist_ok=True)
        open(p, "w").write(content)
    rc = 0
    for c in spec["cmds"]:
        argv = c.split()
        r = subprocess.run([BIN] + argv[1:], cwd=tmp, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            return tmp, r.returncode, (r.stdout + r.stderr).strip().splitlines()[-1:]
    return tmp, rc, []


def norm(path):
    try:
        return [l for l in open(path, errors="replace").read().splitlines() if not l.startswith("$")]
    except Exception:
        return None


FAILS, SKIPS = [], []
for spec in OPS:
    if only and spec["name"] not in only:
        continue
    yfiles = {k: v for k, v in spec["files"].items() if k.endswith((".yaml", ".yml"))}
    if not yfiles:
        continue
    t0, rc0, e0 = run(spec, spec["files"])
    # 시험 대상 op 의 마지막 명령이 읽는 YAML 에만 주석을 넣는다 (앞 generate box 입력은 그대로 — 연쇄 실패 방지)
    last = spec["cmds"][-1].split()
    target = [a for a in last if a.endswith((".yaml", ".yml"))]
    commented = dict(spec["files"])
    for k in yfiles:
        if not target or os.path.basename(k) == os.path.basename(target[-1]):
            commented[k] = inject(commented[k])
    t1, rc1, e1 = run(spec, commented)
    if rc0 != 0:
        print(f"  {spec['name']:14s} 건너뜀 — 원본 사례부터 실패(실행 환경 의존) {e0}")
        SKIPS.append(spec["name"])
        continue
    if rc1 != 0:
        print(f"  {spec['name']:14s} FAIL 주석 넣으면 실패 rc={rc1}  {e1}")
        FAILS.append(spec["name"])
        continue
    diffs = [o for o in spec["outputs"] if norm(os.path.join(t0, o)) != norm(os.path.join(t1, o))]
    print(f"  {spec['name']:14s} {'FAIL 출력 달라짐 ' + str(diffs) if diffs else 'OK'}")
    if diffs:
        FAILS.append(spec["name"])

print()
if SKIPS:
    print(f"건너뜀(실행 환경 의존): {SKIPS}")
if FAILS:
    print(f"FAIL {len(FAILS)} 건: {FAILS}")
    sys.exit(1)
print("ALL PASS")
