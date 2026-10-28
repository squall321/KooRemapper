# sphere 리포트 곁파일(blockstore) — 나눴다 합치면 같고, 가벼운 본으로도 상세 함수가 같은 답을 내는지
"""Unit tests for app.reports.blockstore (no DB).

Uses the new-format one-angle fixture, widened to several angles whose series and
peaks differ per angle so a mix-up between cases shows up as a failure.
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.reports import blockstore, parser

_NEW = Path("/data/koopark/report_fixtures/sphere_hotspot_v1018/report.html")
needs = pytest.mark.skipif(not _NEW.exists(), reason="새 판 sphere 고정본 없음")


def _j(x) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False, default=str)


def _bump(v, i):
    return v + i if isinstance(v, (int, float)) and not isinstance(v, bool) else v


def _multi(n: int = 5) -> dict:
    d = parser.extract_embedded_data(_NEW.read_text(encoding="utf-8", errors="replace"))
    r0 = d["results"][0]
    res = []
    for i in range(n):
        r = copy.deepcopy(r0)
        r["folder"] = f"Run_t_{i:03d}"
        r["angle"] = {**r0["angle"], "name": f"P{i + 1:04d}", "pitch": float(10 * i)}
        for p in r["parts"].values():
            p["peak_stress"] = _bump(p.get("peak_stress"), i)
            ts = p.get("stress_ts")
            if isinstance(ts, dict) and isinstance(ts.get("max"), list):
                ts["max"] = [_bump(v, i) for v in ts["max"]]
        res.append(r)
    d["results"] = res
    cp = d.get("contact_profile") or {}
    for k in ("pf", "ti", "tw"):
        if isinstance(cp.get(k), list):
            cp[k] = [row * n if isinstance(row, list) and len(row) == 1 else row for row in cp[k]]
    return d


@needs
def test_split_then_merge_is_identity():
    full = _multi()
    slim, heavy = blockstore.split(full)
    for r in slim["results"]:
        for p in r["parts"].values():
            assert not any(k.endswith("_ts") for k in p)
    assert all(heavy)  # 각도마다 시계열이 실제로 있었다
    for i, h in enumerate(heavy):
        blockstore.merge_case(slim, i, h)
    assert slim == full


@needs
def test_slim_answers_detail_queries_like_full():
    full = _multi()
    slim, _ = blockstore.split(full)
    key = full["results"][2]["folder"]
    assert _j(parser.hotspot_clusters(slim)) == _j(parser.hotspot_clusters(full))
    assert _j(parser.hotspot_clusters(slim, case_key=key)) == _j(parser.hotspot_clusters(full, case_key=key))
    assert _j(parser.contact_profile(slim, "sphere")) == _j(parser.contact_profile(full, "sphere"))
    assert _j(parser.scatter_analysis(slim, "sphere")) == _j(parser.scatter_analysis(full, "sphere"))
    assert _j(parser.case_energy(slim, "sphere", None)) == _j(parser.case_energy(full, "sphere", None))
    assert _j(parser.extract_geometry(slim, "sphere")) == _j(parser.extract_geometry(full, "sphere"))
    assert _j(parser.analytics_summary(slim)) == _j(parser.analytics_summary(full))
    assert _j(parser.parse_data(slim)) == _j(parser.parse_data(full))  # 정규화(반입)도 시계열을 안 쓴다


@needs
def test_part_series_needs_only_its_case():
    full = _multi()
    slim, heavy = blockstore.split(full)
    i = 3
    key = full["results"][i]["folder"]
    pid = int(next(iter(full["results"][i]["parts"])))
    blockstore.merge_case(slim, i, heavy[i])
    got = parser.part_series(slim, "sphere", key, pid)
    assert got["stress_ts"] is not None
    assert _j(got) == _j(parser.part_series(full, "sphere", key, pid))


@needs
def test_write_read_freshness_and_remove(tmp_path):
    html = tmp_path / "report.html"
    shutil.copyfile(_NEW, html)
    full = _multi()
    meta = blockstore.write(html, full, "sha-a")
    d = blockstore.sidecar_dir(html)
    assert d.name == ".report.html.blocks" and d.is_dir()
    assert not list(tmp_path.glob(".report.html.blocks.*"))  # 임시 폴더를 남기지 않았다
    assert blockstore.is_fresh(blockstore.read_meta(html), "sha-a")
    assert not blockstore.is_fresh(blockstore.read_meta(html), "sha-b")
    assert not blockstore.is_fresh(blockstore.read_meta(html), None)
    slim, heavy = blockstore.split(full)
    assert _j(blockstore.load_slim(html)) == _j(slim)
    assert _j(blockstore.load_case(html, 2)) == _j(heavy[2])
    assert meta["n_cases"] == 5 and meta["case_index"][full["results"][4]["folder"]] == 4
    # 블록 목록은 전체 기준 — 모양은 같고, results 크기는 전체와 2% 안, 나머지 블록은 같다.
    want, got = parser.list_blocks(full), meta["blocks"]
    def shape(bl):
        return [{k: v for k, v in b.items() if k != "bytes"} for b in bl["blocks"]]
    assert shape(got) == shape(want)
    wb = {b["name"]: b["bytes"] for b in want["blocks"]}
    gb = {b["name"]: b["bytes"] for b in got["blocks"]}
    assert abs(gb["results"] - wb["results"]) <= 0.02 * wb["results"]
    assert {k: v for k, v in gb.items() if k != "results"} == {k: v for k, v in wb.items() if k != "results"}
    blockstore.remove(html)
    assert not d.exists() and html.exists()
