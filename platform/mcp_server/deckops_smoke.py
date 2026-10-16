# 덱을 **쓰는** 새 op 들을 살아 있는 플랫폼에서 끝까지 부르는 스모크 — 게시본이 낡으면 빨개진다
"""KooRemapper 덱 op 스모크 (2026-10-11).

왜 이것이 따로 있나.

  `figures_smoke.py` 와 **같은 사고**를 덱 op 쪽에서 막는다. 2026-10-02 에 새 op 셋을 만들고
  검증을 `build/dev` 바이너리 직접 실행으로 했는데, 플랫폼이 쓰는
  `platform/backend/bin/KooRemapper` 는 게시 아티팩트라 **git 으로 가지 않아** 옛 바이너리가
  그대로 있었다. 체크리스트는 34/34 초록이었고 op 은 플랫폼에서 하나도 돌지 않았다.
  2026-10-10 에는 **재부팅**이 그 슬롯을 게시본으로 되돌려 같은 상태를 다시 만들었다.

  그림 op 은 `figures_smoke.py` 가 지킨다. 덱을 쓰는 op 은 지키는 것이 없었다 — 이 파일이
  그 자리다. 통과하려면 **바이너리·카탈로그·API·MCP 프로세스가 모두 최신**이어야 한다.

  판정은 "잡이 succeeded 이고 산출물이 왔나" 다 — op 의 내용은 각 op 의 회귀가 본다.
  여기서 보는 것은 **플랫폼이 그 op 을 아는가** 뿐이다.

  `smoke.py` 와 같은 전제(api+mcp+postgres 가 떠 있어야 한다)이고, 닿지 않으면 **건너뛴다**(rc=0).

새 덱 op 을 만들면 `CASES` 에 한 줄 더한다. 예제 폴더의 덱을 그대로 올린다.

실행:
    mcp_server/venv/bin/python mcp_server/deckops_smoke.py
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import smoke as S
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

REPO = Path(__file__).resolve().parents[2]

# (op, 주 입력 덱, 함께 올릴 파일들, args) — `model` 은 주 덱의 파일명으로 자동 채운다
# (args 가 주 덱을 이미 다른 키로 가리키면 채우지 않는다).
CASES = [
    ("cleanup-nodes",
     REPO / "examples" / "cleanup-nodes" / "cleanup_demo.k", [],
     {"mode": "safe", "output": "clean.k", "report": "cleanup_report.json"}),
    ("extract-parts",
     REPO / "examples" / "extract-parts" / "assembly.k",
     [REPO / "examples" / "extract-parts" / "part2_include.k"],
     {"output": "extracted.k", "parts": [1, 2], "report": "extract_report.json"}),
    # 삽입 흐름 — 바닥을 내고(id_floor 는 덱 대신 JSON 을 쓴다) StepForge 조각을 넣는다
    ("id_floor",
     REPO / "examples" / "cad_solid_merge_to_deck" / "deck.k",
     [REPO / "examples" / "cad_solid_merge_to_deck" / "stepforge_fragment.json"],
     {"output": "floor.json", "fragment_map": "stepforge_fragment.json"}),
    ("cad_solid_merge_to_deck",
     REPO / "examples" / "cad_solid_merge_to_deck" / "deck.k",
     [REPO / "examples" / "cad_solid_merge_to_deck" / f for f in ("stepforge_fragment.k", "stepforge_fragment.json")],
     {"output": "merged.k", "fragment": "stepforge_fragment.k", "fragment_map": "stepforge_fragment.json"}),
    ("rebind_entities_after_remesh",
     REPO / "examples" / "rebind_entities_after_remesh" / "ours.k",
     [REPO / "examples" / "rebind_entities_after_remesh" / f for f in ("v1.k", "v2.k", "range_diff.json")],
     {"old_deck": "v1.k", "new_deck": "v2.k", "entities": "ours.k", "output": "ours_rebound.k",
      "range_diff": "range_diff.json"}),
]

OK = []


def chk(name, cond, detail=""):
    print("  %-56s %s" % (name, "OK" if cond else "FAIL"))
    OK.append(bool(cond))
    if not cond and detail:
        print("      %s" % str(detail)[:400])


async def main():
    missing = [str(d) for _, d, _, _ in CASES if not d.exists()]
    if missing:
        print("FAIL: 예제 덱이 없다 — " + ", ".join(missing))
        return 1
    pat, tid = S._mint_token()
    if not pat:
        print("SKIP: API 에 닿지 않거나 토큰을 발급할 수 없다 (스택이 떠 있어야 한다)")
        return 0
    try:
        async with streamablehttp_client(S.MCP_URL,
                                         headers={"Authorization": f"Bearer {pat}"}) as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = {t.name for t in (await s.list_tools()).tools}
                chk("run_operation 도구가 있다", "run_operation" in tools)
                for op, deck, extra, args in CASES:
                    sess = S._data(await s.call_tool("create_session", {"name": f"deckop_{op}"}))
                    sid = sess.get("id") if isinstance(sess, dict) else None
                    chk(f"{op}: 세션 생성", bool(sid), sess)
                    if not sid:
                        continue
                    for p in [deck] + list(extra):
                        S._data(await s.call_tool("upload_local_path",
                                                  {"session_id": sid, "path": str(p)}))
                    a = dict(args)
                    # 구조화 op 은 모르는 키를 거절한다 — `rebind_entities_after_remesh` 에는 `model` 이 없다
                    if os.path.basename(str(deck)) not in a.values():
                        a["model"] = os.path.basename(str(deck))
                    job = S._data(await s.call_tool("run_operation",
                                                    {"session_id": sid, "operation": op, "args": a}))
                    jid = job.get("id") if isinstance(job, dict) else None
                    chk(f"{op}: 잡이 생겼다 (플랫폼이 이 op 을 안다)", bool(jid), job)
                    st, last = None, None
                    for _ in range(60):
                        j = S._data(await s.call_tool("get_job", {"job_id": jid}))
                        last = j
                        st = j.get("status") if isinstance(j, dict) else str(j)
                        if st in ("succeeded", "failed"):
                            break
                        await asyncio.sleep(1)
                    chk(f"{op}: succeeded (exit 0)", st == "succeeded", last)
                    outs = await s.call_tool("get_job_outputs", {"job_id": jid})
                    chk(f"{op}: 산출물이 왔다", len(outs.content) >= 1, len(outs.content))
                    await s.call_tool("delete_session", {"session_id": sid})
    finally:
        if tid:
            S._revoke_token(tid)
    bad = OK.count(False)
    print("\n=== 덱 op 플랫폼 전수: %s (%d/%d) ===" %
          ("PASS" if bad == 0 else "FAIL", len(OK) - bad, len(OK)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
