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
  - assemble 노트 5 는 database 도 config 폴더 기준이라고 했지만, database 만 슬래시 없는
    파일명일 때만 config 폴더 기준이고 폴더가 붙은 상대경로는 CWD 기준이라 rc=1 로 죽는다.
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

    # prestress 경로는 대수 변형률(log)이 구현돼 있지 않다 — StrainTensor::fromDeformationGradient 는
    # engineering 아니면 모두 Green-Lagrange 다. 그래서 바이너리가 거절하고 카탈로그도 싣지 않는다.
    # (log 를 진짜 계산하는 곳은 StrainCalculator 를 쓰는 strain 명령이다.)
    rc, out = run(binary, d, "prestress", "--strain", "log", "flat.k", "flat.k", "pre_log.dynain")
    check("prestress --strain log 은 rc=1 로 거절", rc == 1 and "log" in out, out[-200:])
    check("카탈로그 prestress.params.strain enum 에 log 없음",
          "log" not in cat_param(ops, "prestress", "strain")["enum"],
          str(cat_param(ops, "prestress", "strain")["enum"]))
    rc, out = run(binary, d, "strain", "--type", "log", "flat.k", "flat.k", "st_log.csv")
    check("strain --type log 은 rc=0 (StrainCalculator 가 구현)", rc == 0, out[-200:])
    check("카탈로그 strain.params.type enum 에 log 있음",
          "log" in cat_param(ops, "strain", "type")["enum"],
          str(cat_param(ops, "strain", "type")["enum"]))

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

    print("[matdb database 경로 — 슬래시가 있으면 CWD 기준]")
    sub = os.path.join(d, "dbsub")
    os.makedirs(os.path.join(sub, "mats"), exist_ok=True)
    shutil.copy2(os.path.join(md, "smartphone_stack.k"), sub)
    shutil.copy2(os.path.join(md, "material_db.json"), os.path.join(sub, "mats"))
    shutil.copy2(os.path.join(md, "material_db.json"), os.path.join(sub, "mdb.json"))
    open(os.path.join(sub, "slash.yaml"), "w").write(
        matdb_yaml("smartphone_stack.k", "out_slash.k").replace(
            "database: material_db.json", "database: mats/material_db.json"))
    open(os.path.join(sub, "noslash.yaml"), "w").write(
        matdb_yaml("smartphone_stack.k", "out_noslash.k").replace(
            "database: material_db.json", "database: mdb.json"))
    # 설정 폴더가 아닌 곳(d)에서 실행한다 — 노트 5 가 말하는 상황
    rc, out = run(binary, d, "matdb", "dbsub/slash.yaml")
    check("database: 'mats/material_db.json' (슬래시 있음) 은 CWD 기준이라 rc=1",
          rc == 1 and "Cannot load database from: mats/material_db.json" in out, out[-200:])
    rc, out = run(binary, d, "matdb", "dbsub/noslash.yaml")
    check("database: 'mdb.json' (슬래시 없음) 은 YAML 폴더 기준이라 rc=0",
          rc == 0 and "Loaded" in out, out[-200:])
    check("assemble 노트 5 가 database 를 일반 목록에서 빼고 예외로 적는다",
          "database, dynain" not in notes
          and "**`database` (matdb) is the one exception**" in notes,
          notes[:200])

    # ── 6b. 2단계 A 가 새로 거절하는 값 / 새로 받는 값 ────────────────────────
    print("[2단계 A — 새로 거절되는 열거값이 카탈로그와 맞는다]")
    LAYER = ("    layers:\n      - name: A\n        num_elements: 1\n        thickness: 1.0\n"
             "        material_card: |\n          *MAT_ELASTIC\n"
             "                   9 7.850E-09  210000.0       0.3\n")
    for val, want_ok in (("solid", True), ("tshell", True), ("shell", True),
                         ("hex", False), ("SOLID", False)):
        rc, out = asm(binary, d, "rs_" + val,
                      f"  - type: restack\n    target_pid: 1\n    element_type: {val}\n" + LAYER)
        if want_ok:
            check(f"assemble restack element_type: {val} 는 rc=0", rc == 0, out[-200:])
        else:
            check(f"assemble restack element_type: {val} 는 rc=1",
                  rc == 1 and "unsupported element_type" in out, out[-200:])
    for path in ("element_type", "layers[].element_type"):
        vals = cat_key(ops, "restack", path)["values"]
        check(f"카탈로그 restack.{path} 는 solid/tshell/shell", vals == ["solid", "tshell", "shell"], str(vals))
    vals = cat_key(ops, "assemble", "operations[].layers[].element_type")["values"]
    check("카탈로그 assemble operations[].layers[].element_type 도 solid/tshell/shell",
          vals == ["solid", "tshell", "shell"], str(vals))

    dpm = os.path.join(d, "dp")
    os.makedirs(dpm, exist_ok=True)
    shutil.copy2(os.path.join(REPO, "materials", "smartphone_stack.k"), dpm)
    shutil.copy2(os.path.join(REPO, "materials", "material_db.json"), dpm)

    def dp_yaml(preset):
        return ("model: smartphone_stack.k\noutput: dp_out.k\ndatabase: material_db.json\n"
                f"mat_type: MAT_ELASTIC\ndamping_preset: {preset}\nmaterials:\n  - match: \"*\"\n")

    for preset, want_ok in (("smartphone_drop", True), ("smartphone_drop_aggressive", True),
                            ("quasi_static", True), ("off", True), ("OFF", True),
                            ("light", False), ("custom", False)):
        open(os.path.join(dpm, "p.yaml"), "w").write(dp_yaml(preset))
        rc, out = run(binary, dpm, "matdb", "p.yaml")
        if want_ok:
            check(f"matdb damping_preset: {preset} 는 rc=0", rc == 0, out[-200:])
        else:
            check(f"matdb damping_preset: {preset} 는 rc=1",
                  rc == 1 and "unsupported damping_preset" in out, out[-200:])
    for op, path in (("matdb", "damping_preset"), ("assemble", "operations[].damping_preset")):
        vals = cat_key(ops, op, path)["values"]
        check(f"카탈로그 {op}.{path} 에 off 가 있고 3 프리셋도 있다",
              set(vals) == {"smartphone_drop", "smartphone_drop_aggressive", "quasi_static", "off"},
              str(vals))
        desc = cat_key(ops, op, path)["desc"]
        check(f"카탈로그 {op}.{path} desc 가 off 는 프리셋이 아니라고 적는다",
              "'off' is NOT a preset" in desc, desc[:200])

    print("[boundary / rbe 의 select — 서로 다른 허용값]")
    mesh = os.path.join(REPO, "examples", "load", "mesh.k")
    bd = os.path.join(d, "bd")
    os.makedirs(bd, exist_ok=True)
    shutil.copy2(mesh, bd)
    for sel, want_ok in (("direction", True), ("all", True), ("set", True), ("bogus", False)):
        open(os.path.join(bd, "b.yaml"), "w").write(
            "model: mesh.k\noutput: b_out.k\nboundaries:\n  - part: 9\n    dof: all\n"
            f"    select: {sel}\n    direction: [0, 0, -1]\n    angle: 45.0\n    set_id: 1\n")
        rc, out = run(binary, bd, "boundary", "b.yaml")
        if want_ok:
            check(f"boundary select: {sel} 는 rc=0", rc == 0, out[-200:])
        else:
            check(f"boundary select: {sel} 는 rc=1 (allowed: direction, all, set)",
                  rc == 1 and "unsupported select" in out and "direction, all, set" in out, out[-200:])
    for sel, want_ok in (("direction", True), ("all", True), ("set", False), ("bogus", False)):
        open(os.path.join(bd, "r.yaml"), "w").write(
            "model: mesh.k\noutput: r_out.k\nrbe:\n  - part: 9\n"
            f"    select: {sel}\n    direction: [0, 0, -1]\n    angle: 45.0\n")
        rc, out = run(binary, bd, "rbe", "r.yaml")
        if want_ok:
            check(f"rbe select: {sel} 는 rc=0", rc == 0, out[-200:])
        else:
            check(f"rbe select: {sel} 는 rc=1 (allowed: direction, all)",
                  rc == 1 and "unsupported select" in out and "direction, all)" in out, out[-200:])
    for op, path in (("boundary", "boundaries[].select"),
                     ("assemble", "operations[].boundaries[].select")):
        vals = cat_key(ops, op, path)["values"]
        check(f"카탈로그 {op}.{path} 는 direction/all/set", vals == ["direction", "all", "set"], str(vals))
    for op, path in (("rbe", "rbe[].select"), ("assemble", "operations[].rbe[].select")):
        vals = cat_key(ops, op, path)["values"]
        check(f"카탈로그 {op}.{path} 는 direction/all (set 없음)",
              vals == ["direction", "all"], str(vals))

    print("[contact create 의 type — 모르는 값은 경고이지 거절이 아니다]")
    ct = os.path.join(d, "ct")
    os.makedirs(ct, exist_ok=True)
    shutil.copy2(os.path.join(REPO, "examples", "contact", "model.k"), ct)

    def ct_run(name, type_line):
        open(os.path.join(ct, name + ".yaml"), "w").write(
            "model: model.k\noutput: %s.k\ncontacts:\n  - action: create\n%s"
            "    slave: { pid: 1 }\n    master: { pid: 3 }\n    title: ZZTAG\n" % (name, type_line))
        rc, out = run(binary, ct, "contact", name + ".yaml")
        kw = ""
        path = os.path.join(ct, name + ".k")
        if os.path.exists(path):
            lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
            for i, ln in enumerate(lines):
                if ln.strip() == "ZZTAG" and i:
                    kw = lines[i - 1].strip()
        return rc, out, kw

    SHORT = {"auto": "AUTOMATIC_SURFACE_TO_SURFACE", "automatic": "AUTOMATIC_SURFACE_TO_SURFACE",
             "tied": "TIED_SURFACE_TO_SURFACE", "tied_thermal": "TIED_SURFACE_TO_SURFACE_THERMAL",
             "thermal": "TIED_SURFACE_TO_SURFACE_THERMAL",
             "tiebreak": "AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK",
             "mortar": "AUTOMATIC_SURFACE_TO_SURFACE_MORTAR",
             "tied_mortar": "TIED_SURFACE_TO_SURFACE_MORTAR",
             "single": "AUTOMATIC_SINGLE_SURFACE", "eroding": "ERODING_SURFACE_TO_SURFACE",
             "forming": "FORMING_SURFACE_TO_SURFACE"}
    for short, full in SHORT.items():
        rc, out, kw = ct_run("ct_" + short, f"    type: {short}\n")
        check(f"contact type: {short} → *CONTACT_{full}",
              rc == 0 and kw == f"*CONTACT_{full}_TITLE", f"rc={rc} kw={kw}")
    rc, out, kw = ct_run("ct_omit", "")
    check("contact type 생략 → *CONTACT_AUTOMATIC_SURFACE_TO_SURFACE (빈 이름 아님)",
          rc == 0 and kw == "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_TITLE", f"rc={rc} kw={kw}")
    rc, out, kw = ct_run("ct_n2s", "    type: automatic_nodes_to_surface\n")
    check("contact type: automatic_nodes_to_surface 는 통과(경고 없음)",
          rc == 0 and kw == "*CONTACT_AUTOMATIC_NODES_TO_SURFACE_TITLE"
          and "not a known contact keyword" not in out, f"rc={rc} kw={kw}")
    rc, out, kw = ct_run("ct_bogus", "    type: bogus\n")
    check("contact type: bogus 는 rc=0 + 경고 + *CONTACT_BOGUS (거절 아님)",
          rc == 0 and kw == "*CONTACT_BOGUS_TITLE" and "not a known contact keyword" in out,
          f"rc={rc} kw={kw} {out[-200:]}")
    ctd = cat_key(ops, "contact", "contacts[].type")["desc"]
    check("카탈로그 contact contacts[].type desc 가 약칭 표와 생략 기본값을 적는다",
          "tied_thermal/thermal -> TIED_SURFACE_TO_SURFACE_THERMAL" in ctd
          and "Omitting the key gives AUTOMATIC_SURFACE_TO_SURFACE" in ctd, ctd[:200])
    ctk = cat_key(ops, "assemble", "operations[].contact.actions[].type")
    check("카탈로그 assemble contact type 은 enum 으로 좁히지 않는다(전체 키워드 허용)",
          ctk["values"] is None, str(ctk["values"]))
    check("카탈로그 assemble contact type desc 가 tied_thermal/thermal/tiebreak 비대칭을 적는다",
          "NOT aliases here" in ctk["desc"], ctk["desc"][:200])

    # detect 의 contact_type 은 create 의 type 과 값 공간이 다르다 — 약칭만 받는 닫힌 목록이라
    # 전체 LS-DYNA 키워드를 주면 rc=1 이다. 카탈로그가 'Same value space' 라고 적어 두면 틀린다.
    def dt_run(name, ctype):
        open(os.path.join(ct, name + ".yaml"), "w").write(
            "model: model.k\noutput: %s.k\ncontacts:\n  - action: detect\n    scope: all\n"
            "    tolerance: 0.5\n    auto_create: true\n    contact_type: %s\n" % (name, ctype))
        return run(binary, ct, "contact", name + ".yaml")
    dtv = cat_key(ops, "contact", "contacts[].contact_type")
    for short in ["auto", "automatic", "tied", "tied_thermal", "thermal", "tiebreak",
                  "mortar", "tied_mortar", "single", "eroding", "forming"]:
        rc, out = dt_run("dt_" + short, short)
        check("contact detect contact_type: %s 는 rc=0" % short, rc == 0, out[-200:])
    for full in ["automatic_surface_to_surface", "automatic_nodes_to_surface", "bogus"]:
        rc, out = dt_run("dt_x_" + full, full)
        check("contact detect contact_type: %s 는 rc=1 로 거절(create 와 다르다)" % full,
              rc == 1 and "unsupported contact_type" in out, f"rc={rc} {out[-200:]}")
    check("카탈로그 contacts[].contact_type values 가 약칭 11개를 싣는다",
          dtv["values"] == ["auto", "automatic", "tied", "tied_thermal", "thermal", "tiebreak",
                            "mortar", "tied_mortar", "single", "eroding", "forming"],
          str(dtv["values"]))
    check("카탈로그 contacts[].contact_type desc 가 'type 과 같은 값 공간' 이라고 적지 않는다",
          "Same value space" not in dtv["desc"] and "CLOSED whitelist" in dtv["desc"],
          dtv["desc"][:200])

    print("[contact slave/master pids — 블록 목록도 인라인과 같은 덱]")
    open(os.path.join(ct, "p_inline.yaml"), "w").write(
        "model: model.k\noutput: p_inline.k\ncontacts:\n  - action: create\n    type: tied\n"
        "    slave:\n      pids: [1, 2]\n    master:\n      pids: [3]\n    title: ZZ\n")
    open(os.path.join(ct, "p_block.yaml"), "w").write(
        "model: model.k\noutput: p_block.k\ncontacts:\n  - action: create\n    type: tied\n"
        "    slave:\n      pids:\n        - 1\n        - 2\n    master:\n      pids:\n"
        "        - 3\n    title: ZZ\n")
    run(binary, ct, "contact", "p_inline.yaml")
    run(binary, ct, "contact", "p_block.yaml")
    a = open(os.path.join(ct, "p_inline.k"), encoding="utf-8", errors="ignore").read()
    b = open(os.path.join(ct, "p_block.k"), encoding="utf-8", errors="ignore").read()
    check("pids 블록 목록 == 인라인 목록 (SET_PART 포함)",
          a == b and a.count("*SET_PART") >= 1, f"len {len(a)}/{len(b)}")
    for op, path in (("contact", "contacts[].slave.pids"),
                     ("assemble", "operations[].contact.actions[].slave.pids")):
        check(f"카탈로그 {op}.{path} desc 가 블록 목록을 적는다",
              "block list" in cat_key(ops, op, path)["desc"])

    # ── 6c. generate box 는 카탈로그에서 호출 가능하다 ─────────────────────────
    print("[generate box 는 카탈로그 params 로 조립된다]")
    sys.path.insert(0, os.path.join(REPO, "platform", "core"))
    from kooremapper_core import build_command  # noqa: E402

    gb = os.path.join(d, "gb")
    os.makedirs(gb, exist_ok=True)
    built = build_command("generate", {"subcommand": "box",
                                       "box_config": {"output": "made.k", "lx": 20.0, "ly": 10.0,
                                                      "lz": 2.0, "nx": 4, "ny": 2, "nz": 1}},
                          __import__("pathlib").Path(gb))
    check("build_command(generate, box) 가 argv ['generate','box','box_config.yaml'] 를 만든다",
          built.error is None and built.argv == ["generate", "box", "box_config.yaml"],
          f"{built.error} {built.argv}")
    rc, out = run(binary, gb, *built.argv)
    check("그 argv 로 실제 .k 가 나온다",
          rc == 0 and os.path.exists(os.path.join(gb, "made.k")), out[-200:])
    built = build_command("generate", {"type": "torus", "output_prefix": "tor"},
                          __import__("pathlib").Path(gb))
    check("type 모드 argv 는 그대로 ['generate','torus','tor']",
          built.error is None and built.argv == ["generate", "torus", "tor"],
          f"{built.error} {built.argv}")
    rc, out = run(binary, gb, *built.argv)
    check("type 모드도 실제로 돈다", rc == 0 and os.path.exists(os.path.join(gb, "tor_bent.k")), out[-200:])

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
    for rel in (("platform", "README.md"),
                ("platform", "mcp_server", "CLAUDE_DESKTOP.md"),
                ("platform", "mcp_server", "skill", "kooremapper", "SKILL.md")):
        path = os.path.join(REPO, *rel)
        txt = open(path, encoding="utf-8").read()
        stale = [m for m in re.findall(r"(?:MCP )?도구 (\d+)개|(\d+)개 도구", txt)]
        nums = {int(a or b) for a, b in stale}
        check(f"{rel[-1]} 의 도구 수가 server.py 의 {tool_count} 와 같다",
              not nums or nums == {tool_count}, str(sorted(nums)))

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
