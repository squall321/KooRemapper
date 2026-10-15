#!/usr/bin/env python3
"""우리가 쓴 덱의 **첫 카드가 `*KEYWORD`** 인가 — 전 op 전수.

왜 이 시험이 있나 (2026-10-15).

  매뉴얼이 못박았다 — "Flags LS-DYNA that the input deck is a keyword deck.
  **To have an effect this must be the very first card in the input deck.**"
  (Vol_I 18086-18087, 다시 18566-18568). 첫 카드가 아니면 LS-DYNA 는 그 파일을
  **옛 structured 입력**으로 읽으려 든다. 그 덱은 해석에 바로 못 쓴다.

  그런데 `KFileWriter::writeHeader` 는 `$` 머리말 넉 줄만 찍고 `*KEYWORD` 를 **안 찍었다.**
  다섯 쓰기 자리(DynainWriter · IGA · core_ops · surface_extract · cclip) 중 **그 하나만**
  빠뜨린 것이다. 그래서 `generate`·`unfold`·`map` 산출 덱에 `*KEYWORD` 가 없었고,
  그 덱을 입력으로 삼은 다음 op 이 그 **없음을 그대로 베껴** 번졌다 —
  실측으로 **추적 덱 496장 중 177장**이 그 상태였다.

  이미 한 번 걸린 적이 있다. `squeeze_assemble.cpp:217` 주석이 적어 뒀다 —
  "예전엔 writeFile() 로 *NODE/*ELEMENT_SOLID 만 써서 ***KEYWORD**/*PART/*SECTION/*MAT 이
  빠진, 해석에 바로 못 쓰는 덱이 나왔다". 그때는 **그 한 명령만** 보존 경로로 돌려 끝냈다.
  쓰는 쪽을 안 고쳤으니 나머지는 그대로 남았다.

  ★그리고 관문 73+78 개가 **전부 초록인 채로** 그 상태였다. 아무도 산출 덱의 **첫 카드**를
  보지 않았기 때문이다. 이 시험이 그 자리다.

무엇을 보나.

  A 전 op 훑기 — 42 op 을 돌려 **새로 쓰거나 바뀐** 덱 전수의 첫 카드가 `*KEYWORD` 이고
    `*KEYWORD` 카드가 **꼭 하나**인가. 둘이면 중복이고, 둘이면 뒤의 옵션이 안 읽힌다.
  B 보존 경로 — 원본에 `*KEYWORD` 가 **있으면** 더 찍지 않는다(중복 금지).
  C 보존 경로 — 원본에 **없으면** 보충한다(옛 덱 177장이 그 꼴이다).
  D ★`I10=Y` 선언이 살아남는다 — 맨 `*KEYWORD` 를 **앞세우면** `deckFieldWidth` 가 첫
    것에서 멈추므로 i10 덱이 **8칸으로 읽힌다**. 선언 10칸·본문 8칸 — `cnrb2` 에서 고친
    그 결함을 쓰는 쪽에서 되살리는 꼴이다. 그래서 "없을 때만" 이 중요하다.
  E 훑은 장 수가 0 이 아니다 — **세는 관문이 0을 세면 언제나 초록이다.**

제외는 하나뿐이고 이유를 적는다 — `materials/` 아래는 번들 재질 DB(`*PARAMETER` + `*MAT_*`)
로 **`*INCLUDE` 로 끌어 쓰는 조각**이다. 조각은 첫 카드가 `*KEYWORD` 일 필요가 없고,
우리가 쓰는 것도 아니다(`stage()` 가 갖다 놓는다).

usage: test_keyword_card.py <KooRemapper 바이너리> [--verbose]
"""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
CORE = os.path.join(REPO, "platform", "core")

# ⚠ 픽스처 표(FIXTURES/PREP/EXCLUDE)와 스테이징은 **매트릭스에서 빌려 쓴다.** 베끼면 둘이
# 갈리고, 갈리면 한쪽은 틀린 채로 초록이 된다(`test_roundtrip_bytes.py` 가 적어 둔 그대로다).
_spec = importlib.util.spec_from_file_location(
    "nlm", os.path.join(HERE, "test_newline_matrix.py"))
_nlm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_nlm)

DECK_EXT = _nlm.DECK_EXT
# 번들 재질 조각 — 위 머리말에 이유를 적었다. 여기 한 줄만 제외한다.
SKIP_PREFIX = "materials" + os.sep

FAILS, OKS = [], []


def check(name, cond, detail=""):
    if cond:
        OKS.append(name)
    else:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:300]) if detail else ""))
    return cond


def resolve_folder(v):
    if not v:
        return None
    return v if os.path.isabs(v) else os.path.join(REPO, v)


def first_card(path):
    """첫 **카드**. `$` 주석과 빈 줄은 카드가 아니다(Vol_I 17862 — 무시되는 줄이다)."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            s = ln.lstrip(" \t")
            if s.startswith("*"):
                return s.rstrip("\r\n")
    return None


def keyword_cards(path):
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            s = ln.lstrip(" \t")
            if s[:8].upper() == "*KEYWORD":
                out.append(s.rstrip("\r\n"))
    return out


def decks_under(d):
    for root, _dirs, files in os.walk(d):
        for fn in sorted(files):
            if fn.endswith(DECK_EXT):
                fp = os.path.join(root, fn)
                yield os.path.relpath(fp, d), fp


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def judge(label, rel, fp):
    """한 산출 덱을 판정한다."""
    fc = first_card(fp)
    kws = keyword_cards(fp)
    ok_first = fc is not None and fc[:8].upper() == "*KEYWORD"
    check("%s %s 의 첫 카드가 *KEYWORD 다" % (label, rel), ok_first,
          "첫 카드=%r (Vol_I 18086 — 첫 카드가 아니면 structured 입력으로 읽힌다)" % fc)
    check("%s %s 의 *KEYWORD 카드가 하나다" % (label, rel), len(kws) == 1,
          "%d 개: %r" % (len(kws), kws[:3]))
    return ok_first and len(kws) == 1


def run_catalog_op(binary, o, env, gmsh, build_command):
    """한 op 을 스테이징해 돌리고 (새로/바뀐 덱 목록, 못 돈 이유) 를 돌려준다."""
    name = o["name"]
    folder = resolve_folder(o.get("example_folder"))
    args = (o.get("example") or {}).get("args")
    if not folder or not os.path.isdir(folder) or not isinstance(args, dict):
        return None, "카탈로그의 example_folder/args 가 없다 — 카탈로그를 고쳐야 한다"
    if o.get("requires_gmsh") and not gmsh:
        return None, "requires_gmsh 인데 gmsh 가 없다 — KOOREMAPPER_GMSH 나 dist/gmsh/gmsh"

    d = tempfile.mkdtemp(prefix="kwc_%s_" % name)
    try:
        why = _nlm.stage(name, folder, d)
        if why:
            return None, why
        if name in _nlm.PREP:
            argv, _w = _nlm.PREP[name]
            prc, pout = _nlm.run_op(binary, d, argv, env)
            if prc != 0:
                return None, "사전 단계 실패: %s" % pout.strip()[-120:]

        # ⚠ **내용이 같아도 덮어쓴 것은 산출물이다.** 리포에는 예제 폴더에 **지난 산출물이
        #   함께 들어 있다**(예: `examples/tet10/tet10_result.k`). `stage()` 가 그것까지 갖다
        #   놓으므로, sha 만 보면 op 이 같은 내용으로 덮어쓴 덱을 "안 건드린 입력" 으로 넘긴다.
        #   실측으로 **7 op(cnrb2solid·convert·refine·elform·matdb·hfdamp·ale)이 0 장**이 됐다.
        #   그래서 `roundtrip` 과 같은 수법을 쓴다 — 돌리기 전에 mtime 을 못박고 바뀌었나 본다.
        base = {}
        for rel, fp in decks_under(d):
            base[rel] = sha(fp)
            os.utime(fp, (_nlm.BASE_T, _nlm.BASE_T))
        built = build_command(name, args, Path(d))
        if getattr(built, "error", None):
            return None, "인자 조립 실패: %s" % built.error
        rc, out = _nlm.run_op(binary, d, built.argv, env)
        if rc != 0:
            return None, "rc=%d %s" % (rc, out.strip()[-120:])

        produced = []
        for rel, fp in decks_under(d):
            if rel.startswith(SKIP_PREFIX):
                continue
            touched = int(os.stat(fp).st_mtime) != _nlm.BASE_T
            if rel in base and base[rel] == sha(fp) and not touched:
                continue                      # 안 건드린 입력
            produced.append((rel, judge("[A] %s" % name, rel, fp)))
        return produced, None
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    if len(sys.argv) < 2:
        print("usage: test_keyword_card.py <KooRemapper 바이너리> [--verbose]")
        return 2
    binary = os.path.abspath(sys.argv[1])
    verbose = "--verbose" in sys.argv
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2

    sys.path.insert(0, CORE)
    try:
        from kooremapper_core.argbuild import build_command
    except Exception as exc:                                   # noqa: BLE001
        print("argbuild 를 못 불러왔다(파이썬 계층 필요): %s" % exc)
        return 2

    env = dict(os.environ)
    gmsh = _nlm.gmsh_path()
    if gmsh:
        env["KOOREMAPPER_GMSH"] = gmsh

    ops = json.load(open(_nlm.CATALOG, encoding="utf-8"))["operations"]
    todo = [o for o in ops if o["name"] not in _nlm.EXCLUDE]
    print("[첫 카드 관문] %d op — 산출 덱의 첫 카드가 *KEYWORD 인가 (Vol_I 18086)" % len(todo))

    # ── A. 전 op 훑기 ───────────────────────────────────────────────────────
    print("[A 전 op 훑기]")
    seen = 0
    for o in todo:
        produced, why = run_catalog_op(binary, o, env, gmsh, build_command)
        if produced is None:
            # 못 돌았으면 **건너뛰지 않는다** — 돌지 않는 op 은 지켜지지 않는 op 이다.
            check("[A] %s 를 돌릴 수 있다" % o["name"], False, why)
            continue
        if not produced:
            check("[A] %s 가 덱을 하나라도 쓴다" % o["name"], False,
                  "산출/변경된 덱이 0 장이다 — 이 op 은 이 관문이 못 지킨다")
            continue
        seen += len(produced)
        if verbose:
            print("   %-18s %d 장" % (o["name"], len(produced)))

    # ── E. 세는 관문이 0 을 세지 않는다 ─────────────────────────────────────
    # 실측(2026-10-15)으로 47 장이었다. 넉넉히 40 으로 둔다 — 스테이징이 깨져 아무것도
    # 안 나오면 위 판정이 **하나도 안 돌고** 초록이 된다. 그 침묵을 막는 자리다.
    check("[E] 훑은 덱이 40 장 이상이다", seen >= 40,
          "%d 장만 봤다 — 스테이징이나 카탈로그가 깨졌다" % seen)

    # ── B·C·D. 보존 경로의 세 갈래 ─────────────────────────────────────────
    print("[B·C·D 보존 경로]")
    d = tempfile.mkdtemp(prefix="kwc_pres_")
    try:
        # B. 원본에 *KEYWORD 가 있다 ⇒ 더 찍지 않는다
        rc, out = _nlm.run_op(binary, d, ["generate", "arc", os.path.join(d, "g")], env)
        if check("[B] generate 가 돈다", rc == 0, out.strip()[-120:]):
            src = os.path.join(d, "g_flat_fine.k")
            check("[B] generate 산출에 *KEYWORD 가 하나 있다",
                  len(keyword_cards(src)) == 1, keyword_cards(src))
            rc, out = _nlm.run_op(binary, d, ["map", os.path.join(d, "g_bent.k"), src,
                                              os.path.join(d, "b_out.k")], env)
            if check("[B] map 이 돈다", rc == 0, out.strip()[-120:]):
                judge("[B] 원본에 있다", "b_out.k", os.path.join(d, "b_out.k"))

        # C. 원본에 *KEYWORD 가 없다(옛 덱 177장의 꼴) ⇒ 보충한다
        old_b = os.path.join(REPO, "examples", "arc30", "arc30_bent.k")
        old_f = os.path.join(REPO, "examples", "arc30", "arc30_flat_fine.k")
        if check("[C] *KEYWORD 없는 옛 덱 픽스처가 있다",
                 os.path.isfile(old_b) and os.path.isfile(old_f),
                 "examples/arc30/arc30_{bent,flat_fine}.k"):
            check("[C] 그 픽스처에 정말 *KEYWORD 가 없다",
                  keyword_cards(old_f) == [],
                  "픽스처가 고쳐졌으면 이 갈래는 다른 덱으로 옮겨야 한다")
            rc, out = _nlm.run_op(binary, d, ["map", old_b, old_f,
                                              os.path.join(d, "c_out.k")], env)
            if check("[C] 옛 덱으로 map 이 돈다", rc == 0, out.strip()[-120:]):
                judge("[C] 원본에 없다", "c_out.k", os.path.join(d, "c_out.k"))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # D. I10 선언이 살아남는다 — 맨 *KEYWORD 를 앞세우면 여기서 걸린다
    d = tempfile.mkdtemp(prefix="kwc_i10_")
    try:
        folder = os.path.join(REPO, "examples", "load")
        load_op = next((o for o in ops if o["name"] == "load"), None)
        if check("[D] load op 과 i10 예제 폴더가 있다",
                 load_op is not None and os.path.isdir(folder), folder):
            _nlm.stage("load", folder, d)
            src = os.path.join(d, "mesh.k")
            kws = keyword_cards(src)
            if check("[D] 원본이 i10 을 선언한다", len(kws) == 1 and "I10" in kws[0].upper(),
                     "%r — 픽스처가 바뀌었으면 다른 i10 덱으로 옮겨야 한다" % kws):
                built = build_command("load", (load_op.get("example") or {})["args"], Path(d))
                rc, out = _nlm.run_op(binary, d, built.argv, env)
                if check("[D] i10 덱으로 load 가 돈다", rc == 0, out.strip()[-120:]):
                    dst = os.path.join(d, "mesh_loaded.k")
                    okws = keyword_cards(dst)
                    judge("[D] i10 덱", "mesh_loaded.k", dst)
                    check("[D] 산출의 첫 *KEYWORD 가 여전히 i10 을 선언한다",
                          len(okws) >= 1 and "I10" in okws[0].upper(),
                          "%r — 맨 *KEYWORD 를 앞세우면 deckFieldWidth 가 8 을 돌려주고"
                          " 선언 10칸·본문 8칸 덱이 된다(Vol_I 19357)" % okws)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    for n in OKS if verbose else []:
        print("  %-70s OK" % n[:70])
    if FAILS:
        print("FAIL %d  (OK %d)" % (len(FAILS), len(OKS)))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS — %d 항 (훑은 덱 %d 장)" % (len(OKS), seen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
