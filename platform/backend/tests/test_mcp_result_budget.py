# MCP 응답이 예산을 넘지 않게 **재서** 자르는지 — 넘으면 URL 이 잘려 그림이 사라진다
"""`fit_to_budget` 의 계약 (2026-10-06).

왜 이 시험이 있나.

  챗은 도구 응답의 텍스트를 이어 붙인 **뒤** 통째로 자른다. 그래서 응답이 길면 뒤에 붙는
  **URL 줄이 잘려 그림이 사라진다**(`TOOL_RESULT_MAX`, URL 줄 81자). 처음 구현은 파트 표를
  **고정 캡**(20, compare 면 10)으로만 잘랐는데 그것은 길이를 **재지 않는다** —
  제목이 긴 덱은 행이 적어도 넘고, 짧은 덱은 더 실을 수 있는데 못 싣는다.

  실측(61파트 배터리 덱) — 고정 캡 20 은 3,702바이트에 20행, **재서 빼면 같은 예산에 25행**
  (4,413바이트)이 들어간다. 즉 재는 쪽이 안전하면서 **더 많이** 싣는다.
"""
import json
from pathlib import Path


def _load_fit():
    """server.py 는 fastmcp 의존이라 통째로 import 하지 않고 함수만 끌어온다."""
    import ast
    import textwrap
    src = (Path(__file__).resolve().parents[2] / "mcp_server" / "server.py").read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "fit_to_budget":
            ns: dict = {}
            exec(compile(ast.Module(body=[node], type_ignores=[]), "<fit>", "exec"), ns)
            return ns["fit_to_budget"]
    raise AssertionError("fit_to_budget 를 server.py 에서 찾지 못했다")


fit_to_budget = _load_fit()


def _build(rows, title_len=12):
    """cap 행만 담는 응답을 만든다 — 행마다 제목 길이를 조절해 '긴 제목' 을 흉내 낸다."""
    def build(cap):
        out = {
            "job_id": "01ABCDEFGHIJKLMNOPQRSTUVWX",
            "svg_file_id": 1234,
            "manifest_file_id": 1235,
            "section": {
                "axis": "y",
                "parts": [{"pid": i, "title": "P" * title_len, "polys": 10,
                           "thickness": 0.0123456789, "E": 70000.0}
                          for i in range(min(cap, rows))],
            },
        }
        if cap < rows:
            out["section"]["parts_omitted"] = rows - cap
        return out
    return build


def _size(d):
    return len(json.dumps(d, ensure_ascii=False))


def test_fits_within_budget():
    """행이 아무리 많아도 **예산 안에** 들어온다."""
    res, cap = fit_to_budget(_build(500), 500, budget=6000, reserve=1200)
    assert _size(res) <= 6000 - 1200
    assert cap < 500 and res["section"]["parts_omitted"] == 500 - cap


def test_keeps_everything_when_it_fits():
    """작으면 **자르지 않는다** — 고정 캡은 여기서 멀쩡한 행을 버렸다."""
    res, cap = fit_to_budget(_build(5), 5, budget=6000, reserve=1200)
    assert cap == 5
    assert "parts_omitted" not in res["section"]
    assert len(res["section"]["parts"]) == 5


def test_long_titles_keep_fewer_rows():
    """★**길이를 잰다**는 증거 — 같은 행 수라도 제목이 길면 더 적게 싣는다.

    고정 캡은 이 차이를 만들 수 없다(행 수만 보므로)."""
    _, cap_short = fit_to_budget(_build(200, title_len=4), 200, budget=6000, reserve=1200)
    _, cap_long = fit_to_budget(_build(200, title_len=120), 200, budget=6000, reserve=1200)
    assert cap_long < cap_short


def test_reserve_is_respected():
    """URL·안내가 붙을 자리를 남긴다 — 그 줄이 잘리면 그림이 사라진다."""
    for reserve in (0, 1200, 3000):
        res, _ = fit_to_budget(_build(500), 500, budget=6000, reserve=reserve)
        assert _size(res) <= max(6000 - reserve, 256)


def test_never_empties_the_table():
    """예산이 아무리 작아도 **행을 0 으로 만들지 않는다** — 빈 표는 아무 말도 하지 않는다."""
    res, cap = fit_to_budget(_build(500), 500, budget=300, reserve=1200)
    assert cap == 1 and len(res["section"]["parts"]) == 1
    assert res["section"]["parts_omitted"] == 499
