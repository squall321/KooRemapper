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
