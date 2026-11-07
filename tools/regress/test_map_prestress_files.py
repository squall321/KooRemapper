#!/usr/bin/env python3
# map · prestress 가 쓰는 곁 파일(메시 사본 · CSV · 앞처리 평판 임시 파일)의 이름과 뒷정리가 문서대로인지 보는 회귀 시험
"""map · prestress 의 곁 파일 (2026-11-07 셋째 묶음).

왜 이 시험이 있나.

  · prestress 의 메시 사본 · CSV 이름을 경로 전체의 마지막 `.` 으로 만들어 `./pre` 가 `.k`, `a.d/pre` 가 `a.k` 를 썼다
    (파일 이름의 확장자가 아니라 폴더 이름의 점을 잘랐다). 이제 파일 이름의 확장자만 바꾼다.

  · map 의 `bbox_align: source` 가 평판의 크기를 바꿔 놓고 그 평판을 임시 파일로 남기지 않아, 고리 prestress 가 크기를 맞추기
    **전** 평판을 기준으로 썼다(되살린 늘림이 가짜 응력으로 들어갔다). 카탈로그와 코드 머리말은 「source 는 임시 파일을 쓴다」였다.

무엇을 보나.
  P — prestress 의 메시 사본 · CSV 가 `<output 에서 파일 이름의 확장자를 뗀 이름>.k` · `.csv` 로 나가고, 폴더 이름의 점이나
      `./` 의 점을 확장자로 보지 않는다.
  B — `bbox_align: source` 로 크기를 바꾸면 고리 prestress 의 기준이 `<output>.__preproc_flat.k` 이고(끝나면 지운다), 평판의
      K-파일 재료는 예전처럼 그대로 쓴다. 대조 — bbox_align 이 없으면 기준은 평판 그대로다.

usage: test_map_prestress_files.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-92s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def exists(d, rel):
    return os.path.exists(os.path.join(d, rel))


def prestress_names(binary, root):
    print("[P] prestress 곁 이름은 파일 이름의 확장자만 바꾼다")
    d = os.path.join(root, "p")
    os.makedirs(os.path.join(d, "a.d"))
    rc, out = run(binary, d, "generate", "--dim-i", "10", "--dim-j", "4", "arc", "demo")
    if not check("P-0 준비 — generate arc", rc == 0, out[-300:]):
        return
    pre = ["prestress", "--E", "210000", "--nu", "0.3"]
    rc, out = run(binary, d, *pre, "demo_flat.k", "demo_bent.k", "./pre")
    check("P-1 output ./pre → 메시 사본 pre.k (예전엔 `.k`)", rc == 0 and exists(d, "pre.k") and not exists(d, ".k"),
          (rc, sorted(os.listdir(d)), out[-300:]))
    check("P-2   └ dynain 은 output 그대로(./pre)", exists(d, "pre"))
    rc, out = run(binary, d, *pre, "demo_flat.k", "demo_bent.k", "a.d/pre")
    check("P-3 output a.d/pre → a.d/pre.k (예전엔 폴더 이름의 점을 잘라 a.k)",
          rc == 0 and exists(d, "a.d/pre.k") and not exists(d, "a.k"), (rc, sorted(os.listdir(d)), out[-300:]))
    rc, out = run(binary, d, *pre, "--csv", "demo_flat.k", "demo_bent.k", "a.d/q")
    check("P-4 --csv output a.d/q → a.d/q.csv · a.d/q.k (예전엔 a.csv · a.k)",
          rc == 0 and exists(d, "a.d/q.csv") and exists(d, "a.d/q.k") and not exists(d, "a.csv"),
          (rc, sorted(os.listdir(d)), out[-300:]))
    rc, out = run(binary, d, *pre, "demo_flat.k", "demo_bent.k", "r.dynain")
    check("P-5 대조 — output r.dynain → r.dynain · r.k (예전과 같다)",
          rc == 0 and exists(d, "r.dynain") and exists(d, "r.k"), (rc, out[-300:]))
    rc, out = run(binary, d, *pre, "demo_flat.k", "demo_bent.k", ".hidden")
    check("P-6 이름 첫 글자의 점은 확장자가 아니다 — output .hidden → .hidden.k",
          rc == 0 and exists(d, ".hidden.k"), (rc, sorted(os.listdir(d)), out[-300:]))


def scaled_flat_with_material(src, dst, sx):
    """평판의 X 좌표를 sx 배로 늘리고 *PART · *SECTION_SOLID · *MAT_ELASTIC(PID 1)을 *END 앞에 더한 사본."""
    out, sec = [], ""
    for line in open(src, encoding="utf-8").read().splitlines():
        if line.startswith("*"):
            sec = line.strip().upper()
            if sec == "*END":
                out += ["*PART", "flat", "%10d%10d%10d" % (1, 1, 1), "*SECTION_SOLID", "%10d%10d" % (1, 1),
                        "*MAT_ELASTIC", "%10d%10s%10s%10s" % (1, "7.85E-9", "210000.", "0.3")]
            out.append(line)
            continue
        if sec == "*NODE" and not line.startswith("$") and len(line) >= 56:
            line = line[:8] + "%16.9e" % (float(line[8:24]) * sx) + line[24:]
        out.append(line)
    with open(dst, "w", newline="\n", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def map_bbox_source(binary, root):
    print("[B] map bbox_align: source — 크기를 맞춘 평판이 고리 prestress 의 기준")
    d = os.path.join(root, "b")
    os.makedirs(d)
    rc, out = run(binary, d, "generate", "--dim-i", "10", "--dim-j", "4", "arc", "demo")
    if not check("B-0 준비 — generate arc", rc == 0, out[-300:]):
        return
    scaled_flat_with_material(os.path.join(d, "demo_flat_fine.k"), os.path.join(d, "flat_s.k"), 1.005)
    base = "bent: demo_bent.k\nflat: flat_s.k\noutput: %s.k\n%sprestress:\n  enabled: true\n  output: %s.dynain\n%s"
    src = "bbox_align: source\nbbox_align_max_drift: 50\n"
    en = "  E: 210000.0\n  nu: 0.3\n"
    with open(os.path.join(d, "b1.yaml"), "w") as f:
        f.write(base % ("m1", src, "m1", en))
    rc, out = run(binary, d, "map", "b1.yaml")
    check("B-1 source 로 크기를 바꾸면 고리 기준이 m1.k.__preproc_flat.k (예전엔 크기를 맞추기 전 flat_s.k)",
          rc == 0 and "Applied scale to detail flat" in out and "Reference (flat): m1.k.__preproc_flat.k" in out,
          (rc, [l for l in out.splitlines() if "Reference" in l or "scale" in l.lower()]))
    check("B-2   └ 임시 파일은 끝나면 지운다 · dynain 이 나온다",
          not exists(d, "m1.k.__preproc_flat.k") and exists(d, "m1.dynain"), sorted(os.listdir(d)))
    with open(os.path.join(d, "b2.yaml"), "w") as f:
        f.write(base % ("m2", src, "m2", ""))
    rc, out = run(binary, d, "map", "b2.yaml")
    check("B-3 E · nu 를 빼면 평판의 K-파일 재료를 예전처럼 쓴다(임시 기준이 카드를 옮긴다) · dynain",
          rc == 0 and "Using materials from K-file" in out and exists(d, "m2.dynain"), (rc, out[-400:]))
    with open(os.path.join(d, "b3.yaml"), "w") as f:
        f.write(base % ("m3", "", "m3", en))
    rc, out = run(binary, d, "map", "b3.yaml")
    check("B-4 대조 — bbox_align 이 없으면 기준은 평판 그대로(flat_s.k)",
          rc == 0 and "Reference (flat): flat_s.k" in out, (rc, out[-300:]))
    # 쓰기 관문 — source 가 쓰는 임시 파일도 쓸 파일이다: 그 이름의 입력(flat)이 있으면 덮기 전에 거절한다
    shutil.copyfile(os.path.join(d, "flat_s.k"), os.path.join(d, "o.k.__preproc_flat.k"))
    before = open(os.path.join(d, "o.k.__preproc_flat.k"), "rb").read()
    with open(os.path.join(d, "b5.yaml"), "w") as f:
        f.write(base.replace("flat: flat_s.k", "flat: o.k.__preproc_flat.k") % ("o", src, "o", en))
    rc, out = run(binary, d, "map", "b5.yaml")
    check("B-5 ★source 의 임시 파일 이름이 flat 이면 → rc 1 「같은 파일」 · flat 바이트 그대로 · 산출 없음",
          rc == 1 and "같은 파일" in out and open(os.path.join(d, "o.k.__preproc_flat.k"), "rb").read() == before
          and not exists(d, "o.k"), (rc, out[-300:]))

    print("[C] 실패해도 이 실행의 임시 파일을 남기지 않는다")
    os.makedirs(os.path.join(d, "outdir"))
    rc, out = run(binary, d, "map", "--bbox-align", "source", "--bbox-align-max-drift", "50",
                  "demo_bent.k", "flat_s.k", "outdir")
    check("C-1 ★앞처리 평판을 쓴 뒤 산출 쓰기가 실패해도(output 이 폴더) outdir.__preproc_flat.k 를 남기지 않는다",
          rc == 1 and "Applied scale to detail flat" in out and not exists(d, "outdir.__preproc_flat.k"),
          (rc, sorted(os.listdir(d)), out[-300:]))
    with open(os.path.join(d, "c2.yaml"), "w") as f:
        f.write((base % ("c2", src, "c2", en)).replace("  enabled: true\n", "  enabled: true\n  strain_type: bogus\n"))
    rc, out = run(binary, d, "map", "c2.yaml")
    check("C-2 ★고리가 map 뒤에 멈춰도(strain_type 오타) c2.k.__preproc_flat.k 를 남기지 않는다",
          rc == 1 and "strain_type" in out and not exists(d, "c2.k.__preproc_flat.k"), (rc, sorted(os.listdir(d)), out[-300:]))
    # flip_input 도 같은 임시 파일을 쓴다(고치기 전에도 썼다 — 고치기 전 바이너리로도 남는 것이 보인다)
    os.makedirs(os.path.join(d, "outdir2"))
    rc, out = run(binary, d, "map", "--flip-input-z", "demo_bent.k", "flat_s.k", "outdir2")
    check("C-3 ★flip_input 의 앞처리 평판도 산출 쓰기가 실패하면 지운다(outdir2.__preproc_flat.k)",
          rc == 1 and not exists(d, "outdir2.__preproc_flat.k"), (rc, sorted(os.listdir(d)), out[-300:]))
    with open(os.path.join(d, "c4.yaml"), "w") as f:
        f.write((base % ("c4", "flip_input_z: true\n", "c4", en)).replace("  enabled: true\n",
                                                                         "  enabled: true\n  strain_type: bogus\n"))
    rc, out = run(binary, d, "map", "c4.yaml")
    check("C-4 ★flip_input 고리가 map 뒤에 멈춰도 c4.k.__preproc_flat.k 를 남기지 않는다",
          rc == 1 and not exists(d, "c4.k.__preproc_flat.k"), (rc, sorted(os.listdir(d)), out[-300:]))


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="mpf_")
    try:
        prestress_names(binary, root)
        map_bbox_source(binary, root)
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
