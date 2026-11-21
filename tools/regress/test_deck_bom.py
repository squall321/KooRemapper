#!/usr/bin/env python3
# 덱 · 번들 · 조각 입력 맨 앞에 UTF-8 BOM 이 붙어도 rc 와 산출이 BOM 없는 쌍둥이와 같은지 op 마다 보는 회귀 시험
"""덱 맨 앞의 UTF-8 BOM — 덱을 받는 모든 op (2026-11-21 · 미룬 결함 3차 1판 L-02).

왜 이 시험이 있나.

  윈도우 편집기는 저장할 때 파일 맨 앞에 BOM(EF BB BF)을 붙인다. 설정 YAML 은 55 op 이 떼고 읽었고 덱은 extract-parts ·
  cleanup-nodes 만 뗐다(2차 H-2 · H-4). 나머지는 rc 0 으로 이렇게 됐다 — 실측(11-21 · 설치된 판):
    · matswap 의 **번들**이 BOM 으로 시작하면 첫 `*PARAMETER` 줄을 키워드로 못 알아봐 `params=5 cards=31` 이 `params=0 cards=36` 이
      되고, 파트 줄의 SECID · HGID 가 번들 값(3 · 3) 대신 1 · 1 로 쓰였다. 번들 카드는 `&HGID1` 을 이름째 실었다
    · 원본을 따라 쓰는 23 op(map · assemble 족 …)은 제 `*KEYWORD` 뒤에 BOM 붙은 원본 `*KEYWORD` 줄을 한 번 더 실었다
    · cad_solid_merge_to_deck 은 **조각**의 BOM 붙은 `*KEYWORD` 줄을 앞 블록(`*MAT_ELASTIC`)의 데이터 줄 자리에 실었다
    · 덱을 줄째 옮기는 19 op(relax · contact · merge …)은 산출 맨 앞에 BOM 을 그대로 실었다
    · apply_carryover_plan 은 BOM 붙은 조각을 「키워드 밖의 데이터 줄」 이라며 거절했다(까닭 글이 BOM 을 말하지 않는다)
  이제 덱 · 번들 · 조각을 여는 자리가 BOM 을 떼고 읽고 산출에 싣지 않는다. apply_carryover_plan 은 그대로 거절하되(조각 검사는
  「고치지 않고 거절한다」 · 덱은 `deck_sha` 가 지킨다) 까닭 글이 BOM 을 말한다.

무엇을 보나(도움말 사례를 판으로 쓴다 — 제 명령이 읽는 덱은 명령줄 → 설정이 가리키는 파일 → `*INCLUDE` 자식 순으로 찾는다).
  op 마다 덱 입력 전부에(여럿이면 하나씩도) BOM 을 붙여 돌린다 → rc 가 같다 · 산출 파일이 BOM 없는 쌍둥이와 바이트로 같다(날짜 ·
  시각 줄은 가린다) · 어느 산출에도 BOM 바이트가 없다 · **화면**도 같다(시각 · 걸린 시간은 가린다).
  화면을 보는 까닭 — BOM 을 떼고 읽게 한 첫 판이 rc 와 산출은 같은데 화면에 거짓 줄을 냈다(실측 11-21). applyfold 는 입력 크기에
  BOM 세 바이트를 넣어 세어 「바이트 크기가 달라졌다」 를, apply_carryover_plan 은 뗀 줄을 파일 바이트와 견줘 `deck_changed` 를 냈다.
  matswap — 화면의 `bundle:` 줄(params · cards)도 같다.
  apply_carryover_plan — 덱에 붙이면 rc 1 `deck_sha`(그 줄이 「BOM」 을 말하고 `deck_changed` 는 없다) · 조각에 붙이면 rc 1 에 그 조각
  줄이 「BOM」 을 말한다 · 어느 쪽도 덱을 쓰지 않는다. 계획이 **BOM 붙은 그 덱**에서 나온 것이면(deck.sha256 이 BOM 째 바이트의 것)
  rc 0 이고 산출 덱이 BOM 없는 쌍둥이와 같다 — 설치된 판(11-21)은 rc 0 에 BOM 이 실린 덱을 썼고, 첫 판은 `deck_changed` 로 막았다.

  matswap 의 옛 자리 인자 꼴(`matswap <모델> <번들> <pid> <산출>`)은 번들을 읽는 자리가 따로다 — 번들에 BOM 을 붙여 따로 잰다.
  ale 의 `material:` 에 재료 파일 경로를 주면 그 파일도 읽는 자리가 따로다 — 실측(11-21)으로 BOM 이 붙으면 rc 0 에 `*MAT_NULL`
  블록이 통째로 빠지고 `*EOS_` 만 실렸다(파트가 가리키는 MID 가 덱에 없다). 도움말 사례는 붙박이 이름(air)이라 따로 잰다.

usage: test_deck_bom.py <KooRemapper 바이너리> [op ...]     (op 을 주면 그 op 만 돈다 — 변이 확인용)
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "help"))
from ops_help import OPS  # noqa: E402

BOM = b"\xef\xbb\xbf"
DATE = re.compile(rb"\d{4}[-/]\d{2}[-/]\d{2}|\d{2}:\d{2}:\d{2}")
CLOCK = re.compile(r"\[\d{4}-\d{2}-\d{2} [\d:.]+\]|\d+(\.\d+)?\s*(ms|s|초)\b|\d{4}[-/]\d{2}[-/]\d{2}|\d{2}:\d{2}:\d{2}")
GMSH_OPS = ("meshfix",)
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-600:]))
    print("  %-96s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def call(binary, cwd, cmd, timeout=900):
    p = subprocess.run([binary] + cmd.split()[1:], cwd=cwd, capture_output=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def screen(text):
    """화면에서 시각 · 걸린 시간을 가린 줄들 — 쌍둥이끼리 견준다."""
    return [CLOCK.sub("<T>", l) for l in text.splitlines()]


def snapshot(d):
    snap = {}
    for dp, _dirs, names in os.walk(d):
        for n in names:
            p = os.path.join(dp, n)
            with open(p, "rb") as f:
                snap[os.path.relpath(p, d)] = f.read()
    return snap


def is_deck(data):
    if data.startswith(BOM):
        data = data[3:]
    try:
        text = data[:4096].decode("utf-8")
    except UnicodeDecodeError:
        return False
    for line in text.splitlines():
        if line.strip():
            return line.startswith("*") or line.startswith("$")
    return False


def find_decks(run, cmd):
    """제 명령이 읽는 덱 — 명령줄 인자 → 설정이 가리키는 파일 → 덱의 *INCLUDE 자식."""
    decks, seen = [], set()
    queue = [(a, run, 0) for a in cmd.split()[2:]]
    while queue:
        tok, base_dir, depth = queue.pop(0)
        for cand in (os.path.join(run, tok), os.path.join(base_dir, tok)):
            if os.path.isfile(cand):
                break
        else:
            continue
        rel = os.path.relpath(cand, run)
        if rel in seen or rel.startswith(".."):
            continue
        seen.add(rel)
        with open(cand, "rb") as f:
            data = f.read()
        if is_deck(data):
            decks.append(rel)
            lines = data.decode("utf-8", "replace").splitlines()
            for i, line in enumerate(lines):
                if line.upper().startswith("*INCLUDE"):
                    for nxt in lines[i + 1:]:
                        if nxt.startswith("*"):
                            break
                        if nxt.strip() and not nxt.startswith("$"):
                            queue.append((nxt.strip(), os.path.dirname(cand), depth + 1))
        elif depth <= 2 and len(data) < 2_000_000:
            for t in re.findall(r"[^\s\"'\[\],:{}]+", data.decode("utf-8", "replace")):
                queue.append((t, os.path.dirname(cand), depth + 1))
    return decks


class Case:
    """op 하나의 판 — 도움말 사례를 차리고 제 명령 앞까지 돌린 폴더(base)를 변형마다 같은 자리(run)로 복사해 돈다."""

    def __init__(self, binary, root, spec):
        self.binary, self.spec = binary, spec
        self.base, self.run = os.path.join(root, "base"), os.path.join(root, "run")
        name = spec["name"]
        own = [i for i, c in enumerate(spec["cmds"]) if c.split()[1] == name]
        self.cmd = spec["cmds"][own[-1]] if own else None
        if not own:
            return
        os.makedirs(self.base)
        for need in spec["needs"]:
            shutil.copytree(os.path.dirname(os.path.join(REPO, need)), os.path.join(self.base, os.path.dirname(need)),
                            dirs_exist_ok=True)
        for fname, content in spec["files"].items():
            with open(os.path.join(self.base, fname), "w", encoding="utf-8") as f:
                f.write(content)
        for c in spec["cmds"][:own[-1]]:
            rc, text = call(binary, self.base, c)
            if rc != 0:
                raise RuntimeError("준비 명령 실패 %s: %s" % (c, text[-400:]))
        self.decks = find_decks(self.base, self.cmd)

    def go(self, bom=(), patch=None):
        """base 를 run 으로 복사하고 bom 의 파일 맨 앞에 BOM 을 붙여(patch 가 있으면 그 뒤에 부른다) 제 명령을 돌린다
        → (rc, 화면, 산출 {이름: 바이트})."""
        shutil.rmtree(self.run, ignore_errors=True)
        shutil.copytree(self.base, self.run)
        for rel in bom:
            p = os.path.join(self.run, rel)
            with open(p, "rb") as f:
                data = f.read()
            with open(p, "wb") as f:
                f.write(BOM + data)
        if patch:
            patch(self.run)
        before = snapshot(self.run)
        rc, text = call(self.binary, self.run, self.cmd)
        outs = {r: DATE.sub(b"<D>", d) for r, d in snapshot(self.run).items() if before.get(r) != d}
        return rc, text, outs


def differs(a, b):
    """두 산출 묶음에서 다른 파일의 이름과 첫 다른 줄 — 비면 같다."""
    out = []
    for r in sorted(set(a) | set(b)):
        x, y = a.get(r), b.get(r)
        if x == y:
            continue
        if x is None or y is None:
            out.append("%s %s" % (r, "없음" if y is None else "새로 생김"))
            continue
        xl, yl = x.split(b"\n"), y.split(b"\n")
        i = next((k for k, (p, q) in enumerate(zip(xl, yl)) if p != q), min(len(xl), len(yl)))
        out.append("%s %d째 줄 %r → %r (%d → %d 줄)" % (r, i + 1, xl[i][:60] if i < len(xl) else b"", yl[i][:60] if i < len(yl) else b"",
                                                      len(xl), len(yl)))
    return out


def carryover(case, plain):
    """apply_carryover_plan — 거절은 그대로 · 조각의 까닭 글이 BOM 을 말한다."""
    deck = case.decks[0]
    rc, text, outs = case.go([deck])
    sha = next((l for l in text.splitlines() if "deck_sha" in l), "")
    check("★apply_carryover_plan · 덱에 BOM → rc 1 · `deck_sha` 줄이 「BOM」 을 말한다 · `deck_changed` 는 없다 · 덱을 쓰지 않는다",
          rc == 1 and "BOM" in sha and "deck_changed" not in text and not any(r.endswith(".k") for r in outs),
          (rc, sorted(outs), sha[-200:], [l[:80] for l in text.splitlines() if "deck_changed" in l]))

    def from_bom_deck(run):
        """계획의 deck.sha256 을 BOM 붙은 덱 바이트의 것으로 바꾼다 — 그 덱에서 낸 계획."""
        plan = next(os.path.join(run, t) for t in case.spec["files"]["c.yaml"].split() if t.endswith("plan.json"))
        with open(plan, encoding="utf-8") as f:
            t = f.read()
        with open(os.path.join(run, deck), "rb") as f:
            new = hashlib.sha256(f.read()).hexdigest()
        old = json.loads(t)["deck"]["sha256"]
        assert t.count(old) == 1
        with open(plan, "w", encoding="utf-8") as f:
            f.write(t.replace(old, new))

    rc, text, outs = case.go([deck], patch=from_bom_deck)
    decks = {r: d for r, d in outs.items() if r.endswith(".k")}
    p_decks = {r: d for r, d in plain[2].items() if r.endswith(".k")}
    check("★apply_carryover_plan · BOM 덱에서 낸 계획(deck.sha256 이 BOM 째) → rc 0 · 산출 덱이 쌍둥이와 같다 · BOM 없음",
          rc == 0 and bool(p_decks) and not differs(p_decks, decks) and not any(BOM in d for d in outs.values()),
          (rc, differs(p_decks, decks)[:2], [l[:160] for l in text.splitlines() if l.startswith("[ERROR]")][:3]))
    for frag in case.decks[1:]:
        rc, text, outs = case.go([frag])
        line = next((l for l in text.splitlines() if l.startswith("[ERROR]") and os.path.basename(frag) in l), "")
        check("★apply_carryover_plan · 조각 %s 에 BOM → rc 1 · 까닭 글이 「BOM」 을 말한다 · 덱을 쓰지 않는다" % os.path.basename(frag),
              rc == 1 and "BOM" in line and "키워드 밖의 데이터 줄" not in line and not any(r.endswith(".k") for r in outs),
              (rc, sorted(outs), line or text[-300:]))


def legacy_matswap(binary, top):
    """옛 자리 인자 꼴 — 번들을 `matswap.cpp` 의 제 리더가 읽는다(YAML 꼴은 조립기 쪽 리더)."""
    def go(tag, bom):
        d = os.path.join(top, "legacy_" + tag)
        shutil.copytree(os.path.join(REPO, "examples", "matswap"), os.path.join(d, "examples", "matswap"))
        if bom:
            p = os.path.join(d, "examples", "matswap", "rubber.k")
            with open(p, "rb") as f:
                data = f.read()
            with open(p, "wb") as f:
                f.write(BOM + data)
        rc, text = call(binary, d, "KooRemapper matswap examples/matswap/two_cubes.k examples/matswap/rubber.k 1 out.k")
        out = os.path.join(d, "out.k")
        data = DATE.sub(b"<D>", open(out, "rb").read()) if os.path.isfile(out) else None
        return rc, [l for l in text.splitlines() if "Bundle cards:" in l], data, text
    p_rc, p_line, p_out, p_text = go("plain", False)
    if not check("matswap(옛 자리 인자 꼴) · 번들 그대로 rc 0 · 화면에 Bundle cards 줄", p_rc == 0 and p_line and p_out, p_text[-400:]):
        return
    rc, line, out, text = go("bom", True)
    check("★matswap(옛 자리 인자 꼴) · 번들에 BOM → rc 같음 · Bundle cards 줄 같음 · 산출 바이트 같음 · 산출에 BOM 없음",
          rc == p_rc and line == p_line and out == p_out and out is not None and BOM not in out,
          (rc, p_line, line, "산출 %s" % ("같음" if out == p_out else "다름"), text[-200:]))


ALE_MAT = """*MAT_NULL
$      MID        RO
         9 1.290E-12
*EOS_LINEAR_POLYNOMIAL
$    EOSID        C0        C1        C2        C3        C4        C5        C6
         9       0.0       0.0       0.0       0.0       0.4       0.4       0.0
       0.0       0.0
"""


def ale_custom(binary, top):
    """ale 의 사용자 재료 파일 — `material:` 에 경로를 주면 그 파일의 첫 `*MAT_` · `*EOS_` 블록을 옮겨 싣는다."""
    case = Case(binary, os.path.join(top, "ale_custom"), next(o for o in OPS if o["name"] == "ale"))
    for fname, content in (("mat.k", ALE_MAT),
                           ("ale.yaml", "model: box.k\noutput: box_ale.k\nale_parts:\n  - pid: 1\n    material: mat.k\n")):
        with open(os.path.join(case.base, fname), "w", encoding="utf-8") as f:
            f.write(content)
    p_rc, p_text, p_outs = case.go()
    deck = p_outs.get("box_ale.k", b"")
    if not check("ale(재료 파일) · 그대로 rc 0 · 산출에 `*MAT_NULL` · `*EOS_LINEAR_POLYNOMIAL` 이 실린다",
                 p_rc == 0 and b"*MAT_NULL" in deck and b"*EOS_LINEAR_POLYNOMIAL" in deck, p_text[-400:]):
        return
    rc, text, outs = case.go(["mat.k"])
    diff = differs(p_outs, outs)
    carried = sorted(r for r, d in outs.items() if BOM in d)
    check("★ale(재료 파일) · 재료 파일에 BOM → rc 같음 · 산출 바이트 같음(`*MAT_NULL` 이 남는다) · 산출에 BOM 없음",
          rc == p_rc and not diff and not carried, ("rc %d" % rc, "BOM 실린 산출 %s" % carried, diff[:3], text[-200:]))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    only = set(sys.argv[2:])
    unknown = only - {spec["name"] for spec in OPS}
    if unknown:
        print("모르는 op: %s" % " ".join(sorted(unknown)))
        return 2
    gmsh = os.environ.get("KOOREMAPPER_GMSH", "")
    top = tempfile.mkdtemp(prefix="kr_deck_bom_")
    ran = 0
    try:
        for spec in OPS:
            name = spec["name"]
            if only and name not in only:
                continue
            if name in GMSH_OPS and not os.path.isfile(gmsh):
                print("[%s] 건너뜀 — KOOREMAPPER_GMSH 가 없다" % name)
                continue
            root = os.path.join(top, re.sub(r"[^A-Za-z0-9]+", "_", name))
            case = Case(binary, root, spec)
            if not case.cmd or not case.decks:
                shutil.rmtree(root, ignore_errors=True)
                continue
            print("[%s] 덱 %d" % (name, len(case.decks)))
            ran += 1
            p_rc, p_text, p_outs = case.go()
            if not check("%s · 도움말 사례 그대로 rc 0" % name, p_rc == 0, p_text[-400:]):
                shutil.rmtree(root, ignore_errors=True)
                continue
            if name == "apply_carryover_plan":
                carryover(case, (p_rc, p_text, p_outs))
                shutil.rmtree(root, ignore_errors=True)
                continue
            groups = [("전부", case.decks)] + ([(d, [d]) for d in case.decks] if len(case.decks) > 1 else [])
            for label, group in groups:
                rc, text, outs = case.go(group)
                carried = sorted(r for r, d in outs.items() if BOM in d)
                diff = differs(p_outs, outs)
                check("★%s · BOM 덱(%s) → rc 같음 · 산출 바이트 같음 · 산출에 BOM 없음" % (name, os.path.basename(label)),
                      rc == p_rc and not diff and not carried, ("rc %d" % rc, "BOM 실린 산출 %s" % carried, diff[:3], text[-200:]))
                check("★%s · BOM 덱(%s) → 화면이 같다(시각 · 걸린 시간은 가린다)" % (name, os.path.basename(label)),
                      screen(text) == screen(p_text), [(a, b) for a, b in zip(screen(p_text), screen(text)) if a != b][:2])
                if name == "matswap":
                    def bundle(t):
                        return [l for l in t.splitlines() if "bundle:" in l]
                    check("★matswap · BOM 덱(%s) → 화면의 bundle 줄(params · cards)이 같다" % os.path.basename(label),
                          bundle(text) == bundle(p_text) and bundle(text), (bundle(p_text), bundle(text)))
            shutil.rmtree(root, ignore_errors=True)
        if not only or "matswap" in only:
            legacy_matswap(binary, top)
        if not only or "ale" in only:
            ale_custom(binary, top)
    finally:
        shutil.rmtree(top, ignore_errors=True)
    if only:
        check("고른 op 을 모두 돌렸다(%s)" % " ".join(sorted(only)), ran == len(only), ran)
    else:
        check("덱을 받는 op 을 쉰 넘게 돌렸다(카탈로그가 비면 이 시험은 아무것도 재지 않는다)", ran >= 50, ran)

    print()
    if FAILS:
        print("FAIL %d  (OK %d)" % (len(FAILS), len(OKS)))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
