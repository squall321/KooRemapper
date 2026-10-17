#!/usr/bin/env python3
# cleanup-nodes 가 '전체 절점 세트' 함정에 빠지지 않고, 지운 뒤 덱이 멀쩡함을 스스로 증명하는지
"""`cleanup-nodes` 계약 (2026-10-11).

왜 이 시험이 있나.

  요청자(CAE그룹 요청서 v1.0)는 이 일을 덱 밖에서 한 번 시도했고 **실패했다** —
  "비-`*NODE`/`*ELEMENT_` 줄에서 8칸·10칸·공백 분리로 숫자를 전부 긁었더니 118,568개
  **전부가 참조됨**으로 나왔다."

  ★그 실패의 원인은 '숫자를 긁은 것' 이 아니라 **`*SET_NODE_*` 블록까지 긁은 것**이다.
  운영 덱에는 보통 '전체 절점' 세트가 있고 그 블록은 모든 절점 ID 를 글자 그대로 담는다.
  그래서 이 시험의 A 절은 **그 함정이 든 덱**을 만들어 고아가 가려지지 않는지 본다.

  그리고 '세트 멤버십은 참조가 아니다' 로만 두면 반대로 깨진다 — CNRB 는 절점을 NSID 로
  가리키므로(요청서의 71건) **세트를 이름하는 카드가 있으면 멤버를 전이로 남겨야** 한다.
  A-4·H 절이 그 전이를 못 박는다.

  ⚠ 이 시험의 픽스처는 **합성이다.** 요청서의 실측 분류(CNRB 71 · 다른 세트 3 ·
  삭제 가능 118,529)는 2.32GB Q8 덱이 이 호스트에 없어 재현하지 못했다 — **실제 덱 미검증**.
  여기서 못 박는 것은 분류의 *수*가 아니라 분류의 *규칙*이다.

요청서 §6 함정을 그대로 채택한다.
  · C 절 — 절점 ID 8자리가 8칸을 꽉 채워 공백이 사라진다(`split()` 이면 연결성이 뒤섞인다)
  · D 절 — CRLF 보존(산출에 홀로 선 LF 0)
  · E 절 — 고차 솔리드의 절점 카드가 **두 줄**이다(한 줄만 읽으면 12개가 고아로 보인다)
  · F 절 — `*INCLUDE` 를 읽지 않으면 그 안이 쓰는 절점을 고아로 본다(닫힘은 정본 — 깊이 · `␣+` 이음 · 인클루드 안 `*END`)
  · H 절 — `_TITLE` 제목줄이 SID 줄을 한 줄 밀어낸다

usage: test_cleanup_nodes.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

FAILS = []


def check(name, cond, detail=""):
    print("  %-70s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:300]) if detail else ""))


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], capture_output=True, text=True, timeout=600, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def write(path, text, newline="\n"):
    with open(path, "w", newline=newline) as f:
        f.write(text)


def nodeline(nid, x, y, z):
    return "%8d%16.7f%16.7f%16.7f" % (nid, x, y, z)


def setlines(ids, fw=10):
    out = []
    for i in range(0, len(ids), 8):
        out.append("".join("%*d" % (fw, n) for n in ids[i:i + 8]))
    return out


CUBE = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
        (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]


def cfg(d, name, **kv):
    lines = []
    for k, v in kv.items():
        if isinstance(v, bool):
            v = "true" if v else "false"
        lines.append("%s: %s" % (k, v))
    write(os.path.join(d, name), "\n".join(lines) + "\n")
    return name


def report(d, name="report.json"):
    with open(os.path.join(d, name)) as f:
        return json.load(f)


def main():
    if len(sys.argv) < 2:
        print("usage: test_cleanup_nodes.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="cleanup_nodes_")
    try:
        # ── A: 전체 절점 세트 함정 + 전이 keep ────────────────────────────────
        orph = {101: 2.0, 102: 2.0, 103: 3.0, 104: 4.0, 105: 5.0, 106: -500.0, 107: 6.0}
        L = ["*KEYWORD", "*NODE"]
        for i, (x, y, z) in enumerate(CUBE, start=1):
            L.append(nodeline(i, x, y, z))
        for nid in sorted(orph):
            L.append(nodeline(nid, orph[nid], 0.0, 0.0))
        L += ["*ELEMENT_SOLID", "%8d%8d" % (1, 1),
              "".join("%8d" % n for n in range(1, 9)),
              "*PART", "solid part", "%10d%10d%10d" % (1, 1, 1),
              "*SECTION_SOLID", "%10d%10d" % (1, 1),
              "*MAT_ELASTIC", "         1  7.85E-9  210000     0.3"]
        # ★함정 — 덱 전체 절점을 담은 세트
        L += ["*SET_NODE_LIST", "%10d" % 9000]
        L += setlines(list(range(1, 9)) + sorted(orph))
        L += ["*SET_NODE_LIST", "%10d" % 2001, "%10d%10d" % (101, 102)]
        L += ["*SET_NODE_LIST", "%10d" % 2002, "%10d" % 103]
        L += ["*CONSTRAINED_NODAL_RIGID_BODY", "%10d%10d%10d" % (1, 0, 2001)]
        L += ["*BOUNDARY_SPC_NODE", "%10d%10d%10d%10d%10d%10d%10d%10d" % (104, 0, 1, 1, 1, 1, 1, 1)]
        L += ["*DEFINE_SOMETHING_WE_DO_NOT_KNOW", "%10d" % 105]
        L += ["*END"]
        write(os.path.join(d, "trap.k"), "\n".join(L) + "\n")
        # 모르는 키는 경고하고 무시한다(조용히 넘어가지 않는다) — `mod: safe` 오타는 기본 report 로 돈다
        write(os.path.join(d, "uk.yaml"), "model: trap.k\nmod: safe\n")
        rc, out = run(binary, d, "cleanup-nodes", "uk.yaml")
        check("A-uk 모르는 키(mod 오타)는 경고하고 무시한다 — rc 0", rc == 0 and "모르는 키는 무시한다: mod" in out, out[-300:])

        cfg(d, "a.yaml", model="trap.k", report="ra.json")
        rc, out = run(binary, d, "cleanup-nodes", "a.yaml")
        check("A-0 rc=0", rc == 0, out[-400:])
        r = report(d, "ra.json")
        check("A-1 요소가 안 쓰는 절점 7개를 후보로 센다 (세트 블록이 요소 참조로 섞이지 않는다)",
              r["nodes"]["unreferenced_candidates"] == 7, r["nodes"])
        check("A-2 요소가 쓰는 절점은 8개", r["nodes"]["used_by_elements"] == 8, r["nodes"])
        check("A-3 세트 멤버십 자체는 참조가 아니다 (9000 이 아무것도 살리지 않았다)",
              "*SET_NODE_LIST" not in r["kept_by"], r["kept_by"])
        check("A-4 ★CNRB 가 NSID 로 가리킨 세트의 멤버는 전이로 남는다 (요청서의 71건 경로)",
              r["kept_by"].get("*CONSTRAINED_NODAL_RIGID_BODY") == 2, r["kept_by"])
        check("A-5 직접 절점을 이름한 keep 키워드도 남긴다",
              r["kept_by"].get("*BOUNDARY_SPC_NODE") == 1, r["kept_by"])
        check("A-6 ★모르는 키워드가 가리킨 절점은 남기고 적는다 ('이해한 것만 지운다')",
              any(x["keyword"] == "*DEFINE_SOMETHING_WE_DO_NOT_KNOW" and x["nodes"] == 1
                  for x in r["unknown_keyword_kept"]), r["unknown_keyword_kept"])
        # ★요청자의 실패를 잡는 칸은 여기다. `*SET_NODE_*` 를 보통 키워드로 두면 이 수가 **0**
        # 이 된다(실측으로 확인: 그 분기를 끄면 deletable 0 · 이 시험 18항 빨강).
        check("A-7 ★삭제 가능 3개 — 전체 절점 세트가 고아를 '참조됨' 으로 덮지 않는다",
              r["nodes"]["deletable"] == 3, r["nodes"])
        check("A-8 ★bbox_before 가 리포트에 있다", r["bbox_before"] is not None)
        check("A-9 ★bbox_after 가 리포트에 있다", r["bbox_after"] is not None)
        check("A-10 고아를 빼면 bbox 가 줄어든다 (낙하판 오배치를 사전에 드러낸다)",
              r["bbox_before"]["min"][0] == -500.0 and r["bbox_after"]["min"][0] == 0.0,
              (r["bbox_before"]["min"], r["bbox_after"]["min"]))
        check("A-11 기본 mode 는 report", r["mode"] == "report", r["mode"])
        check("A-12 report 모드는 덱을 쓰지 않는다", r["output"] is None, r["output"])

        # ── B: 쓰기 + 세트 정리 + 되읽기 검증 ─────────────────────────────────
        cfg(d, "b.yaml", model="trap.k", output="clean.k", mode="safe", report="rb.json")
        rc, out = run(binary, d, "cleanup-nodes", "b.yaml")
        check("B-0 rc=0", rc == 0, out[-400:])
        rb = report(d, "rb.json")
        check("B-1 *NODE 줄 3개를 지웠다", rb["nodes"]["deleted"] == 3, rb["nodes"])
        check("B-2 ★되읽기 검증 — 요소 참조 미정의 0",
              rb["verify"]["undefined_by_elements"] == 0, rb["verify"])
        check("B-3 ★되읽기 검증 — 세트 멤버 미정의 0 (LS-DYNA Error 10233 자리)",
              rb["verify"]["undefined_set_members"] == 0, rb["verify"])
        clean = open(os.path.join(d, "clean.k")).read()
        check("B-4 지운 절점이 *NODE 에서 사라졌다",
              "\n     103 " not in clean and "\n     106 " not in clean, "")
        check("B-5 남긴 절점은 그대로 있다", "\n     101 " in clean and "\n     104 " in clean, "")
        check("B-6 전체 절점 세트에서 지운 멤버가 빠졌다",
              any(x["sid"] == 9000 and x["removed"] == 3 for x in rb["sets_pruned"]),
              rb["sets_pruned"])
        check("B-7 건드릴 것 없는 세트는 정리 목록에 없다",
              not any(x["sid"] == 2001 for x in rb["sets_pruned"]), rb["sets_pruned"])
        check("B-8 멤버가 0 이 된 세트를 센다", rb["sets_emptied"] == 1, rb["sets_emptied"])
        src = open(os.path.join(d, "trap.k")).read()
        def block(text, kw, nxt):
            a = text.index(kw); b = text.index(nxt, a)
            return text[a:b]
        check("B-9 ★손대지 않은 블록은 바이트가 같다 (*ELEMENT_SOLID)",
              block(src, "*ELEMENT_SOLID", "*PART") == block(clean, "*ELEMENT_SOLID", "*PART"))
        check("B-10 ★손대지 않은 블록은 바이트가 같다 (*MAT_ELASTIC)",
              block(src, "*MAT_ELASTIC", "*SET_NODE") == block(clean, "*MAT_ELASTIC", "*SET_NODE"))

        # ── B': prune_sets: false 면 **검증이 빨개져야 한다** ──────────────────
        # 검증이 늘 0 을 내는 장식이 아님을 증명한다.
        cfg(d, "bp.yaml", model="trap.k", output="noprune.k", mode="safe",
            prune_sets=False, report="rbp.json")
        rc, out = run(binary, d, "cleanup-nodes", "bp.yaml")
        rbp = report(d, "rbp.json")
        check("B-11 ★prune_sets: false 면 세트에 없는 절점이 남아 검증이 잡는다",
              rbp["verify"]["undefined_set_members"] > 0, rbp["verify"])
        check("B-12 ★그때 rc 는 0 이 아니다 (깨진 덱을 멀쩡하다고 하지 않는다)", rc != 0, rc)

        # ── C: §6 — 절점 ID 8자리가 8칸을 꽉 채운다 ──────────────────────────
        ids = list(range(10000001, 10000009))
        L = ["*KEYWORD", "*NODE"]
        for n, (x, y, z) in zip(ids, CUBE):
            L.append(nodeline(n, x, y, z))
        L.append(nodeline(10000009, 9.0, 0.0, 0.0))
        L += ["*ELEMENT_SOLID", "%8d%8d" % (1, 1), "".join("%8d" % n for n in ids),
              "*PART", "p", "%10d%10d%10d" % (1, 1, 1),
              "*SECTION_SOLID", "%10d%10d" % (1, 1), "*END"]
        write(os.path.join(d, "packed.k"), "\n".join(L) + "\n")
        check("C-0 픽스처가 정말 공백 없이 붙어 있다",
              "1000000110000002" in open(os.path.join(d, "packed.k")).read())
        cfg(d, "c.yaml", model="packed.k", report="rc.json")
        rc, out = run(binary, d, "cleanup-nodes", "c.yaml")
        rcj = report(d, "rc.json")
        check("C-1 ★8자리 ID 가 붙어도 8개를 요소 참조로 읽는다", rcj["nodes"]["used_by_elements"] == 8,
              rcj["nodes"])
        check("C-2 ★그래서 삭제 가능은 1개뿐이다 (공백 분해면 7개가 고아로 보인다)",
              rcj["nodes"]["deletable"] == 1, rcj["nodes"])

        # ── D: §6 — CRLF 보존 ────────────────────────────────────────────────
        write(os.path.join(d, "crlf.k"), open(os.path.join(d, "trap.k")).read(), newline="\r\n")
        cfg(d, "dd.yaml", model="crlf.k", output="crlf_out.k", mode="safe", report="rd.json")
        rc, out = run(binary, d, "cleanup-nodes", "dd.yaml")
        raw = open(os.path.join(d, "crlf_out.k"), "rb").read()
        lone = raw.replace(b"\r\n", b"").count(b"\n")
        check("D-1 rc=0", rc == 0, out[-300:])
        check("D-2 ★산출에 홀로 선 LF 가 0", lone == 0, lone)
        check("D-3 CRLF 가 실제로 있다", raw.count(b"\r\n") > 10, raw.count(b"\r\n"))
        check("D-4 CRLF 덱에서도 같은 판정", report(d, "rd.json")["nodes"]["deletable"] == 3,
              report(d, "rd.json")["nodes"])

        # ── E: §6 — 고차 솔리드의 절점 카드가 두 줄이다 ───────────────────────
        L = ["*KEYWORD", "*NODE"]
        for n in range(1, 21):
            L.append(nodeline(n, float(n), 0.0, 0.0))
        L.append(nodeline(101, 99.0, 0.0, 0.0))
        L += ["*ELEMENT_SOLID", "%8d%8d" % (1, 1),
              "".join("%8d" % n for n in range(1, 11)),
              "".join("%8d" % n for n in range(11, 21)),
              "*PART", "hex20", "%10d%10d%10d" % (1, 1, 1),
              "*SECTION_SOLID", "%10d%10d" % (1, 23), "*END"]
        write(os.path.join(d, "hex20.k"), "\n".join(L) + "\n")
        cfg(d, "e.yaml", model="hex20.k", report="re.json")
        rc, out = run(binary, d, "cleanup-nodes", "e.yaml")
        re_ = report(d, "re.json")
        check("E-1 ★절점 카드 두 줄을 다 읽는다 (ELFORM 23 = 20절점)",
              re_["nodes"]["used_by_elements"] == 20, re_["nodes"])
        check("E-2 ★그래서 삭제 가능은 1개다 (한 줄만 읽으면 11개가 고아로 보인다)",
              re_["nodes"]["deletable"] == 1, re_["nodes"])

        # ── F: *INCLUDE 를 읽는다 ────────────────────────────────────────────
        L = ["*KEYWORD", "*NODE"]
        for i, (x, y, z) in enumerate(CUBE, start=1):
            L.append(nodeline(i, x, y, z))
        L.append(nodeline(101, 9.0, 0.0, 0.0))
        L += ["*PART", "p", "%10d%10d%10d" % (1, 1, 1),
              "*SECTION_SOLID", "%10d%10d" % (1, 1),
              "*INCLUDE", "inc.k", "*END"]
        write(os.path.join(d, "main.k"), "\n".join(L) + "\n")
        write(os.path.join(d, "inc.k"), "*KEYWORD\n*ELEMENT_SOLID\n%8d%8d\n%s\n*END\n"
              % (1, 1, "".join("%8d" % n for n in range(1, 9))))
        cfg(d, "f.yaml", model="main.k", report="rf.json")
        rc, out = run(binary, d, "cleanup-nodes", "f.yaml")
        rf = report(d, "rf.json")
        check("F-1 인클루드를 한 개 읽었다", rf["deck"]["includes_read"] == 1, rf["deck"])
        check("F-2 ★인클루드가 쓰는 절점을 참조로 센다", rf["nodes"]["used_by_elements"] == 8,
              rf["nodes"])
        check("F-3 ★그래서 삭제 가능은 1개다 (안 읽으면 9개가 고아로 보인다)",
              rf["nodes"]["deletable"] == 1, rf["nodes"])

        # ── F': 못 읽는 인클루드에서 safe 는 쓰지 않는다 ──────────────────────
        write(os.path.join(d, "miss.k"), "\n".join(
            ["*KEYWORD", "*NODE", nodeline(1, 0, 0, 0), nodeline(2, 1, 0, 0),
             "*INCLUDE", "nope.k", "*END"]) + "\n")
        cfg(d, "fm.yaml", model="miss.k", output="miss_out.k", mode="safe")
        rc, out = run(binary, d, "cleanup-nodes", "fm.yaml")
        check("F-4 ★mode: safe 는 못 읽은 *INCLUDE 에서 거절한다", rc == 1, rc)
        check("F-5 그때 덱을 만들지 않는다", not os.path.exists(os.path.join(d, "miss_out.k")))
        cfg(d, "fr.yaml", model="miss.k", report="rfr.json")
        rc, out = run(binary, d, "cleanup-nodes", "fr.yaml")
        check("F-6 report 모드는 돌고 못 읽은 인클루드를 센다",
              rc == 0 and report(d, "rfr.json")["deck"]["includes_unreadable"] == 1, out[-300:])

        # ── F'': *INCLUDE_PATH 는 탐색 경로다(2026-10-16) ───────────────────────
        # 예전에는 `*INCLUDE_PATH` 를 「못 읽은 변종 인클루드」로 세어 safe 가 **거절**했다 —
        # 같은 덱에 그 카드 한 장만 더해도 rc=1. 끌어오는 본문이 없는 카드다.
        L = ["*KEYWORD", "*INCLUDE_PATH", "libdir", "*NODE"]
        for i, (x, y, z) in enumerate(CUBE, start=1):
            L.append(nodeline(i, x, y, z))
        L += ["*PART", "p", "%10d%10d%10d" % (1, 1, 1), "*SECTION_SOLID", "%10d%10d" % (1, 1),
              "*ELEMENT_SOLID", "%8d%8d" % (1, 1), "".join("%8d" % n for n in range(1, 9)), "*END"]
        write(os.path.join(d, "path_only.k"), "\n".join(L) + "\n")
        cfg(d, "fp.yaml", model="path_only.k", output="path_only_out.k", mode="safe")
        rc, out = run(binary, d, "cleanup-nodes", "fp.yaml")
        check("F-7 ★*INCLUDE_PATH 만 있는 덱을 safe 가 쓴다(거절하지 않는다)",
              rc == 0 and os.path.exists(os.path.join(d, "path_only_out.k")), out[-300:])
        # 탐색 경로로 찾은 인클루드는 **읽는다** — 그 안의 요소가 쓰는 절점을 남긴다.
        os.makedirs(os.path.join(d, "libdir"), exist_ok=True)
        L = ["*KEYWORD", "*INCLUDE_PATH", "libdir", "*NODE"]
        for i, (x, y, z) in enumerate(CUBE, start=1):
            L.append(nodeline(i, x, y, z))
        L.append(nodeline(101, 9.0, 0.0, 0.0))
        L += ["*PART", "p", "%10d%10d%10d" % (1, 1, 1), "*SECTION_SOLID", "%10d%10d" % (1, 1),
              "*INCLUDE", "elems_in_lib.k", "*END"]
        write(os.path.join(d, "via_path.k"), "\n".join(L) + "\n")
        write(os.path.join(d, "libdir", "elems_in_lib.k"), "*KEYWORD\n*ELEMENT_SOLID\n%8d%8d\n%s\n*END\n"
              % (1, 1, "".join("%8d" % n for n in range(1, 9))))
        cfg(d, "fv.yaml", model="via_path.k", report="rfv.json")
        rc, out = run(binary, d, "cleanup-nodes", "fv.yaml")
        rv = report(d, "rfv.json")
        check("F-8 ★탐색 경로로 찾은 인클루드를 읽는다",
              rv["deck"]["includes_read"] == 1 and rv["deck"]["includes_unreadable"] == 0, rv["deck"])
        check("F-9 ★그 안의 요소가 쓰는 절점 8개를 남긴다(삭제 가능 1)",
              rv["nodes"]["used_by_elements"] == 8 and rv["nodes"]["deletable"] == 1, rv["nodes"])

        # ── F3: 인클루드 닫힘은 정본(`include_closure::readPaths`)이 정한다(2026-10-17) ─────────
        # 예전에는 이 op 이 자기 재귀(8단)를 돌았다 — 9단째 인클루드를 「read: 9」로 세면서 **훑지 않아** 거기 요소가 쓰는
        # 절점을 고아로 지웠다(safe · rc 0 실측). `␣+` 로 이은 이름은 못 찾아 거절했고, 인클루드 안 `*END` 뒤도 읽었다.
        def chain_deck(tag, depth):
            L = ["*KEYWORD", "*NODE"]
            for i, (x, y, z) in enumerate(CUBE, start=1):
                L.append(nodeline(i, x, y, z))
            L += [nodeline(9, 5, 0, 0), nodeline(10, 6, 0, 0), nodeline(11, 5, 1, 0), nodeline(12, 5, 0, 1),
                  nodeline(13, 9, 9, 9)]
            L += ["*PART", "p", "%10d%10d%10d" % (1, 1, 1), "*SECTION_SOLID", "%10d%10d" % (1, 1),
                  "*ELEMENT_SOLID", "%8d%8d%s" % (1, 1, "".join("%8d" % n for n in range(1, 9))),
                  "*INCLUDE", "%s_1.k" % tag, "*END"]
            write(os.path.join(d, "%s.k" % tag), "\n".join(L) + "\n")
            for k in range(1, depth):
                write(os.path.join(d, "%s_%d.k" % (tag, k)), "*KEYWORD\n*INCLUDE\n%s_%d.k\n*END\n" % (tag, k + 1))
            write(os.path.join(d, "%s_%d.k" % (tag, depth)),
                  "*KEYWORD\n*PART\nt\n%10d%10d%10d\n*SECTION_SOLID\n%10d%10d\n*ELEMENT_SOLID\n%8d%8d%s\n*END\n"
                  % (2, 2, 1, 2, 10, 2, 2, "".join("%8d" % n for n in [9, 10, 11, 12, 12, 12, 12, 12])))

        def kept_nodes(path):
            out, on = [], False
            for l in open(path).read().splitlines():
                if l.startswith("*"):
                    on = l.strip().upper() == "*NODE"
                    continue
                if on and l.strip() and not l.startswith("$"):
                    out.append(int(l[:8]))
            return out

        chain_deck("deep", 9)
        cfg(d, "dp.yaml", model="deep.k", output="deep_out.k", mode="safe", report="rdp.json")
        rc, out = run(binary, d, "cleanup-nodes", "dp.yaml")
        check("F-10 ★9단째 인클루드의 요소가 쓰는 절점 9-12 를 지우지 않는다(지우는 것은 고아 13 뿐)",
              rc == 0 and os.path.exists(os.path.join(d, "deep_out.k"))
              and kept_nodes(os.path.join(d, "deep_out.k")) == list(range(1, 13)), (rc, out[-300:]))
        chain_deck("toodeep", 18)
        cfg(d, "td.yaml", model="toodeep.k", output="toodeep_out.k", mode="safe", report="rtd.json")
        rc, out = run(binary, d, "cleanup-nodes", "td.yaml")
        check("F-11 ★깊이 상한(16)을 넘으면 safe 는 쓰지 않는다 — 「못 봤다」를 말한다",
              rc == 1 and "깊이 상한" in out and not os.path.exists(os.path.join(d, "toodeep_out.k")), (rc, out[-300:]))
        cfg(d, "tdr.yaml", model="toodeep.k", report="rtdr.json")
        run(binary, d, "cleanup-nodes", "tdr.yaml")
        check("F-12 보고서에 include_depth_cut 이 참으로 실린다",
              report(d, "rtdr.json")["deck"].get("include_depth_cut") is True, report(d, "rtdr.json")["deck"])
        # `␣+` 이음 이름(Vol_I 179670) — 정본은 한 이름으로 붙여 찾는다
        L = ["*KEYWORD", "*NODE"]
        for i, (x, y, z) in enumerate(CUBE, start=1):
            L.append(nodeline(i, x, y, z))
        L.append(nodeline(101, 9.0, 0.0, 0.0))
        L += ["*PART", "p", "%10d%10d%10d" % (1, 1, 1), "*SECTION_SOLID", "%10d%10d" % (1, 1),
              "*INCLUDE", "long_name_ +", "elements.k", "*END"]
        write(os.path.join(d, "cont.k"), "\n".join(L) + "\n")
        write(os.path.join(d, "long_name_elements.k"), "*KEYWORD\n*ELEMENT_SOLID\n%8d%8d\n%s\n*END\n"
              % (1, 1, "".join("%8d" % n for n in range(1, 9))))
        cfg(d, "ct.yaml", model="cont.k", output="cont_out.k", mode="safe", report="rct.json")
        rc, out = run(binary, d, "cleanup-nodes", "ct.yaml")
        # 예전 판은 이름을 못 찾아 safe 가 거절하고 보고서를 쓰지 않는다 — 시험이 죽지 않게 비어 있으면 빈 값으로 본다
        rct = report(d, "rct.json") if os.path.exists(os.path.join(d, "rct.json")) else {"deck": {}, "nodes": {}}
        check("F-13 ★`␣+` 로 이은 인클루드 이름을 찾아 읽는다(삭제 가능 1 — 고아 101)",
              rc == 0 and rct["deck"].get("includes_read") == 1 and rct["nodes"].get("deletable") == 1, (rc, rct))
        # 인클루드 안의 `*END` 는 그 파일만 끝낸다(179654) — 뒤의 카드는 LS-DYNA 가 읽지 않는다
        L = ["*KEYWORD", "*NODE"]
        for i, (x, y, z) in enumerate(CUBE, start=1):
            L.append(nodeline(i, x, y, z))
        L.append(nodeline(101, 9.0, 0.0, 0.0))
        L += ["*PART", "p", "%10d%10d%10d" % (1, 1, 1), "*SECTION_SOLID", "%10d%10d" % (1, 1),
              "*INCLUDE", "endmid.k", "*END"]
        write(os.path.join(d, "endmain.k"), "\n".join(L) + "\n")
        write(os.path.join(d, "endmid.k"), "*KEYWORD\n*ELEMENT_SOLID\n%8d%8d\n%s\n*END\n*ELEMENT_SOLID\n%8d%8d%s\n"
              % (1, 1, "".join("%8d" % n for n in range(1, 9)), 2, 1, "".join("%8d" % n for n in [101] * 8)))
        cfg(d, "em.yaml", model="endmain.k", report="rem.json")
        rc, out = run(binary, d, "cleanup-nodes", "em.yaml")
        rem = report(d, "rem.json")
        check("F-14 인클루드 안 `*END` 뒤의 요소는 참조로 세지 않는다(고아 101 은 삭제 가능)",
              rc == 0 and rem["nodes"]["used_by_elements"] == 8 and rem["nodes"]["deletable"] == 1, (rc, rem["nodes"]))

        # ── G: *SET_NODE_LIST_GENERATE 범위는 펼쳐 남긴다 ─────────────────────
        L = ["*KEYWORD", "*NODE"]
        for i, (x, y, z) in enumerate(CUBE, start=1):
            L.append(nodeline(i, x, y, z))
        for n in range(201, 211):
            L.append(nodeline(n, float(n), 0.0, 0.0))
        L += ["*ELEMENT_SOLID", "%8d%8d" % (1, 1), "".join("%8d" % n for n in range(1, 9)),
              "*PART", "p", "%10d%10d%10d" % (1, 1, 1),
              "*SECTION_SOLID", "%10d%10d" % (1, 1),
              "*SET_NODE_LIST_GENERATE", "%10d" % 3001, "%10d%10d" % (201, 210),
              "*END"]
        write(os.path.join(d, "gen.k"), "\n".join(L) + "\n")
        cfg(d, "g.yaml", model="gen.k", report="rg.json")
        rc, out = run(binary, d, "cleanup-nodes", "g.yaml")
        rg = report(d, "rg.json")
        check("G-1 ★범위를 끝점만 보지 않고 펼쳐서 전부 남긴다 (안쪽 8개가 지워지면 세트가 깨진다)",
              rg["nodes"]["deletable"] == 0, rg["nodes"])
        check("G-2 그 이유를 '못 읽는 세트 변종' 으로 적는다",
              rg["kept_by"].get("(unreadable *SET_NODE_* variants)") == 10, rg["kept_by"])

        # ── H: §6 — `_TITLE` 제목줄이 SID 줄을 한 줄 밀어낸다 ─────────────────
        L = ["*KEYWORD", "*NODE"]
        for i, (x, y, z) in enumerate(CUBE, start=1):
            L.append(nodeline(i, x, y, z))
        L.append(nodeline(101, 9.0, 0.0, 0.0))
        L += ["*ELEMENT_SOLID", "%8d%8d" % (1, 1), "".join("%8d" % n for n in range(1, 9)),
              "*PART", "p", "%10d%10d%10d" % (1, 1, 1),
              "*SECTION_SOLID", "%10d%10d" % (1, 1),
              "*SET_NODE_LIST_TITLE", "my spot weld nodes", "%10d" % 4001, "%10d" % 101,
              "*CONSTRAINED_NODAL_RIGID_BODY", "%10d%10d%10d" % (1, 0, 4001),
              "*END"]
        write(os.path.join(d, "title.k"), "\n".join(L) + "\n")
        cfg(d, "h.yaml", model="title.k", report="rh.json")
        rc, out = run(binary, d, "cleanup-nodes", "h.yaml")
        rh = report(d, "rh.json")
        check("H-1 ★제목줄을 세어 SID 를 제 줄에서 읽는다 (못 읽으면 CNRB 전이가 끊긴다)",
              rh["kept_by"].get("*CONSTRAINED_NODAL_RIGID_BODY") == 1, rh["kept_by"])
        check("H-2 그래서 삭제 가능 0", rh["nodes"]["deletable"] == 0, rh["nodes"])

        # ── I: mode: force 는 모르는 키워드를 존중하지 않는다 ─────────────────
        cfg(d, "i.yaml", model="trap.k", output="forced.k", mode="force", report="ri.json")
        rc, out = run(binary, d, "cleanup-nodes", "i.yaml")
        ri = report(d, "ri.json")
        check("I-1 force 는 모르는 키워드가 가리킨 절점도 지운다",
              ri["nodes"]["deletable"] == 4, ri["nodes"])
        check("I-2 ★그 사실을 수로 적는다", ri["force_deleted_despite_unknown"] == 1,
              ri["force_deleted_despite_unknown"])
        check("I-3 keep 목록이 가리킨 것은 force 에서도 남는다",
              ri["kept_by"].get("*CONSTRAINED_NODAL_RIGID_BODY") == 2, ri["kept_by"])
        check("I-4 force 도 되읽기 검증을 통과한다",
              ri["verify"]["undefined_by_elements"] == 0 and
              ri["verify"]["undefined_set_members"] == 0, ri["verify"])

        # ── J: keep_referenced_by 를 사용자가 줄 수 있다 ──────────────────────
        write(os.path.join(d, "j.yaml"),
              "model: trap.k\nreport: rj.json\nkeep_referenced_by:\n"
              "  - DEFINE_SOMETHING_WE_DO_NOT_KNOW\n")
        rc, out = run(binary, d, "cleanup-nodes", "j.yaml")
        rj = report(d, "rj.json")
        check("J-1 사용자가 준 키워드는 'keep' 으로 귀속된다",
              rj["kept_by"].get("*DEFINE_SOMETHING_WE_DO_NOT_KNOW") == 1, rj["kept_by"])
        check("J-2 ★목록을 바꿔도 삭제 가능 수는 그대로다 (안전은 목록이 아니라 전수 훑기가 만든다)",
              rj["nodes"]["deletable"] == 3, rj["nodes"])
        check("J-3 목록에서 빠진 기본 키워드도 여전히 남긴다 (모르는 키워드로 훑힌다)",
              any(x["keyword"] == "*CONSTRAINED_NODAL_RIGID_BODY"
                  for x in rj["unknown_keyword_kept"]) or
              rj["kept_by"].get("*CONSTRAINED_NODAL_RIGID_BODY"), rj)

        # ── K: 가장자리 ──────────────────────────────────────────────────────
        write(os.path.join(d, "noel.k"), "*KEYWORD\n*NODE\n" + nodeline(1, 0, 0, 0) + "\n*END\n")
        cfg(d, "k1.yaml", model="noel.k", report="rk1.json")
        rc, out = run(binary, d, "cleanup-nodes", "k1.yaml")
        check("K-1 요소가 없는 덱도 돌고 그 절점을 후보로 센다",
              rc == 0 and report(d, "rk1.json")["nodes"]["unreferenced_candidates"] == 1, out[-300:])
        cfg(d, "k2.yaml", model="nosuch.k")
        rc, out = run(binary, d, "cleanup-nodes", "k2.yaml")
        check("K-2 없는 모델은 rc=1 로 말한다", rc == 1 and "Cannot open model" in out, out[-200:])
        write(os.path.join(d, "k3.yaml"), "model: trap.k\n\treport: x.json\n")
        rc, out = run(binary, d, "cleanup-nodes", "k3.yaml")
        check("K-3 탭 들여쓰기를 거른다", rc == 1 and "cleanup-nodes" in out, out[-200:])

        # ── L: ★보 족의 **절점이 아닌 칸**을 참조로 세지 않는다 ────────────────
        # 공용 판정기(`auxElementCard`)가 매뉴얼 근거로 칸 자리를 안다. 그 전에는 `*ELEMENT_*`
        # 변형의 정수를 **전부** 절점으로 세서, 보의 LOCAL 칸이나 안전벨트의 SBRID 칸과 번호가
        # 같은 고아 절점이 **영구히 남았다**(과포함은 안전한 방향이지만, 알 수 있으면 아는 게 낫다).
        L = ["*KEYWORD", "*NODE"]
        for i, (x, y, z) in enumerate(CUBE, start=1):
            L.append(nodeline(i, x, y, z))
        for n in (101, 102):
            L.append(nodeline(n, float(n), 0.0, 0.0))
        L.append(nodeline(777, 77.0, 0.0, 0.0))     # BEAM 의 LOCAL 칸 번호와 같다
        L.append(nodeline(888, 88.0, 0.0, 0.0))     # SEATBELT 의 SBRID 칸 번호와 같다
        e8 = lambda *v: "".join("%8d" % n for n in v)
        s10 = lambda *v: "".join("%10d" % n for n in v)
        L += ["*ELEMENT_SOLID", e8(1, 1), e8(*range(1, 9))]
        #                      EID PID  N1   N2   N3 RT1 RR1 RT2 RR2 LOCAL
        L += ["*ELEMENT_BEAM", e8(10, 9, 101, 102, 0, 7, 7, 7, 7, 777)]
        #                          EID PID  N1   N2 SBRID SLEN N3 N4
        L += ["*ELEMENT_SEATBELT", e8(13, 9, 101, 102, 888, 0, 0, 0)]
        L += ["*PART", "solid", s10(1, 1, 1), "aux", s10(9, 9, 9),
              "*SECTION_SOLID", s10(1, 1), "*SECTION_BEAM", s10(9, 1),
              "*MAT_ELASTIC", "         1  7.85E-9  210000     0.3", "*END"]
        write(os.path.join(d, "aux.k"), "\n".join(L) + "\n")
        cfg(d, "l.yaml", model="aux.k", report="rl.json")
        rc, out = run(binary, d, "cleanup-nodes", "l.yaml")
        rl = report(d, "rl.json")
        check("L-0 rc=0", rc == 0, out[-300:])
        check("L-1 보 족의 절점(101·102)은 요소 참조로 센다",
              rl["nodes"]["used_by_elements"] == 10, rl["nodes"])
        check("L-2 ★LOCAL(777)·SBRID(888) 은 절점이 **아니다** → 삭제 가능 2개",
              rl["nodes"]["deletable"] == 2, rl["nodes"])
        check("L-3 그래서 '모르는 키워드가 살렸다' 목록에 보 족이 없다",
              not any("BEAM" in x["keyword"] or "SEATBELT" in x["keyword"]
                      for x in rl["unknown_keyword_kept"]), rl["unknown_keyword_kept"])
        check("L-4 '줄 수를 모르는 *ELEMENT_*' 목록도 비었다",
              rl["element_keywords_opaque"] == [], rl["element_keywords_opaque"])

        # 지운 뒤 되읽기 검증이 보 족까지 본다
        cfg(d, "l2.yaml", model="aux.k", output="auxclean.k", mode="safe", report="rl2.json")
        rc, out = run(binary, d, "cleanup-nodes", "l2.yaml")
        rl2 = report(d, "rl2.json")
        check("L-5 쓰고 나서도 미정의 0", rc == 0 and rl2["verify"]["undefined_by_elements"] == 0,
              rl2.get("verify"))
        ac = open(os.path.join(d, "auxclean.k")).read()
        check("L-6 보 족이 쓰는 절점은 남았다", "\n     101 " in ac and "\n     102 " in ac, "")
        check("L-7 LOCAL·SBRID 와 번호가 같던 고아는 지워졌다",
              "\n     777 " not in ac and "\n     888 " not in ac, "")
    finally:
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
