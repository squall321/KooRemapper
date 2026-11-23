#!/usr/bin/env python3
# battery 덱이 모드 · 선택마다 없는 재질 · 섹션 · 세트를 가리키지 않는지 info --strict 로 재는 회귀 시험
"""battery 덱의 참조 (2026-11-22 · 3차 5판 L-07).

왜 이 시험이 있나.

  적층(stacked) 기본 설정 덱 둘이 LS-DYNA 가 멈추는 참조를 rc 0 으로 냈다.
  - 전해질 PART(13)가 공기주머니 모드에서만 쓰는 MID 8 을 가리켰다 — 공기주머니가 아니면 MID 8 이 없다.
  - side 모드의 `*BOUNDARY_SPC_SET` 이 바닥판 세트 3 을 묶는데 side 는 바닥판을 짓지 않아 세트 3 이 없었다.
  이제 전해질은 솔리드 전해질 재질을, side 는 권취처럼 바닥판도 짓는다.
  같은 꼴이 기본 밖에도 있었다(선택 하나씩 바꿔 96 조합을 돌려 찾았다).
  - no_impactor: true(dent · side)는 압입자 · 바닥판을 짓지 않고도 세트 2 · 3 을 SPC · 처방 운동으로 묶었다 — 이제 묶지 않는다.
  - 권취 core_fill: true 의 Wound_Electrolyte 가 solid_electrode 일 때만 적는 섹션 33 을 가리켰다 — 이제 섹션을 적는다.
  - 모르는 mode(`nail` 등)는 적층에서 압입자 없이 세트를 묶었고 권취에서 움직이지 않는 압입자를 지었다 — 이제 rc 1(카탈로그의 enum).

무엇을 보나.
  적층 모드 dent · side · bare · swell × no_pcm true · false 여덟 덱 — 각각 rc 0 · `info --strict` rc 0 · 참조 무결성 OK
  ★side 덱에 바닥판 PART 가 있고 SPC 가 묶는 절점 세트가 다 덱에 있다
  ★적층 · 권취 no_impactor: true(dent · side) · 권취 core_fill: true(dent) — `info --strict` rc 0 · no_impactor 면 SPC_SET 이 없다
  ★mode: nail → rc 1 · 허용값을 말한다 · 덱 없음
  ★적층 탭을 짓지 않는 덱(no_pcm · 단독 swell · bare)은 탭 PART 20 · 21 을 PART 카드에도 파트 세트에도 쓰지 않는다(3차 7판)
  ★권취 나선 판(wound.flat: false) dent · swell — `info --strict` rc 0(3차 6판 — 전해질 채움 PART 의 섹션 33 을 쓴다)

usage: test_battery_deck_refs.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-96s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def kw_blocks(path, prefix):
    """prefix 로 시작하는 키워드 블록의 자료 줄(주석 뺀) 목록들 — `_TITLE` 이면 제목 줄을 뺀다."""
    out, cur, skip = [], None, 0
    for l in open(path, encoding="utf-8", errors="replace").read().splitlines():
        if l.startswith("*"):
            k = l.split()[0].upper()
            cur = [] if k.startswith(prefix) else None
            skip = 1 if k.endswith("_TITLE") else 0
            if cur is not None:
                out.append(cur)
            continue
        if cur is not None and not l.startswith("$") and skip:
            skip = 0
            cur.append(l)   # 제목 줄도 남긴다(PART 는 제목이 첫 줄) — 번호 줄은 그 다음
            continue
        if cur is not None and not l.startswith("$"):
            cur.append(l)
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="bstk_")
    try:
        for mode in ("dent", "side", "bare", "swell"):
            for no_pcm in ("true", "false"):
                d = os.path.join(root, "%s_%s" % (mode, no_pcm))
                os.makedirs(d)
                with open(os.path.join(d, "b.yaml"), "w", encoding="utf-8") as f:
                    f.write("output: bt\nmodel_type: stacked\ntier: -1\nmode: %s\nno_pcm: %s\n" % (mode, no_pcm))
                p = subprocess.run([binary, "battery", "b.yaml"], cwd=d, capture_output=True, text=True, timeout=900,
                                   encoding="utf-8", errors="replace")
                ks = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".k")]
                if not check("%s · no_pcm %s → rc 0 · 덱 하나" % (mode, no_pcm), p.returncode == 0 and len(ks) == 1,
                             (p.returncode, ks, (p.stdout + p.stderr)[-300:])):
                    continue
                q = subprocess.run([binary, "info", ks[0], "--strict"], cwd=d, capture_output=True, text=True,
                                   timeout=900, encoding="utf-8", errors="replace")
                qo = q.stdout + q.stderr
                bad = [l.strip() for l in qo.splitlines() if "정의되지 않" in l or "미정의" in l and "0건" not in l]
                check("★%s · no_pcm %s → info --strict rc 0 · 참조 무결성 OK(예전엔 MID 8 · 세트 3 이 없었다)"
                      % (mode, no_pcm), q.returncode == 0 and "참조 무결성 OK" in qo, (q.returncode, bad[:4]))
                # 탭을 짓지 않는 덱(no_pcm — 단독 swell · bare 는 저절로)은 탭 PART 카드 · 세트 칸도 쓰지 않는다(3차 7판 L-28)
                pids = {int(bl[1][0:10]) for bl in kw_blocks(ks[0], "*PART") if len(bl) > 1 and bl[1][0:10].strip().isdigit()}
                in_sets = set()
                for bl in kw_blocks(ks[0], "*SET_PART_LIST"):
                    for row in bl[2:]:
                        in_sets |= {int(row[i:i + 10]) for i in range(0, len(row.rstrip()), 10) if row[i:i + 10].strip().isdigit()}
                no_tabs = no_pcm == "true" or mode in ("bare", "swell")
                has = {20, 21} & (pids | in_sets)
                check("★%s · no_pcm %s → 탭 PART 20 · 21 이 %s(PART 카드 · 파트 세트 — 예전엔 요소 없이도 썼다)"
                      % (mode, no_pcm, "없다" if no_tabs else "있다"), (not has) if no_tabs else has == {20, 21},
                      (sorted(has), sorted(pids)[:12]))
                if mode != "side":
                    continue
                parts = kw_blocks(ks[0], "*PART")
                ground = [b for b in parts if b and b[0].strip().lower().startswith("ground")]
                spc_sids = {int(b[0][0:10]) for b in kw_blocks(ks[0], "*BOUNDARY_SPC_SET") if b}
                set_ids = {int(b[1][0:10]) for b in kw_blocks(ks[0], "*SET_NODE_LIST_TITLE") if len(b) > 1}
                set_ids |= {int(b[0][0:10]) for b in kw_blocks(ks[0], "*SET_NODE_LIST") if b and b[0][0:10].strip().isdigit()}
                check("★side · no_pcm %s → 바닥판 PART 가 있고 SPC 가 묶는 세트 %s 가 다 덱에 있다" % (no_pcm, sorted(spc_sids)),
                      bool(ground) and spc_sids and spc_sids <= set_ids,
                      ([b[0] for b in parts][:20], sorted(spc_sids), sorted(set_ids)))
        def gen(tag, text):
            d = os.path.join(root, tag)
            os.makedirs(d)
            with open(os.path.join(d, "b.yaml"), "w", encoding="utf-8") as f:
                f.write(text)
            p = subprocess.run([binary, "battery", "b.yaml"], cwd=d, capture_output=True, text=True, timeout=900,
                               encoding="utf-8", errors="replace")
            ks = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".k")]
            return p.returncode, p.stdout + p.stderr, ks

        def strict(k):
            q = subprocess.run([binary, "info", k, "--strict"], capture_output=True, text=True, timeout=900,
                               encoding="utf-8", errors="replace")
            qo = q.stdout + q.stderr
            return q.returncode == 0 and "참조 무결성 OK" in qo, [l.strip() for l in qo.splitlines() if "정의되지 않" in l][:3]

        for mt in ("stacked", "wound"):
            for mode in ("dent", "side"):
                rc, out, ks = gen("ni_%s_%s" % (mt, mode),
                                  "output: bt\nmodel_type: %s\ntier: -1\nmode: %s\nno_impactor: true\n" % (mt, mode))
                ok, bad = strict(ks[0]) if rc == 0 and len(ks) == 1 else (False, out[-300:])
                spc = kw_blocks(ks[0], "*BOUNDARY_SPC_SET") if len(ks) == 1 else ["?"]
                check("★%s · %s · no_impactor → info --strict rc 0 · SPC_SET 없음(예전엔 없는 세트 2 · 3 을 묶었다)" % (mt, mode),
                      ok and not spc, (rc, bad, len(spc)))
        for mode in ("dent", "swell"):
            rc, out, ks = gen("spiral_%s" % mode, "output: bt\nmodel_type: wound\ntier: -1\nmode: %s\nwound:\n  flat: false\n" % mode)
            ok, bad = strict(ks[0]) if rc == 0 and len(ks) == 1 else (False, out[-300:])
            check("★wound · 나선 판(flat: false) · %s → info --strict rc 0(3차 6판 — 예전엔 전해질 PART 가 없는 섹션 33 을 가리켰다)" % mode,
                  ok, (rc, bad))
        rc, out, ks = gen("cf_wound", "output: bt\nmodel_type: wound\ntier: -1\nmode: dent\ncore_fill: true\n")
        ok, bad = strict(ks[0]) if rc == 0 and len(ks) == 1 else (False, out[-300:])
        check("★wound · dent · core_fill → info --strict rc 0(예전엔 PART 가 없는 섹션 33 을 가리켰다)", ok, (rc, bad))
        for mt in ("stacked", "wound"):
            rc, out, ks = gen("nail_%s" % mt, "output: bt\nmodel_type: %s\ntier: -1\nmode: nail\n" % mt)
            check("★%s · mode: nail → rc 1 · 허용값과 indenter type 을 말한다 · 덱 없음(예전엔 rc 0)" % mt,
                  rc == 1 and "모르는 mode" in out and "swell" in out and "type: nail" in out and not ks, (rc, out[-300:]))
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
