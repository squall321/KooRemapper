# offset 재질 카드 MID 치환·줄바꿈·connection_mode 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_offset_material.py <KooRemapper 바이너리>

배경
  - material_card 의 @MID@(5자)를 setw(10) 문자열로 바꿔 끼워 줄이 5열 밀렸다. LS-DYNA 는 MID 칸을 공백,
    밀도 칸을 MID 로 읽었다. 카드 끝에 줄바꿈이 없어 뒤 키워드가 같은 줄에 붙었다('0.25*END' → *END 없음).
  - CZM 재질 카드는 @MID@ 를 숫자 길이만큼으로 바꿔 줄이 반대로 줄었고, 예제가 쓰는 @CZM_MID@ 는 치환되지 않았다.
  - 리터럴 MID(예: 10)는 치환되지 않아 PART mid 와 재질 카드 MID 가 어긋났다.
  - assemble 경로는 help·단독 offset 이 허용하는 connection_mode: none 을 거부했다.
"""
import os
import re
import subprocess
import sys
import tempfile

FAILS = []
GLUED = re.compile(r"[^\s$]\*(END\b|KEYWORD|MAT_|PART\b|SECTION_|NODE\b|ELEMENT_)")


def box(mid=1):
    return f"""output: box.k
lx: 20.0
ly: 10.0
lz: 2.0
nx: 4
ny: 2
nz: 1
rho: 7.85e-9
E: 210000.0
nu: 0.3
mid: {mid}
secid: 1
pid: 1
part_title: PLATE
"""


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def offset_run(binary, tag, op_yaml, cmd="offset", mid=1):
    d = tempfile.mkdtemp(prefix=f"off_{tag}_")
    open(os.path.join(d, "box.yaml"), "w").write(box(mid))
    run(binary, d, "generate", "box", "box.yaml")
    open(os.path.join(d, "off.yaml"), "w").write("base_model: box.k\noutput: out\noperations:\n" + op_yaml)
    rc, out = run(binary, d, cmd, "off.yaml")
    k = os.path.join(d, "out.k")
    if rc != 0 or not os.path.exists(k):
        check(f"offset {tag} 실행 ({cmd})", False, out[-400:])
        return None
    return k


def kparse(path):
    """줄, {pid: (secid, mid, title)}, [(키워드, 제목, 첫 데이터 줄)]"""
    L = open(path).read().splitlines()
    parts, mats = {}, []

    def skip(j):
        while j < len(L) and L[j].startswith("$"):
            j += 1
        return j

    for i, s in enumerate(L):
        u = s.strip().upper()
        if u in ("*PART", "*PART_TITLE"):
            t = skip(i + 1)
            d = skip(t + 1)
            f = [L[d][k:k + 10].strip() for k in range(0, 30, 10)]
            try:
                parts[int(f[0])] = (int(f[1] or 0), int(f[2] or 0), L[t].strip())
            except ValueError:
                pass
        elif u.startswith("*MAT"):
            j, title = skip(i + 1), None
            if u.endswith("_TITLE"):
                title, j = L[j].strip(), skip(j + 1)
            mats.append((u, title, L[j]))
    return L, parts, mats


def f10(line, n):
    return [line[k:k + 10].strip() for k in range(0, 10 * n, 10)]


def common_checks(tag, L):
    check(f"offset {tag}: *END 가 독립 줄로 있음", any(s.strip().upper() == "*END" for s in L))
    glued = [s for s in L if not s.startswith("$") and GLUED.search(s)]
    check(f"offset {tag}: 키워드가 데이터 줄에 붙지 않음", not glued, str(glued[:2]))


def card(mid_token, rho, e, pr, indent=6):
    pad = " " * indent
    return (f"{pad}*MAT_ELASTIC\n{pad}$#     mid        ro         e        pr\n"
            f"{pad}{mid_token:>10s}{rho:>10s}{e:>10s}{pr:>10s}\n")


BASE = """  - type: offset
    source_pid: 1
    element_type: solid
    thickness: 1.0
    num_layers: {layers}
    offset_direction: +z
    connection_mode: {mode}
    new_pid: 10
"""


def elastic_row_for(mats, mid):
    for u, _, dl in mats:
        if u.startswith("*MAT_ELASTIC") and f10(dl, 1)[0] == str(mid):
            return f10(dl, 4)
    return None


def main():
    binary = os.path.abspath(sys.argv[1])

    print("[offset 재질 카드 MID 칸]")
    # assemble 경로는 카드 끝 줄바꿈이 없어 뒤 키워드가 붙었다 — 두 경로 모두 본다
    for tag, token, cmd in (("@MID@", "@MID@", "offset"), ("리터럴 10", "10", "offset"),
                            ("@MID@ assemble", "@MID@", "assemble")):
        k = offset_run(binary, tag, BASE.format(layers=1, mode="tied") + "    material_card: |\n" +
                       card(token, "7.85E-09", "2.10E+05", "0.3"), cmd=cmd)
        if not k:
            continue
        L, parts, mats = kparse(k)
        common_checks(tag, L)
        m = parts.get(10, (0, 0, ""))[1]
        row = elastic_row_for(mats, m)
        check(f"offset {tag}: PART 10 의 mid 가 재질 카드 MID 칸(1~10열)과 같음", m > 0 and row is not None,
              f"mid={m} mats={[x[2] for x in mats]}")
        check(f"offset {tag}: 밀도·E·PR 이 10열 칸 그대로", row == [str(m), "7.85E-09", "2.10E+05", "0.3"], str(row))

    print("[offset CZM 재질 카드]")
    for tag, token in (("CZM @CZM_MID@", "@CZM_MID@"), ("CZM @MID@", "@MID@")):
        czm = ("    czm_material_card: |\n      *MAT_COHESIVE_MIXED_MODE\n"
               "      $#     mid        ro     roflg   intfail\n"
               f"      {token:>10s}       1.0         0       1.0\n"
               "      $#      en        et       gic      giic       xmu         t         s\n"
               "           20000     10000       0.5       0.5       2.0       1.0       1.0\n")
        k = offset_run(binary, tag, BASE.format(layers=1, mode="czm") + "    material_card: |\n" +
                       card("@MID@", "7.85E-09", "2.10E+05", "0.3") + czm)
        if not k:
            continue
        L, parts, mats = kparse(k)
        common_checks(tag, L)
        czm_mid = [p[1] for pid, p in parts.items() if "CZM" in p[2].upper()]
        rows = [f10(dl, 4) for u, _, dl in mats if u.startswith("*MAT_COHESIVE")]
        check(f"offset {tag}: CZM PART mid 가 코헤시브 카드 MID 칸과 같음",
              len(czm_mid) == 1 and czm_mid[0] > 0 and rows and rows[0][0] == str(czm_mid[0]),
              f"czm_mid={czm_mid} rows={rows}")
        check(f"offset {tag}: 코헤시브 카드 값 칸 보존 (ro roflg intfail)",
              bool(rows) and rows[0][1:] == ["1.0", "0", "1.0"], str(rows))
        check(f"offset {tag}: 자리표시 잔존 없음", not any("@" in s and "MID@" in s for s in L if not s.startswith("$")))

    print("[offset connection_mode: none — assemble 경로]")
    k = offset_run(binary, "none", BASE.format(layers=1, mode="none") + "    material_card: |\n" +
                   card("@MID@", "7.85E-09", "2.10E+05", "0.3"), cmd="assemble")
    if k:
        L, parts, mats = kparse(k)
        check("offset none: PART 10 생성, mid 정의됨", 10 in parts and elastic_row_for(mats, parts[10][1]) is not None,
              str(parts))

    print("[offset 다층 재질 material_cards]")
    multi = (BASE.format(layers=2, mode="tied") + "    material_cards:\n      - |\n" +
             card("@MID@", "7.85E-09", "2.10E+05", "0.3", 8) + "      - |\n" +
             card("@MID@", "2.70E-09", "7.00E+04", "0.33", 8))
    # 단독 offset 파서는 material_cards 를 무시했다 — 두 경로 모두 본다
    for cmd in ("offset", "assemble"):
        k = offset_run(binary, f"multi {cmd}", multi, cmd=cmd)
        if not k:
            continue
        L, parts, mats = kparse(k)
        common_checks(f"multi {cmd}", L)
        es = []
        for pid in sorted(p for p in parts if p >= 10):
            row = elastic_row_for(mats, parts[pid][1])
            es.append(row[2] if row else None)
        check(f"offset multi {cmd}: 층 PART 10·11 이 각자 재질(E)을 10열 칸으로 가리킴",
              sorted(p for p in parts if p >= 10) == [10, 11] and es == ["2.10E+05", "7.00E+04"],
              f"parts={sorted(parts)} es={es}")

    # 명시 PID 가 작으면(new_pid 3) 둘째 층부터 모델 최대+1 로 매겨져 PID 가 겹쳤다 (3, 2, 3)
    k = offset_run(binary, "pid collision", BASE.replace("new_pid: 10", "new_pid: 3").format(layers=3, mode="tied") +
                   "    material_cards:\n" + "".join("      - |\n" + card("@MID@", "7.85E-09", e, "0.3", 8)
                                                    for e in ("2.10E+05", "7.00E+04", "3.00E+03")), cmd="assemble")
    if k:
        pids = []
        L = open(k).read().splitlines()
        for i, s in enumerate(L):
            if s.strip().upper() == "*PART":
                j = i + 1
                while L[j].startswith("$"):
                    j += 1
                j += 1
                while L[j].startswith("$"):
                    j += 1
                pids.append(int(L[j][:10]))
        check("offset 명시 new_pid 3 + 3층: PART 번호 중복 없음", len(pids) == len(set(pids)) and len(pids) == 4,
              str(pids))

    print("[offset 큰 MID (7자리)]")
    k = offset_run(binary, "bigmid", BASE.format(layers=1, mode="tied") + "    material_card: |\n" +
                   card("@MID@", "7.85E-09", "2.10E+05", "0.3"), mid=1234567)
    if k:
        L, parts, mats = kparse(k)
        m = parts.get(10, (0, 0, ""))[1]
        row = elastic_row_for(mats, m)
        check("offset bigmid: 새 MID 가 7자리여도 10열 칸 안에서 정렬", m > 1234567 and
              row == [str(m), "7.85E-09", "2.10E+05", "0.3"], f"mid={m} row={row}")
        check("offset bigmid: 기존 재질(1234567) 카드 유지", elastic_row_for(mats, 1234567) is not None)

    print()
    if FAILS:
        print(f"FAIL {len(FAILS)} 건")
        for f in FAILS:
            print("  -", f)
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
