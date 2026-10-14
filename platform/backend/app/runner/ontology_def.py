# 온톨로지 정의 파일(SP import 꼴)을 읽고 **검사**한다 — 허브의 것과 우리 것을 같은 눈으로
"""왜 검증기를 직접 짓나. SP 의 엔진은 안 가져온다(계획서 §2 — 부서·계정·감사에 묶여 있다).
그러나 **정의의 꼴은 맞춘다** — 허브의 `pipeline/core/plm-core.json` 을 **그대로** 읽을 수
있어야 하고, 우리 정의가 허브가 읽을 수 있는 꼴이어야 한다. 그 둘이 되면 나중에 정의를
주고받을 때 변환기가 필요 없다.

꼴(실측 — `plm-core.json`·`work-core.json`@f7485c0) —

    {"groups":[{slug,label,sort_order}],
     "types":[{slug,label,nav_group_slug,icon,key_policy,description,
               "properties":[{key,label,data_type,ref_type_slug?,required?,multi?,
                              enum_options?,unit?,help?,inverse_label?,pattern?}]}],
     "relation_types":[{slug,label,inverse_label,description,cardinality,
                        transitive?,acyclic?,src_type_slugs?,dst_type_slugs?}]}

⚠ **`cardinality` 는 정의 파일에만 있다** — 코어 API 의 `CoreRelationKindOut` 에는 없다.
그래서 받은 관계 종류는 그 칸이 비고, 자체 정의에서만 채워진다.

**모르는 칸은 흠이 아니다**(수신 규칙 5 와 같은 자세) — 허브가 칸을 늘려도 우리가 안 깨진다.
그래서 「모르는 키」 는 오류가 아니라 **알림**으로만 센다.

실패를 예외로 올리지 않는다 — 흠 목록을 돌려준다. 한 흠에서 멈추면 나머지를 못 보고,
못 본 것은 다음 판에서 또 걸린다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# SP §4.2 의 속성 종류. 여기 없는 것은 **거절한다** — 모르는 종류를 통과시키면 폼이 그것을
# 그릴 방법이 없는데 정의는 통과한 상태가 된다.
DATA_TYPES = frozenset({
    "text", "text_long", "number", "date", "datetime", "bool", "enum", "url",
    "object_ref", "file",
})
KEY_POLICIES = frozenset({"none", "optional", "required"})
CARDINALITIES = frozenset({"one_to_one", "one_to_many", "many_to_one", "many_to_many"})

# 정의 파일이 가리킬 수 있는 **바깥 타입** — 허브 거울과 우리 1급 표.
# 거울은 받아서 채우므로 우리 정의 파일에 없고, 1급 표는 `onto_objects` 에 행을 만들지 않는다
# (SP 의 `kind_class=system` · `object_links` 와 같은 자리).
EXTERNAL_TYPES = frozenset({
    "plm_project", "plm_task", "plm_model", "plm_test_site",   # 허브 거울
    "impact_report", "session", "workspace", "user",           # 우리 1급 표 · 포탈 정본
})

_PROP_KNOWN = frozenset({
    "key", "label", "data_type", "ref_type_slug", "required", "multi", "enum_options",
    "unit", "help", "inverse_label", "pattern", "default_value", "min_value", "max_value",
    "decimals", "unique", "sort_order", "accept", "section",
})
_TYPE_KNOWN = frozenset({
    "slug", "label", "nav_group_slug", "icon", "key_policy", "key_scope", "description",
    "properties", "temporal_kind", "entry_policy", "kind_class", "list_view", "managed_by",
    "system_source", "interfaces",
})
_REL_KNOWN = frozenset({
    "slug", "label", "inverse_label", "description", "cardinality", "directed",
    "transitive", "acyclic", "src_type_slugs", "dst_type_slugs", "managed_by", "properties",
})


class Report:
    """흠과 알림. **빈 흠 목록이 곧 통과**다 — 알림은 통과를 막지 않는다."""

    def __init__(self) -> None:
        self.faults: list[str] = []
        self.notes: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.faults

    def fault(self, where: str, said: str) -> None:
        self.faults.append(f"{where}: {said}")

    def note(self, where: str, said: str) -> None:
        self.notes.append(f"{where}: {said}")

    def __repr__(self) -> str:       # 시험 실패 메시지에 그대로 뜨게
        return f"Report(faults={self.faults}, notes={self.notes})"


def _dupes(names: list[str]) -> list[str]:
    seen, out = set(), []
    for n in names:
        if n in seen and n not in out:
            out.append(n)
        seen.add(n)
    return sorted(out)


def validate(doc: Any, *, known_types: set[str] | None = None) -> Report:
    """정의 문서 하나를 검사한다.

    `known_types` — 이 문서 밖에서 이미 아는 타입(기본은 `EXTERNAL_TYPES`). 허브의
    `plm-core.json` 처럼 자기 안에서 다 푸는 문서도, 우리처럼 거울을 가리키는 문서도
    **같은 검증기로** 봐야 한다.
    """
    rep = Report()
    if not isinstance(doc, dict):
        rep.fault("(문서)", "최상위가 객체가 아니다")
        return rep

    groups = doc.get("groups") or []
    types = doc.get("types") or []
    rels = doc.get("relation_types") or []
    group_slugs = {str(g.get("slug")) for g in groups if isinstance(g, dict)}
    own = [str(t.get("slug")) for t in types if isinstance(t, dict)]
    pool = set(own) | set(known_types if known_types is not None else EXTERNAL_TYPES)

    for dup in _dupes(own):
        rep.fault(f"types/{dup}", "slug 이 두 번 나온다 — 나중 것이 앞 것을 조용히 덮는다")
    for dup in _dupes([str(r.get("slug")) for r in rels if isinstance(r, dict)]):
        rep.fault(f"relation_types/{dup}", "slug 이 두 번 나온다")
    for dup in _dupes([str(g.get("slug")) for g in groups if isinstance(g, dict)]):
        rep.fault(f"groups/{dup}", "slug 이 두 번 나온다")

    for t in types:
        slug = str(t.get("slug") or "")
        where = f"types/{slug or '(이름 없음)'}"
        if not slug:
            rep.fault(where, "slug 이 없다")
        if not t.get("label"):
            rep.fault(where, "label 이 없다 — 화면에 뭐라고 쓸지 알 수 없다")
        kp = t.get("key_policy")
        if kp is not None and str(kp) not in KEY_POLICIES:
            rep.fault(where, f"key_policy 가 {kp!r} — {sorted(KEY_POLICIES)} 중 하나여야 한다")
        ng = t.get("nav_group_slug")
        if ng and str(ng) not in group_slugs:
            rep.fault(where, f"nav_group_slug {ng!r} 이 groups 에 없다 — 사이드바에 안 선다")
        for unknown in sorted(set(t) - _TYPE_KNOWN):
            if not unknown.startswith("_"):
                rep.note(where, f"모르는 키 {unknown!r}(무시한다 — 흠이 아니다)")

        prop_keys = [str(p.get("key")) for p in (t.get("properties") or [])
                     if isinstance(p, dict)]
        for dup in _dupes(prop_keys):
            rep.fault(f"{where}.{dup}", "속성 key 가 두 번 나온다")

        for p in t.get("properties") or []:
            key = str(p.get("key") or "")
            pw = f"{where}.{key or '(이름 없음)'}"
            if not key:
                rep.fault(pw, "key 가 없다")
            if not p.get("label"):
                rep.fault(pw, "label 이 없다")
            dt = str(p.get("data_type") or "")
            if dt not in DATA_TYPES:
                rep.fault(pw, f"data_type 이 {dt!r} — 폼이 그릴 방법이 없다")
            if dt == "object_ref":
                ref = str(p.get("ref_type_slug") or "")
                if not ref:
                    rep.fault(pw, "object_ref 인데 ref_type_slug 가 없다 — 무엇을 고를지 모른다")
                elif ref not in pool:
                    rep.fault(pw, f"ref_type_slug {ref!r} 가 아는 타입이 아니다")
            if dt == "enum" and "enum_options" not in p:
                # SP 는 빈 목록을 두고 "허브의 사내 확장이 채운다" 고 적는다 — 빈 것은 허용,
                # **칸이 아예 없는 것**은 흠이다(폼이 고를 것이 없는 선택 상자를 그린다).
                rep.fault(pw, "enum 인데 enum_options 칸이 없다")
            for unknown in sorted(set(p) - _PROP_KNOWN):
                rep.note(pw, f"모르는 키 {unknown!r}(무시한다)")

    for r in rels:
        slug = str(r.get("slug") or "")
        where = f"relation_types/{slug or '(이름 없음)'}"
        if not slug:
            rep.fault(where, "slug 이 없다")
        if not r.get("label"):
            rep.fault(where, "label 이 없다")
        if not r.get("inverse_label"):
            # 양방향 이름이 없으면 화면이 반대쪽에서 뭐라고 부를지 모른다(SP §3.4).
            rep.fault(where, "inverse_label 이 없다 — 화면이 양방향을 말할 수 없다")
        card = r.get("cardinality")
        if card is not None and str(card) not in CARDINALITIES:
            rep.fault(where, f"cardinality 가 {card!r} — {sorted(CARDINALITIES)} 중 하나여야 한다")
        src = [str(x) for x in (r.get("src_type_slugs") or [])]
        dst = [str(x) for x in (r.get("dst_type_slugs") or [])]
        for name, ends in (("src_type_slugs", src), ("dst_type_slugs", dst)):
            for end in ends:
                if end not in pool:
                    rep.fault(where, f"{name} 의 {end!r} 가 아는 타입이 아니다")
        # ★순환 금지의 뜻 — `acyclic` 은 **같은 타입을 가리킬 때만** 뜻이 있다. 끝 타입이
        #   겹치지 않으면 순환이 애초에 불가능하므로, 켜 둔 것은 베껴 쓴 흔적이다. 조용히
        #   두면 "순환을 막고 있다" 고 읽히는데 아무것도 안 막는다.
        if r.get("acyclic") and src and dst and not (set(src) & set(dst)):
            rep.fault(where, "acyclic 인데 출발·도착 타입이 겹치지 않는다 — 막는 것이 없다")
        # 자기를 가리키는 관계는 **반드시** acyclic 이어야 한다 — 아니면 줄을 따라가는
        # 질의가 영원히 돈다.
        if set(src) & set(dst) and not r.get("acyclic"):
            rep.fault(where, "자기 타입을 가리키는데 acyclic 이 아니다 — 줄을 따라가면 영원히 돈다")
        for unknown in sorted(set(r) - _REL_KNOWN):
            if not unknown.startswith("_"):
                rep.note(where, f"모르는 키 {unknown!r}(무시한다)")

    return rep


def load(path: str | Path, *, known_types: set[str] | None = None) -> tuple[dict, Report]:
    """파일을 읽고 검사한다. 읽기 실패도 **흠**이다(예외로 올리지 않는다)."""
    p = Path(path)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        rep = Report()
        rep.fault(str(p), f"{type(exc).__name__}: {exc}")
        return {}, rep
    return doc, validate(doc, known_types=known_types)
