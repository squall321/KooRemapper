#!/usr/bin/env python3
# 임시 파일 + 바꿔 넣기(공용 staged_write — extract-parts · apply_carryover_plan)가 이름 길이 · 죽은 실행 · 산출 자리 꼴 · 바꿔 넣기 차례 · 말 · 글자를 지키는지 보는 회귀 시험
"""공용 도우미 `staged_write`(include/util/StagedWrite.h) — 두 op 의 쓰기 규칙 (2026-11-08).

왜 이 시험이 있나.

  extract-parts(a33af2f) · apply_carryover_plan(0895025)은 산출 · 곁 파일 · 보고를 임시 파일에 쓰고 끝까지 지나면 바꿔 넣는다. 두 리뷰
  (3차 검토 · 판 2 적대적 검토)가 그 사본에서 결함을 찾았다. 이 시험은 그 자리마다 실제로 돌려 본다.

무엇을 보나.
  E 긴 이름 — 임시 이름이 산출 이름에 30 글자를 더해 NAME_MAX 가까운 이름(ASCII 236 바이트 · 한글 72 자)이 모든 처리를 마친 뒤 보고
    없이 rc 1 이었다(배포 판 752fa2b 은 됐다). 임시 이름은 산출 이름 길이와 무관하게 짧다.

usage: test_staged_write.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples", "apply_carryover_plan")
FAILS, OKS = [], []
TMP = ""


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:500]))
    print("  %-72s %s" % (name[:72], "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args, timeout=600):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(text)


def load(path):
    """보고 JSON — 없으면 None, 못 읽으면(깨진 JSON · 깨진 UTF-8) 그 까닭 글."""
    if not os.path.exists(path):
        return None
    try:
        return json.loads(open(path, "rb").read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 — 시험이 그 까닭을 보인다
        return "BAD " + str(e)


def tmp_left(d):
    """임시 파일(`.kr_tmp_`) — 폴더 아래 전부."""
    return sorted(os.path.relpath(os.path.join(w, n), d) for w, _, ns in os.walk(d) for n in ns if ".kr_tmp_" in n)


def shell_deck(nx=4, ny=2):
    """셸 파트 둘(왼쪽 반 1 · 오른쪽 반 2)."""
    L = ["*KEYWORD", "*NODE"]
    nid = lambda i, j: 1 + i + j * (nx + 1)  # noqa: E731
    for j in range(ny + 1):
        for i in range(nx + 1):
            L.append("%8d%16.6f%16.6f%16.6f" % (nid(i, j), float(i), float(j), 0.0))
    L.append("*ELEMENT_SHELL")
    e = 0
    for j in range(ny):
        for i in range(nx):
            e += 1
            L.append("%8d%8d%8d%8d%8d%8d" % (e, 1 if i < nx // 2 else 2, nid(i, j), nid(i + 1, j), nid(i + 1, j + 1), nid(i, j + 1)))
    for p in (1, 2):
        L += ["*PART", "part %d" % p, "%10d%10d%10d" % (p, 1, 1)]
    L += ["*SECTION_SHELL", "%10d%10d" % (1, 2), "%10s" % "1.0",
          "*MAT_ELASTIC", "%10d%10s%10s%10s" % (1, "7.85E-9", "210000.", "0.3"), "*END"]
    return "\n".join(L) + "\n"


def ep_dir(name, deck=None):
    d = os.path.join(TMP, name)
    os.makedirs(d)
    write(os.path.join(d, "in.k"), deck or shell_deck())
    return d


def ep(binary, d, output="out.k", report="r.json", extra=""):
    """extract-parts — 파트 1 을 뽑는다."""
    y = "model: in.k\noutput: %s\nparts: [1]\n" % output + ("report: %s\n" % report if report else "") + extra
    write(os.path.join(d, "e.yaml"), y)
    rc, out = run(binary, d, "extract-parts", "e.yaml")
    return rc, out, (load(os.path.join(d, report)) if report else None)


def co_dir(name):
    d = os.path.join(TMP, name)
    shutil.copytree(EX, d)
    return d


def co(binary, d, output="deck_applied", report=None):
    """apply_carryover_plan — 진리값 판(examples/apply_carryover_plan)을 그대로 적용한다."""
    y = "model: deck.k\nplan: plan.json\noutput: %s\n" % output + ("report: %s\n" % report if report else "")
    write(os.path.join(d, "a.yaml"), y)
    rc, out = run(binary, d, "apply_carryover_plan", "a.yaml")
    rp = report or (output[:-2] if output.endswith(".k") else output) + "_carryover.json"
    return rc, out, load(os.path.join(d, rp))


def ok_report(rep):
    return isinstance(rep, dict) and rep.get("ok") is True and rep.get("output_written") is True


# ── E 긴 이름 ────────────────────────────────────────────────────────────────
def sec_e(binary):
    print("[E] 긴 이름 — 임시 이름은 산출 이름 길이와 무관하게 짧다(배포 판처럼 NAME_MAX 가까운 이름이 된다)")
    for tag, stem in (("ASCII 236", "a" * 234), ("한글 72 자", "가" * 72)):
        nm = stem + ".k"
        d = ep_dir("E_ep_" + tag.split()[0])
        rc, out, rep = ep(binary, d, output=nm, extra="renumber: true\n")
        mp = stem + "_renumber_map.json"
        check("E-1 extract-parts 산출 %s 바이트(%s) · 번호 지도 %d 바이트 — rc 0 · 보고 ok" % (len(nm.encode()), tag, len(mp.encode())),
              rc == 0 and ok_report(rep) and os.path.exists(os.path.join(d, nm)) and os.path.exists(os.path.join(d, mp)) and not tmp_left(d),
              (rc, rep if not isinstance(rep, dict) else (rep.get("ok"), rep.get("refusals")), out[-400:]))
        d = ep_dir("E_epr_" + tag.split()[0])
        rn = stem + ".json"
        rc, out, rep = ep(binary, d, report=rn)
        check("E-2 extract-parts 보고 %d 바이트(%s) — rc 0 · 보고가 있다" % (len(rn.encode()), tag),
              rc == 0 and ok_report(rep) and not tmp_left(d), (rc, out[-400:]))
        d = co_dir("E_co_" + tag.split()[0])
        rc, out, rep = co(binary, d, output=stem)
        check("E-3 apply_carryover_plan 산출 %d · 기본 보고 %d 바이트(%s) — rc 0 · 보고 ok" %
              (len((stem + ".k").encode()), len((stem + "_carryover.json").encode()), tag),
              rc == 0 and ok_report(rep) and os.path.exists(os.path.join(d, stem + ".k")) and not tmp_left(d),
              (rc, out[-400:]))
    # 파일 시스템이 받지 않는 이름(256 바이트 넘게) — 실패는 그대로지만 보고 자리가 쓸 수 있으면 보고가 남는다
    d = ep_dir("E_toolong")
    rc, out, rep = ep(binary, d, output="b" * 300 + ".k")
    check("E-4 extract-parts 산출 302 바이트(받지 않는 이름) — rc 1 · 보고 ok false · output_written false · 임시 파일 없음",
          rc == 1 and isinstance(rep, dict) and rep.get("ok") is False and rep.get("output_written") is False and not tmp_left(d),
          (rc, rep, out[-300:]))
    d = co_dir("E_co_toolong")
    rc, out, rep = co(binary, d, output="c" * 300, report="r.json")
    check("E-5 apply_carryover_plan 산출 302 바이트 · 보고 r.json — rc 1 · 보고 ok false · 임시 파일 없음",
          rc == 1 and isinstance(rep, dict) and rep.get("ok") is False and rep.get("output_written") is False and not tmp_left(d),
          (rc, rep if not isinstance(rep, dict) else rep.get("problems"), out[-300:]))


def main():
    global TMP
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    TMP = tempfile.mkdtemp(prefix="koorm_staged_")
    try:
        sec_e(binary)
    finally:
        for w, ds, _ in os.walk(TMP):   # 읽기 전용으로 둔 폴더도 지운다
            for x in ds:
                try:
                    os.chmod(os.path.join(w, x), 0o755)
                except OSError:
                    pass
        shutil.rmtree(TMP, ignore_errors=True)
    print("")
    if FAILS:
        print("FAIL %d / %d" % (len(FAILS), len(FAILS) + len(OKS)))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
