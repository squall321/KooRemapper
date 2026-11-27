# 자동 파이프라인 원천 — 바뀐 세션(덱)을 쪽 커서로 끝까지 내고, 세션의 허브 과제 · 개발 단계 · 입력 지문을 싣는다(KR-AP1)
"""포털 자동 파이프라인 계약 v1.1 §1(포털 리포 docs/auto-pipeline/contract.md) · 계획 docs/01-plan/features/auto-pipeline-1127.plan.md.

- 「바뀐 때」 는 세션 수정 시각과 마지막 입력 파일 시각 가운데 늦은 것이다 — 세션 `updated_at` 은 세션 행이 바뀔 때만 움직여 파일이
  와도 그대로다.
- `subject.refs` 는 세션 id 하나로 고정한다(사용자 결정 11-27 — 포털이 같은 refs 로 막힘 줄을 걷는다). StepForge 과제 id 는 refs 밖
  `links.step_forge`.
- `project` · `revision` 은 세션 칸(`task_key` · `dev_rev`)이다. 비면 null — 짐작하지 않는다(계약 §0.1 · §4-5).
- 입력 지문은 세션 입력 파일의 sha256 이다. 빈 옛 행은 처음 볼 때 한 번 재서 남긴다(포털 입력 지문은 sha 를 쓴다).
- 시야 — 설정 `KOORM_AUTO_SERVICE_EMAILS` 의 사용자(게이트웨이 서비스 계정)는 모든 세션을, 그 밖은 볼 수 있는 세션만(사용자 결정
  「auto_* 만 모두 읽기」).
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import func, select, tuple_

from app.config import settings
from app.models import Session, SessionFile, User
from app.shared import storage, visibility

DECK_SUFFIXES = (".k", ".key", ".dyn")   # 낼 수 있는 덱 — 인클루드 꼴(.inc · .dynain)은 뺀다
CHANGES_MAX = 500


class AutoError(Exception):
    """계약 §0.3 의 실패 — `error` 낱말과 사람 글."""

    def __init__(self, error: str, detail: str, **extra):
        super().__init__(detail)
        self.error, self.detail, self.extra = error, detail, extra


def is_service(user: User) -> bool:
    return (user.email or "").strip().lower() in settings.auto_service_email_set


def zulu(t: datetime | None) -> str | None:
    if t is None:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _encode_cursor(t: datetime, sid: str) -> str:
    raw = json.dumps({"t": t.astimezone(timezone.utc).isoformat(), "id": sid}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        d = json.loads(raw)
        t = datetime.fromisoformat(d["t"])
        if t.tzinfo is None:
            raise ValueError("시각에 시간대가 없다")
        return t, str(d["id"])
    except Exception as exc:  # noqa: BLE001 — 무엇이 틀렸든 남이 준 글이다
        raise AutoError("bad_cursor", f"커서를 읽을 수 없다 — 앞 호출의 next_since 를 그대로 준다({type(exc).__name__})") from None


def is_deck(filename: str) -> bool:
    return filename.lower().endswith(DECK_SUFFIXES)


def file_sha256(f: SessionFile) -> str | None:
    """입력 파일의 sha256 — 비어 있으면 파일을 한 번 재서 남긴다(부르는 쪽이 커밋한다). 파일이 없으면 None."""
    if f.sha256:
        return f.sha256
    path = storage.abs_path(f.rel_path)
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    f.sha256 = h.hexdigest()
    return f.sha256


def subject(s: Session) -> dict:
    return {"project": s.task_key or None, "revision": s.dev_rev or None, "refs": {"dynaforge": s.id}}


def links(s: Session) -> dict:
    cad = s.linked_cad if isinstance(s.linked_cad, dict) else {}
    return {"step_forge": cad["project_id"]} if cad.get("project_id") else {}


async def session_inputs(db, s: Session) -> list[SessionFile]:
    return list((await db.execute(select(SessionFile).where(
        SessionFile.session_id == s.id, SessionFile.kind == "input").order_by(SessionFile.id))).scalars())


def input_item(f: SessionFile) -> dict:
    return {"kind": "deck" if is_deck(f.filename) else "file", "ref": str(f.id), "name": f.filename,
            "sha256": file_sha256(f), "at": zulu(f.created_at)}


async def changes(db, user: User, *, since: str | None, limit: int) -> dict:
    limit = max(1, min(int(limit or 200), CHANGES_MAX))
    last_file = (select(SessionFile.session_id, func.max(SessionFile.created_at).label("last_file"))
                 .where(SessionFile.kind == "input").group_by(SessionFile.session_id).subquery())
    changed = func.greatest(Session.updated_at, func.coalesce(last_file.c.last_file, Session.updated_at))
    q = select(Session, changed.label("changed_at")).outerjoin(last_file, last_file.c.session_id == Session.id)
    if not is_service(user):
        q = q.where(visibility.visible_filter(user))
    if since:
        t, sid = _decode_cursor(since)
        q = q.where(tuple_(changed, Session.id) > tuple_(t, sid))
    rows = (await db.execute(q.order_by(changed, Session.id).limit(limit + 1))).all()
    page, more = rows[:limit], len(rows) > limit
    items = []
    for s, changed_at in page:
        files = await session_inputs(db, s)
        item = {"subject": subject(s), "inputs": [input_item(f) for f in files],
                "ready": {"deck_ready": sum(1 for f in files if is_deck(f.filename)) == 1},
                "updated_at": zulu(changed_at), "title": s.name}
        if links(s):
            item["links"] = links(s)
        items.append(item)
    await db.commit()                 # 처음 잰 sha256 을 남긴다 — 없으면 아무것도 안 바뀐다
    last = page[-1] if page else None
    return {"items": items, "next_since": _encode_cursor(last[1], last[0].id) if last else since,
            "complete": not more}
