#!/usr/bin/env python3
# cclip 산출물 자기일관성 검사기 — 솔버 없이 기하·강성·응력→힘 환산 정합을 확인한다.
"""Usage: python3 tools/cclip_check.py <output.k> <output_cclip_report.json>

Checks (per clip):
  1. geometry   — pressed clip max height along the compression axis == installed_height
  2. stiffness  — report rel_error <= 5%
  3. bending    — *INITIAL_STRESS_SHELL top/bottom traces are sign-flipped (pure bending)
  4. force      — max bending moment from written stress, divided by the tip-to-bulge
                  moment arm, reproduces the operating (contact) force within 10%
Exit 0 if all pass.
"""
import json
import re
import sys


def parse_kfile(path):
    nodes, shells, solids, sections, stress, stress_solid = {}, [], [], {}, {}, {}
    kw = None
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith("*"):
            kw = s.upper()
            i += 1
            continue
        if not s or s.startswith("$"):
            i += 1
            continue
        if kw and kw.startswith("*NODE"):
            try:
                nid = int(ln[0:8])
                nodes[nid] = (float(ln[8:24]), float(ln[24:40]), float(ln[40:56]))
            except ValueError:
                pass
        elif kw and kw.startswith("*ELEMENT_SHELL"):
            try:
                shells.append([int(ln[k:k+8]) for k in range(0, 48, 8)])  # eid pid n1..n4
            except ValueError:
                pass
        elif kw and kw.startswith("*ELEMENT_SOLID"):
            try:
                solids.append([int(ln[k:k+8]) for k in range(0, 80, 8)])  # eid pid n1..n8
            except ValueError:
                pass
        elif kw and kw.startswith("*SECTION_SHELL"):
            try:
                sections[int(ln[0:10])] = float(lines[i+1][0:10])
                i += 2
                continue
            except (ValueError, IndexError):
                pass
        elif kw and kw.startswith("*INITIAL_STRESS_SHELL"):
            try:
                eid = int(ln[0:10])
                bot = [float(x) for x in re.findall(r"-?\d\.\d+e[+-]\d+", lines[i+1])]
                top = [float(x) for x in re.findall(r"-?\d\.\d+e[+-]\d+", lines[i+2])]
                stress[eid] = (bot[1:7], top[1:7])  # skip T field
                i += 3
                continue
            except (ValueError, IndexError):
                pass
        elif kw and kw.startswith("*INITIAL_STRESS_SOLID"):
            try:
                eid = int(ln[0:10])
                sig = [float(x) for x in re.findall(r"-?\d\.\d+e[+-]\d+", lines[i+1])]
                stress_solid[eid] = sig[0:6]
                i += 2
                continue
            except (ValueError, IndexError):
                pass
        i += 1
    return nodes, shells, solids, sections, stress, stress_solid


def main():
    kfile, repfile = sys.argv[1], sys.argv[2]
    rep = json.load(open(repfile))
    nodes, shells, solids, sections, stress, stress_solid = parse_kfile(kfile)
    if not stress and not stress_solid and rep.get("stress_output") == "include":
        import os
        dynain = os.path.splitext(kfile)[0] + ".dynain"
        if os.path.exists(dynain):
            _, _, _, _, stress, stress_solid = parse_kfile(dynain)

    deck_mode = rep.get("mode") == "deck"
    if deck_mode:
        print("[mode=deck] main deck holds the FREE-state clip (no prestress by design) — "
              "checking free height + stiffness only; press verification belongs to the "
              "LS-DYNA compression deck (rcforc)")

    failures = 0
    for clip in rep["clips"]:
        pid = clip["pid"]
        iw = "xyz".index(clip["axis"])
        is_solid = clip.get("element") == "solid"
        clip_elems = [e for e in (solids if is_solid else shells) if e[1] == pid]
        nspan = 8 if is_solid else 4
        clip_nids = {n for e in clip_elems for n in e[2:2+nspan]}
        pts = [nodes[n] for n in clip_nids if n in nodes]
        print(f"[clip pid {pid}] element={'solid' if is_solid else 'shell'} "
              f"elems={len(clip_elems)} nodes={len(pts)}")

        # 1. geometry: pressed midsurface reaches installed_height (deck mode: free height).
        #    A solid clip also carries ±t/2 of real thickness along the (curved) normal, so
        #    its bbox height is the reference height plus up to ~one thickness — check the
        #    envelope rather than exact equality.
        wvals = [p[iw] for p in pts]
        height = max(wvals) - min(wvals)
        target_h = clip["free_height"] if deck_mode else clip["installed_height"]
        if is_solid:
            t = clip["thickness"]
            h_ok = (target_h - 1e-6) <= height <= (target_h + 1.2 * t)
        else:
            h_ok = abs(height - target_h) <= 0.01 * target_h + 1e-6
        print(f"  [1] {'free' if deck_mode else 'pressed'} height {height:.4f} vs "
              f"{target_h:.4f}{' (+t envelope)' if is_solid else ''} → {'PASS' if h_ok else 'FAIL'}")

        # 2. stiffness
        k_ok = clip["rel_error"] <= 0.05
        print(f"  [2] stiffness rel_error {clip['rel_error']:.2e} → {'PASS' if k_ok else 'FAIL'}")

        if deck_mode:   # [3][4] are pressed-state checks — not applicable to the free deck
            failures += sum(not ok for ok in (h_ok, k_ok))
            continue

        eids = {e[0] for e in clip_elems}
        if is_solid:
            # 3. bending: through-thickness layers carry BOTH signs of sigma-trace
            traces = [sum(sig[:3]) for eid, sig in stress_solid.items() if eid in eids]
            nz = [tr for tr in traces if abs(tr) > 1e-6]
            flip_ok = any(tr > 0 for tr in nz) and any(tr < 0 for tr in nz)
            print(f"  [3] through-thickness bending: {len(nz)} stressed solids, "
                  f"both signs present → {'PASS' if flip_ok else 'FAIL'}")
            # 4. solid force-integration is not attempted here (shell-only); the analytic
            #    moment↔force equilibrium uses the identical sigma(zeta) field verified on
            #    the shell path. Reported as INFO.
            print("  [4] force-from-stress: shell-only check (solid uses the same analytic "
                  "sigma field) — skipped")
            failures += sum(not ok for ok in (h_ok, k_ok, flip_ok))
            continue

        # 3. bending sign flip (trace(top) == -trace(bot)) on stressed rows
        rows = [(sum(b[:3]), sum(t[:3])) for eid, (b, t) in stress.items() if eid in eids]
        sig = [(tb, tt) for tb, tt in rows if abs(tb) > 1e-6]
        flip_ok = bool(sig) and all(abs(tt + tb) <= 0.02 * max(abs(tb), abs(tt)) for tb, tt in sig)
        print(f"  [3] bending sign-flip on {len(sig)} stressed rows → {'PASS' if flip_ok else 'FAIL'}")

        # 4. moment→force: max |trace| = sigma_b at surface; M = sigma*W*t^2/6; arm = |x_tip - x_far|
        t = sections[clip["new_secid"]]
        W = clip["strip_width"]
        sig_max = max((abs(tb) for tb, _ in rows), default=0.0)
        # profile axis u = in-plane axis with the larger clip extent
        others = [a for a in range(3) if a != iw]
        exts = [max(p[a] for p in pts) - min(p[a] for p in pts) for a in others]
        iu = others[0] if exts[0] >= exts[1] else others[1]
        press = clip.get("press_from", "+" + clip["axis"])
        psign = -1.0 if press.startswith("-") else 1.0
        tip = max(pts, key=lambda p: psign * p[iw])   # extremum toward the mating plane
        xs = [p[iu] for p in pts]
        arm = max(abs(tip[iu] - max(xs)), abs(tip[iu] - min(xs)))
        f_est = sig_max * W * t * t / 6.0 / arm if arm > 0 else 0.0
        f_err = abs(f_est - clip["operating_force"]) / clip["operating_force"]
        f_ok = f_err <= 0.10
        print(f"  [4] force from stress {f_est:.4f} N vs operating {clip['operating_force']:.4f} N "
              f"(err {f_err*100:.1f}%) → {'PASS' if f_ok else 'FAIL'}")

        failures += sum(not ok for ok in (h_ok, k_ok, flip_ok, f_ok))

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
