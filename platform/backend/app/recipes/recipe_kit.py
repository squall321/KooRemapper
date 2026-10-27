# 레시피가 리포트를 받는 키트 — 승격 칸·케이스는 바로, 큰 임베드 데이터는 필요할 때만 파서로.
"""The surface a recipe sees. A recipe defines ``run(reports, params)`` where
``reports`` is a list of :class:`Report`.

A Report exposes the cheap, already-normalized facts directly (``meta``,
``parts``, ``cases``, ``summary``, ``findings``) and the heavy embedded blocks
through the existing report parser (``hotspots``, ``contact_profile``,
``case_energy`` …). The parser functions are pure (they take a ``data`` dict),
so they run unchanged inside the sandbox.

At runtime the sandbox builds a Report from a bundle directory of JSON files;
in tests a recipe builds one with :func:`make_report` from in-memory dicts. Both
paths produce the same object, so a recipe's ``test_*`` exercises the real code.

★ This module imports only the stdlib + the pure report parser, so it is safe to
pre-import before the sandbox locks down. It must NOT import anything that opens
a socket, reads the DB, or touches settings.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any, Callable

from app.reports import parser


class RecipeError(Exception):
    """레시피가 '입력이 이래서 못 한다' 를 명시적으로 말할 때 쓴다(샌드박스가 error 로 적는다)."""


class Report:
    """One ingested drop/impact report, as a recipe sees it.

    Construct via :func:`make_report` (tests) or :meth:`from_bundle` (runtime).
    ``data`` (the full embedded dict) is loaded lazily — it is large (impact can
    be ~8 MB) and most recipes never need it.
    """

    def __init__(
        self,
        *,
        report_id: str,
        kind: str,
        meta: dict | None = None,
        cases: list[dict] | None = None,
        data: dict | None = None,
        data_path: str | None = None,
    ) -> None:
        self.id = report_id
        self.kind = kind
        self.meta: dict = meta or {}
        self.cases: list[dict] = list(cases or [])
        self._data = data
        self._data_path = data_path

    # ── 값으로 바로 쓰는 것(DB 승격 칸 — 재파싱 없음) ────────────────────
    @property
    def label(self) -> str | None:
        return self.meta.get("label")

    @property
    def project_name(self) -> str | None:
        return self.meta.get("project_name")

    @property
    def drop_height(self) -> float | None:
        return self.meta.get("drop_height")

    @property
    def parts(self) -> list[dict]:
        """[{part_id, name, group}] — 리포트가 선언한 파트."""
        return self.meta.get("parts") or []

    @property
    def summary(self) -> dict:
        """전역 최악 롤업(kind 마다 칸이 다르다)."""
        return self.meta.get("summary") or {}

    @property
    def findings(self) -> list[dict]:
        return self.meta.get("findings") or []

    def part_names(self) -> dict[int, str | None]:
        out: dict[int, str | None] = {}
        for p in self.parts:
            pid = _to_int(p.get("part_id"))
            if pid is not None:
                out[pid] = p.get("name")
        return out

    def part_worst(self) -> dict[int, dict]:
        """파트별 최악값과 그게 난 케이스 — ``part_risk`` 와 같은 계산을 케이스에서 한다.

        {pid: {part_id, part_name, worst_stress:{value,case_key}, worst_g, worst_disp,
        min_safety_factor}}. 승격 칸(parts_metrics)만 쓰므로 임베드 데이터가 없어도 된다.
        """
        names = self.part_names()
        acc: dict[int, dict] = {}
        for c in self.cases:
            ck = c.get("case_key")
            for pid_s, m in (c.get("parts_metrics") or {}).items():
                pid = _to_int(pid_s)
                if pid is None:
                    continue
                a = acc.setdefault(pid, {
                    "part_id": pid, "part_name": names.get(pid),
                    "worst_stress": {"value": None, "case_key": None},
                    "worst_g": {"value": None, "case_key": None},
                    "worst_disp": {"value": None, "case_key": None},
                    "min_safety_factor": None,
                })
                _bump(a["worst_stress"], m.get("peak_stress"), ck)
                _bump(a["worst_g"], m.get("peak_g"), ck)
                _bump(a["worst_disp"], m.get("peak_disp"), ck)
                sf = m.get("safety_factor")
                if sf is not None and (a["min_safety_factor"] is None or sf < a["min_safety_factor"]):
                    a["min_safety_factor"] = sf
        return acc

    def cases_sorted(self, metric: str = "max_stress", *, desc: bool = True) -> list[dict]:
        """케이스를 승격 칸 하나로 정렬(None 은 뒤로). metric ∈ max_stress·max_g·max_disp·min_safety_factor."""
        if metric not in _CASE_METRICS:
            raise RecipeError(f"알 수 없는 케이스 정렬 칸: {metric} (허용: {sorted(_CASE_METRICS)})")
        return sorted(
            self.cases,
            key=lambda c: (c.get(metric) is None, -(c.get(metric) or 0.0) if desc else (c.get(metric) or 0.0)),
        )

    # ── 큰 임베드 블록(필요할 때만 재파싱) ──────────────────────────────
    @property
    def data(self) -> dict:
        """임베드 데이터 전체. 번들에 없으면 RecipeError(메타에 needs:["data"] 를 선언해야 받는다)."""
        if self._data is None:
            if self._data_path is None:
                raise RecipeError(
                    "이 레시피는 임베드 데이터를 받지 못했다 — 메타 needs 에 \"data\" 를 넣어야 한다."
                )
            self._data = json.loads(Path(self._data_path).read_text(encoding="utf-8"))
        return self._data

    def hotspots(self, **kw) -> dict:
        """핫스팟 군집(deep · sphere). parser.hotspot_clusters 그대로."""
        return parser.hotspot_clusters(self.data, **kw)

    def contact_profile(self, **kw) -> dict:
        """파트쌍 × 각도(위치) 접촉 스칼라(sphere · impact)."""
        return parser.contact_profile(self.data, self.kind, **kw)

    def case_energy(self, case_key: str | None = None) -> dict:
        return parser.case_energy(self.data, self.kind, case_key)

    def part_series(self, case_key: str, part_id: int) -> dict:
        return parser.part_series(self.data, self.kind, case_key, part_id)

    def part_energy_series(self, part_id: int | None = None) -> dict:
        return parser.part_energy_series(self.data, self.kind, part_id)

    def analytics(self, block: str | None = None) -> dict:
        return parser.analytics_summary(self.data, block)

    def blocks(self) -> dict:
        return parser.list_blocks(self.data)

    def block(self, name: str, path: str | None = None, limit: int | None = None) -> dict:
        return parser.get_block(self.data, name, path, 200_000, limit)

    def geometry(self) -> dict:
        return parser.extract_geometry(self.data, self.kind)

    @classmethod
    def from_bundle(cls, d: str | Path) -> "Report":
        """샌드박스 런타임 — 번들 디렉터리의 JSON 에서 만든다. data.json 은 있으면 지연 로드."""
        d = Path(d)
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        cases_path = d / "cases.json"
        cases = json.loads(cases_path.read_text(encoding="utf-8")) if cases_path.exists() else []
        data_path = d / "data.json"
        return cls(
            report_id=meta.get("id", d.name), kind=meta.get("kind", ""),
            meta=meta, cases=cases,
            data_path=str(data_path) if data_path.exists() else None,
        )

    def __repr__(self) -> str:
        return f"Report(id={self.id!r}, kind={self.kind!r}, n_cases={len(self.cases)})"


def make_report(
    *,
    report_id: str = "R",
    kind: str,
    meta: dict | None = None,
    parts: list[dict] | None = None,
    cases: list[dict] | None = None,
    summary: dict | None = None,
    findings: list[dict] | None = None,
    data: dict | None = None,
) -> Report:
    """시험용 — 작은 리포트를 메모리 dict 로 만든다(파일 없이).

    ``parts``/``summary``/``findings`` 는 meta 안으로 합쳐 넣는다 — 런타임 번들의 meta.json 과 같은 꼴이다.
    """
    m = dict(meta or {})
    m.setdefault("id", report_id)
    m.setdefault("kind", kind)
    if parts is not None:
        m["parts"] = parts
    if summary is not None:
        m["summary"] = summary
    if findings is not None:
        m["findings"] = findings
    return Report(report_id=report_id, kind=kind, meta=m, cases=cases, data=data)


# 레시피 결과를 담는 표준 봉투 — recipe 가 돌려준 값을 이 꼴로 감싸 샌드박스가 직렬화한다.
def as_result(value: Any) -> dict:
    """recipe.run 이 돌려준 것이 dict 면 그대로, 아니면 {"value": …} 로 감싼다(NaN 은 바깥에서 null 로)."""
    return value if isinstance(value, dict) else {"value": value}


_CASE_METRICS = {"max_stress", "max_g", "max_disp", "min_safety_factor"}


def _to_int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _bump(slot: dict, value, case_key) -> None:
    v = _num(value)
    if v is None:
        return
    if slot["value"] is None or v > slot["value"]:
        slot["value"] = v
        slot["case_key"] = case_key


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if (isinstance(v, float) and math.isnan(v)) else float(v)
    return None


# recipe 가 통계를 쓸 때 편하라고 몇 가지를 다시 노출(stdlib 를 직접 import 해도 된다).
mean = statistics.mean
median = statistics.median
pstdev = statistics.pstdev
