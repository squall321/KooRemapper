# help 면이 찍는 내용이 실제 동작과 같은지 보는 회귀 시험 — 찍힌 예제 블록을 그대로 실행해 본다
"""
사용: python3 tools/regress/test_help_truth.py <KooRemapper 바이너리>

배경
  - 'help assemble' 의 restack/bend/indent 블록이 바이너리가 거절하는 키를 찍었다
    (restack 'source_pid' → missing target_pid, bend 'deflection_file' → invalid source '',
     indent 'direction: z' → invalid direction 'z'). 찍힌 블록은 그대로 돌아가야 한다.
  - 'help generate-var' 예제가 --no-scale 을 달아 100x1x1 퇴화 메시를 냈다.
  - 'help load' 가 압력을 내는 mode: gravity 와 없는 select: all 을 문서화했다.
  - '--help 공통 규칙' 의 '경로는 작업 폴더 기준' 이 거짓이었다(YAML 이 있는 폴더 기준).
  - 한때 '예외: load/boundary/contact/relax/… 는 폴더 없는 이름만 YAML 폴더 기준' 이라고 적었는데,
    그 갈래가 모두 YAML 폴더 기준으로 고쳐진 뒤에도 문장이 남아 다시 거짓이 됐다.
    지금 남은 예외는 matdb 의 database 키뿐이다(작업 폴더 기준).
  - 'generate-var --no-scale' 을 'use YAML lengths as-is' 라고 적었지만 J/K 는 1.0 이 된다.
  - 'prestress --strain' / 'strain --type' 이 모르는 값을 조용히 기본값으로 삼켰다.
  - 'prestress --strain log' 는 green 과 바이트 동일한 결과였다(help 에만 있던 값).
"""
import os
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
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr


def help_text(binary, *args):
    return run(binary, REPO, "help", *args)[1]


def op_block(text, opname):
    """'help assemble' 의 'Operation Types' 에서 한 op 블록(하위 들여쓰기 줄)을 떼어낸다."""
    lines = text.splitlines()
    body, started = [], False
    for ln in lines:
        if not started:
            if ln.startswith("  " + opname + " ") and not ln.startswith("   "):
                started = True
            continue
        if ln.strip() == "":
            break
        if not ln.startswith("    "):
            break
        body.append(ln)
    return body


def bbox(path):
    """k 파일 *NODE 의 경계 상자 크기 [dx, dy, dz] — 고정폭 8/16/16/16."""
    xs, ys, zs, sect = [], [], [], ""
    for ln in open(path, errors="replace"):
        if ln.startswith("*"):
            sect = ln.strip().upper()
            continue
        if sect != "*NODE" or not ln.strip() or ln.startswith("$"):
            continue
        try:
            xs.append(float(ln[8:24])); ys.append(float(ln[24:40])); zs.append(float(ln[40:56]))
        except ValueError:
            pass
    return [max(v) - min(v) for v in (xs, ys, zs)] if xs else None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    tmp = tempfile.mkdtemp(prefix="help_truth_")
    open(os.path.join(tmp, "box.yaml"), "w").write(BOX)
    rc, out = run(binary, tmp, "generate", "box", "box.yaml")
    if rc != 0:
        print("생성 실패 — 시험 중단:", out[-300:])
        return 2

    print("[help assemble 의 op 블록을 그대로 assemble 로 실행]")
    asm = help_text(binary, "assemble")
    for opname in ("restack", "bend", "indent"):
        body = op_block(asm, opname)
        if not body:
            check(f"assemble: help 에 {opname} 블록이 있음", False, "블록 없음")
            continue
        yml = os.path.join(tmp, f"help_{opname}.yaml")
        with open(yml, "w") as f:
            f.write("base_model: box.k\noutput: help_%s_out\nmaterial:\n  E: 210000.0\n  nu: 0.3\n"
                    "operations:\n  - type: %s\n" % (opname, opname))
            f.write("\n".join(body) + "\n")
        rc, out = run(binary, tmp, "assemble", f"help_{opname}.yaml")
        made = os.path.exists(os.path.join(tmp, f"help_{opname}_out.k"))
        check(f"assemble: help 의 {opname} 블록이 그대로 돌아감 (rc=0)",
              rc == 0 and made and "[ERROR]" not in out, f"rc={rc} {out[-300:]}")

    print("[help generate-var 예제 — 퇴화 메시가 아니어야 한다]")
    gv = help_text(binary, "generate-var")
    check("generate-var: 예제 명령에 --no-scale 이 없음",
          "--no-scale var.yaml" not in gv, gv[gv.find("$ KooRemapper generate-var"):][:120])
    cmd = [l[2:] for l in gv.splitlines() if l.startswith("$ KooRemapper generate-var")]
    if not cmd:
        check("generate-var: 예제 명령을 help 에서 찾음", False)
    else:
        var = os.path.join(tmp, "var.yaml")
        files, cur, in_ex = {}, None, False
        for ln in gv.splitlines():
            if ln.startswith("-----8<----- 여기부터"):
                in_ex = True
                continue
            if ln.startswith("-----8<----- 여기까지"):
                in_ex = False
                continue
            if not in_ex:
                continue
            if ln.startswith("--- 파일: ") and ln.endswith(" ---"):
                cur = ln[len("--- 파일: "):-4]
                files[cur] = ""
                continue
            if ln.startswith("$ "):
                cur = None
                continue
            if cur is not None:
                files[cur] += ln + "\n"
        for n, c in files.items():
            open(os.path.join(tmp, n), "w").write(c)
        rc, out = run(binary, tmp, *cmd[0].split()[1:])
        got = bbox(os.path.join(tmp, "var.k")) if os.path.exists(os.path.join(tmp, "var.k")) else None
        want = [100.0, 10.0, 2.0]
        check("generate-var: 예제 결과가 reference dimensions 100x10x2 (100x1x1 퇴화 아님)",
              rc == 0 and got is not None and all(abs(g - w) < 1e-3 for g, w in zip(got, want)),
              f"rc={rc} bbox={got}")
        # --no-scale 은 '기준 메시 파일(--ref / reference.flat_mesh)을 무시' 하는 것이고,
        # YAML 에 적은 reference.dimensions 는 그대로 적용된다(치수를 1.0 으로 뭉개던 결함을 고쳤다).
        check("generate-var: --no-scale 을 'use YAML lengths as-is' 라고 하지 않음",
              "use YAML lengths as-is" not in gv,
              [l for l in gv.splitlines() if "no-scale" in l])
        check("generate-var: --no-scale 설명이 dimensions 는 계속 적용됨을 밝힘",
              "dimensions" in gv and "still apply" in gv,
              [l for l in gv.splitlines() if "no-scale" in l or "dimensions" in l])
        rc, out = run(binary, tmp, "generate-var", "--no-scale", "var.yaml", "var_ns.k")
        ns = bbox(os.path.join(tmp, "var_ns.k")) if os.path.exists(os.path.join(tmp, "var_ns.k")) else None
        check("generate-var: --no-scale 에서도 reference.dimensions 100x10x2 가 지켜짐",
              rc == 0 and ns is not None and all(abs(g - w) < 1e-3 for g, w in zip(ns, want)),
              f"rc={rc} bbox={ns}")
        _ = var

    print("[help load — 지원하지 않는 값을 문서에 남기지 않는다]")
    ld = help_text(binary, "load")
    check("load: gravity 모드를 문서에 쓰지 않음", "gravity" not in ld and "중력" not in ld,
          [l for l in ld.splitlines() if "gravity" in l or "중력" in l])
    check("load: select 에 없는 'all' 을 쓰지 않음",
          "| all" not in ld and "tied | all" not in ld and
          not any(l.strip().startswith("all ") for l in ld.splitlines()),
          [l for l in ld.splitlines() if l.strip().startswith("all ")])
    for v in ("normal_pressure", "force", "tied", "set"):
        check(f"load: 실제 지원값 '{v}' 가 문서에 있음", v in ld)

    print("[--help 공통 규칙 — 실제 동작과 같은가]")
    rc, top = run(binary, REPO, "--help")
    rules = top[top.find("공통 규칙"):]
    check("공통 규칙: '경로는 작업 폴더 기준' 이라고 더는 말하지 않음",
          "경로는 작업 폴더 기준" not in rules, rules[:400])
    check("공통 규칙: YAML 안 경로는 YAML 파일 폴더 기준이라고 적음",
          "YAML 파일이 있는 폴더" in rules, rules[:400])
    check("공통 규칙: 단독 명령의 다중 operations 거부를 적음",
          "operations" in rules and "2개 이상" in rules, rules[:400])
    check("공통 규칙: 주석·따옴표 제거 규칙을 적음",
          "주석" in rules and "따옴표" in rules, rules[:400])

    # 규칙 (a) 를 실제로 확인 — cfg/strip.yaml 의 ../data/... 가 cfg 기준으로 풀린다
    os.makedirs(os.path.join(tmp, "cfg"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
    open(os.path.join(tmp, "data", "box.yaml"), "w").write(BOX)
    run(binary, os.path.join(tmp, "data"), "generate", "box", "box.yaml")
    open(os.path.join(tmp, "cfg", "strip.yaml"), "w").write(
        "model: ../data/box.k\noutput: ../data/box_stripped.k\nkeywords:\n  - CONTACT\n")
    rc, out = run(binary, tmp, "strip", "cfg/strip.yaml")
    check("규칙(a): strip cfg/strip.yaml 의 출력이 작업 폴더가 아니라 cfg/../data 로 감",
          os.path.exists(os.path.join(tmp, "data", "box_stripped.k")) and
          not os.path.exists(os.path.join(tmp, "box_stripped.k")), f"rc={rc} {out[-200:]}")

    # 규칙(a) 는 load/boundary/contact/relax/database/implicit/modal/ale/cclip/matdb 에도 똑같이 적용된다 —
    # 폴더가 붙은 상대 경로까지 YAML 폴더 기준이다. help 가 그렇게 적고 있는지, 실제로 그렇게 도는지 본다.
    check("공통 규칙: 폴더 붙은 상대 경로도 YAML 폴더 기준이라고 적음",
          "폴더가 붙은 상대 경로" in rules and "load/boundary" not in rules, rules[:700])
    check("공통 규칙: 남은 예외는 matdb 의 database 키라고 적음",
          "matdb" in rules and "database" in rules, rules[:700])
    open(os.path.join(tmp, "cfg", "box.k"), "wb").write(
        open(os.path.join(tmp, "data", "box.k"), "rb").read())
    LOAD_CASE = "loads:\n  - part: 1\n    mode: normal_pressure\n    value: 1.0\n"
    BND_CASE = ("boundaries:\n  - part: 1\n    dof: all\n    direction: [0, 0, -1]\n"
                "    select: direction\n    angle: 45.0\n")
    for cmd, case in (("load", LOAD_CASE), ("boundary", BND_CASE)):
        open(os.path.join(tmp, "cfg", f"{cmd}_name.yaml"), "w").write(
            f"model: box.k\noutput: {cmd}_name_out.k\n" + case)
        rc, out = run(binary, tmp, cmd, f"cfg/{cmd}_name.yaml")
        check(f"규칙(a): {cmd} 의 폴더 없는 이름은 YAML 폴더(cfg) 기준으로 풀린다",
              f"[{cmd}] Model: cfg/box.k" in out, f"rc={rc} {out[-200:]}")
        open(os.path.join(tmp, "cfg", f"{cmd}_rel.yaml"), "w").write(
            f"model: ../data/box.k\noutput: ../data/{cmd}_rel_out.k\n" + case)
        rc, out = run(binary, tmp, cmd, f"cfg/{cmd}_rel.yaml")
        # 폴더가 붙은 상대 경로도 YAML 폴더 기준이다 — cfg/../data 로 풀려 실제로 산출물이 거기 생긴다.
        check(f"규칙(a): {cmd} 의 '../data/box.k' 도 YAML 폴더(cfg) 기준으로 풀린다",
              rc == 0 and f"[{cmd}] Model: cfg/../data/box.k" in out and
              os.path.exists(os.path.join(tmp, "data", f"{cmd}_rel_out.k")) and
              not os.path.exists(os.path.join(tmp, f"{cmd}_rel_out.k")),
              f"rc={rc} {out[-200:]}")

    # 규칙 (b)
    open(os.path.join(tmp, "multi.yaml"), "w").write(
        "base_model: box.k\noutput: multi_out\noperations:\n  - type: hex20\n  - type: tet10\n")
    rc, out = run(binary, tmp, "convert", "multi.yaml")
    check("규칙(b): 단독 convert 가 operations 2개 YAML 을 rc=1 로 거절하고 assemble 안내",
          rc == 1 and "assemble multi.yaml" in out, f"rc={rc} {out[-300:]}")

    # 규칙 (c)
    open(os.path.join(tmp, "cmt.yaml"), "w").write(
        'output: "cmt#1.k"   # 주석\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 2\nny: 2\nnz: 1\n'
        "rho: 7.85e-9\nE: 210000.0\nnu: 0.3\nmid: 1\nsecid: 1\npid: 1\n")
    rc, out = run(binary, tmp, "generate", "box", "cmt.yaml")
    check("규칙(c): 값 뒤 주석은 떼고 따옴표는 벗기되 따옴표 안 '#' 는 값으로 남음",
          rc == 0 and os.path.exists(os.path.join(tmp, "cmt#1.k")),
          f"rc={rc} {sorted(os.listdir(tmp))[:12]}")

    print("[prestress --strain / strain --type — 모르는 값을 삼키지 않는다]")
    run(binary, tmp, "generate", "--dim-i", "10", "--dim-j", "5", "arc", "demo")
    # prestress 의 log 는 green 과 바이트 동일한 결과를 냈다(요약도 'Green-Lagrange') —
    # 구현될 때까지 help·허용목록에서 빼, 매뉴얼·플랫폼 카탈로그와 같은 값 집합(engineering/green)이 된다.
    for cmd, flag, allowed in (("prestress", "--strain", ("engineering", "green")),
                               ("strain", "--type", ("engineering", "green", "log"))):
        ext = ".dynain" if cmd == "prestress" else ".csv"
        listing = ", ".join(allowed)
        hlp = help_text(binary, cmd)
        check(f"{cmd} {flag}: help 가 적은 값 집합이 허용목록과 같음 ({listing})",
              all(v in hlp for v in allowed) and
              ("log" in allowed or "green (default), log" not in hlp),
              [l for l in hlp.splitlines() if flag in l])
        for v in allowed:
            rc, out = run(binary, tmp, cmd, flag, v, "demo_flat.k", "demo_bent.k", f"{cmd}_{v}{ext}")
            check(f"{cmd} {flag} {v}: 허용값은 그대로 동작 (rc=0)", rc == 0, f"rc={rc} {out[-200:]}")
        for v in ("bogus",) + tuple(x for x in ("log",) if x not in allowed):
            rc, out = run(binary, tmp, cmd, flag, v, "demo_flat.k", "demo_bent.k", f"{cmd}_bogus{ext}")
            check(f"{cmd} {flag} {v}: rc=1 + 허용값 목록",
                  rc == 1 and listing in out, f"rc={rc} {out[-300:]}")
        check(f"{cmd} {flag} bogus: 결과 파일을 쓰지 않음",
              not os.path.exists(os.path.join(tmp, f"{cmd}_bogus{ext}")))

    print("[HelpCatalogData.inc 가 ops_help.py 와 같은지]")
    p = subprocess.run([sys.executable, os.path.join(REPO, "tools", "help", "gen_help_cpp.py"), "--check"],
                       capture_output=True, text=True)
    check("gen_help_cpp.py --check: .inc 가 정본과 같음", p.returncode == 0, p.stdout + p.stderr)

    print()
    if FAILS:
        print(f"FAIL {len(FAILS)}")
        for f in FAILS:
            print("  -", str(f)[:300])
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
