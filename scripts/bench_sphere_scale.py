# 합성 N각도 sphere 리포트로 반입·상세 질의 경로의 시간과 최대 메모리를 재는 P0 실측 스크립트(낙하 트윈)
"""usage — PYTHONPATH=platform/backend python3 scripts/bench_sphere_scale.py …
결과와 방법: docs/04-report/drop-twin-p0-1028.report.md · 이 박스에서는 prlimit --as 로 상한을 걸고 돌린다.

  build:   bench_sphere_scale.py build FIXTURE.html N OUT.html
  measure: bench_sphere_scale.py measure OUT.html ingest|detail
measure 는 경로 하나만 재고 JSON 한 줄을 찍는다 — 경로마다 새 프로세스로 돌려 최대 RSS 를 따로 잰다.
"""
import json, math, os, re, resource, sys, time

from app.reports import parser


def _locate(text):
    m = re.search(r"REPORT_DATA\s*=\s*\{", text)
    brace = text.index("{", m.start())
    obj, end = json.JSONDecoder().raw_decode(text, brace)
    return brace, end, obj


def build(fixture, n, out):
    t = open(fixture, encoding="utf-8", errors="replace").read()
    brace, end, d = _locate(t)
    ensure_ascii = all(ord(c) < 128 for c in t[brace:end])
    r0 = d["results"][0]
    ga = math.pi * (3 - math.sqrt(5))
    res = []
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        a = dict(r0["angle"], name=f"P{i + 1:04d}", roll=0.0,
                 pitch=round(math.degrees(math.asin(z)), 4),
                 yaw=round(math.degrees((i * ga) % (2 * math.pi)) - 180, 4))
        res.append(dict(r0, folder=f"Run_synth_{i:04d}", angle=a))
    d["results"] = res
    d["total_runs"] = d["successful_runs"] = n
    d["failed_runs"] = 0
    grown = []
    cp = d.get("contact_profile") or {}
    for k in ("pf", "ti", "tw"):
        rows = cp.get(k)
        if isinstance(rows, list) and rows and all(isinstance(r, list) and len(r) == 1 for r in rows):
            cp[k] = [r * n for r in rows]
            grown.append(k)
    ef = d.get("energy_flows") or {}
    if ef:  # 생성기는 하중경로 상세를 상위 60 각도에만 싣는다
        v0 = next(iter(ef.values()))
        d["energy_flows"] = {res[i]["folder"]: v0 for i in range(min(n, 60))}
    with open(out, "w", encoding="utf-8") as f:
        f.write(t[:brace])
        f.write(json.dumps(d, ensure_ascii=ensure_ascii))
        f.write(t[end:])
    print(json.dumps({"angles": n, "bytes": os.path.getsize(out), "contact_profile_grown": grown}))


def measure(path, mode):
    out = {"mode": mode}
    t0 = time.perf_counter()
    text = open(path, encoding="utf-8", errors="replace").read()  # services 와 같은 읽기
    t1 = time.perf_counter()
    out.update(read_s=round(t1 - t0, 3), chars=len(text))
    if mode == "ingest":  # 반입 — parse_html 한 번(그 뒤 DB 쓰기는 재지 않는다)
        study = parser.parse_html(text)
        out.update(parse_s=round(time.perf_counter() - t1, 3), cases=len(study["cases"]))
    else:  # 상세 질의 — 매번 원본을 다시 읽고 임베드 JSON 을 다시 푼다(_load_html_data 와 같은 길)
        data = parser.extract_embedded_data(text)
        t3 = time.perf_counter()
        ck = data["results"][-1]["folder"]
        parser.part_series(data, "sphere", ck, 3)
        t4 = time.perf_counter()
        parser.hotspot_clusters(data, case_key=ck)
        t5 = time.perf_counter()
        out.update(extract_s=round(t3 - t1, 3),
                   part_series_s=round(t4 - t3, 4), hotspot_clusters_s=round(t5 - t4, 4),
                   detail_total_s=round(t5 - t0, 3))
    out["maxrss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    print(json.dumps(out))


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    else:
        measure(sys.argv[2], sys.argv[3])
