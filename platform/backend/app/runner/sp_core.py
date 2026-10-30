# SP 허브의 코어 API 로 기준정보(과제 · 개발모델 …)를 **받는** 쪽(층 1) — 받기만 하고 고치지 않는다
"""출처: StandardPlatform `backend/app/modules/coreapi/kit/sp_core_pull.py`@778db2f(키트 2026-10-21 판)와 지시서
`kit/01-AI-GUIDE.md` §5. 그 키트는 `requests`+`sqlite3` 이다 — 여기서는 **httpx + SQLAlchemy** 로 옮겼다.

**층 1 이다** — SP 규칙만 알고 이 플랫폼의 쓰임(개정 잇기 등)은 모른다. 반영은 층 2(`app/modules/ontology/services.py`)가
사본 표만 읽어서 한다. 규칙 번호는 지시서 §5.6 의 열여섯을 그대로 단다 — 한 줄을 고칠 때 무엇을 깨는지 보이게.

계약 —

    GET /core                                   → {system, revision, as_of, types[]}
    GET /core/{type}?since=&cursor=&limit=      → {type_slug, as_of, since, next, items[]}
    GET /core/{type}/relations?since=&cursor=   → {…, reset, reset_reason, items[{src, relation, dst, dst_type, …}]}
    Authorization: Bearer <core:read 범위 토큰>

DynaForge 사정 셋(계획 `docs/01-plan/features/sp-receive-1030.plan.md`) —
- 선 표(`onto_relations`)에 허브 선과 우리 선(개정 · 리포트)이 함께 산다. 끊기 · 정리는 **허브 선(source=hub)만** 한다.
- 끊은 선은 지우지 않고 `deleted` 로 둔다(이 표의 규약 — 지시서는 한 가지로 일관하라고만 한다).
- 우리 선이 가리키는 허브 객체가 사라지거나 합쳐져도 우리 선은 그대로다 — 층 2 와 사람이 정한다(사용자 결정 10-30).

실패를 예외로 올리지 않는다 — 결과 사전으로 돌려준다(이 리포 규약). 결과는 셋이다(규칙 16): `ok`(정상) ·
`needs_check`(끝까지 돌았지만 사람이 볼 것이 있다) · `failed`(멈췄다). 토큰은 어디에도 찍지 않는다.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Awaitable, Callable, Iterable, Mapping

import httpx
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models import (
    SOURCE_HUB,
    OntoCatalog,
    OntoObject,
    OntoPreviousKey,
    OntoRelation,
    OntoRelationType,
    OntoSyncState,
    OntoType,
)

KIT_VERSION = "2026-10-21"
DEFAULT_TIMEOUT = 60.0
# 규칙 11 — 연결 오류 · 429 · 5xx 는 2초 · 4초 뒤 다시(모두 세 번 시도). 시험은 (0, 0) 을 준다.
RETRY_WAITS = (2.0, 4.0)
# 규칙 11 — 404 는 코드 **끝**으로 가른다(접두사는 설치마다 다를 수 있다).
NOT_PUBLISHED = "CORE-0001"
CURSOR_LOST = "CORE-0002"
# 한 흐름에서 받을 쪽 수 상한 — 커서가 제자리를 돌면(서버 버그 · 우리 오해) 영원히 돈다.
MAX_PAGES = 10_000
# 규칙 7 — 처음부터 받았는데 가진 것의 이 비율보다 많이(그리고 GONE_FLOOR 건보다 많이) 안 왔으면 정리하지 않는다.
GONE_LIMIT = 0.5
GONE_FLOOR = 10
_CHUNK = 400


class _NotPublished(Exception):
    """`-CORE-0001` — 공개되지 않은 타입(공개를 거두었거나 이름이 틀렸다). 그 타입만 건너뛴다(규칙 11 · 16)."""


class _Stop(Exception):
    """이번 실행을 멈출 오류 — 인증 거절 · 주소 오류 · 되풀이되는 커서 오류 · reset 되풀이 · 서버 오류 계속."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


def _said(response: httpx.Response) -> str:
    try:
        body = response.json()
        return str((body.get("error") or {}).get("message") or body)[:300]
    except ValueError:
        return response.text[:300]


def _error_code(response: httpx.Response) -> str:
    try:
        return str((response.json().get("error") or {}).get("code") or "")
    except ValueError:
        return ""


def _chunks(items: list, size: int = _CHUNK) -> Iterable[list]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


class SpCoreClient:
    """코어 API 읽기 전용 클라이언트. 자격이 없으면 **아무것도 부르지 않는다**."""

    def __init__(self, base_url: str, token: str, *,
                 client: httpx.AsyncClient | None = None,
                 timeout: float = DEFAULT_TIMEOUT, page_size: int = 500,
                 retry_waits: tuple[float, ...] = RETRY_WAITS,
                 sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep) -> None:
        self.base = (base_url or "").strip().rstrip("/")
        self.token = (token or "").strip()
        self.page_size = page_size
        self.retry_waits = tuple(retry_waits)
        self._sleep = sleep
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    @property
    def available(self) -> bool:
        return bool(self.base and self.token)

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            # ★trust_env=False — 프록시 환경변수(HTTP(S)_PROXY)를 따르지 않는다(KR-14). 따르면
            #   NO_PROXY 에 허브가 빠졌을 때 `core:read` 토큰이 사내 프록시를 평문으로 지난다.
            self._client = httpx.AsyncClient(timeout=self._timeout, trust_env=False)
        return self._client

    async def get(self, path: str, params: Mapping[str, Any] | None = None) -> dict:
        """→ {"ok": True, "body": …} 또는 {"ok": False, "error": 종류, "code", "status", "detail"}.

        종류 — unavailable · auth(401 · 403, 즉시 멈춤) · not_published(`-CORE-0001`) · cursor_lost(`-CORE-0002`) ·
        not_found(그 밖 404 — 주소 오류) · server(429 · 5xx 가 세 번 계속) · transport(연결 오류 세 번) ·
        http_<n>(그 밖 4xx) · unparsable_reply.
        """
        if not self.available:
            return {"ok": False, "error": "unavailable",
                    "detail": "허브 주소 또는 토큰이 없다(KOORM_SP_CORE_URL/KOORM_SP_CORE_TOKEN)"}
        attempts = len(self.retry_waits) + 1
        for attempt in range(attempts):
            last = attempt == attempts - 1
            try:
                res = await self._http().get(
                    self.base + path,
                    headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
                    params=dict(params or {}), timeout=self._timeout)
            except httpx.HTTPError as exc:
                if not last:
                    await self._sleep(self.retry_waits[attempt])
                    continue
                return {"ok": False, "error": "transport", "detail": f"{type(exc).__name__}: {exc}"}
            if res.status_code in (401, 403):
                return {"ok": False, "error": "auth", "status": res.status_code,
                        "detail": f"인증이 거절됐다(HTTP {res.status_code}) — 토큰과 범위(core:read)를 확인한다: {_said(res)}"}
            if res.status_code == 404:
                code = _error_code(res)
                if code.endswith(NOT_PUBLISHED):
                    return {"ok": False, "error": "not_published", "code": code, "status": 404, "detail": _said(res)}
                if code.endswith(CURSOR_LOST):
                    return {"ok": False, "error": "cursor_lost", "code": code, "status": 404, "detail": _said(res)}
                return {"ok": False, "error": "not_found", "code": code, "status": 404,
                        "detail": f"주소를 찾지 못했다(HTTP 404) — 허브 주소(KOORM_SP_CORE_URL)를 확인한다: {path}"}
            if res.status_code == 429 or res.status_code >= 500:
                if not last:
                    await self._sleep(self.retry_waits[attempt])
                    continue
                return {"ok": False, "error": "server", "status": res.status_code,
                        "detail": f"허브 오류가 계속된다(HTTP {res.status_code}): {_said(res)}"}
            if res.status_code >= 400:
                return {"ok": False, "error": f"http_{res.status_code}", "code": _error_code(res),
                        "status": res.status_code, "detail": _said(res)}
            try:
                return {"ok": True, "body": res.json()}
            except ValueError:
                return {"ok": False, "error": "unparsable_reply", "detail": res.text[:300]}
        return {"ok": False, "error": "transport", "detail": "시도가 남지 않았다"}   # 닿지 않는다

    async def catalog(self) -> dict:
        return await self.get("/core")

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None


# ── 쪽 ─────────────────────────────────────────────────────────────────────

def _new_counts() -> dict[str, int]:
    return {"rows": 0, "deleted": 0, "pages": 0, "reset": 0, "restarted": 0, "full": 0,
            "renamed": 0, "revived": 0, "cut": 0, "gone": 0, "held_back": 0, "skipped_gone": 0}


async def _pages(client: SpCoreClient, path: str, since: str, counts: dict[str, int],
                 label: str) -> AsyncIterator[dict]:
    """쪽을 마지막까지 내준다 — 객체와 선이 **같은 규칙**(since · next · as_of · reset · 404).

    끝나면 `counts["full"]` 이 처음부터 받았는지(since 없이) 말한다 — 그때만 부재 대조를 한다(규칙 7).
    """
    cursor = ""
    while True:
        if counts["pages"] >= MAX_PAGES:
            raise _Stop("too_many_pages", f"{label}: 쪽이 {MAX_PAGES} 을 넘었다 — 커서가 제자리를 돈다")
        params: dict[str, Any] = {"limit": client.page_size}
        if since:
            params["since"] = since          # 규칙 1 — 받은 as_of 를 글자 그대로
        if cursor:
            params["cursor"] = cursor        # `next` 는 그대로 돌려준다(모양은 약속이 아니다)
        reply = await client.get(path, params)
        if not reply["ok"]:
            kind = str(reply.get("error"))
            if kind == "cursor_lost":
                # 규칙 11 — 커서를 못 읽으면 커서 없이 **같은 since 로** 한 번 더(같은 행이 두 번 와도 덮어쓰면 그만이다).
                #   되풀이되면 무한히 돌 자리다.
                if not cursor or counts["restarted"]:
                    raise _Stop("cursor_lost", f"{label}: 커서를 읽을 수 없다는 답이 되풀이된다 — 허브에 물어야 한다: "
                                               f"{reply.get('detail')}")
                cursor, counts["restarted"] = "", 1
                continue
            if kind == "not_published":
                # 코드를 남긴다 — `-CORE-0001`(공개 안 됨)은 고칠 곳이 허브 관리자다. 사유 문구만 남기면 어느 쪽인지 모른다.
                raise _NotPublished(f"[{reply.get('code') or '-'}] {reply.get('detail') or ''}")
            raise _Stop(kind, f"{label}: {reply.get('detail')}")
        body = reply["body"] or {}
        if body.get("reset"):
            # 규칙 9 — **처음부터 다시 받으라는 말이다.** 빈 쪽을 「바뀐 것 없음」 으로 읽으면 이미 끊긴 것을 영영
            #   들고 있다. 두 번 연속이면 멈춘다.
            if counts["reset"]:
                raise _Stop("reset_loop", f"{label}: since 를 비웠는데도 reset 이 온다 — 허브에 물어야 한다: "
                                          f"{body.get('reset_reason') or ''}")
            since, cursor, counts["reset"] = "", "", 1
            continue
        counts["pages"] += 1
        cursor = str(body.get("next") or "")
        if not cursor:
            counts["full"] = 0 if since else 1
        yield body
        if not cursor:
            return            # 규칙 2 — `next` 가 빌 때까지 이어 받는다


# ── 객체 ───────────────────────────────────────────────────────────────────

def _old_keys(row: Mapping[str, Any]) -> list[str]:
    """이 행의 옛 식별자 — `previous_keys`(전부, 오래된 것부터)와 `renamed_from`(마지막 것)."""
    key = str(row.get("key") or "")
    out: list[str] = []
    for one in [*(row.get("previous_keys") or []), row.get("renamed_from")]:
        if one and str(one) != key and str(one) not in out:
            out.append(str(one))
    return out


async def _move_edge_ends(db, type_slug: str, key: str, olds: list[str]) -> None:
    """허브 선의 끝을 새 key 로 — 출발 쪽은 (그 타입, 옛 key), 도착 쪽은 (그 타입 또는 빈 도착 타입, 옛 key).

    새 끝으로 같은 선이 이미 있으면 옛 줄은 같은 선의 두 번째 줄이라 지운다(살아 있는 쪽을 남긴다).
    """
    rows = (await db.execute(select(OntoRelation).where(
        OntoRelation.source == SOURCE_HUB,
        or_(and_(OntoRelation.src_type == type_slug, OntoRelation.src_key.in_(olds)),
            and_(OntoRelation.dst_type.in_([type_slug, ""]), OntoRelation.dst_key.in_(olds)))))).scalars().all()
    for r in rows:
        src = key if (r.src_type == type_slug and r.src_key in olds) else r.src_key
        dst = key if (r.dst_type in (type_slug, "") and r.dst_key in olds) else r.dst_key
        clash = (await db.execute(select(OntoRelation).where(
            OntoRelation.relation == r.relation, OntoRelation.src_type == r.src_type, OntoRelation.src_key == src,
            OntoRelation.dst_type == r.dst_type, OntoRelation.dst_key == dst, OntoRelation.id != r.id))).scalar_one_or_none()
        if clash is not None:
            if clash.deleted and not r.deleted:
                clash.deleted = False
            await db.delete(r)
        else:
            r.src_key, r.dst_key = src, dst
    await db.flush()


async def _rekey(db, type_slug: str, key: str, olds: list[str]) -> int:
    """규칙 5 — 식별자가 바뀐 것: 가진 행과 허브 선을 **새 key 로 옮긴다.** 옮긴(또는 지운) 행 수를 돌려준다.

    옮기지 않으면 새 key 가 처음 보는 것이 되어 같은 것이 둘이 된다. 오래 안 받았으면 가진 것이 마지막 옛
    식별자가 아닐 수 있어(A→B→C 에서 A) 옛 식별자를 전부 본다. 옛 → 새 짝은 `onto_previous_keys` 에 남긴다 —
    다른 곳(우리 개정 · 별칭 · 다른 행의 참조 칸)에 남은 옛 값을 거기서 푼다(층 2).
    """
    for old in olds:
        stmt = pg_insert(OntoPreviousKey).values(type_slug=type_slug, old_key=old, key=key)
        await db.execute(stmt.on_conflict_do_update(
            index_elements=["type_slug", "old_key"], set_={"key": key, "seen_at": func.now()}))
    # A→B 를 남긴 뒤 B→C 가 오면 A 도 C 를 가리키게 한다
    await db.execute(update(OntoPreviousKey).where(
        OntoPreviousKey.type_slug == type_slug, OntoPreviousKey.key.in_(olds)).values(key=key))
    moved = 0
    has_new = (await db.execute(select(OntoObject.id).where(
        OntoObject.type_slug == type_slug, OntoObject.key == key))).first() is not None
    for old in olds:
        obj = (await db.execute(select(OntoObject).where(
            OntoObject.type_slug == type_slug, OntoObject.key == old,
            OntoObject.source == SOURCE_HUB))).scalar_one_or_none()
        if obj is None:
            continue
        if has_new:
            await db.delete(obj)          # 새 key 로 이미 받았다 — 옛 행은 같은 것의 두 번째 줄이다
        else:
            obj.key = key
            obj.previous_keys = list(dict.fromkeys([*(obj.previous_keys or []), *olds]))
            has_new = True
        moved += 1
    await db.flush()
    await _move_edge_ends(db, type_slug, key, olds)
    return moved


async def _cut_touching(db, type_slug: str, keys: list[str]) -> int:
    """규칙 10 — 그 객체를 끝으로 하는 **허브 선**을 끊는다(지워졌거나 · 합쳐졌거나 · 더 이상 안 보이는 객체).

    허브는 객체를 지우면 그 선을 내보내지 않을 뿐 「끊긴 선」 으로 알려 주지 않는다(합치기도 같다 — 진 쪽의 선은
    이긴 쪽으로 옮겨 새로 오고, 옛 선의 끊김은 안 온다). 받는 쪽이 끊지 않으면 없는 객체에 매달린 선이 남는다.
    """
    cut = 0
    for part in _chunks(sorted(set(keys))):
        res = await db.execute(update(OntoRelation).where(
            OntoRelation.source == SOURCE_HUB, OntoRelation.deleted.is_(False),
            or_(and_(OntoRelation.src_type == type_slug, OntoRelation.src_key.in_(part)),
                and_(OntoRelation.dst_type.in_([type_slug, ""]), OntoRelation.dst_key.in_(part)))
        ).values(deleted=True, synced_at=func.now()))
        cut += int(res.rowcount or 0)
    return cut


def _fold(rows: list[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    """같은 key 가 한 쪽 안에 두 번 오면 **나중 것이 이긴다**(그것이 더 새것이다).

    Postgres 는 한 `INSERT … ON CONFLICT DO UPDATE` 문장에서 같은 행을 두 번 못 고친다(실측:
    `CardinalityViolationError`) — 접지 않으면 트랜잭션이 통째로 깨져 그 쪽의 멀쩡한 행까지 안 들어간다.
    """
    out: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        key = str(row.get("key") or "")
        if key:
            out[key] = row
    return out


async def save_rows(db, type_slug: str, rows: list[dict]) -> dict:
    """객체 한 쪽을 사본에 맞춘다(§5.4). 규칙 3 · 4 · 5 · 6 · 8 · 10 이 여기 산다."""
    done = {"rows": len(rows), "deleted": sum(1 for r in rows if r.get("deleted")),
            "hidden": sum(1 for r in rows if r.get("hidden")), "renamed": 0, "revived": 0, "cut": 0}
    if not rows:
        return done
    # 규칙 5 — 바뀐 식별자를 **먼저** 옮긴다. 그래야 아래 upsert 가 「새로 만들기」 가 아니라 「고침」 이 된다.
    for row in rows:
        olds = _old_keys(row)
        if olds and row.get("key"):
            done["renamed"] += await _rekey(db, type_slug, str(row["key"]), olds)

    shown = [r for r in rows if r.get("key") and not r.get("hidden")]
    alive = _fold([r for r in shown if not r.get("deleted")])
    dead = _fold([r for r in shown if r.get("deleted")])
    if alive:
        # 규칙 8 — 비활성이던 (타입, key) 가 다시 왔다. 그 선은 바뀐 것이 아니라 증분으로 다시 오지 않으므로
        #   부르는 쪽이 선을 처음부터 다시 받는다.
        done["revived"] = int((await db.execute(select(func.count()).select_from(OntoObject).where(
            OntoObject.type_slug == type_slug, OntoObject.key.in_(list(alive)),
            OntoObject.deleted.is_(True)))).scalar_one())
    now = datetime.now(timezone.utc)

    def values(key: str, row: Mapping[str, Any]) -> dict[str, Any]:
        return {"type_slug": type_slug, "key": key, "label": str(row.get("label") or ""),
                "status": str(row.get("status") or "active"),
                # 규칙 6 — **모르는 칸도 그대로 담는다**(층 2 가 무시한다). 참조 칸의 값은 상대의 key 다 — 풀지 않는다.
                "properties": row.get("properties") or {},
                "deleted": bool(row.get("deleted")), "hidden": False,
                "merged_into": row.get("merged_into"), "source": SOURCE_HUB,
                "updated_at": row.get("updated_at"), "synced_at": now}

    if alive:
        # 규칙 6 — 살아 있는 행은 칸을 **통째로** 바꾼다. 기존 칸에 합치면 허브에서 비운 칸이 안 지워진다.
        stmt = pg_insert(OntoObject).values([values(k, r) for k, r in alive.items()])
        await db.execute(stmt.on_conflict_do_update(
            constraint="uq_onto_objects_type_key",
            set_={c: stmt.excluded[c] for c in ("label", "status", "properties", "deleted", "hidden",
                                                  "merged_into", "source", "updated_at", "synced_at")}))
    if dead:
        # 규칙 4 — 지운 행은 칸이 빈 채로 온다. **가진 칸은 두고**(이미 쓴 기록이 그 값을 보인다) 비활성 + merged_into.
        #   가진 적 없으면 비활성 행으로 만든다(merged_into 를 남기려고).
        stmt = pg_insert(OntoObject).values([values(k, r) for k, r in dead.items()])
        await db.execute(stmt.on_conflict_do_update(
            constraint="uq_onto_objects_type_key",
            set_={c: stmt.excluded[c] for c in ("label", "status", "deleted", "hidden",
                                                  "merged_into", "source", "updated_at", "synced_at")}))
    hidden = [r for r in rows if r.get("key") and r.get("hidden")]
    for row in hidden:
        # 규칙 4 — hidden 은 지운 것이 아니라 이 토큰으로 더 이상 안 보이는 것(소유 부서가 옮겨 감). 이름 · 칸은
        #   오지 않으므로(오는 이름은 식별자다) 가진 것을 그대로 두고 비활성만 한다. **없던 것은 만들지 않는다.**
        await db.execute(update(OntoObject).where(
            OntoObject.type_slug == type_slug, OntoObject.key == str(row["key"])
        ).values(deleted=True, hidden=True, updated_at=row.get("updated_at"), synced_at=now))
    # 규칙 10 — 사라진 것(지움 · 합침 · 안 보임 — hidden 도 deleted 로 온다)을 끝으로 하는 허브 선을 끊는다.
    done["cut"] = await _cut_touching(db, type_slug, [str(r["key"]) for r in rows if r.get("key") and r.get("deleted")])
    return done


# ── 선 ─────────────────────────────────────────────────────────────────────

async def save_relations(db, type_slug: str, rows: list[dict]) -> dict:
    """그 타입에서 출발하는 선 한 쪽을 사본에 맞춘다(§5.4 선). 규칙 10 · 15.

    선의 키는 **다섯 칸**(출발 타입 · 출발 · 관계 · 도착 · 도착 타입)이다 — key 는 타입 안에서만 하나라, 끝이
    인터페이스인 관계는 같은 도착 key 가 두 타입에 있다(규칙 15).
    """
    done = {"rows": len(rows), "deleted": sum(1 for r in rows if r.get("deleted")), "skipped_gone": 0}
    if not rows:
        return done
    folded: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
    for row in rows:
        src, rel, dst = row.get("src"), row.get("relation"), row.get("dst")
        if not src or not rel or not dst:
            continue
        folded[(str(src), str(rel), str(dst), str(row.get("dst_type") or ""))] = row
    # 규칙 10 — 도착 객체가 이쪽에서 비활성이면 넣지 않는다(허브는 출발이 지워진 선만 거르고 도착이 지워진 선은 보낸다).
    wanted: dict[str, set[str]] = {}
    for (_s, _r, dst, dst_type), row in folded.items():
        if dst_type and not row.get("deleted"):
            wanted.setdefault(dst_type, set()).add(dst)
    gone: set[tuple[str, str]] = set()
    for dst_type, keys in wanted.items():
        for part in _chunks(sorted(keys)):
            found = (await db.execute(select(OntoObject.key).where(
                OntoObject.type_slug == dst_type, OntoObject.key.in_(part),
                OntoObject.deleted.is_(True)))).scalars().all()
            gone.update((dst_type, k) for k in found)
    now = datetime.now(timezone.utc)
    payload: list[dict[str, Any]] = []
    for (src, rel, dst, dst_type), row in folded.items():
        if row.get("deleted") or (dst_type, dst) in gone:
            # 끊는다 — 이 다섯 칸의 허브 선(도착 타입이 빈 옛 줄도 같은 선으로 본다)
            await db.execute(update(OntoRelation).where(
                OntoRelation.source == SOURCE_HUB, OntoRelation.relation == rel,
                OntoRelation.src_type == type_slug, OntoRelation.src_key == src,
                OntoRelation.dst_key == dst, OntoRelation.dst_type.in_([dst_type, ""])
            ).values(deleted=True, synced_at=now))
            if not row.get("deleted"):
                done["skipped_gone"] += 1
            continue
        payload.append({"relation": rel, "src_type": type_slug, "src_key": src,
                        "dst_type": dst_type, "dst_key": dst,
                        "properties": row.get("properties") or {},
                        "evidence_note": row.get("evidence_note"), "updated_at": row.get("updated_at"),
                        "deleted": False, "source": SOURCE_HUB, "synced_at": now})
    if payload:
        stmt = pg_insert(OntoRelation).values(payload)
        await db.execute(stmt.on_conflict_do_update(
            constraint="uq_onto_relations_edge",
            set_={c: stmt.excluded[c] for c in ("properties", "evidence_note", "updated_at",
                                                  "deleted", "source", "synced_at")}))
    return done


# ── 처음부터 받았을 때 — 부재 대조(규칙 7) ─────────────────────────────────

def _too_many(gone: int, held: int) -> bool:
    return gone > GONE_FLOOR and gone > GONE_LIMIT * held


async def _prune_rows(db, type_slug: str, seen: set[str], *, allow_shrink: bool) -> tuple[int, int]:
    """처음부터 받았으면 **이번에 안 온 허브 객체를 비활성으로** — (정리한 수, 멈춘 수).

    `since` 없이 받으면 지워진 것은 오지 않는다 — 부재로만 안다. 마지막 쪽까지 받은 뒤에만 부른다(중간에 대조하면
    아직 안 받은 것이 지워진다). **먼저 비우지 않는다** — 받다가 끊기면 아직 안 받은 것까지 사라진다.
    """
    held = set((await db.execute(select(OntoObject.key).where(
        OntoObject.type_slug == type_slug, OntoObject.source == SOURCE_HUB,
        OntoObject.deleted.is_(False)))).scalars().all())
    gone = sorted(held - seen)
    if _too_many(len(gone), len(held)) and not allow_shrink:
        return 0, len(gone)       # 안전장치 — 토큰의 부서 · 공개 범위가 바뀐 날 전부를 비활성으로 만들지 않는다
    for part in _chunks(gone):
        await db.execute(update(OntoObject).where(
            OntoObject.type_slug == type_slug, OntoObject.key.in_(part),
            OntoObject.source == SOURCE_HUB).values(deleted=True, synced_at=func.now()))
    await _cut_touching(db, type_slug, gone)
    return len(gone), 0


async def _prune_relations(db, type_slug: str, seen: set[tuple[str, str, str, str]], *,
                           allow_shrink: bool) -> tuple[int, int]:
    """선도 같다 — 처음부터 받았으면 이번에 안 온 허브 선을 끊는다. (끊은 수, 멈춘 수)."""
    held = {(r.src_key, r.relation, r.dst_key, r.dst_type): r.id for r in (await db.execute(
        select(OntoRelation).where(OntoRelation.src_type == type_slug, OntoRelation.source == SOURCE_HUB,
                                   OntoRelation.deleted.is_(False)))).scalars().all()}
    gone = [rid for edge, rid in held.items() if edge not in seen]
    if _too_many(len(gone), len(held)) and not allow_shrink:
        return 0, len(gone)
    for part in _chunks(gone):
        await db.execute(update(OntoRelation).where(OntoRelation.id.in_(part)).values(
            deleted=True, synced_at=func.now()))
    return len(gone), 0


# ── 흐름 ───────────────────────────────────────────────────────────────────

async def _pull_type(db, client: SpCoreClient, type_slug: str, since: str, *,
                     allow_shrink: bool) -> tuple[dict[str, int], str | None]:
    """한 타입의 객체. 처음부터 받았으면 끝까지 받은 뒤 안 온 것을 비활성으로 둔다. → (건수, 마지막 as_of)."""
    counts = _new_counts()
    seen: set[str] = set()
    last: dict[str, Any] = {}
    async for body in _pages(client, f"/core/{type_slug}", since, counts, type_slug):
        items = body.get("items") or []
        done = await save_rows(db, type_slug, items)
        for k in ("renamed", "revived", "cut"):
            counts[k] += done[k]
        counts["rows"] += len(items)
        counts["deleted"] += done["deleted"]
        seen.update(str(r["key"]) for r in items if r.get("key") and not r.get("deleted"))
        last = body
    if counts["full"]:
        counts["gone"], counts["held_back"] = await _prune_rows(db, type_slug, seen, allow_shrink=allow_shrink)
    # 규칙 1 · 2 — **끝까지 받았을 때만** 서버가 준 as_of 를 글자 그대로 둔다(`next` 가 있으면 as_of 는 null 이다).
    return counts, (str(last["as_of"]) if last.get("as_of") else None)


async def _pull_relations(db, client: SpCoreClient, type_slug: str, since: str, *,
                          allow_shrink: bool) -> tuple[dict[str, int], str | None]:
    """그 타입에서 출발하는 선 — 객체와 **같은 규칙**. 기준 시각은 따로 둔다."""
    counts = _new_counts()
    seen: set[tuple[str, str, str, str]] = set()
    last: dict[str, Any] = {}
    async for body in _pages(client, f"/core/{type_slug}/relations", since, counts, f"{type_slug} 관계"):
        items = body.get("items") or []
        done = await save_relations(db, type_slug, items)
        counts["rows"] += len(items)
        counts["deleted"] += done["deleted"]
        counts["skipped_gone"] += done["skipped_gone"]
        seen.update((str(r.get("src")), str(r.get("relation")), str(r.get("dst")), str(r.get("dst_type") or ""))
                    for r in items if not r.get("deleted"))
        last = body
    if counts["full"]:
        counts["gone"], counts["held_back"] = await _prune_relations(db, type_slug, seen, allow_shrink=allow_shrink)
    return counts, (str(last["as_of"]) if last.get("as_of") else None)


# ── 카탈로그(규칙 12) ──────────────────────────────────────────────────────

def _diff_catalog(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    """두 카탈로그의 차이 — 타입 · 칸 · 관계. 표시 문구(이름 · 설명)는 보지 않는다."""
    old = {one["slug"]: one for one in before.get("types") or [] if one.get("slug")}
    new = {one["slug"]: one for one in after.get("types") or [] if one.get("slug")}
    out = [f"+ 타입 {slug}" for slug in sorted(set(new) - set(old))]
    out += [f"- 타입 {slug}(더 이상 공개되지 않음)" for slug in sorted(set(old) - set(new))]
    for slug in sorted(set(new) & set(old)):
        a = {one.get("key"): one for one in old[slug].get("properties") or []}
        b = {one.get("key"): one for one in new[slug].get("properties") or []}
        out += [f"+ {slug}.{key}({b[key].get('data_type')})" for key in sorted(set(b) - set(a), key=str)]
        out += [f"- {slug}.{key}" for key in sorted(set(a) - set(b), key=str)]
        for key in sorted(set(a) & set(b), key=str):
            changed = [n for n in ("data_type", "multi", "ref_type_slug", "enum_options", "unit")
                       if a[key].get(n) != b[key].get(n)]
            if changed:
                out.append(f"~ {slug}.{key}: {', '.join(changed)} 바뀜")
        was, now = set(old[slug].get("relations") or []), set(new[slug].get("relations") or [])
        out += [f"+ {slug} 관계 {one}" for one in sorted(now - was)]
        out += [f"- {slug} 관계 {one}" for one in sorted(was - now)]
    return out


async def _mirror_definitions(db, catalog: Mapping[str, Any], revision: str) -> None:
    """받은 정의를 `onto_types` · `onto_relation_types`(source=hub)에 둔다 — 화면이 이 정의로 타입 · 칸 · 관계를 그린다.

    지금 카탈로그에 없는 허브 정의는 지운다(정의는 데이터가 아니다 — 그 타입의 객체는 사본에 그대로 남는다).
    관계 종류의 방향 · 전이 · 순환 금지 · 카디널리티는 코어 API 가 싣지 않는다 — 기본값으로 둔다(지어내지 않는다).
    """
    types = [t for t in (catalog.get("types") or []) if t.get("slug")]
    now = datetime.now(timezone.utc)
    if types:
        stmt = pg_insert(OntoType).values([{
            "slug": str(t["slug"]), "label": str(t.get("label") or ""), "description": str(t.get("description") or ""),
            "properties": t.get("properties") or [], "relations": t.get("relations") or [],
            "source": SOURCE_HUB, "catalog_revision": revision, "updated_at": now} for t in types])
        await db.execute(stmt.on_conflict_do_update(
            constraint="uq_onto_types_slug",
            set_={c: stmt.excluded[c] for c in ("label", "description", "properties", "relations",
                                                  "source", "catalog_revision", "updated_at")},
            where=OntoType.source == SOURCE_HUB))
    await db.execute(OntoType.__table__.delete().where(
        OntoType.source == SOURCE_HUB, OntoType.slug.not_in([str(t["slug"]) for t in types] or [""])))
    kinds: dict[str, Mapping[str, Any]] = {}
    for t in types:
        for kind in t.get("relation_kinds") or []:
            if kind.get("slug"):
                kinds[str(kind["slug"])] = kind
    if kinds:
        stmt = pg_insert(OntoRelationType).values([{
            "slug": slug, "label": str(k.get("label") or ""), "src": k.get("src") or [], "dst": k.get("dst") or [],
            "source": SOURCE_HUB, "catalog_revision": revision, "updated_at": now} for slug, k in kinds.items()])
        await db.execute(stmt.on_conflict_do_update(
            constraint="uq_onto_relation_types_slug",
            set_={c: stmt.excluded[c] for c in ("label", "src", "dst", "source", "catalog_revision", "updated_at")},
            where=OntoRelationType.source == SOURCE_HUB))
    await db.execute(OntoRelationType.__table__.delete().where(
        OntoRelationType.source == SOURCE_HUB, OntoRelationType.slug.not_in(list(kinds) or [""])))


async def _remember_catalog(db, catalog: Mapping[str, Any]) -> list[str]:
    """카탈로그를 남기고 — 정의 판이 바뀌었으면 **무엇이 달라졌나**를 돌려준다(처음이면 빈 목록)."""
    revision = str(catalog.get("revision") or "")
    prev = (await db.execute(select(OntoCatalog).order_by(OntoCatalog.id.desc()).limit(1))).scalar_one_or_none()
    lines: list[str] = []
    if prev is None or prev.revision != revision:
        if prev is not None:
            lines.append(f"정의 판이 바뀌었다: {prev.revision} → {revision}")
            lines.extend(_diff_catalog(prev.body or {}, catalog))
        db.add(OntoCatalog(revision=revision, body=dict(catalog)))
        await db.flush()
    await _mirror_definitions(db, catalog, revision)
    return lines


async def _state(db, type_slug: str) -> OntoSyncState:
    row = await db.get(OntoSyncState, type_slug)
    if row is None:
        row = OntoSyncState(type_slug=type_slug)
        db.add(row)
        await db.flush()
    return row


def _held_problem(label: str, counts: Mapping[str, int]) -> str:
    return (f"{label}: 처음부터 받았는데 가진 것 중 {counts['held_back']}건이 안 와서(절반 넘음) 정리하지 않았다 — "
            "토큰의 부서 · 공개 범위를 허브에 확인하고, 정말 줄어든 것이면 「강제 정리」 로 한 번 더 받는다")


# ── 한 번 실행(§5.1) ───────────────────────────────────────────────────────

async def sync_all(db, client: SpCoreClient, *, types: list[str] | None = None,
                   full: bool = False, allow_shrink: bool = False) -> dict:
    """카탈로그를 읽고 공개된 타입을 받는다 — 객체를 **모든 타입 먼저**, 선은 그 뒤에(규칙 13).

    커밋은 부르는 쪽이 한다(잠금 · 실행 기록도 부르는 쪽 — `app/worker/plm_sync.py`). 멈춘 실행(`failed`)도
    그때까지 끝까지 받은 흐름의 기준 시각은 옮겨 둔다 — 다음 실행이 거기서 잇는다.
    """
    out: dict[str, Any] = {"ok": False, "result": "failed", "kit": KIT_VERSION, "system": None, "revision": None,
                           "opened": [], "skipped": [], "types": {}, "relations": {}, "problems": [], "notes": [],
                           "error": None}
    cat = await client.catalog()
    if not cat["ok"]:
        out["error"] = f"{cat.get('error')}: {cat.get('detail')}"
        return out
    catalog = cat["body"] or {}
    opened = [str(t.get("slug")) for t in (catalog.get("types") or []) if t.get("slug")]
    out.update(system=catalog.get("system"), revision=str(catalog.get("revision") or ""), opened=opened)
    changed = await _remember_catalog(db, catalog)
    out["notes"].extend(changed)
    problems: list[str] = out["problems"]

    requested = list(types or opened)
    missing = [t for t in requested if t not in opened]
    if missing:
        # 규칙 16 — 받기로 한 타입이 카탈로그에 없다. 조용히 빠뜨리지 않는다.
        problems.append(f"공개되지 않은 타입은 건너뛰었다: {missing} — 허브 관리자에게 확인한다")
        out["skipped"] = missing
    wanted = [t for t in requested if t in opened]
    has_rel = {str(t.get("slug")): bool(t.get("relations")) for t in (catalog.get("types") or [])}

    restart = bool(full)
    if changed:
        held = (await db.execute(select(func.count()).select_from(OntoSyncState).where(
            or_(OntoSyncState.objects_as_of.is_not(None), OntoSyncState.relations_as_of.is_not(None))))).scalar_one()
        if held:
            # 규칙 12 — 새로 열린 칸 · 관계의 기존 값은 바뀐 것이 아니라 증분으로 오지 않는다.
            out["notes"].append("정의가 바뀌어 전부 처음부터 다시 받는다")
            restart = True

    now = datetime.now(timezone.utc)
    current = ""
    try:
        pulled: list[str] = []
        revived = False
        for slug in wanted:
            current = slug
            st = await _state(db, slug)
            try:
                counts, as_of = await _pull_type(db, client, slug, "" if restart else (st.objects_as_of or ""),
                                                 allow_shrink=allow_shrink)
            except _NotPublished as exc:
                problems.append(f"{slug}: 공개되지 않은 타입이라 건너뛰었다 — {exc}")
                st.last_status, st.last_error, st.last_run_at = "skipped", str(exc)[:400], now
                continue
            if as_of:
                st.objects_as_of = as_of
            st.catalog_revision, st.last_run_at, st.last_status, st.last_error = out["revision"], now, "ok", None
            out["types"][slug] = counts
            pulled.append(slug)
            if counts["held_back"]:
                problems.append(_held_problem(slug, counts))
            revived = revived or counts["revived"] > 0
        if revived:
            out["notes"].append("되살아난 객체가 있어 선을 처음부터 다시 받는다")
        for slug in pulled:
            if not has_rel.get(slug):
                continue
            current = f"{slug} 관계"
            st = await _state(db, slug)
            try:
                counts, as_of = await _pull_relations(
                    db, client, slug, "" if (restart or revived) else (st.relations_as_of or ""),
                    allow_shrink=allow_shrink)
            except _NotPublished as exc:
                problems.append(f"{slug} 관계: 공개되지 않아 건너뛰었다 — {exc}")
                continue
            if as_of:
                st.relations_as_of = as_of
            out["relations"][slug] = counts
            if counts["held_back"]:
                problems.append(_held_problem(f"{slug} 관계", counts))
    except _Stop as exc:
        out["error"] = f"{exc.kind}: {exc.detail}"
        if current:
            st = await _state(db, current.split(" ")[0])
            st.last_status, st.last_error, st.last_run_at = "error", out["error"][:400], now
        return out
    out["ok"] = True
    out["result"] = "needs_check" if problems else "ok"
    return out
