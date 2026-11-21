#!/usr/bin/env python3
# 고쳐 쓰는 op 이 인클루드로 쪼갠 덱에서 — 옵션 없이는 멈추고 안내하며, flatten_includes: true 면 안 쪼갠 덱과 같은 산출을 낸다
"""`flatten_includes` (2026-10-17 · 사용자 결정 「펼쳐서 한 파일로 — 옵션을 줄 때만」).

왜 이 시험이 있나.

  덱을 고쳐 쓰는 op 은 **주 덱만** 고친다(인클루드 안의 카드를 고쳐 쓸 길이 없다). 실측 — 모든 op 의 도움말 사례를
  모델 덱 = `*KEYWORD` + `*INCLUDE body.k` 로 쪼개 다시 돌렸더니
    · 14개가 rc 1(「Part 1 not found」 등 — 까닭은 맞지만 길을 말하지 않았다)
    · 10여 개가 rc 0 인데 **아무것도 안 바꾼 덱**을 냈다(convert·refine·elform·update·load·boundary·rbe·matdb ·
      tetremesh 는 메시도 *INCLUDE 도 없는 **빈 덱** · explicit 은 인클루드의 *CONTROL_IMPLICIT_* 를 그대로 남겼다)
  그래서 이 시험은 op 마다 셋을 본다.
    A. 안 쪼갠 덱 — 기준(rc 0)
    B. 쪼갠 덱 · 옵션 없음 — rc 1 이고 `flatten_includes` 를 안내한다(조용한 무편집 없음)
    C. 쪼갠 덱 · `flatten_includes: true` — rc 0 이고 산출이 A 와 같다(주석·빈 줄·*KEYWORD·*END 만 빼고 대조) ·
       주 덱 옆 임시 파일(`.*.kr_tmp_flat_*.k`)이 남지 않는다
  그리고 펼칠 수 없는 닫힘(없는 파일 · 칸 폭이 주 덱과 갈리는 인클루드)은 펼치지 않고 까닭을 말한다(D). 폭 규칙은
  `include_closure::widthMixWhy` 하나고 extract-parts 도 같이 쓴다(2026-11-21 — 그쪽 시험은 test_extract_parts_long.py 의 W).

usage: test_flatten_includes.py <KooRemapper 바이너리>
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "help"))
from ops_help import OPS  # noqa: E402

FAILS, OKS = [], []
TARGET = ["cclip", "disconnect", "offset", "restack", "iga", "merge", "warpage", "bend", "indent", "matswap",
          "assemble", "cnrb2spring", "ale", "applyfold", "convert", "refine", "elform", "wrap", "update", "tetremesh",
          "cnrb2solid", "strip", "matdb", "load", "boundary", "rbe", "explicit"]


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:300]))
    print("  %-72s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, cmd):
    argv = cmd.split()
    p = subprocess.run([binary] + argv[1:], cwd=cwd, capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def prep(spec, tmp):
    for need in spec["needs"]:
        dst = os.path.join(tmp, need)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copytree(os.path.dirname(os.path.join(ROOT, need)), os.path.dirname(dst), dirs_exist_ok=True)
    for n, c in spec["files"].items():
        p = os.path.join(tmp, n)
        os.makedirs(os.path.dirname(p) or tmp, exist_ok=True)
        open(p, "w").write(c)


def model_of(yaml_path):
    for l in open(yaml_path, errors="replace"):
        m = re.match(r"^(model|base_model|input)\s*:\s*(\S+)", l)
        if m:
            return m.group(2).strip().strip("\"'")
    return None


def split(path):
    """주 덱 = `*KEYWORD` + `*INCLUDE body_<이름>` + `*END` · 본문은 같은 폴더의 인클루드로."""
    L = open(path, errors="replace").read().splitlines()
    body = [l for l in L if not re.match(r"^\*(KEYWORD|END)\b", l.strip(), re.I)]
    kw = [l for l in L if re.match(r"^\*KEYWORD", l.strip(), re.I)]
    b = "body_" + os.path.basename(path)
    open(os.path.join(os.path.dirname(path), b), "w").write("\n".join(body) + "\n")
    open(path, "w").write("\n".join((kw or ["*KEYWORD"]) + ["*INCLUDE", b, "*END"]) + "\n")


def norm(text):
    return [l.rstrip() for l in text.splitlines()
            if l.strip() and not l.startswith("$") and not re.match(r"^\*(KEYWORD|END)\b", l.strip(), re.I)]


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    specs = {s["name"]: s for s in OPS}
    for name in TARGET:
        spec = specs.get(name)
        if not spec or not spec.get("cmds"):
            check("%s — 도움말 사례가 있다" % name, False)
            continue
        print("[%s]" % name)
        cmds = spec["cmds"]
        last = cmds[-1]
        ycfg = last.split()[2]
        dirs = [tempfile.mkdtemp(prefix="flt_%s_%s_" % (name, t)) for t in "abc"]
        try:
            for t in dirs:
                prep(spec, t)
                for c in cmds[:-1]:
                    run(binary, t, c)
            mp = model_of(os.path.join(dirs[1], ycfg))
            if not mp:
                check("%s — 사례 YAML 에서 모델을 찾았다" % name, False)
                continue
            for t in dirs[1:]:
                split(os.path.join(t, mp))
            with open(os.path.join(dirs[2], ycfg), "a") as f:
                f.write("\nflatten_includes: true\n")
            ra, oa = run(binary, dirs[0], last)
            rb, ob = run(binary, dirs[1], last)
            rc_, oc = run(binary, dirs[2], last)
            check("%s A 안 쪼갠 덱 — rc 0" % name, ra == 0, oa[-200:])
            check("%s B 쪼갠 덱 · 옵션 없음 — rc 1 · flatten_includes 를 안내한다" % name,
                  rb == 1 and "flatten_includes" in ob, (rb, [l for l in ob.splitlines() if "ERROR" in l][:2]))
            outs = [o for o in spec["outputs"] if o.endswith(".k")]
            same = all(os.path.exists(os.path.join(d, o)) for d in (dirs[0], dirs[2]) for o in outs) and all(
                norm(open(os.path.join(dirs[0], o), errors="replace").read()) ==
                norm(open(os.path.join(dirs[2], o), errors="replace").read()) for o in outs)
            check("%s C flatten_includes: true — rc 0 · 산출이 안 쪼갠 덱과 같다" % name, rc_ == 0 and same,
                  (rc_, [l for l in oc.splitlines() if "ERROR" in l][:2]))
            left = glob.glob(os.path.join(dirs[2], "**", ".*.kr_tmp_flat_*.k"), recursive=True)
            check("%s C 임시 파일이 남지 않는다" % name, not left, left)
        finally:
            for t in dirs:
                shutil.rmtree(t, ignore_errors=True)

    print("[D 펼칠 수 없는 닫힘 — 까닭을 말하고 쓰지 않는다]")
    d = tempfile.mkdtemp(prefix="flt_d_")
    try:
        spec = specs["convert"]
        prep(spec, d)
        for c in spec["cmds"][:-1]:
            run(binary, d, c)
        split(os.path.join(d, "box.k"))
        txt = open(os.path.join(d, "box.k")).read().replace("*END", "*INCLUDE\nmissing_part.k\n*END")
        open(os.path.join(d, "box.k"), "w").write(txt)
        with open(os.path.join(d, "convert.yaml"), "a") as f:
            f.write("\nflatten_includes: true\n")
        rc, out = run(binary, d, spec["cmds"][-1])
        check("D-1 없는 인클루드가 있으면 펼치지 않는다(rc 1 · 그 이름을 말한다)",
              rc == 1 and "missing_part.k" in out and not os.path.exists(os.path.join(d, "box_hex20.k")),
              (rc, [l for l in out.splitlines() if "ERROR" in l][:2]))
        ytxt = open(os.path.join(d, "convert.yaml")).read().replace("flatten_includes: true", "flatten_includes: maybe")
        open(os.path.join(d, "convert.yaml"), "w").write(ytxt)
        rc, out = run(binary, d, spec["cmds"][-1])
        check("D-2 참·거짓이 아닌 값은 말하고 펼치지 않는다", "참·거짓으로 읽지 못했다" in out and rc == 1, out[-300:])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    def edit(path, fn):
        txt = open(path).read()
        open(path, "w").write(fn(txt))

    # (이름, 주 덱을 고친다, 인클루드를 고친다, 기대 — 거절 까닭의 한 토막 또는 None(rc 0))
    for tag, what, on_main, on_body, want in (
            ("D-3", "인클루드가 제 `*KEYWORD I10=Y`(주 덱은 표준)", None, lambda t: "*KEYWORD I10=Y\n" + t,
             "body_box.k 의 *KEYWORD 폭(10)이 주 덱(8)과 다르다"),
            ("D-4", "주 덱의 `*INCLUDE -`", lambda t: t.replace("*INCLUDE\n", "*INCLUDE -\n"), None,
             "*INCLUDE + / *INCLUDE - (그 파일의 칸 폭을 바꾼다)가 있다"),
            ("D-5", "인클루드 안의 `*INCLUDE +`", None, lambda t: t + "*INCLUDE +\nextra.k\n",
             "body_box.k 에 *INCLUDE + / - 가 있다"),
            ("D-6", "인클루드가 제 맨 `*KEYWORD`(주 덱과 같은 폭)", None, lambda t: "*KEYWORD\n" + t, None)):
        d = tempfile.mkdtemp(prefix="flt_d_")
        try:
            spec = specs["convert"]
            prep(spec, d)
            for c in spec["cmds"][:-1]:
                run(binary, d, c)
            split(os.path.join(d, "box.k"))
            open(os.path.join(d, "extra.k"), "w").write("$ empty\n")
            if on_main:
                edit(os.path.join(d, "box.k"), on_main)
            if on_body:
                edit(os.path.join(d, "body_box.k"), on_body)
            with open(os.path.join(d, "convert.yaml"), "a") as f:
                f.write("\nflatten_includes: true\n")
            rc, out = run(binary, d, spec["cmds"][-1])
            wrote = os.path.exists(os.path.join(d, "box_hex20.k"))
            if want:
                check("%s %s — 펼치지 않는다(rc 1 · 까닭이 폭이다 · 산출 없음)" % (tag, what),
                      rc == 1 and want in out and not wrote, (rc, wrote, [l for l in out.splitlines() if "ERROR" in l][:2]))
            else:
                check("%s %s — 펼친다(rc 0)" % (tag, what), rc == 0 and wrote,
                      (rc, wrote, [l for l in out.splitlines() if "ERROR" in l][:2]))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    print("[E 마스터 덱 + 다른 파트 인클루드 — 주 덱에 대상이 있으면 예전처럼 고치고 말한다]")
    d = tempfile.mkdtemp(prefix="flt_e_")
    try:
        spec = specs["convert"]
        prep(spec, d)
        for c in spec["cmds"][:-1]:
            run(binary, d, c)
        # 주 덱은 그대로 두고, 다른 파트(PID 7) 하나를 인클루드로 붙인다
        open(os.path.join(d, "other.k"), "w").write(
            "*NODE\n%8d%16.6f%16.6f%16.6f\n%8d%16.6f%16.6f%16.6f\n%8d%16.6f%16.6f%16.6f\n%8d%16.6f%16.6f%16.6f\n"
            "*ELEMENT_SOLID\n%8d%8d%s\n*PART\nother\n%10d%10d%10d\n" % (
                9001, 50.0, 0.0, 0.0, 9002, 51.0, 0.0, 0.0, 9003, 50.0, 1.0, 0.0, 9004, 50.0, 0.0, 1.0,
                9001, 7, "".join("%8d" % n for n in [9001, 9002, 9003, 9004, 9004, 9004, 9004, 9004]), 7, 1, 1))
        txt = open(os.path.join(d, "box.k")).read().replace("*END", "*INCLUDE\nother.k\n*END")
        open(os.path.join(d, "box.k"), "w").write(txt)
        rc, out = run(binary, d, spec["cmds"][-1])
        check("E-1 「모든 파트」 op 이 주 덱의 파트를 고친다(rc 0)", rc == 0 and os.path.exists(os.path.join(d, "box_hex20.k")),
              [l for l in out.splitlines() if "ERROR" in l][:2])
        check("E-2 인클루드 안의 파트(PID 7)는 고치지 않았다고 말한다",
              "인클루드 안의 파트 1개(PID 7)는 고치지 않는다" in out, [l for l in out.splitlines() if "WARN" in l][:3])
        sp = specs["strip"]
        prep(sp, d)
        open(os.path.join(d, "strip.yaml"), "w").write(
            "model: box.k\noutput: box_cards_only.k\nkeywords:\n  - \"*SECTION_SOLID\"\n")
        rc, out = run(binary, d, "KooRemapper strip strip.yaml")
        check("E-3 strip — 남길 키워드가 인클루드에 없으면 예전처럼 거른다(rc 0)", rc == 0, out[-300:])
        open(os.path.join(d, "strip2.yaml"), "w").write(
            "model: box.k\noutput: box_cards_only2.k\nkeywords:\n  - \"*ELEMENT_SOLID\"\n")
        rc, out = run(binary, d, "KooRemapper strip strip2.yaml")
        check("E-4 strip — 남길 키워드가 인클루드에도 있으면 멈추고 안내한다",
              rc == 1 and "flatten_includes" in out and "other.k" in out, out[-300:])
    finally:
        shutil.rmtree(d, ignore_errors=True)

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
