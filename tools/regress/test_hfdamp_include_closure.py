#!/usr/bin/env python3
# 선택형 hfdamp 가 메시를 인클루드한 마스터 덱에서 전체 감쇠로 조용히 바뀌지 않는지 보는 회귀 시험
"""`hfdamp mode: selective` — 인클루드 닫힘 안의 파트를 본다 (2026-10-16).

왜 이 시험이 있나.

  `box.k`(PID 1) 를 `*INCLUDE` 하는 마스터 덱에 선택형 hfdamp 를 돌리면 「dt 조건을 만족하는 파트가 없다」며
  **전체 감쇠(PSID=0)로 조용히 바꿨다** — rc 0(실측, 독립 op 과 `assemble` 의 `type: hfdamp` 둘 다). 선택형을
  달라고 했는데 모델 전체에 감쇠가 걸린 덱이 나온다. 파트는 인클루드 안에 있었다 — 분석이 주 덱만 봤다.

  지금은 분석이 인클루드 닫힘을 펼친 줄을 보고(감쇠 키워드는 주 덱에 넣는다), 닫힘을 다 못 읽었는데 파트를
  못 찾으면 전체로 바꾸지 않고 멈춘다. 인클루드가 없는 덱은 예전과 바이트가 같다(그 비교는 이 시험 밖 —
  커밋 메시지에 적었다).

usage: test_hfdamp_include_closure.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
FAILS, OKS = [], []
BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\n"
       "mid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:300]))
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    with open(path, "w", newline="\n") as f:
        f.write(text)


def psid(path):
    """`*DAMPING_FREQUENCY_RANGE_DEFORM` Card 1 의 PSID(칸 4 · 14칸 폭 표기) — 0 이면 전체 감쇠."""
    L = open(path, encoding="utf-8", errors="replace").read().splitlines()
    for i, l in enumerate(L):
        if l.strip().upper() == "*DAMPING_FREQUENCY_RANGE_DEFORM":
            for c in L[i + 1:]:
                if c.startswith("$") or not c.strip():
                    continue
                m = re.match(r"^(.{10})(.{10})(.{10})(.{10})", c)
                return int(m.group(4)) if m else None
    return None


def hf_yaml(model, out, dt="1.0"):
    return ("model: %s\noutput: %s\ndt_target: %s\ncdamp: 0.99\nfhigh_ratio: 100.0\nmode: selective\n"
            % (model, out, dt))


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="hfi_")
    try:
        write(os.path.join(d, "box.yaml"), BOX)
        run(binary, d, "generate", "box", "box.yaml")
        write(os.path.join(d, "master.k"), "*KEYWORD\n*INCLUDE\nbox.k\n*END\n")

        print("[A 독립 op]")
        write(os.path.join(d, "a.yaml"), hf_yaml("box.k", "hf_box.k"))
        rc, out = run(binary, d, "hfdamp", "a.yaml")
        check("A-1 인클루드 없는 덱 — PID 1 을 대상으로 잡는다(기준)", rc == 0 and psid(os.path.join(d, "hf_box.k")) == 1,
              out[-300:])
        write(os.path.join(d, "b.yaml"), hf_yaml("master.k", "hf_master.k"))
        rc, out = run(binary, d, "hfdamp", "b.yaml")
        check("A-2 ★메시를 인클루드한 마스터 덱 — 같은 PID 1 을 잡는다(전체로 바뀌지 않는다)",
              rc == 0 and "1 part(s) targeted" in out and psid(os.path.join(d, "hf_master.k")) == 1, out[-300:])
        check("A-3 대상 세트가 주 덱 산출에 들어간다", "*SET_PART_LIST" in open(os.path.join(d, "hf_master.k")).read())

        print("[B assemble 의 type: hfdamp]")
        write(os.path.join(d, "asm.yaml"), "base_model: master.k\noutput: asm_hf\noperations:\n  - type: hfdamp\n"
              "    dt_target: 1.0\n    cdamp: 0.99\n    fhigh_ratio: 100.0\n    mode: selective\n")
        rc, out = run(binary, d, "assemble", "asm.yaml")
        check("B-1 ★assemble 경로도 PID 1 을 잡는다", rc == 0 and "1 part(s) targeted" in out and
              psid(os.path.join(d, "asm_hf.k")) == 1, out[-300:])

        print("[C 닫힘을 다 못 읽었을 때]")
        write(os.path.join(d, "master2.k"), "*KEYWORD\n*INCLUDE\nbox.k\n*INCLUDE\nmissing.k\n*END\n")
        write(os.path.join(d, "c.yaml"), hf_yaml("master2.k", "hf_m2.k", dt="1.0e-12"))
        rc, out = run(binary, d, "hfdamp", "c.yaml")
        # ★종료 코드는 **1** 이다 — 다른 op 의 거절과 같다. 예전에는 `hfdamp_apply` 의 −1 을 그대로 돌려 셸이 255 로
        #   받았다(2026-10-16 실측). 그래서 「rc≠0」 이 아니라 값을 단정한다.
        check("C-1 파트를 못 찾았으면 전체로 바꾸지 않고 멈춘다(rc 1 · 산출 없음)",
              rc == 1 and "바꾸지 않는다" in out and not os.path.exists(os.path.join(d, "hf_m2.k")), (rc, out[-300:]))
        write(os.path.join(d, "c1b.yaml"), hf_yaml("box.k", "hf_bad.k").replace("cdamp: 0.99", "cdamp: 2.0"))
        rc, out = run(binary, d, "hfdamp", "c1b.yaml")
        check("C-1b 값 검사(cdamp 범위 밖)로 거절해도 rc 1 · 산출 없음",
              rc == 1 and "cdamp must be in" in out and not os.path.exists(os.path.join(d, "hf_bad.k")), (rc, out[-300:]))
        write(os.path.join(d, "c2.yaml"), hf_yaml("master2.k", "hf_m2b.k"))
        rc, out = run(binary, d, "hfdamp", "c2.yaml")
        check("C-2 파트를 찾았으면 쓰되 못 본 인클루드가 있다고 말한다",
              rc == 0 and psid(os.path.join(d, "hf_m2b.k")) == 1 and "읽지 못한 *INCLUDE" in out, (rc, out[-300:]))
        write(os.path.join(d, "c3.yaml"), hf_yaml("box.k", "hf_box2.k", dt="1.0e-12"))
        rc, out = run(binary, d, "hfdamp", "c3.yaml")
        check("C-3 인클루드 없는 덱에서 대상이 없으면 예전처럼 전체(PSID=0)로 — 동작 불변",
              rc == 0 and psid(os.path.join(d, "hf_box2.k")) == 0 and "Falling back to global" in out, (rc, out[-300:]))
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
