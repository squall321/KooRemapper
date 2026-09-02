# 물성 카드 되쓰기·레이크 대조 회귀 — 조용히 망가지는 자리를 못 박는다
"""실행: `/home/koopark/claude/StepForge/.venv/bin/pytest scripts/test_material_sync.py -q`
(이 리포엔 파이썬 venv 가 없어 형제 리포의 것을 빌린다 — 순수 파이썬 테스트다.)
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from material_cards import (CARD_FIELDS, CardEditError, data_line_index,  # noqa: E402
                            set_card_field, write_float)
import material_sync as ms  # noqa: E402

CARD = ("*MAT_PLASTIC_KINEMATIC_TITLE\n"
        "SUS201_annealed Kinematic Pure\n"
        "$      MID        RO         E        PR      SIGY      ETAN      BETA\n"
        "    130501 7.800e-09  200000.0    0.3000    260.00    990.72    0.0000\n")


# ── 카드 되쓰기 ──────────────────────────────────────────────────────────────
def test_data_line_is_not_the_title() -> None:
    """`_TITLE` 카드의 제목은 `*`·`$` 로 시작하지 않는다 — 그걸 데이터로 오인하면
    **제목 자리에 물성값을 써 넣는다**(실측으로 밟은 함정)."""
    assert data_line_index(CARD) == 3
    out = set_card_field(CARD, "MAT_PLASTIC_KINEMATIC", "E", 199500.0)
    assert out.splitlines()[1] == "SUS201_annealed Kinematic Pure"


def test_only_the_named_column_changes() -> None:
    out = set_card_field(CARD, "MAT_PLASTIC_KINEMATIC", "E", 199500.0)
    a, b = CARD.splitlines()[3], out.splitlines()[3]
    assert b[20:30].strip() == "199500.0"
    assert a[:20] == b[:20] and a[30:] == b[30:], "옆 칸이 함께 움직였다"


def test_format_is_inherited() -> None:
    """있던 칸의 서식을 흉내 낸다 — 지수 표기는 지수로, 소수 자릿수는 그대로."""
    out = set_card_field(CARD, "MAT_PLASTIC_KINEMATIC", "RHO", 7.85e-9)
    assert out.splitlines()[3][10:20].strip() == "7.850e-09"
    out = set_card_field(CARD, "MAT_PLASTIC_KINEMATIC", "PR", 0.27)
    assert out.splitlines()[3][30:40].strip() == "0.2700"


def test_derived_fields_are_refused() -> None:
    """MOONEY·VISCOELASTIC 의 E·PR 은 카드에 칸이 없다(계산값이다).
    없는 칸에 쓰려 하면 **거절**해야 한다 — 조용히 옆 칸을 먹으면 카드가 망가진다."""
    for mat_type, field in (("MAT_VISCOELASTIC", "E"), ("MAT_MOONEY-RIVLIN_RUBBER", "E"),
                            ("MAT_VISCOELASTIC", "SIGY")):
        assert field not in CARD_FIELDS[mat_type]
        with pytest.raises(CardEditError, match="칸이 없다"):
            set_card_field(CARD.replace("MAT_PLASTIC_KINEMATIC", mat_type),
                           mat_type, field, 1.0)


def test_overflow_is_refused_not_truncated() -> None:
    """10칸을 넘는 값은 **쓰지 않는다** — 넘치면 옆 칸을 먹어 카드가 조용히 망가진다."""
    line = "    130501 7.800e-09  200000.0"
    assert write_float(line, 20, 1.0)[20:30].strip() == "1.0"
    # `%10.1f` 로는 302칸이 되는 값 — 서식을 지수로 좁혀 10칸에 담는다
    assert write_float(line, 20, 1.234e300)[20:30] == "1.234e+300"
    # 부호가 붙으면 11칸이라 담을 수 없다 → 거절
    with pytest.raises(CardEditError, match="넘친다"):
        write_float(line, 20, -1.234e300)


# ── 대조·판단 ────────────────────────────────────────────────────────────────
def _pair(used_mech, lake_val, key="physical.density", mat_type="MAT_ELASTIC",
          tier=1, method="measured"):
    used = {"1": {"name": "X", "mat_type": mat_type, "mechanical": dict(used_mech)}}
    lake = {"X": {"name": "X", "category": "metal", "props": {key: {
        "value_num": lake_val, "method": method, "quality_tier": tier,
        "candidates": 1, "spread_rel": None, "src_kind": "journal",
        "src_title": "t", "src_doi": None, "src_year": 2026}}}}
    pairs, unmatched = ms.match(used, lake, {})
    return ms.compare(pairs, 0.05), unmatched


def test_si_is_converted_not_copied() -> None:
    """레이크는 SI, 사용 집합은 t/mm/s — 환산을 빼먹으면 12자리가 어긋난다."""
    found, _ = _pair({"RHO": 7.8e-9}, 7850.0)           # kg/m³ → t/mm³
    assert found[0]["verdict"] == "일치" and abs(found[0]["new"] - 7.85e-9) < 1e-15
    found, _ = _pair({"E": 200000.0}, 2.0e11, key="mechanical.youngs_modulus")
    assert found[0]["verdict"] == "일치"                 # Pa → MPa


def test_out_of_band_values_are_dropped() -> None:
    """환산 뒤 말이 안 되는 값은 쓰지 않는다 — 단위를 잘못 읽은 값이 조용히 들어가는
    것이 이 판에서 가장 흔한 사고다."""
    found, _ = _pair({"RHO": 7.8e-9}, 7.85e9)            # 단위를 두 번 곱한 꼴
    assert found[0]["verdict"] == "범위밖"
    assert not ms.proposals(found)


def test_soft_adhesive_modulus_is_not_mistaken_for_a_unit_error() -> None:
    """연질 PSA 의 실측 E 는 0.09MPa 다 — 밴드가 그것까지 받아야 한다(실측으로 걸렸다)."""
    found, _ = _pair({"E": 1.2}, 8.94e4, key="mechanical.youngs_modulus")
    assert found[0]["verdict"] != "범위밖"


def test_large_differences_are_held_back_for_a_human() -> None:
    """차이가 크면 교정이 아니라 **짝을 잘못 지은 것**일 때가 많다.
    실측 — `NBR Cushion Rubber`(1.3 g/cc)가 같은 이름의 스펀지 데이터시트(0.15)와
    짝지어져 -88% 갱신을 제안했다."""
    found, _ = _pair({"RHO": 1.3e-9}, 150.0)
    assert found[0]["verdict"] == "차이(큼·짝 확인)"
    assert not ms.proposals(found)
    assert ms.proposals(found, include_large=True), "확인 뒤에는 넣을 수 있어야 한다"


def test_weak_evidence_is_not_proposed() -> None:
    found, _ = _pair({"RHO": 7.8e-9}, 7000.0, tier=5, method="estimated")
    assert found[0]["verdict"] == "차이(근거약함)"
    assert not ms.proposals(found)


def test_ambiguous_names_are_not_matched() -> None:
    """같은 정규화 이름 후보가 여럿이면 **고르지 않는다** — 엉뚱한 물성이 붙는다."""
    used = {"1": {"name": "SUS 304", "mat_type": "MAT_ELASTIC", "mechanical": {}}}
    lake = {"SUS-304": {"name": "SUS-304", "category": "m", "props": {}},
            "sus304": {"name": "sus304", "category": "m", "props": {}}}
    pairs, unmatched = ms.match(used, lake, {})
    assert not pairs and unmatched[0]["reason"] == "동명 후보 여럿"
    # 별칭으로 사람이 지목하면 붙는다
    pairs, _ = ms.match(used, lake, {"SUS 304": "sus304"})
    assert pairs["1"]["how"] == "alias"


def test_overlay_round_trip_keeps_entry_and_card_in_step(tmp_path) -> None:
    """오버레이를 얹으면 **항목값과 카드 원문이 함께** 바뀌어야 한다.
    한쪽만 바뀌면 한 항목이 같은 값을 두 번 다르게 들고 있게 된다."""
    import yaml

    from build_material_db import apply_overrides
    materials = {"130501": {"name": "X", "mat_type": "MAT_PLASTIC_KINEMATIC",
                            "mechanical": {"RHO": 7.8e-9, "E": 200000.0},
                            "cards_structural": {"MAT_PLASTIC_KINEMATIC": CARD}}}
    (tmp_path / "material_overrides.yaml").write_text(yaml.safe_dump(
        {"version": 1, "overrides": {"130501": {"mechanical": {"E": 199500.0}}}}),
        encoding="utf-8")
    st = apply_overrides(tmp_path, materials)
    assert st["fields"] == 1
    m = materials["130501"]
    assert m["mechanical"]["E"] == 199500.0
    assert m["mechanical"]["E_GPa"] == 199.5, "파생 SI 표기도 다시 계산해야 한다"
    card_val = float(m["cards_structural"]["MAT_PLASTIC_KINEMATIC"]
                     .splitlines()[3][20:30])
    assert card_val == 199500.0, "카드 원문이 항목값과 어긋난다"


def test_overlay_reports_what_it_could_not_apply(tmp_path) -> None:
    """못 얹은 것을 조용히 넘기지 않는다."""
    import yaml

    from build_material_db import apply_overrides
    (tmp_path / "material_overrides.yaml").write_text(yaml.safe_dump(
        {"version": 1, "overrides": {"999": {"mechanical": {"E": 1.0}}}}),
        encoding="utf-8")
    st = apply_overrides(tmp_path, {})
    assert st["fields"] == 0 and st["skipped"][0]["why"] == "MID 가 DB 에 없다"
