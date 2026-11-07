#!/usr/bin/env python3
# 덱 · 보고를 쓰는 모든 op 이 쓸 파일을 읽는 파일(설정 YAML · 모델 · 인클루드 닫힘 · 다른 입력)과 같게 주면 아무것도 쓰지 않고 거절하는지 보는 회귀 시험
"""쓸 파일이 읽는 파일을 덮는가 — 모든 op (2026-11-07 · 쓰기 관문 `output_guard`).

왜 이 시험이 있나.

  흘려 읽는 op 셋(extract-parts · cleanup-nodes · strip)만 막혀 있었다(`test_output_clobbers_input.py`). 나머지는 쓸 파일을 읽는
  파일과 견주지 않았다 — 실측:
    · `update` 의 output 이 모델의 인클루드면 rc 0 으로 그 인클루드가 주 덱으로 바뀌어 자기 자신을 끌어오고 `*NODE` 가 사라졌다
    · meshfix 는 output == model 이면 쓰기 뒤 재검사가 실패할 때 「산출을 지웠다」며 모델을 지웠다
    · prestress 는 변형 메시를 다시 읽기 전에 dynain 을 써 `prestress ref def.key def.key` 가 그 입력을 덮었다
    · map 의 prestress 고리는 prestress.output 이 flat 이면 메시 사본이 기준 메시를 덮었다
    · rebind 는 output 과 entities 를 문자열로만 견줬다(`./x` · 링크 · 두 덱 · range_diff 는 못 봤다)
  이제 op 마다 산출을 열기 전에 쓸 파일 전부를 읽는 파일과 견줘(정규 경로 · 심볼릭 링크 · 하드 링크) 같으면 거절한다.

무엇을 보나(op 마다 — 도움말 사례를 판으로 쓴다).
  거절(rc 1 · 「같은 파일」 · 폴더의 파일이 바이트 하나 안 바뀐다 · 새 파일도 없다):
    output == model · 모델의 인클루드 · 설정 YAML · 다른 입력(dynain · bundle · dat · entities …) · 모델의 하드 링크 · 심볼릭 링크 ·
    `../<폴더>/모델` 철자
  거절하지 않음(rc 0 · 모델 그대로): 대조(도움말 그대로) · 다른 폴더의 같은 이름 · 상관없는 기존 파일(덮어쓴다)
  문서에 적힌 in-place — assemble 의 output == base_model 은 rc 0(인클루드 · 설정 · 다른 입력은 거절)
  위치 인자 op(map · shellmap · unfold · extract-surface · strain · prestress · squeeze · generate · generate-var · matswap 옛 꼴)과
  빈 output(boundary · rbe) · 곁 파일(warpage 진단 · cad_solid_merge 대응표 · stackwrap `_neutral.k`)은 따로 본다.

usage: test_output_guard_ops.py <KooRemapper 바이너리>
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "help"))
from ops_help import OPS  # noqa: E402

SPEC = {o["name"]: o for o in OPS}
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-500:]))
    print("  %-96s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, args, timeout=900):
    p = subprocess.run([binary] + list(args), cwd=cwd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def snapshot(d):
    """폴더 안 모든 파일 → 내용 sha(링크는 가리키는 곳까지) — 거절이 아무것도 쓰지 않았는지 본다."""
    out = {}
    for dp, _dirs, files in os.walk(d):
        for fn in files:
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, d)
            out[rel] = ("link:" + os.readlink(p)) if os.path.islink(p) else sha(p)
    return out


def diff(a, b):
    keys = sorted(set(a) | set(b))
    return [k for k in keys if a.get(k) != b.get(k)]


# ── 산출 이름 규칙 — op 이 output 값에서 실제로 쓰는 파일 ────────────────────────────
#   asis      : 값 그대로                                    (relax · contact · merge …)
#   prefix_k  : 끝의 `.k` 를 떼고 `.k` 를 붙인다 — 값이 X.k 면 X.k (ModelAssembler 계열 · cclip · squeeze …)
#   ("sfx", s): 값 + s                                       (section `_section.json` · linkage-fit `.yaml` …)
#   json      : `.json` 으로 끝나지 않으면 붙인다            (id_floor)
def fits(rule, t):
    if rule == "asis":
        return True
    if rule == "prefix_k":
        return t.endswith(".k")
    if rule == "json":
        return t.endswith(".json")
    return t.endswith(rule[1])


def out_for(rule, t):
    if isinstance(rule, tuple):
        return t[:-len(rule[1])]
    return t


def fitted(rule, stem):
    """규칙이 그대로 쓸 수 있는 이름 — stem 뒤에 붙인다."""
    if rule in ("asis", "prefix_k"):
        return stem + ".k"
    if rule == "json":
        return stem + ".json"
    return stem + rule[1]


def yget(text, key):
    m = re.search(r"^[ \t]*(?:-[ \t]+)?" + re.escape(key) + r":[ \t]*(\S.*?)[ \t]*$", text, re.M)
    return m.group(1).strip().strip('"\'') if m else None


def yset(text, key, val):
    pat = re.compile(r"^([ \t]*(?:-[ \t]+)?)" + re.escape(key) + r":[ \t]*\S.*$", re.M)
    if pat.search(text):
        return pat.sub(lambda m: m.group(1) + key + ": " + val, text, count=1)
    return key + ": " + val + "\n" + text


def add_include(model_path, inc_name):
    """주 덱의 첫 `*KEYWORD` 바로 뒤(없으면 맨 앞)에 맨 `*INCLUDE` 카드를 넣는다 — 인클루드 파일은 빈 덱."""
    lines = read(model_path).splitlines()
    at = next((i + 1 for i, l in enumerate(lines) if l.strip().upper().startswith("*KEYWORD")), 0)
    lines[at:at] = ["*INCLUDE", inc_name]
    write(model_path, "\n".join(lines) + "\n")
    write(os.path.join(os.path.dirname(model_path), inc_name), "*KEYWORD\n$ 쓰기 관문 시험용 빈 인클루드\n*END\n")


class Stager:
    """op 마다 도움말 사례의 준비 명령(마지막 명령 앞까지)을 한 번 돌린 판을 만들고, 변형마다 그 판을 복사해 쓴다."""

    def __init__(self, binary, root):
        self.binary, self.root, self.templates, self.n = binary, root, {}, 0

    def template(self, op):
        if op in self.templates:
            return self.templates[op]
        spec = SPEC[op]
        t = os.path.join(self.root, "_tpl_" + op)
        os.makedirs(t)
        for need in spec["needs"]:
            src_dir = os.path.dirname(os.path.join(REPO, need))
            shutil.copytree(src_dir, os.path.join(t, os.path.dirname(need)), dirs_exist_ok=True)
        for name, content in spec["files"].items():
            write(os.path.join(t, name), content)
        for c in spec["cmds"][:-1]:
            argv = c.split()
            rc, text = run(self.binary, t, argv[1:])
            if rc != 0:
                raise RuntimeError("준비 명령 실패 %s: %s" % (c, text[-400:]))
        self.templates[op] = (t, spec["cmds"][-1].split()[1:])
        return self.templates[op]

    def case(self, op, tag):
        t, last = self.template(op)
        self.n += 1
        d = os.path.join(self.root, "%s_%d_%s" % (op, self.n, re.sub(r"[^A-Za-z0-9]+", "_", tag)[:20]))
        shutil.copytree(t, d, symlinks=True)
        return d, list(last)


def expect_refused(name, binary, d, argv, timeout=900):
    before = snapshot(d)
    rc, text = run(binary, d, argv, timeout)
    changed = diff(before, snapshot(d))
    return check("★" + name + " → rc 1 · 「같은 파일」 · 폴더 바이트 그대로",
                 rc == 1 and "같은 파일" in text and not changed, (rc, changed[:5], text[-500:]))


def expect_ok(name, binary, d, argv, keep, made=None, timeout=900):
    """rc 0 · keep(입력)은 바이트 그대로 · made(산출)가 생겼다."""
    keep_sha = {k: sha(os.path.join(d, k)) for k in keep if os.path.exists(os.path.join(d, k))}
    rc, text = run(binary, d, argv, timeout)
    same = all(sha(os.path.join(d, k)) == v for k, v in keep_sha.items())
    exists = made is None or os.path.exists(os.path.join(d, made))
    return check(name + " → rc 0 · 입력 그대로", rc == 0 and same and exists and "같은 파일" not in text,
                 (rc, same, exists, text[-500:]))


# ── YAML op — 도움말 사례의 설정에서 output 만 바꿔 돈다 ─────────────────────────────
def yaml_op(st, binary, op, rule, model_key="model", extras=(), inplace=False, config=True, include=True,
            gmsh_needed=False):
    print("[%s]" % op)
    gmsh_ok = (not gmsh_needed) or bool(os.environ.get("KOOREMAPPER_GMSH")) and os.path.isfile(os.environ["KOOREMAPPER_GMSH"])

    def prep(tag):
        d, argv = st.case(op, tag)
        cfg_name = argv[1]
        return d, argv, cfg_name, read(os.path.join(d, cfg_name))

    def fit_input(d, cfg, key, val):
        """val(설정 폴더 기준)이 규칙에 안 맞으면 맞는 이름으로 복사하고 설정을 고친다 → (설정, 맞춘 이름)."""
        if fits(rule, val):
            return cfg, val
        new = os.path.join(os.path.dirname(val), fitted(rule, os.path.basename(val).replace(".", "_") + "__g"))
        shutil.copyfile(os.path.join(d, val), os.path.join(d, new))
        return yset(cfg, key, new), new

    def go(name, d, argv, cfg_name, cfg, refuse):
        write(os.path.join(d, cfg_name), cfg)
        argv = [argv[0], cfg_name]
        if refuse:
            expect_refused("%s %s" % (op, name), binary, d, argv)
        else:
            rc, text = run(binary, d, argv)
            check("%s %s (in-place — 문서의 쓰임) → rc 0" % (op, name), rc == 0 and "같은 파일" not in text, (rc, text[-400:]))

    # 대조 — 도움말 그대로
    d, argv, cfg_name, cfg = prep("control")
    model = yget(cfg, model_key)
    if gmsh_ok:
        expect_ok("%s 대조(도움말 그대로)" % op, binary, d, [argv[0], cfg_name], [model])
    # output == model
    d, argv, cfg_name, cfg = prep("model")
    cfg, m = fit_input(d, cfg, model_key, yget(cfg, model_key))
    go("output == %s(모델)" % model_key, d, argv, cfg_name, yset(cfg, "output", out_for(rule, m)), not inplace)
    # 모델의 인클루드
    if include:
        d, argv, cfg_name, cfg = prep("include")
        m = yget(cfg, model_key)
        inc = fitted(rule, "guard_inc")
        add_include(os.path.join(d, m), inc)
        go("output == 모델의 인클루드", d, argv, cfg_name,
           yset(cfg, "output", out_for(rule, os.path.join(os.path.dirname(m), inc))), True)
    # 설정 YAML
    if config:
        d, argv, cfg_name, cfg = prep("config")
        new_cfg = cfg_name if rule == "asis" else fitted(rule, "guard_cfg")
        go("output == 설정 YAML", d, argv, new_cfg, yset(cfg, "output", out_for(rule, new_cfg)), True)
    # 다른 입력
    for key in extras:
        d, argv, cfg_name, cfg = prep("in_" + key)
        cfg, t = fit_input(d, cfg, key, yget(cfg, key))
        go("output == %s(다른 입력)" % key, d, argv, cfg_name, yset(cfg, "output", out_for(rule, t)), True)
    # 하드 링크 · 심볼릭 링크 · ../ 철자
    for kind in ("hard", "sym", "dotdot"):
        d, argv, cfg_name, cfg = prep(kind)
        m = yget(cfg, model_key)
        if kind == "dotdot":
            cfg, m = fit_input(d, cfg, model_key, m)
            tgt = "../%s/%s" % (os.path.basename(d), m)
        else:
            tgt = fitted(rule, "guard_" + kind)
            if kind == "hard":
                os.link(os.path.join(d, m), os.path.join(d, tgt))
            else:
                os.symlink(os.path.abspath(os.path.join(d, m)), os.path.join(d, tgt))
        what = {"hard": "모델의 하드 링크", "sym": "모델을 가리키는 심볼릭 링크", "dotdot": "../<폴더>/모델 철자"}[kind]
        go("output == " + what, d, argv, cfg_name, yset(cfg, "output", out_for(rule, tgt)), not inplace)
    if not gmsh_ok:
        print("  (gmsh 없음 — %s 의 거절하지 않는 변형은 건너뛴다)" % op)
        return
    # 거절하지 않는 것 — 다른 폴더의 같은 이름 · 상관없는 기존 파일
    d, argv, cfg_name, cfg = prep("subdir")
    m = yget(cfg, model_key)
    os.makedirs(os.path.join(d, "sub"), exist_ok=True)
    sub_out = "sub/" + os.path.basename(m)
    write(os.path.join(d, cfg_name), yset(cfg, "output", sub_out))
    expect_ok("%s output 이 다른 폴더의 같은 이름(%s)" % (op, sub_out), binary, d, [argv[0], cfg_name], [m])
    d, argv, cfg_name, cfg = prep("unrelated")
    m = yget(cfg, model_key)
    old = fitted(rule, "guard_old")
    write(os.path.join(d, old), "junk — 지난 실행의 산출\n")
    before = sha(os.path.join(d, old))
    write(os.path.join(d, cfg_name), yset(cfg, "output", out_for(rule, old)))
    ok = expect_ok("%s output 이 상관없는 기존 파일(%s)" % (op, old), binary, d, [argv[0], cfg_name], [m])
    if ok:
        check("%s   └ 그 파일은 덮어쓴다(보통의 덮어쓰기)" % op, sha(os.path.join(d, old)) != before)


def positional_ops(st, binary):
    """위치 인자 op — 입력과 같은 산출 · 대조."""
    print("[map · shellmap · unfold · strain · prestress]")
    d, _ = st.case("prestress", "pos")   # generate arc demo — demo_bent.k · demo_flat.k · demo_flat_fine.k · demo_flat_tet.k
    run(binary, d, ["extract-surface", "demo_bent.k", "bent_top.k", "--face", "top"])
    expect_refused("map output == flat", binary, d, ["map", "demo_bent.k", "demo_flat_fine.k", "demo_flat_fine.k"])
    expect_refused("map output == bent", binary, d, ["map", "demo_bent.k", "demo_flat_fine.k", "demo_bent.k"])
    expect_refused("shellmap output == flat_detail", binary, d, ["shellmap", "bent_top.k", "demo_flat_fine.k", "demo_flat_fine.k"])
    expect_refused("shellmap output == bent_shell", binary, d, ["shellmap", "bent_top.k", "demo_flat_fine.k", "bent_top.k"])
    expect_refused("unfold output == bent", binary, d, ["unfold", "demo_bent.k", "demo_bent.k"])
    os.link(os.path.join(d, "demo_bent.k"), os.path.join(d, "bent_hard.k"))
    expect_refused("unfold output == bent 의 하드 링크", binary, d, ["unfold", "demo_bent.k", "bent_hard.k"])
    expect_refused("strain output == def", binary, d, ["strain", "demo_flat.k", "demo_bent.k", "demo_bent.k"])
    shutil.copyfile(os.path.join(d, "demo_bent.k"), os.path.join(d, "def.key"))
    expect_refused("prestress ref def.key def.key (dynain 이 변형 메시를 다시 읽기 전에 덮었다)", binary, d,
                   ["prestress", "--E", "210000", "--nu", "0.3", "demo_flat.k", "def.key", "def.key"])
    expect_refused("prestress output bent.dynain → 메시 사본 bent.k == def", binary, d,
                   ["prestress", "--E", "210000", "--nu", "0.3", "demo_flat.k", "demo_bent.k", "demo_bent.dynain"])
    expect_refused("prestress output == ref(메시 사본이 기준 메시)", binary, d,
                   ["prestress", "--E", "210000", "--nu", "0.3", "demo_flat.k", "demo_bent.k", "demo_flat.k"])
    expect_refused("prestress --csv output x.csv → dynain 과 CSV 가 한 파일", binary, d,
                   ["prestress", "--E", "210000", "--nu", "0.3", "--csv", "demo_flat.k", "demo_bent.k", "x.csv"])
    keep = ["demo_bent.k", "demo_flat.k", "demo_flat_fine.k", "bent_top.k"]
    expect_ok("map 대조", binary, d, ["map", "demo_bent.k", "demo_flat_fine.k", "mapped.k"], keep, "mapped.k")
    expect_ok("shellmap 대조", binary, d, ["shellmap", "bent_top.k", "demo_flat_fine.k", "shellmapped.k"], keep, "shellmapped.k")
    expect_ok("unfold 대조", binary, d, ["unfold", "demo_bent.k", "unfolded.k"], keep, "unfolded.k")
    expect_ok("strain 대조", binary, d, ["strain", "demo_flat.k", "demo_bent.k", "strain.csv"], keep, "strain.csv")
    expect_ok("prestress 대조", binary, d, ["prestress", "--E", "210000", "--nu", "0.3", "demo_flat.k", "demo_bent.k", "pre"],
              keep, "pre.k")

    print("[map — prestress 고리]")
    base = "bent: demo_bent.k\nflat: demo_flat_fine.k\n"
    pre = "prestress:\n  enabled: true\n  output: %s\n  E: 210000.0\n  nu: 0.3\n"
    write(os.path.join(d, "m1.yaml"), base + "output: mapped1.k\n" + pre % "demo_flat_fine.k")
    expect_refused("map 고리 prestress.output == flat(메시 사본이 기준 메시를 덮었다)", binary, d, ["map", "m1.yaml"])
    write(os.path.join(d, "m2.yaml"), base + "output: demo_flat_fine.k\n" + pre % "pre2.dynain")
    expect_refused("map 고리 output == flat(고리가 덮인 flat 을 기준으로 0 응력)", binary, d, ["map", "m2.yaml"])
    write(os.path.join(d, "m3.yaml"), base + "output: foo.k\n" + pre % "foo.dynain")
    ok = expect_ok("map 고리 output foo.k + prestress.output foo.dynain(문서의 쓰임 — 사본이 map 산출 자리)", binary, d,
                   ["map", "m3.yaml"], keep, "foo.dynain")
    if ok:
        check("  └ foo.k 가 foo.dynain 을 *INCLUDE 한다", "foo.dynain" in read(os.path.join(d, "foo.k")))
    write(os.path.join(d, "m4.yaml"), base + "output: m4.key\n" + pre % "m4.key")
    expect_refused("map 고리 prestress.output == output(dynain 이 map 산출을 덮는다)", binary, d, ["map", "m4.yaml"])

    print("[extract-surface · squeeze · generate · generate-var · matswap 옛 꼴]")
    d, _ = st.case("squeeze", "pos")   # box.k · sq.yaml
    expect_refused("extract-surface output == solid", binary, d, ["extract-surface", "box.k", "box.k", "--face", "top"])
    expect_refused("squeeze prefix box → box.k == mesh", binary, d, ["squeeze", "box.k", "sq.yaml", "box"])
    expect_ok("extract-surface 대조", binary, d, ["extract-surface", "box.k", "box_top.k", "--face", "top"], ["box.k"], "box_top.k")
    expect_ok("squeeze 대조", binary, d, ["squeeze", "box.k", "sq.yaml", "box_sq"], ["box.k", "sq.yaml"], "box_sq.dynain")
    write(os.path.join(d, "gb.k"), SPEC["generate"]["files"]["box.yaml"].replace("output: box.k", "output: gb"))
    expect_refused("generate box 설정 gb.k + output gb → 설정을 덮는다", binary, d, ["generate", "box", "gb.k"])
    d, _ = st.case("generate-var", "pos")
    expect_refused("generate-var output == 설정", binary, d, ["generate-var", "var.yaml", "var.yaml"])
    expect_ok("generate-var 대조", binary, d, ["generate-var", "var.yaml", "var.k"], ["var.yaml"], "var.k")
    d, _ = st.case("matswap", "legacy")
    m, b = "examples/matswap/two_cubes.k", "examples/matswap/rubber.k"
    expect_refused("matswap 옛 꼴 output == model", binary, d, ["matswap", m, b, "1", m])
    expect_refused("matswap 옛 꼴 output == bundle", binary, d, ["matswap", m, b, "1", b])
    expect_ok("matswap 옛 꼴 대조", binary, d, ["matswap", m, b, "1", "swapped.k"], [m, b], "swapped.k")


def special_yaml(st, binary):
    print("[빈 output · 곁 파일 · 철자]")
    for op, cfg_name in (("boundary", "bc.yaml"), ("rbe", "rbe.yaml")):
        d, _ = st.case(op, "noout")
        cfg = re.sub(r"^output:.*\n", "", read(os.path.join(d, cfg_name)), flags=re.M)
        write(os.path.join(d, cfg_name), cfg)
        before = snapshot(d)
        rc, text = run(binary, d, [op, cfg_name])
        check("★%s output 을 빼면 → rc 1 「output 이 비어 있습니다」 · 모델을 덮지 않는다(예전엔 model 자리에 rc 0)" % op,
              rc == 1 and "output 이 비어" in text and not diff(before, snapshot(d)), (rc, text[-300:]))
    # rebind — 예전엔 문자열 비교라 `./` 철자를 못 봤다
    d, argv = st.case("rebind_entities_after_remesh", "dot")
    cfg = read(os.path.join(d, argv[1]))
    ent = yget(cfg, "entities")
    write(os.path.join(d, argv[1]), yset(cfg, "output", "./" + ent))
    expect_refused("rebind output == ./entities(문자열 비교가 놓쳤다)", binary, d, argv)
    # warpage 진단 파일 — 덱보다 먼저 쓴다
    d, argv = st.case("warpage", "debug")
    cfg = read(os.path.join(d, argv[1]))
    shutil.copyfile(os.path.join(d, "warp.dat"), os.path.join(d, "w_raw.dat"))
    cfg = yset(cfg, "dat_file", "w_raw.dat").replace("    mode: deform\n", "    mode: deform\n    debug: true\n    debug_prefix: w\n")
    write(os.path.join(d, argv[1]), cfg)
    expect_refused("warpage debug_prefix w → w_raw.dat == dat_file", binary, d, argv)
    # cad_solid_merge — 덱 뒤에 쓰는 대응표가 입력 대응표
    d, argv = st.case("cad_solid_merge_to_deck", "map")
    cfg = read(os.path.join(d, argv[1]))
    fm = yget(cfg, "fragment_map")
    shutil.copyfile(os.path.join(d, fm), os.path.join(d, "fm_fragment_map.json"))
    write(os.path.join(d, argv[1]), yset(yset(cfg, "fragment_map", "fm_fragment_map.json"), "output", "fm"))
    expect_refused("cad_solid_merge output fm → fm_fragment_map.json == fragment_map", binary, d, argv)
    # stackwrap — `_neutral.k` 를 bent_shell 을 읽기 전에 쓴다
    d, argv = st.case("stackwrap", "neutral")
    cfg = read(os.path.join(d, argv[1]))
    shutil.copyfile(os.path.join(d, yget(cfg, "bent_shell")), os.path.join(d, "sw_neutral.k"))
    write(os.path.join(d, argv[1]), yset(yset(cfg, "bent_shell", "sw_neutral.k"), "output", "sw"))
    expect_refused("stackwrap output sw → sw_neutral.k == bent_shell", binary, d, argv)
    # assemble — in-place 는 되고 인클루드는 막는다(위 행렬) · 처리의 입력(update 의 dynain)도 막는다
    d, argv = st.case("assemble", "update_dynain")
    write(os.path.join(d, "upd.yaml"), "base_model: box.k\noutput: dyn\noperations:\n  - type: update\n    dynain: dyn.k\n")
    write(os.path.join(d, "dyn.k"), "*KEYWORD\n*NODE\n       1             0.0             0.0             0.0\n*END\n")
    expect_refused("assemble update 의 dynain == output(dyn.k)", binary, d, ["assemble", "upd.yaml"])
    # assemble — 루프 안에서 덱보다 먼저 쓰는 곁 파일이 **뒤 처리**의 입력이면 무엇이든 쓰기 전에 막는다(예전엔 그때까지 읽은 것만 보았다)
    d, argv = st.case("warpage", "asm_mid")
    nodes = "*KEYWORD\n*NODE\n       1             0.0             0.0             0.0\n*END\n"
    write(os.path.join(d, "dbg_raw.dat"), nodes)
    write(os.path.join(d, "mid.yaml"),
          "base_model: box.k\noutput: wv\nmaterial:\n  E: 210000\n  nu: 0.3\noperations:\n"
          "  - type: warpage\n    target_pid: 1\n    dat_file: warp.dat\n    plane: xy\n    deflection_axis: +z\n"
          "    unit: um\n    mode: deform\n    debug: true\n    debug_prefix: dbg\n"
          "  - type: update\n    dynain: dbg_raw.dat\n")
    expect_refused("assemble warpage 진단(dbg_raw.dat)이 뒤 update 의 dynain — 쓰기 전에", binary, d, ["assemble", "mid.yaml"])
    d, argv = st.case("assemble", "asm_battery")
    bat = os.path.join(REPO, "examples", "battery", "swell", "stacked", "stacked_swell.yaml")
    shutil.copyfile(bat, os.path.join(d, "bat.yaml"))   # tier 0 · phase 1 → <output>_tier0_phase1.k
    write(os.path.join(d, "bx_tier0_phase1.k"), nodes)
    write(os.path.join(d, "bat_asm.yaml"),
          "base_model: box.k\noutput: ba\noperations:\n  - type: battery\n    config: bat.yaml\n    output: bx\n"
          "  - type: update\n    dynain: bx_tier0_phase1.k\n")
    expect_refused("assemble battery 덱(bx_tier0_phase1.k)이 뒤 update 의 dynain — 쓰기 전에", binary, d,
                   ["assemble", "bat_asm.yaml"])
    # meshfix polish — 임시 파일 `<줄기>__pol<회차>_<덩어리>.*` 은 gmsh 를 돌려 봐야 정해지니 그 꼴의 입력이 있으면 gmsh 전에 막는다
    d, argv = st.case("meshfix", "polish")
    cfg = read(os.path.join(d, argv[1]))
    write(os.path.join(d, argv[1]), cfg + "polish: true\n")
    add_include(os.path.join(d, yget(cfg, "model")), "remeshed__pol0_0.stl")
    before = snapshot(d)
    rc, text = run(binary, d, argv)
    check("★meshfix polish 의 임시 파일 꼴(remeshed__pol0_0.stl)인 인클루드 → gmsh 전에 rc 1 · 폴더 바이트 그대로",
          rc == 1 and "polish 의 임시 파일" in text and not diff(before, snapshot(d)), (rc, text[-300:]))


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="ogd_")
    st = Stager(binary, root)
    try:
        P, S = "prefix_k", lambda s: ("sfx", s)
        # ModelAssembler 계열(쓰기 관문 = writeOutput) — assemble 만 in-place
        for op in ("convert", "refine", "elform", "offset", "restack", "iga", "bend", "indent"):
            yaml_op(st, binary, op, P, "base_model")
        yaml_op(st, binary, "warpage", P, "base_model", extras=("dat_file",))
        yaml_op(st, binary, "disconnect", P, "base_model")
        yaml_op(st, binary, "formstrain", P, "base_model")
        yaml_op(st, binary, "wrap", P)
        yaml_op(st, binary, "update", P, extras=("dynain",))
        yaml_op(st, binary, "assemble", P, "base_model", inplace=True)
        for op in ("load", "boundary", "rbe", "matdb"):
            yaml_op(st, binary, op, P)
        yaml_op(st, binary, "matswap", P, extras=("bundle",), config=False)   # YAML 꼴은 설정이 .yaml 이어야 한다
        yaml_op(st, binary, "cad_solid_merge_to_deck", P, extras=("fragment", "fragment_map"))
        yaml_op(st, binary, "stackwrap", P, "flat_stack", extras=("bent_shell",))
        yaml_op(st, binary, "applyfold", P, extras=("groups",))
        yaml_op(st, binary, "cclip", P)
        # 자기 쓰기 op(DeckWriter · 보고)
        for op in ("relax", "stabilize", "database", "hfdamp", "implicit", "explicit", "modal", "ale", "optimize",
                   "contact", "cnrb2solid", "cnrb2spring", "merge", "tetremesh"):
            yaml_op(st, binary, op, "asis")
        yaml_op(st, binary, "meshfix", "asis", gmsh_needed=True)
        yaml_op(st, binary, "rebind_entities_after_remesh", "asis", "old_deck", extras=("new_deck", "entities", "range_diff"))
        yaml_op(st, binary, "refshell", "asis", "curve", include=False)
        yaml_op(st, binary, "modelmeta", S("_modelmeta.json"))
        yaml_op(st, binary, "section", S("_section.json"))
        yaml_op(st, binary, "surfview", S("_surface.svg"))
        yaml_op(st, binary, "stackdiagram", S("_stackdiagram.svg"))
        yaml_op(st, binary, "linkage-fit", S(".yaml"), "reference", extras=("folded",))
        yaml_op(st, binary, "id_floor", "json", extras=("fragment_map",))
        positional_ops(st, binary)
        special_yaml(st, binary)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print()
    if FAILS:
        print("FAIL %d  (OK %d)" % (len(FAILS), len(OKS)))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
