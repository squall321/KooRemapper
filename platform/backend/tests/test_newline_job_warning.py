# 실제 잡을 돌려 개행 왕복 경고가 잡 기록에 남나 — 러너 연결(P1-8)을 끝까지 확인한다
"""`newline_audit` 의 규칙은 tests/test_newline_audit.py 가 순수 함수로 지킨다. 여기서는
**연결**을 본다 — 잡 실행 전 메타를 제대로 떴나, 산출물 메타를 제대로 읽었나, `job.warnings`
에 남았나. 실 DB + 실 바이너리로 `_execute` 를 직접 돌린다.

⚠ 양성 시험이 왜 메타를 손으로 바꿔 놓나 — **이제 개행을 뒤집는 op 이 없다**(afbc154·e841e5a
에서 12곳을 고쳤다). 그래서 진짜 뒤집기를 만들 수가 없다. 그렇다고 연결을 안 보면, 다음에
누가 개행을 다시 잃게 만들었을 때 **보고 경로가 죽어 있는 것을 아무도 모른다.** 그래서 DB 의
'왕복 전' 기록만 LF 로 바꿔 두고, 산출물(CRLF)과의 차이가 실제로 경고로 나오는지 본다.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ulid
from sqlalchemy import delete

from app.models import Job, Session, SessionFile, User
from app.modules.sessions import services as svc
from app.shared import security, storage
from app.worker.runner_loop import _execute

_aio = pytest.mark.asyncio(loop_scope="session")

# CRLF 덱. `database` op 은 *END 앞에 *DATABASE 카드를 끼워 새 덱을 낸다.
_DECK_CRLF = (
    "*KEYWORD\r\n"
    "*NODE\r\n"
    "         1             0.0             0.0             0.0\r\n"
    "         2            10.0             0.0             0.0\r\n"
    "*END\r\n"
).encode("latin-1")

_DB_ARGS = {"config": {"model": "model.k", "output": "model_db.k",
                       "preset": "all", "dt": 0.001, "dt_plot": 0.01}}


async def _mk(db):
    u = User(email=f"nlw_{ulid.new().str}@kooremapper.test",
             password_hash=security.hash_password("x"), is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    sid = ulid.new().str
    s = Session(id=sid, user_id=u.id, name="nl-warn",
                storage_path=storage.session_rel_dir(u.id, sid))
    db.add(s)
    await db.commit()
    await db.refresh(s)
    storage.ensure_session_dir(u.id, sid)
    return u, s


@pytest.fixture
async def sess(db):
    u, s = await _mk(db)
    try:
        yield u, s
    finally:
        await db.execute(delete(Job).where(Job.session_id == s.id))
        await db.execute(delete(SessionFile).where(SessionFile.session_id == s.id))
        await db.execute(delete(Session).where(Session.id == s.id))
        await db.execute(delete(User).where(User.id == u.id))
        await db.commit()
        d = storage.session_abs_dir(u.id, s.id)
        if d.exists():
            import shutil
            shutil.rmtree(d, ignore_errors=True)


async def _run(db, u, s, *, doctor_input_to_lf: bool):
    row = await svc.add_uploaded_file(db, s, filename="model.k", raw=_DECK_CRLF)
    assert (row.meta or {}).get("newline") == "crlf", f"업로드 메타가 CRLF 가 아니다 — {row.meta}"
    if doctor_input_to_lf:
        # 이 잡이 보게 될 '왕복 전' 기록만 LF 로 바꾼다(디스크는 그대로 CRLF 다).
        row.meta = {**row.meta, "newline": "lf", "n_crlf": 0}
        await db.commit()
    job = Job(id=ulid.new().str, session_id=s.id, user_id=u.id,
              operation="database", args=_DB_ARGS, status="queued")
    db.add(job)
    await db.commit()
    await _execute(job.id)
    await db.refresh(job)
    return job


@_aio
async def test_a_clean_crlf_job_gets_no_warning(db, sess):
    """행복한 길에 경고가 뜨면 실사용 잡마다 뜬다 — 오탐이 없어야 이 경고를 믿을 수 있다."""
    u, s = sess
    job = await _run(db, u, s, doctor_input_to_lf=False)
    assert job.status == "succeeded", f"{job.status} / {job.error_summary}"
    assert not job.warnings, f"멀쩡한 왕복에 경고가 떴다 — {job.warnings}"
    out = storage.session_abs_dir(u.id, s.id) / "model_db.k"
    raw = out.read_bytes()
    lone = raw.count(b"\n") - raw.count(b"\r\n")
    assert raw.count(b"\r\n") > 0 and lone == 0, f"산출 덱이 CRLF 가 아니다 — 단독 LF {lone}"


@_aio
async def test_a_newline_change_reaches_the_job_record(db, sess):
    """보고 경로가 살아 있나 — 왕복 전 기록이 LF 인데 산출 덱이 CRLF 면 잡에 경고가 남는다."""
    u, s = sess
    job = await _run(db, u, s, doctor_input_to_lf=True)
    assert job.status == "succeeded", f"{job.status} / {job.error_summary}"
    assert job.warnings, "개행이 달라졌는데 잡 기록에 아무 말도 없다 — 보고 경로가 죽었다"
    joined = " ".join(job.warnings)
    assert "model_db.k" in joined, joined
    assert "LF" in joined and "CRLF" in joined, joined
