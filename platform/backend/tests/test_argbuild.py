"""argbuild tests — positional/flag ordering + YAML serialization style."""
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
import yaml  # noqa: E402

from app.runner.argbuild import _dump_yaml, build_command  # noqa: E402
from kooremapper_core.argbuild import CardSerializationError  # noqa: E402


def _wd():
    return Path(tempfile.mkdtemp())


def test_positional_flags_after():
    b = build_command("map", {"single": True, "bent_mesh": "b.k", "flat_mesh": "f.k", "output": "o.k"}, _wd())
    assert b.error is None
    # positionals first, then flags (extract-surface requires this)
    assert b.argv == ["map", "b.k", "f.k", "o.k", "--single"], b.argv


def test_positional_valued_flag():
    b = build_command("prestress", {"ref_mesh": "r.k", "def_mesh": "d.k", "output": "o.dynain", "E": 210000, "strain": "green"}, _wd())
    assert b.error is None
    assert b.argv[:4] == ["prestress", "r.k", "d.k", "o.dynain"]
    assert "--E" in b.argv and "210000" in b.argv
    assert "--strain" in b.argv and "green" in b.argv


def test_yaml_structured_written():
    wd = _wd()
    b = build_command("relax", {"model": "m.k", "output": "r.k", "level": 3, "mode": "explicit"}, wd)
    assert b.argv[0]=="relax" and b.argv[1].endswith("config.yaml")
    cfg = yaml.safe_load((wd / "config.yaml").read_text())
    assert cfg == {"model": "m.k", "output": "r.k", "level": 3, "mode": "explicit"}


def test_yaml_freeform_verbatim():
    wd = _wd()
    config = {"base_model": "x.k", "output": "r", "operations": [{"type": "bend", "target_pid": 1}]}
    b = build_command("assemble", {"config": config}, wd)
    assert b.argv[0]=="assemble" and b.argv[1].endswith("config.yaml")
    cfg = yaml.safe_load((wd / "config.yaml").read_text())
    assert cfg == config


def test_dump_yaml_scalar_arrays_flow_mappings_block():
    text = _dump_yaml({"loads": [{"part": 1, "direction": [0, 0, 1]}], "material": {"E": 1.0, "nu": 0.3}})
    # scalar array inline (flow)
    assert "direction: [0, 0, 1]" in text
    # block sequence indented
    assert "loads:\n  - part: 1" in text
    # mapping stays block (not flow), so no inline brace for material
    assert "material:\n  E: 1.0" in text
    assert "{E:" not in text


def test_dump_yaml_nested_array_flow_inner():
    text = _dump_yaml({"operations": [{"shape": {"points": [[3, 3], [7, 3]]}}]})
    # inner coordinate arrays flow, outer block + indented
    assert "- [3, 3]" in text
    assert "points:\n" in text


def test_dump_yaml_multiline_card_literal_block():
    # 여러 줄 재질 카드는 `key: |` 리터럴 블록이어야 C++ 파서가 읽는다(따옴표 문자열이면 restack 층 mid=0).
    card = "*MAT_ELASTIC   \n$#     mid        ro         e        pr\n    MID001  7.85E-09    210000       0.3"
    cfg = {"layers": [{"thickness": 0.3, "material_card": card}]}
    text = _dump_yaml(cfg)
    assert "    material_card: |\n      *MAT_ELASTIC\n" in text, text
    assert "\"*MAT_ELASTIC" not in text
    back = yaml.safe_load(text)["layers"][0]["material_card"]
    assert back.splitlines() == [ln.rstrip() for ln in card.splitlines()]
    # 한 줄 문자열은 그대로(블록 아님)
    assert "note: plain" in _dump_yaml({"note": "plain"})


def test_dump_yaml_card_with_tab_is_rejected():
    # 탭을 펴면 탭 폭 가정(8/4)에 따라 뒤 칸이 밀린다 — 줄 중간 탭이면 RO 가 사라지고 E 가 'E-09' 가
    # 되는데 덱은 정상으로 보인다. 조용히 틀린 덱 대신 여기서 멈춘다.
    tabbed = "*MAT_ELASTIC_TITLE\nSubstrate\n        90\t7.85E-09\t2.10E+05\t0.3"
    with pytest.raises(CardSerializationError) as exc:
        _dump_yaml({"layers": [{"thickness": 0.3, "material_card": tabbed}]})
    assert "TAB" in str(exc.value) and "line 3" in str(exc.value)
    b = build_command("restack", {"config": {"base_model": "m.k", "output": "o",
        "operations": [{"type": "restack", "target_pid": 1,
                        "layers": [{"thickness": 0.3, "material_card": tabbed}]}]}}, _wd())
    assert b.error and "TAB" in b.error, b.error


def test_dump_yaml_card_with_cr_line_breaks_becomes_block():
    # \r\n 과 단독 \r 은 줄 구분자다. 단독 \r 은 그대로 내보내면 따옴표 한 줄이 되어 덱에 쓰레기가
    # 써지고 층 mid=0 이 됐다(수정 전 실측). 공백으로 쓴 같은 카드와 한 글자도 다르지 않아야 한다.
    lf = "*MAT_ELASTIC_TITLE\nSubstrate\n        90  7.85E-09  2.10E+05       0.3\n"
    for card in (lf.replace("\n", "\r\n"), lf.replace("\n", "\r")):
        text = _dump_yaml({"layers": [{"material_card": card}]})
        assert "  - material_card: |\n      *MAT_ELASTIC_TITLE\n" in text, text
        assert text == _dump_yaml({"layers": [{"material_card": lf}]})
        assert yaml.safe_load(text)["layers"][0]["material_card"] == lf


def test_dump_yaml_blank_card_is_rejected():
    # 공백·탭뿐인 카드는 정규화하면 내용 줄이 0 이다. 수정 전에는 따옴표 스칼라로 조용히 나가
    # rc=0 인 채 층 mid=0 짜리 덱이 됐다.
    with pytest.raises(CardSerializationError) as exc:
        _dump_yaml({"layers": [{"material_card": "\n   \n\t\n"}]})
    assert "blank" in str(exc.value)


def test_dump_yaml_card_with_leading_space_is_rejected():
    # 첫 줄이 공백으로 시작하면 YAML 이 `|2` 헤더를 붙이는데, 받는 쪽은 블록 들여쓰기를 '첫 내용
    # 줄' 기준으로 잡아 그 선행 공백을 먹는다(MID 칸이 밀린다). 애매하므로 거절한다.
    card = "  *MAT_ELASTIC_TITLE\nSubstrate\n        90  7.85E-09  2.10E+05       0.3\n"
    with pytest.raises(CardSerializationError):
        _dump_yaml({"layers": [{"material_card": card}]})


def test_dump_yaml_card_with_yaml_line_break_char_is_rejected():
    # 0x85/U+2028 은 블록으로는 나가지만 읽을 때 한 줄이 두 줄로 쪼개진다(카드 줄 수가 달라진다).
    for ch in ("\x85", "\u2028"):
        with pytest.raises(CardSerializationError):
            _dump_yaml({"layers": [{"material_card": f"*MAT_ELASTIC_TITLE\nSub{ch}strate\n        90  1.0\n"}]})


def test_dump_yaml_single_line_value_is_normalized():
    # 한 줄로 접히는 값도 정규화한 쪽이 나가야 한다(예전에는 원본이 나가 앞뒤 빈 줄이 되살아났다).
    text = _dump_yaml({"layers": [{"material_card": "\n\n*MAT_ELASTIC   \n\n"}]})
    assert text == "layers:\n  - material_card: '*MAT_ELASTIC'\n", text


def test_dump_yaml_card_with_leading_blank_line_stays_plain_block():
    # 카드 앞 빈 줄이 있으면 PyYAML 이 `|2` 명시 들여쓰기 헤더를 붙였고, C++ 파서는 그 '|2' 를
    # 카드 본문으로 읽어 덱에 그대로 썼다(mid=0). 카드 앞뒤 빈 줄은 의미가 없으므로 떼고 낸다.
    card = "\n\n*MAT_ELASTIC_TITLE\nSubstrate\n        90  7.85E-09  2.10E+05       0.3\n\n"
    text = _dump_yaml({"layers": [{"thickness": 0.3, "material_card": card}]})
    assert "    material_card: |\n      *MAT_ELASTIC_TITLE\n" in text, text
    assert "|2" not in text
    assert yaml.safe_load(text)["layers"][0]["material_card"] == card.strip("\n") + "\n"


def test_dump_yaml_card_round_trip_preserves_columns():
    # 왕복(dump → safe_load)이 원본 카드의 칸 위치를 그대로 돌려줘야 한다 —
    # 정규화는 줄 끝 공백·탭·앞뒤 빈 줄만 건드리고 칸을 옮기지 않는다.
    card = ("*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE\n"
            "7075-T6 aluminum\n"
            "$#     mid        ro         e        pr      sigy\n"
            "        90  2.70E-09  7.10E+04      0.33  4.50E+02\n")
    back = yaml.safe_load(_dump_yaml({"layers": [{"material_card": card}]}))
    assert back["layers"][0]["material_card"] == card


def test_validation_error_propagates():
    b = build_command("map", {"bent_mesh": "b.k"}, _wd())
    assert b.error and "flat_mesh" in b.error


def test_unknown_op_error():
    b = build_command("nope", {}, _wd())
    assert b.error and "unknown" in b.error


def test_all_catalog_examples_build():
    """Every op's catalog example must build a command without error — guards
    against an argbuild/catalog change breaking any op (M14)."""
    from app.runner import catalog

    failures = []
    for name in catalog.operation_names():
        op = catalog.get_operation(name)
        args = (op.get("example") or {}).get("args") or {}
        b = build_command(name, args, _wd())
        if b.error:
            failures.append(f"{name}: {b.error}")
    assert not failures, "catalog examples that fail to build:\n" + "\n".join(failures)


def test_matdb_defaults_to_bundled_db():
    """Omitting `database` for matdb injects the bundled library path (L8)."""
    from app.runner.argbuild import _BUNDLED_MATERIAL_DB

    b = build_command("matdb", {"model": "m.k", "output": "o.k", "mat_type": "MAT_ELASTIC"}, _wd())
    assert b.error is None
    cfg = b.written_files.get("config.yaml", "")
    assert str(_BUNDLED_MATERIAL_DB) in cfg, "bundled DB path not injected"
    # an explicit database is respected (not overridden)
    b2 = build_command("matdb", {"model": "m.k", "output": "o.k", "database": "custom.json"}, _wd())
    assert "custom.json" in b2.written_files.get("config.yaml", "")
