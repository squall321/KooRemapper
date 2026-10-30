# SP 키트 2026-10-21 시험장(가짜 SP 8단계)으로 받기(층 1)를 채점한다 — 지시서 완료 조건 3 · 7
"""SP `backend/app/modules/coreapi/kit/01-AI-GUIDE.md`@778db2f §8 — 「시험장 8단계를 도는 자동 시험을 이 저장소의
시험에 넣었다」 가 완료 조건이다. 시험장은 실제 SP 에서 일부러 만들 수 없는 상황(식별자 두 번 바뀜 · 합치기 · 안 보이게
됨 · 오래 안 받음 · 커서 오류 · 정의 판 바뀜 · 공개 거둠 · 범위 줄어듦)을 겪게 하는 유일한 자리다.

가짜 SP(`testbed/fake_sp.py`)는 서브모듈에서 **하위 프로세스로** 띄운다 — 런타임은 서브모듈을 import 하지 않는다
(`test_external_boundary.py`). 단계마다 `POST /_step` → 받기 → 사본(층 1)을 채점기 꼴로 내보내기 → `compare.py`
끝값 0 · 결과 상태가 `expect_status` 와 같은지 본다. 한 트랜잭션 안에서 돌리고 끝에 되돌린다 — 떠 있는 dev DB 에
시험장 객체가 남지 않는다.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import SOURCE_HUB, OntoObject, OntoRelation
from app.runner import sp_core

_aio = pytest.mark.asyncio(loop_scope="session")
ROOT = Path(__file__).resolve().parents[3]
KIT = ROOT / "external" / "StandardPlatform" / "backend" / "app" / "modules" / "coreapi" / "kit"
pytestmark = [pytest.mark.skipif(not (KIT / "testbed" / "fake_sp.py").exists(),
                                 reason="SP 시험장 없음(서브모듈 778db2f 이후)")]
EXPECT = {"정상": "ok", "확인 필요": "needs_check"}


def _post(url: str) -> dict:
    req = urllib.request.Request(url, method="POST", data=b"")
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read())


async def _dump(db, types: set[str]) -> dict:
    """사본(층 1)을 채점기 꼴로 — 객체는 비활성까지 전부, 선은 지금 이어진 허브 선만."""
    fresh = {"populate_existing": True}     # 수신부는 Core 문으로 고친다 — 앞서 읽은 ORM 객체를 새로 채운다
    objs = (await db.execute(select(OntoObject).where(
        OntoObject.type_slug.in_(types), OntoObject.source == SOURCE_HUB).execution_options(**fresh))).scalars().all()
    rels = (await db.execute(select(OntoRelation).where(
        OntoRelation.src_type.in_(types), OntoRelation.source == SOURCE_HUB, OntoRelation.deleted.is_(False))
        .execution_options(**fresh))).scalars().all()
    return {"objects": [{"type": o.type_slug, "key": o.key, "label": o.label, "status": o.status,
                         "active": not o.deleted, "properties": o.properties or {}} for o in objs],
            "relations": [{"src_type": r.src_type, "src": r.src_key, "relation": r.relation,
                           "dst": r.dst_key, "dst_type": r.dst_type} for r in rels]}


@_aio
async def test_the_receiver_passes_all_eight_testbed_steps(db, tmp_path):
    srv = subprocess.Popen([sys.executable, "-I", "-B", str(KIT / "testbed" / "fake_sp.py"), "--port", "0", "--quiet"],
                           stdout=subprocess.PIPE, text=True, cwd=str(tmp_path))
    client = None
    try:
        port = int(srv.stdout.readline().strip().split("=")[1])
        base = f"http://127.0.0.1:{port}"
        client = sp_core.SpCoreClient(base + "/api", "test-token", retry_waits=(0.0, 0.0))
        types: set[str] = set()
        failures: list[str] = []
        for _ in range(8):
            info = _post(base + "/_step")
            got = await sp_core.sync_all(db, client, full=info.get("run") == "처음부터")
            types.update(got.get("opened") or [])
            dump = tmp_path / f"state_{info['step']}.json"
            dump.write_text(json.dumps(await _dump(db, types), ensure_ascii=False))
            graded = subprocess.run([sys.executable, "-I", "-B", str(KIT / "testbed" / "compare.py"),
                                     "--dump", str(dump), "--server", base], capture_output=True, text=True)
            want = EXPECT.get(info.get("expect_status"), info.get("expect_status"))
            if graded.returncode != 0 or got.get("result") != want:
                failures.append(f"{info['step']}단계 {info.get('title')} — 결과 {got.get('result')}(기대 {want}) · "
                                f"사유 {got.get('problems')} · 채점 끝값 {graded.returncode}\n"
                                + (graded.stdout + graded.stderr)[-1500:])
        assert not failures, "\n\n".join(failures)
    finally:
        await db.rollback()
        srv.terminate()
        srv.wait(timeout=10)
        if client is not None:
            await client.close()
