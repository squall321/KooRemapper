# SP 키트 2026-11-06 시험장(가짜 SP 8단계)으로 받기(층 1)를 채점한다 — 지시서 완료 조건 3 · 7
"""SP `backend/app/modules/coreapi/kit/01-AI-GUIDE.md`@ab41cff §8 — 「시험장 8단계를 도는 자동 시험을 이 저장소의
시험에 넣었다」 가 완료 조건이다. 시험장은 실제 SP 에서 일부러 만들 수 없는 상황(식별자 두 번 바뀜 · 합치기 · 안 보이게
됨 · 오래 안 받음 · 커서 오류 · 정의 판 바뀜 · 공개 거둠 · 범위 줄어듦)을 겪게 하는 유일한 자리다.

가짜 SP(`testbed/fake_sp.py`)는 서브모듈에서 **하위 프로세스로** 띄운다 — 런타임은 서브모듈을 import 하지 않는다
(`test_external_boundary.py`). 단계마다 `POST /_step` → 받기 → 사본(층 1)을 채점기 꼴로 내보내기 → `compare.py`
끝값 0 · 결과 상태가 `expect_status` 와 같은지 본다. 한 트랜잭션 안에서 돌리고 끝에 되돌린다 — 떠 있는 dev DB 에
시험장 객체가 남지 않는다.

§8.1 선 확인표(키트 2026-11-03)는 이 플랫폼의 말로 옮긴다. DynaForge 는 받은 선을 우리 연결 표로 옮기지 않고 보기
(온톨로지 화면 · API · MCP)에서 읽기 전용으로 보인다 — 그래서 선의 상태는 채점기가 보는 사본 그대로이고, 층 2 가 지켜야
할 것은 둘이다. ① **사람이 이은 연결**(우리 선, 출처 `dynaforge`)은 SP 에 없어도 어느 단계에서도 끊기거나 바뀌지 않는다.
② 끝이 인터페이스인 선은 보기가 **도착 타입**으로 끝을 찾는다 — 같은 key(K-1)가 공급사 · 공장 두 표에 있다(§9).
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import SOURCE_HUB, SOURCE_SELF, OntoObject, OntoRelation
from app.modules.ontology import routes as onto_routes
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


async def _browse(db, type_slug: str, key: str) -> dict:
    """보기 API(객체 하나)가 내는 것 — 화면 · MCP 가 같은 길을 읽는다."""
    db.expire_all()                         # 수신부는 Core 문으로 고친다 — 보기가 읽을 객체를 새로 채운다
    res = await onto_routes.ontology_object(type_slug=type_slug, key=key, _user=None, db=db)
    return json.loads(res.body)["data"]


async def _interface_ends(db, step: int) -> list[str]:
    """§8.1 6단계 — 검사처 P-1X→K-1 이 공급사 쪽 · 공장 쪽 레코드에 하나씩. 들어온 선도 그 타입의 것만."""
    bad: list[str] = []
    out = sorted((e["type"], e["key"], e["label"]) for e in (await _browse(db, "part", "P-1X"))["out"]
                 if e["relation"] == "inspected_by")
    want = [("plant", "K-1", "구미 검사동"), ("vendor", "K-1", "공용검사소")]
    if out != want:
        bad.append(f"{step}단계 — P-1X 의 검사처가 {out}(기대 {want})")
    for t in ("vendor", "plant"):
        inc = [(e["type"], e["key"]) for e in (await _browse(db, t, "K-1"))["in"] if e["relation"] == "inspected_by"]
        if inc != [("part", "P-1X")]:
            bad.append(f"{step}단계 — {t} K-1 에 들어온 검사처가 {inc}(기대 P-1X 하나 — 다른 타입의 K-1 선이 섞이면 안 된다)")
    return bad


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
        # §8.1 — 사람이 이은 연결 하나(SP 에 없는 P-2–V-4). 받기는 허브 선만 끊고 정리한다.
        human = OntoRelation(relation="supplied_by", src_type="part", src_key="P-2", dst_type="vendor", dst_key="V-4",
                             source=SOURCE_SELF, properties={"note": "사람이 이음"}, deleted=False)
        db.add(human)
        await db.flush()
        human_id = human.id
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
            mine = (await db.execute(select(OntoRelation).where(OntoRelation.id == human_id)
                                     .execution_options(populate_existing=True))).scalar_one_or_none()
            if mine is None or mine.deleted or mine.source != SOURCE_SELF or mine.properties != {"note": "사람이 이음"}:
                failures.append(f"{info['step']}단계 — 사람이 이은 연결 P-2–V-4 를 받기가 끊거나 바꿨다"
                                f"({None if mine is None else (mine.deleted, mine.source, mine.properties)})")
            if info["step"] in (6, 8):         # 8단계는 정리를 멈췄으니 6단계 뒤와 같아야 한다
                failures += await _interface_ends(db, info["step"])
        shown = [(e["type"], e["key"], e["source"]) for e in (await _browse(db, "part", "P-2"))["out"]
                 if e["relation"] == "supplied_by"]
        if ("vendor", "V-4", SOURCE_SELF) not in shown:
            failures.append(f"보기에 사람이 이은 연결이 안 보인다 — P-2 의 공급처 {shown}")
        assert not failures, "\n\n".join(failures)
    finally:
        await db.rollback()
        srv.terminate()
        srv.wait(timeout=10)
        if client is not None:
            await client.close()
