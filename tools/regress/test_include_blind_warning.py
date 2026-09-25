#!/usr/bin/env python3
"""ID 발행자가 `*INCLUDE` 를 못 봤다고 **말하나** — 그리고 번호는 **그대로인가**.

왜 이 시험이 있나 (2026-09-25, 덱 계약 2차 P0-6):

  이 리포의 발행자는 "이 덱의 최대 ID + 1" 로 새 번호를 낸다. 그런데 리더는 `*INCLUDE` 안을
  읽지 않는다(`KFileReader` 에 INCLUDE 처리가 0건이다). 실사용 낙하시험 덱은 거의 언제나
  나뉘어 있으므로 **인클루드에 이미 있는 번호를 다시 발급할 수 있다.**

  이 단계의 목표는 번호 정책을 바꾸는 것이 **아니다** — 하류(pyKooCAE REMAP 체인·플랫폼
  워커)가 바이트 동일과 rc=0 을 기대한다. 목표는 **모른다는 사실을 말하게 하는 것**이다.

무엇을 지키나:

  ① 인클루드가 있는 덱에서 경고가 **나온다**
  ② 인클루드가 **없는** 덱에서는 안 나온다(실사용 잡에 경고가 쏟아지면 아무도 안 읽는다)
  ③ `*INCLUDE_PATH` 만 있는 덱에서도 안 나온다 — 그것은 탐색 경로일 뿐 카드를 안 끌어온다.
     예전 `ReferenceIntegrity` 는 그것을 파일로 세어 `info` 가 거짓 경고를 냈다
  ④ **번호가 안 바뀐다** — 인클루드 두 줄만 뺀 덱과 발급된 ID 집합이 같다.
     인클루드 줄 자체는 ID 를 정의하지 않으므로 같아야 한다. 이것이 '번호 불변' 의 직접 증거다
  ⑤ **rc 가 안 바뀐다** — 두 경우 모두 같다

usage: test_include_blind_warning.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples")

# 새로 발급된 ID 를 뽑을 키워드 — 값이 첫 칸인 것만 본다(오독을 안 만든다).
_ID_KW = ("*SET_PART", "*SET_SEGMENT", "*SET_NODE", "*PART", "*SECTION", "*MAT", "*DEFINE_CURVE")


def check(name, cond, detail=""):
    print("  %-64s %s" % (name[:64], "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:300]) if detail else ""))


def run(binary, cwd, *args, env=None):
    e = dict(os.environ)
    g = os.path.join(REPO, "dist", "gmsh", "gmsh")
    if os.path.exists(g):
        e["KOOREMAPPER_GMSH"] = g
    if env:
        e.update(env)
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True,
                       timeout=900, env=e)
    return p.returncode, p.stdout + p.stderr


def ids_of(path):
    """산출 덱에서 ID 집합을 뽑는다 — 키워드마다 첫 데이터 카드의 첫 칸."""
    out = {}
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return out
    i = 0
    while i < len(lines):
        s = lines[i].strip().upper()
        if s.startswith("*") and any(s.startswith(k) for k in _ID_KW):
            kw = next(k for k in _ID_KW if s.startswith(k))
            skip = 1 if "_TITLE" in s or kw == "*PART" else 0
            j = i + 1
            while j < len(lines):
                d = lines[j].strip()
                if not d or d.startswith("$"):
                    j += 1
                    continue
                if d.startswith("*"):
                    break
                if skip > 0:
                    skip -= 1
                    j += 1
                    continue
                m = re.match(r"^\s*([-+]?\d+)", lines[j])
                if m:
                    out.setdefault(kw, set()).add(int(m.group(1)))
                break
        i += 1
    return out


def prep(d, src, *, mode):
    """덱을 만든다. mode: 'inc'(*INCLUDE 2줄) · 'none' · 'path'(*INCLUDE_PATH 만)."""
    lines = open(src, encoding="utf-8", errors="replace").read().splitlines()
    k = next((n for n, l in enumerate(lines) if l.strip().upper().startswith("*KEYWORD")), 0)
    extra = {"inc": ["*INCLUDE", "part_1.k", "*INCLUDE", "sub/part_2.k"],
             "none": [],
             "path": ["*INCLUDE_PATH", "/some/dir"]}[mode]
    body = lines[:k + 1] + extra + lines[k + 1:]
    name = {"inc": "m_inc.k", "none": "m_none.k", "path": "m_path.k"}[mode]
    open(os.path.join(d, name), "w").write("\n".join(body) + "\n")
    return name


def lane(binary, label, op, base_deck, yaml_text, out_name, extra=()):
    """한 op 을 세 모드(inc / none / path)로 돌려 ①~⑤ 를 본다.

    ⚠ ④ 는 **실제로 발급된 ID** 를 비교한다. 처음에는 산출 덱의 ID 집합을 그냥 비교했는데,
    발급이 0건인 조합(`hfdamp` + 1파트 덱)에서는 기존 ID 만 비교해 **변이가 살아남았다.**
    그래서 입력 대비 새로 생긴 ID 를 뽑고, 그것이 0건이면 이 레인은 발행자를 시험하지 못한
    것이므로 FAIL 이다.
    """
    print("[%s]" % label)
    d = tempfile.mkdtemp(prefix="ibw_")
    try:
        shutil.copytree(os.path.join(REPO, "materials"), os.path.join(d, "materials"),
                        dirs_exist_ok=True)
        for f in extra:
            shutil.copy(f, os.path.join(d, os.path.basename(f)))
        res, decks = {}, {}
        for mode in ("inc", "none", "path"):
            decks[mode] = prep(d, base_deck, mode=mode)
            y = "y_%s.yaml" % mode
            open(os.path.join(d, y), "w").write(
                yaml_text.replace("@MODEL@", decks[mode]).replace("@OUT@", "o_%s.k" % mode))
            res[mode] = run(binary, d, op, y)

        check("① 인클루드가 있으면 경고한다",
              "읽지 않았습니다" in res["inc"][1], res["inc"][1][-400:])
        check("② 인클루드가 없으면 조용하다",
              "읽지 않았습니다" not in res["none"][1], res["none"][1][-300:])
        check("③ *INCLUDE_PATH 만 있으면 조용하다(탐색 경로는 파일이 아니다)",
              "읽지 않았습니다" not in res["path"][1], res["path"][1][-300:])
        check("⑤ rc 가 안 바뀐다",
              res["inc"][0] == res["none"][0] == res["path"][0],
              {k: v[0] for k, v in res.items()})
        if res["inc"][0] != 0:
            check("op 이 돌았다", False, res["inc"][1][-300:])
            return

        def issued(mode):
            before = ids_of(os.path.join(d, decks[mode]))
            after = ids_of(os.path.join(d, "o_%s.k" % mode))
            out = {}
            for k in set(before) | set(after):
                diff = after.get(k, set()) - before.get(k, set())
                if diff:
                    out[k] = sorted(diff)
            return out

        a, b = issued("inc"), issued("none")
        check("④-a 이 레인이 실제로 ID 를 발급한다(안 하면 ④ 가 헛통과한다)", bool(a),
              "새로 생긴 ID 가 없다 — 다른 덱/모드를 골라야 한다")
        check("④-b 발급된 ID 가 그대로다(인클루드 줄은 ID 를 정의하지 않는다)", a == b,
              "inc=%s  none=%s" % (sorted(a.items()), sorted(b.items())))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    if len(sys.argv) < 2:
        print("usage: test_include_blind_warning.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2

    box = os.path.join(EX, "assemble", "box.k")
    cubes = os.path.join(EX, "matswap", "two_cubes.k")
    rubber = os.path.join(EX, "matswap", "rubber.k")
    ale_deck = os.path.join(EX, "ale", "explicit.k")
    for f in (box, cubes, rubber, ale_deck):
        if not os.path.exists(f):
            print("예제 덱이 없다: " + f)
            return 2

    # 창구 둘을 각각 대표로 본다.
    #   assembler 창구(ModelAssembler::loadBaseModel) — 발행자 18곳을 한 곳이 덮는다
    #   자립 창구 — op 이 자기 덱을 직접 읽는 경로
    lane(binary, "matswap YAML — assembler 창구(loadBaseModel)", "matswap", cubes,
         "model: @MODEL@\noutput: @OUT@\nswaps:\n  - bundle: rubber.k\n    pid: 1\n",
         "@OUT@", extra=[rubber])
    lane(binary, "ale YAML — 자립 창구", "ale", ale_deck,
         "model: @MODEL@\noutput: @OUT@\nale_parts:\n  - pid: 3\n    material: air\n",
         "@OUT@")

    # ── 창구가 둘 열려 **두 번** 찍지 않나 ──────────────────────────────────
    # `hfdamp`·`matswap`·`cnrb2solid` 는 입구가 둘이다(자립 실행 · assemble 안의 op). 발급은
    # 공통 함수에서 일어나므로 거기에 경고를 넣으면 assemble 경로에서 두 번 찍힌다. 그래서
    # 경고는 **진입점**에만 둔다 — 이 시험이 그 규율을 지킨다. 경고가 두 번이면 사람이 센다.
    print("[assemble 안의 hfdamp — 경고가 한 번만]")
    d = tempfile.mkdtemp(prefix="ibw_dup_")
    try:
        shutil.copytree(os.path.join(REPO, "materials"), os.path.join(d, "materials"),
                        dirs_exist_ok=True)
        m = prep(d, box, mode="inc")
        open(os.path.join(d, "asm.yaml"), "w").write(
            "base_model: %s\noutput: asm_out\noperations:\n"
            "  - type: hfdamp\n    dt_target: 3.0e-8\n    cdamp: 0.99\n"
            "    fhigh_ratio: 100.0\n    mode: global\n    tssfac: 0.9\n" % m)
        rc, out = run(binary, d, "assemble", "asm.yaml")
        n = out.count("읽지 않았습니다")
        check("경고가 정확히 한 번 나온다(창구 중복 없음)", n == 1,
              "n=%d rc=%d %s" % (n, rc, out[-300:]))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # ── info 의 오탐 — `*INCLUDE_PATH` 만 있는 덱을 '안 읽은 인클루드' 로 세지 않는다 ──
    # 예전 `ReferenceIntegrity` 는 `rfind("*INCLUDE",0)==0` 만 봐서 탐색 경로를 파일로 셌다.
    # ⚠ 기존 `test_reference_integrity.py` 는 이 오탐을 **못 잡는다**(진짜 `*INCLUDE` 만 쓴다).
    print("[info — *INCLUDE_PATH 오탐이 사라졌다]")
    d = tempfile.mkdtemp(prefix="ibw_info_")
    try:
        mp = prep(d, box, mode="path")
        mi = prep(d, box, mode="inc")
        rc_p, out_p = run(binary, d, "info", mp)
        rc_i, out_i = run(binary, d, "info", mi)
        check("*INCLUDE_PATH 만: '보지 않았습니다' 를 안 찍는다",
              "*INCLUDE 안은 보지 않았습니다" not in out_p, out_p[-300:])
        check("진짜 *INCLUDE: 여전히 찍는다(잠금)",
              "*INCLUDE 안은 보지 않았습니다" in out_i, out_i[-300:])
        check("info 의 rc 계약은 그대로 0", rc_p == 0 and rc_i == 0,
              "path=%d inc=%d" % (rc_p, rc_i))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("")
    if FAILS:
        print("FAIL %d" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
