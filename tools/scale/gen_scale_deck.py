#!/usr/bin/env python3
# Q8 규모(13.4M 절점) 합성 덱 생성기 — "스트리밍이다·상수 메모리다" 를 **재기** 위한 것
"""Q8 Close 급 덱을 흉내낸 합성 덱을 만든다 (매뉴얼 §48.9 의 측정을 재현하는 도구).

왜 이것이 리포에 있나 (2026-10-13).

  `cleanup-nodes`·`extract-parts` 는 "2.32GB 덱을 전제로 스트리밍한다" 고 적혀 있었지만
  그것은 **주장**이었다. 요청자의 2.32GB Q8 Close 덱은 개발 호스트에 없다.

  ★그런데 "실제 덱이 없어서 검증 못 했다" 는 **두 가지를 섞은 말**이다 —
    ① 규모에서 도는가 · 메모리가 터지지 않는가 → **합성으로 잴 수 있다**(이 스크립트).
    ② 그쪽 덱의 수치가 맞는가 → 그 덱이 **있어야** 한다.
  섞어 두면 잴 수 있는 것도 안 재게 된다. 그래서 ①을 재는 도구를 남긴다.

측정값(매뉴얼 §48.9, 2026-10-13 · 이 스크립트의 기본 설정):
    덱 1.9GB · 절점 13,368,568(고아 118,568) · 요소 13,082,211 · *INCLUDE 분할
    cleanup-nodes(report)  16.7초 ·  686MB
    cleanup-nodes(safe)    37.0초 · 1.28GB   118,494줄 삭제 · 되읽기 미정의 0
    extract-parts          34.0초 · 1.18GB   미정의 0

⚠ **5GB 가까이 쓴다**(main 1.4G + include 510M + 산출물). 디스크 여유를 보고 돌려라.
   회귀(`tools/regress/`)에 넣지 않은 이유가 그것이다 — 전수 관문이 매번 5GB 를 쓰면 안 된다.

참값은 **여기서 정한다**(생성 시점에 아는 수다) — 그래서 분류를 대조할 수 있다.
    고아 ORPHANS · 그중 CNRB 세트 CNRB_SET_N · 다른 세트 OTHER_SET_N
    → 삭제 가능 = ORPHANS - CNRB_SET_N - OTHER_SET_N

사용:
    python3 -I tools/scale/gen_scale_deck.py [출력폴더]        # 기본 ./koorm_scale
    cd <출력폴더> && printf 'model: main.k\\nreport: r.json\\n' > cn.yaml
    /usr/bin/time -v <KooRemapper> cleanup-nodes cn.yaml
"""
import os
import sys
import time

NX, NY, NZ = 250, 250, 212          # 13,250,000 절점 — 요소가 **전부** 쓴다
ORPHANS = 118_568                   # 요청서가 보고한 고아 수와 같은 모양
CNRB_SET_N = 71                     # CNRB 가 세트로 가리키는 고아(요청서의 71건 경로)
OTHER_SET_N = 3                     # 다른 세트에 든 고아
CHUNK = 200_000                     # 줄을 묶어 쓴다 — 한 줄씩 쓰면 40M 줄을 못 끝낸다

USED = NX * NY * NZ
ORPH0 = USED + 1


def nid(i, j, k):
    return 1 + i + j * NX + k * NX * NY


def write_nodes(f, lo, hi):
    """`*NODE` (I8,3F16) — 격자 좌표를 ID 에서 되돌려 계산한다(배열을 들지 않는다)."""
    buf = []
    for n in range(lo, hi):
        z, r = divmod(n - 1, NX * NY)
        y, x = divmod(r, NX)
        buf.append("%8d%16.7f%16.7f%16.7f\n" % (n, x * 0.5, y * 0.5, z * 0.5))
        if len(buf) >= CHUNK:
            f.write("".join(buf))
            buf.clear()
    f.write("".join(buf))


def write_elems(f, k0, k1, eid):
    """`*ELEMENT_SOLID` 표준 2줄 포맷 — Card 1 = EID PID, Card 2 = N1..N8."""
    buf = []
    for k in range(k0, k1):
        for j in range(NY - 1):
            for i in range(NX - 1):
                buf.append("%8d%8d\n" % (eid, 1))
                buf.append("%8d%8d%8d%8d%8d%8d%8d%8d\n" % (
                    nid(i, j, k), nid(i + 1, j, k), nid(i + 1, j + 1, k), nid(i, j + 1, k),
                    nid(i, j, k + 1), nid(i + 1, j, k + 1), nid(i + 1, j + 1, k + 1),
                    nid(i, j + 1, k + 1)))
                eid += 1
        if len(buf) >= 2 * CHUNK:
            f.write("".join(buf))
            buf.clear()
    f.write("".join(buf))
    return eid


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "koorm_scale"
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    half = NZ // 2

    with open(os.path.join(out, "main.k"), "w", newline="\n") as f:
        f.write("*KEYWORD\n*NODE\n")
        write_nodes(f, 1, USED + 1)
        # 고아 — x 를 멀리 둬서 bbox 가 벌어지게(요청서의 '낙하판이 53mm 밖' 상황을 흉내낸다)
        buf = []
        for t in range(ORPHANS):
            buf.append("%8d%16.7f%16.7f%16.7f\n" % (ORPH0 + t, -500.0 - (t % 100), 0.0, 0.0))
            if len(buf) >= CHUNK:
                f.write("".join(buf))
                buf.clear()
        f.write("".join(buf))
        print("[%6.1fs] 절점 %d + 고아 %d" % (time.time() - t0, USED, ORPHANS), flush=True)

        f.write("*ELEMENT_SOLID\n")
        eid = write_elems(f, 0, half, 1)
        print("[%6.1fs] 주 덱 요소 %d" % (time.time() - t0, eid - 1), flush=True)

        f.write("*PART\nbody\n%10d%10d%10d\n" % (1, 1, 1))
        f.write("*SECTION_SOLID\n%10d%10d\n" % (1, 1))
        f.write("*MAT_ELASTIC\n         1  7.85E-9  210000     0.3\n")
        # ★함정 — 덱 **전체 절점**을 담은 세트. 이것을 참조로 세면 고아가 전부 가려진다
        #   (요청자가 밖에서 시도해 실패한 원인이 정확히 이것이다 — 매뉴얼 §47.1).
        f.write("*SET_NODE_LIST\n%10d\n" % 9000)
        buf = []
        for s in range(1, USED + ORPHANS + 1, 8):
            ids = [n if n <= USED else ORPH0 + (n - USED - 1)
                   for n in range(s, min(s + 8, USED + ORPHANS + 1))]
            buf.append("".join("%10d" % n for n in ids) + "\n")
            if len(buf) >= CHUNK:
                f.write("".join(buf))
                buf.clear()
        f.write("".join(buf))
        # CNRB 가 가리키는 세트 + 다른 세트 — 전이 keep 경로를 규모에서도 확인한다
        f.write("*SET_NODE_LIST\n%10d\n" % 2001)
        ids = list(range(ORPH0, ORPH0 + CNRB_SET_N))
        for s in range(0, len(ids), 8):
            f.write("".join("%10d" % n for n in ids[s:s + 8]) + "\n")
        f.write("*SET_NODE_LIST\n%10d\n" % 2002)
        ids2 = list(range(ORPH0 + CNRB_SET_N, ORPH0 + CNRB_SET_N + OTHER_SET_N))
        f.write("".join("%10d" % n for n in ids2) + "\n")
        f.write("*CONSTRAINED_NODAL_RIGID_BODY\n%10d%10d%10d\n" % (1, 0, 2001))
        f.write("*BOUNDARY_SPC_SET\n%10d%10d%10d%10d%10d%10d%10d%10d\n"
                % (2002, 0, 1, 1, 1, 1, 1, 1))
        f.write("*INCLUDE\ninc_rest.k\n*END\n")

    # 나머지 요소를 인클루드로 — 인클루드를 읽지 않으면 그 절점이 전부 고아로 보인다
    with open(os.path.join(out, "inc_rest.k"), "w", newline="\n") as f:
        f.write("*KEYWORD\n*ELEMENT_SOLID\n")
        e2 = write_elems(f, half, NZ - 1, eid)
        f.write("*END\n")
    print("[%6.1fs] 인클루드 요소 %d" % (time.time() - t0, e2 - eid), flush=True)

    print("[%6.1fs] 완료 — 참값: 고아 %d · CNRB세트 %d · 다른세트 %d · **삭제 가능 %d**"
          % (time.time() - t0, ORPHANS, CNRB_SET_N, OTHER_SET_N,
             ORPHANS - CNRB_SET_N - OTHER_SET_N), flush=True)
    for n in ("main.k", "inc_rest.k"):
        p = os.path.join(out, n)
        print("   %-12s %.1f MB" % (n, os.path.getsize(p) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
