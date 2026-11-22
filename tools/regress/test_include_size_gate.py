#!/usr/bin/env python3
# 인클루드 닫힘의 크기 관문 — 끌어온 파일이 남은 메모리에 비해 크면 열기 전에 rc 1 로 멈추는지 보는 회귀 시험(3차 4판 L-01)
"""인클루드 크기 관문 (2026-11-22 · 미룬 결함 3차 4판 L-01).

왜 이 시험이 있나.

  인클루드 닫힘을 읽는 op 은 끌어온 파일의 크기를 열기 전에 보지 않았다. 474 바이트 주 덱이 34 GB 희소 파일(줄바꿈이 없다 — 한 줄)을
  끌어오면 그것을 다 읽으려 해 박스 메모리를 쓰고(earlyoom 이 남의 프로세스를 죽인다), 8 GB 주소 공간 상한 아래에선 4 GB 를 쓴 뒤 rc 0 으로
  「참조 무결성 OK — 인클루드 1개를 함께 읽었습니다」 였다(카탈로그 op 59 가운데 덱을 읽는 57 이 다 그랬다). 이제 닫힘 읽기가 파일을 열기
  전에 크기를 본다 — 줄로 담는 걸음은 바이트 합 × 9, 흘려 읽는 걸음은 파일 하나 × 4 가 남은 메모리를 넘으면 까닭을 찍고 rc 1.

무엇을 보나(희소 파일 크기는 시험 때의 남은 메모리 + 1 GB — 두 규칙에 다 걸린다).
  A op 다섯(info --strict · extract-parts · cleanup-nodes · assemble offset · matswap) — rc 1 · 「너무 크다」 · 주소 공간 2 GB 상한 안에서(읽으려 했다면
    큰 할당이 실패해 다른 글로 멈춘다)
  B 대조 — 작은 인클루드는 그대로 읽는다(info rc 0 · 「인클루드 1개를 함께 읽었다」)

usage: test_include_size_gate.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS, OKS = [], []
BOX = """output: box.k
lx: 20.0
ly: 10.0
lz: 2.0
nx: 4
ny: 2
nz: 1
rho: 7.85e-9
E: 210000.0
nu: 0.3
mid: 1
secid: 1
pid: 1
part_title: PLATE
"""
OFFSET = """base_model: box.k
output: out
operations:
  - type: offset
    source_pid: 1
    element_type: solid
    thickness: 1.0
    num_layers: 1
    offset_direction: +z
    connection_mode: tied
    new_pid: 10
"""
BUNDLE = """*KEYWORD
*PARAMETER
I PID1 0
I SECID1 0
I MID1 0
I HGID1 0
*SECTION_SOLID
&SECID1 1
*MAT_ELASTIC
&MID1 1.0E-9 10.0 0.49
*HOURGLASS
&HGID1 6
*END
"""


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:500]))
    print("  %-70s %s" % (name[:70], "OK" if cond else "FAIL"))
    return cond


def avail_bytes():
    for l in open("/proc/meminfo"):
        if l.startswith("MemAvailable:"):
            return int(l.split()[1]) * 1024
    return 0


def run(binary, d, *args, as_bytes=2 * 1024 ** 3):
    p = subprocess.run(["prlimit", "--as=%d" % as_bytes, "timeout", "300", binary, *args], cwd=d, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    avail = avail_bytes()
    if avail == 0:
        print("SKIP — /proc/meminfo 의 MemAvailable 을 못 읽는다(관문이 꺼진다)")
        return 0
    tmp = tempfile.mkdtemp(prefix="include_gate_")
    try:
        d = os.path.join(tmp, "a")
        os.makedirs(d)
        open(os.path.join(d, "box.yaml"), "w").write(BOX)
        rc, out = run(binary, d, "generate", "box", "box.yaml")
        assert rc == 0, out[-300:]
        main_k = os.path.join(d, "box.k")
        body = open(main_k, encoding="utf-8").read()
        shutil.copy(main_k, os.path.join(d, "plain.k"))
        open(main_k, "w", encoding="utf-8").write(body.replace("*END", "*INCLUDE\nbig.k\n*END"))
        subprocess.run(["truncate", "-s", str(avail + 1024 ** 3), os.path.join(d, "big.k")], check=True)
        open(os.path.join(d, "x.yaml"), "w").write("model: box.k\noutput: x_out.k\nparts: [1]\nreport: x.json\n")
        open(os.path.join(d, "c.yaml"), "w").write("model: box.k\noutput: c_out.k\n")
        open(os.path.join(d, "off.yaml"), "w").write(OFFSET)
        open(os.path.join(d, "rubber.k"), "w").write(BUNDLE)
        print("[A 큰 희소 인클루드(%.1f GB) — 열기 전에 멈춘다]" % ((avail + 1024 ** 3) / 1e9))
        for args in (("info", "--strict", "box.k"), ("extract-parts", "x.yaml"), ("cleanup-nodes", "c.yaml"), ("assemble", "off.yaml"),
                     ("matswap", "box.k", "rubber.k", "1", "m_out.k")):
            rc, out = run(binary, d, *args)
            check("A %s — rc 1 · 「너무 크다」" % " ".join(args), rc == 1 and "너무 크다" in out, (rc, out[-400:]))
        print("[B 대조 — 작은 인클루드]")
        part = os.path.join(d, "part.k")
        open(part, "w", encoding="utf-8").write("*KEYWORD\n*DEFINE_CURVE\n       101\n0.0,0.0\n1.0,1.0\n*END\n")
        open(os.path.join(d, "small.k"), "w", encoding="utf-8").write(body.replace("*END", "*INCLUDE\npart.k\n*END"))
        rc, out = run(binary, d, "info", "small.k")
        check("B info small.k — rc 0 · 인클루드를 함께 읽었다", rc == 0 and "인클루드 1개를 함께 읽었다" in out, (rc, out[-300:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("결과: %d 통과 · %d 실패" % (len(OKS), len(FAILS)))
    for f in FAILS:
        print("  FAIL " + f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
