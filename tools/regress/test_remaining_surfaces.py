# 남은 표면(map·squeeze BOM/탭, battery·tetremesh·meshfix 경로, matdb database, rbe mode, contact 별칭, boundary help) 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_remaining_surfaces.py <KooRemapper 바이너리> [gmsh 실행 파일]

배경 — 앞선 YAML 공통 규칙 정리에서 손이 닿지 않은 자리들이다.

  [H1] map <config.yaml> 만 BOM 제거·탭 들여쓰기 검사가 둘 다 없었다. 파서가 main.cpp 안에
       인라인으로 박혀 있어 다른 op 을 고친 손이 지나쳤다. BOM 을 붙이면 첫 키가 '<BOM>bent' 가
       되어 "YAML config missing required keys (bent, flat, output)" 로 끝났고, 탭으로 들여쓴
       prestress 블록은 rc=0 으로 엉뚱한 산출물을 냈다.
  [H2] squeeze <mesh> <config> <prefix> 는 탭 가드만 있고 BOM 제거가 없었다 —
       BOM 뒤 첫 키가 'parts' 면 "No parts defined in squeeze config" 로 끝났다.
  [H3] battery / tetremesh / meshfix 의 model·output 은 아직 작업 폴더 기준이라
       매뉴얼 §3.1(a)(YAML 안 상대 경로 = 그 YAML 폴더 기준)가 이 셋에서 거짓이었다.
       (modelmeta 는 이미 §3.1(a) 를 지키고 있었고, extract-surface 는 YAML 설정 자체가 없다 —
        경로를 명령줄 인자로만 받으므로 §3.1(a) 의 대상이 아니다. 둘 다 여기서 함께 못박아 둔다.)
       meshfix 는 덤으로, gmsh 가 .geo 안 Save 의 상대 경로를 '.geo 가 있는 폴더' 기준으로 풀어
       output 에 폴더가 붙으면 임시 .msh 경로가 두 번 붙던 버그도 같이 막는다.
  [H4] matdb 의 database 키만 규칙이 달랐다 — '슬래시 없는 이름' 은 YAML 폴더, '폴더가 붙은 상대
       경로' 는 작업 폴더. 이제 다른 경로 키와 같다: **YAML 폴더 기준으로 먼저 찾고, 그 자리에
       없으면 같은 파일 이름을 번들(작업 폴더 materials/, <exe>/materials/, <exe>/../materials/)에서
       찾는다. 절대 경로는 그대로, 키를 생략하면 예전처럼 번들.**
  [H5] rbe 의 mode 에 D1 검증이 없어 'mode: bogus' 가 조용히 face 모드로 돌며 rc=0 이었다
       (아래 분기가 'spider' 만 갈라내고 나머지를 전부 face 로 흘린다). select 와 같은 규칙으로 거절한다.
  [H6] assemble 의 contact create 에 단독 contact 가 가진 별칭 tied_thermal / thermal / tiebreak 가
       없어, 같은 YAML 이 단독에선 *CONTACT_TIED_SURFACE_TO_SURFACE_THERMAL, assemble 에선
       LS-DYNA 에 없는 *CONTACT_TIED_THERMAL 을 냈다. 이제 둘 다 같은 표(ct_getPreset)를 쓴다.
  [H7] legacy help 의 거짓 문구 — boundary 가 '*BOUNDARY_SPC_NODE, *RIGIDWALL_PLANAR 를 넣는다' 고
       적었지만 실제 산출은 *SET_NODE_LIST + *BOUNDARY_SPC_SET 이고 *RIGIDWALL 은 소스 어디에도 없다.
       select 허용값도 'direction | all' 이라고 적었지만 실제로는 direction | all | set 이다(set 은 set_id 필수).
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

BOX = ("output: box\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 4\nny: 3\nnz: 2\nrho: 7.85e-9\n"
       "E: 210000.0\nnu: 0.3\nmid: 1\nsecid: 1\npid: 1\n")

TAB_MSG = "YAML 들여쓰기에 탭을 쓸 수 없습니다"
MATRULE = 'mat_type: MAT_ELASTIC\nmaterials:\n  - match: "*"\n'


def check(name, cond, detail=""):
    print("  %-74s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True,
                       timeout=900, env=e)
    return p.returncode, p.stdout + p.stderr


def write(path, text, bom=False):
    with open(path, "w", encoding="utf-8") as f:
        f.write(("﻿" if bom else "") + text)


def find_gmsh(argv):
    if len(argv) > 2 and os.path.isfile(argv[2]):
        return os.path.abspath(argv[2])
    env = os.environ.get("KOOREMAPPER_TEST_GMSH")
    if env and os.path.isfile(env):
        return os.path.abspath(env)
    cand = os.path.join(REPO, "dist", "gmsh", "gmsh")
    return cand if os.path.isfile(cand) else ""


def first_contact_kw(path):
    if not os.path.exists(path):
        return ""
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("*CONTACT"):
            return line.strip()
    return ""


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    gmsh = find_gmsh(sys.argv)
    with tempfile.TemporaryDirectory() as tmp:
        rc = body(binary, gmsh, tmp)
    if FAILS:
        print("\n실패 %d건:" % len(FAILS))
        for f in FAILS:
            print("  -", f)
        return 1
    print("\nALL PASS")
    return rc


def body(binary, gmsh, tmp):
    cfg = os.path.join(tmp, "cfg")
    data = os.path.join(tmp, "data")
    os.makedirs(cfg, exist_ok=True)
    os.makedirs(data, exist_ok=True)
    write(os.path.join(data, "box.yaml"), BOX)
    rc, out = run(binary, data, "generate", "box", "box.yaml")
    if rc != 0 or not os.path.exists(os.path.join(data, "box.k")):
        print("setup failed:", out[-400:])
        return 2
    # map 은 bent/flat 두 메시가 필요하다 — 같은 상자를 두 벌로 쓴다(변형 없는 매핑)
    shutil.copy2(os.path.join(data, "box.k"), os.path.join(data, "bent.k"))
    shutil.copy2(os.path.join(data, "box.k"), os.path.join(data, "flat.k"))
    # 사면체 입력 (meshfix 용)
    tet = os.path.join(REPO, "arc30_flat_tet.k")
    has_tet = os.path.isfile(tet)
    if has_tet:
        shutil.copy2(tet, os.path.join(data, "tet.k"))

    # ── H1. map: BOM · 탭 ─────────────────────────────────────────────────────
    print("[H1] map <config.yaml> 도 BOM 을 무시하고 탭 들여쓰기를 거절한다")
    # map 의 bent/flat/output 은 아직 작업 폴더 기준이다(§3.1(a) 가 아직 닿지 않은 자리) —
    # 이 시험은 BOM·탭만 보므로, 경로 규칙이 나중에 바뀌어도 흔들리지 않게 절대 경로를 쓴다.
    MAP = ("bent: " + os.path.join(data, "bent.k") + "\n"
           "flat: " + os.path.join(data, "flat.k") + "\n"
           "output: " + os.path.join(data, "{0}") + "\n")
    write(os.path.join(cfg, "map_plain.yaml"), MAP.format("map_plain.k"))
    write(os.path.join(cfg, "map_bom.yaml"), MAP.format("map_bom.k"), bom=True)
    rp, op = run(binary, tmp, "map", "cfg/map_plain.yaml")
    rb, ob = run(binary, tmp, "map", "cfg/map_bom.yaml")
    check("map: BOM 붙은 설정이 BOM 없는 설정과 똑같이 rc=0 으로 덱을 낸다",
          rp == 0 and rb == 0 and os.path.exists(os.path.join(data, "map_bom.k")),
          f"plain rc={rp} / bom rc={rb} {ob[-250:]}")
    check("map: BOM 이 'missing required keys' 로 둔갑하지 않는다",
          "missing required keys" not in ob, ob[-250:])

    write(os.path.join(cfg, "map_tab.yaml"),
          MAP.format("map_tab.k") + "prestress:\n\tenabled: true\n\toutput: p.dynain\n")
    rc, out = run(binary, tmp, "map", "cfg/map_tab.yaml")
    check("map: 탭 들여쓰기는 rc=1 + 공통 문구 + [map] 태그",
          rc == 1 and TAB_MSG in out and "[map]" in out, f"rc={rc} {out[-250:]}")
    check("map: 탭으로 막힌 설정은 산출물을 남기지 않는다",
          not os.path.exists(os.path.join(data, "map_tab.k")))

    # ── H2. squeeze: BOM ──────────────────────────────────────────────────────
    print("[H2] squeeze <mesh> <config> <prefix> 도 BOM 을 무시한다")
    SQ = "parts:\n  - pid: 1\n    eps_x: -0.01\n    eps_y: -0.01\n    eps_z: 0.0\nmaterial:\n  E: 210000.0\n  nu: 0.3\n"
    write(os.path.join(cfg, "sq_plain.yaml"), SQ)
    write(os.path.join(cfg, "sq_bom.yaml"), SQ, bom=True)
    rp, op = run(binary, data, "squeeze", "box.k", "../cfg/sq_plain.yaml", "sq_plain")
    rb, ob = run(binary, data, "squeeze", "box.k", "../cfg/sq_bom.yaml", "sq_bom")
    check("squeeze: BOM 붙은 설정이 BOM 없는 설정과 똑같이 rc=0",
          rp == 0 and rb == 0 and os.path.exists(os.path.join(data, "sq_bom.k")),
          f"plain rc={rp} / bom rc={rb} {ob[-250:]}")
    check("squeeze: BOM 이 'No parts defined' 로 둔갑하지 않는다",
          "No parts defined" not in ob, ob[-250:])

    # ── H3. 경로 규칙 ─────────────────────────────────────────────────────────
    print("[H3] battery/tetremesh/meshfix 의 YAML 안 상대 경로 = YAML 폴더 기준 (§3.1(a))")
    write(os.path.join(cfg, "bat.yaml"),
          "output: ../data/bat\nmodel_type: stacked\ntier: 0\nphase: 1\n"
          "geometry:\n  n_unit_cells: 1\n")
    rc, out = run(binary, tmp, "battery", "cfg/bat.yaml")
    check("battery: output '../data/bat' 이 YAML 폴더(cfg) 기준으로 풀린다",
          rc == 0 and os.path.exists(os.path.join(data, "bat_tier0_phase1.k")) and
          not os.path.exists(os.path.join(tmp, "bat_tier0_phase1.k")), f"rc={rc} {out[-250:]}")

    write(os.path.join(cfg, "tr.yaml"),
          "model: ../data/box.k\noutput: ../data/tr_out.k\nreport_only: false\n")
    rc, out = run(binary, tmp, "tetremesh", "cfg/tr.yaml")
    check("tetremesh: model/output 이 YAML 폴더(cfg) 기준으로 풀린다",
          rc == 0 and os.path.exists(os.path.join(data, "tr_out.k")) and
          not os.path.exists(os.path.join(tmp, "tr_out.k")), f"rc={rc} {out[-250:]}")

    if gmsh and has_tet:
        env = {"KOOREMAPPER_GMSH": gmsh}
        write(os.path.join(cfg, "mf.yaml"),
              "model: ../data/tet.k\noutput: ../data/mf_out.k\npid: 1\nlc_target: 3.0\n")
        rc, out = run(binary, tmp, "meshfix", "cfg/mf.yaml", env=env)
        check("meshfix: model/output 이 YAML 폴더(cfg) 기준으로 풀린다",
              rc == 0 and os.path.exists(os.path.join(data, "mf_out.k")) and
              not os.path.exists(os.path.join(tmp, "mf_out.k")), f"rc={rc} {out[-400:]}")
        # gmsh 의 Save 상대 경로는 .geo 폴더 기준이라, 폴더가 붙은 output 에서 경로가 두 번 붙었다
        os.makedirs(os.path.join(data, "sub"), exist_ok=True)
        write(os.path.join(data, "mf_sub.yaml"),
              "model: tet.k\noutput: sub/mf_sub.k\npid: 1\nlc_target: 3.0\n")
        rc, out = run(binary, data, "meshfix", "mf_sub.yaml", env=env)
        check("meshfix: output 에 폴더가 붙어도 임시 .msh 경로가 두 번 붙지 않는다",
              rc == 0 and os.path.exists(os.path.join(data, "sub", "mf_sub.k")),
              f"rc={rc} {out[-400:]}")
    else:
        print("  SKIP: gmsh 또는 사면체 입력이 없어 meshfix 는 건너뜀")

    # modelmeta 는 이미 §3.1(a) 를 지키고 있었다 — 되돌아가지 않도록 못박는다
    write(os.path.join(cfg, "mm.yaml"), "model: ../data/box.k\noutput: ../data/mm_out\n")
    rc, out = run(binary, tmp, "modelmeta", "cfg/mm.yaml")
    check("modelmeta: model/output 이 YAML 폴더(cfg) 기준 (예전부터 그랬다 — 유지)",
          rc == 0 and os.path.exists(os.path.join(data, "mm_out_modelmeta.json")),
          f"rc={rc} {out[-250:]}")

    # extract-surface 는 YAML 설정이 없다 — 경로는 명령줄 인자뿐이라 §3.1(a) 대상이 아니다
    rc, out = run(binary, tmp, "extract-surface", "data/box.k", "data/es_out.k", "--face", "top")
    check("extract-surface: 경로를 명령줄 인자로 받고 작업 폴더 기준으로 동작 (YAML 설정 없음)",
          rc == 0 and os.path.exists(os.path.join(data, "es_out.k")), f"rc={rc} {out[-250:]}")
    rc, out = run(binary, tmp, "extract-surface", "cfg/mm.yaml", "x.k")
    check("extract-surface: YAML 을 solid 입력으로 줘도 설정으로 읽지 않는다 (rc=1)",
          rc == 1, f"rc={rc} {out[-250:]}")

    # ── H4. matdb database 키 ─────────────────────────────────────────────────
    print("[H4] matdb database: YAML 폴더 먼저, 없으면 번들 — 다른 경로 키와 같은 규칙")
    repo_db = os.path.join(REPO, "materials", "material_db.json")
    if not os.path.isfile(repo_db):
        print("  SKIP: materials/material_db.json 이 없음")
    else:
        MD = "model: ../data/box.k\noutput: ../data/{0}\ndatabase: {1}\n" + MATRULE
        # (1) 슬래시 없는 이름 + YAML 폴더에 사본 → 그 사본
        shutil.copy2(repo_db, os.path.join(cfg, "material_db.json"))
        write(os.path.join(cfg, "md1.yaml"), MD.format("md_local.k", "material_db.json"))
        rc, out = run(binary, tmp, "matdb", "cfg/md1.yaml")
        check("matdb: 'database: material_db.json' 이 YAML 폴더의 사본을 쓴다",
              rc == 0 and os.path.exists(os.path.join(data, "md_local.k")), f"rc={rc} {out[-250:]}")
        # (2) 폴더가 붙은 상대 경로 → 작업 폴더가 아니라 YAML 폴더 기준
        os.makedirs(os.path.join(cfg, "db"), exist_ok=True)
        shutil.copy2(repo_db, os.path.join(cfg, "db", "material_db.json"))
        os.remove(os.path.join(cfg, "material_db.json"))
        write(os.path.join(cfg, "md2.yaml"), MD.format("md_sub.k", "db/material_db.json"))
        rc, out = run(binary, tmp, "matdb", "cfg/md2.yaml")
        check("matdb: 'database: db/material_db.json' 도 YAML 폴더 기준 (예전엔 작업 폴더였다)",
              rc == 0 and os.path.exists(os.path.join(data, "md_sub.k")), f"rc={rc} {out[-250:]}")
        # (3) 절대 경로는 그대로
        write(os.path.join(cfg, "md3.yaml"), MD.format("md_abs.k", repo_db))
        rc, out = run(binary, tmp, "matdb", "cfg/md3.yaml")
        check("matdb: 절대 경로는 그대로 쓴다",
              rc == 0 and os.path.exists(os.path.join(data, "md_abs.k")), f"rc={rc} {out[-250:]}")
        # (4) 없는 이름 → YAML 폴더 경로로 실패 메시지
        write(os.path.join(cfg, "md4.yaml"), MD.format("md_bad.k", "nope.json"))
        rc, out = run(binary, tmp, "matdb", "cfg/md4.yaml")
        check("matdb: 못 찾으면 rc=1 이고 메시지에 YAML 폴더 경로(cfg/nope.json)가 찍힌다",
              rc == 1 and "cfg/nope.json" in out, f"rc={rc} {out[-250:]}")
        # (5) 번들 폴백 — 작업 폴더 materials/ 에 두고 YAML 폴더엔 두지 않는다
        os.makedirs(os.path.join(tmp, "materials"), exist_ok=True)
        shutil.copy2(repo_db, os.path.join(tmp, "materials", "material_db.json"))
        write(os.path.join(cfg, "md5.yaml"), MD.format("md_bundle.k", "material_db.json"))
        rc, out = run(binary, tmp, "matdb", "cfg/md5.yaml")
        check("matdb: YAML 폴더에 없으면 번들(materials/) 에서 같은 이름을 찾는다",
              rc == 0 and os.path.exists(os.path.join(data, "md_bundle.k")), f"rc={rc} {out[-250:]}")
        # (6) 키를 생략하면 예전처럼 번들
        write(os.path.join(cfg, "md6.yaml"),
              "model: ../data/box.k\noutput: ../data/md_def.k\n" + MATRULE)
        rc, out = run(binary, tmp, "matdb", "cfg/md6.yaml")
        check("matdb: database 키를 생략하면 번들 DB (예전과 같다)",
              rc == 0 and os.path.exists(os.path.join(data, "md_def.k")), f"rc={rc} {out[-250:]}")

    # ── H5. rbe mode ──────────────────────────────────────────────────────────
    print("[H5] rbe 의 mode 는 spider | face 뿐 — 모르는 값은 rc=1 (D1)")
    RBE = ("model: box.k\noutput: rbe_{0}.k\nrbe:\n  - part: 1\n    select: all\n"
           "    type: rbe2\n    mode: {0}\n")
    for mode in ("spider", "face"):
        write(os.path.join(data, f"rbe_{mode}.yaml"), RBE.format(mode))
        rc, out = run(binary, data, "rbe", f"rbe_{mode}.yaml")
        check(f"rbe: 실제 지원값 '{mode}' 는 rc=0 으로 덱을 낸다",
              rc == 0 and os.path.exists(os.path.join(data, f"rbe_{mode}.k")), f"rc={rc} {out[-250:]}")
    write(os.path.join(data, "rbe_bogus.yaml"), RBE.format("bogus"))
    rc, out = run(binary, data, "rbe", "rbe_bogus.yaml")
    check("rbe: 'mode: bogus' 는 rc=1 + 허용값 출력 (예전엔 조용히 face 로 돌았다)",
          rc == 1 and "unsupported mode 'bogus'" in out and "spider, face" in out,
          f"rc={rc} {out[-250:]}")
    check("rbe: 막힌 설정은 산출물을 남기지 않는다",
          not os.path.exists(os.path.join(data, "rbe_bogus.k")))
    write(os.path.join(data, "rbe_asm.yaml"),
          "base_model: box.k\noutput: rbe_asm\noperations:\n  - type: rbe\n    rbe:\n"
          "      - part: 1\n        select: all\n        type: rbe2\n        mode: bogus\n")
    rc, out = run(binary, data, "assemble", "rbe_asm.yaml")
    check("rbe: assemble 도 같은 문구로 rc=1 (단독과 같은 자리에서 검사)",
          rc == 1 and "unsupported mode 'bogus'" in out, f"rc={rc} {out[-250:]}")

    # ── H6. contact 별칭 단독 == assemble ─────────────────────────────────────
    print("[H6] contact create 의 짧은 이름이 단독과 assemble 에서 같은 키워드를 낸다")
    ALIASES = {
        "auto": "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE",
        "automatic": "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE",
        "tied": "*CONTACT_TIED_SURFACE_TO_SURFACE",
        "tied_thermal": "*CONTACT_TIED_SURFACE_TO_SURFACE_THERMAL",
        "thermal": "*CONTACT_TIED_SURFACE_TO_SURFACE_THERMAL",
        "tiebreak": "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK",
        "mortar": "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_MORTAR",
        "tied_mortar": "*CONTACT_TIED_SURFACE_TO_SURFACE_MORTAR",
        "single": "*CONTACT_AUTOMATIC_SINGLE_SURFACE",
        "eroding": "*CONTACT_ERODING_SURFACE_TO_SURFACE",
        "forming": "*CONTACT_FORMING_SURFACE_TO_SURFACE",
    }
    for alias, kw in ALIASES.items():
        write(os.path.join(data, f"cs_{alias}.yaml"),
              f"model: box.k\noutput: cs_{alias}.k\ncontacts:\n  - action: create\n"
              f"    type: {alias}\n    slave: {{ pid: 1 }}\n    master: {{ pid: 1 }}\n")
        write(os.path.join(data, f"ca_{alias}.yaml"),
              f"base_model: box.k\noutput: ca_{alias}\noperations:\n  - type: contact\n"
              f"    contacts:\n      - action: create\n        type: {alias}\n"
              "        slave:\n          pid: 1\n        master:\n          pid: 1\n")
        rs, os_ = run(binary, data, "contact", f"cs_{alias}.yaml")
        ra, oa = run(binary, data, "assemble", f"ca_{alias}.yaml")
        a = first_contact_kw(os.path.join(data, f"cs_{alias}.k"))
        b = first_contact_kw(os.path.join(data, f"ca_{alias}.k"))
        check(f"contact: '{alias}' → 단독·assemble 둘 다 {kw}",
              rs == 0 and ra == 0 and a.startswith(kw) and a == b,
              f"alone={a!r} asm={b!r}")
        check(f"contact: '{alias}' 는 아는 키워드라 경고가 없다 (단독·assemble 모두)",
              "not a known contact keyword" not in os_ and
              "not a known contact keyword" not in oa)
    # 대시는 밑줄과 같게 푼다 (단독이 쓰던 규칙)
    write(os.path.join(data, "cs_dash.yaml"),
          "model: box.k\noutput: cs_dash.k\ncontacts:\n  - action: create\n"
          "    type: tied-surface-to-surface\n    slave: { pid: 1 }\n    master: { pid: 1 }\n")
    write(os.path.join(data, "ca_dash.yaml"),
          "base_model: box.k\noutput: ca_dash\noperations:\n  - type: contact\n    contacts:\n"
          "      - action: create\n        type: tied-surface-to-surface\n"
          "        slave:\n          pid: 1\n        master:\n          pid: 1\n")
    run(binary, data, "contact", "cs_dash.yaml")
    run(binary, data, "assemble", "ca_dash.yaml")
    a = first_contact_kw(os.path.join(data, "cs_dash.k"))
    b = first_contact_kw(os.path.join(data, "ca_dash.k"))
    check("contact: '-' 는 '_' 와 같게 풀리고 단독·assemble 이 같다",
          a.startswith("*CONTACT_TIED_SURFACE_TO_SURFACE") and a == b, f"alone={a!r} asm={b!r}")
    # 표 밖의 값은 양쪽 다 경고만 찍고 그대로 통과
    write(os.path.join(data, "cs_bogus.yaml"),
          "model: box.k\noutput: cs_bogus.k\ncontacts:\n  - action: create\n    type: bogus\n"
          "    slave: { pid: 1 }\n    master: { pid: 1 }\n")
    write(os.path.join(data, "ca_bogus.yaml"),
          "base_model: box.k\noutput: ca_bogus\noperations:\n  - type: contact\n    contacts:\n"
          "      - action: create\n        type: bogus\n        slave:\n          pid: 1\n"
          "        master:\n          pid: 1\n")
    rs, os_ = run(binary, data, "contact", "cs_bogus.yaml")
    ra, oa = run(binary, data, "assemble", "ca_bogus.yaml")
    check("contact: 표 밖의 값은 단독·assemble 둘 다 경고 후 *CONTACT_BOGUS 로 통과",
          rs == 0 and ra == 0 and
          "not a known contact keyword" in os_ and "not a known contact keyword" in oa and
          first_contact_kw(os.path.join(data, "cs_bogus.k")).startswith("*CONTACT_BOGUS") and
          first_contact_kw(os.path.join(data, "ca_bogus.k")).startswith("*CONTACT_BOGUS"),
          f"alone rc={rs} asm rc={ra}")

    # ── H7. boundary / rbe help 의 진실성 ─────────────────────────────────────
    print("[H7] legacy help 가 실제 산출·허용값과 같은 말을 한다")
    rc, hb = run(binary, tmp, "help", "boundary")
    check("help boundary: *RIGIDWALL 을 더는 약속하지 않는다 (소스에 없다)",
          "RIGIDWALL" not in hb, [l for l in hb.splitlines() if "RIGIDWALL" in l])
    check("help boundary: 실제 산출 키워드 *SET_NODE_LIST + *BOUNDARY_SPC_SET 를 적는다",
          "*SET_NODE_LIST" in hb and "*BOUNDARY_SPC_SET" in hb,
          [l for l in hb.splitlines() if "Inserts" in l])
    check("help boundary: *BOUNDARY_SPC_NODE 를 적지 않는다",
          "BOUNDARY_SPC_NODE" not in hb)
    check("help boundary: select 허용값 direction | all | set 을 적고 set_id 가 필수임을 밝힌다",
          "direction | all | set" in hb and "set_id" in hb,
          [l for l in hb.splitlines() if "select" in l or "set_id" in l])
    rc, hr = run(binary, tmp, "help", "rbe")
    check("help rbe: mode 허용값 spider | face 를 적는다",
          "spider | face" in hr, [l for l in hr.splitlines() if "mode" in l])
    check("help rbe: select 은 direction | all 둘뿐이라고 적는다 (boundary 와 다르다)",
          "direction | all" in hr and "direction | all | set" not in hr,
          [l for l in hr.splitlines() if "select" in l])

    # 문구가 실제 산출과 같은지 덱으로 확인
    write(os.path.join(data, "bnd.yaml"),
          "model: box.k\noutput: bnd_out.k\nboundaries:\n  - part: 1\n    dof: all\n"
          "    direction: [0, 0, -1]\n    select: direction\n    angle: 45.0\n")
    rc, out = run(binary, data, "boundary", "bnd.yaml")
    deck = (open(os.path.join(data, "bnd_out.k"), encoding="utf-8", errors="replace").read()
            if os.path.exists(os.path.join(data, "bnd_out.k")) else "")
    check("boundary: 실제 덱에 *SET_NODE_LIST 와 *BOUNDARY_SPC_SET 이 들어간다",
          rc == 0 and "*SET_NODE_LIST" in deck and "*BOUNDARY_SPC_SET" in deck, f"rc={rc}")
    check("boundary: 실제 덱에 *RIGIDWALL 도 *BOUNDARY_SPC_NODE 도 없다",
          "*RIGIDWALL" not in deck and "*BOUNDARY_SPC_NODE" not in deck)
    write(os.path.join(data, "bnd_all.yaml"),
          "model: box.k\noutput: bnd_all.k\nboundaries:\n  - part: 1\n    dof: all\n"
          "    select: all\n")
    rc, out = run(binary, data, "boundary", "bnd_all.yaml")
    check("boundary: select: all 이 실제로 동작한다", rc == 0 and
          os.path.exists(os.path.join(data, "bnd_all.k")), f"rc={rc} {out[-250:]}")
    write(os.path.join(data, "bnd_set.yaml"),
          "model: box.k\noutput: bnd_set.k\nboundaries:\n  - part: 1\n    dof: all\n"
          "    select: set\n    set_id: 7\n")
    rc, out = run(binary, data, "boundary", "bnd_set.yaml")
    check("boundary: select: set + set_id 가 실제로 동작한다", rc == 0 and
          os.path.exists(os.path.join(data, "bnd_set.k")), f"rc={rc} {out[-250:]}")
    write(os.path.join(data, "bnd_set_noid.yaml"),
          "model: box.k\noutput: bnd_set_noid.k\nboundaries:\n  - part: 1\n    dof: all\n"
          "    select: set\n")
    rc, out = run(binary, data, "boundary", "bnd_set_noid.yaml")
    check("boundary: select: set 에 set_id 가 없으면 rc=1 (help 가 필수라고 적은 대로)",
          rc == 1 and "set_id" in out, f"rc={rc} {out[-250:]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
