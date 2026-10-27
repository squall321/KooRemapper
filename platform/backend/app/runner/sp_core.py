# SP 허브의 코어 API 로 기준정보(과제·개발모델 …)를 **받는** 쪽 — 받기만 하고 고치지 않는다
"""출처: StandardPlatform `backend/app/modules/coreapi/kit/sp_core_pull.py`@f7485c0
(그 키트는 `requests`+`sqlite3` 이다 — 여기서는 **httpx + SQLAlchemy** 로 옮겼다).

**과제의 정본은 허브다.** 우리 화면에서 고치면 다음 받기가 그 값을 덮어쓰고, 그 사실은 고친
사람에게 안 보인다(SP `ontology/managed.py`). 그래서 받은 행은 `source="hub"` 로 표시하고
우리 길에서는 고치지 않는다.

계약(실측 — `coreapi/routes.py`·`schemas.py`@f7485c0) —

    GET /core                        → {system, revision, as_of, types[]}
    GET /core/{type}?since=&cursor=  → {type_slug, as_of, since, next, items[]}
    GET /core/{type}/relations        → 같은 꼴, items 는 {src, relation, dst, …}
    Authorization: Bearer <core:read 범위 토큰>

행 봉투는 **고정**이다 — `key`·`label`·`status`·`updated_at`·`deleted`·`hidden`·
`merged_into`·`renamed_from`.

**수신 규칙 열하나**(`docs/외부-시스템-연동-지침서.md` §4.2 — 머리 186행 · 규칙 311~343행)를
이 파일이 전부 지킨다. 규칙 번호를 주석에 **그대로** 달아 둔다 — 나중에 한 줄을 고칠 때
무엇을 깨는지 보이게.

★**키트에 없는 것을 하나 채웠다** — 키트는 `renamed_from` 을 **전혀 다루지 않는다**
(`ENVELOPE` 에도 없다). 그런데 규칙 4 가 요구한다: "`renamed_from` 이 있으면 그 옛 식별자로
제가 가진 행을 찾아 키를 옮긴다 — 안 그러면 **같은 것이 둘이 된다**." 그대로 베끼면 구멍을
물려받으므로 여기서 구현했고 회귀로 고정했다.

실패를 예외로 올리지 않는다 — `{"ok": False, "error": …}` 로 돌려준다(이 리포 규약).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models import SOURCE_HUB, OntoObject, OntoRelation, OntoSyncState

DEFAULT_TIMEOUT = 60.0
# 규칙 11 — 404 는 두 가지다. 이 코드면 **그 타입 수신을 멈추고 알린다**(계속 두드리지 않는다).
NOT_PUBLISHED = "APP-CORE-0001"
# 한 타입에서 받을 쪽 수 상한 — 커서가 제자리를 돌면(서버 버그·우리 오해) 영원히 돈다.
MAX_PAGES = 10_000


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


class SpCoreClient:
    """코어 API 읽기 전용 클라이언트. 자격이 없으면 **아무것도 부르지 않는다**."""

    def __init__(self, base_url: str, token: str, *,
                 client: httpx.AsyncClient | None = None,
                 timeout: float = DEFAULT_TIMEOUT, page_size: int = 500) -> None:
        self.base = (base_url or "").strip().rstrip("/")
        self.token = (token or "").strip()
        self.page_size = page_size
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    @property
    def available(self) -> bool:
        return bool(self.base and self.token)

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def get(self, path: str, params: Mapping[str, Any] | None = None) -> dict:
        """→ {"ok": True, "body": …} 또는 {"ok": False, "error": …, "code": …}."""
        if not self.available:
            return {"ok": False, "error": "unavailable",
                    "detail": "허브 주소 또는 토큰이 없다(KOORM_SP_CORE_URL/KOORM_SP_CORE_TOKEN)"}
        try:
            res = await self._http().get(
                self.base + path,
                headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
                params=dict(params or {}), timeout=self._timeout)
        except httpx.HTTPError as exc:
            return {"ok": False, "error": "transport_error",
                    "detail": f"{type(exc).__name__}: {exc}"}
        if res.status_code >= 400:
            # 규칙 11 — 404 를 가른다. 공개 안 된 타입은 **고칠 곳이 다르다**(허브 관리자).
            return {"ok": False, "error": f"http_{res.status_code}",
                    "code": _error_code(res), "detail": _said(res)}
        try:
            return {"ok": True, "body": res.json()}
        except ValueError:
            return {"ok": False, "error": "unparsable_reply", "detail": res.text[:300]}

    async def catalog(self) -> dict:
        return await self.get("/core")

    async def page(self, type_slug: str, *, since: str = "", cursor: str = "") -> dict:
        params: dict[str, Any] = {"limit": self.page_size}
        if since:
            params["since"] = since          # 규칙 1 — 서버가 준 값을 그대로 되돌려 준다
        if cursor:
            params["cursor"] = cursor        # 규칙 — `next` 는 그대로 돌려준다(모양은 약속이 아니다)
        return await self.get(f"/core/{type_slug}", params)

    async def relations_page(self, type_slug: str, *, since: str = "", cursor: str = "") -> dict:
        params: dict[str, Any] = {"limit": self.page_size}
        if since:
            params["since"] = since
        if cursor:
            params["cursor"] = cursor
        return await self.get(f"/core/{type_slug}/relations", params)

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None


# ── 저장 ───────────────────────────────────────────────────────────────────

async def _move_renamed(db, type_slug: str, rows: list[dict]) -> int:
    """규칙 4 — `renamed_from` 이 오면 **옛 식별자로 가진 행을 찾아 키를 옮긴다.**

    ★키트에 이 처리가 없다. 없으면 새 식별자가 처음 보는 것이라 **같은 것이 둘이 된다**
    (옛 행은 아무도 안 지우므로 조용히 남아 검색·집계에 두 번 센다).

    옛 키는 버리지 않고 `previous_keys` 에 쌓는다 — 우리 선이 옛 키를 가리키고 있을 수 있고,
    "그 과제 예전 번호로 찾았다" 를 답할 수 있어야 한다.
    """
    moved = 0
    for row in rows:
        old = str(row.get("renamed_from") or "").strip()
        new = str(row.get("key") or "").strip()
        if not old or not new or old == new:
            continue
        found = (await db.execute(
            select(OntoObject).where(OntoObject.type_slug == type_slug,
                                     OntoObject.key == old))).scalar_one_or_none()
        if found is None:
            continue
        prev = list(found.previous_keys or [])
        if old not in prev:
            prev.append(old)
        found.key = new
        found.previous_keys = prev
        moved += 1
    if moved:
        await db.flush()
    return moved


async def save_rows(db, type_slug: str, rows: list[dict]) -> dict:
    """받은 행을 `onto_objects` 에 upsert. 규칙 3·4·5·6·8 이 여기 산다."""
    if not rows:
        return {"rows": 0, "deleted": 0, "hidden": 0, "renamed": 0}

    renamed = await _move_renamed(db, type_slug, rows)   # 규칙 4 — upsert **전에** 옮긴다

    # 규칙 4(hidden) — 이름·칸이 **안 오므로** 가진 값은 두고 비활성만 한다.
    #   없던 것은 **만들지 않는다** — 빈 라벨의 유령 행이 생기면 화면이 그것을 보여 준다.
    hidden_keys = [str(r["key"]) for r in rows if r.get("hidden") and r.get("key")]
    if hidden_keys:
        await db.execute(
            update(OntoObject)
            .where(OntoObject.type_slug == type_slug, OntoObject.key.in_(hidden_keys))
            .values(deleted=True, hidden=True))

    # ★규칙 6 — 같은 행이 **한 쪽 안에서** 두 번 올 수 있다. Postgres 는 한 `INSERT … ON
    #   CONFLICT DO UPDATE` 문장에서 **같은 행을 두 번 못 고친다**(실측:
    #   `CardinalityViolationError: ON CONFLICT DO UPDATE command cannot affect row a second
    #   time`). 그래서 보내기 전에 접는다 — **나중 것이 이긴다**(그것이 더 새것이다).
    #   접지 않으면 트랜잭션이 통째로 깨지고, 그 쪽의 멀쩡한 행까지 안 들어간다.
    folded: dict[str, dict] = {}
    for row in rows:
        if row.get("hidden"):
            continue
        key = str(row.get("key") or "")
        if not key:
            continue
        folded[key] = row

    payload = []
    for key, row in folded.items():
        payload.append({
            "type_slug": type_slug,
            "key": key,
            "label": str(row.get("label") or ""),
            "status": str(row.get("status") or "active"),
            # 규칙 5 — **모르는 칸은 무시한다.** 해석해서 줄이지 않고 그대로 담는다.
            #   규칙 10 — 참조 칸의 값은 보낼 때의 `key` 다. 풀지 않는다.
            "properties": row.get("properties") or {},
            "deleted": bool(row.get("deleted")),      # 규칙 8 — false 로 다시 오면 되살아난다
            "hidden": False,
            "merged_into": row.get("merged_into"),
            "source": SOURCE_HUB,
            "updated_at": row.get("updated_at"),
            "synced_at": datetime.now(timezone.utc),
        })

    if payload:
        stmt = pg_insert(OntoObject).values(payload)
        # 규칙 6 — 같은 행이 두 번 올 수 있다. upsert 라 덮어쓰면 해가 없다.
        #   `previous_keys` 는 **건드리지 않는다** — 개명 이력은 우리가 쌓은 것이다.
        await db.execute(stmt.on_conflict_do_update(
            constraint="uq_onto_objects_type_key",
            set_={c: stmt.excluded[c] for c in
                  ("label", "status", "properties", "deleted", "hidden",
                   "merged_into", "source", "updated_at", "synced_at")}))
    return {"rows": len(rows), "deleted": sum(1 for r in rows if r.get("deleted")),
            "hidden": len(hidden_keys), "renamed": renamed}


async def save_relations(db, type_slug: str, rows: list[dict]) -> dict:
    """선을 `onto_relations` 에 upsert. **끝점은 `key` 로** 온다.

    규칙 9 — 합쳐진 쪽의 선은 「끊긴 선」 으로 오지 않는다. 합치기는 진 쪽의 선을 **이긴
    쪽으로 옮기므로** 새 끝점으로 다시 온다. 그래서 끊김을 따로 추론하지 않는다.
    """
    if not rows:
        return {"rows": 0, "deleted": 0}
    # 규칙 6 은 선에도 같다 — 끝점 다섯이 같은 선이 두 번 오면 접는다(나중 것이 이긴다).
    folded: dict[tuple, dict] = {}
    for row in rows:
        src, dst, rel = row.get("src"), row.get("dst"), row.get("relation")
        if not src or not dst or not rel:
            continue
        folded[(str(rel), str(row.get("src_type") or type_slug), str(src),
                str(row.get("dst_type") or ""), str(dst))] = row

    payload = []
    for (rel, src_type, src, dst_type, dst), row in folded.items():
        payload.append({
            "relation": rel,
            "src_type": src_type,
            "src_key": src,
            "dst_type": dst_type,
            "dst_key": dst,
            "properties": row.get("properties") or {},
            "deleted": bool(row.get("deleted")),
            "source": SOURCE_HUB,
            "synced_at": datetime.now(timezone.utc),
        })
    if payload:
        stmt = pg_insert(OntoRelation).values(payload)
        await db.execute(stmt.on_conflict_do_update(
            constraint="uq_onto_relations_edge",
            set_={c: stmt.excluded[c] for c in
                  ("properties", "deleted", "source", "synced_at")}))
    return {"rows": len(rows), "deleted": sum(1 for r in rows if r.get("deleted"))}


async def _absent_sweep(db, type_slug: str, seen: set[str]) -> int:
    """규칙 7 — **`since` 없이 받으면 지워진 것은 안 온다.**

    처음 받을 때는 그게 맞지만, 이미 받아 둔 것이 있는데 전량으로 다시 받으면 「안 온 것」 이
    곧 「사라진 것」 이다. 그것을 안 하면 **허브에서 지워진 과제가 우리 쪽에 영원히 산다.**
    빈 응답을 「없다」 로 읽는 함정과 같은 자리다 — 그래서 **전량일 때만** 쓸어낸다.
    """
    if not seen:
        # 전량인데 한 건도 안 왔다 — 「다 지워졌다」 와 「조회가 잘못됐다」 를 가릴 수 없다.
        # 조용히 전부 비활성으로 만들면 되돌릴 수 없으므로 **아무것도 안 한다.**
        return 0
    res = await db.execute(
        update(OntoObject)
        .where(OntoObject.type_slug == type_slug, OntoObject.source == SOURCE_HUB,
               OntoObject.deleted.is_(False), OntoObject.key.not_in(seen))
        .values(deleted=True))
    return int(res.rowcount or 0)


async def _state(db, type_slug: str) -> OntoSyncState:
    row = await db.get(OntoSyncState, type_slug)
    if row is None:
        row = OntoSyncState(type_slug=type_slug)
        db.add(row)
        await db.flush()
    return row


async def sync_type(db, client: SpCoreClient, type_slug: str, *,
                    full: bool = False, with_relations: bool = False) -> dict:
    """한 타입을 받는다. 규칙 1·2·7·11 과 `reset` 이 여기 산다."""
    state = await _state(db, type_slug)
    since = "" if full else (state.objects_as_of or "")
    cursor, pages, did_reset = "", 0, False
    counts = {"rows": 0, "deleted": 0, "hidden": 0, "renamed": 0, "pages": 0, "reset": 0}
    seen: set[str] = set()

    while True:
        if pages >= MAX_PAGES:
            state.last_status, state.last_error = "error", f"쪽이 {MAX_PAGES} 을 넘었다 — 커서가 제자리를 돈다"
            return {"ok": False, "error": "too_many_pages", **counts}
        reply = await client.page(type_slug, since=since, cursor=cursor)
        if not reply["ok"]:
            # 규칙 11 — 공개 안 된 타입이면 **멈추고 알린다.** 계속 두드리지 않는다.
            stopped = reply.get("code") == NOT_PUBLISHED
            state.last_status = "stopped" if stopped else "error"
            # 코드를 **빠뜨리면 안 된다** — `APP-CORE-0001`(공개 안 된 타입)과 그 외는
            # 고칠 곳이 다르다. 사유 문구만 남기면 운영자가 어느 쪽인지 모른다.
            state.last_error = (f"{reply.get('error')} [{reply.get('code') or '-'}]: "
                                f"{str(reply.get('detail'))[:400]}")
            state.last_run_at = datetime.now(timezone.utc)
            return {"ok": False, "error": reply.get("error"), "code": reply.get("code"),
                    "stopped": stopped, **counts}

        body = reply["body"] or {}
        if body.get("reset"):
            if did_reset:
                state.last_status = "error"
                state.last_error = ("since 를 비웠는데도 reset 이 온다 — 허브 쪽에 물어야 한다: "
                                    + str(body.get("reset_reason") or ""))
                return {"ok": False, "error": "reset_loop", **counts}
            # 처음부터 다시 받는다. 옛 시계를 버리고 전량으로 간다.
            did_reset, since, cursor = True, "", ""
            state.objects_as_of = None
            counts["reset"] = 1
            full = True
            seen.clear()
            continue

        items = body.get("items") or []
        saved = await save_rows(db, type_slug, items)
        for k in ("rows", "deleted", "hidden", "renamed"):
            counts[k] += saved[k]
        seen.update(str(r["key"]) for r in items if r.get("key"))
        pages += 1
        counts["pages"] = pages

        cursor = str(body.get("next") or "")
        if cursor:
            # 규칙 2 — 쪽이 남았으면 **시계를 옮기지 않는다.** 여기서 멈추면 남은 쪽을 영영
            #   안 받는다. 서버도 그래서 `next` 가 있을 때 `as_of` 를 null 로 준다.
            continue
        # 규칙 1·2 — **끝까지 받았을 때만** 서버가 준 `as_of` 를 그대로 둔다.
        if body.get("as_of"):
            state.objects_as_of = str(body["as_of"])
        break

    if full:
        counts["swept"] = await _absent_sweep(db, type_slug, seen)   # 규칙 7

    if with_relations:
        edges = await sync_relations(db, client, type_slug, full=full)
        counts["relations"] = edges

    state.last_run_at = datetime.now(timezone.utc)
    state.last_status, state.last_error = "reset" if counts["reset"] else "ok", None
    return {"ok": True, **counts}


async def sync_relations(db, client: SpCoreClient, type_slug: str, *, full: bool = False) -> dict:
    state = await _state(db, type_slug)
    since = "" if full else (state.relations_as_of or "")
    cursor, pages, did_reset = "", 0, False
    counts = {"rows": 0, "deleted": 0, "pages": 0, "reset": 0}

    while True:
        if pages >= MAX_PAGES:
            return {"ok": False, "error": "too_many_pages", **counts}
        reply = await client.relations_page(type_slug, since=since, cursor=cursor)
        if not reply["ok"]:
            return {"ok": False, "error": reply.get("error"), "code": reply.get("code"),
                    "stopped": reply.get("code") == NOT_PUBLISHED, **counts}
        body = reply["body"] or {}
        if body.get("reset"):
            if did_reset:
                return {"ok": False, "error": "reset_loop", **counts}
            did_reset, since, cursor = True, "", ""
            state.relations_as_of = None
            counts["reset"] = 1
            continue
        saved = await save_relations(db, type_slug, body.get("items") or [])
        counts["rows"] += saved["rows"]
        counts["deleted"] += saved["deleted"]
        pages += 1
        counts["pages"] = pages
        cursor = str(body.get("next") or "")
        if cursor:
            continue
        if body.get("as_of"):
            state.relations_as_of = str(body["as_of"])
        break
    return {"ok": True, **counts}


async def sync_all(db, client: SpCoreClient, *, types: list[str] | None = None,
                   full: bool = False) -> dict:
    """카탈로그를 읽고 공개된 타입을 받는다.

    고른 타입 중 공개 목록에 없는 것은 **거절하지 않고 건너뛰며 알린다**(응답 `skipped`, KR-06).
    조용히 빠뜨리지 않는 것이 요점이다 — `skipped` 로 무엇을 못 받았는지 보여 준다(규칙 11 의
    '조용한 빈 결과 금지' 는 그대로 지킨다). 예전엔 하나라도 미공개면 통째 거절했는데, 그러면
    쓰는 타입 셋을 받으려다 공개 안 된 하나 때문에 나머지가 영영 안 들어왔다.
    """
    cat = await client.catalog()
    if not cat["ok"]:
        return {"ok": False, "error": cat.get("error"), "detail": cat.get("detail")}
    body = cat["body"] or {}
    opened = [str(t.get("slug")) for t in (body.get("types") or []) if t.get("slug")]
    revision = str(body.get("revision") or "")
    has_rel = {str(t.get("slug")): bool(t.get("relations")) for t in (body.get("types") or [])}

    requested = list(types or opened)
    skipped = [t for t in requested if t not in opened]
    wanted = [t for t in requested if t in opened]

    out: dict[str, Any] = {"ok": True, "system": body.get("system"), "revision": revision,
                           "opened": opened, "skipped": skipped, "types": {}}
    for slug in wanted:
        got = await sync_type(db, client, slug, full=full,
                              with_relations=has_rel.get(slug, False))
        st = await _state(db, slug)
        # 카탈로그 판 지문이 바뀌면 정의가 바뀐 것이다 — 남겨서 보이게 한다(계획서 §6).
        st.catalog_revision = revision
        out["types"][slug] = got
        if not got.get("ok"):
            out["ok"] = False
    return out
