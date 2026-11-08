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
    실행이 주인 프로세스가 없을 때만 지운다(산 프로세스 · 다른 산출의 것은 그대로 · 지웠다는 [INFO] 는 수만 — 여섯째 검토 때까지 임시
    이름을 셋까지 찍었다). 실행 가운데 멈추는 자리는 임시 파일이 보일 때 SIGSTOP 으로 잡는다(멈춘 뒤 다시 보고 · 이미 끝났으면 다시
    돌린다).
  O 산출 자리 꼴 — 배포 판은 산출 자리에 제자리로 썼다. 임시 파일 + 이름 바꾸기가 그 꼴들을 바꿨다: 심볼릭 링크가 일반 파일로 바뀌고 ·
    모드가 0644 로 돌아가고 · `/dev/null`(보고만 보는 마른 실행) · FIFO · 읽기 전용 폴더의 쓸 수 있는 파일을 거절했다. 링크는 따라간
    파일 옆에서 바꿔 넣고(링크 그대로) · 권한 비트를 잇고 · 장치 · FIFO 는 바로 쓰고 · 읽기 전용 폴더면 [WARN] 와 함께 바꿔 넣을 때
    제자리로 쓴다(거절 · 실패면 그 파일 그대로). 하드 링크는 새 파일로 바뀐다(다른 이름은 앞 내용) · 읽기 전용 파일은 앞 판처럼 거절.
  C 바꿔 넣기 차례 — 산출을 바꿔 넣은 뒤 번호 지도가 실패하면 rc 1 · 새 산출 · 앞 번호 지도 · 앞 보고(앞 실행을 말한다)가 남았다.
    보고는 늘 마지막이고 실제로 바꿔 넣은 것을 말한다(뒤가 실패하면 그 상태로 다시 쓴다). 같은 산출을 쓰는 동시 실행은 잠금
    `.kr_tmp_lock_<이름 해시>`(flock)로 바꿔 넣기가 겹치지 않는다 — 이 시험이 그 잠금을 쥐고 실행이 기다리는지 본다(이름 해시는
    FNV-1a 64 의 아래 32 비트 — 도우미의 정의를 여기서 다시 센다).
  M 말 — 쓰기 관문의 말(long 덱은 `.k` 없는 접두)과 되읽기 예외가 임시 이름을 콘솔 · 보고에 실었다. 멈춘 사이 임시 덱을 못 읽게
    (chmod 000) 해 그 실패를 일으키고 콘솔 · 보고 어디에도 `.kr_tmp_` 가 없고 제 이름이 있는지 본다.
  U 보고 글자 — extract-parts 보고는 덱 · 경로의 깨진 바이트(CP949 로 쓴 `*INCLUDE` 이름 · 모르는 키워드 · 모델 경로)를 그대로 실어
    엄격한 UTF-8 리더에서 읽히지 않았다(3차 검토 TJ_euckr). 이월 적용 보고(54ac559)와 같은 함수로 U+FFFD 를 싣는다.
  D 매달린 링크 — 링크 글을 `parent_path()/글` 의 낱말 정규화로 풀어, 폴더 링크를 지난 `S/../deck.k` 가 입력 덱이 되어 rc 0 으로 그것을
    덮었다(여섯째 검토 S3 — 모델 · 주 덱 · 보고 링크로 계획). 커널처럼 물리로 따라가고, 쓸 파일 관문이 그 물리 자리도 본다(두 쓸 파일이
    매달린 링크로 한 파일에 닿으면 거절).
  F 제자리 쓰기로 넘어간 뒤의 임시 파일 — 잡은 뒤 폴더가 읽기 전용이 되면 이름 바꾸기가 EACCES 라 그 파일에 제자리로 쓰는데, 같은 까닭으로
    임시 파일을 못 지워 꽉 찬 채 rc 0 · 말없이 남았다(여섯째 검토 S11). 이제 0 바이트로 비우고 [WARN] 로 말하며, 폴더에 쓸 수 있게 된
    다음 실행이 지운다.
  P 제자리로 옮겨 쓰다 멈춘 산출 — 읽기 전용 폴더(시스템 임시 폴더에 써 두었다가) · 이름 바꾸기를 막은 폴더 권한이면 바꿔 넣을 때 그
    파일에 제자리로 옮겨 쓴다. 그 사이 쓰기가 멈추면(크기 상한 · 디스크가 찼다) 그 파일은 잘렸는데 말은 「앞 파일은 그대로다」 · 보고는
    output_written false 뿐이었다(여섯째 검토). 이제 잘렸다고 말하고 보고가 output_damaged(extract-parts 칸 · 이월 적용 problems 갈래)로
    적는다. 이 시험이 잠금을 쥔 동안 실행이 다 써 두고 기다리게 하고, 그 사이 폴더 권한 · 크기 상한(prlimit — 산출 반)을 건다.
  T 임시 파일 이름 표지 — 플랫폼은 `.kr_tmp_` 가 든 파일만 산출로 올리지 않는다. map 의 앞처리 평판(`.__preproc_flat.k`) · 뒤집은 기준
    (`.__flipped_ref.k`) · 펼친 덱(`.kr_flat_`) · meshfix 의 gmsh 왕복(`__mf.*`) · polish(`__pol<회차>_<덩어리>.*`)는 표지가 없어 SIGKILL 된
    잡이 남기면 산출로 올라갔다(여섯째 검토 — runner 의 걸러내기). 이름에 표지를 붙였다 — strace 로 실행이 만들었다 지운 파일을 모아
    모두 `.kr_tmp_` 를 지녔는지 본다(strace 가 없으면 건너뛴다).
  W 쓰기 오류 — 쓰기 · 닫기 결과를 보지 않아 디스크가 차거나 파일 크기 상한(RLIMIT_FSIZE · SIGXFSZ 무시 — ENOSPC · EDQUOT 의
    대역)에 걸려 잘린 덱을 rc 0 · ok 로 바꿔 넣었다(여섯째 검토 S2 — extract-parts 는 `*NODE` 가운데서 끊긴 덱 · 이월 적용은 마지막
    새 섹션을 잃은 덱). 이제 바꿔 넣지 않고 rc 1 · 보고가 그 오류를 말한다. 바로 쓰는 op(DeckWriter · writeOutput)도 rc 1.

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


def start(binary, d, *args, pipe=False):
    if pipe:   # 말을 모은다(짧은 말뿐이라 파이프가 차지 않는다)
        return subprocess.Popen([binary, *args], cwd=d, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace")
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
        # 지웠다는 말은 수만 — 임시 이름(.kr_tmp_…)은 찍지 않는다(여섯째 검토 — 예전엔 셋까지 찍었다)
        check("K-3 %s SIGKILL 이 남긴 임시 파일 %d 개를 다음 실행이 지운다(rc 0 · 지웠다는 말 · 임시 이름은 안 찍는다)" % (op, len(left)),
              left and rc == 0 and not tmp_left(d) and "주인 프로세스가 없다" in out and ".kr_tmp_" not in out,
              (left, rc, tmp_left(d), out[-300:]))
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
    # K-6 읽기 전용 폴더(제자리 쓰기 — 시스템 임시 폴더에 써 둔다)에서 SIGKILL 이 남긴 것도 다음 실행이 지운다
    if os.geteuid() != 0:
        d = ep_big_dir("K6")
        ro = os.path.join(d, "ro")
        os.makedirs(ro)
        write(os.path.join(ro, "out.k"), "old\n")
        os.chmod(ro, 0o555)
        write(os.path.join(d, "e6.yaml"), "model: in.k\noutput: ro/out.k\nparts: [1]\nreport: r.json\n")
        p = None
        for _ in range(20):
            q = start(binary, d, "extract-parts", "e6.yaml")
            while q.poll() is None:
                if sys_tmp_of(q.pid):
                    os.kill(q.pid, signal.SIGSTOP)
                    if sys_tmp_of(q.pid):
                        p = q
                        break
                    os.kill(q.pid, signal.SIGCONT)
                    break
            if p:
                break
            q.wait()
        if p is None:
            check("K-6 — 실행 가운데 멈추지 못했다", False)
        else:
            finish(p, signal.SIGKILL)
            left = sys_tmp_of(p.pid)
            rc, out = run(binary, d, "extract-parts", "e6.yaml")
            check("K-6 읽기 전용 폴더 · SIGKILL 이 시스템 임시 폴더에 남긴 %d 개를 다음 실행이 지운다 — rc 0 · 임시 이름은 안 찍는다" % len(left),
                  left and rc == 0 and not sys_tmp_of(p.pid) and is_new_deck(os.path.join(ro, "out.k")) and ".kr_tmp_" not in out,
                  (left, rc, out[-300:]))
        os.chmod(ro, 0o755)
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


# ── O 산출 자리 꼴 ───────────────────────────────────────────────────────────
def is_new_deck(path):
    try:
        return open(path, encoding="utf-8", errors="replace").read().startswith("*KEYWORD")
    except OSError:
        return False


def sys_tmp_of(pid):
    """시스템 임시 폴더(InPlace 의 자리)에 그 프로세스가 남긴 임시 파일."""
    td = tempfile.gettempdir()
    return [n for n in os.listdir(td) if n.startswith(".kr_tmp_") and "_%d_" % pid in n]


def sec_o(binary):
    import stat
    import threading
    print("[O] 산출 자리 꼴 — 링크 · 모드 · /dev/null · FIFO · 읽기 전용 폴더(배포 판이 되던 꼴)")
    # O-1 링크 산출 — 따라간 파일이 새것 · 링크 그대로
    for op in ("extract-parts", "apply_carryover_plan"):
        d = ep_dir("O1_" + op) if op == "extract-parts" else co_dir("O1_" + op)
        name = "out.k" if op == "extract-parts" else "deck_applied.k"
        os.makedirs(os.path.join(d, "real"))
        write(os.path.join(d, "real", "t.k"), "old\n")
        os.symlink("real/t.k", os.path.join(d, name))
        rc, out, rep = ep(binary, d) if op == "extract-parts" else co(binary, d)
        check("O-1 %s 링크 산출 — 링크 그대로 · 따라간 파일이 새 덱 · rc 0" % op,
              rc == 0 and os.path.islink(os.path.join(d, name)) and is_new_deck(os.path.join(d, "real", "t.k")) and not tmp_left(d),
              (rc, os.path.islink(os.path.join(d, name)), out[-300:]))
        # 매달린 링크 — 링크가 가리키는 자리에 만든다
        d = ep_dir("O1d_" + op) if op == "extract-parts" else co_dir("O1d_" + op)
        os.makedirs(os.path.join(d, "real"))
        os.symlink("real/new.k", os.path.join(d, name))
        rc, out, rep = ep(binary, d) if op == "extract-parts" else co(binary, d)
        check("O-2 %s 매달린 링크 — 링크가 가리키는 자리에 만든다 · 링크 그대로" % op,
              rc == 0 and os.path.islink(os.path.join(d, name)) and is_new_deck(os.path.join(d, "real", "new.k")) and not tmp_left(d),
              (rc, os.path.exists(os.path.join(d, "real", "new.k")), out[-300:]))
        # 모드 0640 을 잇는다 · 하드 링크는 새 파일로 바뀐다(다른 이름은 앞 내용 — 문서에 적은 그대로)
        d = ep_dir("O3_" + op) if op == "extract-parts" else co_dir("O3_" + op)
        p = os.path.join(d, name)
        write(p, "old\n")
        os.chmod(p, 0o640)
        os.link(p, os.path.join(d, "other.k"))
        rc, out, rep = ep(binary, d) if op == "extract-parts" else co(binary, d)
        st = os.stat(p)
        check("O-3 %s 있던 산출의 모드 0640 을 잇는다 · 하드 링크의 다른 이름은 앞 내용(바뀐다)" % op,
              rc == 0 and stat.S_IMODE(st.st_mode) == 0o640 and is_new_deck(p) and open(os.path.join(d, "other.k")).read() == "old\n",
              (rc, oct(stat.S_IMODE(st.st_mode)), out[-300:]))
        # 읽기 전용 파일 — 앞 판처럼 거절(이름 바꾸기로 덮지 않는다)
        d = ep_dir("O8_" + op) if op == "extract-parts" else co_dir("O8_" + op)
        p = os.path.join(d, name)
        write(p, "old\n")
        os.chmod(p, 0o444)
        rc, out, rep = ep(binary, d) if op == "extract-parts" else co(binary, d)
        check("O-8 %s 읽기 전용 산출 파일 — rc 1 · 그 파일 그대로 · 보고 output_written false" % op,
              rc == 1 and open(p).read() == "old\n" and isinstance(rep, dict) and rep.get("output_written") is False and not tmp_left(d),
              (rc, out[-300:]))
    # O-4 /dev/null — 보고만 보는 마른 실행(배포 판이 됐다) · 장치는 그대로
    for extra, tag in (("verify: false\n", "verify false"), ("", "verify true")):
        d = ep_dir("O4_" + tag.replace(" ", "_"))
        rc, out, rep = ep(binary, d, output="/dev/null", extra=extra)
        check("O-4 extract-parts output: /dev/null (%s) — rc 0 · 보고 ok · /dev/null 은 문자 장치 그대로" % tag,
              rc == 0 and ok_report(rep) and stat.S_ISCHR(os.lstat("/dev/null").st_mode) and not tmp_left(d), (rc, out[-300:]))
    d = co_dir("O4_co")
    rc, out, _ = co(binary, d, report="/dev/null")
    check("O-4 apply_carryover_plan report: /dev/null — rc 0 · 덱은 쓴다", rc == 0 and is_new_deck(os.path.join(d, "deck_applied.k")),
          (rc, out[-300:]))
    # O-5 FIFO 산출 — 읽는 쪽이 덱을 받고 FIFO 는 그대로(이름 바꾸기로 일반 파일이 되지 않는다)
    d = ep_dir("O5")
    fifo = os.path.join(d, "out.k")
    os.mkfifo(fifo)
    got = []

    def reader():
        with open(fifo, "rb") as f:
            got.append(f.read())
    t = threading.Thread(target=reader, daemon=True)
    t.start()
    rc, out, rep = ep(binary, d, extra="verify: false\n")
    t.join(10)
    if t.is_alive():   # 쓰는 쪽이 오지 않았다 — 읽는 쪽을 풀어 준다
        os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
    check("O-5 extract-parts FIFO 산출 — rc 0 · 읽는 쪽이 덱을 받았다 · FIFO 그대로",
          rc == 0 and got and got[0].startswith(b"*KEYWORD") and stat.S_ISFIFO(os.lstat(fifo).st_mode) and not tmp_left(d),
          (rc, len(got[0]) if got else None, out[-300:]))
    # O-6 읽기 전용 폴더의 쓸 수 있는 파일 — [WARN](원자적이 아님)와 함께 제자리로 · 시스템 임시 폴더에 남는 것 없음
    if os.geteuid() == 0:
        check("O-6 읽기 전용 폴더 — root 는 폴더 권한을 넘는다(건너뜀)", True)
        return
    d = ep_dir("O6")
    ro = os.path.join(d, "ro")
    os.makedirs(ro)
    for f in ("out.k", "r.json"):
        write(os.path.join(ro, f), "old\n")
    os.chmod(ro, 0o555)
    write(os.path.join(d, "e.yaml"), "model: in.k\noutput: ro/out.k\nparts: [1]\nreport: ro/r.json\n")
    p = subprocess.Popen([binary, "extract-parts", "e.yaml"], cwd=d, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace")
    out = p.communicate(timeout=300)[0]
    rep = load(os.path.join(ro, "r.json"))
    check("O-6 extract-parts 읽기 전용 폴더의 쓸 수 있는 산출 · 보고 — rc 0 · 둘 다 새것 · [WARN] 원자적이 아님 · 임시 폴더 깨끗",
          p.returncode == 0 and is_new_deck(os.path.join(ro, "out.k")) and ok_report(rep) and "[WARN]" in out and "원자적이 아니다" in out
          and not sys_tmp_of(p.pid), (p.returncode, sys_tmp_of(p.pid), out[-400:]))
    # 거절 · 실패면 그 파일 그대로(바꿔 넣을 때만 제자리로 쓴다)
    write(os.path.join(d, "bad.k"), shell_deck().replace("       1       1       1       2       7       6",
                                                          "       1       1       1       2       7     999"))
    os.chmod(ro, 0o755)
    write(os.path.join(ro, "out.k"), "old\n")
    os.chmod(ro, 0o555)
    write(os.path.join(d, "e2.yaml"), "model: bad.k\noutput: ro/out.k\nparts: [1]\nreport: ro/r.json\n")
    rc, out = run(binary, d, "extract-parts", "e2.yaml")
    rep = load(os.path.join(ro, "r.json"))
    check("O-7 읽기 전용 폴더 · 되읽기 실패 — rc 1 · 산출 파일은 앞 내용 그대로 · 보고 output_written false",
          rc == 1 and open(os.path.join(ro, "out.k")).read() == "old\n" and isinstance(rep, dict) and rep.get("output_written") is False,
          (rc, out[-300:]))
    os.chmod(ro, 0o755)
    d = co_dir("O6_co")
    ro = os.path.join(d, "ro")
    os.makedirs(ro)
    write(os.path.join(ro, "deck_applied.k"), "old\n")
    write(os.path.join(ro, "deck_applied_carryover.json"), "{}\n")
    os.chmod(ro, 0o555)
    rc, out, rep = co(binary, d, output="ro/deck_applied")
    check("O-6 apply_carryover_plan 읽기 전용 폴더의 쓸 수 있는 덱 · 보고 — rc 0 · 둘 다 새것 · [WARN] 원자적이 아님",
          rc == 0 and is_new_deck(os.path.join(ro, "deck_applied.k")) and ok_report(rep) and "원자적이 아니다" in out, (rc, out[-400:]))
    os.chmod(ro, 0o755)


# ── C 바꿔 넣기 차례 · 잠금 ─────────────────────────────────────────────────
def name_hash(base):
    """도우미의 이름 해시 — FNV-1a 64 의 아래 32 비트(16진 8 자리)."""
    h = 1469598103934665603
    for c in base.encode("utf-8"):
        h = ((h ^ c) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return "%08x" % (h & 0xFFFFFFFF)


def temp_of(d, base):
    """그 대상의 임시 파일 — 지금 꼴(이름 해시)과 옛 꼴(.<이름>.kr_tmp_) 둘 다."""
    h = name_hash(base)
    return [n for n in os.listdir(d) if (n.startswith(".kr_tmp_") and not n.startswith(".kr_tmp_lock_") and
                                         n.split(".")[1].endswith("_" + h)) or n.startswith("." + base + ".kr_tmp_")]


def stop_before_commit(binary, d, args, base, also=(), tries=40, pipe=False):
    """그 대상(과 `also` 의 대상)의 임시 파일이 다 보이면 SIGSTOP — 멈춘 뒤에도 있어야 한다(아직 바꿔 넣지 않았다)."""
    staged = lambda: temp_of(d, base) and all(temp_of(d, b) for b in also)  # noqa: E731
    for _ in range(tries):
        p = start(binary, d, *args, pipe=pipe)
        while p.poll() is None:
            if staged():
                os.kill(p.pid, signal.SIGSTOP)
                if staged():
                    return p
                os.kill(p.pid, signal.SIGCONT)
                break
        p.wait()
    return None


def first_shell_pid(path):
    sect = ""
    for ln in open(path, encoding="utf-8", errors="replace"):
        if ln.startswith("*"):
            sect = ln.strip()
        elif sect == "*ELEMENT_SHELL" and ln.strip() and not ln.startswith("$"):
            return int(ln[8:16])
    return None


def hold_lock(d, base):
    import fcntl
    fd = os.open(os.path.join(d, ".kr_tmp_lock_" + name_hash(base)), os.O_RDWR | os.O_CREAT, 0o666)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def sec_c(binary):
    print("[C] 바꿔 넣기 차례 — 보고는 늘 마지막이고 바꿔 넣은 것을 말한다 · 같은 산출의 동시 실행은 잠금으로 겹치지 않는다")
    # C-1 산출을 바꿔 넣은 뒤 번호 지도가 실패한다(멈춘 사이 그 자리를 폴더로) — 보고가 그 상태를 말한다
    d = ep_big_dir("C1")
    rc0, _ = run(binary, d, *EP_ARGS)
    write(os.path.join(d, "e2.yaml"), "model: in.k\noutput: out.k\nparts: [2]\nrenumber: true\nreport: r.json\n")
    p = stop_before_commit(binary, d, ("extract-parts", "e2.yaml"), "out.k", also=("out_renumber_map.json",))
    if p is None:
        check("C-1 — 바꿔 넣기 전에 멈추지 못했다", False)
    else:
        mp = os.path.join(d, "out_renumber_map.json")
        os.remove(mp)
        os.mkdir(mp)
        rc = finish(p)
        rep = load(os.path.join(d, "r.json"))
        ok = (rc0 == 0 and rc == 1 and isinstance(rep, dict) and rep.get("ok") is False and rep.get("output_written") is True and
              str(rep.get("output", "")).endswith("out.k") and rep.get("renumber", {}).get("map") is None and
              rep.get("parts_selected") == [2] and any(r.get("kind") == "commit" for r in rep.get("refusals", [])) and
              first_shell_pid(os.path.join(d, "out.k")) == 2 and not tmp_left(d))
        check("C-1 extract-parts 번호 지도 바꿔 넣기 실패 — rc 1 · 보고가 새 산출(parts [2]) · output_written true · map null · ok false",
              ok, (rc0, rc, rep if not isinstance(rep, dict) else {k: rep.get(k) for k in ("ok", "output_written", "parts_selected",
                                                                                            "renumber", "refusals")}, tmp_left(d)))
    # C-2 보고 자리의 폴더가 멈춘 사이 읽기 전용이 된다 — 그 파일에 제자리로 쓴다(앞 실행을 말하는 보고를 남기지 않는다)
    if os.geteuid() != 0:
        d = ep_big_dir("C2")
        os.makedirs(os.path.join(d, "rep"))
        write(os.path.join(d, "e.yaml"), "model: in.k\noutput: out.k\nparts: [1]\nrenumber: true\nreport: rep/r.json\n")
        rc0, _ = run(binary, d, *EP_ARGS)
        write(os.path.join(d, "e2.yaml"), "model: in.k\noutput: out.k\nparts: [2]\nrenumber: true\nreport: rep/r.json\n")
        p = stop_before_commit(binary, d, ("extract-parts", "e2.yaml"), "out.k")
        if p is None:
            check("C-2 — 바꿔 넣기 전에 멈추지 못했다", False)
        else:
            os.chmod(os.path.join(d, "rep"), 0o555)
            rc = finish(p)
            os.chmod(os.path.join(d, "rep"), 0o755)
            rep = load(os.path.join(d, "rep", "r.json"))
            check("C-2 extract-parts 보고 폴더가 읽기 전용이 됐다 — rc 0 · 보고가 이번 실행(parts [2]) · 임시 파일 없음",
                  rc0 == 0 and rc == 0 and ok_report(rep) and rep.get("parts_selected") == [2] and not tmp_left(d),
                  (rc0, rc, rep if not isinstance(rep, dict) else rep.get("parts_selected")))
    # C-3 산출 바꿔 넣기가 실패한다(멈춘 사이 그 자리를 폴더로) — 보고 ok false · output_written false
    d = ep_big_dir("C3")
    run(binary, d, *EP_ARGS)
    p = stop_before_commit(binary, d, EP_ARGS, "out.k")
    if p is None:
        check("C-3 — 바꿔 넣기 전에 멈추지 못했다", False)
    else:
        os.remove(os.path.join(d, "out.k"))
        os.mkdir(os.path.join(d, "out.k"))
        rc = finish(p)
        rep = load(os.path.join(d, "r.json"))
        check("C-3 extract-parts 산출 바꿔 넣기 실패 — rc 1 · 보고 ok false · output_written false · map null · 임시 파일 없음",
              rc == 1 and isinstance(rep, dict) and rep.get("ok") is False and rep.get("output_written") is False and
              rep.get("renumber", {}).get("map") is None and not tmp_left(d), (rc, rep if not isinstance(rep, dict) else rep.get("refusals")))
    # C-4 · C-5 이월 적용 — 덱 바꿔 넣기 실패 · 보고 폴더가 읽기 전용이 됐다
    d = co_ready("C4")
    run(binary, d, *CO_ARGS)
    p = stop_before_commit(binary, d, CO_ARGS, "deck_applied.k")
    if p is None:
        check("C-4 — 바꿔 넣기 전에 멈추지 못했다", False)
    else:
        os.remove(os.path.join(d, "deck_applied.k"))
        os.mkdir(os.path.join(d, "deck_applied.k"))
        rc = finish(p)
        rep = load(os.path.join(d, "deck_applied_carryover.json"))
        check("C-4 apply_carryover_plan 덱 바꿔 넣기 실패 — rc 1 · 보고 ok false · output_written false",
              rc == 1 and isinstance(rep, dict) and rep.get("ok") is False and rep.get("output_written") is False and not tmp_left(d),
              (rc, rep if not isinstance(rep, dict) else rep.get("problems")))
    if os.geteuid() != 0:
        d = co_dir("C5")
        os.makedirs(os.path.join(d, "rep"))
        args = ("apply_carryover_plan", "a.yaml")
        write(os.path.join(d, "a.yaml"), "model: deck.k\nplan: plan.json\noutput: deck_applied\nreport: rep/r.json\n")
        write(os.path.join(d, "rep", "r.json"), "{\"old\": true}\n")
        p = stop_before_commit(binary, d, args, "deck_applied.k")
        if p is None:
            check("C-5 — 바꿔 넣기 전에 멈추지 못했다", False)
        else:
            os.chmod(os.path.join(d, "rep"), 0o555)
            rc = finish(p)
            os.chmod(os.path.join(d, "rep"), 0o755)
            rep = load(os.path.join(d, "rep", "r.json"))
            check("C-5 apply_carryover_plan 보고 폴더가 읽기 전용이 됐다 — rc 0 · 보고가 이번 실행(ok · output_written)",
                  rc == 0 and ok_report(rep) and "old" not in rep and not tmp_left(d), (rc, rep))
    # C-6 · C-7 잠금 — 이 시험이 잠금을 쥔 동안 실행은 바꿔 넣지 않고 기다린다 · 풀면 끝나고 잠금 파일을 지운다
    for op, mk, args, out_name in (("extract-parts", ep_big_dir, EP_ARGS, "out.k"),
                                   ("apply_carryover_plan", co_ready, CO_ARGS, "deck_applied.k")):
        d = mk("C6_" + op)
        run(binary, d, *args)
        before = sha(os.path.join(d, out_name))
        fd = hold_lock(d, out_name)
        p = start(binary, d, *args)
        t0 = time.time()
        while p.poll() is None and time.time() - t0 < 20 and not [n for n in tmp_left(d) if not n.startswith(".kr_tmp_lock_")]:
            time.sleep(0.01)
        time.sleep(1.0)   # 기다리는 실행이면 이 사이 바꿔 넣지 않는다
        waited = p.poll() is None and sha(os.path.join(d, out_name)) == before
        os.close(fd)      # 푼다
        rc = p.wait(timeout=120)
        check("C-%d %s 잠금을 쥔 동안 기다리고(산출 그대로) 풀면 rc 0 · 잠금 파일을 지운다" % (6 if op == "extract-parts" else 7, op),
              waited and rc == 0 and not os.path.exists(os.path.join(d, ".kr_tmp_lock_" + name_hash(out_name))) and not tmp_left(d),
              (waited, rc, tmp_left(d)))
    # C-8 죽은 실행이 남긴(쥐는 이 없는) 잠금 파일은 막지 않는다 — 쓰고 지운다
    d = ep_dir("C8")
    lock = os.path.join(d, ".kr_tmp_lock_" + name_hash("out.k"))
    write(lock, "")
    rc, out, rep = ep(binary, d)
    check("C-8 쥐는 이 없는 잠금 파일 — rc 0 · 보고 ok · 잠금 파일 지움", rc == 0 and ok_report(rep) and not os.path.exists(lock), (rc, out[-200:]))
    # C-10 · C-11 거절 보고도 잠금을 쥐고 쓴다 — 이 시험이 쥔 동안 거절하는 실행은 보고를 쓰지 않고 기다린다
    for k, op, mk, args, out_name, rep_name in ((10, "extract-parts", ep_dir, ("extract-parts", "x.yaml"), "out.k", "r.json"),
                                                (11, "apply_carryover_plan", co_dir, ("apply_carryover_plan", "x.yaml"), "deck_applied.k",
                                                 "deck_applied_carryover.json")):
        d = mk("C%d" % k)
        if op == "extract-parts":
            write(os.path.join(d, "x.yaml"), "model: in.k\noutput: out.k\nparts: [77]\nreport: r.json\n")   # 덱에 없는 PID — 거절
        else:
            write(os.path.join(d, "x.yaml"), "model: deck.k\nplan: missing.json\noutput: deck_applied\n")   # 없는 계획 — 거절
        fd = hold_lock(d, out_name)
        p = start(binary, d, *args)
        time.sleep(1.5)
        waited = p.poll() is None and not os.path.exists(os.path.join(d, rep_name))
        os.close(fd)
        rc = p.wait(timeout=120)
        rep = load(os.path.join(d, rep_name))
        check("C-%d %s 거절 보고 — 잠금을 쥔 동안 쓰지 않고 기다리고 풀면 rc 1 · 보고 ok false" % (k, op),
              waited and rc == 1 and isinstance(rep, dict) and rep.get("ok") is False and not tmp_left(d), (waited, rc, rep))
    # C-9 잠금 이름에 심어 둔 심볼릭 링크는 따라가지 않는다(O_NOFOLLOW — 예전엔 링크가 가리키는 자리에 빈 파일을 만들었다)
    d = ep_dir("C9")
    os.symlink("victim.txt", os.path.join(d, ".kr_tmp_lock_" + name_hash("out.k")))
    rc, out, rep = ep(binary, d)
    check("C-9 잠금 이름이 심볼릭 링크 — 따라가지 않는다(victim.txt 없음) · [WARN] · rc 0 · 보고 ok",
          rc == 0 and ok_report(rep) and not os.path.exists(os.path.join(d, "victim.txt")) and "심볼릭 링크" in out,
          (rc, sorted(os.listdir(d)), out[-300:]))


# ── M 말 ─────────────────────────────────────────────────────────────────────
def sec_m(binary):
    print("[M] 말 — 콘솔 · 보고에 임시 이름(.kr_tmp_)이 새지 않는다")
    if os.geteuid() == 0:
        check("M — root 는 파일 권한을 넘는다(건너뜀)", True)
        return
    # M-1 이월 적용 — 멈춘 사이 임시 덱을 못 읽게 한다(쓰기 관문의 열기 실패 또는 되읽기 예외 — 둘 다 임시 경로를 말한다)
    got = None
    for k in range(10):
        d = co_ready("M1_%d" % k)
        p = start(binary, d, *CO_ARGS, pipe=True)
        hit = False
        while p.poll() is None:
            t = temp_of(d, "deck_applied.k")
            if t:
                os.kill(p.pid, signal.SIGSTOP)
                t = temp_of(d, "deck_applied.k")
                if t:
                    os.chmod(os.path.join(d, t[0]), 0)
                    hit = True
                os.kill(p.pid, signal.SIGCONT)
                break
        out = p.communicate(timeout=120)[0]
        if hit and p.returncode == 1:
            got = (d, out)
            break
    if got is None:
        check("M-1 — 임시 덱을 못 읽게 한 실패를 일으키지 못했다", False)
    else:
        d, out = got
        text = open(os.path.join(d, "deck_applied_carryover.json"), encoding="utf-8").read()
        rep = json.loads(text)
        said = " ".join(p["detail"] for p in rep.get("problems", []))
        check("M-1 apply_carryover_plan 임시 덱을 못 읽는 실패 — 콘솔 · 보고에 .kr_tmp_ 없음 · 제 이름(deck_applied.k)을 말한다",
              ".kr_tmp_" not in out and ".kr_tmp_" not in text and "deck_applied.k" in said and rep.get("output_written") is False,
              ([l for l in out.splitlines() if ".kr_tmp_" in l][:2], said[:300]))
    # M-2 extract-parts — 바꿔 넣기 실패(멈춘 사이 산출 자리를 폴더로) · 앞서 거절(번호 지도 자리를 폴더로)
    for tag, prep in (("산출 자리가 폴더", lambda d: (os.remove(os.path.join(d, "out.k")), os.mkdir(os.path.join(d, "out.k")))),
                      ("번호 지도 자리가 폴더", lambda d: (os.remove(os.path.join(d, "out_renumber_map.json")),
                                                     os.mkdir(os.path.join(d, "out_renumber_map.json"))))):
        d = ep_big_dir("M2_" + tag.split()[0])
        run(binary, d, *EP_ARGS)
        p = stop_before_commit(binary, d, EP_ARGS, "out.k", also=("out_renumber_map.json",), pipe=True)
        if p is None:
            check("M-2 — 바꿔 넣기 전에 멈추지 못했다", False)
            continue
        prep(d)
        os.kill(p.pid, signal.SIGCONT)
        out1 = p.communicate(timeout=120)[0]
        text1 = open(os.path.join(d, "r.json"), encoding="utf-8").read()
        rc, out2 = run(binary, d, *EP_ARGS)   # 같은 자리로 한 번 더(쓰기 전에 거절하는 길)
        text2 = open(os.path.join(d, "r.json"), encoding="utf-8").read()
        said = out1 + out2 + text1 + text2
        check("M-2 extract-parts %s — 바꿔 넣기 실패 · 다음 실행 거절 모두 rc 1 · 콘솔 · 보고에 .kr_tmp_ 없음" % tag,
              p.returncode == 1 and rc == 1 and ".kr_tmp_" not in said, (p.returncode, rc, [l for l in said.splitlines() if ".kr_tmp_" in l][:2]))


# ── U 보고 글자 ──────────────────────────────────────────────────────────────
def strict_report(path):
    """엄격한 UTF-8 로 읽은 보고 — 못 읽으면 None."""
    try:
        return json.loads(open(path, "rb").read().decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, ValueError):
        return None


def sec_u(binary):
    print("[U] 보고 글자 — extract-parts 보고는 깨진 바이트 대신 U+FFFD 를 싣는다(늘 바른 UTF-8)")
    cp949 = "한글".encode("cp949")
    # U-1 CP949 로 쓴 *INCLUDE 이름(없는 파일) — 인클루드 거절의 목록 줄
    d = ep_dir("U1")
    with open(os.path.join(d, "m.k"), "wb") as f:
        f.write(b"*KEYWORD\n*INCLUDE\nin.k\n*INCLUDE\n" + cp949 + b".k\n*END\n")
    write(os.path.join(d, "e.yaml"), "model: m.k\noutput: out.k\nparts: [1]\nreport: r.json\n")
    rc, out = run(binary, d, "extract-parts", "e.yaml")
    rep = strict_report(os.path.join(d, "r.json"))
    line = " ".join(" ".join(r.get("lines", [])) for r in rep.get("refusals", [])) if rep else ""
    check("U-1 CP949 *INCLUDE 이름 — rc 1 · 보고가 바른 UTF-8 · 그 줄에 U+FFFD · 거절 include",
          rc == 1 and rep is not None and "�" in line and ".k" in line and rep["refusals"][0]["kind"] == "include", (rc, line[:200]))
    # U-2 깨진 바이트의 모르는 키워드(버리고 dropped_keywords 에 센다) · U-3 CP949 이름의 모델
    d = ep_dir("U2", deck=shell_deck().replace("*END\n", ""))
    with open(os.path.join(d, "in.k"), "ab") as f:
        # 키워드 줄은 1열 `*` 다음이 글자다(리더 `KFileReader::isKeywordLine` 규칙 · 01ef094) — `*` 바로 뒤가 깨진 바이트면 키워드가 아니라
        # 앞 블록의 데이터다. 깨진 바이트는 이름 가운데에 둔다
        f.write(b"*K" + cp949 + b"_CARD\n        1\n*END\n")
    rc, out, _ = ep(binary, d)
    rep = strict_report(os.path.join(d, "r.json"))
    keys = list((rep or {}).get("dropped_keywords", {}))
    check("U-2 깨진 바이트의 모르는 키워드 — rc 0 · 보고가 바른 UTF-8 · dropped_keywords 에 U+FFFD 꼴로",
          rc == 0 and rep is not None and any("�" in k for k in keys), (rc, keys))
    d = os.path.join(TMP, "U3")
    os.makedirs(d)
    model = cp949 + b"_model.k"
    with open(os.path.join(d.encode(), model), "wb") as f:
        f.write(shell_deck().encode())
    with open(os.path.join(d, "e.yaml"), "wb") as f:
        f.write(b"model: " + model + b"\noutput: out.k\nparts: [1]\nreport: r.json\n")
    rc, out = run(binary, d, "extract-parts", "e.yaml")
    rep = strict_report(os.path.join(d, "r.json"))
    check("U-3 CP949 이름의 모델 — rc 0 · 보고가 바른 UTF-8 · model 에 U+FFFD",
          rc == 0 and rep is not None and "�" in rep.get("model", "") and rep.get("ok") is True, (rc, (rep or {}).get("model")))


# ── D 매달린 링크 — 물리로 ────────────────────────────────────────────────────
def dotdot(d, link_name, target):
    """L → real/sub · real/sub/<link_name> → <target>(물리 자리는 real/ 안 · 낱말 풀이는 d 바로 아래)."""
    os.makedirs(os.path.join(d, "real", "sub"))
    os.symlink("real/sub", os.path.join(d, "L"))
    os.symlink(target, os.path.join(d, "real", "sub", link_name))


def sec_d(binary):
    print("[D] 매달린 링크 — 커널처럼 물리로 따라간다 · 쓸 파일 관문이 그 자리도 본다")
    d = ep_dir("D1")
    dotdot(d, "out.k", "../in.k")
    before = sha(os.path.join(d, "in.k"))
    rc, out, rep = ep(binary, d, output="L/out.k")
    check("D-1 extract-parts 산출 L/out.k → ../in.k(물리 real/in.k) — rc 0 · 모델 in.k 그대로 · real/in.k 가 새 덱 · 링크 그대로",
          rc == 0 and sha(os.path.join(d, "in.k")) == before and is_new_deck(os.path.join(d, "real", "in.k")) and
          os.path.islink(os.path.join(d, "real", "sub", "out.k")), (rc, out[-300:]))
    d = co_dir("D2")
    dotdot(d, "x.k", "../deck.k")
    before = sha(os.path.join(d, "deck.k"))
    rc, out, rep = co(binary, d, output="L/x", report="rep.json")
    check("D-2 apply_carryover_plan 산출 L/x.k → ../deck.k(물리 real/deck.k) — rc 0 · 주 덱 그대로 · real/deck.k 가 새 덱",
          rc == 0 and sha(os.path.join(d, "deck.k")) == before and is_new_deck(os.path.join(d, "real", "deck.k")), (rc, out[-300:]))
    d = co_dir("D3")
    dotdot(d, "rep.json", "../plan.json")
    before = sha(os.path.join(d, "plan.json"))
    rc, out, rep = co(binary, d, report="L/rep.json")
    got = load(os.path.join(d, "real", "plan.json"))
    check("D-3 apply_carryover_plan 보고 L/rep.json → ../plan.json(물리 real/plan.json) — rc 0 · 계획 그대로 · 보고는 real/plan.json",
          rc == 0 and sha(os.path.join(d, "plan.json")) == before and isinstance(got, dict) and got.get("ok") is True, (rc, out[-300:]))
    # D-4 두 쓸 파일이 매달린 링크로 한 파일에 닿는다 — 보고 r.json → out.k(아직 없다) · 산출 out.k
    d = ep_dir("D4")
    os.symlink("out.k", os.path.join(d, "r.json"))
    rc, out, rep = ep(binary, d)
    check("D-4 extract-parts 보고(매달린 링크 → out.k) · 산출 out.k — rc 1 · 같은 파일이라 거절 · 아무것도 쓰지 않음",
          rc == 1 and "같은 파일" in out and not os.path.exists(os.path.join(d, "out.k")) and os.path.islink(os.path.join(d, "r.json"))
          and not tmp_left(d), (rc, sorted(os.listdir(d)), out[-300:]))


# ── F 제자리 쓰기로 넘어간 뒤의 임시 파일 ──────────────────────────────────────
def sec_f(binary):
    print("[F] 잡은 뒤 폴더가 읽기 전용이 됐다 — 제자리로 쓰고, 못 지운 임시 파일은 비우고 말한다 · 다음 실행이 지운다")
    if os.geteuid() == 0:
        check("F — root 는 폴더 권한을 넘는다(건너뜀)", True)
        return
    for op in ("extract-parts", "apply_carryover_plan"):
        if op == "extract-parts":
            d = os.path.join(TMP, "F_ep")
            os.makedirs(os.path.join(d, "o"))
            os.symlink(big_deck(), os.path.join(d, "in.k"))
            write(os.path.join(d, "f.yaml"), "model: in.k\noutput: o/out.k\nparts: [1]\nreport: o/r.json\n")
            args, out_name, rep_name = ("extract-parts", "f.yaml"), "out.k", "r.json"
        else:
            d = co_dir("F_co")
            os.makedirs(os.path.join(d, "o"))
            write(os.path.join(d, "f.yaml"), "model: deck.k\nplan: plan.json\noutput: o/deck_applied\nreport: o/rep.json\n")
            args, out_name, rep_name = ("apply_carryover_plan", "f.yaml"), "deck_applied.k", "rep.json"
        o = os.path.join(d, "o")
        write(os.path.join(o, out_name), "OLD\n")
        write(os.path.join(o, rep_name), "{}\n")
        p = None
        for _ in range(40):   # 산출의 임시 파일이 o/ 에 보이면 멈춘다
            q = start(binary, d, *args, pipe=True)
            while q.poll() is None:
                if temp_of(o, out_name):
                    os.kill(q.pid, signal.SIGSTOP)
                    if temp_of(o, out_name):
                        p = q
                    else:
                        os.kill(q.pid, signal.SIGCONT)
                    break
            if p:
                break
            q.communicate()
        if p is None:
            check("F %s — 바꿔 넣기 전에 멈추지 못했다" % op, False)
            continue
        os.chmod(o, 0o555)
        os.kill(p.pid, signal.SIGCONT)
        said = p.communicate(timeout=300)[0]
        left = [n for n in os.listdir(o) if ".kr_tmp_" in n]
        sizes = [os.path.getsize(os.path.join(o, n)) for n in left]
        os.chmod(o, 0o755)
        rep = load(os.path.join(o, rep_name))
        check("F-1 %s 폴더가 읽기 전용이 됐다 — rc 0 · 산출 · 보고가 새것 · 못 지운 임시 파일 %d 개는 0 바이트 · [WARN] 지우지 못했다 · 말에 .kr_tmp_ 없음" %
              (op, len(left)),
              p.returncode == 0 and is_new_deck(os.path.join(o, out_name)) and ok_report(rep) and left and all(s == 0 for s in sizes) and
              "지우지 못했다" in said and ".kr_tmp_" not in said, (p.returncode, left, sizes, said[-400:]))
        rc2, said2 = run(binary, d, *args)
        check("F-2 %s 폴더에 쓸 수 있게 된 다음 실행이 남은 임시 파일을 지운다 — rc 0" % op,
              rc2 == 0 and not [n for n in os.listdir(o) if ".kr_tmp_" in n], (rc2, os.listdir(o), said2[-300:]))


# ── T 임시 파일 이름 표지 ────────────────────────────────────────────────────
def traced(binary, d, args, env=None):
    """strace 로 돌려 이 실행이 d 아래에 만들었다가 끝에 없는 파일(임시 파일)을 모은다 — (rc, 말, 임시 파일 이름들)."""
    import re
    trace = d.rstrip("/") + ".strace"
    p = subprocess.run(["strace", "-f", "-qq", "-o", trace, "-e", "trace=open,openat,creat", binary, *args], cwd=d,
                       capture_output=True, text=True, timeout=900, encoding="utf-8", errors="replace", env=env)
    made = set()
    for line in open(trace, encoding="utf-8", errors="replace"):
        m = re.search(r'\b(open|openat|creat)\((?:AT_FDCWD, )?"([^"]+)"(?:, ([A-Z_|]+))?', line)
        if not m or re.search(r"= -1 ", line):
            continue
        if m.group(1) != "creat" and "O_CREAT" not in (m.group(3) or ""):
            continue
        made.add(os.path.normpath(m.group(2) if m.group(2).startswith("/") else os.path.join(d, m.group(2))))
    os.remove(trace)
    gone = sorted(os.path.basename(x) for x in made if x.startswith(os.path.normpath(d) + os.sep) and not os.path.exists(x))
    return p.returncode, p.stdout + p.stderr, gone


def sec_t(binary):
    print("[T] 임시 파일 이름 표지 — 실행이 만들었다 지운 파일은 모두 .kr_tmp_ 를 지닌다(플랫폼이 산출로 올리지 않는다)")
    if not shutil.which("strace"):
        check("T — strace 가 없다(건너뜀)", True)
        return
    gmsh = os.environ.get("KOOREMAPPER_GMSH") or os.environ.get("KOOREMAPPER_TEST_GMSH")
    cases = []
    # map — bbox_align: source(앞처리 평판) · flip_x(뒤집은 기준)이 prestress 고리와
    d = os.path.join(TMP, "T_map")
    os.makedirs(d)
    run(binary, d, "generate", "--dim-i", "10", "--dim-j", "4", "arc", "demo")
    flat = open(os.path.join(d, "demo_flat_fine.k"), encoding="utf-8").read().splitlines()
    sec, out = "", []
    for ln in flat:   # x 를 0.5% 늘린 평판(크기를 맞추는 갈래가 돈다) — 재료 카드는 그대로
        if ln.startswith("*"):
            sec = ln.strip().upper()
        if sec == "*NODE" and not ln.startswith("*") and not ln.startswith("$") and len(ln) >= 56:
            ln = ln[:8] + "%16.9e" % (float(ln[8:24]) * 1.005) + ln[24:]
        out.append(ln)
    write(os.path.join(d, "flat_s.k"), "\n".join(out) + "\n")
    write(os.path.join(d, "src.yaml"), "bent: demo_bent.k\nflat: flat_s.k\noutput: m1.k\nbbox_align: source\nbbox_align_max_drift: 50\n"
                                       "prestress:\n  enabled: true\n  output: m1.dynain\n  E: 210000.0\n  nu: 0.3\n")
    write(os.path.join(d, "flip.yaml"), "bent: demo_bent.k\nflat: demo_flat_fine.k\noutput: m2.k\nflip_x: true\n"
                                        "prestress:\n  enabled: true\n  output: m2.dynain\n  E: 210000.0\n  nu: 0.3\n")
    cases += [("map bbox_align: source", d, ("map", "src.yaml"), "kr_tmp_preproc_flat", None),
              ("map flip_x 고리", d, ("map", "flip.yaml"), "kr_tmp_flipped_ref", None)]
    # 펼친 덱 — elform 의 flatten_includes
    d = os.path.join(TMP, "T_flat")
    os.makedirs(d)
    write(os.path.join(d, "box.yaml"), "output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 4\nny: 2\nnz: 1\nrho: 7.85e-9\nE: 210000.0\n"
                                       "nu: 0.3\nmid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")
    run(binary, d, "generate", "box", "box.yaml")
    body = [l for l in open(os.path.join(d, "box.k"), encoding="utf-8").read().splitlines() if l.strip().upper() not in ("*KEYWORD", "*END")]
    write(os.path.join(d, "body.k"), "\n".join(body) + "\n")
    write(os.path.join(d, "main.k"), "*KEYWORD\n*INCLUDE\nbody.k\n*END\n")
    write(os.path.join(d, "el.yaml"), "base_model: main.k\noutput: el\nflatten_includes: true\noperations:\n  - type: elform\n    target_elform: 2\n")
    cases.append(("elform flatten_includes", d, ("elform", "el.yaml"), "kr_tmp_flat_", None))
    # meshfix — gmsh 왕복 · polish
    if gmsh and os.path.exists(gmsh):
        env = dict(os.environ, KOOREMAPPER_GMSH=gmsh)
        for tag, extra in (("meshfix", ""), ("meshfix polish", "polish: true\n")):
            d = os.path.join(TMP, "T_" + tag.replace(" ", "_"))
            os.makedirs(d)
            shutil.copy(os.path.join(REPO, "examples", "mesh", "tetramesh.k"), d)
            write(os.path.join(d, "mf.yaml"), "model: tetramesh.k\noutput: mf_out.k\npid: 1\n" + extra)
            cases.append((tag, d, ("meshfix", "mf.yaml"), "kr_tmp_pol" if extra else "kr_tmp_mf", env))
    else:
        check("T meshfix — gmsh 가 없다(KOOREMAPPER_GMSH · 건너뜀)", True)
    for tag, d, args, want, env in cases:
        rc, said, gone = traced(binary, d, args, env)
        check("T %s — rc 0 · 만들었다 지운 파일 %d 개가 모두 .kr_tmp_ 를 지닌다(%s 가 그 가운데 있다)" % (tag, len(gone), want),
              rc == 0 and gone and all(".kr_tmp_" in n for n in gone) and any(want in n for n in gone), (rc, gone[:6], said[-300:]))


# ── W 쓰기 오류 ──────────────────────────────────────────────────────────────
def run_fsize(binary, d, args, limit):
    """파일 크기 상한(SIGXFSZ 무시 — 넘는 쓰기가 EFBIG 로 짧게 끝난다)으로 돌린다."""
    import resource

    def pre():
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace",
                       preexec_fn=pre)
    return p.returncode, p.stdout + p.stderr


def parts_first_deck(nx, ny):
    """*PART · *SECTION · *MAT 를 앞에, 요소를 끝에 — 잘려도 미정의 참조가 없어 되읽기가 못 잡는 꼴."""
    full = shell_deck(nx, ny).splitlines()
    i_el, i_part = full.index("*ELEMENT_SHELL"), full.index("*PART")
    return "\n".join(full[:1] + full[i_part:-1] + full[1:i_el] + full[i_el:i_part] + ["*END"]) + "\n"


def sec_w(binary):
    print("[W] 쓰기 오류 — 잘린 덱을 바꿔 넣지 않고 rc 1 · 보고가 그 오류를 말한다(바로 쓰는 op 도 rc 1)")
    # W-1 extract-parts — 앞 실행의 산출 · 보고가 있는 자리에 크기 상한(산출 반)으로
    for tag, deck, verify in (("표준 덱 · verify true", shell_deck(40, 20), "true"), ("파트 먼저 덱 · verify false", parts_first_deck(40, 20), "false")):
        d = ep_dir("W1_" + verify, deck=deck)
        write(os.path.join(d, "e.yaml"), "model: in.k\noutput: out.k\nparts: [1]\nreport: r.json\nverify: %s\n" % verify)
        rc0, _ = run(binary, d, "extract-parts", "e.yaml")
        before = sha(os.path.join(d, "out.k"))
        rc, out = run_fsize(binary, d, ("extract-parts", "e.yaml"), os.path.getsize(os.path.join(d, "out.k")) // 2)
        rep = load(os.path.join(d, "r.json"))
        said = " ".join(r.get("message", "") for r in rep.get("refusals", [])) if isinstance(rep, dict) else ""
        check("W-1 extract-parts %s · 산출 반 크기 상한 — rc 1 · 앞 산출 그대로 · 보고 ok false 가 그 오류(File too large)를 말한다" % tag,
              rc0 == 0 and rc == 1 and sha(os.path.join(d, "out.k")) == before and isinstance(rep, dict) and rep.get("ok") is False and
              rep.get("output_written") is False and "File too large" in said and not tmp_left(d), (rc0, rc, said[:200], out[-300:]))
    # W-2 extract-parts output: /dev/full — 바로 쓰는 자리의 쓰기 오류(verify false — 끝없이 읽히는 장치를 되읽지 않게)
    d = ep_dir("W2")
    rc, out, rep = ep(binary, d, output="/dev/full", extra="verify: false\n")
    check("W-2 extract-parts output: /dev/full — rc 1 · 보고 ok false 가 그 오류(No space left)를 말한다",
          rc == 1 and isinstance(rep, dict) and rep.get("ok") is False and
          "No space left" in " ".join(r.get("message", "") for r in rep.get("refusals", [])), (rc, out[-300:]))
    # W-3 이월 적용 — 마지막 *SECTION 블록 앞까지만 쓰이게(되읽기 대조가 못 잡던 꼴 — 검토 t_efbig_sec)
    d = co_ready("W3")
    rc0, _ = run(binary, d, *CO_ARGS)
    full = open(os.path.join(d, "deck_applied.k"), "rb").read()
    lines = full.split(b"\n")
    last = max(i for i, l in enumerate(lines) if l.startswith(b"*SECTION"))
    cut = len(b"\n".join(lines[:last]) + b"\n")
    before = sha(os.path.join(d, "deck_applied.k"))
    rc, out = run_fsize(binary, d, CO_ARGS, cut)
    rep = load(os.path.join(d, "deck_applied_carryover.json"))
    said = " ".join(p.get("detail", "") for p in rep.get("problems", [])) if isinstance(rep, dict) else ""
    check("W-3 apply_carryover_plan 마지막 *SECTION 앞까지만 쓰이는 상한 — rc 1 · 앞 덱 그대로 · 보고 ok false · write(File too large)",
          rc0 == 0 and rc == 1 and sha(os.path.join(d, "deck_applied.k")) == before and isinstance(rep, dict) and rep.get("ok") is False and
          "File too large" in said and not tmp_left(d), (rc0, rc, said[:200], out[-300:]))
    # W-4 · W-5 바로 쓰는 op — writeOutput(elform) · DeckWriter(database)
    for k, opname, body, outname in ((4, "elform", "base_model: box.k\noutput: box_el\noperations:\n  - type: elform\n    target_elform: 2\n",
                                      "box_el.k"),
                                     (5, "database", "model: box.k\noutput: box_db.k\npreset: drop\ndt: 0.0001\ndt_plot: 0.005\n",
                                      "box_db.k")):
        d = os.path.join(TMP, "W%d_%s" % (k, opname))
        os.makedirs(d)
        write(os.path.join(d, "box.yaml"), "output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\nrho: 7.85e-9\nE: 210000.0\n"
                                           "nu: 0.3\nmid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")
        run(binary, d, "generate", "box", "box.yaml")
        write(os.path.join(d, "c.yaml"), body)
        rc0, _ = run(binary, d, opname, "c.yaml")
        size = os.path.getsize(os.path.join(d, outname)) if os.path.exists(os.path.join(d, outname)) else 0
        if size:
            os.remove(os.path.join(d, outname))
        rc, out = run_fsize(binary, d, (opname, "c.yaml"), max(size // 2, 1))
        check("W-%d %s(%s) 산출 반 크기 상한 — rc 1 · [ERROR] 가 쓰다 멈춘 파일과 까닭(File too large)을 말한다" %
              (k, opname, "writeOutput" if k == 4 else "DeckWriter"),
              rc0 == 0 and size > 0 and rc == 1 and "File too large" in out and "[ERROR]" in out, (rc0, size, rc, out[-300:]))


# ── P 제자리로 옮겨 쓰다 멈춘 산출 ────────────────────────────────────────────
def start_nofsz(binary, d, *args):
    """SIGXFSZ 무시로 띄운다 — 뒤에 prlimit 로 크기 상한을 걸면 넘는 쓰기가 EFBIG 로 짧게 끝난다(말을 모은다)."""
    return subprocess.Popen([binary, *args], cwd=d, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", preexec_fn=lambda: signal.signal(signal.SIGXFSZ, signal.SIG_IGN))


def sec_p(binary):
    print("[P] 제자리로 옮겨 쓰다 멈췄다 — 그 파일이 잘렸다고 말한다(앞 파일이 그대로라고 하지 않는다 · output_damaged)")
    import resource
    if os.geteuid() == 0:
        check("P — root 는 폴더 권한을 넘는다(건너뜀)", True)
        return
    k = 0
    for op in ("extract-parts", "apply_carryover_plan"):
        for how in ("rename_fallback", "inplace"):
            k += 1
            name = "P%d_%s_%s" % (k, op, how)
            if op == "extract-parts":
                d = ep_dir(name, deck=shell_deck(40, 20))
                write(os.path.join(d, "p.yaml"), "model: in.k\noutput: o/out.k\nparts: [1]\nreport: o/r.json\n")
                args, out_name, rep_name = ("extract-parts", "p.yaml"), "out.k", "r.json"
            else:
                d = co_dir(name)
                write(os.path.join(d, "p.yaml"), "model: deck.k\nplan: plan.json\noutput: o/deck_applied\nreport: o/rep.json\n")
                args, out_name, rep_name = ("apply_carryover_plan", "p.yaml"), "deck_applied.k", "rep.json"
            o = os.path.join(d, "o")
            os.makedirs(o)
            rc0, _ = run(binary, d, *args)   # 앞 실행 — 제자리로 옮겨 쓸 산출 · 보고가 있다
            out_p = os.path.join(o, out_name)
            full = os.path.getsize(out_p) if os.path.exists(out_p) else 0
            limit = full // 2
            # 이 시험이 잠금을 쥔 동안 실행은 다 써 두고 기다린다. rename_fallback — 그 사이 폴더를 읽기 전용으로(이름 바꾸기 EACCES →
            # 그 파일에 제자리로) · inplace — 처음부터 읽기 전용(시스템 임시 폴더에 써 두었다가 제자리로). 풀기 전에 크기 상한(산출 반)을 건다
            fd = hold_lock(o, out_name)
            if how == "inplace":
                os.chmod(o, 0o555)
            p = start_nofsz(binary, d, *args)
            staged = (lambda: temp_of(o, out_name) and temp_of(o, rep_name)) if how == "rename_fallback" else \
                     (lambda: len(sys_tmp_of(p.pid)) >= 2)
            t0 = time.time()
            while p.poll() is None and time.time() - t0 < 60 and not staged():
                time.sleep(0.01)
            time.sleep(0.5)   # 보고를 써 두고 잠금에서 기다린다
            waiting = p.poll() is None
            if how == "rename_fallback":
                os.chmod(o, 0o555)
            if waiting:
                resource.prlimit(p.pid, resource.RLIMIT_FSIZE, (limit, limit))
            os.close(fd)
            said = p.communicate(timeout=300)[0]
            size = os.path.getsize(out_p)
            os.chmod(o, 0o755)
            rep = load(os.path.join(o, rep_name))
            if op == "extract-parts":
                marked = isinstance(rep, dict) and rep.get("output_damaged") is True and rep.get("output_written") is False
            else:
                marked = isinstance(rep, dict) and any(x.get("kind") == "output_damaged" for x in rep.get("problems", []))
            check("P-%d %s %s · 옮겨 쓰다 멈췄다(산출 반 크기 상한) — rc 1 · 그 파일이 잘렸다고 말한다(앞 파일 그대로라 하지 않는다) · 보고 "
                  "ok false · output_damaged" % (k, op, how),
                  rc0 == 0 and limit > 0 and waiting and p.returncode == 1 and size == limit and isinstance(rep, dict) and
                  rep.get("ok") is False and marked and "잘려 반쯤 쓴 채다" in said and "앞 파일은 그대로다" not in said and
                  "File too large" in said and ".kr_tmp_" not in said,
                  (rc0, limit, waiting, p.returncode, size, rep if not isinstance(rep, dict) else
                   {x: rep.get(x) for x in ("ok", "output_written", "output_damaged", "problems")}, said[-500:]))


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
        sec_o(binary)
        sec_c(binary)
        sec_m(binary)
        sec_u(binary)
        sec_w(binary)
        sec_d(binary)
        sec_f(binary)
        sec_p(binary)
        sec_t(binary)
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
