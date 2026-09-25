#!/usr/bin/env python3
"""덱을 LF 로 넣든 CRLF 로 넣든 **같은 내용**이 나오나 — 개행만 보는 매트릭스의 다음 단계.

왜 이 시험이 있나 (2026-09-25, 덱 계약 2차 P1-1):

  `test_newline_matrix.py` 는 산출 덱에 **LF 단독 줄이 있나**만 본다. 그것으로는
  "입력 개행에 따라 **내용이** 달라지는" 결함을 못 잡는다. 예를 들어 리더가 `\\r` 을 덜 떼서
  `stoi`·`substr`·`back()` 분기가 갈리면, 산출 덱은 개행이 멀쩡한데 **값이 다르다.**
  그 종류는 구조 카운트도 정상이라 아무도 못 알아본다 — 이 리포가 여러 번 당한 모양이다.

무엇을 지키나. 같은 op 을 **같은 덱의 LF 판과 CRLF 판**에 각각 돌려서

  ① 내용이 같다        — `개행치환(출력_CRLF)` 의 sha256 == `출력_LF` 의 sha256
  ② 셈이 맞는다        — 줄 수 일치 · `n_crlf(CRLF판) == 줄 수` · `n_crlf(LF판) == 0` ·
                          말미 개행 일치 · **바이트 차이 == 줄 수**(줄마다 CR 하나씩만 늘었다)
  ③ 말미 개행이 없는 덱 — 그 판으로도 ①②가 성립한다(무-말미개행 픽스처)

덧붙여 알아낸 사실 — **이 도구의 산출 덱은 바이트 단위로 재현되지 않는다.** 헤더에
`$ Date: <현재 시각>` 이 박히기 때문이다(`KFileWriter::writeHeader`·`DynainWriter`).
같은 입력에 같은 op 을 두 번 돌려도 초가 넘어가면 sha256 이 달라진다. 이 시험은 비교 전에
그 값만 같은 길이의 자리표시자로 가린다 — **감추는 것이 아니라 여기 적어 두는 것이다.**
3자 대조(원본↔템플릿↔per-run)나 sha256 계보를 바이트로 하려면 이 줄을 끌 수 있어야 한다.

②의 마지막 항이 핵심이다. 바이트 차이가 줄 수와 정확히 같지 않으면 어딘가에서 CR 이 더
붙었거나(`\\r\\r\\n`) 빠진 것이다 — 개행 종류만 보면 둘 다 "CRLF" 로 통과한다.

usage: test_roundtrip_bytes.py <KooRemapper 바이너리> [--verbose]
"""
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
CORE = os.path.join(REPO, "platform", "core")

# ⚠ 픽스처 표(FIXTURES/PREP/EXCLUDE)와 스테이징은 **매트릭스에서 빌려 쓴다.** 베끼면 둘이
# 갈리고, 갈리면 한쪽은 틀린 채로 초록이 된다(`*INCLUDE` 판정이 셋으로 갈렸던 전례가 있다).
_spec = importlib.util.spec_from_file_location(
    "nlm", os.path.join(HERE, "test_newline_matrix.py"))
_nlm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_nlm)

DECK_EXT = _nlm.DECK_EXT
FAILS, OKS, SKIPS = [], [], []


def check(name, cond, detail=""):
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:300]) if detail else ""))
    return cond


def to_lf(path):
    b = open(path, "rb").read()
    open(path, "wb").write(b.replace(b"\r\n", b"\n"))


def to_crlf(path):
    b = open(path, "rb").read()
    open(path, "wb").write(b.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))


def drop_final_newline(path):
    b = open(path, "rb").read()
    while b.endswith(b"\n") or b.endswith(b"\r"):
        b = b[:-1]
    open(path, "wb").write(b)


# ⚠ 산출 덱에는 **시각이 박힌다** — `KFileWriter::writeHeader` 와 `DynainWriter` 가
# `$ Date: YYYY-MM-DD HH:MM:SS` 를 찍는다. 두 판을 1초 걸쳐 돌리면 그 한 줄 때문에 바이트가
# 달라진다(실측으로 `map` 이 그렇게 걸렸다 — 비결정성으로 오진할 뻔했다).
#
# 그래서 비교 전에 그 값만 **같은 길이**의 자리표시자로 바꾼다. 길이가 같으므로 바이트·줄·CR
# 셈은 그대로 유효하다. 이것은 시험의 편의가 아니라 **사실**이다 — 이 도구의 산출 덱은
# 지금 바이트 단위로 재현되지 않는다(3자 대조·sha256 계보에 영향이 있다).
_DATE = re.compile(rb"(\$ Date: )\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
_DATE_MASK = rb"\1XXXX-XX-XX XX:XX:XX"


def metrics(path):
    b = _DATE.sub(_DATE_MASK, open(path, "rb").read())
    n_crlf = b.count(b"\r\n")
    return {
        "bytes": len(b),
        "lines": b.count(b"\n"),
        "crlf": n_crlf,
        "final": b.endswith(b"\n"),
        "norm_sha": hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest(),
    }


def run_variant(binary, op, folder, args, build_command, env, *, newline, final):
    """한 변형으로 op 을 돌리고 {산출 덱 이름: 지표} 를 돌려준다. 못 돌면 (None, 이유)."""
    d = tempfile.mkdtemp(prefix="rtb_%s_" % op)
    try:
        why = _nlm.stage(op, folder, d)
        if why:
            return None, why
        if op in _nlm.PREP:
            argv, _w = _nlm.PREP[op]
            prc, pout = _nlm.run_op(binary, d, argv, env)
            if prc != 0:
                return None, "사전 단계 실패: %s" % pout.strip()[-100:]

        before = set()
        for fn in sorted(os.listdir(d)):
            fp = os.path.join(d, fn)
            if not os.path.isfile(fp) or not fn.endswith(DECK_EXT):
                continue
            (to_crlf if newline == "crlf" else to_lf)(fp)
            if not final:
                drop_final_newline(fp)
            before.add(fn)
        base = {fn: hashlib.sha256(_DATE.sub(_DATE_MASK,
                                              open(os.path.join(d, fn), "rb").read())).hexdigest()
                for fn in before}
        for fn in os.listdir(d):
            fp = os.path.join(d, fn)
            if os.path.isfile(fp):
                os.utime(fp, (_nlm.BASE_T, _nlm.BASE_T))

        built = build_command(op, args, Path(d))
        if getattr(built, "error", None):
            return None, "인자 조립 실패: %s" % built.error
        rc, out = _nlm.run_op(binary, d, built.argv, env)
        if rc != 0:
            return None, "rc=%d %s" % (rc, out.strip()[-100:])

        produced = {}
        for fn in sorted(os.listdir(d)):
            fp = os.path.join(d, fn)
            if not fn.endswith(DECK_EXT) or not os.path.isfile(fp):
                continue
            touched = int(os.stat(fp).st_mtime) != _nlm.BASE_T
            if fn in base:
                same = hashlib.sha256(
                    _DATE.sub(_DATE_MASK, open(fp, "rb").read())).hexdigest() == base[fn]
                if same and not touched:
                    continue            # 안 건드린 입력
            produced[fn] = metrics(fp)
        if not produced:
            return None, "산출 덱이 없다"
        return produced, None
    finally:
        shutil.rmtree(d, ignore_errors=True)


def compare(op, label, a, b):
    """a=CRLF 판, b=LF 판. 둘의 산출 덱을 대조한다."""
    if set(a) != set(b):
        check("%s[%s] 산출 덱 목록이 같다" % (op, label), False,
              "crlf=%s lf=%s" % (sorted(a), sorted(b)))
        return False
    ok = True
    for fn in sorted(a):
        x, y = a[fn], b[fn]
        ok &= check("%s[%s] %s 내용이 개행과 무관하다" % (op, label, fn),
                    x["norm_sha"] == y["norm_sha"],
                    "정규화 sha 가 다르다 — 입력 개행이 **내용**을 바꿨다")
        ok &= check("%s[%s] %s 줄 수가 같다" % (op, label, fn),
                    x["lines"] == y["lines"], "crlf=%d lf=%d" % (x["lines"], y["lines"]))
        ok &= check("%s[%s] %s CRLF 판이 전부 CRLF 다" % (op, label, fn),
                    x["crlf"] == x["lines"], "crlf=%d lines=%d" % (x["crlf"], x["lines"]))
        ok &= check("%s[%s] %s LF 판에 CR 이 없다" % (op, label, fn),
                    y["crlf"] == 0, "crlf=%d" % y["crlf"])
        ok &= check("%s[%s] %s 말미 개행이 같다" % (op, label, fn),
                    x["final"] == y["final"], "crlf=%s lf=%s" % (x["final"], y["final"]))
        # ⚠ 이 항이 `\r\r\n` 과 CR 누락을 잡는다 — 개행 종류만 보면 둘 다 "CRLF" 다.
        ok &= check("%s[%s] %s 바이트 차이가 줄 수와 같다" % (op, label, fn),
                    x["bytes"] - y["bytes"] == x["crlf"],
                    "Δbytes=%d crlf=%d" % (x["bytes"] - y["bytes"], x["crlf"]))
    return ok


def main():
    if len(sys.argv) < 2:
        print("usage: test_roundtrip_bytes.py <KooRemapper 바이너리> [--verbose]")
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
    g = _nlm.gmsh_path()
    if g:
        env["KOOREMAPPER_GMSH"] = g

    import json
    ops = json.load(open(_nlm.CATALOG, encoding="utf-8"))["operations"]
    print("[바이트 왕복 회귀] %d op — LF 판과 CRLF 판의 산출물을 대조한다" % len(ops))

    for o in ops:
        name = o["name"]
        if name in _nlm.EXCLUDE:
            continue
        folder = o.get("example_folder")
        args = (o.get("example") or {}).get("args")
        if not folder or not os.path.isdir(folder) or not isinstance(args, dict):
            check("%s 예제 폴더/인자가 있다" % name, False, "카탈로그를 고쳐야 한다")
            continue
        if o.get("requires_gmsh") and not g:
            check("%s gmsh 가 있다" % name, False,
                  "requires_gmsh 인데 gmsh 가 없다 — KOOREMAPPER_GMSH 나 dist/gmsh/gmsh")
            continue

        n_before = len(FAILS)
        for label, final in (("말미개행", True), ("무-말미개행", False)):
            a, why_a = run_variant(binary, name, folder, args, build_command, env,
                                   newline="crlf", final=final)
            b, why_b = run_variant(binary, name, folder, args, build_command, env,
                                   newline="lf", final=final)
            if a is None or b is None:
                # 두 판 다 같은 이유로 못 돌면 이 op 의 이 변형은 판정 대상이 아니다.
                if why_a == why_b:
                    SKIPS.append("%s[%s] — %s" % (name, label, why_a))
                else:
                    check("%s[%s] 두 판이 같은 결말을 낸다" % (name, label), False,
                          "crlf=%s / lf=%s" % (why_a, why_b))
                continue
            compare(name, label, a, b)
        if len(FAILS) == n_before:
            OKS.append(name)
            if verbose:
                print("  %-20s OK" % name)
        else:
            print("  %-20s FAIL" % name)

    print("")
    print("통과 %d · 실패 %d · 못 돌린 변형 %d" % (len(OKS), len(FAILS), len(SKIPS)))
    if verbose or FAILS:
        for s in SKIPS:
            print("  skip: " + s)
    if FAILS:
        print("")
        print("FAIL %d" % len(FAILS))
        for f in FAILS[:40]:
            print("  - " + f)
        if len(FAILS) > 40:
            print("  … 외 %d건" % (len(FAILS) - 40))
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
