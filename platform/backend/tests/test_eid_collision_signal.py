# 요소 번호 겹침으로 리더가 잃은 수(DF-14)가 modelmeta → 플랫폼 파일 메타까지 끊기지 않고 오는지
"""`kfile_modelmeta` 가 요소 번호 겹침 신호를 넘기는 계약 (2026-11-17 · DF-14 · 사용자 결정 「감지 · 경고 · 쓰기 거절」).

왜 이 시험이 있나.

  리더는 요소를 번호 하나로 한 표에 담아, 솔리드 · 셸처럼 족을 건넌 번호(LS-DYNA 는 받는다)도 앞 정의를 말없이 잃었다. 실제 덱에서
  파트 목록이 944 파트 줄었는데 화면 · MCP 는 그 사실을 알 길이 없었다. 바이너리는 이제 `model.element_id_collisions` ·
  `model.parts_missing` 을 내고, `run_modelmeta` 는 `model` 블록에서 칸을 골라 넘기므로 여기서 빠지면 신호가 끊긴다
  (2026-10-10 고아 절점 신호가 같은 자리에서 끊겼다 — `test_orphan_node_signal.py`).

  바이너리 동작은 `tools/regress/test_eid_collision_ops.py` 가 잰다. 여기서는 가짜 바이너리로 통과만 본다
  (`bin/KooRemapper` 는 Drive 게시본이라 새 칸은 게시 뒤에 그 사본에서 보인다).
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.runner import kfile_modelmeta as km  # noqa: E402


def _fake_with(model):
    def fake(args, *, cwd=None, timeout=None):
        (Path(cwd) / ".mm_d_modelmeta.json").write_text(json.dumps({
            "model": model, "parts": [{"pid": 2}], "connectivity": {}, "conventions": {}}))
        return SimpleNamespace(exit_code=0, stdout="", stderr="", timed_out=False)
    return fake


def test_collision_counts_reach_the_platform(tmp_path, monkeypatch):
    deck = tmp_path / "d.k"
    deck.write_text("*KEYWORD\n*END\n")
    monkeypatch.setattr(km, "run_kooremapper", _fake_with(
        {"orphan_nodes": 81765, "orphan_nodes_reason": None, "element_id_collisions": 37466, "parts_missing": 944}))
    mm = km.run_modelmeta(deck)
    assert mm["element_id_collisions"] == 37466 and mm["parts_missing"] == 944, mm
    assert mm["orphan_nodes"] == 81765, mm


def test_old_binary_without_the_fields_gives_none(tmp_path, monkeypatch):
    """옛 바이너리(11-08 판)는 칸을 내지 않는다 — 0 으로 지어내지 않고 None 으로 둔다(「겹침 없음」 과 「모름」 을 가른다)."""
    deck = tmp_path / "d.k"
    deck.write_text("*KEYWORD\n*END\n")
    monkeypatch.setattr(km, "run_kooremapper", _fake_with({"orphan_nodes": 0, "orphan_nodes_reason": None}))
    mm = km.run_modelmeta(deck)
    assert mm["element_id_collisions"] is None and mm["parts_missing"] is None, mm
