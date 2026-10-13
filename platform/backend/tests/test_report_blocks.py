# 리포트에 있는 블록이 플랫폼에서 **도달 불가**로 남지 않는지 — 생성기가 키를 늘리면 빨개진다
"""임베드 블록 전수 접근 계약 (2026-10-13).

왜 이 시험이 있나.

  "핫스팟 클러스터 들어있나" 를 재 보니 생성기에는 있고(`DATA.hotspot`, 실측 102 레코드·
  105 군집) **플랫폼이 버리고 있었다.** 전수로 세니 deep 21키 중 11, impact 27키 중 18 이
  어디에도 도달하지 않았다. ④ 고아 절점·`modelmeta` 2차 솔리드와 **같은 부류의 세 번째**다.

  원인은 하나다 — 정규화(`normalize_*`)가 **허용 목록**이라서, 생성기가 키를 늘리면 플랫폼은
  가만히 있어도 뒤처지고 **그 사실이 보이지 않는다**(에러도 경고도 없다).

  그래서 이 시험은 두 가지를 못 박는다.
    ① 모든 최상위 블록은 `get_block` 으로 **꺼낼 수 있다**(도달 불가가 없다).
    ② 지금 '정규화가 해석하지 않는' 블록 목록을 **이름으로 고정**한다 — 생성기가 키를 늘리면
      이 목록이 커져서 빨개지고, 사람이 "새 것이 생겼다" 를 **알게 된다**.
      ②가 요점이다. 허용 목록을 잘 관리하는 것보다 **잊을 수 없게 만드는** 쪽이 낫다.

실제 리포트가 없는 호스트에서는 건너뛴다(합성으로는 ②의 뜻이 없다).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.reports import parser as P  # noqa: E402

_DEEP = Path("/data/koopark/Test_hs_shell_e2e/report.html")
_SPHERE = Path("/data/SmartTwinPostprocessor/lib/koo_sphere_report/examples/Test_001_report.html")
_IMPACT = Path("/data/koopark/Test_Impact_A/impact_report.html")

# ★지금 정규화가 해석하지 않는 블록 — **이름으로 고정한다.**
# 늘어나면: 생성기가 키를 늘렸다는 뜻이다. 줄어들면: 누군가 해석을 붙였다는 뜻이다.
# 어느 쪽이든 이 줄을 **의식해서** 고쳐야 한다. 그게 이 상수의 목적이다.
EXPECTED_UNREAD = {
    "deep": {"element_quality", "hotspot", "label", "peak_element_tensors", "renders"},
    "sphere": set(),
    "impact": {
        "clusters", "contact_profile", "deep_analytics", "device_geometry", "doe_analysis",
        "energy_conservation_tolerance", "energy_flow_max_ie", "energy_flow_thresholds",
        "faces", "impactor_mesh", "insights", "part_motion", "physics", "positions",
        "risk_score", "set_report", "solver_quality", "trajectories",
    },
}

# 해석하지 않더라도 **일급 함수**가 따로 다루는 블록 — '버려짐' 이 아니다.
FIRST_CLASS = {"hotspot": "hotspot_clusters()", "clusters": "behavior_clusters()",
               "doe_analysis": "analytics_summary()", "deep_analytics": "analytics_summary()",
               "insights": "analytics_summary()", "physics": "analytics_summary()",
               "solver_quality": "analytics_summary()", "contact_profile": "analytics_summary()",
               "set_report": "analytics_summary()"}


def _raw(path: Path):
    return P.extract_embedded_data(path.read_text(encoding="utf-8", errors="replace"))


CASES = [("deep", _DEEP), ("sphere", _SPHERE), ("impact", _IMPACT)]


@pytest.mark.parametrize("kind,path", CASES)
def test_every_block_is_reachable(kind, path):
    """①도달 불가가 없다 — 목록에 뜨는 모든 블록을 `get_block` 으로 꺼낼 수 있다."""
    if not path.exists():
        pytest.skip(f"실제 리포트 없음: {path}")
    raw = _raw(path)
    listing = P.list_blocks(raw)
    assert listing["n_blocks"] == len(raw), (listing["n_blocks"], len(raw))
    for b in listing["blocks"]:
        got = P.get_block(raw, b["name"], max_bytes=400_000)
        assert got["found"] is True, (b["name"], got.get("note"))


@pytest.mark.parametrize("kind,path", CASES)
def test_unread_block_set_is_pinned(kind, path):
    """②'해석되지 않는 블록' 집합을 이름으로 고정 — 생성기가 키를 늘리면 여기서 잡는다."""
    if not path.exists():
        pytest.skip(f"실제 리포트 없음: {path}")
    raw = _raw(path)
    unread = {b["name"] for b in P.list_blocks(raw)["blocks"] if not b["read_by_parser"]}
    want = EXPECTED_UNREAD[kind]
    added, removed = unread - want, want - unread
    assert not added, (
        f"{kind}: 정규화가 모르는 **새 블록**이 생겼다 → {sorted(added)}. "
        "해석을 붙이거나 EXPECTED_UNREAD 를 의식해서 고쳐라")
    assert not removed, (
        f"{kind}: 해석이 붙은 블록이 있다 → {sorted(removed)}. EXPECTED_UNREAD 에서 빼라")


def test_hotspot_clusters_are_first_class():
    """★원래 질문 — 핫스팟 군집이 꺼내 쓸 수 있는 형태로 나온다."""
    if not _DEEP.exists():
        pytest.skip("실제 deep 리포트 없음")
    h = P.hotspot_clusters(_raw(_DEEP), top=5)
    assert h["available"] is True
    assert h["n_records"] > 0 and h["n_clusters"] > 0
    assert set(h["criteria"]) >= {"von_mises"}, h["criteria"]
    c = h["clusters"][0]
    for k in ("part_id", "criterion", "center", "radius_enclosing", "element_count",
              "stress_max", "volume", "peak_element_id", "peak_time",
              "top_percent", "threshold_value", "distance_threshold"):
        assert k in c, k
    # 절대값 정렬 — direction=min 기준은 값이 음수다
    vals = [abs(x["stress_max"]) for x in h["clusters"] if x.get("stress_max") is not None]
    assert vals == sorted(vals, reverse=True), vals
    # 상한을 넘으면 **잘랐다고 말한다**
    assert h["truncated"]["total"] == h["n_clusters"]


def test_hotspot_absent_is_said_not_faked():
    """핫스팟을 안 돌린 리포트에서는 '없다' 고 말한다 — 빈 목록으로 조용히 넘기지 않는다."""
    if not _SPHERE.exists():
        pytest.skip("실제 sphere 리포트 없음")
    h = P.hotspot_clusters(_raw(_SPHERE))
    assert h["available"] is False and "hotspot-clusters" in h["note"]


def test_behavior_clusters_report_degeneracy_and_mock():
    """★선언한 군집 수와 **실제로 쓰인** 수가 다르면 말한다(실측 4 선언 / 1 사용)."""
    if not _IMPACT.exists():
        pytest.skip("실제 impact 리포트 없음")
    b = P.behavior_clusters(_raw(_IMPACT))
    assert b["available"] is True
    assert b["n_clusters"] == 4 and b["n_archetypes_used"] == 1, (b["n_clusters"], b["n_archetypes_used"])
    assert b["degenerate"] is True and "갈리지 않았다" in b["degenerate_note"]
    assert b["is_mock"] is False          # 합성이면 크게 적어야 한다
    assert b["features_used"], "군집에 쓴 특징을 밝혀야 한다"


def test_analytics_summary_uses_generator_summaries_and_flags_not_computed():
    """요약은 생성기 `summary` 를 **그대로** 쓰고, 미계산 플래그를 숨기지 않는다."""
    if not _IMPACT.exists():
        pytest.skip("실제 impact 리포트 없음")
    raw = _raw(_IMPACT)
    a = P.analytics_summary(raw)
    names = {b["name"] for b in a["blocks"]}
    assert {"doe_analysis", "deep_analytics", "insights", "physics", "solver_quality"} <= names
    phys = [b for b in a["blocks"] if b["name"] == "physics"][0]
    rm = [s for s in phys["subs"] if s["name"] == "RestitutionMap"][0]
    # 생성기 값 그대로여야 한다 — 다시 계산하면 화면 숫자와 조용히 갈린다
    assert rm["summary"] == raw["physics"]["RestitutionMap"]["summary"]
    assert "raw_access_note" in a, "요약이 원본을 가리지 않는다고 말해야 한다"


def test_analytics_summary_does_not_hide_raw():
    """요약이 원본을 가리지 않는다 — 같은 데이터를 끝까지 꺼낼 수 있다."""
    if not _IMPACT.exists():
        pytest.skip("실제 impact 리포트 없음")
    raw = _raw(_IMPACT)
    g = P.get_block(raw, "doe_analysis", path="worst_position")
    assert g["found"] is True and g["value"] == raw["doe_analysis"]["worst_position"]
    bad = P.get_block(raw, "doe_analysis", path="nope.deeper")
    assert bad["found"] is False and "경로가 끊겼다" in bad["note"]


def test_get_block_truncates_loudly():
    """큰 블록을 잘랐으면 **잘랐다고 말한다** — 조용히 자르면 전체를 본 줄로 안다."""
    if not _IMPACT.exists():
        pytest.skip("실제 impact 리포트 없음")
    raw = _raw(_IMPACT)
    g = P.get_block(raw, "results", max_bytes=5_000)
    assert g["found"] is True and g["truncated"]["kind"] in ("bytes", "limit")
    assert g["truncated"]["total"] > g["truncated"]["returned"]
    assert "잘라서" in g.get("note", "")


def test_deep_part_series_covers_all_series_blocks():
    """★전에는 `stress` 하나만 읽어 주응력·주변형·변형 시계열이 전부 끊겼다."""
    if not _DEEP.exists():
        pytest.skip("실제 deep 리포트 없음")
    raw = _raw(_DEEP)
    assert len(P.DEEP_SERIES_BLOCKS) == 7, P.DEEP_SERIES_BLOCKS
    present = {b for b in P.DEEP_SERIES_BLOCKS if raw.get(b)}
    assert len(present) >= 4, present          # 이 리포트는 네 개가 비어 있지 않다
    pid = int(sorted(raw["parts"], key=int)[0])
    got = None
    for cand in sorted(raw["parts"], key=int):
        r = P.part_series(raw, "deep", "single", int(cand))
        if len(r.get("series_blocks") or []) >= 2:
            got, pid = r, int(cand)
            break
    assert got is not None, "두 개 이상의 시계열을 가진 파트가 없다"
    assert "stress" in got and got["stress"], "하위 호환 — `stress` 자리는 그대로여야 한다"
    for blk in got["series_blocks"]:
        bucket = got["stress"] if blk == "stress" else got[blk]
        q, v = next(iter(bucket.items()))
        assert v["t"] and v["max"], (blk, q)
        assert "unit" in v and "time_of_max" in v, (blk, q)
