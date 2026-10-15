#!/usr/bin/env python3
"""contact 가 새 세트·접촉 번호를 **인클루드 닫힘까지 본 최대값 위로** 내는가.

왜 이 시험이 있나 (2026-10-15, plan2 P1-3 · `IdAllocator` 첫 채택).

  contact 는 새 세트를 "이 덱의 최대 SID + 1" 로 냈다. 그런데 **주 덱 파일 하나만** 셌다.
  재현 — `examples/contact/model.k`(세트 최대 10)에 `*INCLUDE` 로 `*SET_SEGMENT 11` 을 붙이고
  세그먼트 접촉을 만들면 새 `*SET_SEGMENT` 를 **11** 과 12 로 냈다. 인클루드를 펼쳐 `info` 로
  보면 "SID 11 가 line 70 과 겹칩니다 — 같은 종류의 세트 ID 는 유일해야 합니다". 같은 종류의
  SID 가 둘이면 LS-DYNA 는 키워드 단계에서 멈춘다. 경고는 냈지만("겹쳐 발급할 수 있습니다")
  **번호는 그대로 겹쳤다.**

  ⚠ 재현은 **같은 종류**로 해야 한다. 처음에 `*SET_PART 11` 로 재현했는데 그것은 LS-DYNA 에서
    **합법**이다(SET 네임스페이스는 종류별 — `*SET_PART 6` 과 `*SET_NODE 6` 공존이 실사용 24%).
    contact 는 모든 종류를 한 통으로 세는 더 보수적인 규약이라 그 경우도 피하지만, "불법 덱"
    재현은 `*SET_SEGMENT` 끼리여야 한다.

무엇을 보나.
  A 인클루드의 `*SET_SEGMENT 11` 과 CID 3 위로 낸다 — 새 세트 12·13, 새 CID 4
  B 펼친 덱에 **같은 종류 SID 중복이 없다**(`info` 의 검사로 — 덱이 합법인지를 직접 본다)
  C 인클루드가 없으면 **번호가 그대로다** — 새 세트 11·12, 새 CID 3(주 덱 최대값 위)
  D 못 읽은 인클루드는 **그 자리를 말한다** — rc 는 0 그대로(읽기 실패가 op 실패는 아니다)
  E `*INCLUDE_TRANSFORM` 은 따라가지 않고 말한다(오프셋을 모르고 읽으면 번호가 그럴듯하게 틀린다)

usage: test_contact_include_ids.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
MODEL = os.path.join(REPO, "examples", "contact", "model.k")
YAML = os.path.join(REPO, "examples", "contact", "03_create_segment.yaml")

FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail)[:300]))
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    return cond


INCLUDE_BODY = """*KEYWORD
*SET_SEGMENT_TITLE
FromInclude
        11       0.0       0.0       0.0       0.0
         1         2         3         4
*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID
         3FromInclude
        11         0         0         0         0         0         0         0
       0.0       0.0       0.0       0.0       0.0         0       0.0       0.0
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
*END
"""


def stage(d, include_line=None, include_body=None, keyword="*INCLUDE"):
    """model.k 의 *END 앞에 인클루드 카드를 끼운다. include_line 이 None 이면 그대로 둔다."""
    src = open(MODEL, encoding="utf-8").read().splitlines()
    out = []
    for l in src:
        if include_line is not None and l.strip().upper() == "*END":
            out += [keyword, include_line]
            if keyword == "*INCLUDE_TRANSFORM":
                out += ["         0         0         0         0         0         0         0",
                        "         0", "       1.0       1.0       1.0      ", "         0"]
        out.append(l)
    open(os.path.join(d, "model.k"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    if include_body is not None:
        open(os.path.join(d, include_line), "w", encoding="utf-8").write(include_body)
    y = open(YAML, encoding="utf-8").read().replace("03_create_segment_result.k", "out.k")
    open(os.path.join(d, "c.yaml"), "w", encoding="utf-8").write(y)


def run(binary, d, *argv):
    p = subprocess.run([binary, *argv], cwd=d, capture_output=True, text=True, timeout=120,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def new_ids(path, base):
    """out.k 에서 base(model.k)에 없던 *SET_SEGMENT SID 와 *CONTACT_*_ID CID 를 뽑는다."""
    def scan(p):
        L = open(p, encoding="utf-8").read().splitlines()
        segs, cids = [], []
        for i, l in enumerate(L):
            u = l.strip().upper()
            if u.startswith("*SET_SEGMENT"):
                j = i + 1 + (1 if "_TITLE" in u else 0)
                while j < len(L) and L[j].lstrip().startswith("$"):
                    j += 1
                segs.append(int(L[j][:10]))
            elif u.startswith("*CONTACT_") and re.search(r"_ID(_|$)", u):
                j = i + 1
                while j < len(L) and L[j].lstrip().startswith("$"):
                    j += 1
                cids.append(int(L[j][:10]))
        return segs, cids
    s1, c1 = scan(path)
    s0, c0 = scan(base)
    return sorted(set(s1) - set(s0)), sorted(set(c1) - set(c0))


def flatten(d):
    """인클루드를 펼친 덱 — LS-DYNA 가 보는 그대로 한 파일로."""
    out = open(os.path.join(d, "out.k"), encoding="utf-8").read().splitlines()
    flat, k = [], 0
    while k < len(out):
        if out[k].strip().upper() == "*INCLUDE":
            body = open(os.path.join(d, out[k + 1].strip()), encoding="utf-8").read().splitlines()
            flat += [l for l in body if l.strip().upper() not in ("*KEYWORD", "*END")]
            k += 2
            continue
        flat.append(out[k])
        k += 1
    p = os.path.join(d, "flat.k")
    open(p, "w", encoding="utf-8").write("\n".join(flat) + "\n")
    return p


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])

    print("[A·B 인클루드에 같은 종류 SID 11 · CID 3]")
    d = tempfile.mkdtemp(prefix="cii_a_")
    try:
        stage(d, "extra.k", INCLUDE_BODY)
        rc, out = run(binary, d, "contact", "c.yaml")
        if check("A contact rc=0", rc == 0, out[-300:]):
            segs, cids = new_ids(os.path.join(d, "out.k"), os.path.join(d, "model.k"))
            check("A 새 세트가 인클루드의 11 위다(12·13)", segs == [12, 13], segs)
            check("A 새 CID 가 인클루드의 3 위다(4)", cids == [4], cids)
            check("A 인클루드를 읽었다고 말한다", "인클루드 1개를 읽어" in out, out[-300:])
            rc2, out2 = run(binary, d, "info", flatten(d))
            check("B 펼친 덱에 같은 종류 SID 중복이 없다", "겹칩니다" not in out2,
                  [l for l in out2.splitlines() if "겹칩니다" in l][:2])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("[C 인클루드가 없으면 번호가 그대로다]")
    d = tempfile.mkdtemp(prefix="cii_c_")
    try:
        stage(d)
        rc, out = run(binary, d, "contact", "c.yaml")
        if check("C contact rc=0", rc == 0, out[-300:]):
            segs, cids = new_ids(os.path.join(d, "out.k"), os.path.join(d, "model.k"))
            check("C 새 세트 11·12(주 덱 최대 10 위)", segs == [11, 12], segs)
            check("C 새 CID 3(주 덱 최대 2 위)", cids == [3], cids)
            check("C 인클루드 이야기를 하지 않는다", "인클루드" not in out, out[-200:])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("[D 못 읽은 인클루드]")
    d = tempfile.mkdtemp(prefix="cii_d_")
    try:
        stage(d, "gone.k")                      # 파일을 만들지 않는다
        rc, out = run(binary, d, "contact", "c.yaml")
        check("D rc 는 0 그대로", rc == 0, out[-300:])
        check("D 못 본 자리를 이름으로 말한다", "못 본 인클루드" in out and "gone.k" in out, out[-300:])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("[E *INCLUDE_TRANSFORM]")
    d = tempfile.mkdtemp(prefix="cii_e_")
    try:
        stage(d, "extra.k", INCLUDE_BODY, keyword="*INCLUDE_TRANSFORM")
        rc, out = run(binary, d, "contact", "c.yaml")
        check("E rc 는 0 그대로", rc == 0, out[-300:])
        check("E 따라가지 않았다고 말한다", "*INCLUDE_TRANSFORM" in out and "따라가지 않았다" in out,
              out[-300:])
    finally:
        shutil.rmtree(d, ignore_errors=True)

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
