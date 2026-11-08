#!/usr/bin/env python3
# 임시 파일 + 바꿔 넣기(공용 staged_write — extract-parts · apply_carryover_plan)가 이름 길이 · 죽은 실행 · 산출 자리 꼴 · 바꿔 넣기 차례 · 말 · 글자를 지키는지 보는 회귀 시험
"""공용 도우미 `staged_write`(include/util/StagedWrite.h) — 두 op 의 쓰기 규칙 (2026-11-08).

왜 이 시험이 있나.

  extract-parts(a33af2f) · apply_carryover_plan(0895025)은 산출 · 곁 파일 · 보고를 임시 파일에 쓰고 끝까지 지나면 바꿔 넣는다. 두 리뷰
  (3차 검토 · 판 2 적대적 검토)가 그 사본에서 결함을 찾았다. 이 시험은 그 자리마다 실제로 돌려 본다.

무엇을 보나.
  E 긴 이름 — 임시 이름이 산출 이름에 30 글자를 더해 NAME_MAX 가까운 이름(ASCII 236 바이트 · 한글 72 자)이 모든 처리를 마친 뒤 보고
    없이 rc 1 이었다(배포 판 752fa2b 은 됐다). 임시 이름은 산출 이름 길이와 무관하게 짧다.
  K 죽은 실행 — SIGTERM · SIGINT · SIGHUP 을 받은 실행이 1.7–32 MB 의 임시 파일을 남겼고(플랫폼 취소는 SIGTERM, 시간 초과는 SIGKILL)
    다시 돌려도 아무도 치우지 않았다. 이제 신호를 받으면 이번 실행의 임시 파일을 지우고 그 신호로 끝나며, SIGKILL 이 남긴 것은 다음
    실행이 주인 프로세스가 없을 때만 지운다(산 프로세스 · 다른 산출의 것은 그대로). 실행 가운데 멈추는 자리는 임시 파일이 보일 때
    SIGSTOP 으로 잡는다(멈춘 뒤 다시 보고 · 이미 끝났으면 다시 돌린다).

usage: test_staged_write.py <KooRemapper 바이너리>
"""
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

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


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else None


BIG = ""


def big_deck():
    """임시 파일이 0.3 초 넘게 있는 크기(셸 36 만 · 38 MB) — 한 번 짓고 링크로 쓴다."""
    global BIG
    if not BIG:
        BIG = os.path.join(TMP, "big.k")
        write(BIG, shell_deck(600, 600))
    return BIG


def ep_big_dir(name):
    d = os.path.join(TMP, name)
    os.makedirs(d)
    os.symlink(big_deck(), os.path.join(d, "in.k"))
    write(os.path.join(d, "e.yaml"), "model: in.k\noutput: out.k\nparts: [1]\nrenumber: true\nreport: r.json\n")
    return d


def start(binary, d, *args):
    return subprocess.Popen([binary, *args], cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop_when_staged(binary, d, args, tries=40):
    """실행을 띄우고 임시 파일이 보이면 SIGSTOP — 멈춘 뒤에도 임시 파일이 있어야 한다(아니면 끝까지 돌리고 다시). 멈춘 Popen 을 돌려준다."""
    for _ in range(tries):
        p = start(binary, d, *args)
        while p.poll() is None:
            if tmp_left(d):
                os.kill(p.pid, signal.SIGSTOP)
                if tmp_left(d):
                    return p
                os.kill(p.pid, signal.SIGCONT)
                break
        p.wait()
    return None


def finish(p, sig=None):
    if sig is not None:
        os.kill(p.pid, sig)
    if sig != signal.SIGKILL:
        os.kill(p.pid, signal.SIGCONT)
    return p.wait(timeout=120)


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


# ── K 죽은 실행 ──────────────────────────────────────────────────────────────
EP_ARGS = ("extract-parts", "e.yaml")
CO_ARGS = ("apply_carryover_plan", "a.yaml")
EP_FILES = ("out.k", "out_renumber_map.json", "r.json")
CO_FILES = ("deck_applied.k", "deck_applied_carryover.json")


def co_ready(name):
    d = co_dir(name)
    write(os.path.join(d, "a.yaml"), "model: deck.k\nplan: plan.json\noutput: deck_applied\n")
    return d


def sec_k(binary):
    print("[K] 죽은 실행 — 신호를 받으면 이번 임시 파일을 지우고 그 신호로 끝난다 · SIGKILL 이 남긴 것은 다음 실행이 치운다")
    for op, mk, args, files in (("extract-parts", ep_big_dir, EP_ARGS, EP_FILES), ("apply_carryover_plan", co_ready, CO_ARGS, CO_FILES)):
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            d = mk("K1_%s_%s" % (op, sig.name))
            rc0, out0 = run(binary, d, *args)
            before = {f: sha(os.path.join(d, f)) for f in files}
            p = stop_when_staged(binary, d, args)
            if p is None:
                check("K-1 %s %s — 실행 가운데 멈추지 못했다(임시 파일이 보이기 전에 끝났다)" % (op, sig.name), False, out0[-200:])
                continue
            seen = tmp_left(d)
            rc = finish(p, sig)
            after = {f: sha(os.path.join(d, f)) for f in files}
            check("K-1 %s %s 가운데 — rc -%d · 임시 파일 %d 개를 지웠다 · 앞 실행의 파일 그대로" % (op, sig.name, sig, len(seen)),
                  rc0 == 0 and rc == -sig and not tmp_left(d) and after == before and all(before.values()),
                  (rc0, rc, seen, tmp_left(d), after == before))
        # SIGKILL — 잡을 수 없다. 남은 것을 다음 실행이 지운다
        d = mk("K3_%s" % op)
        p = stop_when_staged(binary, d, args)
        if p is None:
            check("K-3 %s SIGKILL — 실행 가운데 멈추지 못했다" % op, False)
            continue
        finish(p, signal.SIGKILL)
        left = tmp_left(d)
        rc, out = run(binary, d, *args)
        check("K-3 %s SIGKILL 이 남긴 임시 파일 %d 개를 다음 실행이 지운다(rc 0 · 지웠다는 말)" % (op, len(left)),
              left and rc == 0 and not tmp_left(d) and "주인 프로세스가 없다" in out, (left, rc, tmp_left(d), out[-300:]))
        # 산 프로세스의 임시 파일 — 멈춰 둔 실행 A 옆에서 B 가 같은 산출로 끝까지 돈다
        d = mk("K4_%s" % op)
        a = stop_when_staged(binary, d, args)
        if a is None:
            check("K-4 %s — 실행 가운데 멈추지 못했다" % op, False)
            continue
        held = tmp_left(d)
        rc_b, out_b = run(binary, d, *args)
        kept = all(os.path.exists(os.path.join(d, t)) for t in held)
        rc_a = finish(a)
        check("K-4 %s 멈춘(산) 실행의 임시 파일 %d 개는 다른 실행이 지우지 않는다 — 둘 다 rc 0 · 끝나면 임시 파일 없음" % (op, len(held)),
              held and kept and rc_b == 0 and rc_a == 0 and not tmp_left(d), (held, kept, rc_b, rc_a, tmp_left(d), out_b[-300:]))
    # 다른 산출의 주인 없는 임시 파일은 그대로 — 그 산출을 다시 돌릴 때 지운다
    d = ep_big_dir("K5")
    write(os.path.join(d, "o.yaml"), "model: in.k\noutput: other.k\nparts: [2]\n")
    p = stop_when_staged(binary, d, ("extract-parts", "o.yaml"))
    if p is None:
        check("K-5 — 실행 가운데 멈추지 못했다", False)
        return
    finish(p, signal.SIGKILL)
    left = tmp_left(d)
    rc1, _ = run(binary, d, *EP_ARGS)
    kept = left and all(os.path.exists(os.path.join(d, t)) for t in left)
    rc2, _ = run(binary, d, "extract-parts", "o.yaml")
    check("K-5 out.k 실행은 other.k 의 주인 없는 임시 파일을 두고 · other.k 실행이 지운다",
          rc1 == 0 and kept and rc2 == 0 and not tmp_left(d), (left, rc1, kept, rc2, tmp_left(d)))


def main():
    global TMP
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    TMP = tempfile.mkdtemp(prefix="koorm_staged_")
    try:
        sec_e(binary)
        sec_k(binary)
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
