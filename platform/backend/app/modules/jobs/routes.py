from __future__ import annotations

from pathlib import Path

import ulid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Job, SessionFile, User
from app.modules.jobs.schemas import JobCreate, JobRead
from app.modules.sessions.services import get_owned_session
from app.runner import catalog
from app.shared.auth import get_current_user
from app.shared.responses import ok
from app.worker.runner_loop import request_cancel

router = APIRouter(tags=["jobs"])


async def _require_session(db, user, session_id):
    s = await get_owned_session(db, user.id, session_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
    return s


async def _require_job(db, user, job_id) -> Job:
    job = await db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "작업을 찾을 수 없습니다.")
    return job


@router.post("/sessions/{session_id}/jobs")
async def create_job(
    session_id: str,
    body: JobCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_session(db, user, session_id)
    entry = catalog.get_operation(body.operation)
    if entry is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"알 수 없는 오퍼레이션: {body.operation}")
    errs = catalog.validate_args(body.operation, body.args)
    if errs:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "인자 검증 실패: " + "; ".join(errs))

    # gmsh 가 필요한 op 은 **큐에 넣기 전에** 확인한다(P1-9). 예전에는 그냥 넣었고, 잡이 한참
    # 돌다 `Gmsh failed (exit 32512)` 로 죽었다 — 사람은 자기 덱이 잘못된 줄 안다.
    # ⚠ 파일이 있다고 gmsh 인 것은 아니다. 탐지기가 `--version` 을 실제로 돌린다.
    if entry.get("requires_gmsh"):
        from app.config import settings as _settings
        from app.runner.gmsh_probe import probe as _gmsh_probe

        g = _gmsh_probe(_settings.kooremapper_bin)
        if not g["available"]:
            detail = ("이 오퍼레이션(%s)은 gmsh 가 필요한데 이 서버에서 gmsh 를 실행할 수 없습니다."
                      % body.operation)
            if g["rejected"]:
                detail += " 건너뛴 후보: " + "; ".join(g["rejected"])
            detail += (" — 서버에 gmsh 를 설치하고 KOOREMAPPER_GMSH 를 가리키거나, "
                       "바이너리 옆 bin/gmsh/ 에 두세요.")
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail)

    # Pre-check that file-typed args reference files that exist in the session,
    # so the user gets a clear error instead of a worker failure later.
    from app.modules.sessions.services import list_files

    names = {f.filename for f in await list_files(db, session_id)}
    missing = [
        f"{p['name']}={body.args[p['name']]}"
        for p in entry.get("params", [])
        if p.get("type") == "file" and body.args.get(p["name"]) and body.args[p["name"]] not in names
    ]
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "세션에 없는 입력 파일: " + ", ".join(missing) + " (먼저 업로드하세요)",
        )

    # 참조된 `*INCLUDE` 가 세션에 있는지 — **여기서 막지 않으면 아무도 못 막는다.**
    # KooRemapper 는 인클루드를 읽지 않으므로 op 은 그대로 성공하고, 산출물에는 그 `*INCLUDE` 줄이
    # 보존된다(실측). 깨진 덱은 LS-DYNA 에 넣고 나서야 드러나고, 그때는 해석 시간을 이미 썼다.
    # 다만 인클루드를 클러스터에 따로 두는 운용도 있으므로 `allow_missing_includes` 로 넘어갈 수 있다.
    if not body.allow_missing_includes:
        from app.modules.sessions.services import include_status

        inc = await include_status(db, session_id)
        used = {body.args.get(p["name"]) for p in entry.get("params", []) if p.get("type") == "file"}
        hit = {k: v for k, v in inc.items() if k in used} or inc
        if hit:
            detail = "; ".join(f"{k} → {', '.join(v['missing'])}" for k, v in hit.items())
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "덱이 참조하는 *INCLUDE 가 세션에 없습니다: " + detail
                + " — 그 파일도 올리세요(하위 폴더면 경로째로). "
                  "클러스터에 따로 두는 운용이면 allow_missing_includes=true 로 넘어갈 수 있습니다.",
            )
    # 덱이 정의되지 않은 것을 가리키면 LS-DYNA 가 **키워드 단계에서** 죽는다 — 해석 시간을
    # 쓰기도 전에다. `info` 는 그것을 보고만 하고 rc=0 으로 끝내므로(그 rc 는 계약이다) 막는
    # 자리는 여기다. 실측: 추적 덱 489장 중 40장이 이 부류이고 40장 전부 rc=0 으로 나갔다.
    # 위 인클루드 게이트와 **같은 패턴**이다. 단정 등급만 막는다 — `*INCLUDE` 를 못 읽었으면
    # 그 안에 정의됐을 수 있어 단정하면 오탐이고, 오탐 한 번에 사람은 게이트를 통째로 끈다.
    dangling_warnings: list[str] = []
    from app.modules.sessions.services import dangling_status

    dang = await dangling_status(db, session_id)
    used = {body.args.get(p["name"]) for p in entry.get("params", []) if p.get("type") == "file"}
    # ⚠ **`or dang` 폴백을 쓰지 않는다.** 위 인클루드 게이트에는 그 폴백이 있는데(빠진 인클루드는
    # 세션 어디에 있어도 산출물을 깨뜨리므로 그쪽은 맞다) 이 축에서는 반대다 — 이 잡이 **쓰지도
    # 않는 덱** 때문에 경고가 붙는다. 실사용 실측(2026-09-27): 막힌 덱이 1장이라도 있는 study
    # 폴더가 51/230 이고 그 폴더의 덱 총수는 **515/938** 이다. 폴더 하나를 세션 하나로 올리는
    # 정상 운용에서 개별로 걸리는 147장의 **3.5배**가 함께 물든다.
    hit = {k: v for k, v in dang.items() if k in used}
    if hit:
        detail = "; ".join(
            f"{k} → {v['count']}건"
            + (f"(망가진 카드 {v['damaged']}건 포함)" if v.get("damaged") else "")
            + (" · " + ", ".join(f"line {i['line']} {i['keyword']}" for i in v["top"][:3]) if v.get("top") else "")
            for k, v in hit.items()
        )
        msg = ("덱이 정의되지 않은 것을 가리킵니다: " + detail
               + " — LS-DYNA 가 키워드 단계에서 멈춥니다. "
                 "`KooRemapper info <덱> --strict` 로 전부 볼 수 있습니다.")
        if body.allow_dangling_refs:
            # 기본 경로 — 막지 않는다. 다만 **조용히 지나가지도 않는다.** P1-8 의 개행 경고와
            # 같은 자리(`job.warnings`)에 남겨 화면에서 보이게 한다.
            dangling_warnings.append(msg)
        else:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, msg)
    job = Job(
        id=ulid.new().str,
        session_id=session_id,
        user_id=user.id,
        operation=body.operation,
        args=body.args,
        status="queued",
        warnings=dangling_warnings or None,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return ok(JobRead.model_validate(job).model_dump(), message="작업이 큐에 등록되었습니다.", status_code=201)


@router.get("/sessions/{session_id}/jobs")
async def list_session_jobs(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_session(db, user, session_id)
    rows = (
        await db.execute(
            select(Job)
            .where(Job.session_id == session_id)
            .order_by(Job.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars()
    return ok([JobRead.model_validate(j).model_dump() for j in rows])


import re

_PCT = re.compile(r"(\d{1,3})\s*%")


def _live_progress(stdout_path: str | None) -> int | None:
    """Parse the most recent NN% marker from a running job's stdout."""
    if not stdout_path:
        return None
    try:
        with open(stdout_path, "rb") as fh:
            try:
                fh.seek(-4096, 2)
            except OSError:
                fh.seek(0)
            tail = fh.read().decode("utf-8", "ignore")
    except OSError:
        return None
    matches = _PCT.findall(tail)
    if not matches:
        return None
    return min(100, int(matches[-1]))


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _require_job(db, user, job_id)
    data = JobRead.model_validate(job).model_dump()
    if job.status == "running" and data.get("progress") is None:
        data["progress"] = _live_progress(job.stdout_path)
    return ok(data)


@router.get("/jobs/{job_id}/logs", response_class=PlainTextResponse)
async def get_job_logs(
    job_id: str,
    which: str = Query("both", pattern="^(stdout|stderr|both)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _require_job(db, user, job_id)

    def _read(path: str | None) -> str:
        if not path:
            return ""
        # defense in depth: only read log files inside the storage dir
        from app.config import settings as _s

        try:
            rp = Path(path).resolve()
            root = _s.storage_dir.resolve()
            if root not in rp.parents:
                return ""
            with open(rp, encoding="utf-8", errors="ignore") as fh:
                return fh.read()
        except OSError:
            return ""

    if which == "stdout":
        return _read(job.stdout_path)
    if which == "stderr":
        return _read(job.stderr_path)
    return f"===== STDOUT =====\n{_read(job.stdout_path)}\n===== STDERR =====\n{_read(job.stderr_path)}"


@router.get("/jobs/{job_id}/outputs")
async def get_job_outputs(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _require_job(db, user, job_id)
    if not job.output_file_ids:
        return ok([])
    rows = (
        await db.execute(select(SessionFile).where(SessionFile.id.in_(job.output_file_ids)))
    ).scalars()
    from app.modules.sessions.schemas import FileRead

    return ok([FileRead.model_validate(f).model_dump() for f in rows])


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _require_job(db, user, job_id)
    if job.status not in ("queued", "running"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"취소할 수 없는 상태입니다: {job.status}")
    # ⚠ 외부 잡은 **여기서 취소할 수 없다.** request_cancel 은 이 프로세스의 자식을
    #    죽이는 것인데, 그 잡은 다른 클러스터에서 돈다. 그대로 두면 "취소됨" 이라고
    #    답해 놓고 잡은 계속 도는 — 성공처럼 생긴 실패가 된다. 명시적으로 거절한다.
    if job.status == "running" and job.external_kind:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            f"외부 잡({job.external_kind})은 여기서 취소할 수 없습니다 — 제출한 클러스터에서 취소하세요.",
        )
    request_cancel(job_id)
    return ok(message="취소 요청됨")
