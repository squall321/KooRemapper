# 해석 객체(cae_*) → 코어 온톨로지 다리(core-link SRC-08) — 정확 일치만 규칙 선, 나머지는 후보, 사람 선은 다시 붙여도 남는다
"""사용자 결정 — 포털 결정 기록 CK-2 · Q-5(11-09, 다리 셋 다 · 정확 일치만) · 이름 · 권한(11-10). 계획
`docs/01-plan/features/corelink-src08-11.plan.md`, 계약 HWAXPortal `docs/core-link/design.md` §8.

다리 셋은 자체 정의(`platform/core/ontology/dynaforge-core.json`)의 관계다 — 끝 타입 · 카디널리티는 그 파일에서 읽는다(코드에
두 벌을 두지 않는다). 코드가 정하는 것은 **해석 객체를 부르는 칸**(`NAME_PROP`) 하나다.
  ★`maps_to` 는 StepForge 와 **같은 정의**다(사용자 결정 11-11) — 두 앱이 같은 블록을 바이트 그대로 싣는다(출발 `part_role` · `cae_part`,
  근거 층 human · other · rule — other 는 StepForge 의 값이라 우리는 쓰지 않는다). 그 설명은 앱 중립이라 **우리 쪽 규칙은 여기(아래)와
  MCP `report_cae` 설명에 둔다** — 정확 일치만 규칙 선 · 후보 · 사람 선은 다시 붙여도 남는다 · 끊긴 사람 선 · 이름 바뀐 사람 선.
  - 파트(cae_part)는 이름(`name` — 덱 *PART 제목).
  - 소견(cae_finding)은 제목(`title`) — 해석 어휘에 고장 종류를 따로 적는 칸이 없고 제목이 판정 문장이다.
  - 캠페인(cae_campaign)은 해석 종류(`scenario_kind` — drop_all_angle · impact_all_position · single_run).

**정확**은 과제 잇기(`ontology.services.resolve_task`)와 같은 규칙이다 — 앞뒤 공백만 걷고 글자 그대로 견준다(대소문자 · 구분기호
그대로). 앱 안에 「정확」 이 하나다. 견주는 코어 쪽 글은 거울 행(허브가 준 것 · 사라지지 않은 것)의 key · 이름(label) · 허브 별칭
(`properties.aliases`) · 허브가 바꾼 옛 key(`onto_previous_keys`)와 우리 별칭 표(`onto_aliases`, 그 코어 타입)다.
  ★이 칸들이 모두 **코어 객체 하나**로 모일 때만 규칙 선이다. 칸끼리 엇갈리면(우리 별칭은 X 인데 다른 객체 Y 의 key · 이름 ·
  허브 별칭이 같은 글) 어느 쪽도 정하지 않고 둘 다 후보로 낸다 — 예전에는 우리 별칭이 먼저라 X 로 그었다(검토 11-11 — 과제 잇기도
  같은 규칙으로 바뀐다). 여러 칸이 같은 객체를 가리키면 맞은 칸(`matched_by`)은 우리 별칭 > key > 이름 > 허브 별칭 > 옛 key 차례로
  하나를 적는다.

**후보**(짐작 — 선이 아니다)는 과제 후보(`task_candidates`)와 같은 정규화(`normalize` — 대소문자 · 공백 · 구분기호를 지운다)로 본다.
  ① 글자 그대로 맞는 코어 객체가 여럿 ② 정규화하면 같다 ③ 정규화한 한쪽이 다른 쪽을 품는다(짧은 쪽이 두 글자 이상).
  객체마다 가까운 것부터 다섯까지 낸다. 그만 씀(deprecated)인 코어 객체는 후보에 넣지 않는다(새로 고르는 목록 — 10-30 결정).

**선은 리포트에 묶인다**(`report_id`) — 리포트를 지우면 함께 사라지고 읽기는 리포트 가시성을 따른다(10-31 결정 — 리포트 행은
전사 보기에 내지 않는다). 규칙 선(`basis: rule`)은 다시 지을 때마다 걷고 다시 긋는다. 사람 선(`basis: human`)은 다시 붙여도
지우지 않는다(`attach_ontology` 가 사람 선만 남기고 리포트의 선을 걷는다). 가리키던 해석 객체가 다시 반입에서 사라지면 지우지 않고
「끊긴 사람 선」(stale)으로 보인다. 같은 key 인데 이름이 바뀌어 다시 반입되면(확정 때 남긴 `src_label` 과 다르면) 사람 선은 그대로 남고
이기지만 조용히 따라가지 않는다 — 셈 `renamed` · 보기 `drift.renamed` 로 보인다(검토 11-11 P7). 다대일 다리(파트 · 캠페인)는 사람 선이
있으면 규칙이 그 객체를 건너뛴다(사람이 이긴다).
다대다 다리(소견)는 사람 선과 규칙 선이 함께 선다 — 다만 여럿이 맞아 갈리지 않은 것은 사람이 하나를 골랐어도 규칙이 나머지를 긋지 않는다.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.orm.attributes import set_committed_value

from app.models import SOURCE_HUB, SOURCE_SELF, ImpactReport, OntoAlias, OntoObject, OntoRelation
from app.modules.ontology.services import hub_aliases, normalize, renamed_keys
from app.reports.onto_package import VOCAB_DIR

logger = logging.getLogger("koorm.reports")

CORE_DEFS = "dynaforge-core.json"
# 해석 객체를 부르는 칸 — 정의 파일에는 없는, 코드가 정하는 단 하나(위 머리말).
NAME_PROP = {"cae_campaign": "scenario_kind", "cae_part": "name", "cae_finding": "title"}
RULE, HUMAN = "rule", "human"
CANDIDATES_PER_OBJECT = 5
MIN_CONTAINED = 2           # 품는 쪽 후보 — 짧은 쪽이 이보다 짧으면 아무 글에나 걸린다
RULE_TEXT = ("규칙 선 = 해석 쪽 이름(파트 name · 소견 title · 캠페인 scenario_kind)이 코어 객체의 key · 이름 · 허브 별칭 · 옛 key · "
             "우리 별칭과 글자 그대로(앞뒤 공백만 걷고) 같고 그 칸들이 모두 객체 하나를 가리킬 때. 후보 = 여럿이 맞음(칸끼리 엇갈림 포함) · "
             "구분기호와 대소문자만 다름 · 한쪽이 다른 쪽을 품음 — 선이 아니고 사람이 고른다(그만 쓴 객체는 안 낸다). 사람 선은 다시 붙여도 남고, 가리키던 해석 객체가 사라지면 stale, 이름이 바뀌면 drift.renamed 로 보인다. counts 는 지금 "
             "거울로 센 것이다 — 저장된 규칙 선과 다르면 drift 가 말한다(다시 붙이면 맞춰진다).")

_WHY_SAME = {"key": "key 가 구분기호 · 대소문자만 다르다", "label": "이름이 구분기호 · 대소문자만 다르다",
             "hub_alias": "허브 별칭이 구분기호 · 대소문자만 다르다", "alias": "우리 별칭이 구분기호 · 대소문자만 다르다"}
_WHY_HOLDS = {"key": "해석 쪽 글이 코어 key 를 품고 있다", "label": "해석 쪽 글이 코어 이름을 품고 있다",
              "hub_alias": "해석 쪽 글이 허브 별칭을 품고 있다", "alias": "해석 쪽 글이 우리 별칭을 품고 있다"}
_WHY_HELD = {"key": "코어 key 가 해석 쪽 글을 품고 있다", "label": "코어 이름이 해석 쪽 글을 품고 있다",
             "hub_alias": "허브 별칭이 해석 쪽 글을 품고 있다", "alias": "우리 별칭이 해석 쪽 글을 품고 있다"}
_WHY_MANY = "글자 그대로 맞는 코어 객체가 여럿이다"
# 정확 일치의 칸 — 같은 객체를 여러 칸이 가리키면 맞은 칸은 이 차례로 하나를 적고, 여럿이 맞으면 후보 까닭에 칸 이름을 단다
_EXACT_ORDER = ("alias", "key", "label", "hub_alias", "previous_key")
_FIELD = {"alias": "우리 별칭", "key": "key", "label": "이름", "hub_alias": "허브 별칭", "previous_key": "옛 key"}


@dataclass(frozen=True)
class Bridge:
    relation: str
    src_type: str
    dst_type: str
    cardinality: str
    name_prop: str

    @property
    def single(self) -> bool:
        """한 해석 객체에 선 하나 — 사람 선이 있으면 규칙은 그 객체를 건너뛴다."""
        return self.cardinality in ("many_to_one", "one_to_one")


@lru_cache(maxsize=1)
def bridges() -> dict[str, Bridge]:
    """해석 타입 → 다리. 정의 파일의 관계 가운데 출발에 `NAME_PROP` 의 타입이 든 것(어긋나면 시험이 잡는다).

    공유 정의(`maps_to` — StepForge 와 같은 블록, 11-11)는 출발이 여럿이다(StepForge `part_role` · 우리 `cae_part`) — 우리 타입만 다리다.
    """
    doc = json.loads((VOCAB_DIR / CORE_DEFS).read_text(encoding="utf-8"))
    out: dict[str, Bridge] = {}
    for r in doc.get("relation_types") or []:
        dst = r.get("dst_type_slugs") or []
        if len(dst) != 1:
            continue
        for src in r.get("src_type_slugs") or []:
            if src in NAME_PROP:
                out[src] = Bridge(r["slug"], src, dst[0], r.get("cardinality") or "many_to_many", NAME_PROP[src])
    return {t: out[t] for t in NAME_PROP if t in out}


def relations() -> list[str]:
    return [b.relation for b in bridges().values()]


def keep_on_reattach():
    """다시 붙일 때 남기는 선 — 다리의 사람 선. 리포트의 나머지 선(꾸러미 선 · 규칙 선)은 걷는다.

    ★붙이기의 본 트랜잭션 안에서 불린다 — 다리 정의 파일을 못 읽어도 붙이기를 깨지 않는다. 그때는 사람 표시(`basis: human`)만으로
    남기고(사람 선을 잃지 않는다), 다리는 다시 짓기에서 따로 깨져 `bridges.error` 로 말한다(검토 11-11).
    """
    human = func.coalesce(OntoRelation.properties["basis"].astext, "") == HUMAN
    try:
        rels = relations()
    except Exception:                       # noqa: BLE001 — 정의 파일 하나가 꾸러미 싣기를 막으면 안 된다
        logger.exception("다리 정의를 못 읽었다 — 다시 붙일 때 사람 표시만으로 사람 선을 남긴다")
        return human
    return and_(OntoRelation.relation.in_(rels), human)


def _basis(e: OntoRelation) -> str:
    return str((e.properties or {}).get("basis") or "")


def _rel(rid: str, key: str) -> str:
    """`<리포트 id>/part/3` → `part/3` — 리포트 보기의 다른 칸과 같은 상대 키."""
    pre = f"{rid}/"
    return key[len(pre):] if isinstance(key, str) and key.startswith(pre) else key


def _natural(key: str) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", key or "")]


def _order(o: OntoObject) -> tuple:
    return list(NAME_PROP).index(o.type_slug) if o.type_slug in NAME_PROP else 9, _natural(o.key)


# ── 거울 한 타입 — 정확 색인 · 후보용 정규화 이름 ─────────────────────────────────────────────

@dataclass
class _Pool:
    exact: dict[str, dict[str, set[str]]] = field(default_factory=dict)    # 글 → {코어 key: 맞은 칸들}
    ours: dict[str, str] = field(default_factory=dict)                 # 우리 별칭 → 코어 key(거울에 살아 있는 것만)
    names: list[tuple[str, str, str]] = field(default_factory=list)    # (코어 key, 정규화 글, 어디서) — 후보용
    labels: dict[str, str] = field(default_factory=dict)               # 살아 있는 코어 key → 이름
    quiet: set[str] = field(default_factory=set)                       # 그만 씀(deprecated) — 정확히 맞으면 잇지만 후보로는 안 낸다


async def _pool(db, dst_type: str) -> _Pool:
    pool = _Pool()
    quiet = pool.quiet
    rows = (await db.execute(select(OntoObject).where(
        OntoObject.type_slug == dst_type, OntoObject.report_id.is_(None), OntoObject.source == SOURCE_HUB,
        OntoObject.deleted.is_(False)))).scalars().all()
    for o in rows:
        pool.labels[o.key] = o.label or ""
        if o.status == "deprecated":
            quiet.add(o.key)        # 그만 씀 — 정확히 맞으면 잇지만(resolve_task 와 같다) 후보에는 안 낸다
        for how, text in (("key", o.key), ("label", o.label or ""), *(("hub_alias", a) for a in hub_aliases(o))):
            if not text:
                continue
            pool.exact.setdefault(text, {}).setdefault(o.key, set()).add(how)
            if o.key not in quiet and normalize(text):
                pool.names.append((o.key, normalize(text), how))
    for old, new in (await renamed_keys(db, dst_type)).items():
        if new in pool.labels:
            pool.exact.setdefault(old, {}).setdefault(new, set()).add("previous_key")
    for alias, key in (await db.execute(select(OntoAlias.alias, OntoAlias.key).where(
            OntoAlias.type_slug == dst_type))).all():
        if key in pool.labels:      # 거울에 없는 key 를 가리키는 별칭으로는 선을 긋지 않는다(끊긴 선이 된다)
            pool.ours[alias] = key
            if key not in quiet and normalize(alias):
                pool.names.append((key, normalize(alias), "alias"))
    return pool


def match(pool: _Pool, text: Any) -> dict:
    """해석 쪽 글 하나 → `verdict`(rule · candidates · unmatched · unnamed)와 그 근거. 쓰지 않는다."""
    t = text.strip() if isinstance(text, str) else ""     # resolve_task 와 같은 「정확」 — 앞뒤 공백만 걷는다
    if not t:
        return {"verdict": "unnamed", "text": "", "options": []}
    hits = {k: set(hows) for k, hows in pool.exact.get(t, {}).items()}
    if t in pool.ours:
        hits.setdefault(pool.ours[t], set()).add("alias")       # 우리 별칭도 칸 하나다 — 먼저가 아니다
    if len(hits) == 1:
        (key, hows), = hits.items()
        return {"verdict": "rule", "key": key, "matched_by": next(h for h in _EXACT_ORDER if h in hows), "text": t,
                "options": []}
    # 여럿 — 칸끼리 엇갈려도 여럿이다. 그만 씀은 여기서도 뺀다 — 후보는 새로 고르는 목록이다(10-30 결정 · 검토 11-11 P3).
    best: dict[str, tuple[int, int, str]] = {
        k: (0, 0, f"{_WHY_MANY}({' · '.join(_FIELD[h] for h in _EXACT_ORDER if h in hows)})")
        for k, hows in hits.items() if k not in pool.quiet}
    n = normalize(t)
    for key, name, how in pool.names:
        if name == n:
            got = (1, 0, _WHY_SAME[how])
        elif min(len(name), len(n)) >= MIN_CONTAINED and name in n:
            got = (2, -len(name), _WHY_HOLDS[how])             # 길게 품을수록 가깝다
        elif min(len(name), len(n)) >= MIN_CONTAINED and n in name:
            got = (2, -len(n), _WHY_HELD[how])
        else:
            continue
        if key not in best or got < best[key]:
            best[key] = got
    ranked = sorted(best.items(), key=lambda kv: (kv[1][0], kv[1][1], kv[0]))
    options = [{"key": k, "label": pool.labels.get(k, ""), "why": why} for k, (_, _, why) in ranked[:CANDIDATES_PER_OBJECT]]
    out = {"verdict": "candidates" if options else "unmatched", "text": t, "options": options}
    if len(ranked) > CANDIDATES_PER_OBJECT:
        out["more"] = len(ranked) - CANDIDATES_PER_OBJECT
    return out


# ── 계획(쓰지 않는다) · 다시 짓기 ─────────────────────────────────────────────────────────

_STATES = ("rule", "human", "stale", "renamed", "candidates", "unmatched", "unnamed")


async def plan(db, report: ImpactReport, *, rows: list | None = None, edges: list | None = None) -> dict:
    """그 리포트의 다리를 지금 거울로 셈한다 — **아무것도 쓰지 않는다.**

    셈(`counts`)의 단위 — rule · human · stale · renamed 는 **선** 수(human 은 가리키는 해석 객체가 있는 사람 선, stale 은 없는 것,
    renamed 는 human 가운데 그 객체 이름이 확정 때 남긴 `src_label` 과 달라진 것), candidates · unmatched · unnamed 는
    **선이 없는 해석 객체** 수(후보가 있다 · 없다 · 부르는 칸이 비었다).
    """
    rid, bmap = report.id, bridges()
    rels = {b.relation for b in bmap.values()}
    if rows is None:
        rows = (await db.execute(select(OntoObject).where(
            OntoObject.report_id == rid, OntoObject.type_slug.in_(list(bmap))))).scalars().all()
    if edges is None:
        edges = (await db.execute(select(OntoRelation).where(
            OntoRelation.report_id == rid, OntoRelation.relation.in_(list(rels))))).scalars().all()
    objs = sorted((o for o in rows if o.type_slug in bmap), key=_order)
    lines = [e for e in edges if e.relation in rels]
    present = {o.key for o in objs}
    human: dict[str, set[str]] = {}
    for e in lines:
        if _basis(e) == HUMAN and e.src_key in present:
            human.setdefault(e.src_key, set()).add(e.dst_key)
    pools = {b.dst_type: await _pool(db, b.dst_type) for b in bmap.values()}
    by_type = {t: {"objects": 0, **{s: 0 for s in _STATES}} for t in bmap}
    rules: list[dict] = []
    states: list[dict] = []
    for o in objs:
        b, c = bmap[o.type_slug], by_type[o.type_slug]
        c["objects"] += 1
        mine = human.get(o.key, set())
        c["human"] += len(mine)
        text = (o.properties or {}).get(b.name_prop)
        if mine and b.single:
            states.append({"obj": o, "bridge": b, "state": "human"})
            continue
        m = match(pools[b.dst_type], text)
        if m["verdict"] == "rule" and m["key"] not in mine:
            rules.append({"relation": b.relation, "src_type": o.type_slug, "src_key": o.key, "dst_type": b.dst_type,
                          "dst_key": m["key"], "matched_by": m["matched_by"], "matched_text": m["text"]})
            c["rule"] += 1
        state = "linked" if (mine or m["verdict"] == "rule") else m["verdict"]
        if state != "linked":
            c[state] += 1
        states.append({"obj": o, "bridge": b, "state": state, "match": m})
    stale = [e for e in lines if _basis(e) == HUMAN and e.src_key not in present]
    for e in stale:
        if e.src_type in by_type:
            by_type[e.src_type]["stale"] += 1
    # 같은 key 인데 이름이 바뀐 해석 객체의 사람 선 — 남기고 이기지만 조용히 따라가지 않는다(검토 11-11 P7). 새 칸을 두지 않고
    # 확정 때 남긴 이름(src_label)과 지금 이름을 견준다 — 남긴 이름이 없는 선은 견줄 수 없어 세지 않는다.
    label_of = {o.key: o.label for o in objs}
    renamed = [e for e in lines if _basis(e) == HUMAN and e.src_key in present
               and (e.properties or {}).get("src_label") and (e.properties or {})["src_label"] != label_of[e.src_key]]
    for e in renamed:
        by_type[e.src_type]["renamed"] += 1
    mirror = {b.dst_type: len(pools[b.dst_type].labels) for b in bmap.values()}
    notes = [f"코어 거울에 {b.dst_type} 가 없다 — 허브에서 그 타입을 받아야(받을 타입 KOORM_SP_CORE_TYPES) {b.src_type} → "
             f"{b.dst_type} 다리({b.relation})가 선다" for t, b in bmap.items() if by_type[t]["objects"] and not mirror[b.dst_type]]
    counts = {**{s: sum(c[s] for c in by_type.values()) for s in _STATES}, "by_type": by_type, "mirror": mirror,
              "notes": notes, "computed_at": datetime.now(timezone.utc).isoformat()}
    return {"counts": counts, "rules": rules, "states": states, "stale": stale, "renamed": renamed, "lines": lines,
            "pools": pools}


async def lock_report(db, rid: str) -> None:
    """한 리포트의 다리 · 해석 행 쓰기는 한 번에 하나 — 리포트 행을 FOR UPDATE 로 잠근다.

    ★모든 쓰기 길이 **이 잠금을 먼저** 잡는다(사람 선 확정 · 지우기 · 다시 짓기 · 꾸러미 붙이기의 본 트랜잭션). 차례가 엇갈리면
    교착이었다 — 붙이기가 선을 지운 뒤 FK 검사에서 확정의 행 잠금을, 확정은 규칙 선 지우기에서 붙이기를 기다렸다(검토 11-11 P4).
    둘이 함께 다시 지으면 같은 규칙 선을 두 번 넣어 유일 제약에 걸리는 것도 이 잠금이 막는다.
    """
    await db.execute(select(ImpactReport.id).where(ImpactReport.id == rid).with_for_update())


async def rebuild(db, report: ImpactReport) -> dict:
    """그 리포트의 다리를 다시 짓는다 — 규칙 선은 걷고 지금 거울로 다시 긋고, 사람 선은 그대로 둔다. 셈은 리포트의
    `ontology.bridges` 에 남는다. **커밋은 부르는 쪽이 한다.**"""
    await lock_report(db, report.id)
    # 잠근 뒤 요약을 다시 읽는다 — 잠그기 전에 읽은 객체로 쓰면 그사이 붙은 새 꾸러미의 요약(지문 · 파일)을 옛 값으로 덮었다(검토 11-11 P5)
    await db.refresh(report, attribute_names=["ontology"])
    p = await plan(db, report)
    await db.execute(delete(OntoRelation).where(
        OntoRelation.report_id == report.id, OntoRelation.relation.in_(relations()),
        func.coalesce(OntoRelation.properties["basis"].astext, "") != HUMAN))
    db.add_all([OntoRelation(relation=r["relation"], src_type=r["src_type"], src_key=r["src_key"], dst_type=r["dst_type"],
                             dst_key=r["dst_key"], source=SOURCE_SELF, deleted=False, report_id=report.id,
                             properties={"basis": RULE, "matched_by": r["matched_by"], "matched_text": r["matched_text"]})
                for r in p["rules"]])
    onto = {**(report.ontology if isinstance(report.ontology, dict) else {}), "bridges": p["counts"]}
    # 리포트 행은 ORM 으로 더럽히지 않고 문장으로 쓴다 — 저장점(rebuild_after_attach)이 되감기면 더럽혀진 객체는 만료되고,
    # 부르는 쪽(번들 반입 · 7-1 스캔)이 그 객체를 async 에서 읽으면 깨진다. 쓴 뒤에 메모리 값만 맞춘다.
    await db.execute(update(ImpactReport).where(ImpactReport.id == report.id).values(ontology=onto)
                     .execution_options(synchronize_session=False))
    set_committed_value(report, "ontology", onto)
    return p


async def rebuild_after_attach(db, report: ImpactReport) -> dict:
    """꾸러미를 붙인 끝에 다리를 다시 짓고 커밋한다 — **깨져도 붙이기를 무르지 않는다**(행은 이미 커밋됐다).

    ★저장점(SAVEPOINT) 안에서 짓는다 — 깨지면 다리만 되감고 **부르는 쪽 세션은 되감지 않는다.** 예전에는 세션을 통째로 되감아
    부르는 쪽 객체가 만료됐고, 번들 반입이 응답을 짓다 500 이 나고(리포트 · 꾸러미는 이미 굳은 뒤) 7-1 스캔이 다음 잡에서 멈췄다
    (검토 11-11 P1 · P8). 셈 또는 `{"error": …}` — 실패해도 붙이기 결과는 그대로다(다음 붙이기가 다시 짓는다).
    """
    rid = report.id
    try:
        async with db.begin_nested():
            got = await rebuild(db, report)
        counts = got["counts"]
    except Exception as exc:                # noqa: BLE001 — 다리 하나가 실은 꾸러미를 무르게 하면 안 된다
        logger.exception("코어 다리 짓기 실패 — report %s", rid)
        counts = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        await db.commit()                   # 지은 다리(또는 아무것도)를 굳히고 리포트 행 잠금을 푼다 — 되감지 않는다
    except Exception as exc:                # noqa: BLE001
        logger.exception("코어 다리 커밋 실패 — report %s", rid)
        counts = counts if counts.get("error") else {"error": f"{type(exc).__name__}: {exc}"}
    return counts


def brief(counts: dict | None) -> str:
    """응답 문구 한 토막 — 「코어 다리 규칙 7 · 사람 0 · 후보 8 · 못 붙임 31」."""
    if not isinstance(counts, dict):
        return ""
    if counts.get("error"):
        return f"코어 다리를 못 지었다({counts['error']})"
    out = (f"코어 다리 규칙 {counts.get('rule', 0)} · 사람 {counts.get('human', 0)} · 후보 {counts.get('candidates', 0)} · "
           f"못 붙임 {counts.get('unmatched', 0) + counts.get('unnamed', 0)}")
    out += f" · 끊긴 사람 선 {counts['stale']}" if counts.get("stale") else ""
    return out + (f" · 이름 바뀐 사람 선 {counts['renamed']}" if counts.get("renamed") else "")


# ── 보기 ────────────────────────────────────────────────────────────────────────────────

async def _ends(db, lines: list, pools: dict) -> dict[tuple[str, str], tuple[str, bool]]:
    """선의 코어 끝 → (이름, 살아 있나). 거울에 살아 있는 것은 계획이 읽은 것으로, 사라진 것은 한 번 더 읽는다."""
    out: dict[tuple[str, str], tuple[str, bool]] = {}
    gone = set()
    for e in lines:
        pool = pools.get(e.dst_type)
        if pool is not None and e.dst_key in pool.labels:
            out[(e.dst_type, e.dst_key)] = (pool.labels[e.dst_key], True)
        else:
            gone.add((e.dst_type, e.dst_key))
    if gone:
        for t, k, lab in (await db.execute(select(OntoObject.type_slug, OntoObject.key, OntoObject.label).where(
                OntoObject.report_id.is_(None), OntoObject.key.in_(sorted({k for _, k in gone}))))).all():
            if (t, k) in gone:
                out[(t, k)] = (lab, False)
    return out


def _line(rid: str, e: OntoRelation, names: dict[str, str], ends: dict) -> dict:
    p = e.properties or {}
    lab, alive = ends.get((e.dst_type, e.dst_key), (None, False))
    out = {"relation": e.relation, "basis": p.get("basis") or RULE, "src_type": e.src_type, "src_key": _rel(rid, e.src_key),
           "src_label": names.get(e.src_key) or p.get("src_label"), "dst_type": e.dst_type, "dst_key": e.dst_key,
           "dst_label": lab, "dst_active": alive}
    for k in ("matched_by", "matched_text", "decided_by", "decided_at", "note"):
        if p.get(k):
            out[k] = p[k]
    if out["basis"] == HUMAN and p.get("src_label") and e.src_key in names and names[e.src_key] != p["src_label"]:
        out["renamed_from"] = p["src_label"]        # 확정 때 이름 — 지금 이름(src_label)과 다르다(drift.renamed)
    return out


async def view(db, report: ImpactReport, *, rows: list, edges: list) -> dict:
    """리포트 보기(`ontology_view`)의 `bridges` — 선(규칙 · 사람) · 끊긴 사람 선 · 후보 · 못 붙인 것 · 셈 · 규칙 글."""
    rid = report.id
    p = await plan(db, report, rows=rows, edges=edges)
    names = {o.key: o.label for o in rows}
    present = {s["obj"].key for s in p["states"]}
    ends = await _ends(db, p["lines"], p["pools"])
    live = sorted((e for e in p["lines"] if e.src_key in present),
                  key=lambda e: (list(NAME_PROP).index(e.src_type) if e.src_type in NAME_PROP else 9,
                                 _natural(e.src_key), e.dst_key))
    out: dict[str, Any] = {
        "rule": RULE_TEXT,
        "counts": p["counts"],
        "lines": [_line(rid, e, names, ends) for e in live],
        "stale": [_line(rid, e, names, ends) for e in sorted(p["stale"], key=lambda e: _natural(e.src_key))],
        "candidates": [{"src_type": s["obj"].type_slug, "src_key": _rel(rid, s["obj"].key), "src_label": s["obj"].label,
                        "name": s["match"]["text"], "relation": s["bridge"].relation, "dst_type": s["bridge"].dst_type,
                        "options": s["match"]["options"], **({"more": s["match"]["more"]} if s["match"].get("more") else {})}
                       for s in p["states"] if s["state"] == "candidates"],
        "unmatched": {},
        "unnamed": {},
    }
    for s in p["states"]:
        if s["state"] in ("unmatched", "unnamed"):
            out[s["state"]].setdefault(s["obj"].type_slug, []).append(_rel(rid, s["obj"].key))
    stored = {(e.relation, e.src_key, e.dst_key) for e in p["lines"] if _basis(e) != HUMAN}
    planned = {(r["relation"], r["src_key"], r["dst_key"]) for r in p["rules"]}
    drift: dict[str, Any] = {}
    notes = []
    if stored != planned:
        drift["add"] = [{"relation": r, "src_key": _rel(rid, s), "dst_key": d} for r, s, d in sorted(planned - stored)]
        drift["drop"] = [{"relation": r, "src_key": _rel(rid, s), "dst_key": d} for r, s, d in sorted(stored - planned)]
        notes.append("거울이나 별칭이 붙인 뒤 바뀌었다 — 저장된 규칙 선이 지금 셈과 다르다. 꾸러미를 다시 붙이면(같은 꾸러미도 된다) "
                     "규칙 선을 다시 짓는다(사람 선은 그대로).")
    if p["renamed"]:
        drift["renamed"] = [{"relation": e.relation, "src_key": _rel(rid, e.src_key), "dst_key": e.dst_key,
                             "src_label_then": (e.properties or {})["src_label"], "src_label_now": names.get(e.src_key)}
                            for e in sorted(p["renamed"], key=lambda e: _natural(e.src_key))]
        notes.append("다시 반입한 꾸러미에서 사람 선이 가리키는 해석 객체의 이름이 확정 때와 다르다 — 사람 선은 그대로 남고 규칙은 그 "
                     "객체를 건너뛴다. 같은 것을 가리키는지 사람이 본다(아니면 그 사람 선을 지우고 다시 확정한다).")
    if drift:
        out["drift"] = {**drift, "note": " ".join(notes)}
    return out


# ── 사람 선 — 확정 · 지우기(권한은 부르는 쪽 — 리포트 주인 · 시스템 관리자, 사용자 결정 11-10) ──────────────────

def _full(rid: str, key: str) -> str:
    key = (key or "").strip()
    return key if key.startswith(f"{rid}/") else f"{rid}/{key}"


def _refuse(status: int, error: str, detail: str, **more) -> dict:
    return {"ok": False, "status": status, "error": error, "detail": detail, **more}


async def confirm(db, report: ImpactReport, *, src_key: str, dst_key: str, dst_type: str = "", relation: str = "",
                  by: str = "", note: str = "") -> dict:
    """사람 선을 긋는다 — 후보든 아니든 **타입이 맞는 짝이면** 된다. 다시 붙여도 남는다. 커밋은 부르는 쪽.

    거절(→ `ok: False` · `status` · `error`) — 그런 해석 객체가 없다(404 not_found) · 다리가 없는 타입(422 no_bridge) · 관계 이름이
    다르다(422 wrong_relation) · 끝 타입이 다르다(422 wrong_type — cae_part 는 part 에만) · 거울에 없는 코어 객체(422 not_in_mirror) ·
    허브에서 사용 안 함(422 inactive) · 다대일인데 다른 사람 선이 이미 있다(409 already_bound — 먼저 지운다).
    같은 짝의 규칙 선이 있으면 그 선을 사람 선으로 올린다. 다대일이면 그 객체의 다른 규칙 선은 다시 짓기에서 빠진다(사람이 이긴다).
    """
    rid, bmap = report.id, bridges()
    await lock_report(db, rid)
    key = _full(rid, src_key)
    found = (await db.execute(select(OntoObject).where(
        OntoObject.report_id == rid, OntoObject.key == key))).scalars().all()
    # 꾸러미 키는 타입 안에서만 유일하다 — 같은 키가 두 타입에 있으면 다리가 있는 타입을 고른다
    obj = next((o for o in found if o.type_slug in bmap), found[0] if found else None)
    if obj is None:
        return _refuse(404, "not_found", f"이 리포트에 해석 객체 {_rel(rid, key)!r} 가 없다 — report_cae 의 key(예 part/3)를 쓴다")
    b = bmap.get(obj.type_slug)
    if b is None:
        return _refuse(422, "no_bridge", f"{obj.type_slug} 에는 코어 다리가 없다 — "
                       + " · ".join(f"{x.src_type} → {x.dst_type}({x.relation})" for x in bmap.values()) + " 만 잇는다")
    if relation and relation != b.relation:
        return _refuse(422, "wrong_relation", f"{obj.type_slug} 의 다리는 {b.relation} 다({relation} 아님)")
    if dst_type and dst_type != b.dst_type:
        return _refuse(422, "wrong_type", f"{obj.type_slug} 는 {b.dst_type} 에만 잇는다({dst_type} 아님)")
    dst_key = (dst_key or "").strip()
    core = (await db.execute(select(OntoObject).where(
        OntoObject.type_slug == b.dst_type, OntoObject.key == dst_key, OntoObject.report_id.is_(None),
        OntoObject.source == SOURCE_HUB))).scalar_one_or_none()
    if core is None:
        other = sorted(set((await db.execute(select(OntoObject.type_slug).where(
            OntoObject.key == dst_key, OntoObject.report_id.is_(None)))).scalars()))
        if other:
            return _refuse(422, "wrong_type", f"{dst_key!r} 는 {' · '.join(other)} 다 — {obj.type_slug} 는 {b.dst_type} 에만 잇는다")
        return _refuse(422, "not_in_mirror", f"코어 거울에 {b.dst_type} {dst_key!r} 가 없다 — 받은 적이 없거나 key 가 틀렸다"
                       " (ontology_find 로 찾는다)")
    if core.deleted:
        return _refuse(422, "inactive", f"코어 {b.dst_type} {dst_key!r} 는 허브에서 사용 안 함이다 — 살아 있는 것에만 잇는다",
                       merged_into=core.merged_into)
    lines = (await db.execute(select(OntoRelation).where(
        OntoRelation.report_id == rid, OntoRelation.relation == b.relation, OntoRelation.src_key == key))).scalars().all()
    same = next((e for e in lines if e.dst_key == dst_key), None)
    if same is not None and _basis(same) == HUMAN:
        return {"ok": True, "already": True, "line": _line(rid, same, {key: obj.label}, {(b.dst_type, dst_key): (core.label, True)}),
                "bridges": (report.ontology or {}).get("bridges") if isinstance(report.ontology, dict) else None}
    if b.single:
        bound = [e.dst_key for e in lines if _basis(e) == HUMAN and e.dst_key != dst_key]
        if bound:
            return _refuse(409, "already_bound", f"{_rel(rid, key)} 에는 사람 선이 이미 있다(→ {bound[0]}) — {b.relation} 는 "
                           "한 객체에 하나다. 먼저 그 선을 지운다", existing=bound[0])
    replaced = [e.dst_key for e in lines if b.single and _basis(e) != HUMAN and e.dst_key != dst_key]
    props = {"basis": HUMAN, "decided_by": by or "", "decided_at": datetime.now(timezone.utc).isoformat(),
             "src_label": obj.label, **({"note": note} if note else {})}
    if same is not None:
        same.properties = {**props, **{k: v for k, v in (same.properties or {}).items() if k in ("matched_by", "matched_text")}}
        line = same
    else:
        line = OntoRelation(relation=b.relation, src_type=obj.type_slug, src_key=key, dst_type=b.dst_type, dst_key=dst_key,
                            properties=props, source=SOURCE_SELF, deleted=False, report_id=rid)
        db.add(line)
    await db.flush()
    got = await rebuild(db, report)
    return {"ok": True, "already": False, "promoted_rule": same is not None, "replaced_rule": replaced,
            "line": _line(rid, line, {key: obj.label}, {(b.dst_type, dst_key): (core.label, True)}), "bridges": got["counts"]}


async def remove(db, report: ImpactReport, *, src_key: str, dst_key: str) -> dict:
    """사람 선을 지운다 — 끊긴 사람 선(해석 객체가 사라진 것)도 지울 수 있다. 규칙 선은 지우지 않는다(다시 지으면 다시 선다).
    커밋은 부르는 쪽."""
    rid = report.id
    await lock_report(db, rid)
    key, dst_key = _full(rid, src_key), (dst_key or "").strip()
    line = (await db.execute(select(OntoRelation).where(
        OntoRelation.report_id == rid, OntoRelation.relation.in_(relations()), OntoRelation.src_key == key,
        OntoRelation.dst_key == dst_key))).scalars().first()
    if line is None:
        return _refuse(404, "not_found", f"{_rel(rid, key)} → {dst_key!r} 다리 선이 없다")
    if _basis(line) != HUMAN:
        return _refuse(409, "rule_line", "규칙 선은 지우지 않는다 — 다시 지으면 다시 선다. 다대일 다리(파트 · 캠페인)는 다른 짝을 "
                       "사람 선으로 확정하면 그것이 이긴다. 다대다(소견)의 규칙 선을 걷는 길은 아직 없다")
    obj = (await db.execute(select(OntoObject.key, OntoObject.label).where(
        OntoObject.report_id == rid, OntoObject.key == key))).first()
    was = _line(rid, line, {key: obj.label} if obj is not None else {}, {})
    was.pop("dst_label", None)
    was.pop("dst_active", None)
    await db.delete(line)
    await db.flush()
    got = await rebuild(db, report)
    return {"ok": True, "was": was, "was_stale": obj is None, "bridges": got["counts"]}
