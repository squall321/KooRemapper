# merge·contact·load/boundary/rbe·squeeze·meshfix·stabilize 의 종료 코드·enum 검증·블록 리스트·키워드 보존 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_ops_behavior_guards.py <KooRemapper 바이너리>

배경
  - merge 는 없는 모델을 가리키면 '[ERROR] Cannot open model' 을 찍고도 rc=0 으로 '*END' 다섯 바이트짜리
    출력을 남겼다(플랫폼 Job 이 성공으로 기록됐다). 그룹에 요소가 없을 때도 rc=0 이었다.
  - contact 의 include:/exclude: 를 블록 리스트('- Left')로 쓰면 콜론이 없어 줄이 버려지고 빈 표면으로
    [WARN] 만 찍혔다(인라인 '[Left, Center]' 와 결과가 달랐다).
  - load 의 mode: gravity 는 *LOAD_BODY 를 만드는 코드가 없어 압력 하중과 똑같은 덱을 냈고,
    select: all 은 select: direction 과 같았다(둘 다 구현된 적이 없는 값).
  - 탭으로 들여쓴 boundary/load/rbe YAML 은 공백만 세는 countIndent 탓에 블록 구조가 무너져
    '[boundary] Done' rc=0 인데 출력이 입력과 똑같았다.
  - 단독 squeeze 출력 .k 에 *KEYWORD/*PART/*SECTION/*MAT 이 없어 해석에 바로 넣을 수 없었고,
    swelling 의 *MAT_ADD_THERMAL_EXPANSION 이 없는 MID 를 가리켰다.
  - 쓰레기 enum 값을 조용히 삼켰다: merge method/direction → VRH/Z, contact contact_type → *CONTACT_BOGUS_TITLE,
    meshfix algorithm → hxt, stabilize level -1 은 no-op, 13/99 는 12 로 클램프
    (level: 0 은 문서에 적힌 수동 모드라 계속 받는다).
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SCRATCH = os.path.join(REPO, "build", "scratch")

BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\n"
       "mid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")


def check(name, cond, detail=""):
    print("  %-72s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def mkd(prefix):
    os.makedirs(SCRATCH, exist_ok=True)
    return tempfile.mkdtemp(prefix=prefix, dir=SCRATCH)


def write(d, name, text):
    open(os.path.join(d, name), "w").write(text)


def keywords(path):
    """파일에 든 '*KEYWORD' 류 카드 이름 목록 (없으면 None)."""
    try:
        return [l.split()[0].upper() for l in open(path, errors="replace").read().splitlines()
                if l.startswith("*")]
    except OSError:
        return None


def body(path):
    try:
        return [l for l in open(path, errors="replace").read().splitlines() if not l.startswith("$")]
    except OSError:
        return None


def test_merge(binary):
    print("[merge — 실패하면 rc=1, 쓰레기 출력 없음]")
    d = mkd("mg_guard_")
    shutil.copy(os.path.join(REPO, "examples", "merge", "three_layer.k"), d)

    write(d, "ok.yaml", "model: three_layer.k\noutput: ok_out.k\ndirection: z\nmethod: vrh\n"
                        "merge:\n  - pids: [1, 2, 3]\n    name: H\n")
    rc, out = run(binary, d, "merge", "ok.yaml")
    check("정상 설정은 그대로 rc=0 + 출력 생성", rc == 0 and os.path.exists(os.path.join(d, "ok_out.k")),
          f"rc={rc} {out[-200:]}")

    write(d, "nomodel.yaml", "model: nonexistent_model.k\noutput: bad_out.k\ndirection: z\n"
                             "merge:\n  - pids: [1, 2]\n    name: G1\n")
    rc, out = run(binary, d, "merge", "nomodel.yaml")
    check("없는 모델: rc=1 (예전엔 rc=0)", rc == 1, f"rc={rc} {out[-200:]}")
    check("없는 모델: 출력 파일을 남기지 않음 (예전엔 '*END' 5바이트)",
          not os.path.exists(os.path.join(d, "bad_out.k")))

    write(d, "nopid.yaml", "model: three_layer.k\noutput: nopid_out.k\ndirection: z\n"
                           "merge:\n  - pids: [777]\n    name: G1\n")
    rc, out = run(binary, d, "merge", "nopid.yaml")
    check("없는 PID 그룹: rc=1 + 출력 없음", rc == 1 and not os.path.exists(os.path.join(d, "nopid_out.k")),
          f"rc={rc} {out[-200:]}")

    for key, bad, allowed in (("method", "bogus", "voigt, reuss, vrh"), ("direction", "bogus", "x, y, z")):
        write(d, f"e_{key}.yaml", f"model: three_layer.k\noutput: e_{key}_out.k\n{key}: {bad}\n"
                                  "merge:\n  - pids: [1, 2, 3]\n    name: H\n")
        rc, out = run(binary, d, "merge", f"e_{key}.yaml")
        check(f"{key}: '{bad}' 를 조용히 삼키지 않고 rc=1 + 허용값 출력",
              rc == 1 and allowed in out and not os.path.exists(os.path.join(d, f"e_{key}_out.k")),
              f"rc={rc} {out[-200:]}")


def test_contact(binary):
    print("[contact — include/exclude 블록 리스트, contact_type 검증]")
    d = mkd("ct_guard_")
    shutil.copy(os.path.join(REPO, "examples", "contact", "model.k"), d)

    head = "model: model.k\noutput: @OUT@\n\ncontacts:\n  - action: detect\n"
    tail = "    tolerance: 0.1\n    auto_create: true\n    contact_type: auto\n"
    write(d, "inline.yaml", head.replace("@OUT@", "inline.k") + "    include: [Left, Center]\n" + tail)
    write(d, "block.yaml", head.replace("@OUT@", "block.k") + "    include:\n      - Left\n      - Center\n" + tail)
    rc0, out0 = run(binary, d, "contact", "inline.yaml")
    rc1, out1 = run(binary, d, "contact", "block.yaml")
    b0, b1 = body(os.path.join(d, "inline.k")), body(os.path.join(d, "block.k"))
    check("include: 블록 리스트 → 인라인 [a, b] 와 같은 출력 (rc=0)",
          rc0 == 0 and rc1 == 0 and b0 is not None and b0 == b1, f"rc={rc0}/{rc1} {out1[-200:]}")
    check("include: 블록 리스트 → 'empty surface(s)' 경고 없음", "empty surface" not in out1, out1[-200:])
    check("include: 블록 리스트 → *SET_SEGMENT 생성", b1 is not None and
          any(l.upper().startswith("*SET_SEGMENT") for l in b1))

    write(d, "xinline.yaml", head.replace("@OUT@", "xinline.k") + "    exclude: [Right]\n" + tail)
    write(d, "xblock.yaml", head.replace("@OUT@", "xblock.k") + "    exclude:\n      - Right\n" + tail)
    rc0, _ = run(binary, d, "contact", "xinline.yaml")
    rc1, out1 = run(binary, d, "contact", "xblock.yaml")
    b0, b1 = body(os.path.join(d, "xinline.k")), body(os.path.join(d, "xblock.k"))
    check("exclude: 블록 리스트 → 인라인 [a] 와 같은 출력 (rc=0)",
          rc0 == 0 and rc1 == 0 and b0 is not None and b0 == b1, f"rc={rc0}/{rc1} {out1[-200:]}")

    # 블록 리스트 뒤에 오는 다음 액션 항목('- action:')을 삼키지 않는다
    write(d, "multi.yaml", "model: model.k\noutput: multi.k\n\ncontacts:\n"
                           "  - action: detect\n    include:\n      - Left\n    tolerance: 0.1\n"
                           "    auto_create: true\n    contact_type: tied\n    title_prefix: T1\n"
                           "  - action: detect\n    include: [Center]\n    tolerance: 0.1\n"
                           "    auto_create: true\n    contact_type: auto\n    title_prefix: T2\n")
    rc, out = run(binary, d, "contact", "multi.yaml")
    txt = open(os.path.join(d, "multi.k"), errors="replace").read() if rc == 0 else ""
    check("블록 리스트 다음의 '- action:' 을 리스트 항목으로 삼키지 않음 (T1·T2 둘 다)",
          rc == 0 and "T1_" in txt and "T2_" in txt, f"rc={rc} {out[-200:]}")

    write(d, "bogus.yaml", head.replace("@OUT@", "bogus.k") + "    include: [Left]\n"
          + tail.replace("contact_type: auto", "contact_type: bogus"))
    rc, out = run(binary, d, "contact", "bogus.yaml")
    check("contact_type: 'bogus' → rc=1 + 허용값 출력 (예전엔 *CONTACT_BOGUS_TITLE)",
          rc == 1 and "allowed:" in out and not os.path.exists(os.path.join(d, "bogus.k")),
          f"rc={rc} {out[-200:]}")


def test_load_select_mode(binary):
    print("[load — 구현된 mode/select 만 받음]")
    d = mkd("ld_guard_")
    write(d, "box.yaml", BOX)
    run(binary, d, "generate", "box", "box.yaml")

    def cfg(name, mode, select):
        write(d, name + ".yaml", f"model: box.k\noutput: {name}.k\nloads:\n  - part: 1\n    mode: {mode}\n"
                                 f"    value: 1.0\n    direction: [0, 0, 1]\n    select: {select}\n")
        return run(binary, d, "load", name + ".yaml")

    for mode in ("pressure", "force", "normal_pressure"):
        rc, out = cfg("m_" + mode, mode, "direction")
        check(f"mode: {mode} 는 그대로 동작 (rc=0)", rc == 0, f"rc={rc} {out[-200:]}")
    for select in ("direction", "tied"):
        rc, out = cfg("s_" + select, "pressure", select)
        check(f"select: {select} 는 그대로 동작 (rc=0)", rc == 0, f"rc={rc} {out[-200:]}")

    rc, out = cfg("m_gravity", "gravity", "direction")
    check("mode: gravity → rc=1 + 허용값 출력 (예전엔 조용히 압력 하중)",
          rc == 1 and "pressure, force, normal_pressure" in out and
          not os.path.exists(os.path.join(d, "m_gravity.k")), f"rc={rc} {out[-200:]}")
    rc, out = cfg("s_all", "pressure", "all")
    check("select: all → rc=1 + 허용값 출력 (예전엔 direction 과 동일)",
          rc == 1 and "direction, set, tied" in out and
          not os.path.exists(os.path.join(d, "s_all.k")), f"rc={rc} {out[-200:]}")


def test_tab_indent(binary):
    print("[load/boundary/rbe — 탭 들여쓰기는 rc=1]")
    d = mkd("tab_guard_")
    write(d, "box.yaml", BOX)
    run(binary, d, "generate", "box", "box.yaml")

    cases = {
        "boundary": ("boundaries", "- part: 1\n@dof: all\n@direction: [0, 0, -1]\n@select: direction\n@angle: 45.0\n"),
        "load":     ("loads", "- part: 1\n@mode: pressure\n@value: 1.0\n@direction: [0, 0, 1]\n@select: direction\n"),
        "rbe":      ("rbe", "- part: 1\n@type: rbe2\n@mode: spider\n@direction: [0, 0, 1]\n@select: direction\n"),
    }
    for cmd, (listKey, itemTmpl) in cases.items():
        sp = "".join("  " + l + "\n" for l in itemTmpl.replace("@", "  ").split("\n") if l)
        tb = "".join("\t" + l + "\n" for l in itemTmpl.replace("@", "  ").split("\n") if l)
        write(d, cmd + "_sp.yaml", f"model: box.k\noutput: {cmd}_sp.k\n{listKey}:\n" + sp)
        write(d, cmd + "_tab.yaml", f"model: box.k\noutput: {cmd}_tab.k\n{listKey}:\n" + tb)
        rc0, out0 = run(binary, d, cmd, cmd + "_sp.yaml")
        check(f"{cmd}: 공백 들여쓰기는 그대로 rc=0", rc0 == 0, f"rc={rc0} {out0[-200:]}")
        rc1, out1 = run(binary, d, cmd, cmd + "_tab.yaml")
        check(f"{cmd}: 탭 들여쓰기 → rc=1 + '탭' 알림 (예전엔 rc=0 'Done' 인데 입력 그대로)",
              rc1 == 1 and "탭" in out1 and not os.path.exists(os.path.join(d, cmd + "_tab.k")),
              f"rc={rc1} {out1[-200:]}")


def test_squeeze_keywords(binary):
    print("[squeeze — 출력 .k 가 전체 모델]")
    d = mkd("sq_guard_")
    write(d, "box.yaml", BOX)
    run(binary, d, "generate", "box", "box.yaml")

    write(d, "sq.yaml", "parts:\n  - pid: 1\n    eps_z: -0.01\nmaterial:\n  E: 210000.0\n  nu: 0.3\n")
    rc, out = run(binary, d, "squeeze", "box.k", "sq.yaml", "sqout")
    kws = keywords(os.path.join(d, "sqout.k")) or []
    need = ["*KEYWORD", "*PART", "*SECTION_SOLID", "*MAT_ELASTIC", "*NODE", "*ELEMENT_SOLID", "*END"]
    check("stress 모드: *KEYWORD/*PART/*SECTION/*MAT 보존", rc == 0 and all(k in kws for k in need),
          f"rc={rc} kws={kws} {out[-200:]}")
    check("stress 모드: dynain *INCLUDE 유지", "*INCLUDE" in kws, f"kws={kws}")

    write(d, "sw.yaml", "parts:\n  - pid: 1\n    swelling: 0.05\n")
    rc, out = run(binary, d, "squeeze", "box.k", "sw.yaml", "swout")
    txt = open(os.path.join(d, "swout.k"), errors="replace").read() if rc == 0 else ""
    kws = keywords(os.path.join(d, "swout.k")) or []
    mids = set()
    lines = txt.splitlines()
    for i, l in enumerate(lines):
        if l.upper().startswith("*MAT_ELASTIC"):
            for nxt in lines[i + 1:]:
                if nxt.startswith("*"):
                    break
                if nxt.startswith("$") or not nxt.strip():
                    continue
                mids.add(nxt.split()[0])
                break
    swMid = ""
    for i, l in enumerate(lines):
        if l.upper().startswith("*MAT_ADD_THERMAL_EXPANSION"):
            for nxt in lines[i + 1:]:
                if nxt.startswith("$") or not nxt.strip():
                    continue
                swMid = nxt.split()[0]
                break
    check("swelling 모드: *MAT_ADD_THERMAL_EXPANSION 이 실재하는 MID 를 가리킴",
          rc == 0 and "*MAT_ADD_THERMAL_EXPANSION" in kws and swMid and swMid in mids,
          f"rc={rc} swMid={swMid} mids={mids} {out[-200:]}")


def test_meshfix_stabilize(binary):
    print("[meshfix algorithm · stabilize level — 허용값 밖은 rc=1]")
    d = mkd("en_guard_")
    write(d, "box.yaml", BOX)
    run(binary, d, "generate", "box", "box.yaml")

    write(d, "mf_bad.yaml", "model: box.k\noutput: mf_bad.k\npid: 1\nalgorithm: bogus\n")
    rc, out = run(binary, d, "meshfix", "mf_bad.yaml")
    check("meshfix algorithm: 'bogus' → rc=1 + 허용값 출력 (예전엔 hxt 로 실행)",
          rc == 1 and "hxt, frontal3d, del3d" in out, f"rc={rc} {out[-200:]}")

    for lv in ("-1", "13", "99", "abc"):
        write(d, f"st_{lv}.yaml", f"model: box.k\noutput: st_{lv}.k\nstabilize: explicit\nlevel: {lv}\n")
        rc, out = run(binary, d, "stabilize", f"st_{lv}.yaml")
        check(f"stabilize level: {lv} → rc=1 + 0~12 안내", rc == 1 and "0~12" in out
              and not os.path.exists(os.path.join(d, f"st_{lv}.k")), f"rc={rc} {out[-200:]}")

    write(d, "st_6.yaml", "model: box.k\noutput: st_6.k\nstabilize: explicit\nlevel: 6\n")
    rc, out = run(binary, d, "stabilize", "st_6.yaml")
    check("stabilize level: 6 은 그대로 rc=0", rc == 0 and os.path.exists(os.path.join(d, "st_6.k")),
          f"rc={rc} {out[-200:]}")

    write(d, "st_man.yaml", "model: box.k\noutput: st_man.k\nstabilize: explicit\ntssfac: 0.80\n")
    rc, out = run(binary, d, "stabilize", "st_man.yaml")
    check("stabilize: level 을 안 적은 수동 설정은 그대로 rc=0", rc == 0
          and os.path.exists(os.path.join(d, "st_man.k")), f"rc={rc} {out[-200:]}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    test_merge(binary)
    test_contact(binary)
    test_load_select_mode(binary)
    test_tab_indent(binary)
    test_squeeze_keywords(binary)
    test_meshfix_stabilize(binary)

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
