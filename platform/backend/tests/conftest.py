"""Pytest fixtures for DB-integration tests.

These run against the live dev postgres (KOORM_DATABASE_URL, default the
Apptainer instance on :5436). Each test creates uniquely-named rows and cleans
them up, so they don't disturb existing data. Skipped automatically if the DB
is unreachable.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import pytest_asyncio
import ulid

from app.database import SessionLocal, engine


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture()
def own_sync_lock(monkeypatch):
    """받기 잠금(`plm_sync.LOCK_NAME`)을 시험마다 제 이름으로 둔다.

    잠금은 DB 하나에 하나다 — 진짜 이름을 쓰면 같은 dev DB 에서 도는 다른 시험 · 반입 · 워커가 그 잠금을 쥔 순간 「busy」 로
    빨개진다(재검토 11-14 F-17 — 잠금을 쥔 채 돌리니 스무 개가 빨갰다). 잠금을 쓰는 길은 모두 `plm_sync.try_lock` 을 부르고
    그 함수는 부를 때 이름을 읽으므로, 이름만 바꾸면 이 프로세스 안의 라우트 · 받기 · 잇기가 같은 새 잠금을 쓴다.
    ★**진짜 받기(`sync_all`)를 돌리지 않는** 시험만 쓴다. 진짜 받기는 카탈로그를 갈아 끼우므로 두 실행이 섞이면 안 된다 —
    `test_plm_sync` 는 진짜 잠금을 그대로 쓴다(그쪽은 잠금이 잡혀 있으면 빨간 것이 맞다).
    """
    from app.worker import plm_sync
    monkeypatch.setattr(plm_sync, "LOCK_NAME", f"{plm_sync.LOCK_NAME}.test.{ulid.new().str.lower()}")


@pytest_asyncio.fixture(loop_scope="session")
async def db():
    # skip the whole module if the DB isn't up
    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"DB unavailable: {exc}")
    async with SessionLocal() as session:
        yield session
