# YAML 공통 규칙(BOM·탭 들여쓰기·상대 경로) + contact pids 블록 목록·type 허용값 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_yaml_common_rules.py <KooRemapper 바이너리>

배경
  - UTF-8 BOM: 윈도우 편집기가 기본으로 붙이는 세 바이트가 첫 키에 붙어 'model'/'base_model' 이
    매칭되지 않았다. 20여 개 단독 op 과 assemble 이 통째로 "model not specified" 로 끝났고
    에러 메시지에는 BOM 이라는 힌트가 없었다.
  - 탭 들여쓰기: 파서마다 흩어져 있던 countIndent 가 공백만 세서, 탭으로 들여쓴 YAML 은 모든 줄이
    indent 0 이 되어 블록(loads·operations·clips…)이 통째로 무너졌다. 대부분 rc=0 으로 '아무 일도
    안 한' 덱이 나왔다. 이제 YAML 을 읽는 모든 명령이 같은 문구로 rc=1 로 거절한다.
    단, 따옴표 값 안의 탭과 '|' 블록 안(공백으로 더 깊이 들여쓴 줄)의 탭은 값이므로 막지 않는다.
    '|' 블록 안이라는 판정은 파서(공백만 세는 countIndent)와 같아야 한다 — 한때 스캐너만 탭 줄을
    블록 안으로 봐 통과시켜, 파서가 그 카드 줄을 블록 밖으로 튕겨 버린 *MAT 카드가 데이터 줄 없이
    덱에 실리고도 rc=0 이었다.
  - 탭 검사는 파일 전체를 훑는다 — op 이 읽지도 않는 구역(메모·미사용 키)을 탭으로 들여쓴,
    예전엔 올바른 덱을 내던 설정도 rc=1 이 된다. 문구에는 몇 번째 줄인지 붙는다.
  - 탭 검사는 설정 파일을 '한 번 더' 여는데, 되감을 수 없는 입력(파이프·프로세스 치환)이면 그 한 번이
    전부라 파서가 빈 설정을 봤다 — 그런 입력에서는 검사를 건너뛴다.
  - 상대 경로: assemble·strip·단독 op 은 'YAML 안의 상대 경로 = 그 YAML 폴더 기준' 인데
    load/boundary/rbe/contact/relax/database/explicit/implicit/modal/ale/cclip/matdb/generate 는
    폴더 없는 이름만 그 규칙이고 '../data/box.k' 는 작업 폴더에서 찾아 열지 못했다.
  - contact slave:/master: 밑의 'pids:' 를 블록 목록('- 1')으로 쓰면 조용히 버려져 SET_PART 가
    만들어지지 않았다(인라인 'pids: [1]' 만 동작).
  - contact create 의 'type:' 은 짧은 이름을 풀어 주지 않고 허용값 검증도 없어, assemble 에서
    AUTOMATIC_SURFACE_TO_SURFACE 가 되는 'type: auto' 가 단독 contact 에서는 LS-DYNA 에 없는
    *CONTACT_AUTO 가 됐다. 이제 assemble 과 같은 표(ct_getPreset)를 쓰고, 표에도 없고 아는
    키워드도 아닌 값은 rc=1 로 거절한다.
"""
import os
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

BOX = ("output: box\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 2\nny: 2\nnz: 1\nrho: 7.85e-9\n"
       "E: 210000.0\nnu: 0.3\nmid: 1\nsecid: 1\npid: 1\n")

TAB_MSG = "YAML 들여쓰기에 탭을 쓸 수 없습니다"

# YAML 한 개만 인자로 받는 명령 전부 (main.cpp 의 dispatch 기준)
ONE_ARG_CMDS = [
    "load", "boundary", "rbe", "strip", "merge", "contact", "relax", "explicit", "implicit",
    "modal", "ale", "database", "optimize", "stabilize", "matdb", "cclip", "convert", "refine",
    "elform", "restack", "bend", "indent", "formstrain", "disconnect", "iga", "warpage",
    "offset", "wrap", "update", "cnrb2solid", "hfdamp", "battery", "modelmeta", "assemble",
    "matswap", "tetremesh", "meshfix",
]

# BOM 을 붙여도 첫 키를 읽는지 — 같은 설정을 BOM 있이/없이 돌려 결과가 같은지 본다
BOM_CMDS = [c for c in ONE_ARG_CMDS if c != "assemble"]


def check(name, cond, detail=""):
    print("  %-72s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def write(path, text, bom=False):
    with open(path, "w", encoding="utf-8") as f:
        f.write(("﻿" if bom else "") + text)


def errs(out):
    return [l for l in out.splitlines() if "[ERROR]" in l]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    with tempfile.TemporaryDirectory() as tmp:
        return body(binary, tmp)


def body(binary, tmp):
    cfg = os.path.join(tmp, "cfg")
    data = os.path.join(tmp, "data")
    os.makedirs(cfg, exist_ok=True)
    os.makedirs(data, exist_ok=True)
    write(os.path.join(data, "box.yaml"), BOX)
    rc, out = run(binary, data, "generate", "box", "box.yaml")
    if rc != 0 or not os.path.exists(os.path.join(data, "box.k")):
        print("setup failed:", out[-400:])
        return 2

    # ── 1. BOM ────────────────────────────────────────────────────────────────
    print("[BOM: 첫 키가 망가지지 않는다]")
    write(os.path.join(cfg, "bom.yaml"), "model: nope.k\noutput: out.k\n", bom=True)
    write(os.path.join(cfg, "plain.yaml"), "model: nope.k\noutput: out.k\n")
    for cmd in BOM_CMDS:
        rb, ob = run(binary, tmp, cmd, "cfg/bom.yaml")
        rp, op = run(binary, tmp, cmd, "cfg/plain.yaml")
        check(f"BOM: {cmd} 가 BOM 없는 설정과 똑같이 동작",
              (rb, errs(ob)) == (rp, errs(op)) and
              not any("'model' not specified" in l or "model not specified" in l for l in errs(ob)),
              f"bom rc={rb} {errs(ob)[:1]} / plain rc={rp} {errs(op)[:1]}")

    write(os.path.join(cfg, "bomasm.yaml"),
          "base_model: nope.k\noutput: out\noperations:\n  - type: hex20\n", bom=True)
    rc, out = run(binary, tmp, "assemble", "cfg/bomasm.yaml")
    check("BOM: assemble 의 base_model 도 읽힌다 (base_model not specified 가 아니다)",
          "base_model not specified" not in out, out[-200:])

    # BOM 붙은 설정이 실제로 끝까지 돌아 산출물을 낸다
    write(os.path.join(cfg, "bomconv.yaml"),
          "model: ../data/box.k\noutput: ../data/bom_hex20.k\ntype: hex20\n", bom=True)
    rc, out = run(binary, tmp, "convert", "cfg/bomconv.yaml")
    check("BOM: convert 가 rc=0 으로 끝나고 산출 k 가 생긴다",
          rc == 0 and os.path.exists(os.path.join(data, "bom_hex20.k")), f"rc={rc} {out[-200:]}")

    write(os.path.join(cfg, "bomasm2.yaml"),
          "base_model: ../data/box.k\noutput: ../data/bom_asm\noperations:\n  - type: hex20\n", bom=True)
    rc, out = run(binary, tmp, "assemble", "cfg/bomasm2.yaml")
    check("BOM: assemble 이 rc=0 으로 끝나고 산출 k 가 생긴다",
          rc == 0 and os.path.exists(os.path.join(data, "bom_asm.k")), f"rc={rc} {out[-200:]}")

    LOAD_CASE = "loads:\n  - part: 1\n    mode: normal_pressure\n    value: 1.0\n"

    # ── 2. 탭 들여쓰기 ────────────────────────────────────────────────────────
    print("[탭 들여쓰기: 모든 YAML 명령이 같은 문구로 rc=1]")
    write(os.path.join(cfg, "tab.yaml"), "model: ../data/box.k\noutput: ../data/t.k\nfoo:\n\t- a: 1\n")
    for cmd in ONE_ARG_CMDS:
        rc, out = run(binary, tmp, cmd, "cfg/tab.yaml")
        check(f"탭: {cmd} 가 rc=1 + 공통 문구로 거절",
              rc == 1 and TAB_MSG in out and f"[{cmd}]" in out, f"rc={rc} {out[-200:]}")
    rc, out = run(binary, tmp, "generate", "box", "cfg/tab.yaml")
    check("탭: generate box 도 rc=1 + 공통 문구", rc == 1 and TAB_MSG in out, f"rc={rc} {out[-200:]}")
    rc, out = run(binary, tmp, "squeeze", "data/box.k", "cfg/tab.yaml", "data/sq")
    check("탭: squeeze 도 rc=1 + 공통 문구", rc == 1 and TAB_MSG in out, f"rc={rc} {out[-200:]}")
    rc, out = run(binary, tmp, "generate-var", "cfg/tab.yaml", "data/gv")
    check("탭: generate-var 도 rc=1 + 공통 문구", rc == 1 and TAB_MSG in out, f"rc={rc} {out[-200:]}")

    # 탭이 없으면 같은 구조가 그대로 돈다
    write(os.path.join(cfg, "notab.yaml"),
          "model: ../data/box.k\noutput: ../data/notab.k\nloads:\n  - part: 1\n"
          "    mode: normal_pressure\n    value: 1.0\n")
    rc, out = run(binary, tmp, "load", "cfg/notab.yaml")
    check("탭: 공백 들여쓰기 같은 설정은 그대로 rc=0",
          rc == 0 and os.path.exists(os.path.join(data, "notab.k")), f"rc={rc} {out[-200:]}")

    # '|' 블록 안이라는 판정은 파서와 같다(공백만 들여쓰기) — 탭으로 시작한 카드 줄은 블록 밖이라
    # 구조 줄로 보아 rc=1 이다. 예전엔 스캐너만 통과시켜 그 카드 줄이 조용히 사라졌다.
    write(os.path.join(cfg, "blocktab.yaml"),
          "model: ../data/box.k\noutput: ../data/blocktab.k\nsource_pid: 1\nthickness: 0.5\n"
          "material_cards:\n  - |\n    *MAT_ELASTIC_TITLE\n    Tabbed\n\t2,7.8e-9,2.0e5,0.3\n")
    rc, out = run(binary, tmp, "offset", "cfg/blocktab.yaml")
    check("탭: '|' 블록 안의 탭 줄은 파서가 버리던 줄이라 rc=1 로 막는다",
          rc == 1 and TAB_MSG in out and
          not os.path.exists(os.path.join(data, "blocktab.k")), f"rc={rc} {out[-200:]}")
    # 통제군 — 같은 카드 줄을 공백으로 들여쓰면 rc=0 이고 카드 내용이 산출 덱에 다 들어간다
    write(os.path.join(cfg, "blockok.yaml"),
          "model: ../data/box.k\noutput: ../data/blockok.k\nsource_pid: 1\nthickness: 0.5\n"
          "material_cards:\n  - |\n    *MAT_ELASTIC_TITLE\n    Tabbed\n    2,7.8e-9,2.0e5,0.3\n")
    rc, out = run(binary, tmp, "offset", "cfg/blockok.yaml")
    deck = (open(os.path.join(data, "blockok.k")).read()
            if os.path.exists(os.path.join(data, "blockok.k")) else "")
    check("탭: 공백으로 들여쓴 '|' 블록은 카드 내용이 산출 덱에 다 들어간다",
          rc == 0 and TAB_MSG not in out and "*MAT_ELASTIC_TITLE" in deck and
          "2,7.8e-9,2.0e5,0.3" in deck, f"rc={rc} {out[-200:]}")
    # 블록 안(공백으로 더 깊이 들여쓴 줄) 값 중간의 탭은 값이라 막지 않는다
    write(os.path.join(cfg, "blockmid.yaml"),
          "model: ../data/box.k\noutput: ../data/blockmid.k\nsource_pid: 1\nthickness: 0.5\n"
          "material_cards:\n  - |\n    *MAT_ELASTIC_TITLE\n    Mid\n    2,7.8e-9\t,2.0e5,0.3\n")
    rc, out = run(binary, tmp, "offset", "cfg/blockmid.yaml")
    check("탭: '|' 블록 값 중간의 탭은 들여쓰기가 아니라 막지 않는다",
          rc == 0 and TAB_MSG not in out, f"rc={rc} {out[-200:]}")
    # 같은 파일에서 구조 줄이 탭이면 거절
    write(os.path.join(cfg, "blocktab2.yaml"),
          "model: ../data/box.k\noutput: ../data/blocktab2.k\nsource_pid: 1\n\tthickness: 0.5\n"
          "material_cards:\n  - |\n    *MAT_ELASTIC_TITLE\n    T2\n    2,7.8e-9,2.0e5,0.3\n")
    rc, out = run(binary, tmp, "offset", "cfg/blocktab2.yaml")
    check("탭: 같은 파일의 구조 줄 탭은 rc=1", rc == 1 and TAB_MSG in out, f"rc={rc} {out[-200:]}")
    check("탭: 문구에 몇 번째 줄인지 붙는다 (blocktab2.yaml 의 4번째 줄)",
          "4번째 줄: thickness: 0.5" in out, f"rc={rc} {out[-200:]}")
    # 따옴표 값 안의 탭도 값이다
    write(os.path.join(cfg, "qtab.yaml"),
          "model: ../data/box.k\noutput: \"../data/q\ttab.k\"\nkeywords:\n  - CONTACT\n")
    rc, out = run(binary, tmp, "strip", "cfg/qtab.yaml")
    check("탭: 따옴표 값 안의 탭은 들여쓰기가 아니라 막지 않는다",
          TAB_MSG not in out, f"rc={rc} {out[-200:]}")

    # 되감을 수 없는 입력(파이프)도 설정이 통째로 도착한다 — 탭 검사가 파일을 '한 번 더' 열기 때문에
    # 한때 파이프·프로세스 치환으로 넘긴 YAML 은 파서가 빈 설정을 보고 "'model' not specified" 로 끝났다.
    # 그런 입력에서는 탭 검사를 건너뛴다(한 번 읽으면 끝인 스트림이라 검사와 파싱을 같이 할 수 없다).
    if os.path.exists("/dev/stdin"):
        print("[파이프 입력: 되감을 수 없는 스트림도 설정이 통째로 도착한다]")
        pipe_cfg = (f"model: {os.path.join(data, 'box.k')}\n"
                    f"output: {os.path.join(data, 'pipe_out.k')}\n" + LOAD_CASE)
        pp = subprocess.run([binary, "load", "/dev/stdin"], cwd=tmp, input=pipe_cfg,
                            capture_output=True, text=True, timeout=300)
        pout = pp.stdout + pp.stderr
        check("파이프: load /dev/stdin 이 rc=0 으로 덱을 낸다",
              pp.returncode == 0 and os.path.exists(os.path.join(data, "pipe_out.k")),
              f"rc={pp.returncode} {pout[-250:]}")

    # ── 3. 상대 경로 = YAML 폴더 기준 ─────────────────────────────────────────
    print("[상대 경로: 폴더가 붙은 상대 경로도 YAML 폴더 기준]")
    LOAD = "loads:\n  - part: 1\n    mode: normal_pressure\n    value: 1.0\n"
    BND = ("boundaries:\n  - part: 1\n    dof: all\n    direction: [0, 0, -1]\n"
           "    select: direction\n    angle: 45.0\n")
    RBE = "rbe:\n  - part: 1\n    type: rbe2\n    select: all\n"
    CT = ("contacts:\n  - action: create\n    type: automatic_single_surface\n"
          "    slave: { pid: 1 }\n")
    CASES = [
        ("load", "rel_load.k", LOAD),
        ("boundary", "rel_bnd.k", BND),
        ("rbe", "rel_rbe.k", RBE),
        ("contact", "rel_ct.k", CT),
        ("relax", "rel_relax.k", "level: 2\n"),
        ("explicit", "rel_exp.k", ""),
        ("implicit", "rel_imp.k", "mode: static\nlevel: 2\n"),
        ("modal", "rel_modal.k", "nmode: 5\n"),
        ("database", "rel_db.k", "dt: 1.0e-4\n"),
        ("ale", "rel_ale.k", "ale_parts:\n  - pid: 1\n    material: air\n"),
    ]
    for cmd, outname, extra in CASES:
        name = f"rel_{cmd}.yaml"
        write(os.path.join(cfg, name),
              f"model: ../data/box.k\noutput: ../data/{outname}\n" + extra)
        rc, out = run(binary, tmp, cmd, "cfg/" + name)
        check(f"경로: {cmd} 의 '../data/box.k' 가 YAML 폴더(cfg) 기준으로 풀린다",
              rc == 0 and os.path.exists(os.path.join(data, outname)), f"rc={rc} {out[-250:]}")

    # matdb 는 database 도 필요하다 (database 키 자체의 규칙은 예외로 남아 있다 — 감사 노트 참고)
    import shutil
    shutil.copy2(os.path.join(REPO, "materials", "material_db.json"), cfg)
    write(os.path.join(cfg, "rel_matdb.yaml"),
          "model: ../data/box.k\noutput: ../data/rel_matdb.k\ndatabase: material_db.json\n"
          "mat_type: MAT_ELASTIC\nmaterials:\n  - match: \"*\"\n")
    rc, out = run(binary, tmp, "matdb", "cfg/rel_matdb.yaml")
    check("경로: matdb 의 model/output 도 YAML 폴더 기준",
          rc == 0 and os.path.exists(os.path.join(data, "rel_matdb.k")), f"rc={rc} {out[-250:]}")

    # generate box 의 output 도 같은 규칙
    write(os.path.join(cfg, "rel_gen.yaml"), BOX.replace("output: box", "output: ../data/rel_gen"))
    rc, out = run(binary, tmp, "generate", "box", "cfg/rel_gen.yaml")
    check("경로: generate box 의 output 도 YAML 폴더 기준",
          rc == 0 and os.path.exists(os.path.join(data, "rel_gen.k")) and
          not os.path.exists(os.path.join(tmp, "rel_gen.k")), f"rc={rc} {out[-250:]}")

    # 절대 경로는 그대로
    write(os.path.join(cfg, "abs.yaml"),
          "model: %s\noutput: %s\n" % (os.path.join(data, "box.k"), os.path.join(data, "abs_out.k")) + LOAD)
    rc, out = run(binary, tmp, "load", "cfg/abs.yaml")
    check("경로: 절대 경로는 configDir 를 붙이지 않는다",
          rc == 0 and os.path.exists(os.path.join(data, "abs_out.k")), f"rc={rc} {out[-250:]}")

    # ── 4. contact pids 블록 목록 / type 허용값 ───────────────────────────────
    print("[contact: pids 블록 목록 · create type 허용값]")
    ct_inline = ("model: box.k\noutput: ct_inline.k\ncontacts:\n  - action: create\n"
                 "    type: automatic_surface_to_surface\n    slave:\n      pids: [1]\n"
                 "    master:\n      pids: [1]\n")
    ct_block = ("model: box.k\noutput: ct_block.k\ncontacts:\n  - action: create\n"
                "    type: automatic_surface_to_surface\n    slave:\n      pids:\n        - 1\n"
                "    master:\n      pids:\n        - 1\n")
    write(os.path.join(data, "ct_inline.yaml"), ct_inline)
    write(os.path.join(data, "ct_block.yaml"), ct_block)
    rc1, o1 = run(binary, data, "contact", "ct_inline.yaml")
    rc2, o2 = run(binary, data, "contact", "ct_block.yaml")
    check("contact: 'pids:' 블록 목록도 SET_PART 를 만든다 (인라인과 같은 수)",
          rc1 == 0 and rc2 == 0 and o1.count("Created SET_PART") == 2 and
          o2.count("Created SET_PART") == 2, f"rc={rc1},{rc2} {o2[-250:]}")
    b1 = os.path.join(data, "ct_inline.k")
    b2 = os.path.join(data, "ct_block.k")
    same = (os.path.exists(b1) and os.path.exists(b2) and
            [l for l in open(b1).read().splitlines() if not l.startswith("$")] ==
            [l for l in open(b2).read().splitlines() if not l.startswith("$")])
    check("contact: 블록 목록 산출 덱이 인라인 산출 덱과 같다", same)

    write(os.path.join(data, "ct_bad.yaml"),
          "model: box.k\noutput: ct_bad.k\ncontacts:\n  - action: create\n    type: bogus\n"
          "    slave: { pid: 1 }\n    master: { pid: 1 }\n")
    rc, out = run(binary, data, "contact", "ct_bad.yaml")
    check("contact: create 의 모르는 type 은 rc=1 + 허용값 목록 (예전엔 *CONTACT_BOGUS)",
          rc == 1 and "unsupported type 'bogus'" in out and
          "automatic_surface_to_surface" in out and "*CONTACT_BOGUS" not in out, f"rc={rc} {out[-300:]}")
    check("contact: 거절했으면 산출 덱을 쓰지 않는다", not os.path.exists(os.path.join(data, "ct_bad.k")))

    # 짧은 이름은 assemble 과 같은 전체 키워드로 풀린다 (예전엔 단독 contact 만 *CONTACT_AUTO 였다)
    for short, kw in (("auto", "AUTOMATIC_SURFACE_TO_SURFACE"),
                      ("tied", "TIED_SURFACE_TO_SURFACE"),
                      ("single", "AUTOMATIC_SINGLE_SURFACE"),
                      ("mortar", "AUTOMATIC_SURFACE_TO_SURFACE_MORTAR")):
        write(os.path.join(data, f"ct_s_{short}.yaml"),
              f"model: box.k\noutput: ct_s_{short}.k\ncontacts:\n  - action: create\n    type: {short}\n"
              "    slave: { pid: 1 }\n    master: { pid: 1 }\n")
        rc, out = run(binary, data, "contact", f"ct_s_{short}.yaml")
        check(f"contact: 짧은 이름 '{short}' 가 *CONTACT_{kw} 로 풀린다",
              rc == 0 and ("Created *CONTACT_" + kw) in out, f"rc={rc} {out[-250:]}")

    # 단독 contact 와 assemble 이 같은 type 에 같은 키워드를 쓴다
    write(os.path.join(data, "ct_asm.yaml"),
          "base_model: box.k\noutput: ct_asm\noperations:\n  - type: contact\n    contacts:\n"
          "      - action: create\n        type: auto\n        slave:\n          pid: 1\n")
    rc, out = run(binary, data, "assemble", "ct_asm.yaml")
    asm_kw = [l for l in open(os.path.join(data, "ct_asm.k")).read().splitlines()
              if l.startswith("*CONTACT_")] if os.path.exists(os.path.join(data, "ct_asm.k")) else []
    std_kw = [l for l in open(os.path.join(data, "ct_s_auto.k")).read().splitlines()
              if l.startswith("*CONTACT_")] if os.path.exists(os.path.join(data, "ct_s_auto.k")) else []
    check("contact: 'type: auto' 가 assemble 과 단독 contact 에서 같은 키워드를 만든다",
          rc == 0 and asm_kw and std_kw and
          asm_kw[0].replace("_TITLE", "") == std_kw[0].replace("_TITLE", ""),
          f"rc={rc} asm={asm_kw[:1]} std={std_kw[:1]}")

    for alias, kw in (("tied_thermal", "TIED_SURFACE_TO_SURFACE_THERMAL"),
                      ("thermal", "TIED_SURFACE_TO_SURFACE_THERMAL"),
                      ("tiebreak", "AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK")):
        write(os.path.join(data, f"ct_{alias}.yaml"),
              f"model: box.k\noutput: ct_{alias}.k\ncontacts:\n  - action: create\n    type: {alias}\n"
              "    slave: { pid: 1 }\n    master: { pid: 1 }\n")
        rc, out = run(binary, data, "contact", f"ct_{alias}.yaml")
        check(f"contact: 별칭 '{alias}' 는 그대로 통과해 *CONTACT_{kw} 를 만든다",
              rc == 0 and ("Created *CONTACT_" + kw) in out, f"rc={rc} {out[-250:]}")

    write(os.path.join(data, "ct_full.yaml"),
          "model: box.k\noutput: ct_full.k\ncontacts:\n  - action: create\n"
          "    type: automatic_single_surface\n    slave: { pid: 1 }\n")
    rc, out = run(binary, data, "contact", "ct_full.yaml")
    check("contact: 전체 키워드(automatic_single_surface)는 그대로 통과",
          rc == 0 and "Created *CONTACT_AUTOMATIC_SINGLE_SURFACE" in out, f"rc={rc} {out[-250:]}")

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
