#!/usr/bin/env python3
# 플랫폼 경로의 YAML 키 순서 — 카탈로그 예제를 사람이 쓴 순서와 플랫폼 순서(JSONB + argbuild 우선 키)로 각각 돌려 산출이 같은지 본다
"""왜 이 시험이 있나 (2026-10-24, D23).

  플랫폼은 잡 인자를 Postgres JSONB 로 저장한다. JSONB 는 키 순서를 지키지 않는다(키 길이 → 바이트 순으로 다시 놓는다).
  argbuild 는 그 순서를 받아 `type` · `action` 만 앞으로 끌어 YAML 을 쓴다. 그런데 contact 파서는 `- action` 으로 시작하는
  항목만 알아봐서, 플랫폼에서 type 을 준 create 가 늘 「YAML has no contact actions」 로 떨어졌고 카탈로그 예제는 create 를
  앞 항목에 섞어 **조용히 버리고 rc 0** 이었다. 바이너리 회귀는 사람이 쓴 YAML(`- action` 먼저)만 써서 못 봤다.

  YAML 에서 키 순서는 뜻이 없다. 그러니 어느 op 이든 두 순서의 산출이 같아야 한다 — 그것을 여기서 잰다.
    · 사람이 쓴 순서 — 카탈로그 예제 그대로(argbuild 우선 키를 끈 판)
    · 플랫폼 순서     — JSONB 순서로 다시 놓고 argbuild 그대로
  두 YAML 글자가 같은 op 은 돌리지 않는다(같은 입력이면 같은 산출이다). 덱 지문(`deck_manifest`)이 빼는 op(battery ·
  generate-var 처럼 덱을 새로 만드는 것)도 여기서는 돌린다 — 그 산출도 키 순서와 상관없어야 한다.

  산출은 덱 지문과 같은 규칙으로 잰다(`$ Date` · 스테이징 폴더 경로를 가린다).

usage: test_platform_key_order.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools"))
import deck_manifest as dm  # noqa: E402  — 스테이징 · 지문 규칙을 베끼지 않는다
import kooremapper_core.argbuild as AB  # noqa: E402

nlm = dm.nlm
FAILS = []


def check(name, cond, detail=""):
    print("  %-60s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:400]) if detail else ""))


def jsonb(o):
    """Postgres JSONB 가 객체 키를 다시 놓는 순서 — 키 길이(바이트) 다음 바이트 순. 목록 순서는 그대로다."""
    if isinstance(o, dict):
        return {k: jsonb(o[k]) for k in sorted(o, key=lambda k: (len(k.encode()), k.encode()))}
    if isinstance(o, list):
        return [jsonb(x) for x in o]
    return o


def built_text(name, args, d, platform):
    prio = AB._PRIORITY_KEYS
    try:
        AB._PRIORITY_KEYS = prio if platform else ()
        b = AB.build_command(name, jsonb(args) if platform else args, Path(d))
    finally:
        AB._PRIORITY_KEYS = prio
    return b, (b.written_files or {}).get("config.yaml", " ".join(b.argv or []))


def run_once(binary, op, args, platform, env):
    folder = nlm.resolve_folder(op.get("example_folder"))
    d = tempfile.mkdtemp(prefix="ko_%s_" % op["name"])
    try:
        if folder and os.path.isdir(folder):
            why = nlm.stage(op["name"], folder, d)
            if why:
                return None, "스테이징 실패: " + why
        if op["name"] in nlm.PREP:
            argv, _ = nlm.PREP[op["name"]]
            rc, _o = nlm.run_op(binary, d, argv, env)
            if rc != 0:
                return None, "사전 단계 실패"
        b, _t = built_text(op["name"], args, d, platform)
        if getattr(b, "error", None):
            return {"rc": None, "err": str(b.error), "files": {}}, None
        rc, _o = nlm.run_op(binary, d, b.argv, env)
        files = {fn: dm.digest(os.path.join(d, fn)) for fn in sorted(os.listdir(d))
                 if os.path.isfile(os.path.join(d, fn)) and fn != "config.yaml"}
        return {"rc": rc, "err": None, "files": files}, None
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2
    env = dict(os.environ)
    g = nlm.gmsh_path() if hasattr(nlm, "gmsh_path") else os.environ.get("KOOREMAPPER_GMSH")
    if g:
        env["KOOREMAPPER_GMSH"] = g
    ops = json.load(open(nlm.CATALOG, encoding="utf-8"))["operations"]

    print("[두 순서의 YAML 이 다른 op 만 돌린다]")
    differ, same, skipped = [], 0, []
    for o in ops:
        args = (o.get("example") or {}).get("args")
        if not isinstance(args, dict):
            continue
        tmp = tempfile.mkdtemp(prefix="ko_txt_")
        try:
            _a, ta = built_text(o["name"], args, tmp, False)
            _b, tb = built_text(o["name"], args, tmp, True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if ta == tb:
            same += 1
        else:
            differ.append(o)
    print("  YAML 이 다른 op %d · 같은 op %d" % (len(differ), same))
    check("두 순서의 YAML 이 다른 op 이 있다(시험이 빈 것을 재지 않는다)", len(differ) > 0)

    print("[산출 대조 — 사람이 쓴 순서 대 플랫폼 순서]")
    for o in differ:
        if o.get("requires_gmsh") and not g:
            skipped.append((o["name"], "gmsh 없음"))
            continue
        a, why_a = run_once(binary, o, o["example"]["args"], False, env)
        b, why_b = run_once(binary, o, o["example"]["args"], True, env)
        if a is None or b is None:
            skipped.append((o["name"], why_a or why_b))
            continue
        bad = [f for f in sorted(set(a["files"]) | set(b["files"])) if a["files"].get(f) != b["files"].get(f)]
        check("%s: rc 가 같다 (%s)" % (o["name"], a["rc"]), a["rc"] == b["rc"] and a["err"] == b["err"],
              "사람 %s %s / 플랫폼 %s %s" % (a["rc"], a["err"], b["rc"], b["err"]))
        check("%s: 산출이 같다 (%d 파일)" % (o["name"], len(a["files"])), not bad, ", ".join(bad[:6]))
    for n, why in skipped:
        print("  %-60s 건너뜀(%s)" % (n, why))

    print("")
    if FAILS:
        print("FAIL %d" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
