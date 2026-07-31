#!/usr/bin/env python3
# K파일을 modelmeta로 분석해 AI Data Hub SIM 레코드(파트·연결도·재료 연계)로 업로드한다.
"""KooRemapper → AI Data Hub 업로더 (k-enrichment Phase D).

흐름:
  1. KooRemapper modelmeta 실행 → 파트별 메트릭·재료·connectivity JSON
  2. 재료명으로 DataHub 재료 카드(MaterialTwin sync, DOC-MX-MAT-*) 매칭
  3. SIM 레코드 조립 — components/connectivity/eng_meta + 검색 승격
     (파트명·재료명 → subject_keywords/tags) + 첨부(K파일 kind=cae)
  4. ZIP 번들로 POST /api/ingest/bundle

사용:
  python3 tools/kr2datahub.py model.k --project S26-X --stage dv1 \
      [--variation antA] [--doe study:case] [--unit mm-t-s] [--detect] \
      [--title "..."] [--datahub http://localhost:8001] [--dry-run]

stdlib 전용 (requests 불필요).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path

DEF_HUB = "http://localhost:8001"
TEAM, GROUP = "MX", "CAE"


def http_json(url: str, data: bytes | None = None, headers: dict | None = None,
              method: str | None = None) -> dict:
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def run_modelmeta(binary: str, model: Path, outdir: Path, detect: bool) -> dict:
    cfg = outdir / "mm.yaml"
    out = outdir / "meta"
    cfg.write_text(
        f"model: {model.resolve()}\noutput: {out}\ndetect: {'true' if detect else 'false'}\n")
    r = subprocess.run([binary, "modelmeta", str(cfg)], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"modelmeta 실패:\n{r.stdout}\n{r.stderr}")
    return json.loads((outdir / "meta_modelmeta.json").read_text())


def match_material(hub: str, name: str, cache: dict) -> str | None:
    """재료명으로 DataHub 재료 카드 record_id 조회 (완전일치 우선)."""
    key = name.strip().lower()
    if not key:
        return None
    if key in cache:
        return cache[key]
    q = urllib.parse.quote(name)
    rid = None
    try:
        d = http_json(f"{hub}/api/records?q={q}&group=MAT&limit=5")
        items = d.get("items") or []
        for it in items:
            if str(it.get("title", "")).strip().lower() == key:
                rid = it["id"]
                break
        if rid is None and items:          # 유일 부분일치만 수용
            hits = [it for it in items
                    if key in str(it.get("title", "")).lower()]
            if len(hits) == 1:
                rid = hits[0]["id"]
    except Exception as e:                  # noqa: BLE001 — 매칭 실패는 비치명
        print(f"  [warn] 재료 조회 실패({name}): {e}")
    cache[key] = rid
    return rid


def next_sim_id(hub: str) -> str:
    d = http_json(f"{hub}/api/records?data_type=SIM&limit=100")
    max_seq = 0
    for it in d.get("items") or []:
        m = re.match(r"SIM-\w+-\w+-(\d{4})-(\d+)$", it.get("id", ""))
        if m:
            max_seq = max(max_seq, int(m.group(2)))
    from datetime import date
    return f"SIM-{TEAM}-{GROUP}-{date.today().year}-{max_seq + 1:010d}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("model", type=Path)
    ap.add_argument("--project", required=True, help="과제코드")
    ap.add_argument("--stage", required=True,
                    help="개발단계 코드 (pre|dv1..dvr|pv1..pvr|pra|mp)")
    ap.add_argument("--variation", default=None, help="설계안 (예: antA)")
    ap.add_argument("--doe", default=None, help="DOE 참조 study[:case]")
    ap.add_argument("--title", default=None)
    ap.add_argument("--unit", default="mm-t-s", help="단위계 (기본 mm-t-s)")
    ap.add_argument("--detect", action="store_true", help="기하학적 접촉 탐지 포함")
    ap.add_argument("--datahub", default=os.environ.get("AIDH_URL", DEF_HUB))
    ap.add_argument("--binary", default=str(Path(__file__).resolve().parents[1]
                                            / "build/linux/bin/KooRemapper"))
    ap.add_argument("--dry-run", action="store_true", help="번들만 만들고 업로드 생략")
    a = ap.parse_args()

    if not a.model.is_file():
        sys.exit(f"모델 없음: {a.model}")

    # eng_meta.dev_revision — 스키마와 동일한 분해 규칙
    m = re.fullmatch(r"(pre|dv|pv|pra|mp)([123r])?", a.stage)
    if not m or (m.group(1) in ("dv", "pv")) != bool(m.group(2)):
        sys.exit(f"stage 형식 오류: {a.stage} (dv/pv는 차수 필수, pre/pra/mp는 금지)")
    dev_rev = {"phase": m.group(1)}
    if m.group(2):
        dev_rev["round"] = m.group(2)

    with tempfile.TemporaryDirectory(prefix="kr2datahub-") as td:
        tmp = Path(td)
        print(f"[1/4] modelmeta 실행: {a.model}")
        meta = run_modelmeta(a.binary, a.model, tmp, a.detect)
        parts = meta.get("parts", [])
        conn = meta.get("connectivity", {})
        print(f"      parts={len(parts)} edges={len(conn.get('contact_edges', []))} "
              f"single={len(conn.get('single_surface', []))} "
              f"geo={len(conn.get('geometric_edges', []))}")

        print("[2/4] 재료 카드 매칭 (MaterialTwin sync 레코드)")
        cache: dict = {}
        components, kw, tags, related = [], [], [], []
        matched = 0
        for p in parts:
            mat = p.get("material", {})
            db = mat.get("db") or {}
            kf = mat.get("kfile") or {}
            name = db.get("name") or kf.get("name") or ""
            rid = match_material(a.datahub, name, cache) if name else None
            if rid:
                matched += 1
                if rid not in related:
                    related.append(rid)
            comp = {
                "pid": p["pid"], "title": p["title"],
                "elem_class": p["elem_class"], "n_elems": p["n_elems"],
                "area_ext": p["area_ext"], "volume": p["volume"], "proj": p["proj"],
                "material": {
                    "mid": mat.get("mid"), "name": name or None,
                    "category": db.get("category") or None,
                    "match_basis": (db.get("match_basis") if db else None),
                    "record_id": rid,
                },
            }
            components.append(comp)
            if p["title"]:
                kw.append(p["title"])
                tags.append("part:" + p["title"])
            if name and "mat:" + name not in tags:
                kw.append(name)
                tags.append("mat:" + name)
        print(f"      매칭 {matched}/{len(parts)} 파트, 재료 레코드 {len(related)}건 연계")

        rid = next_sim_id(a.datahub)
        title = a.title or f"{a.project} {a.stage} — {a.model.name} 모델 메타"
        eng_meta = {"project": a.project, "dev_revision": dev_rev}
        if a.variation:
            eng_meta["design_variation"] = a.variation
        if a.doe:
            st, _, case = a.doe.partition(":")
            eng_meta["doe"] = {"study": st, **({"case": case} if case else {})}

        attachments = [
            {"id": f"{rid}-A001", "record_id": rid, "number": 1, "kind": "cae",
             "caption": f"입력 K파일 — {a.model.name} ({a.unit})",
             "file_name": a.model.name, "file_path": f"{rid}/{a.model.name}",
             "extra": {"solver": "LS-DYNA", "format": "keyword", "role": "input",
                       "unit_system": a.unit,
                       "model_summary": {k: meta["model"][k]
                                         for k in ("nodes", "elements", "parts")}}},
            {"id": f"{rid}-A002", "record_id": rid, "number": 2, "kind": "data",
             "caption": "modelmeta 구조화 메타 JSON (파트 메트릭·재료·connectivity)",
             "file_name": "modelmeta.json", "file_path": f"{rid}/modelmeta.json",
             "extra": {"generator": "KooRemapper modelmeta"}},
        ]

        record = {
            "id": rid, "data_type": "SIM", "doc_type": "model_meta",
            "title": title,
            # FTS 는 title/summary 만 보므로 파트·재료명을 summary 에도 승격한다.
            "summary": (f"{a.model.name}: 파트 {len(parts)}개, 접촉 엣지 "
                        f"{len(conn.get('contact_edges', []))}건 — modelmeta 자동 추출 | "
                        + " ".join(list(dict.fromkeys(kw))[:30]))[:900],
            "project": a.project,
            "tags": ["stage:" + a.stage] + tags,
            "subject_keywords": list(dict.fromkeys(kw))[:50],
            "related_record_ids": related,
            "source_system": "KooRemapper",
            "agents": ["kooremapper-modelmeta"],
            "content": {
                "solver": "LS-DYNA",
                "inputs": {"model_file": a.model.name, "op": "modelmeta"},
                "outputs": {"report": {"conventions": meta.get("conventions", {})}},
                "eng_meta": eng_meta,
                "components": components,
                "connectivity": conn,
                "attachments": attachments,
            },
        }

        print(f"[3/4] 번들 조립: {rid}")
        zpath = tmp / "bundle.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("record.json", json.dumps(record, ensure_ascii=False, indent=1))
            z.write(a.model, f"{rid}/{a.model.name}")
            z.write(tmp / "meta_modelmeta.json", f"{rid}/modelmeta.json")

        if a.dry_run:
            out = Path(f"{rid}.zip")
            out.write_bytes(zpath.read_bytes())
            print(f"[dry-run] 번들 저장: {out}")
            return

        print(f"[4/4] 업로드: {a.datahub}/api/ingest/bundle")
        boundary = uuid.uuid4().hex
        body = (f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="bundle.zip"\r\n'
                f"Content-Type: application/zip\r\n\r\n").encode() \
            + zpath.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        resp = http_json(f"{a.datahub}/api/ingest/bundle", data=body,
                         headers={"Content-Type":
                                  f"multipart/form-data; boundary={boundary}"})
        print(json.dumps(resp, ensure_ascii=False, indent=1))
        print(f"\n완료 — 레코드 {resp.get('id', rid)}")
        print(f"  조회:  {a.datahub}/api/records/{resp.get('id', rid)}")
        print(f"  검색:  {a.datahub}/api/search?mode=fts&q=<파트명 or 재료명>")


if __name__ == "__main__":
    main()
