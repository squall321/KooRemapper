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

from app.database import SessionLocal, engine


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


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
