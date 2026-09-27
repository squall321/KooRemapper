#!/usr/bin/env python3
# 42개 op 의 산출 덱 sha256 을 떠서 커밋 전/후를 대조한다 — "어느 덱의 바이트가 바뀌었나" 에 답한다
"""덱 쓰기 op 의 산출물 지문(manifest)을 뜨고 대조한다.

왜 이 도구가 있나 (2026-09-27):

  이 캠페인은 "전 op 산출물 sha256 불변" 을 관문으로 계속 말해 왔는데, **그것을 자동으로 답하는
  것이 리포에 없었다.** 개행 매트릭스와 바이트 왕복 시험은 같은 바이너리의 **LF 판과 CRLF 판을
  서로** 비교한다 — 양쪽이 똑같이 달라지면 초록이다. 실제로 그 구멍 때문에 `KFileWriter` 의
  TC/RC 소실이 닷새 동안 안 잡혔다.

  그래서 이 도구는 **다른 바이너리(또는 다른 커밋)의 산출물끼리** 비교한다.

사용법

    # 지금 바이너리로 지문을 뜬다
    python3 tools/regress/deck_manifest.py --emit before.json <바이너리>
    # …고친 뒤…
    python3 tools/regress/deck_manifest.py --emit after.json <바이너리>
    # 대조 — 다르면 rc=1 이고 op·파일 단위로 찍는다
    python3 tools/regress/deck_manifest.py --compare before.json after.json

    # 일부 op 만
    python3 tools/regress/deck_manifest.py --emit a.json <바이너리> --only map shellmap

⚠ **날짜를 가린다.** 산출 덱 머리에 `$ Date: YYYY-MM-DD HH:MM:SS` 가 초 단위로 박히므로 가리지
않으면 42 op 전부가 "바뀌었다" 로 나온다(`test_roundtrip_bytes.py` 의 `_DATE` 를 그대로 쓴다).

⚠ **모든 파일을 본다.** 처음 판은 '새로 생긴 파일' 만 봤는데, `map`·`shellmap`·`unfold` 처럼
출력이 스테이징된 이름을 덮어쓰는 op 이 "산출물 0개" 로 빠졌다 — 정작 검증하려던 경로가 대조
밖이었다. 그래서 스테이징 뒤 폴더의 **전체 파일**을 지문에 넣는다.

스테이징·인자 조립은 `test_newline_matrix.py` 와 `kooremapper_core.argbuild` 를 그대로 쓴다.
판정을 베끼면 두 곳이 갈린다.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "platform", "core"))

import test_newline_matrix as nlm  # noqa: E402
from kooremapper_core.argbuild import build_command  # noqa: E402
from pathlib import Path  # noqa: E402


def _digest(path):
    raw = open(path, "rb").read()
    raw = nlm._DATE.sub(nlm._DATE_MASK, raw) if hasattr(nlm, "_DATE") else raw
    return hashlib.sha256(raw).hexdigest()


def _mask(raw):
    """`$ Date:` 를 가린다. 매트릭스 모듈이 그 정규식을 안 내주면 여기 사본을 쓴다."""
    import re
    pat = re.compile(rb"(\$ Date: )\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
    return pat.sub(rb"\1XXXX-XX-XX XX:XX:XX", raw)


def digest(path):
    return hashlib.sha256(_mask(open(path, "rb").read())).hexdigest()


def emit(binary, only=None):
    env = dict(os.environ)
    g = nlm.gmsh_path() if hasattr(nlm, "gmsh_path") else os.environ.get("KOOREMAPPER_GMSH")
    if g:
        env["KOOREMAPPER_GMSH"] = g
    ops = json.load(open(nlm.CATALOG, encoding="utf-8"))["operations"]
    out = {"ops": {}, "skipped": {}}
    for o in ops:
        name = o["name"]
        if only and name not in only:
            continue
        if name in nlm.EXCLUDE:
            out["skipped"][name] = "EXCLUDE: " + nlm.EXCLUDE[name]
            continue
        folder = nlm.resolve_folder(o.get("example_folder"))
        args = (o.get("example") or {}).get("args")
        if not folder or not os.path.isdir(folder) or not isinstance(args, dict):
            out["skipped"][name] = "예제 폴더/인자가 없다"
            continue
        if o.get("requires_gmsh") and not g:
            out["skipped"][name] = "requires_gmsh 인데 gmsh 가 없다"
            continue
        d = tempfile.mkdtemp(prefix="dm_%s_" % name)
        try:
            why = nlm.stage(name, folder, d)
            if why:
                out["skipped"][name] = "스테이징 실패: " + why
                continue
            if name in nlm.PREP:
                argv, _ = nlm.PREP[name]
                rc, _o = nlm.run_op(binary, d, argv, env)
                if rc != 0:
                    out["skipped"][name] = "선언된 사전 단계 실패"
                    continue
            built = build_command(name, args, Path(d))
            if getattr(built, "error", None):
                out["skipped"][name] = "인자 조립 실패: " + str(built.error)
                continue
            rc, _o = nlm.run_op(binary, d, built.argv, env)
            files = {}
            for fn in sorted(os.listdir(d)):
                fp = os.path.join(d, fn)
                if os.path.isfile(fp):
                    files[fn] = digest(fp)
            out["ops"][name] = {"rc": rc, "files": files}
        finally:
            shutil.rmtree(d, ignore_errors=True)
    return out


def compare(a, b):
    bad = 0
    names = sorted(set(a["ops"]) | set(b["ops"]))
    for n in names:
        x, y = a["ops"].get(n), b["ops"].get(n)
        if x is None or y is None:
            print("  %-16s 한쪽에만 있다 (%s → %s)" % (n, "있음" if x else "없음", "있음" if y else "없음"))
            bad += 1
            continue
        if x["rc"] != y["rc"]:
            print("  %-16s rc %d → %d" % (n, x["rc"], y["rc"]))
            bad += 1
        diff = [f for f in sorted(set(x["files"]) | set(y["files"]))
                if x["files"].get(f) != y["files"].get(f)]
        if diff:
            print("  %-16s 달라진 파일 %d개: %s" % (n, len(diff), ", ".join(diff[:6])))
            bad += 1
    only_skip = set(a["skipped"]) ^ set(b["skipped"])
    if only_skip:
        print("  건너뛴 op 이 달라졌다: %s" % ", ".join(sorted(only_skip)))
        bad += 1
    if bad:
        print("\n달라진 op %d개 — 의도한 것인지 확인하라." % bad)
        return 1
    print("동일 %d op · 건너뜀 %d — 바이트가 바뀌지 않았다." % (len(names), len(a["skipped"])))
    return 0


def main():
    ap = argparse.ArgumentParser(description="덱 산출물 지문 뜨기/대조")
    ap.add_argument("--emit", metavar="OUT.json")
    ap.add_argument("--compare", nargs=2, metavar=("A.json", "B.json"))
    ap.add_argument("binary", nargs="?")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    if a.compare:
        return compare(json.load(open(a.compare[0])), json.load(open(a.compare[1])))
    if not a.emit or not a.binary:
        ap.error("--emit OUT.json <바이너리> 또는 --compare A.json B.json")
    m = emit(os.path.abspath(a.binary), set(a.only) if a.only else None)
    json.dump(m, open(a.emit, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print("지문 %d op (건너뜀 %d) → %s" % (len(m["ops"]), len(m["skipped"]), a.emit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
