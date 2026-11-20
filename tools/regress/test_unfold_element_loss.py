#!/usr/bin/env python3
# unfold 가 요소를 말없이 잃지 않는지 — 색인이 겹친 덱은 거절하고 멀쩡한 덱은 요소를 전부 쓰는지 보는 회귀 시험
"""unfold 의 요소 보존 (2026-11-20 · 11-08 에 「다음 판」 으로 미뤘던 결함).

왜 이 시험이 있나.

  unfold 가 굽은 덱의 요소를 rc 0 으로 버렸다(`examples/foldable_display/test_small_bent.k` 100 → 53 ·
  `examples/wave/wave_bent.k` 250 → 238). 구조 격자 색인기가 이웃마다 「중심 방향과 가장 가까운 축」 을 골라 번호를 주는데
  고른 칸이 이미 찼는지 보지 않아, 두 요소가 같은 (i,j,k) 칸에 놓이면 평판을 지을 때 칸마다 하나만 남았다. 잃은 수는 정확히
  겹친 칸 수였다(탐침 실측). 펼친 덱은 그럴듯하게 돌고, 요소가 빠진 자리는 한참 뒤에 보인다.

  이제 색인기는 칸이 겹치면 실패하고(수를 싣는다), unfold 는 지은 요소 수가 읽은 수와 다르면 쓰지 않는다.

무엇을 보나.
  불변식 — **unfold 는 rc ≠ 0 이거나 쓴 요소 수 = 읽은 요소 수다.** 요소 수는 덱의 `*ELEMENT_SOLID` 줄을 직접 센다
  (연산이 찍는 수를 믿지 않는다).
  U-1 · U-2 색인이 겹치는 덱 둘 — 불변식. 거절이면 산출 파일이 없고 글에 겹친 수가 있다
  U-3 · U-4 대조(`foldable_bent.k` 3,750 요소 · 상자 10×5×2) — rc 0 · 요소 전부
  U-5 구멍 난 격자(상자에서 안쪽 요소 하나 · 둘을 뺀 것) — 남은 요소 전부(색인이 안 겹치면 거절하지 않는다)
  U-6 이 도구의 `generate` 가 지은 굽은 덱 둘(helix 20×5×3 · wave 10×10×2 — 예전엔 300 → 127 · 200 → 127 로 썼다) — 불변식.
      예제 파일만의 일이 아니다. 굽힘 종류 11 × 크기 3 가운데 이 둘이 겹쳤다
  M-1 · M-2 같은 두 덱을 `map` 의 굽은 기준으로 — 지나면 안 된다. 거절 글이 색인 겹침을 말한다(예전엔 뒤의 모서리 절점
        검사에 걸려 「only 1/8 corner nodes found」 로 끝났다). 색인기가 이 덱을 제대로 읽게 되면 rc 0 도 받는다

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
SLOT = "share an (i,j,k) slot"

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


def unfold_case(binary, d, name, deck, expect_full):
    """불변식을 재고, expect_full 이면 rc 0 · 요소 전부까지 본다."""
    out = os.path.join(d, name + "_flat.k")
    read = solid_count(deck)
    rc, text = run(binary, d, "unfold", deck, out)
    wrote = solid_count(out) if os.path.exists(out) else None
    check("%s 불변식 — rc ≠ 0 이거나 쓴 요소 수 = 읽은 요소 수(%d)" % (name, read),
          read > 0 and (rc != 0 or wrote == read), (rc, read, wrote, text[-300:]))
    if expect_full:
        check("%s rc 0 · 요소 %d 전부" % (name, read), rc == 0 and wrote == read, (rc, wrote, text[-300:]))
    elif rc != 0:
        check("%s 거절이면 산출이 없고 글이 겹친 수를 말한다" % name, wrote is None and SLOT in text, (wrote, text[-300:]))


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
                         ("foldable", "foldable_display/foldable_bent.k")):
            decks[key] = shutil.copy(os.path.join(ex, *rel.split("/")), root)
        with open(os.path.join(root, "box.yaml"), "w", encoding="utf-8") as f:
            f.write(BOX)
        rc, out = run(binary, root, "generate", "box", "box.yaml")
        if rc != 0:
            raise RuntimeError("generate box 실패: " + out[-300:])
        box = os.path.join(root, "box.k")

        unfold_case(binary, root, "U-1 test_small_bent", decks["small"], False)
        unfold_case(binary, root, "U-2 wave_bent", decks["wave"], False)
        unfold_case(binary, root, "U-3 foldable_bent", decks["foldable"], True)
        unfold_case(binary, root, "U-4 상자 10×5×2", box, True)
        for tag, eids in (("하나", {23}), ("둘", {23, 24})):
            holed = os.path.join(root, "hole_%d.k" % len(eids))
            drop_elements(box, holed, eids)
            unfold_case(binary, root, "U-5 구멍 %s" % tag, holed, True)

        for kind, (ni, nj, nk) in (("helix", (20, 5, 3)), ("wave", (10, 10, 2))):
            rc, out = run(binary, root, "generate", "--dim-i", str(ni), "--dim-j", str(nj), "--dim-k", str(nk), kind, "gen_" + kind)
            bent = os.path.join(root, "gen_%s_bent.k" % kind)
            if rc != 0 or not os.path.exists(bent):
                raise RuntimeError("generate %s 실패: %s" % (kind, out[-300:]))
            unfold_case(binary, root, "U-6 generate %s %d×%d×%d" % (kind, ni, nj, nk), bent, False)

        for name, bent, flat in (("M-1 test_small_bent", "small", "small_flat"), ("M-2 wave_bent", "wave", "wave_flat")):
            out_path = os.path.join(root, name.split()[0] + "_out.k")
            rc, text = run(binary, root, "map", decks[bent], decks[flat], out_path)
            check("%s map 굽은 기준 — 거절이면 색인 겹침을 말한다(산출 없음)" % name,
                  rc == 0 or (SLOT in text and not os.path.exists(out_path)), (rc, text[-300:]))
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
