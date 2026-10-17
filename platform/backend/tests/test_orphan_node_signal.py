# 고아 절점 신호가 CLI→래퍼→플랫폼까지 이어지는지 — 끊기면 낙하판이 기기 밖에 생긴다
"""`kfile_inspect` 가 고아 절점 신호를 전달하는 계약 (2026-10-10).

왜 이 시험이 있나.

  현장 보고 — Q8 Close 덱에서 **기기 두께 14.55 mm 인데 bbox 가 67.50 mm** 로 낙하판이 기기
  밖 **53 mm** 에 생겨 충돌이 아예 없었다. 고아 절점 118,568개가 원인이었다.

  ★`info` 는 요소 기준 bbox 를 내므로 플랫폼의 `bbox_min`/`size` 는 **이미 안전하다.**
  문제는 **고아가 있다는 사실 자체**가 하류로 가지 않는 것이었다 —
  `kfile_modelmeta.run_modelmeta` 가 "model 카운트는 info 와 중복" 이라며 `model` 블록을
  통째로 버렸고, 그 안에 `orphan_nodes` 와 bbox 두 기준이 있었다.

  그래서 이 시험이 보는 것은 bbox 값이 아니라 **신호가 끊기지 않는가** 다.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.runner import kfile_inspect as ki  # noqa: E402

_BIN = Path("/home/koopark/claude/KooRemapper/platform/backend/bin/KooRemapper")


def _orphan_deck(path: Path):
    """단위 육면체 하나 + 고아 둘(x=-40, x=28). 요소 사용 폭 10, 전체 폭 68."""
    L = ["*KEYWORD", "*NODE"]
    nid, idx = 1, {}
    for k in (0, 1):
        for j in (0, 1):
            for i in (0, 1):
                idx[(i, j, k)] = nid
                L.append("%8d%16.9f%16.9f%16.9f" % (nid, i * 10.0, j * 5.0, k * 2.0))
                nid += 1
    for ox in (-40.0, 28.0):
        L.append("%8d%16.9f%16.9f%16.9f" % (nid, ox, 0.0, 0.0))
        nid += 1
    c = [idx[(0, 0, 0)], idx[(1, 0, 0)], idx[(1, 1, 0)], idx[(0, 1, 0)],
         idx[(0, 0, 1)], idx[(1, 0, 1)], idx[(1, 1, 1)], idx[(0, 1, 1)]]
    L += ["*ELEMENT_SOLID", "%8d%8d" % (1, 1) + "".join("%8d" % v for v in c),
          "*SET_NODE_LIST", "%10d" % 4, "".join("%10d" % n for n in range(1, nid)),
          "*PART", "body", "%10d%10d%10d" % (1, 1, 1),
          "*SECTION_SOLID", "%10d%10d" % (1, 1),
          "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
    path.write_text("\n".join(L) + "\n", newline="\n")


@pytest.mark.skipif(not _BIN.exists(), reason="KooRemapper 바이너리 없음")
def test_orphan_signal_reaches_the_platform():
    d = Path(tempfile.mkdtemp())
    try:
        p = d / "orph.k"
        _orphan_deck(p)
        meta = ki.inspect_kfile(p)

        # ① info 에서 오는 bbox 는 **요소 기준**이어야 한다 (이게 틀리면 낙하판이 밖에 생긴다)
        assert meta.get("bbox_min") == [0.0, 0.0, 0.0], meta.get("bbox_min")
        assert meta.get("size") == [10.0, 5.0, 2.0], meta.get("size")

        # ② ★고아 신호가 **끊기지 않는다** — 래퍼가 `model` 을 버리던 자리
        mm = meta.get("modelmeta") or {}
        assert mm.get("orphan_nodes") == 2, mm.get("orphan_nodes")
        assert mm.get("bbox_basis") == "all_nodes", mm.get("bbox_basis")

        # ③ 두 기준이 **둘 다** 오고 서로 다르다 (다르다는 것이 경고의 근거다)
        assert mm.get("bbox_all_min") == [-40, 0, 0], mm.get("bbox_all_min")
        assert mm.get("bbox_used_min") == [0, 0, 0], mm.get("bbox_used_min")
        assert mm["bbox_all_max"][0] - mm["bbox_all_min"][0] == 68
        assert mm["bbox_used_max"][0] - mm["bbox_used_min"][0] == 10

        # ④ conventions 가 기준을 말한다 (전에 '고립 절점은 들어오지 않는다' 고 거짓을 적었다)
        conv = (mm.get("conventions") or {}).get("bbox") or ""
        assert "전체" in conv and "고아" in conv, conv[:160]
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.skipif(not _BIN.exists(), reason="KooRemapper 바이너리 없음")
def test_clean_deck_reports_no_orphans():
    """고아가 없으면 0 이다 — 거짓 경보가 프런트에 뜨지 않아야 한다."""
    d = Path(tempfile.mkdtemp())
    try:
        p = d / "clean.k"
        L = ["*KEYWORD", "*NODE"]
        nid, idx = 1, {}
        for k in (0, 1):
            for j in (0, 1):
                for i in (0, 1):
                    idx[(i, j, k)] = nid
                    L.append("%8d%16.9f%16.9f%16.9f" % (nid, i * 10.0, j * 5.0, k * 2.0))
                    nid += 1
        c = [idx[(0, 0, 0)], idx[(1, 0, 0)], idx[(1, 1, 0)], idx[(0, 1, 0)],
             idx[(0, 0, 1)], idx[(1, 0, 1)], idx[(1, 1, 1)], idx[(0, 1, 1)]]
        L += ["*ELEMENT_SOLID", "%8d%8d" % (1, 1) + "".join("%8d" % v for v in c),
              "*PART", "body", "%10d%10d%10d" % (1, 1, 1),
              "*SECTION_SOLID", "%10d%10d" % (1, 1),
              "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
        p.write_text("\n".join(L) + "\n", newline="\n")
        mm = (ki.inspect_kfile(p).get("modelmeta") or {})
        assert mm.get("orphan_nodes") == 0, mm.get("orphan_nodes")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _tet_deck(path: Path, elform: int):
    """TET4 둘을 LS-DYNA 관례(n5..n8 = n4)로 적는다. `elform` 만 바꿔 1차/2차를 가른다."""
    pts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1)]
    els = [[1, 2, 3, 4], [2, 3, 4, 5]]
    L = ["*KEYWORD", "*NODE"]
    for i, (x, y, z) in enumerate(pts, 1):
        L.append("%8d%16.9f%16.9f%16.9f" % (i, x, y, z))
    L.append("*ELEMENT_SOLID")
    for e, c in enumerate(els, 1):
        L.append("%8d%8d" % (e, 1) + "".join("%8d" % v for v in c + [c[3]] * 4))
    L += ["*PART", "tets", "%10d%10d%10d" % (1, 1, 1),
          "*SECTION_SOLID", "%10d%10d" % (1, elform),
          "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
    path.write_text("\n".join(L) + "\n", newline="\n")


@pytest.mark.skipif(not _BIN.exists(), reason="KooRemapper 바이너리 없음")
def test_second_order_signal_reaches_the_platform():
    """★2차 솔리드 신호도 끊기지 않는다 — 그 파트의 부피는 실측 -48.4% 다.

    고아 절점과 **같은 종류의 조용한 사고**다. `modelmeta` 는 인벤토리라 거절하지 않고 값을
    내므로, 신호가 끊기면 프런트가 틀린 부피를 아무 표시 없이 그린다.
    """
    d = Path(tempfile.mkdtemp())
    try:
        p = d / "tet10.k"
        _tet_deck(p, elform=16)
        mm = (ki.inspect_kfile(p).get("modelmeta") or {})
        bad = mm.get("second_order_solid_pids")
        assert isinstance(bad, list) and len(bad) == 1, bad
        assert bad[0].get("pid") == 1 and bad[0].get("elform") == 16, bad
        # 파트 하나만 읽는 소비자도 알 수 있어야 한다
        parts = mm.get("parts") or []
        assert parts and parts[0].get("second_order") is True, parts[:1]
        # ★이 덱은 옛 한 줄 꼴(EID PID N1..N8)에 ELFORM 16 이다 — 칸이 모자란 2차 카드라 값을 믿을 수 없다(2026-10-17).
        #   그 파트만 geometry_basis 가 null 이고 값도 null 이다(코너를 아는 2차 솔리드는 "corners" 로 숫자를 낸다 — 아래 시험).
        assert bad[0].get("geometry_basis", "없음") is None, bad
        assert parts[0].get("geometry_basis", "없음") is None and parts[0].get("volume", "없음") is None, parts[:1]
        # 규약 — 코너로 잰 값이고 null 이 되는 자리를 적는다(2026-10-16 까지는 「쓰지 말라」 였다)
        conv = (mm.get("conventions") or {}).get("second_order", "")
        assert "코너로 잰 값" in conv and "모자란" in conv, conv
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.skipif(not _BIN.exists(), reason="KooRemapper 바이너리 없음")
def test_corner_basis_reaches_the_platform():
    """표준 꼴 TET10(Card 1 = EID PID · Card 2 = N1..N10)은 코너로 잰 값이 플랫폼까지 온다(2026-10-17).

    리더가 절점 칸을 다 읽고 코너를 제자리에 놓으므로 값이 숫자이고 `geometry_basis` 가 "corners" 다. 래퍼가 그 칸을
    버리면 프런트는 그 값이 코너로 잰 것인지 말할 수 없다.
    """
    d = Path(tempfile.mkdtemp())
    try:
        corners = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
        pts = list(corners) + [tuple((corners[a][k] + corners[b][k]) / 2 for k in range(3))
                               for a, b in ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3))]
        L = ["*KEYWORD", "*NODE"] + ["%8d%16.9f%16.9f%16.9f" % (i, *q) for i, q in enumerate(pts, 1)]
        L += ["*ELEMENT_SOLID", "%8d%8d" % (1, 1), "".join("%8d" % n for n in range(1, 11)),
              "*PART", "tet10", "%10d%10d%10d" % (1, 1, 1), "*SECTION_SOLID", "%10d%10d" % (1, 16),
              "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
        p = d / "t10.k"
        p.write_text("\n".join(L) + "\n", newline="\n")
        mm = (ki.inspect_kfile(p).get("modelmeta") or {})
        so = mm.get("second_order_solid_pids")
        assert so == [{"pid": 1, "elform": 16, "geometry_basis": "corners"}], so
        part = (mm.get("parts") or [{}])[0]
        assert part.get("geometry_basis") == "corners" and abs((part.get("volume") or 0) - 1 / 6) < 1e-6, part
        assert mm.get("orphan_nodes") == 0, mm.get("orphan_nodes")      # 중간절점까지 센다
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.skipif(not _BIN.exists(), reason="KooRemapper 바이너리 없음")
def test_first_order_deck_has_no_second_order_flag():
    """1차 덱에서는 비어 있다 — 거짓 경보가 프런트에 뜨지 않아야 한다."""
    d = Path(tempfile.mkdtemp())
    try:
        p = d / "tet4.k"
        _tet_deck(p, elform=10)
        mm = (ki.inspect_kfile(p).get("modelmeta") or {})
        assert mm.get("second_order_solid_pids") == [], mm.get("second_order_solid_pids")
        parts = mm.get("parts") or []
        assert parts and parts[0].get("second_order") is False, parts[:1]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_second_order_nulls_pass_through_with_reasons(tmp_path, monkeypatch):
    """2차 솔리드 덱에서 바이너리는 틀린 숫자 대신 null + 까닭을 낸다(2026-10-16) — 플랫폼이 **까닭까지**
    넘기는가. null 만 넘기면 프런트가 「왜 비었나」를 말할 수 없다. 바이너리 없이 통과만 본다
    (`bin/KooRemapper` 는 Drive 게시본이라 새 동작은 게시 뒤에 그 사본에서 보인다)."""
    import json
    from types import SimpleNamespace

    from app.runner import kfile_modelmeta as km

    deck = tmp_path / "t10.k"
    deck.write_text("*KEYWORD\n*END\n")
    why_o = "절점 칸이 모자란 2차 카드가 있어 못 읽은 칸의 절점을 고아로 센다 — 센 값은 상한일 뿐이다(2개)"
    why_g = "2차 솔리드(ELFORM 16) — 절점 칸이 모자란 2차 요소 2개(그 기하로 잰 값은 믿을 수 없다)"

    def fake(args, *, cwd=None, timeout=None):
        (Path(cwd) / ".mm_t10_modelmeta.json").write_text(json.dumps({
            "model": {"orphan_nodes": None, "orphan_nodes_reason": why_o,
                      "second_order_solid_pids": [{"pid": 1, "elform": 16}]},
            "parts": [{"pid": 1, "second_order": True, "geometry_reason": why_g,
                       "volume": None, "area_ext": None, "proj": None, "n_node": None}],
            "connectivity": {}, "conventions": {}}))
        return SimpleNamespace(exit_code=0, stdout="", stderr="", timed_out=False)

    monkeypatch.setattr(km, "run_kooremapper", fake)
    mm = km.run_modelmeta(deck)
    assert mm["orphan_nodes"] is None and mm["orphan_nodes_reason"] == why_o, mm
    p = mm["parts"][0]
    assert p["volume"] is None and p["geometry_reason"] == why_g, p

