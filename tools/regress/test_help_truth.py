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
    matdb 의 database 도 같은 규칙으로 고쳐졌는데 '아직 작업 폴더 기준' 이라는 예외 문장이
    또 남았다 — 없앤 예외를 계속 적지 않는지 아래에서 못 박는다. 지금 남은 예외는 map 뿐이다.
  - 'generate-var --no-scale' 을 'use YAML lengths as-is' 라고 적었지만 J/K 는 1.0 이 된다.
  - 'prestress --strain' / 'strain --type' 이 모르는 값을 조용히 기본값으로 삼켰다.
  - 'prestress --strain log' 는 green 과 바이트 동일한 결과였다(help 에만 있던 값).
  - restack·merge 가 비운 PID·지운 요소·지운 노드를 가리키던 자리를 옮기기 시작했다 —
    help 가 rc=1 과 pid_refs 를 적지 않으면 자동화는 경고를 못 보고 그 덱을 솔버로 넘긴다.
    스칼라 PID 칸의 동작이 restack(manual)과 merge(옮김)로 갈리는 것도 여기서 못 박는다.
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
    check("공통 규칙: matdb 의 database 도 YAML 폴더 기준이라고 적음",
          "matdb" in rules and "database" in rules
          and "database 키는 아직 작업 폴더 기준" not in rules, rules[:900])
    check("공통 규칙: 남은 작업 폴더 기준 예외로 map 만 적음",
          "남은 예외" in rules and "map" in rules, rules[:900])
    # 없앤 예외를 다시 사실처럼 적지 않는지 — '예외' 로 시작하는 줄에 matdb/database 가 없어야 한다
    exc_lines = [ln for ln in rules.splitlines() if "예외" in ln]
    check("공통 규칙: '예외' 줄에 matdb·database 가 남아 있지 않다",
          not any(("matdb" in ln or "database" in ln) for ln in exc_lines), exc_lines)
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

    # 규칙 (d) 탭 / (e) BOM — 공통 규칙 블록에 적혀 있고 실제로 그렇게 도는가
    check("공통 규칙: YAML 들여쓰기 탭 거절을 적음",
          "탭" in rules and "종료 코드 1" in rules, rules[:900])
    check("공통 규칙: UTF-8 BOM 무시를 적음", "BOM" in rules, rules[:900])
    open(os.path.join(tmp, "tab.yaml"), "w").write(
        'model: box.k\noutput: tab_out.k\nkeywords:\n\t- "*NODE"\n')
    rc, out = run(binary, tmp, "strip", "tab.yaml")
    check("규칙(d): 탭 들여쓰기 YAML 이 rc=1 + [ERROR] 이고 출력 파일이 없음",
          rc == 1 and "[ERROR]" in out and not os.path.exists(os.path.join(tmp, "tab_out.k")),
          f"rc={rc} {out[-200:]}")
    open(os.path.join(tmp, "bom.yaml"), "wb").write(
        b"\xef\xbb\xbf" + b'model: box.k\noutput: bom_out.k\nkeywords:\n  - "*NODE"\n')
    rc, out = run(binary, tmp, "strip", "bom.yaml")
    check("규칙(e): BOM 이 붙은 YAML 도 그대로 돌아감",
          rc == 0 and os.path.exists(os.path.join(tmp, "bom_out.k")), f"rc={rc} {out[-200:]}")
    # 두 규칙 모두 예외가 남아 있다(매뉴얼 §3.1 (d)(e)) — 문구와 실제 동작을 함께 잠근다.
    # 무조건문으로 적으면 윈도우 사용자가 --help 가 괜찮다고 한 입력으로 rc=1 을 맞는다.
    check("공통 규칙: 탭 검사의 예외(되감을 수 없는 입력)를 적음",
          "예외: 되감을 수 없는 입력" in rules, rules[:1200])
    check("공통 규칙: BOM 은 예외 없이 무시한다고 적음(map·squeeze 도 고쳐졌다)",
          "BOM 에서 실패" not in rules, rules[:1200])
    open(os.path.join(tmp, "map_tab.yaml"), "w").write(
        "bent: bent.k\nflat: flat.k\noutput: map_tab_out.k\nnotes:\n\t- memo\n")
    rc, out = run(binary, tmp, "map", "map_tab.yaml")
    check("규칙(d): map 도 탭 들여쓰기를 rc=1 로 거절한다",
          rc == 1 and "탭을 쓸 수 없습니다" in out, f"rc={rc} {out[-200:]}")
    open(os.path.join(tmp, "sq_bom.yaml"), "wb").write(
        b"\xef\xbb\xbf" + b"parts:\n  - pid: 1\n    eps_x: -0.01\n"
        b"material:\n  E: 210000.0\n  nu: 0.3\n")
    rc, out = run(binary, tmp, "squeeze", "box.k", "sq_bom.yaml", "sq_bom")
    check("규칙(e): squeeze 도 BOM 붙은 config 를 그대로 읽는다",
          rc == 0 and os.path.exists(os.path.join(tmp, "sq_bom.k")), f"rc={rc} {out[-200:]}")

    print("[열거값 표기 — help 가 적은 허용값이 바이너리와 같은가]")
    # boundary 와 load 의 select 는 값 집합이 다르다(boundary: all, load: tied). 한쪽 목록을 베껴 적으면
    # 사용자가 rc=1 을 맞는다.
    bnd = help_text(binary, "boundary")
    check("boundary: select 의 set (기존 *SET_NODE, set_id 필요)을 적음",
          "set(기존 *SET_NODE, set_id 필요)" in bnd,
          [l for l in bnd.splitlines() if "select" in l])
    check("boundary: load 와 select 값 집합이 다름을 적음",
          "load 의 select(direction|set|tied)와 값이 다르다" in bnd,
          [l for l in bnd.splitlines() if "select" in l])
    open(os.path.join(tmp, "bnd_tied.yaml"), "w").write(
        "model: box.k\noutput: bnd_tied.k\nboundaries:\n  - part: 1\n    dof: xyz\n    select: tied\n")
    rc, out = run(binary, tmp, "boundary", "bnd_tied.yaml")
    check("boundary: select 'tied' 는 rc=1 + 허용목록 (direction, all, set)",
          rc == 1 and "allowed: direction, all, set" in out, f"rc={rc} {out[-200:]}")
    open(os.path.join(tmp, "bnd_all.yaml"), "w").write(
        "model: box.k\noutput: bnd_all.k\nboundaries:\n  - part: 1\n    dof: xyz\n    select: all\n")
    rc, out = run(binary, tmp, "boundary", "bnd_all.yaml")
    check("boundary: select 'all' 은 실제로 동작 (rc=0)",
          rc == 0 and os.path.exists(os.path.join(tmp, "bnd_all.k")), f"rc={rc} {out[-200:]}")

    rst = help_text(binary, "restack")
    check("restack: element_type 허용값(solid|tshell|shell)을 적음",
          all(v in rst for v in ("solid", "tshell", "shell")),
          [l for l in rst.splitlines() if "element_type" in l])
    check("restack: direction 허용값(auto|x|y|z, +/- 부호)을 적음",
          "auto" in rst and "direction" in rst,
          [l for l in rst.splitlines() if "direction" in l])
    RESTACK_LAYERS = ("    layers:\n      - thickness: 0.5\n        material_card: |\n"
                      "          *MAT_ELASTIC\n          $#     mid        ro         e        pr\n"
                      "              MID001  7.85E-09  2.10E+05       0.3\n")
    open(os.path.join(tmp, "rs_bad.yaml"), "w").write(
        "base_model: box.k\noutput: rs_bad\noperations:\n  - type: restack\n    target_pid: 1\n"
        "    direction: z\n    element_type: hex\n" + RESTACK_LAYERS)
    rc, out = run(binary, tmp, "restack", "rs_bad.yaml")
    check("restack: element_type 'hex' 는 rc=1 + 허용목록 (solid, tshell, shell)",
          rc == 1 and "allowed: solid, tshell, shell" in out, f"rc={rc} {out[-250:]}")
    open(os.path.join(tmp, "rs_dir.yaml"), "w").write(
        "base_model: box.k\noutput: rs_dir\noperations:\n  - type: restack\n    target_pid: 1\n"
        "    direction: w\n" + RESTACK_LAYERS)
    rc, out = run(binary, tmp, "restack", "rs_dir.yaml")
    check("restack: direction 'w' 는 rc=1 + 허용목록 (auto, x, y, z, +x ...)",
          rc == 1 and "auto, x, y, z" in out, f"rc={rc} {out[-250:]}")

    stb = help_text(binary, "stabilize")
    check("stabilize: level 범위 0~12 를 적음", "0~12" in stb,
          [l for l in stb.splitlines() if "level" in l])
    open(os.path.join(tmp, "stab13.yaml"), "w").write(
        "model: box.k\noutput: stab13.k\nstabilize: explicit\nlevel: 13\n")
    rc, out = run(binary, tmp, "stabilize", "stab13.yaml")
    check("stabilize: level 13 은 rc=1 + 0~12 안내",
          rc == 1 and "0~12" in out, f"rc={rc} {out[-200:]}")

    mdb = help_text(binary, "matdb")
    check("matdb: damping_preset 허용값을 적음",
          "damping_preset" in mdb and "quasi_static" in mdb,
          [l for l in mdb.splitlines() if "damping_preset" in l])
    open(os.path.join(tmp, "md_bad.yaml"), "w").write(
        "model: box.k\noutput: md_bad.k\nmat_type: MAT_ELASTIC\ndamping_preset: bogus\n"
        'materials:\n  - mid: 1\n    match: "*"\n')
    rc, out = run(binary, tmp, "matdb", "md_bad.yaml")
    check("matdb: damping_preset 'bogus' 는 rc=1 + 허용목록",
          rc == 1 and "smartphone_drop" in out and "quasi_static" in out, f"rc={rc} {out[-250:]}")

    # contact 의 create type 만은 D1(rc=1)이 아니라 '경고 후 그대로 기록' 이다 — help 가 그렇게 적는가
    ctc = help_text(binary, "contact")
    check("contact: create 의 type 은 경고 후 그대로 쓴다고 적음",
          "경고" in ctc and "type" in ctc, [l for l in ctc.splitlines() if "type" in l])
    open(os.path.join(tmp, "ct_odd.yaml"), "w").write(
        "model: box.k\noutput: ct_odd.k\ncontacts:\n  - action: create\n"
        "    type: automatic_nodes_to_surface_bogus\n    slave: { pid: 1 }\n")
    rc, out = run(binary, tmp, "contact", "ct_odd.yaml")
    check("contact: 모르는 create type 은 rc=0 + 경고 + 그대로 기록",
          rc == 0 and os.path.exists(os.path.join(tmp, "ct_odd.k")) and
          "not a known contact keyword" in out and "[ERROR]" not in out,
          f"rc={rc} {out[-250:]}")

    print("[matdb 사례 — 컨테이너 밖에서도 그대로 돈다]")
    check("matdb: 사례가 SIF 절대경로(/opt/kooremapper/...)를 박아 두지 않음",
          "/opt/kooremapper/materials" not in mdb.split("-----8<----- 여기까지")[0],
          [l for l in mdb.splitlines() if "/opt/kooremapper" in l])
    # database 를 생략한 YAML 이 번들 DB 를 스스로 찾는가 — 작업 폴더에 materials/ 가 없는 자리에서
    os.makedirs(os.path.join(tmp, "nomat"), exist_ok=True)
    open(os.path.join(tmp, "nomat", "box.k"), "wb").write(
        open(os.path.join(tmp, "box.k"), "rb").read())
    open(os.path.join(tmp, "nomat", "md.yaml"), "w").write(
        "model: box.k\noutput: md_bundle.k\nmat_type: MAT_ELASTIC\n"
        'materials:\n  - mid: 1\n    match: "*"\n')
    # 번들 DB 는 작업 폴더 materials/ → 바이너리 옆 materials/·../materials/ 순으로 찾는다.
    # 갓 빌드한 트리에는 build/dev/materials 가 없다(dist/materials 를 복사해야 생긴다) — 그때는 건너뛴다.
    bindir = os.path.dirname(os.path.realpath(binary))
    bundle = [os.path.join(bindir, "materials", "material_db.json"),
              os.path.join(bindir, "..", "materials", "material_db.json")]
    if not any(os.path.isfile(b) for b in bundle):
        print("  SKIP: 바이너리 옆 materials/material_db.json 없음 "
              "(cp -r dist/materials <빌드 트리>/ 후 다시 돌릴 것)")
    else:
        rc, out = run(binary, tmp, "matdb", "nomat/md.yaml")
        check("matdb: database 를 생략하면 번들 DB 를 스스로 찾는다 (rc=0)",
              rc == 0 and os.path.exists(os.path.join(tmp, "nomat", "md_bundle.k")),
              f"rc={rc} {out[-250:]}")

    print("[restack·merge 의 죽은 PID 참조 — help 문구가 실제 동작과 같은가]")
    # help 가 '옮긴다' 고만 적고 rc=1 을 안 적으면, 자동화는 경고를 못 보고 빈 파트를 가리키는
    # 덱을 그대로 솔버에 넘긴다. 문구와 종료 코드를 함께 잠근다.
    rst = help_text(binary, "restack")
    mrg = help_text(binary, "merge")
    for nm, txt in (("restack", rst), ("merge", mrg)):
        check(f"{nm}: 원 파트가 요소 0 개인 빈 파트로 남는다고 적음",
              "요소 0 개인 빈 파트" in txt, [l for l in txt.splitlines() if "빈 파트" in l])
        check(f"{nm}: pid_refs 허용값(strict 기본, warn)을 적음",
              "pid_refs: strict(기본) | warn" in txt,
              [l for l in txt.splitlines() if "pid_refs" in l])
        check(f"{nm}: 못 옮기면 rc=1 이고 덱은 쓴다고 적음",
              "못 옮긴 자리가 하나라도 남으면 rc=1 이고 덱은 쓴다" in txt,
              [l for l in txt.splitlines() if "rc=1" in l])
        check(f"{nm}: 덱 머리의 $ KOOREMAPPER-PIDREF 블록을 적음",
              "$ KOOREMAPPER-PIDREF" in txt and "*KEYWORD 바로 뒤" in txt,
              [l for l in txt.splitlines() if "PIDREF" in l])
    # 스칼라 PID 칸은 restack(층 N 개)과 merge(새 PID 1 개)의 동작이 갈린다 — 한쪽 문장을 베껴 적으면
    # 사용자가 restack 결과를 '옮겨졌겠지' 하고 넘긴다.
    check("restack: 스칼라 PID 칸은 manual 로 남는다고 적음",
          "manual(직접 고치세요)로 남는다" in rst and "merge 는 이 칸들까지 옮긴다" in rst,
          [l for l in rst.splitlines() if "manual" in l])
    check("merge: 스칼라 PID 칸까지 새 PID 로 바꾼다고 적음",
          "도 새 PID 로 바꾼다" in mrg and "restack 은 이 칸들을 manual 로 남긴다" in mrg,
          [l for l in mrg.splitlines() if "새 PID 로 바꾼다" in l])

    RS_OPS = ("operations:\n  - type: restack\n    target_pid: 1\n    direction: z\n" + RESTACK_LAYERS)
    # box.k 에 층 PID 로 나눌 수 없는 스칼라 PID 칸(*DATABASE_HISTORY_PART)과 펼 수 있는 세트를 함께 둔다
    dead = open(os.path.join(tmp, "box.k")).read().replace(
        "*END", "*DATABASE_HISTORY_PART\n$#     pid\n         1\n"
                "*SET_PART_LIST\n$#     sid\n         9\n         1\n*END")
    open(os.path.join(tmp, "box_dead.k"), "w").write(dead)
    open(os.path.join(tmp, "rs_dead.yaml"), "w").write(
        "base_model: box_dead.k\noutput: rs_dead\n" + RS_OPS)
    rc, out = run(binary, tmp, "restack", "rs_dead.yaml")
    head = open(os.path.join(tmp, "rs_dead.k")).read().splitlines()[:12]
    check("restack: 옮기지 못한 스칼라 PID 칸이 남으면 rc=1 (덱은 쓴다)",
          rc == 1 and os.path.exists(os.path.join(tmp, "rs_dead.k")) and
          "*DATABASE_HISTORY_PART (manual)" in out, f"rc={rc} {out[-300:]}")
    check("restack: 덱 머리 *KEYWORD 바로 뒤에 $ KOOREMAPPER-PIDREF 블록이 있다",
          head[0].startswith("*KEYWORD") and head[1].startswith("$ KOOREMAPPER-PIDREF") and
          any(l.startswith("$ KOOREMAPPER-PIDREF-END") for l in head), head[:4])
    check("restack: 펼 수 있는 *SET_PART_LIST 는 층 PID 전부로 옮겨진다(moved)",
          "*SET_PART_LIST (moved)" in out, [l for l in out.splitlines() if "SET_PART_LIST" in l])
    open(os.path.join(tmp, "rs_warn.yaml"), "w").write(
        "base_model: box_dead.k\noutput: rs_warn\npid_refs: warn\n" + RS_OPS)
    rc, out = run(binary, tmp, "restack", "rs_warn.yaml")
    check("restack: pid_refs 'warn' 은 같은 보고에 rc=0",
          rc == 0 and "*DATABASE_HISTORY_PART (manual)" in out, f"rc={rc} {out[-300:]}")
    open(os.path.join(tmp, "rs_pr_bad.yaml"), "w").write(
        "base_model: box_dead.k\noutput: rs_pr_bad\npid_refs: bogus\n" + RS_OPS)
    rc, out = run(binary, tmp, "restack", "rs_pr_bad.yaml")
    check("restack: pid_refs 'bogus' 는 rc=1 + must be one of strict, warn",
          rc == 1 and "invalid pid_refs 'bogus' (must be one of strict, warn)" in out,
          f"rc={rc} {out[-300:]}")

    # 비-tied 접촉은 shell 층이 섞이면 옮기지 않는다 — help 가 조건 없이 'STYP 3→2 로 바꾼다' 라고만
    # 적으면 shell restack 이 rc=1 로 멈추는 이유를 사용자가 못 찾는다.
    check("restack: 비-tied 접촉은 shell 층이 섞이면 못 옮긴다고 적음",
          "shell 층이 섞이지 않았을 때 층 전부를 담은 새 세트로(STYP 3→2)" in rst and
          "shell 층이 섞이면 옮기지 않고" in rst,
          [l for l in rst.splitlines() if "STYP 3" in l])
    auto = open(os.path.join(tmp, "box.k")).read().replace(
        "*END", "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n"
                "$#   ssid      msid     sstyp     mstyp\n"
                "         1         0         3         0\n"
                "       0.0       0.0       0.0       0.0       0.0         0       0.0       0.0\n"
                "       1.0       1.0       0.0       0.0       1.0       1.0       1.0       1.0\n*END")
    open(os.path.join(tmp, "box_auto.k"), "w").write(auto)
    open(os.path.join(tmp, "rs_auto.yaml"), "w").write(
        "base_model: box_auto.k\noutput: rs_auto\n" + RS_OPS)
    rc, out = run(binary, tmp, "restack", "rs_auto.yaml")
    check("restack: solid 층이면 비-tied 접촉을 층 전부의 세트로 옮긴다(STYP 3→2, rc=0)",
          rc == 0 and "(STYP 3→2)" in out and
          "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE (moved)" in out, f"rc={rc} {out[-300:]}")
    open(os.path.join(tmp, "rs_auto_sh.yaml"), "w").write(
        "base_model: box_auto.k\noutput: rs_auto_sh\n" +
        RS_OPS.replace("    direction: z\n", "    direction: z\n    element_type: shell\n"))
    rc, out = run(binary, tmp, "restack", "rs_auto_sh.yaml")
    check("restack: shell 층이면 그 접촉을 옮기지 않고 left 로 남겨 rc=1",
          rc == 1 and "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE (left)" in out and
          "shell 층이 섞여" in out, f"rc={rc} {out[-300:]}")

    # help merge 사례는 rc=0 이어야 한다 — three_layer.k 의 *MAT_ADD_THERMAL_EXPANSION 이 죽은 PID 를
    # 가리키지만 merge 는 스칼라 칸까지 옮기므로 못 옮긴 자리가 남지 않는다.
    check("merge: 사례가 rc=0 이고 *MAT_ADD_THERMAL_EXPANSION 이 옮겨진다고 적음",
          "못 옮긴 자리가 없어 rc=0 이다" in mrg and "MAT_ADD_THERMAL_EXPANSION" in mrg,
          [l for l in mrg.splitlines() if "rc=0" in l])
    mdir = os.path.join(tmp, "mg")
    os.makedirs(os.path.join(mdir, "examples", "merge"), exist_ok=True)
    shutil.copy(os.path.join(REPO, "examples", "merge", "three_layer.k"),
                os.path.join(mdir, "examples", "merge", "three_layer.k"))
    open(os.path.join(mdir, "merge.yaml"), "w").write(
        "model: examples/merge/three_layer.k\noutput: three_layer_merged.k\n"
        'direction: z\nmethod: vrh\nmerge:\n  - pids: [1, 2, 3]\n    name: "Homogenized_Stack"\n')
    rc, out = run(binary, mdir, "merge", "merge.yaml")
    check("merge: help 사례가 실제로 rc=0 이고 '옮김' 으로 보고된다",
          rc == 0 and "*MAT_ADD_THERMAL_EXPANSION_TITLE (moved)" in out and
          os.path.exists(os.path.join(mdir, "three_layer_merged.k")), f"rc={rc} {out[-400:]}")

    print("[restack 재질 카드 — 숫자 MID·빠진 제목 줄·강체 거부]")
    check("restack: 숫자 MID 를 그대로 쓰고 충돌하면 새 번호를 준다고 적음",
          "material MID 90 is already in use -> assigned MID 91" in rst,
          [l for l in rst.splitlines() if "MID 90" in l])
    NUM_MID = ("    layers:\n      - thickness: 0.5\n        material_card: |\n"
               "          *MAT_ELASTIC\n          $#     mid        ro         e        pr\n"
               "                  90  7.85E-09  2.10E+05       0.3\n"
               "      - thickness: 0.5\n        material_card: |\n"
               "          *MAT_ELASTIC\n          $#     mid        ro         e        pr\n"
               "                  90  1.20E-09  3.00E+03      0.45\n")
    open(os.path.join(tmp, "rs_num.yaml"), "w").write(
        "base_model: box.k\noutput: rs_num\noperations:\n  - type: restack\n    target_pid: 1\n"
        "    direction: z\n" + NUM_MID)
    rc, out = run(binary, tmp, "restack", "rs_num.yaml")
    made = open(os.path.join(tmp, "rs_num.k")).read() if rc == 0 else ""
    check("restack: 숫자 MID 90 을 그대로 쓰고 충돌한 층은 91 을 받는다",
          rc == 0 and "material MID 90 is already in use -> assigned MID 91" in out and
          "        90  7.85E-09" in made and "        91  1.20E-09" in made,
          f"rc={rc} {out[-300:]}")

    check("restack: *MAT_..._TITLE 에 제목 줄이 없으면 채워 준다고 적음",
          "제목 줄이 없으면" in rst and "Restack Layer N" in rst,
          [l for l in rst.splitlines() if "제목 줄" in l])
    NO_TITLE = ("    layers:\n      - thickness: 0.5\n        material_card: |\n"
                "          *MAT_ELASTIC_TITLE\n"
                "          $#     mid        ro         e        pr\n"
                "              MID001  7.85E-09  2.10E+05       0.3\n")
    open(os.path.join(tmp, "rs_nt.yaml"), "w").write(
        "base_model: box.k\noutput: rs_nt\noperations:\n  - type: restack\n    target_pid: 1\n"
        "    direction: z\n" + NO_TITLE)
    rc, out = run(binary, tmp, "restack", "rs_nt.yaml")
    nt = open(os.path.join(tmp, "rs_nt.k")).read() if rc == 0 else ""
    check("restack: 제목 줄 없는 *MAT_..._TITLE 은 [WARN] 뒤 제목을 채워 데이터 줄을 지킨다",
          rc == 0 and "[WARN]" in out and "no title line" in out and
          "*MAT_ELASTIC_TITLE\nRestack Layer 1\n" in nt, f"rc={rc} {out[-300:]}")

    check("restack: 강체 파트를 거절한다고 적음",
          "강체" in rst and "*MAT_RIGID" in rst and "rc=1 로 거절한다" in rst,
          [l for l in rst.splitlines() if "강체" in l])
    rigid = open(os.path.join(tmp, "box.k")).read().replace("*MAT_ELASTIC", "*MAT_RIGID", 1)
    open(os.path.join(tmp, "box_rigid.k"), "w").write(rigid)
    open(os.path.join(tmp, "rs_rigid.yaml"), "w").write(
        "base_model: box_rigid.k\noutput: rs_rigid\n" + RS_OPS)
    rc, out = run(binary, tmp, "restack", "rs_rigid.yaml")
    check("restack: 강체 파트는 rc=1 로 거절하고 출력을 쓰지 않는다",
          rc == 1 and "cannot restack a rigid part" in out and
          not os.path.exists(os.path.join(tmp, "rs_rigid.k")), f"rc={rc} {out[-300:]}")

    check("restack: 새 층이 ELFORM·HGID·TMID 를 물려받는다고 적음",
          "ELFORM" in rst and "HGID·TMID" in rst,
          [l for l in rst.splitlines() if "ELFORM" in l])
    e2 = open(os.path.join(tmp, "box.k")).read().replace(
        "*SECTION_SOLID\n$#   secid    elform\n         1         1\n",
        "*SECTION_SOLID\n$#   secid    elform\n         1         2\n", 1)
    open(os.path.join(tmp, "box_e2.k"), "w").write(e2)
    open(os.path.join(tmp, "rs_e2.yaml"), "w").write(
        "base_model: box_e2.k\noutput: rs_e2\n" + RS_OPS)
    rc, out = run(binary, tmp, "restack", "rs_e2.yaml")
    elf = [l for l in (open(os.path.join(tmp, "rs_e2.k")).read().splitlines() if rc == 0 else [])]
    secs = [elf[i + 2] for i, l in enumerate(elf) if l.strip() == "*SECTION_SOLID" and i + 2 < len(elf)]
    check("restack: 원 ELFORM 2 가 새 층 *SECTION_SOLID 로 이어진다",
          rc == 0 and len(secs) >= 2 and all(s.split()[-1] == "2" for s in secs),
          f"rc={rc} {secs[:4]}")

    print("[--help 공통 규칙 — restack·merge 의 죽은 PID 참조 한 줄]")
    check("공통 규칙: restack·merge 의 참조 이관과 rc=1 을 한 줄로 적음",
          "restack·merge 는 비운 PID 를 가리키던 자리를 옮기고" in rules and
          "pid_refs: warn" in rules, rules[:1600])

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
