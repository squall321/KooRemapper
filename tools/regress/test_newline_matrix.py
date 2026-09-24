#!/usr/bin/env python3
"""**모든 op** 이 CRLF 덱의 개행을 보존하나 — op 마다 쓰기 경로가 달라 한 곳만 고쳐선 안 된다.

왜 이 시험이 있나 (2026-09-24, 덱 편집 계약 요청서 DF-01 / SYS-02):

  같은 CRLF 덱에 op 만 바꿔 돌린 실측(수정 전):

      indent    CRLF 0   / LF 579   전멸
      database  CRLF 0   / LF 635   전멸
      relax     CRLF 578 / LF 585   **혼재** — 원본 줄은 CRLF, 새로 넣은 줄은 LF
      strip     CRLF 578 / LF 579   보존

  한 파일 안에서 개행이 갈리는 `relax` 가 최악이다. 그리고 이 차이 자체가 **계약이 없다는
  직접 증거**다 — 25곳 넘는 자체 `ofstream` 이 각자 개행을 정한다.

어떻게 도나:
  카탈로그(`platform/core/kooremapper_core/catalog_data.json`)의 op 별 `example` + `example_folder`
  를 그대로 쓴다. 예제 폴더를 임시 디렉터리에 복사하고 **모든 `.k` 를 CRLF 로 바꾼 뒤** 그 op 을
  돌려, 새로 생긴 `.k` 의 개행을 본다. 예제가 곧 구동기라 op 이 늘어도 시험이 따라온다.

판정:
  · 새 `.k` 에 **LF 단독 줄이 있으면 FAIL**(전멸이든 혼재든 같은 실패다)
  · op 이 실패했거나 새 `.k` 가 없으면 **SKIP**(이 시험의 관심사가 아니다 — 솔직히 건너뛴다)

usage: test_newline_matrix.py <KooRemapper 바이너리> [--verbose]
"""
import hashlib
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
CATALOG = os.path.join(CORE, "kooremapper_core", "catalog_data.json")

FAILS = []
SKIPS = []
OKS = []

# 이 시험이 다루지 않는 op — 이유를 적어 둔다(조용히 빼지 않는다).
EXCLUDE = {
    "stcx_fullangle_drop": "외부 클러스터 제출 op — 덱을 여기서 쓰지 않는다",
    "info": "읽기 전용 — 덱을 쓰지 않는다",
    "modelmeta": "메타 JSON 만 낸다",
    # `generate*` 는 덱을 **새로** 만든다 — 보존할 원본 개행이 없다(입력 덱이 없다).
    # 새 덱을 어떤 개행으로 낼지는 별개 정책 문제라 이 시험의 관심사가 아니다.
}


def _consumes_a_deck(op, args, folder):
    """이 호출이 **실제로 입력 덱을 먹나.**

    덱을 새로 만드는 op 은 보존할 원본 개행이 없으므로 이 시험의 관심사가 아니다.
    판정은 이름 목록이 아니라 **카탈로그의 file 타입 파라미터 + 그 파일의 실재**로 한다
    (`takes_kfile` 만으로는 부족하다 — `generate-var` 는 true 지만 예제는 config 로만 돈다).
    """
    # ① 최상위 file 파라미터가 **있는데 하나도 안 주어졌다면** 새로 만드는 호출이다.
    #    (`generate-var` 가 그렇다 — `ref` 를 받을 수 있지만 예제는 config 로만 돈다)
    file_params = [pr["name"] for pr in op.get("params", []) if pr.get("type") == "file"]
    if file_params:
        given = [n for n in file_params
                 if isinstance(args.get(n), str) and args.get(n)
                 and os.path.isfile(os.path.join(folder, args[n]))]
        return bool(given)
    # ② yaml 계열은 덱 경로가 config 안에 있어 최상위 file 파라미터가 없다.
    #    카탈로그가 덱을 먹는다고 선언했고(`takes_kfile`) 예제 폴더에 덱이 있으면 먹는 호출로 본다.
    #    ⚠ `takes_kfile` 조건이 없으면 `generate` 가 걸린다 — 그 예제 폴더에는 **산출물** .k 가
    #    커밋돼 있어서, 폴더에 덱이 있다는 것만으로는 "먹는다" 를 못 말한다.
    if not op.get("takes_kfile", False):
        return False
    return any(fn.endswith((".k", ".key", ".dyn")) for fn in os.listdir(folder))


def to_crlf(path):
    b = open(path, "rb").read()
    b = b.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    open(path, "wb").write(b)


def newline_counts(path):
    b = open(path, "rb").read()
    lf = b.count(b"\n")
    crlf = b.count(b"\r\n")
    return crlf, lf - crlf          # (crlf, lone_lf)


def run_op(binary, cwd, argv, timeout=300):
    p = subprocess.run([binary, *argv], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr)


def main():
    if len(sys.argv) < 2:
        print("usage: test_newline_matrix.py <KooRemapper 바이너리> [--verbose]")
        return 2
    binary = os.path.abspath(sys.argv[1])
    verbose = "--verbose" in sys.argv
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2
    if not os.path.exists(CATALOG):
        print("catalog not found: " + CATALOG)
        return 2

    sys.path.insert(0, CORE)
    try:
        from kooremapper_core.argbuild import build_command
    except Exception as exc:                                  # noqa: BLE001
        print("argbuild 를 못 불러왔다(파이썬 계층 필요): %s" % exc)
        return 2

    ops = json.load(open(CATALOG, encoding="utf-8"))["operations"]
    print("[전 op CRLF 보존 매트릭스] %d op" % len(ops))

    for o in ops:
        name = o["name"]
        if name in EXCLUDE:
            SKIPS.append("%s — %s" % (name, EXCLUDE[name]))
            continue
        folder = o.get("example_folder")
        args = (o.get("example") or {}).get("args")
        if not folder or not os.path.isdir(folder) or not isinstance(args, dict):
            SKIPS.append("%s — 예제 폴더/인자가 없다" % name)
            continue
        if not _consumes_a_deck(o, args, folder):
            SKIPS.append("%s — 이 호출은 입력 덱을 먹지 않는다(새로 만든다)" % name)
            continue

        d = tempfile.mkdtemp(prefix="nlm_%s_" % name)
        try:
            for fn in os.listdir(folder):
                src = os.path.join(folder, fn)
                if os.path.isfile(src):
                    shutil.copy2(src, os.path.join(d, fn))
            # ⚠ mtime 으로 "새로 생겼나" 를 재면 안 된다 — op 이 예제 폴더에 이미 있는 이름으로
            # 덮어쓰는데(예: tetremesh 의 tet10_result.k) 같은 mtime 틱에 걸리면 **건너뛰어져
            # 거짓 통과**가 된다(실제로 한 번 그랬다). 내용 해시로 잰다.
            before = {}
            for fn in os.listdir(d):
                fp = os.path.join(d, fn)
                if fn.endswith((".k", ".key", ".dyn", ".dynain")):
                    to_crlf(fp)
                before[fn] = hashlib.sha256(open(fp, "rb").read()).hexdigest()

            built = build_command(name, args, Path(d))
            if getattr(built, "error", None):
                SKIPS.append("%s — 인자 조립 실패: %s" % (name, built.error))
                continue
            rc, out = run_op(binary, d, built.argv)

            produced = []
            for fn in sorted(os.listdir(d)):
                if not fn.endswith((".k", ".key", ".dyn", ".dynain")):
                    continue
                p = os.path.join(d, fn)
                if fn in before and hashlib.sha256(open(p, "rb").read()).hexdigest() == before[fn]:
                    continue                                   # 한 바이트도 안 바뀐 입력
                produced.append(fn)

            if rc != 0 or not produced:
                SKIPS.append("%s — rc=%d, 새 덱 %d개 (%s)" % (name, rc, len(produced), out.strip()[-90:]))
                continue

            bad = []
            for fn in produced:
                crlf, lone = newline_counts(os.path.join(d, fn))
                if lone > 0:
                    bad.append("%s(CRLF %d / LF단독 %d)" % (fn, crlf, lone))
            if bad:
                FAILS.append("%s: %s" % (name, ", ".join(bad)))
                print("  %-20s FAIL  %s" % (name, ", ".join(bad)))
            else:
                OKS.append(name)
                if verbose:
                    print("  %-20s OK    %s" % (name, ", ".join(produced)))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    print("")
    print("보존 %d · 깨짐 %d · 건너뜀 %d" % (len(OKS), len(FAILS), len(SKIPS)))
    if verbose or FAILS:
        for s in SKIPS:
            print("  skip: " + s)
    if FAILS:
        print("")
        print("FAIL %d" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
