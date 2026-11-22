from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.modules.sessions import services as svc
from app.modules.sessions.schemas import (
    FileRead,
    PartRename,
    SessionCreate,
    SessionRead,
    SessionUpdate,
)
from app.config import settings
from app.shared import storage
from app.shared.auth import get_current_user
from app.shared.ratelimit import rate_limit
from app.shared.responses import ok

router = APIRouter(tags=["sessions"])


# ── sessions ────────────────────────────────────────────────────────
def _revision_warning(label: str | None, cad: dict | None) -> str | None:
    """덱 판 라벨과 연결된 CAD 판이 둘 다 있고(앞뒤 공백 · 대소문자를 빼고) 다르면 경고 글(DF-15)."""
    rev = (cad or {}).get("revision")
    if not label or not rev or label.strip().casefold() == str(rev).strip().casefold():
        return None
    return f"덱 판 「{label}」 과 연결된 CAD 판 「{rev}」 이 다르다 — 리포트를 근거로 쓰기 전에 판을 맞추세요"


def _session_out(s, **extra) -> dict:
    """세션 응답 — 환경 · 덱 판 · CAD 연결 · 판 경고를 싣는다(DF-15 — 모든 세션 응답에 environment)."""
    d = SessionRead.model_validate(s).model_dump()
    d["environment"] = settings.environment
    d["revision_warning"] = _revision_warning(s.deck_revision_label, s.linked_cad)
    d.update(extra)
    return d


@router.get("/sessions")
async def list_sessions(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await svc.list_sessions(db, user))[offset : offset + limit]
    data = []
    for s, count in rows:
        data.append(_session_out(s, file_count=count))
    return ok(data)


@router.post("/sessions")
async def create_session(
    body: SessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await svc.create_session(db, user.id, body.name, body.description)
    return ok(_session_out(s), message="세션 생성됨", status_code=201)


async def _require_session(db, user, session_id):
    """쓰기·삭제용 — 소유자만. 공개 세션이어도 남이 고치지는 못한다."""
    s = await svc.get_owned_session(db, user.id, session_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
    return s


async def _require_viewable(db, user, session_id):
    """읽기용 — 내 것이거나 공개 범위에 걸리는 세션."""
    s = await svc.get_viewable_session(db, user, session_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
    return s


async def _require_viewable_file(db, user, session_id, file_id):
    f = await svc.get_viewable_file(db, user, session_id, file_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "파일을 찾을 수 없습니다.")
    return f


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await _require_viewable(db, user, session_id)
    files = await svc.list_files(db, session_id)
    return ok(_session_out(s, file_count=len(files), files=[FileRead.model_validate(f).model_dump() for f in files]))


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str,
    body: SessionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await _require_session(db, user, session_id)
    if body.name is not None:
        s.name = body.name
    if body.description is not None:
        s.description = body.description
    if body.status is not None:
        s.status = body.status
    if body.visibility is not None:
        # 이 세션을 조직에 여는 행위 — 소유자만 도달한다(_require_session).
        s.visibility = body.visibility
    # 덱 판 · CAD 연결(DF-15) — 보낸 칸만(null 이면 지운다)
    if "deck_revision_label" in body.model_fields_set:
        s.deck_revision_label = body.deck_revision_label.strip() if body.deck_revision_label else None
    if "linked_cad" in body.model_fields_set:
        s.linked_cad = body.linked_cad.model_dump() if body.linked_cad is not None else None
    await db.commit()
    await db.refresh(s)
    return ok(_session_out(s), message="수정됨")


@router.patch("/sessions/{session_id}/parts/{part_id}")
async def rename_session_part(
    session_id: str,
    part_id: int,
    body: PartRename,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """세션 덱 파일의 *PART 제목을 바꾼다(DF-15) — 그 파일 주 덱에서 「제목 줄 + PID 가 맞는 Card 1」 을 찾아 제목 줄만 고친다(줄 끝 꼴 · 다른
    바이트 그대로 · 제자리). 자리가 없거나(인클루드 안이면 그 파일을 file_id 로) 둘 이상이면 422. 제목은 70 자까지 · 출력 가능한 ASCII ·
    `*` · `$` 로 시작하지 않는다. 파일의 sha256 · 메타의 파트 제목을 고친다. 세션 주인만."""
    import asyncio
    import os

    from app.modules.sessions import part_title as PT
    await _require_session(db, user, session_id)
    if part_id <= 0:
        raise HTTPException(422, "part_id 는 1 이상입니다.")
    f = await svc.get_owned_file(db, user.id, session_id, body.file_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "파일을 찾을 수 없습니다.")
    path = storage.abs_path(f.rel_path)
    data = await asyncio.to_thread(path.read_bytes)
    try:
        new, info = PT.rename(data, part_id, body.title)
    except PT.TitleError as exc:
        raise HTTPException(422, str(exc))
    tmp = path.with_name(path.name + ".kr_tmp_rename")
    await asyncio.to_thread(tmp.write_bytes, new)
    os.replace(tmp, path)
    f.sha256 = await asyncio.to_thread(storage.sha256_of, path)
    f.size_bytes = len(new)
    meta = dict(f.meta or {})
    for holder in (meta, meta.get("modelmeta") if isinstance(meta.get("modelmeta"), dict) else None):
        if holder is None or not isinstance(holder.get("parts"), list):
            continue
        holder["parts"] = [({**p, **{k: body.title for k in ("title", "name") if k in p}}
                            if isinstance(p, dict) and str(p.get("pid", p.get("part_id", p.get("id")))) == str(part_id) else p)
                           for p in holder["parts"]]
    f.meta = meta
    await db.commit()
    return ok({"session_id": session_id, "file_id": f.id, "part_id": part_id, "title": body.title, "old_title": info["old_title"],
               "line_no": info["line_no"], "sha256": f.sha256, "environment": settings.environment},
              message=f"파트 {part_id} 제목 「{info['old_title']}」 → 「{body.title}」(줄 {info['line_no']})")


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await _require_session(db, user, session_id)
    await svc.delete_session(db, s)
    return ok(message="세션이 삭제되었습니다.")


# ── files ───────────────────────────────────────────────────────────
@router.post(
    "/sessions/{session_id}/files",
    dependencies=[Depends(rate_limit("upload", settings.ratelimit_upload_per_min))],
)
async def upload_files(
    session_id: str,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await _require_session(db, user, session_id)
    cap = settings.max_upload_mb * 1024 * 1024
    created = []
    for uf in files:
        # Reject oversized parts BEFORE buffering the whole body into memory,
        # using the part's declared size when available.
        if uf.size is not None and uf.size > cap:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"{uf.filename}: 파일이 너무 큽니다 (최대 {settings.max_upload_mb}MB)",
            )
        raw = await uf.read()
        if len(raw) > cap:  # fallback when size wasn't declared
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"{uf.filename}: 파일이 너무 큽니다 (최대 {settings.max_upload_mb}MB)",
            )
        row = await svc.add_uploaded_file(db, s, filename=uf.filename or "file", raw=raw)
        created.append(FileRead.model_validate(row).model_dump())
    # 인클루드가 빠져 있으면 **여기서** 귀띔한다 — 덱을 고쳐 쓰는 op 은 인클루드 안을 고치지 않아 그대로 성공하고,
    # 깨진 것은 산출물이라 LS-DYNA 에 넣고 나서야 드러난다. 막지는 않는다(순서가 달라 아직 안
    # 올라왔을 수 있다). 자세한 목록은 GET /sessions/{id}/includes, 강제는 잡 생성 때.
    # ⚠ data 는 **리스트 그대로** 둔다 — 프론트·MCP·회귀가 `data[0]` 을 읽는다.
    missing = await svc.include_status(db, session_id)
    msg = f"{len(created)}개 파일 업로드됨"
    if missing:
        n = sum(len(v["missing"]) for v in missing.values())
        msg += f" — ⚠ 참조된 *INCLUDE {n}개가 세션에 없습니다 (GET /sessions/{session_id}/includes)"
    return ok(created, message=msg, status_code=201)


@router.get("/sessions/{session_id}/includes")
async def session_includes(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """이 세션의 덱들이 참조하는 `*INCLUDE` 가 실제로 올라와 있나.

    덱을 고쳐 쓰는 op 은 주 덱만 고치고 **출력 덱에 그 `*INCLUDE` 줄을 보존한다**(분석 op 은 함께 읽는다) —
    그래서 인클루드가 빠져도 그 op 은 성공하고, 산출물을 LS-DYNA 에 넣을 때 깨진다. 실행 전에 이걸로 확인하라."""
    await _require_viewable(db, user, session_id)
    st = await svc.include_status(db, session_id)
    return ok({"ok": not st, "missing_by_file": st})


@router.get("/sessions/{session_id}/files")
async def list_files(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_viewable(db, user, session_id)
    files = await svc.list_files(db, session_id)
    return ok([FileRead.model_validate(f).model_dump() for f in files])


@router.get("/sessions/{session_id}/files/{file_id}")
async def get_file(
    session_id: str,
    file_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    f = await svc.get_viewable_file(db, user, session_id, file_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "파일을 찾을 수 없습니다.")
    return ok(FileRead.model_validate(f).model_dump())


@router.get("/sessions/{session_id}/files/{file_id}/inspect")
async def inspect_file(
    session_id: str,
    file_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cached metadata (nodes/elements/parts/bbox/*INCLUDE/keywords/modelmeta)."""
    f = await svc.get_viewable_file(db, user, session_id, file_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "파일을 찾을 수 없습니다.")
    # sha256 은 파일 행의 것(덱 판을 가리는 지문 — 리스크 앱 RK-06 이 여기서 찾는다, 2026-11-17)
    return ok({"filename": f.filename, "sha256": f.sha256, "meta": f.meta or {}})


@router.post(
    "/sessions/{session_id}/files/{file_id}/connectivity",
    dependencies=[Depends(rate_limit("connectivity", settings.ratelimit_upload_per_min))],
)
async def file_connectivity(
    session_id: str,
    file_id: int,
    detect: bool = True,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """온디맨드 connectivity 재추출 — detect=true 면 기하 접촉쌍 탐지(무거움).

    *CONTACT 가 SINGLE_SURFACE(자기접촉)라 카드만으로 파트쌍이 안 나오는 모델에서
    실제 '어떤 파트가 어디에 닿나'를 기하 탐지로 뽑는다. 결과는 file.meta 에 저장.
    """
    f = await svc.get_owned_file(db, user.id, session_id, file_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "파일을 찾을 수 없습니다.")
    mm = await svc.run_file_connectivity(db, f, detect=detect)
    return ok(mm, message="connectivity 추출 완료")


@router.get("/sessions/{session_id}/files/{file_id}/download")
async def download_file(
    session_id: str,
    file_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    f = await svc.get_viewable_file(db, user, session_id, file_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "파일을 찾을 수 없습니다.")
    path = storage.abs_path(f.rel_path)
    if not path.exists():
        raise HTTPException(status.HTTP_410_GONE, "파일 실물이 없습니다.")
    return FileResponse(path, filename=f.filename, media_type="application/octet-stream")


@router.delete("/sessions/{session_id}/files/{file_id}")
async def delete_file(
    session_id: str,
    file_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    f = await svc.get_owned_file(db, user.id, session_id, file_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "파일을 찾을 수 없습니다.")
    await svc.delete_file(db, f)
    return ok(message="파일이 삭제되었습니다.")
