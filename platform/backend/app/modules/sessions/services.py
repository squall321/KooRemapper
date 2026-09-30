from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Optional

import ulid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, Session, SessionFile, User
from app.shared import visibility as vis
from app.runner.kfile_inspect import inspect_kfile
from app.runner.kfile_modelmeta import run_modelmeta
from app.shared import storage

logger = logging.getLogger(__name__)


async def create_session(
    db: AsyncSession, user_id: int, name: str, description: str | None
) -> Session:
    sid = ulid.new().str
    row = Session(
        id=sid,
        user_id=user_id,
        name=name,
        description=description,
        storage_path=storage.session_rel_dir(user_id, sid),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    storage.ensure_session_dir(user_id, sid)
    return row


async def list_sessions(db: AsyncSession, viewer: User) -> list[tuple[Session, int]]:
    """내 세션 + 내가 볼 수 있는 공개 세션(회사·부서·팀).

    예전에는 user_id 로만 걸렀다. 그러면 조직이 공개해 둔 레퍼런스 모델도 안 보이고,
    게이트웨이 서비스 계정으로 조회하는 심의는 아무것도 못 본다.
    """
    rows = (
        await db.execute(
            select(Session, func.count(SessionFile.id))
            .outerjoin(SessionFile, SessionFile.session_id == Session.id)
            .where(vis.visible_filter(viewer))
            .group_by(Session.id)
            .order_by(Session.updated_at.desc())
        )
    ).all()
    return [(s, c) for s, c in rows]


async def get_owned_session(
    db: AsyncSession, user_id: int, session_id: str
) -> Optional[Session]:
    """쓰기·삭제용 — 소유자 본인만. 공개 세션이어도 남이 고치지는 못한다."""
    row = await db.get(Session, session_id)
    if row is None or row.user_id != user_id:
        return None
    return row


async def get_viewable_session(
    db: AsyncSession, viewer: User, session_id: str
) -> Optional[Session]:
    """읽기용 — 내 것이거나, 공개 범위에 걸리는 남의 세션."""
    row = await db.get(Session, session_id)
    if row is None:
        return None
    if row.user_id == viewer.id:
        return row
    owner = await db.get(User, row.user_id)
    return row if vis.can_view(viewer, row, owner) else None


async def get_viewable_file(
    db: AsyncSession, viewer: User, session_id: str, file_id: int
) -> Optional[SessionFile]:
    """읽기용 파일 — 세션이 보이면 그 안의 파일도 보인다."""
    sess = await get_viewable_session(db, viewer, session_id)
    if sess is None:
        return None
    f = await db.get(SessionFile, file_id)
    if f is None or f.session_id != session_id:
        return None
    return f


async def set_visibility(
    db: AsyncSession, user_id: int, session_id: str, level: str
) -> Optional[Session]:
    """공개 범위 변경 — 소유자만. 잘못된 값은 예외로 구분한다."""
    if not vis.is_valid(level):
        raise ValueError(f"visibility 는 {'|'.join(vis.LEVELS)} 중 하나여야 한다: {level!r}")
    row = await get_owned_session(db, user_id, session_id)
    if row is None:
        return None
    row.visibility = level
    await db.commit()
    await db.refresh(row)
    return row


async def list_files(db: AsyncSession, session_id: str) -> list[SessionFile]:
    return list(
        (
            await db.execute(
                select(SessionFile)
                .where(SessionFile.session_id == session_id)
                .order_by(SessionFile.id.asc())
            )
        ).scalars()
    )


async def get_owned_file(
    db: AsyncSession, user_id: int, session_id: str, file_id: int
) -> Optional[SessionFile]:
    sess = await get_owned_session(db, user_id, session_id)
    if sess is None:
        return None
    f = await db.get(SessionFile, file_id)
    if f is None or f.session_id != session_id:
        return None
    return f


async def add_uploaded_file(
    db: AsyncSession,
    session: Session,
    *,
    filename: str,
    raw: bytes,
    kind: str = "input",
) -> SessionFile:
    """Persist an uploaded file to disk, inspect it, and record metadata.

    ⚠ 하위 경로를 **살린다**(`safe_relpath`). 예전에는 `safe_filename` 으로 눕혀서 `sub/part.k` 가
    `part.k` 가 됐는데, KooRemapper 는 `*INCLUDE` 줄을 출력 덱에 그대로 보존하므로 산출물이
    존재하지 않는 `sub/part.k` 를 가리키게 됐다. LS-DYNA 는 인클루드를 따라가므로 그 덱은 깨진다.
    """
    safe = storage.safe_relpath(filename)
    sess_dir = storage.ensure_session_dir(session.user_id, session.id)
    dest = storage.resolve_within(sess_dir, safe)   # 쓰기 직전 두 번째 방어
    # de-dup name collisions: foo.k, foo_1.k, ... (하위 폴더 안에서 센다)
    if dest.exists():
        parent, base = safe.rsplit("/", 1) if "/" in safe else ("", safe)
        stem, suffix = Path(base).stem, Path(base).suffix
        n = 1
        while (sess_dir / (f"{parent}/{stem}_{n}{suffix}" if parent else f"{stem}_{n}{suffix}")).exists():
            n += 1
        safe = f"{parent}/{stem}_{n}{suffix}" if parent else f"{stem}_{n}{suffix}"
        dest = storage.resolve_within(sess_dir, safe)
    # Offload the blocking I/O + `info` subprocess (up to 120s) off the event loop
    # so one upload doesn't stall the single-process API for all other requests.
    dest.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(dest.write_bytes, raw)

    rel = f"{session.storage_path}/{safe}"
    meta = await asyncio.to_thread(inspect_kfile, dest)
    sha = await asyncio.to_thread(storage.sha256_of, dest)
    row = SessionFile(
        session_id=session.id,
        filename=safe,
        rel_path=rel,
        kind=kind,
        size_bytes=dest.stat().st_size,
        sha256=sha,
        meta=meta,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


def _norm_include(p: str) -> str:
    """덱에 적힌 인클루드 경로를 세션 파일명과 견줄 수 있는 꼴로 normalize."""
    return storage.safe_relpath(p)


async def include_status(db: AsyncSession, session_id: str) -> dict:
    """세션 안의 덱들이 참조하는 `*INCLUDE` 가 실제로 올라와 있나.

    ⚠ 왜 필요한가 — KooRemapper 는 `*INCLUDE` 를 **읽지 않지만 출력 덱에 그 줄을 보존한다**.
    그래서 인클루드가 빠져 있어도 op 은 **성공한다**. 깨진 것은 산출물이고, 그것을 LS-DYNA 에
    넣는 순간 드러난다 — 도구가 말해 주지 않으면 사람은 해석을 돌리고 나서야 안다.

    반환: {"<덱 파일명>": {"missing": [...], "satisfied": [...]}} — 빠진 게 없으면 항목을 내지 않는다.
    """
    files = await list_files(db, session_id)
    have = {f.filename for f in files}
    # 하위 경로 없이 올라온 것도 이름으로 맞춰 본다(옛 세션은 평탄화돼 있다)
    have_basenames = {f.filename.rsplit("/", 1)[-1] for f in files}
    out: dict[str, dict] = {}
    for f in files:
        incs = ((f.meta or {}).get("includes") or []) if isinstance(f.meta, dict) else []
        if not incs:
            continue
        missing, satisfied = [], []
        for raw in incs:
            norm = _norm_include(raw)
            if norm in have or norm.rsplit("/", 1)[-1] in have_basenames:
                satisfied.append(raw)
            else:
                missing.append(raw)
        if missing:
            out[f.filename] = {"missing": missing, "satisfied": satisfied}
    return out


async def dangling_status(db: AsyncSession, session_id: str) -> dict:
    """세션 안의 덱들이 **정의되지 않은 것을 가리키나** (P1-5).

    ⚠ 왜 필요한가 — `info` 는 그것을 **보고만 하고 rc 를 올리지 않는다**(그 rc=0 은 계약이다).
    실측: 추적 덱 489장 중 40장에 실제 결함이 들어 있고 40장 전부 rc=0 으로 나갔다. 하류는
    rc 로만 판정하므로 LS-DYNA 에 가서야 터진다. 그래서 막는 자리는 **잡 제출**이다.

    **단정 등급만 낸다.** `*INCLUDE` 를 못 읽었으면 그 안에 정의됐을 수 있어 단정할 수 없고,
    그것을 막으면 오탐이다 — 오탐 한 번에 사람은 이 게이트를 통째로 끈다.

    ⚠ **다른 덱이 `*INCLUDE` 하는 파일은 단독으로 판정하지 않는다.** LS-DYNA 는 그 파일을 혼자
    읽지 않으므로 "이 덱 안에 정의가 없다" 는 것이 결함이 아니다 — 정의는 마스터 덱에 있다.

    실사용 1,967장 실측(2026-09-27): 단정 등급 **148장** 중 **147장이 오탐**이고 진성은 1장이다
    (오탐율 **99.3%**). 그 147장의 정체 — 122장이 같은/부모 폴더의 다른 덱이 `*INCLUDE` 하는
    파일, 13장이 마스터가 보관되지 않은 조각, 12장이 재료를 뒤에서 붙이는 파이프라인의 메시 전용
    입력 덱(그게 바로 KooRemapper op 의 입력이다). 이 면제가 그중 122장을 걷어낸다.

    반환: {"<덱 파일명>": {"count": n, "damaged": n, "top": [...]}} — 단정할 게 없으면 안 낸다.
    """
    files = await list_files(db, session_id)
    # 이 세션 안에서 **누군가가 인클루드하는** 이름들. 그 파일은 조각이므로 단독 판정에서 뺀다.
    included: set[str] = set()
    for f in files:
        for raw in (((f.meta or {}).get("includes") or []) if isinstance(f.meta, dict) else []):
            norm = _norm_include(raw)
            included.add(norm)
            included.add(norm.rsplit("/", 1)[-1])
    out: dict[str, dict] = {}
    for f in files:
        ref = (f.meta or {}).get("ref_dangling") if isinstance(f.meta, dict) else None
        if not isinstance(ref, dict) or ref.get("grade") != "certain":
            continue
        if f.filename in included or f.filename.rsplit("/", 1)[-1] in included:
            continue     # 조각이다 — 정의는 이 파일을 인클루드하는 마스터에 있다
        out[f.filename] = {
            "count": ref.get("count") or 0,
            "damaged": ref.get("damaged") or 0,
            "top": ref.get("top") or [],
        }
    return out


async def run_file_connectivity(
    db: AsyncSession, f: SessionFile, *, detect: bool = True
) -> dict:
    """온디맨드 connectivity 재추출 (detect=기하 탐지). 결과를 file.meta 에 갱신.

    modelmeta 는 별도 프로세스라 이벤트 루프를 막지 않게 스레드로 오프로드한다.
    """
    p = storage.abs_path(f.rel_path)
    mm = await asyncio.to_thread(run_modelmeta, p, detect=detect, timeout=300)
    if mm is not None:
        meta = dict(f.meta or {})
        meta["modelmeta"] = mm
        f.meta = meta
        await db.commit()
        await db.refresh(f)
    return mm or {"error": "not a keyword deck"}


async def delete_file(db: AsyncSession, f: SessionFile) -> None:
    p = storage.abs_path(f.rel_path)
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass
    await db.delete(f)
    await db.commit()


# 세션 삭제 시 도는 잡이 멈출 때까지 기다리는 상한. 사용자는 삭제를 눌렀으니 무한정 붙잡지
# 않는다 — 상한을 넘기면 삭제를 진행하고, 못 멈춘 잡은 러너가 로그에 남긴다(`_note_crash`).
# SIGTERM 뒤 5초에 SIGKILL 이 가므로(`request_cancel`) 8초면 프로세스가 죽고 러너가 상태를
# 쓸 틈까지 든다.
_STOP_WAIT_SEC = 8.0
_STOP_POLL_SEC = 0.25
_LIVE_STATUSES = ("queued", "running")


async def _stop_live_jobs(session_id: str) -> list[str]:
    """이 세션의 로컬 잡에 취소를 넣고 멈출 때까지 짧게 기다린다.

    돌려주는 것은 **상한 안에 멈추지 않은** 잡 목록이다(빈 목록이면 다 멈췄다).
    """
    from app.database import SessionLocal
    from app.worker.runner_loop import request_cancel  # 순환 임포트를 피해 함수 안에서 받는다

    async with SessionLocal() as probe:
        ids = list((await probe.execute(
            select(Job.id).where(
                Job.session_id == session_id,
                Job.status.in_(_LIVE_STATUSES),
                # ⚠ 외부 잡은 우리 자식이 아니라 다른 클러스터에서 돈다 — 신호를 보낼 자리가
                # 없으므로 기다리지 않는다. 붙잡으면 4시간짜리 하나 때문에 삭제가 멈춘다.
                Job.external_kind.is_(None),
            )
        )).scalars())
    if not ids:
        return []
    for jid in ids:
        request_cancel(jid)

    left = ids
    waited = 0.0
    while waited < _STOP_WAIT_SEC:
        await asyncio.sleep(_STOP_POLL_SEC)
        waited += _STOP_POLL_SEC
        # ⚠ **새 세션으로** 읽는다. 요청 세션의 트랜잭션 안에서 읽으면 워커가 커밋한 상태 변화를
        # 언제 보게 될지가 격리 수준에 달린다 — 그 불확실성을 여기 두지 않는다.
        async with SessionLocal() as probe:
            left = list((await probe.execute(
                select(Job.id).where(Job.id.in_(ids), Job.status.in_(_LIVE_STATUSES))
            )).scalars())
        if not left:
            return []
    return left


async def delete_session(db: AsyncSession, session: Session) -> None:
    """세션과 그 파일을 지운다. **도는 잡을 먼저 멈춘다.**

    ⚠ 예전 판은 `rmtree` + `db.delete` 두 줄이라 도는 잡을 보지 않았고, 실측으로 두 가지가
    일어났다.

      · 자식 프로세스가 신호를 하나도 못 받는다. unlink 된 cwd 에서 계산을 계속하다 **끝에서**
        산출물 쓰기가 깨지고, 그동안 `worker_concurrency` 자리 하나를 최대 `job_timeout_sec`
        (기본 1800초) 물고 있어 다른 사용자의 큐가 좁아진다.
      · `sessions.id` FK 가 `ON DELETE CASCADE` 라 잡 행이 함께 사라진다. 그러면 러너의 `UPDATE`
        가 `StaleDataError` 를 내고 잡이 제품에서 **흔적 없이 사라진다** — 그렇게 사라진 잡 4건이
        로그에만 있고 DB 에는 없었으며 `error_summary='worker exception'` 인 잡은 **0건**이었다.

    이제 취소를 먼저 넣고 짧게 기다린다. 사용자 눈에는 그대로 지워지고 잡은 `canceled` 로 남는다.
    """
    stuck = await _stop_live_jobs(session.id)
    if stuck:
        # 상한 안에 못 멈춘 잡이 있다는 사실을 말한다 — 조용히 지우면 위의 옛 동작으로 되돌아간다.
        logger.warning(
            "session %s 삭제: 잡 %s 가 %.0f초 안에 멈추지 않았다 — 그대로 삭제한다"
            "(그 잡은 러너가 크래시 로그로 남긴다)",
            session.id, ",".join(stuck), _STOP_WAIT_SEC,
        )
    # remove files on disk
    d = storage.session_abs_dir(session.user_id, session.id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    await db.delete(session)
    await db.commit()
