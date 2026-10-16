# tools/kr2datahub.py 업로더 시험 — 기본은 미리보기(올리지 않는다), --upload 일 때만 허브에 올린다
"""S26-DEMO 시험 카드 3장이 운영 허브에 올라가 kooremapper-modelmeta 라는 빈 전문가 밑에 쌓였다
(HWAX 요청서 10-15 K6-2). 예전 업로더는 --dry-run 을 줄 때만 멈췄고, --datahub 기본값이
localhost:8001 이라 운영 박스에서 그냥 돌리면 운영 허브로 갔다. 붙이는 전문가 키도 허브에 등록된
적이 없었다. 네트워크·modelmeta 바이너리는 쓰지 않는다(가짜로 바꾼다).
"""
from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parents[3] / "tools" / "kr2datahub.py"
_HUB = "http://hub.invalid"   # 가짜 http_json 이 막지 못해도 어디에도 닿지 않는 주소


@pytest.fixture
def kr(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("kr2datahub_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    calls: list[tuple[str, bool]] = []

    def fake_http_json(url, data=None, headers=None, method=None):
        calls.append((url, data is not None))
        if url.endswith("/api/ingest/bundle"):
            return {"id": "SIM-MX-CAE-2026-0000000001"}
        return {"items": []}

    def fake_modelmeta(binary, model, outdir, detect):
        meta = {"parts": [{"pid": 1, "title": "Board", "elem_class": "shell", "n_elems": 10,
                           "area_ext": 1.0, "volume": 0.1, "proj": {},
                           "material": {"mid": 1, "kfile": {"name": "FR4"}}}],
                "connectivity": {}, "model": {"nodes": 4, "elements": 1, "parts": 1}}
        (outdir / "meta_modelmeta.json").write_text(json.dumps(meta))
        return meta

    monkeypatch.setattr(mod, "http_json", fake_http_json)
    monkeypatch.setattr(mod, "run_modelmeta", fake_modelmeta)
    monkeypatch.chdir(tmp_path)
    model = tmp_path / "deck.k"
    model.write_text("*KEYWORD\n*END\n")

    def run(*extra: str) -> int:
        monkeypatch.setattr(sys, "argv", ["kr2datahub.py", str(model), "--project", "S26-X",
                                          "--stage", "dv1", "--datahub", _HUB, *extra])
        try:
            mod.main()
        except SystemExit as exc:
            return exc.code
        return 0

    mod.run, mod.calls = run, calls
    return mod


def _posts(kr) -> list[str]:
    return [url for url, posted in kr.calls if posted]


def test_default_is_a_preview_that_does_not_upload(kr, tmp_path):
    assert kr.run() == 0
    assert _posts(kr) == []   # 올리지 않는다
    zips = list(tmp_path.glob("SIM-*.zip"))
    assert len(zips) == 1     # 번들은 남겨 미리 본다
    rec = json.loads(zipfile.ZipFile(zips[0]).read("record.json"))
    # 붙이는 전문가는 허브에 등록된 키다 — 없는 키는 적재가 빈 전문가를 만들거나(예전) 거절한다.
    assert rec["agents"] == ["sim-drop-impact"] == [kr.HUB_AGENT]


def test_upload_flag_posts_the_bundle(kr, tmp_path):
    assert kr.run("--upload") == 0
    assert _posts(kr) == [f"{_HUB}/api/ingest/bundle"]
    assert list(tmp_path.glob("SIM-*.zip")) == []   # 올릴 때는 미리보기 번들을 남기지 않는다


def test_second_order_part_carries_null_geometry_with_reason(kr, tmp_path, monkeypatch):
    """2차 솔리드 파트의 기하는 null 로 오고 까닭이 함께 실린다 — 1차 파트의 칸 꼴은 그대로다."""
    why = "2차 솔리드(ELFORM 16) — 앞 8개만 저장한다"

    def fake_modelmeta(binary, model, outdir, detect):
        meta = {"parts": [
            {"pid": 1, "title": "Tet", "elem_class": "solid", "n_elems": 2, "second_order": True,
             "geometry_reason": why, "area_ext": None, "volume": None, "proj": None,
             "material": {"mid": 1, "kfile": {"name": "AL"}}},
            {"pid": 2, "title": "Board", "elem_class": "shell", "n_elems": 10, "second_order": False,
             "geometry_reason": None, "area_ext": 1.0, "volume": 0.1, "proj": {},
             "material": {"mid": 2, "kfile": {"name": "FR4"}}}],
            "connectivity": {}, "model": {"nodes": 4, "elements": 1, "parts": 2}}
        (outdir / "meta_modelmeta.json").write_text(json.dumps(meta))
        return meta

    monkeypatch.setattr(kr, "run_modelmeta", fake_modelmeta)
    assert kr.run() == 0
    rec = json.loads(zipfile.ZipFile(next(tmp_path.glob("SIM-*.zip"))).read("record.json"))
    tet, board = rec["content"]["components"]
    assert tet["volume"] is None and tet["area_ext"] is None and tet["geometry_reason"] == why
    assert "geometry_reason" not in board and board["volume"] == 0.1

