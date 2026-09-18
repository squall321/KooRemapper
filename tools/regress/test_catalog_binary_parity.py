# 플랫폼 카탈로그(enum·required)와 MCP 도구 수가 바이너리·소스 실동작과 맞는지 보는 회귀 시험
"""
사용: python3 tools/regress/test_catalog_binary_parity.py <KooRemapper 바이너리>

배경
  - catalog_data.json 은 웹 폼과 MCP 도구 스키마를 만든다. 여기 값이 틀리면 사용자가
    바이너리가 거절하는 설정을 만들거나(assemble plane: xz, mode: stress_only, source: file,
    element_type: hex), 바이너리가 받는 설정을 플랫폼이 막았다(stabilize 의 stabilize 키를
    required 로 표시해 model/output/level 만 있는 정상 YAML 이 validate_args 에서 거절됨,
    matdb 의 database, offset 의 connection_mode: none·offset_direction: both 누락).
  - assemble indent 의 depth·r1·r2 는 카탈로그가 기본값 1.0/1.0/0.5 라고 했지만 실제로는
    기본값이 없어 빠지면 'depth must be non-zero'·'r1 and r2 must be positive' 로 거절된다.
  - meshfix 의 gmsh 경로 안내(dist/gmsh)는 바이너리가 찾는 곳이 아니었다.
  - mcp_server/smoke.py 는 도구 수를 22 로 박아둬 도구가 50개인 지금 항상 실패했다.
  - matdb 의 damping_preset 설명은 '키를 빼면 감쇠 변화 없음' 이라고 했지만, 매칭된 DB 물성의
    감쇠 카드는 프리셋과 무관하게 항상 삽입되고 묵은 *DAMPING_PART_* 제거는 값이 있을 때만
    일어난다 — 프리셋 없이 두 번 돌리면 감쇠 카드가 중복된다.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
CATALOG = os.path.join(REPO, "platform", "core", "kooremapper_core", "catalog_data.json")
MCP_SERVER = os.path.join(REPO, "platform", "mcp_server", "server.py")
MCP_SMOKE = os.path.join(REPO, "platform", "mcp_server", "smoke.py")
MCP_TOOLS_MD = os.path.join(REPO, "platform", "mcp_server", "TOOLS.md")

BOX = "output: flat.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\npid: 1\nmid: 1\nsecid: 1\n"

INDENT_SHAPE = ("    shape:\n      type: polygon\n      points:\n"
                "        - [1,1]\n        - [5,1]\n        - [5,5]\n")


def check(name, cond, detail=""):
    print("  %-72s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def yaml_run(binary, d, cmd, name, body):
    open(os.path.join(d, name + ".yaml"), "w").write(body)
    return run(binary, d, cmd, name + ".yaml")


def asm(binary, d, name, ops_body, extra=""):
    body = f"base_model: flat.k\noutput: o_{name}\n{extra}operations:\n{ops_body}"
    return yaml_run(binary, d, "assemble", name, body)


# ── 카탈로그 조회 도우미 ─────────────────────────────────────────────────────
def load_catalog():
    data = json.load(open(CATALOG, encoding="utf-8"))
    return {o["name"]: o for o in data["operations"]}


def cat_key(ops, opname, path):
    for k in ops[opname]["keys"]:
        if k["path"] == path:
            return k
    return None


def cat_param(ops, opname, name):
    for p in ops[opname]["params"]:
        if p["name"] == name:
            return p
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    ops = load_catalog()

    d = tempfile.mkdtemp(prefix="catparity_")
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    run(binary, d, "generate", "box", "box.yaml")

    # ── 1. 바이너리가 거절하는 값이 카탈로그에 없다 ──────────────────────────
    print("[거절되는 값은 카탈로그에서 빠졌다]")
    rc, out = asm(binary, d, "plane_xz",
                  '  - type: bend\n    target_pid: 1\n    plane: xz\n'
                  '    source: formula\n    expression: "0.1*x1"\n')
    check("assemble bend plane: xz 는 rc=1 로 거절", rc == 1 and "invalid plane" in out, out[-200:])
    check("카탈로그 operations[].plane 에 xz 없음 / zx 있음",
          cat_key(ops, "assemble", "operations[].plane")["values"] == ["xy", "yz", "zx"],
          str(cat_key(ops, "assemble", "operations[].plane")["values"]))

    rc, out = asm(binary, d, "mode_so",
                  '  - type: bend\n    target_pid: 1\n    mode: stress_only\n'
                  '    source: formula\n    expression: "0.1*x1"\n')
    check("assemble bend mode: stress_only 는 rc=1 로 거절", rc == 1 and "invalid mode" in out, out[-200:])
    modes = cat_key(ops, "assemble", "operations[].mode")["values"]
    check("카탈로그 operations[].mode 에 stress_only 없음", "stress_only" not in modes, str(modes))
    check("카탈로그 operations[].mode 는 deform/stress/prestress 를 싣는다",
          {"deform", "stress", "prestress"} <= set(modes), str(modes))

    rc, out = asm(binary, d, "src_file",
                  '  - type: bend\n    target_pid: 1\n    source: file\n    dat_file: x.dat\n')
    check("assemble bend source: file 은 rc=1 로 거절", rc == 1 and "invalid source" in out, out[-200:])
    src = cat_key(ops, "assemble", "operations[].source")
    check("카탈로그 operations[].source 에 file 없음", "file" not in src["values"], str(src["values"]))
    check("카탈로그 operations[].source 는 required", src["required"] is True, str(src))

    rc, out = asm(binary, d, "etype_hex",
                  '  - type: offset\n    source_pid: 1\n    thickness: 1.0\n    element_type: hex\n')
    check("assemble offset element_type: hex 는 rc=1 로 거절",
          rc == 1 and "element_type must be" in out, out[-200:])
    check("카탈로그 operations[].element_type 에 hex 없음",
          "hex" not in cat_key(ops, "assemble", "operations[].element_type")["values"],
          str(cat_key(ops, "assemble", "operations[].element_type")["values"]))

    # ── 2. indent 의 depth·r1·r2 는 기본값이 없다(= required) ────────────────
    print("[indent depth·r1·r2 는 기본값이 없어 required]")
    rc, out = asm(binary, d, "ind_nodepth",
                  "  - type: indent\n    target_pid: 1\n" + INDENT_SHAPE)
    check("depth 없으면 rc=1 'depth must be non-zero'",
          rc == 1 and "depth must be non-zero" in out, out[-200:])
    rc, out = asm(binary, d, "ind_nor",
                  "  - type: indent\n    target_pid: 1\n    depth: 0.5\n" + INDENT_SHAPE)
    check("r1·r2 없으면 rc=1 'r1 and r2 must be positive'",
          rc == 1 and "r1 and r2 must be positive" in out, out[-200:])
    for f in ("depth", "r1", "r2"):
        k = cat_key(ops, "assemble", f"operations[].{f}")
        check(f"카탈로그 operations[].{f} required=true, 기본값 없음",
              k["required"] is True and k.get("default") is None, str(k))

    # ── 3. 바이너리가 받는 설정을 카탈로그가 막지 않는다 ────────────────────
    print("[받는 설정은 카탈로그도 허용한다]")
    rc, out = yaml_run(binary, d, "stabilize", "stab",
                       "model: flat.k\noutput: stab.k\nlevel: 2\n")
    check("stabilize: model/output/level 만으로 rc=0 (기본 explicit)", rc == 0, out[-200:])
    for entry, label in ((cat_param(ops, "stabilize", "stabilize"), "params"),
                         (cat_key(ops, "stabilize", "stabilize"), "keys")):
        check(f"카탈로그 stabilize.{label} 의 stabilize 는 required 아님",
              entry["required"] is False, str(entry))

    check("카탈로그 matdb.keys 의 database 는 required 아님",
          cat_key(ops, "matdb", "database")["required"] is False,
          str(cat_key(ops, "matdb", "database")))
    check("카탈로그 matdb.params 의 database 는 required 아님",
          cat_param(ops, "matdb", "database")["required"] is False)

    rc, out = asm(binary, d, "of_none",
                  '  - type: offset\n    source_pid: 1\n    thickness: 1.0\n    connection_mode: none\n')
    check("assemble offset connection_mode: none 은 rc=0", rc == 0, out[-200:])
    for op, path in (("offset", "connection_mode"), ("assemble", "operations[].connection_mode")):
        vals = cat_key(ops, op, path)["values"]
        check(f"카탈로그 {op}.{path} 에 none 있음", "none" in vals, str(vals))

    rc, out = asm(binary, d, "of_both",
                  '  - type: offset\n    source_pid: 1\n    thickness: 1.0\n    offset_direction: both\n')
    check("assemble offset offset_direction: both 은 rc=0", rc == 0, out[-200:])
    for op, path in (("offset", "offset_direction"), ("assemble", "operations[].offset_direction")):
        vals = cat_key(ops, op, path)["values"]
        check(f"카탈로그 {op}.{path} 에 both 있음", "both" in vals, str(vals))

    rc, out = yaml_run(binary, d, "offset", "of_formula",
                       "model: flat.k\noutput: of_formula.k\nsource_pid: 1\n"
                       'thickness_formula: "0.5 + 0.1*x"\n')
    check("단독 offset: thickness 없이 thickness_formula 만으로 rc=0", rc == 0, out[-200:])
    check("카탈로그 offset.thickness 는 required 아님(thickness_formula 대안)",
          cat_key(ops, "offset", "thickness")["required"] is False)

    rc, out = yaml_run(binary, d, "bend", "b_nopid",
                       "model: flat.k\noutput: b_nopid.k\nsource: formula\n"
                       'expression: "0.1*x1"\n')
    check("단독 bend: target_pid 없이 rc=0 (0 = 전체 파트)", rc == 0, out[-200:])
    check("카탈로그 bend.target_pid 는 required 아님",
          cat_key(ops, "bend", "target_pid")["required"] is False,
          str(cat_key(ops, "bend", "target_pid")))

    rc, out = run(binary, d, "prestress", "--strain", "log", "flat.k", "flat.k", "pre_log.dynain")
    check("prestress --strain log 은 rc=0", rc == 0, out[-200:])
    check("카탈로그 prestress.params.strain enum 에 log 있음",
          "log" in cat_param(ops, "prestress", "strain")["enum"],
          str(cat_param(ops, "prestress", "strain")["enum"]))

    rc, out = yaml_run(binary, d, "cnrb2solid", "cn", "model: flat.k\noutput: cn_out.k\n")
    check("cnrb2solid: E/PR/RHO 없이 rc=0 (기본값 있음)", rc == 0, out[-200:])
    for f in ("E", "PR", "RHO"):
        check(f"카탈로그 cnrb2solid.params.{f} 는 required 아님",
              cat_param(ops, "cnrb2solid", f)["required"] is False)

    check("카탈로그 cclip.params.calibration 은 required 아님(clips 안에 줄 수 있다)",
          cat_param(ops, "cclip", "calibration")["required"] is False)
    rc, out = yaml_run(binary, d, "cclip", "cc",
                       "model: flat.k\noutput: cc_out\nclips:\n  - pid: 1\n    free_height: 3.0\n"
                       "    calibration:\n      point:\n        deflection: 0.5\n        force: 10.0\n")
    check("cclip: 최상위 calibration 없이 clips[].calibration 만으로 'calibration missing' 아님",
          "calibration missing" not in out, out[-200:])

    # ── 4. assemble 의 method 는 split 이 아니라 merge 의 평균법 ─────────────
    print("[assemble operations[].method 는 merge 의 평균법]")
    rc, out = asm(binary, d, "mg_voigt",
                  "  - type: merge\n    method: voigt\n    direction: z\n    target_pids: [1]\n")
    check("assemble merge method: voigt 가 실제로 Voigt 로 적용",
          rc == 0 and "method=Voigt" in out, out[-300:])
    mk = cat_key(ops, "assemble", "operations[].method")
    check("카탈로그 operations[].method 는 voigt/reuss/vrh",
          set(mk["values"]) == {"voigt", "reuss", "vrh"}, str(mk["values"]))

    # ── 5. 노트 본문이 실제 규칙을 적는다 ───────────────────────────────────
    print("[노트 본문 — update dynain 경로 / meshfix gmsh 탐색]")
    sub = os.path.join(d, "sub", "dd")
    os.makedirs(sub, exist_ok=True)
    open(os.path.join(sub, "coords.k"), "w").write(open(os.path.join(d, "flat.k")).read())
    open(os.path.join(d, "sub", "flat.k"), "w").write(open(os.path.join(d, "flat.k")).read())
    open(os.path.join(d, "sub", "u.yaml"), "w").write(
        "base_model: flat.k\noutput: upd_out\noperations:\n  - type: update\n    dynain: dd/coords.k\n")
    rc, out = run(binary, d, "assemble", "sub/u.yaml")
    check("assemble update: 'dd/coords.k' 가 YAML 폴더 기준으로 풀린다",
          rc == 0 and "sub/dd/coords.k" in out, out[-300:])
    notes = ops["assemble"]["notes"]
    check("assemble 노트가 키 이름을 dynain 으로 바로잡았다",
          "the key is `dynain`" in notes and "dynain_file path resolution" not in notes)
    mfnotes = ops["meshfix"]["notes"]
    check("meshfix 노트가 dist/gmsh 를 요구사항으로 안내하지 않는다",
          "must be placed at dist/gmsh" not in mfnotes
          and "'dist/gmsh/' next to the executable is NOT searched" in mfnotes)
    check("meshfix 노트가 실제 탐색 순서(KOOREMAPPER_GMSH→옆 gmsh/→PATH→/opt)를 적는다",
          all(t in mfnotes for t in ("KOOREMAPPER_GMSH", "<exe-dir>/gmsh/", "PATH", "/opt/gmsh-")),
          mfnotes[:400])

    # gmsh 실행 파일이 있으면 노트의 주장(dist/gmsh 는 찾지 않는다)을 실제로 확인한다
    gmsh = (os.environ.get("KOOREMAPPER_TEST_GMSH")
            or os.path.join(REPO, "dist", "gmsh", "gmsh"))
    if os.path.isfile(gmsh):
        env = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", "/tmp")}
        for layout, expect_found in (("dist/gmsh", False), ("gmsh", True)):
            g = tempfile.mkdtemp(prefix="gmshlayout_")
            gdir = os.path.join(g, "bin", *layout.split("/"))
            os.makedirs(gdir)
            exe = os.path.join(g, "bin", "KooRemapper")
            shutil.copy2(binary, exe)
            shutil.copy2(gmsh, os.path.join(gdir, "gmsh"))
            work = os.path.join(g, "work")
            os.makedirs(work)
            subprocess.run([exe, "generate", "--dim-i", "8", "--dim-j", "4", "arc", "demo"],
                           cwd=work, env=env, capture_output=True)
            open(os.path.join(work, "m.yaml"), "w").write(
                "model: demo_flat_tet.k\noutput: remeshed.k\npid: 1\nlc_target: 5.0\n")
            pr = subprocess.run([exe, "meshfix", "m.yaml"], cwd=work, env=env,
                                capture_output=True, text=True, timeout=900)
            found = "Gmsh not found" not in (pr.stdout + pr.stderr)
            check(f"바이너리 옆 bin/{layout}/gmsh 배치 → 찾음={expect_found}",
                  found is expect_found, (pr.stdout + pr.stderr)[-200:])
            shutil.rmtree(g, ignore_errors=True)
    else:
        print(f"  SKIP: gmsh 실행 파일 없음 ({gmsh}) — dist/gmsh 배치 확인 건너뜀")

    # ── 6. matdb 감쇠 설명 / database 경로 예외 ──────────────────────────────
    print("[matdb damping_preset 설명 — 프리셋을 빼도 감쇠 카드는 들어간다]")
    md = os.path.join(d, "md")
    os.makedirs(md, exist_ok=True)
    shutil.copy2(os.path.join(REPO, "materials", "smartphone_stack.k"), md)
    shutil.copy2(os.path.join(REPO, "materials", "material_db.json"), md)

    def matdb_yaml(model, out, preset=None):
        body = (f"model: {model}\noutput: {out}\ndatabase: material_db.json\n"
                "mat_type: MAT_ELASTIC\n")
        if preset is not None:
            body += f"damping_preset: {preset}\n"
        return body + 'materials:\n  - match: "*"\n'

    def damping_lines(path):
        return sum(1 for ln in open(path, encoding="utf-8", errors="ignore")
                   if ln.strip().upper().startswith("*DAMPING_PART"))

    open(os.path.join(md, "np.yaml"), "w").write(matdb_yaml("smartphone_stack.k", "md_np.k"))
    rc, out = run(binary, md, "matdb", "np.yaml")
    check("matdb: damping_preset 없이도 DB 감쇠 카드가 삽입된다",
          rc == 0 and "Inserted 3 damping sets" in out and damping_lines(os.path.join(md, "md_np.k")) == 6,
          out[-200:])

    open(os.path.join(md, "np2.yaml"), "w").write(matdb_yaml("md_np.k", "md_np2.k"))
    rc, out = run(binary, md, "matdb", "np2.yaml")
    check("matdb: 프리셋 없이 두 번 돌리면 묵은 카드가 남아 감쇠가 중복된다",
          rc == 0 and "Stripped" not in out and damping_lines(os.path.join(md, "md_np2.k")) == 12,
          out[-200:])

    open(os.path.join(md, "off2.yaml"), "w").write(matdb_yaml("md_np.k", "md_off2.k", preset="off"))
    rc, out = run(binary, md, "matdb", "off2.yaml")
    check("matdb: 값을 주면(프리셋 아닌 'off' 라도) 묵은 카드를 지우고 다시 쓴다",
          rc == 0 and "Stripped 6 pre-existing" in out and damping_lines(os.path.join(md, "md_off2.k")) == 6,
          out[-200:])

    dp = cat_key(ops, "matdb", "damping_preset")["desc"]
    check("카탈로그 damping_preset desc 에 '키를 빼면 감쇠 변화 없음' 이라는 거짓말이 없다",
          "Omit the key entirely for no damping changes" not in dp, dp[:200])
    check("카탈로그 damping_preset desc 가 삽입은 항상·값 주면 strip 을 적는다",
          "whether or not this key is present" in dp and "strips pre-existing *DAMPING_PART_*" in dp,
          dp[:300])

    # ── 7. MCP 도구 수는 소스에서 도출된다 ──────────────────────────────────
    print("[MCP 도구 수]")
    tool_count = open(MCP_SERVER, encoding="utf-8").read().count("@mcp.tool(")
    smoke_src = open(MCP_SMOKE, encoding="utf-8").read()
    check("smoke.py 에 EXPECTED_TOOLS 숫자 리터럴이 없다",
          not re.search(r"EXPECTED_TOOLS\s*=\s*\d+", smoke_src))
    check("smoke.py 의 EXPECTED_TOOLS 는 server.py 의 @mcp.tool( 수",
          '.count("@mcp.tool(")' in smoke_src)
    md = open(MCP_TOOLS_MD, encoding="utf-8").read()
    md_tools = set(re.findall(r"^\| `([a-z_]+)`", md, re.M))
    py_tools = set(re.findall(r"@mcp\.tool\([^)]*\)\s*\n(?:async )?def (\w+)",
                              open(MCP_SERVER, encoding="utf-8").read()))
    check(f"TOOLS.md 표가 server.py 의 도구 {tool_count}개를 모두 싣는다",
          md_tools == py_tools, f"md-only={sorted(md_tools - py_tools)} py-only={sorted(py_tools - md_tools)}")
    check("TOOLS.md 에 '22개 도구' 문구가 없다", "22개 도구" not in md)

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
