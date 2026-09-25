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

왜 다시 고쳤나 (2026-09-25, 덱 계약 2차 P0-3):

  이 시험이 "보존 19 · 깨짐 0 · 건너뜀 30" 을 냈고 그것을 근거로 회신을 썼다. 그런데 실사용
  박스가 `meshfix` 의 CRLF 소실을 돌려줬다 — **건너뜀 30 안에 있던 것**이다(gmsh 가 없어
  skip 됐다). 같은 자리에 더 있었다. 건너뜀 29를 하나씩 뜯어보니 세 부류였다.

    ① 예제 폴더에 입력 덱이 아예 없다(16 op) — 카탈로그 example 의 파일 이름은 프런트 폼
       자리표시자(`SessionDetailPage.tsx:54`)이고, 실제 덱은 다른 폴더에 있거나 생성물이다.
    ② **판정이 잘못됐다**(6 op) — 로그는 `Done -> xxx.k` 인데 "새 덱 0개" 로 세어졌다. 산출물
       이름이 예제 폴더에 이미 커밋돼 있어서, op 이 그것을 **바이트 동일하게** 다시 쓰면
       내용 해시가 같아 "안 바뀐 입력" 으로 걸러졌다. 이건 실패가 아니라 **보존**이다.
    ③ 정말 덱을 안 쓴다(7 op).

  그래서 이 시험은 이제 **건너뛰지 않는다.** op 은 셋 중 하나로 끝나야 한다 —
  보존 / 깨짐 / **선언된 제외**. 그 밖은 전부 FAIL(미판정)이다. gmsh 가 없어도 FAIL 이다.

어떻게 도나:
  카탈로그(`platform/core/kooremapper_core/catalog_data.json`)의 op 별 `example` + `example_folder`
  를 그대로 쓴다. 예제 폴더를 임시 디렉터리에 복사하고, 필요하면 아래 `FIXTURES`/`PREP` 로
  입력 덱을 갖다 놓은 뒤, **모든 덱을 CRLF 로 바꾸고** op 을 돌려 산출 덱의 개행을 본다.

판정:
  · 산출 덱에 **LF 단독 줄이 있으면 FAIL**(전멸이든 혼재든 같은 실패다)
  · 덱을 건드렸는데 바이트가 그대로면 **보존(바이트 동일)** — 통과지만 따로 센다
  · 덱을 하나도 건드리지 못했거나 rc≠0 이면 **FAIL(미판정)** — 건너뛰지 않는다

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

DECK_EXT = (".k", ".key", ".dyn", ".dynain")
# 기준선 mtime — 복사·변환이 끝난 뒤 모든 파일을 이 시각으로 맞춘다. 그러면 op 이 **건드렸는지**
# (mtime 변화)와 **내용을 바꿨는지**(해시 변화)를 따로 볼 수 있다. 둘을 안 나누면 바이트 동일
# 보존이 "안 건드렸다" 로 묻힌다 — 실제로 6개 op 이 그렇게 묻혀 있었다.
BASE_T = 946684800                                   # 2000-01-01 UTC

# ── 선언 ① 덱을 쓰지 않는 op ────────────────────────────────────────────────
# 이 목록에 있는 op 만 판정을 면제받는다. 조용히 빠지는 길은 없다.
EXCLUDE = {
    "info": "읽기 전용 — 덱을 쓰지 않는다",
    "modelmeta": "메타 JSON 만 낸다",
    "strain": "CSV 만 낸다(ref_mesh/def_mesh 를 읽고 변형률 표를 쓴다)",
    "stcx_fullangle_drop": "외부 클러스터 제출 op — 덱을 여기서 쓰지 않는다",
    # 아래 셋은 덱을 **새로** 만든다 — 보존할 원본 개행이 없다. 새 덱을 어떤 개행으로 낼지는
    # 별개 정책 문제다(입력이 없으니 '보존' 이라는 말이 성립하지 않는다).
    "generate": "덱을 새로 만든다 — 입력 덱이 없다",
    "generate-var": "덱을 새로 만든다 — 입력 덱이 없다(`ref` 는 예제가 쓰지 않는다)",
    "battery": "배터리 덱을 새로 만든다 — src/commands/battery.cpp 는 입력 덱을 읽지 않는다",
}

# ── 선언 ② 예제 폴더에 입력 덱이 없는 op ────────────────────────────────────
# (예제 폴더 기준 원본 경로, 임시 디렉터리에 놓을 이름, 왜 이 덱인가)
#
# ⚠ 카탈로그를 고치지 않는 이유 — `example.args` 의 파일 이름은 프런트가 폼에 그대로 채우는
#   **자리표시자**다(`SessionDetailPage.tsx:54`). 거기에 `../ale/explicit.k` 같은 경로를 넣으면
#   업로드 세션에서 `safe_relpath` 가 `..` 를 떼어내 더 헷갈린다. 스테이징은 시험의 몫이다.
FIXTURES = {
    "squeeze":   [("squeeze_box.k", "model.k", "이 폴더의 실제 덱")],
    "indent":    [("small/block.k", "block.k", "예제가 하위 폴더에 있다")],
    "explicit":  [("../ale/explicit.k", "base_model.k", "level01.yaml 이 가리키는 덱")],
    "implicit":  [("../ale/explicit.k", "explicit.k", "dynamic_lv1.yaml 이 가리키는 덱")],
    "modal":     [("../ale/explicit.k", "explicit.k", "modal_minimal.yaml 이 가리키는 덱")],
    "stabilize": [("../ale/explicit.k", "base_model.k", "explicit 폴더를 공유한다")],
    "boundary":  [("../load/mesh.k", "mesh.k", "boundary_fixed.yaml 이 가리키는 덱")],
    "rbe":       [("../load/mesh.k", "mesh.k", "rbe_face.yaml 이 가리키는 덱")],
    "offset":    [("../arc30/arc30_flat.k", "arc30_flat.k", "01_basic_solid_tied.yaml 이 가리키는 덱")],
    "hfdamp":    [("../assemble/box.k", "box.k", "basic.yaml 이 가리키는 덱")],
    "restack":   [("../replace_test/restack_base.k", "restack_base.k", "restack 예제는 replace_test 에 있다")],
    "optimize":  [("two_cubes.k", "model.k", "matswap 폴더를 공유한다 — 이 폴더의 실제 덱")],
    "warpage":   [("../bend/small/warpage_3x3.dat", "warpage_3x3.dat", "dat 는 bend 예제에 있다")],
    # 아래 둘은 예제가 가리키는 덱이 리포에 없다 — 대체 덱을 **쓰는 이유까지** 적는다.
    "database":  [("../ale/explicit.k", "test_model.k",
                   "materials/test_model.k 가 리포에 없다. database 는 *DATABASE 카드만 붙이므로 덱을 가린다")],
    "strip":     [("../load/mesh.k", "al_box.k",
                   "assemble_display/al_box.k 는 120MB 라 커밋돼 있지 않다. strip 은 키워드만 뽑으므로 덱을 가린다")],
}

# ── 선언 ③ 입력 덱을 다른 op 으로 먼저 만들어야 하는 op ─────────────────────
PREP = {
    "cclip": (["generate", "box", "gen_board.yaml"],
              "clip_board.k 는 생성물이다 — gen_board.yaml 주석대로 generate 로 먼저 만든다"),
}

FAILS = []
OKS = []
IDENTICAL = []
EXCLUDED = []


def fail(name, why):
    FAILS.append("%s: %s" % (name, why))
    print("  %-20s FAIL  %s" % (name, why))


def gmsh_path():
    """gmsh 를 결정적으로 찾는다 — PATH 의 깨진 파이썬 래퍼를 집으면 op 이 rc=1 로 죽는다."""
    env = os.environ.get("KOOREMAPPER_GMSH")
    if env and os.path.exists(env):
        return env
    cand = os.path.join(REPO, "dist", "gmsh", "gmsh")
    return cand if os.path.exists(cand) else None


def to_crlf(path):
    b = open(path, "rb").read()
    b = b.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    open(path, "wb").write(b)


def newline_counts(path):
    b = open(path, "rb").read()
    lf = b.count(b"\n")
    crlf = b.count(b"\r\n")
    return crlf, lf - crlf          # (crlf, lone_lf)


def run_op(binary, cwd, argv, env, timeout=600):
    p = subprocess.run([binary, *argv], cwd=cwd, capture_output=True, text=True,
                       timeout=timeout, env=env)
    return p.returncode, (p.stdout + p.stderr)


def stage(name, folder, d):
    """예제 폴더를 평탄 복사하고 선언된 픽스처를 갖다 놓는다. 실패하면 이유를 돌려준다."""
    # 번들 재질 DB — `matdb` 는 작업 폴더 `materials/` → 실행 파일 옆 `materials/` 순으로 찾는다
    # (`ModelAssembler.cpp:12527 md_findBundledDb`). 갖다 놓지 않으면 **바이너리가 어디 있느냐**에
    # 따라 결과가 갈린다(배포 트리에선 통과, 빌드 트리에선 rc=1). 시험은 그 차이에 걸리면 안 된다.
    shutil.copytree(os.path.join(REPO, "materials"), os.path.join(d, "materials"),
                    dirs_exist_ok=True)
    for fn in os.listdir(folder):
        src = os.path.join(folder, fn)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(d, fn))
    for rel, as_name, _why in FIXTURES.get(name, []):
        src = os.path.normpath(os.path.join(folder, rel))
        if not os.path.isfile(src):
            return "선언된 픽스처가 없다: %s (FIXTURES 를 고쳐야 한다)" % rel
        shutil.copy2(src, os.path.join(d, as_name))
    return None


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

    env = dict(os.environ)
    g = gmsh_path()
    if g:
        env["KOOREMAPPER_GMSH"] = g

    ops = json.load(open(CATALOG, encoding="utf-8"))["operations"]
    names = {o["name"] for o in ops}
    print("[전 op CRLF 보존 매트릭스] %d op" % len(ops))

    # 선언이 카탈로그와 어긋나면 먼저 잡는다 — op 이 빠졌는데 선언만 남으면 다음 사람이 속는다.
    for label, table in (("EXCLUDE", EXCLUDE), ("FIXTURES", FIXTURES), ("PREP", PREP)):
        for stale in sorted(set(table) - names):
            fail(stale, "%s 에 선언돼 있는데 카탈로그에 없는 op 이다" % label)

    for o in ops:
        name = o["name"]
        if name in EXCLUDE:
            EXCLUDED.append("%s — %s" % (name, EXCLUDE[name]))
            continue
        folder = o.get("example_folder")
        args = (o.get("example") or {}).get("args")
        if not folder or not os.path.isdir(folder) or not isinstance(args, dict):
            fail(name, "예제 폴더/인자가 없다 — 카탈로그를 고치거나 EXCLUDE 에 이유를 적어야 한다")
            continue
        if o.get("requires_gmsh") and not g:
            # ⚠ skip 이 아니라 FAIL 이다. `meshfix` 의 CRLF 소실이 정확히 이 자리에 숨어 있었다.
            fail(name, "requires_gmsh 인데 gmsh 가 없다 — apt install gmsh 뒤 "
                       "KOOREMAPPER_GMSH=/usr/bin/gmsh, 또는 dist/gmsh/gmsh 를 두고 다시 돌린다")
            continue

        d = tempfile.mkdtemp(prefix="nlm_%s_" % name)
        try:
            why = stage(name, folder, d)
            if why:
                fail(name, why)
                continue
            if name in PREP:
                argv, _why = PREP[name]
                prc, pout = run_op(binary, d, argv, env)
                if prc != 0:
                    fail(name, "선언된 사전 단계 실패(%s): %s" % (" ".join(argv), pout.strip()[-120:]))
                    continue

            before = {}
            for fn in os.listdir(d):
                fp = os.path.join(d, fn)
                if not os.path.isfile(fp):
                    continue
                if fn.endswith(DECK_EXT):
                    to_crlf(fp)
                before[fn] = hashlib.sha256(open(fp, "rb").read()).hexdigest()
                os.utime(fp, (BASE_T, BASE_T))

            built = build_command(name, args, Path(d))
            if getattr(built, "error", None):
                fail(name, "인자 조립 실패: %s" % built.error)
                continue
            rc, out = run_op(binary, d, built.argv, env)
            if rc != 0:
                fail(name, "rc=%d — 예제가 돌지 않는다: %s" % (rc, out.strip()[-140:]))
                continue

            changed, same = [], []
            for fn in sorted(os.listdir(d)):
                fp = os.path.join(d, fn)
                if not fn.endswith(DECK_EXT) or not os.path.isfile(fp):
                    continue
                if fn not in before:
                    changed.append(fn)                          # 새로 생긴 덱
                    continue
                if hashlib.sha256(open(fp, "rb").read()).hexdigest() != before[fn]:
                    changed.append(fn)
                elif int(os.stat(fp).st_mtime) != BASE_T:
                    same.append(fn)                             # 다시 썼는데 바이트가 같다 = 보존
            if not changed and not same:
                fail(name, "덱을 하나도 건드리지 않았다 — 예제가 산출 덱을 내지 않는다: %s" % out.strip()[-140:])
                continue

            bad = []
            for fn in changed:
                crlf, lone = newline_counts(os.path.join(d, fn))
                if lone > 0:
                    bad.append("%s(CRLF %d / LF단독 %d)" % (fn, crlf, lone))
            if bad:
                fail(name, ", ".join(bad))
            elif changed:
                OKS.append(name)
                if verbose:
                    print("  %-20s OK    %s" % (name, ", ".join(changed)))
            else:
                IDENTICAL.append(name)
                if verbose:
                    print("  %-20s OK    (바이트 동일) %s" % (name, ", ".join(same)))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    adjudicated = len(OKS) + len(IDENTICAL) + len(FAILS)
    print("")
    print("보존 %d(그중 바이트 동일 %d) · 깨짐 %d · 제외 %d  →  판정 %d + 제외 %d = %d op"
          % (len(OKS) + len(IDENTICAL), len(IDENTICAL), len(FAILS), len(EXCLUDED),
             adjudicated, len(EXCLUDED), adjudicated + len(EXCLUDED)))
    if verbose:
        for s in EXCLUDED:
            print("  제외: " + s)
    if adjudicated + len(EXCLUDED) != len(ops):
        print("  ⚠ 합이 op 수와 다르다 — 판정을 놓친 op 이 있다")
        FAILS.append("판정 합 불일치: %d + %d != %d" % (adjudicated, len(EXCLUDED), len(ops)))
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
