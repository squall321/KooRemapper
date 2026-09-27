#!/usr/bin/env python3
"""`cnrb2solid` 가 **네임스페이스별로** ID 를 발행하고 8칸을 넘기면 멈추는가 (P1-13 ①).

왜 이 시험이 있나 (2026-09-27) — `cnrb2solid` 전용 회귀는 **오늘까지 0개**였다(plan2 P1-13).

  발행 기준을 정하는 스캔이 **모든 비키워드 줄**의 첫 10칸을 읽어 SECID·MID·SID·PID 네 곳에
  **동시에** 밀어 넣었다(코드 주석이 "We'll be conservative" 라고 적혀 있었다). 그러면 상관없는
  번호가 전부를 밀어 올린다.

  실측 — `examples/cnrb2solid/bolt_simple.k` 는 `*SECTION` 최대 1 · `*MAT` 1 · `*SET` 18 인데,
  `*CONSTRAINED_NODAL_RIGID_BODY` 의 첫 칸 **200**(그것은 **파트 ID** 다) 때문에 새 SECID·MID·SID 가
  전부 **201** 로 나갔다. 노드 ID 가 9,900,001 대인 덱에서는 SECID 가 그 대역으로 뛴다.

  ⚠ CNRB 의 첫 칸은 파트 ID 이므로 **PART 쪽에는 남긴다** — 새 파트가 그 번호를 다시 쓰면 안 된다.
  이 시험이 그 비대칭을 못 박는다.

그리고 `%8d` 는 넘치면 **잘라 주지 않고 칸을 넓힌다** — 다음 칸을 침범한 줄이 조용히 나가고
LS-DYNA 가 엉뚱한 노드를 읽는다. 그래서 8칸을 넘기면 **파일을 쓰지 않고 rc=1** 이다.

usage: test_cnrb2solid_ids.py <KooRemapper 바이너리>
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
EX = os.path.join(REPO, "examples", "cnrb2solid")


def check(name, cond, detail=""):
    print("  %-64s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:400]) if detail else ""))


def ids_by_kw(path):
    """키워드별 첫 칸 ID 모음 — 출력 덱에서 무엇이 발행됐나."""
    out, cur = {}, None
    for l in open(path, encoding="latin-1", newline="").read().split("\n"):
        u = l.upper()
        if l.startswith("*"):
            cur = ("SEC" if u.startswith("*SECTION") else
                   "MAT" if u.startswith("*MAT") and not u.startswith("*MAT_ADD") else
                   "SET" if u.startswith("*SET") else
                   "PART" if u.startswith("*PART") else None)
            continue
        if not l.strip() or l.startswith("$") or cur is None:
            continue
        m = re.match(r"\s*(\d+)", l[:10])
        if m:
            out.setdefault(cur, set()).add(int(m.group(1)))
    return out


def run(binary, d, yaml_name):
    p = subprocess.run([binary, "cnrb2solid", yaml_name], capture_output=True, text=True,
                       timeout=900, cwd=d)
    return p.returncode, p.stdout + p.stderr


def stage(d, model_text=None, out_name="out.k"):
    shutil.copy(os.path.join(EX, "bolt_simple.k"), os.path.join(d, "in.k"))
    if model_text is not None:
        open(os.path.join(d, "in.k"), "w", newline="\n").write(model_text)
    cfg = open(os.path.join(EX, "basic.yaml"), encoding="utf-8").read()
    cfg = cfg.replace("model: bolt_simple.k", "model: in.k")
    cfg = cfg.replace("output: bolt_simple_solid.k", "output: " + out_name)
    open(os.path.join(d, "cfg.yaml"), "w", newline="\n").write(cfg)
    return os.path.join(d, out_name)


def base_deck():
    return open(os.path.join(EX, "bolt_simple.k"), encoding="latin-1", newline="").read()


def main():
    if len(sys.argv) < 2:
        print("usage: test_cnrb2solid_ids.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2
    if not os.path.isdir(EX):
        print("fixture not found: " + EX)
        return 2

    print("[A 네임스페이스별로 발행한다]")
    d = tempfile.mkdtemp(prefix="c2s_")
    op = stage(d)
    rc, out = run(binary, d, "cfg.yaml")
    check("A-1 rc=0", rc == 0, out[-300:])
    if os.path.exists(op):
        got = ids_by_kw(op)
        # 원본: *SECTION 1 · *MAT 1 · *SET 18(+2,10) · *PART 1 · CNRB pid 200
        check("A-2 SECID 가 섹션 대역에서 나온다(2)", 2 in got.get("SEC", set()),
              "SEC=%r" % sorted(got.get("SEC", ())))
        check("A-3 MID 가 재질 대역에서 나온다(2)", 2 in got.get("MAT", set()),
              "MAT=%r" % sorted(got.get("MAT", ())))
        check("A-4 SID 가 세트 대역에서 나온다(19)", 19 in got.get("SET", set()),
              "SET=%r" % sorted(got.get("SET", ())))
        # ⚠ 201 은 CNRB 의 파트 ID 200 이 새어 들어왔던 옛 번호다.
        for ns in ("SEC", "MAT", "SET"):
            check("A-5 %s 에 201 이 없다(옛 오염 번호)" % ns, 201 not in got.get(ns, set()),
                  "%s=%r" % (ns, sorted(got.get(ns, ()))))
        # ⚠ 새 `*PART` 는 **발행하지 않고 `cnrb.pid` 를 재사용한다**(`maxPartId` 매개변수는 쓰이지
        # 않는다). 처음에 이 자리를 "PART 대역도 센다" 로 적었는데 돌연변이가 살아남아 그것이
        # 관찰 불가능한 코드임을 드러냈다 — 코드를 빼고 계약을 사실대로 적는다.
        check("A-6 새 파트는 CNRB 의 pid 를 재사용한다(200)", 200 in got.get("PART", set()),
              "PART=%r" % sorted(got.get("PART", ())))
    else:
        check("A 산출물이 생겼다", False, out[-300:])
    shutil.rmtree(d, ignore_errors=True)

    print("[B 무관한 네임스페이스의 큰 번호는 발행을 밀지 않는다]")
    # `*DEFINE_CURVE` 의 LCID 는 곡선 네임스페이스다. 옛 코드는 이것으로 SEC/MAT/SET 을 999,999
    # 대로 밀어 올렸다.
    deck = base_deck().replace(
        "*END",
        "*DEFINE_CURVE\n    999999         0       1.0       1.0       0.0       0.0\n"
        "       0.0       0.0\n       1.0       1.0\n*END", 1)
    d = tempfile.mkdtemp(prefix="c2s_")
    op = stage(d, deck)
    rc, out = run(binary, d, "cfg.yaml")
    check("B-1 rc=0", rc == 0, out[-300:])
    if os.path.exists(op):
        got = ids_by_kw(op)
        for ns, want in (("SEC", 2), ("MAT", 2), ("SET", 19)):
            vs = got.get(ns, set())
            check("B-2 %s 가 곡선 번호에 안 끌려간다(%d)" % (ns, want),
                  want in vs and not any(v >= 999999 for v in vs), "%s=%r" % (ns, sorted(vs)))
    else:
        check("B 산출물이 생겼다", False, out[-300:])
    shutil.rmtree(d, ignore_errors=True)

    print("[B2 네임스페이스끼리 섞이지 않는다 — 섹션만 크게]")
    # ⚠ 기본 픽스처는 세 네임스페이스 최대가 1·1·18 로 가까워 **섞여도 티가 안 난다**(첫 판에서
    # 그 돌연변이가 살아남았다). 섹션 ID 만 500 으로 올려 섞임을 관찰 가능하게 만든다.
    deck = base_deck().replace("*SECTION_SHELL", "*SECTION_SHELL", 1)
    lines = deck.split("\n")
    for i, l in enumerate(lines):
        if l.upper().startswith("*SECTION"):
            for j in range(i + 1, len(lines)):
                if lines[j].strip() and not lines[j].startswith("$") and not lines[j].startswith("*"):
                    lines[j] = "%10d%s" % (500, lines[j][10:])
                    break
            break
    d = tempfile.mkdtemp(prefix="c2s_")
    op = stage(d, "\n".join(lines))
    rc, out = run(binary, d, "cfg.yaml")
    check("B2-1 rc=0", rc == 0, out[-300:])
    if os.path.exists(op):
        got = ids_by_kw(op)
        check("B2-2 SECID 는 501(섹션 대역을 따른다)", 501 in got.get("SEC", set()),
              "SEC=%r" % sorted(got.get("SEC", ())))
        check("B2-3 MID 는 2 그대로(섹션에 안 끌려간다)", 2 in got.get("MAT", set()),
              "MAT=%r" % sorted(got.get("MAT", ())))
        check("B2-4 SID 는 19 그대로(섹션에 안 끌려간다)", 19 in got.get("SET", set()),
              "SET=%r" % sorted(got.get("SET", ())))
    else:
        check("B2 산출물이 생겼다", False, out[-300:])
    shutil.rmtree(d, ignore_errors=True)

    print("[C 8칸을 넘기면 파일을 쓰지 않고 멈춘다]")
    # 최대 노드 ID 를 99,999,999 로 올리면 생성 노드가 그 다음부터라 8칸을 넘는다.
    deck = base_deck().replace(
        "*ELEMENT_SHELL",
        "%8d%16.8e%16.8e%16.8e       0       0\n*ELEMENT_SHELL" % (99999999, 0.0, 0.0, 99.0), 1)
    d = tempfile.mkdtemp(prefix="c2s_")
    op = stage(d, deck)
    rc, out = run(binary, d, "cfg.yaml")
    check("C-1 rc=1", rc == 1, "rc=%d / %s" % (rc, out[-300:]))
    check("C-2 산출 파일을 쓰지 않았다", not os.path.exists(op),
          "파일이 생겼다 — 잘린 덱이 나갔을 수 있다")
    check("C-3 건수와 최대값을 말한다", "8칸을 넘긴 ID" in out and "최대" in out, out[-300:])
    # ⚠ 수백 건을 한 줄에 나열하면 읽을 수 없다 — 처음에 그렇게 만들어 봤다.
    long_lines = [l for l in out.splitlines() if "8칸을 넘긴" in l and len(l) > 400]
    check("C-4 보고가 한 줄에 수백 건을 나열하지 않는다", not long_lines,
          "긴 줄 길이=%r" % [len(l) for l in long_lines])
    shutil.rmtree(d, ignore_errors=True)

    print()
    if FAILS:
        print("--- 실패 %d건 ---" % len(FAILS))
        for f in FAILS:
            print("  " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
