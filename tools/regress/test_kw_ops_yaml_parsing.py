# contact·relax·hfdamp·implicit·explicit·modal·stabilize·optimize·matswap YAML 파서 회귀 시험 — 따옴표·인라인 주석·블록 목록·CONTROL_CONTACT 카드 2
"""
사용: python3 tools/regress/test_kw_ops_yaml_parsing.py <KooRemapper 바이너리>

배경
  - 이 명령들의 미니 YAML 파서가 find('#') 로 주석을 뗐다. 따옴표 안의 #('title: "Self # x"') 까지 잘라
    제목이 '"Self' 가 됐고, 값 양끝의 따옴표는 아예 떼지 않아 'output: "q.k"' 는 따옴표가 들어간 이름으로
    파일을 쓰고 'mode: "explicit"' · 'stabilize: "explicit"' · 'optimize: "rubber"' 는 모르는 값으로 거부됐다.
    matswap 은 'bundle: "rubber.k"' 를 못 열고 'output: "x.k"' 를 '"x.k".k' 로 썼다.
  - stabilize 는 모델의 *CONTROL_CONTACT 에 카드 1 만 있으면 빈 줄을 카드 2 로 넣었는데 패치가 빈 줄을
    건너뛰어 nsbcs·xpene 이 조용히 빠지고 로그는 '*CONTROL_CONTACT: OK' 였다.
  - optimize 의 'pids:' 는 인라인 [1, 2] 만 읽고 블록 목록('- 1' 줄)은 조용히 무시했다.
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\n"
       "rho: 7.85e-9\nE: 210000.0\nnu: 0.3\nmid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def yaml(d, name, body):
    open(os.path.join(d, name), "w").write(body)
    return name


def field(line, pos, width=10):
    return line[pos:pos + width].strip() if len(line) > pos else ""


def cc_card2(path):
    """*CONTROL_CONTACT 의 두 번째 데이터 카드 줄 (없으면 '')"""
    lines = open(path).read().splitlines()
    for i, ln in enumerate(lines):
        if not ln.startswith("*CONTROL_CONTACT"):
            continue
        data = []
        for ln2 in lines[i + 1:]:
            if ln2.startswith("*"):
                break
            if ln2.strip() and not ln2.startswith("$"):
                data.append(ln2)
        return data[1] if len(data) >= 2 else ""
    return ""


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="kw_ops_yaml_")
    for f in ("two_cubes.k", "rubber.k"):
        shutil.copy(os.path.join(REPO, "examples", "matswap", f), d)
    yaml(d, "box.yaml", BOX)
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    if rc != 0:
        print("generate box 실패:", out[-300:])
        return 2

    print("[따옴표 안의 # 는 주석이 아니다]")
    yaml(d, "ct.yaml", 'model: box.k\noutput: "ct_out.k"\ncontacts:\n  - action: create   # 주석\n'
                       '    type: automatic_single_surface\n    slave: { pid: 1 }\n'
                       '    title: "Self # not-a-comment"\n')
    rc, out = run(binary, d, "contact", "ct.yaml")
    ct_out = os.path.join(d, "ct_out.k")
    check("contact: output 따옴표를 떼고 ct_out.k 로 씀", rc == 0 and os.path.exists(ct_out), f"rc={rc} {out[-200:]}")
    title = ""
    if os.path.exists(ct_out):
        ls = open(ct_out).read().splitlines()
        for i, ln in enumerate(ls):
            if ln.startswith("*CONTACT_AUTOMATIC_SINGLE_SURFACE_TITLE"):
                title = ls[i + 1].strip()
    check("contact: title 의 따옴표 안 # 가 살아 있음", title == "Self # not-a-comment", f"title={title!r}")

    yaml(d, "rx.yaml", 'model: box.k\noutput: "rx # x.k"\nmode: "explicit"\nlevel: 2\n')
    rc, out = run(binary, d, "relax", "rx.yaml")
    check("relax: mode: \"explicit\" 수용 + 따옴표 안 # 가 든 이름으로 씀",
          rc == 0 and os.path.exists(os.path.join(d, "rx # x.k")), f"rc={rc} {out[-200:]}")

    print("[값 양끝의 따옴표는 뗀다]")
    yaml(d, "hf.yaml", 'model: box.k\noutput: "hf_out.k"\ndt_target: 3.0e-7\nmode: "selective"\n')
    rc, out = run(binary, d, "hfdamp", "hf.yaml")
    check("hfdamp: mode: \"selective\" 가 selective 로 적용",
          rc == 0 and "Selective mode" in out and os.path.exists(os.path.join(d, "hf_out.k")),
          f"rc={rc} {out[-200:]}")

    yaml(d, "im.yaml", 'model: box.k\noutput: "im_out.k"\nmode: "static"\nlevel: 2\nendtime: 1.0\n')
    rc, out = run(binary, d, "implicit", "im.yaml")
    check("implicit: mode: \"static\" 수용 + im_out.k 로 씀",
          rc == 0 and os.path.exists(os.path.join(d, "im_out.k")), f"rc={rc} {out[-200:]}")

    yaml(d, "ex.yaml", 'model: im_out.k\noutput: "ex_out.k"\nkeep_dr_curves: "false"\n')
    rc, out = run(binary, d, "explicit", "ex.yaml")
    check("explicit: output 따옴표를 떼고 ex_out.k 로 씀",
          rc == 0 and os.path.exists(os.path.join(d, "ex_out.k")), f"rc={rc} {out[-200:]}")

    yaml(d, "md.yaml", 'model: box.k\noutput: "md_out.k"\nnmode: 10\nfmax: 2000.0\n')
    rc, out = run(binary, d, "modal", "md.yaml")
    check("modal: output 따옴표를 떼고 md_out.k 로 씀",
          rc == 0 and os.path.exists(os.path.join(d, "md_out.k")), f"rc={rc} {out[-200:]}")

    yaml(d, "sb.yaml", 'model: box.k\noutput: "sb_out.k"\nstabilize: "explicit"\nlevel: 3\n')
    rc, out = run(binary, d, "stabilize", "sb.yaml")
    check("stabilize: stabilize: \"explicit\" 수용 + sb_out.k 로 씀",
          rc == 0 and os.path.exists(os.path.join(d, "sb_out.k")), f"rc={rc} {out[-200:]}")

    yaml(d, "op.yaml", 'model: box.k\noutput: "op_out.k"\noptimize: "rubber"\npids: [1]\ntssfac: 0.67\n')
    rc, out = run(binary, d, "optimize", "op.yaml")
    check("optimize: optimize: \"rubber\" 수용 + op_out.k 로 씀",
          rc == 0 and os.path.exists(os.path.join(d, "op_out.k")), f"rc={rc} {out[-200:]}")

    yaml(d, "ms.yaml", 'model: "two_cubes.k"\noutput: "ms_out.k"\nswaps:\n  - bundle: "rubber.k"\n    pid: 1\n')
    rc, out = run(binary, d, "matswap", "ms.yaml")
    check("matswap: 따옴표 친 bundle 을 열고 ms_out.k 로 씀 ('\"ms_out.k\".k' 아님)",
          rc == 0 and os.path.exists(os.path.join(d, "ms_out.k")), f"rc={rc} {out[-200:]}")

    print("[stabilize: 카드 1 만 있는 *CONTROL_CONTACT 에 카드 2 를 만든다]")
    lines = open(os.path.join(d, "box.k")).read().splitlines()
    i = lines.index("*END")
    lines[i:i] = ["*CONTROL_CONTACT",
                  "$    SLSFAC    RWPNAL    ISLCHK    SHLTHK    PENOPT    THKCHG     ORIEN    ENMASS",
                  "       0.1       0.0         1         0         1         0         1         0"]
    open(os.path.join(d, "cc1.k"), "w").write("\n".join(lines) + "\n")
    yaml(d, "cc.yaml", "model: cc1.k\noutput: cc_out.k\nstabilize: explicit\nnsbcs: 7\nxpene: 3.0\n")
    rc, out = run(binary, d, "stabilize", "cc.yaml")
    card2 = cc_card2(os.path.join(d, "cc_out.k")) if os.path.exists(os.path.join(d, "cc_out.k")) else ""
    check("stabilize: 카드 2 에 NSBCS 가 고정폭으로 들어감", rc == 0 and field(card2, 20) == "7",
          f"rc={rc} card2={card2!r}")
    check("stabilize: 카드 2 에 XPENE 가 고정폭으로 들어감", field(card2, 40) == "3.0000", f"card2={card2!r}")
    check("stabilize: 값이 실제로 바뀌었으면 로그도 modified", "*CONTROL_CONTACT: modified" in out, out[-200:])

    print("[optimize: pids 블록 목록]")
    yaml(d, "cs.yaml", "model: box.k\noutput: ct_soft.k\ncontacts:\n  - action: create\n"
                       "    type: automatic_surface_to_surface\n    slave: { pid: 1 }\n    master: { pid: 1 }\n"
                       "    soft: 1\n    title: T1\n")
    rc, out = run(binary, d, "contact", "cs.yaml")
    if rc != 0:
        print("contact create 실패:", out[-300:])
        return 2
    yaml(d, "ob.yaml", "model: ct_soft.k\noutput: ob_out.k\noptimize: rubber\npids:\n  - 1   # 대상 파트\n")
    rc, out = run(binary, d, "optimize", "ob.yaml")
    check("optimize: 'pids:' 아래 '- 1' 블록 목록을 읽음", rc == 0 and "PIDs   : 1" in out, f"rc={rc} {out[-200:]}")
    check("optimize: 블록 목록 PID 의 접촉 Card A 를 실제로 고침 (SOFT=1->0)",
          "SOFT=1->0" in out, out[-300:])

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
