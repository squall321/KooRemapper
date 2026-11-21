#!/usr/bin/env python3
# unfold 가 요소를 잃거나 바꿔 끼우지 않는지 — 접힌 덱도 요소 · 절점을 그대로 펼치고, 한 블록이 아닌 덱은 거절하는지 보는 회귀 시험
"""unfold 의 요소 · 절점 보존 (2026-11-20 관문 → 11-21 색인 · 절점 순서를 면 위상으로).

왜 이 시험이 있나.

  ① 요소를 잃었다(11-20 에 막음). unfold 가 굽은 덱의 요소를 rc 0 으로 버렸다(`examples/foldable_display/test_small_bent.k`
     100 → 53 · `examples/wave/wave_bent.k` 250 → 238). 구조 격자 색인기가 이웃마다 「중심 방향과 가장 가까운 축」 을 골라
     번호를 줘서 접힌 자리의 두 요소가 같은 (i,j,k) 칸에 놓였고, 평판을 지을 때 칸마다 하나만 남았다. 11-20 에는 칸이 겹치면
     거절하는 관문만 세웠다 — 그 덱들은 rc 1 이었다.
  ② 요소를 바꿔 끼웠다(11-21 에 찾음). 색인이 멀쩡해도 요소의 절점 순서를 「이웃 중심이 어느 쪽인가」 로 어림해, 바짝 접힌
     자리에서 엉뚱한 절점이 코너를 차지했다. 평판 생성이 그 코너에 새 절점 번호를 지어 붙여, rc 0 인데 **원본에 없던 절점
     묶음을 가진 요소**가 나갔다(`examples/teardrop/teardrop_bent.k` 250 요소 가운데 15 · 이 도구의 `generate scurve
     20×5×3` 300 가운데 80 · 새 절점 26). 요소 수는 맞아서 ① 의 관문은 이것을 못 잡는다.

  이제 색인(전파)과 절점 순서를 **맞닿은 면**만으로 정한다 — 접힌 덱이 그대로 펼쳐지고, 면이 한 블록으로 닫히지 않는 덱은
  어림하지 않고 거절한다.

무엇을 보나.
  불변식 I-1 — **unfold 는 rc ≠ 0 이거나 쓴 요소 수 = 읽은 요소 수다.** 요소 수는 덱의 `*ELEMENT_SOLID` 줄을 직접 센다
  (연산이 찍는 수를 믿지 않는다).
  불변식 I-2 — **rc 0 이면 절점 번호 집합 · 요소 번호 집합이 원본과 같고, 요소마다 절점 묶음이 원본과 같고(새 절점 없음 ·
  바꿔 끼움 없음), 펼친 요소의 야코비안이 전부 양수다.**
  U-1 · U-2 접힌 덱 둘(11-20 에는 거절하던 것) — rc 0 · 요소 전부 · I-2
  U-3 · U-4 대조(`foldable_bent.k` 3,750 요소 · 상자 10×5×2) — rc 0 · 요소 전부 · I-2
  U-5 구멍 난 격자(상자에서 안쪽 요소 하나 · 둘을 뺀 것) — 남은 요소 전부 · I-2
  U-6 이 도구의 `generate` 가 지은 굽은 덱 둘(helix 20×5×3 · wave 10×10×2 — 처음엔 300 → 127 · 200 → 127 로 썼고 11-20
      에는 거절했다) — rc 0 · 요소 전부 · I-2
  U-7 `teardrop_bent.k` · U-8 `generate` teardrop 기본 크기 · scurve 20×5×3 — ② 의 덱. 예전에도 rc 0 · 요소 수가 맞았다.
      I-2 가 잡는다
  R-1 떨어진 두 덩어리(`tests/offset/regression/05_contact_mode.k`) — rc ≠ 0 · 산출 없음 · 글이 못 닿은 요소를 말한다
  M-1 · M-2 U-1 · U-2 의 덱을 `map` 의 굽은 기준으로 — rc 0 · 산출의 요소 번호 · 절점 묶음이 평판 덱과 같고 야코비안이 전부
        양수(예전엔 「only 1/8 corner nodes found」, 11-20 에는 색인 겹침으로 rc 1)

usage: test_unfold_element_loss.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FAILS, OKS = [], []

BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\n"
       "mid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-500:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def solid_count(path):
    """덱의 `*ELEMENT_SOLID` 요소 수 — 한 줄 꼴(칸 열)과 두 줄 꼴(EID · PID 줄 + 절점 줄)을 다 센다."""
    n, in_block, skip = 0, False, False
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("*"):
                in_block, skip = line.upper().startswith("*ELEMENT_SOLID"), False
                continue
            if not in_block or not line.strip() or line.startswith("$"):
                continue
            if skip:
                skip = False
                continue
            n += 1
            skip = len(line.split()) == 2
    return n


def read_deck(path):
    """절점 {번호: 좌표} · 솔리드 {번호: 절점 여덟} — 폭 8 칸 열(쉼표면 쉼표로) · 한 줄 꼴과 두 줄 꼴."""
    nodes, elems, mode, pend = {}, {}, None, None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("$") or not line.strip():
                continue
            if line.startswith("*"):
                kw = line.strip().upper()
                mode, pend = ("n" if kw == "*NODE" else "e" if kw == "*ELEMENT_SOLID" else None), None
            elif mode == "n":
                if "," in line:
                    t = line.split(",")
                    nodes[int(t[0])] = (float(t[1]), float(t[2]), float(t[3]))
                else:
                    nodes[int(line[0:8])] = (float(line[8:24]), float(line[24:40]), float(line[40:56]))
            elif mode == "e":
                if "," in line:
                    fs = [int(t) for t in line.split(",") if t.strip()]
                else:
                    fs = [int(line[i:i + 8]) for i in range(0, len(line.rstrip()), 8) if line[i:i + 8].strip()]
                if pend is not None:
                    elems[pend], pend = fs[:8], None
                elif len(fs) >= 10:
                    elems[fs[0]] = fs[2:10]
                else:
                    pend = fs[0]
    return nodes, elems


def jacobian(nodes, conn):
    """요소 중심의 야코비안 행렬식(LS-DYNA 절점 순서) — 양수면 뒤집히지 않았다."""
    p = [nodes[n] for n in conn]
    a, b, c = ([sum(s[q] * p[q][x] for q in range(8)) / 8.0 for x in range(3)]
               for s in ((-1, 1, 1, -1, -1, 1, 1, -1), (-1, -1, 1, 1, -1, -1, 1, 1), (-1, -1, -1, -1, 1, 1, 1, 1)))
    return a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])


def drop_elements(src, dst, eids):
    """상자 덱(한 줄 꼴 · 폭 8)에서 그 번호의 요소 줄을 뺀다."""
    out, in_block = [], False
    with open(src, encoding="utf-8") as f:
        for line in f.read().split("\n"):
            if line.startswith("*"):
                in_block = line.startswith("*ELEMENT_SOLID")
            elif in_block and line.strip() and not line.startswith("$") and int(line[:8]) in eids:
                continue
            out.append(line)
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def unfold_case(binary, d, name, deck):
    """I-1 · rc 0 · 요소 전부 · I-2 를 잰다."""
    out = os.path.join(d, name.split()[0] + "_" + os.path.basename(deck)[:-2] + "_flat.k")
    read = solid_count(deck)
    rc, text = run(binary, d, "unfold", deck, out)
    wrote = solid_count(out) if os.path.exists(out) else None
    check("%s I-1 — rc ≠ 0 이거나 쓴 요소 수 = 읽은 요소 수(%d)" % (name, read),
          read > 0 and (rc != 0 or wrote == read), (rc, read, wrote, text[-300:]))
    if not check("%s rc 0 · 요소 %d 전부" % (name, read), rc == 0 and wrote == read, (rc, wrote, text[-300:])):
        return
    sn, se = read_deck(deck)
    on, oe = read_deck(out)
    check("%s I-2 절점 번호 · 요소 번호 집합이 원본과 같다(새 절점 없음)" % name,
          len(se) == read and set(on) == set(sn) and set(oe) == set(se),
          (len(se), len(sn), len(on), sorted(set(on) - set(sn))[:5], sorted(set(sn) - set(on))[:5]))
    rewired = sorted(e for e in se if e in oe and set(oe[e]) != set(se[e]))
    check("%s I-2 요소마다 절점 묶음이 원본과 같다(바꿔 끼움 없음)" % name, not rewired, (len(rewired), rewired[:8]))
    flipped = sorted(e for e, conn in oe.items() if not all(n in on for n in conn) or jacobian(on, conn) <= 0)
    check("%s I-2 펼친 요소의 야코비안이 전부 양수" % name, not flipped, (len(flipped), flipped[:8]))


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="unfold_loss_")
    try:
        ex = os.path.join(REPO, "examples")
        decks = {}
        for key, rel in (("small", "foldable_display/test_small_bent.k"), ("small_flat", "foldable_display/test_small_flat_fine.k"),
                         ("wave", "wave/wave_bent.k"), ("wave_flat", "wave/wave_flat_fine.k"),
                         ("foldable", "foldable_display/foldable_bent.k"), ("teardrop", "teardrop/teardrop_bent.k")):
            decks[key] = shutil.copy(os.path.join(ex, *rel.split("/")), root)
        decks["two_bodies"] = shutil.copy(os.path.join(REPO, "tests", "offset", "regression", "05_contact_mode.k"), root)
        with open(os.path.join(root, "box.yaml"), "w", encoding="utf-8") as f:
            f.write(BOX)
        rc, out = run(binary, root, "generate", "box", "box.yaml")
        if rc != 0:
            raise RuntimeError("generate box 실패: " + out[-300:])
        box = os.path.join(root, "box.k")

        unfold_case(binary, root, "U-1 test_small_bent", decks["small"])
        unfold_case(binary, root, "U-2 wave_bent", decks["wave"])
        unfold_case(binary, root, "U-3 foldable_bent", decks["foldable"])
        unfold_case(binary, root, "U-4 상자 10×5×2", box)
        for tag, eids in (("하나", {23}), ("둘", {23, 24})):
            holed = os.path.join(root, "hole_%d.k" % len(eids))
            drop_elements(box, holed, eids)
            unfold_case(binary, root, "U-5 구멍 %s" % tag, holed)

        unfold_case(binary, root, "U-7 teardrop_bent", decks["teardrop"])
        for case, kind, dims in (("U-6", "helix", (20, 5, 3)), ("U-6", "wave", (10, 10, 2)),
                                 ("U-8", "teardrop", None), ("U-8", "scurve", (20, 5, 3))):
            size = [] if dims is None else ["--dim-i", str(dims[0]), "--dim-j", str(dims[1]), "--dim-k", str(dims[2])]
            stem = "gen_%s_%s" % (kind, "def" if dims is None else "x".join(map(str, dims)))
            rc, out = run(binary, root, "generate", *size, kind, stem)
            bent = os.path.join(root, stem + "_bent.k")
            if rc != 0 or not os.path.exists(bent):
                raise RuntimeError("generate %s 실패: %s" % (kind, out[-300:]))
            unfold_case(binary, root, "%s generate %s %s" % (case, kind, "기본 크기" if dims is None else "%d×%d×%d" % dims), bent)

        out_path = os.path.join(root, "R-1_flat.k")
        rc, text = run(binary, root, "unfold", decks["two_bodies"], out_path)
        check("R-1 떨어진 두 덩어리 — rc ≠ 0 · 산출 없음 · 글이 못 닿은 요소를 말한다",
              rc != 0 and not os.path.exists(out_path) and "was not indexed" in text, (rc, os.path.exists(out_path), text[-300:]))

        for name, bent, flat in (("M-1 test_small_bent", "small", "small_flat"), ("M-2 wave_bent", "wave", "wave_flat")):
            out_path = os.path.join(root, name.split()[0] + "_out.k")
            rc, text = run(binary, root, "map", decks[bent], decks[flat], out_path)
            if not check("%s map 굽은 기준 — rc 0 · 산출 있음" % name, rc == 0 and os.path.exists(out_path), (rc, text[-300:])):
                continue
            fn, fe = read_deck(decks[flat])
            on, oe = read_deck(out_path)
            check("%s map 산출의 요소 번호 · 절점 묶음이 평판 덱(%d 요소)과 같다" % (name, len(fe)),
                  len(fe) > 0 and set(on) == set(fn) and oe == fe, (len(fe), len(oe), len(fn), len(on)))
            flipped = sorted(e for e, conn in oe.items() if jacobian(on, conn) <= 0)
            check("%s map 산출의 야코비안이 전부 양수" % name, not flipped, (len(flipped), flipped[:8]))
    finally:
        shutil.rmtree(root, ignore_errors=True)
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
