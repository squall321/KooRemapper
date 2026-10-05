# 세 그림 MCP 도구를 **살아 있는 플랫폼**에서 끝까지 부르는 스모크 — 이전 검증이 빠뜨린 자리
"""KooRemapper 그림 MCP 스모크 (2026-10-05).

왜 이것이 따로 있나.

  `mesh_section_figure`·`mesh_surface_figure`·`mesh_stack_diagram` 을 만들고 나서 검증을
  **카탈로그 `build_command` + `build/dev` 바이너리 직접 실행**으로 했다. 그 경로는 통과했는데
  **플랫폼은 세 op 을 몰랐다** — `platform/backend/bin/KooRemapper` 가 10-02 게시본이었고
  세 op 은 10-03~04 커밋이다. MCP 로 부르면 잡이 `Unknown command` 로 rc=1 이 되고, `.svg` 가
  애초에 생기지 않아 프런트 '그림 보기' 버튼도 뜨지 않았다. 체크리스트는 34/34 초록이었다.

  그래서 이 스모크는 **오직 살아 있는 스택을 거쳐서만** 판정한다. 통과하려면
  바이너리·카탈로그·MCP 프로세스 셋이 모두 최신이어야 한다 — 그 셋 중 하나만 낡아도 빨개진다.

  `smoke.py` 와 같은 전제(api+mcp+postgres 가 떠 있어야 한다)이고, 닿지 않으면 **건너뛴다**(rc=0).

실행:
    mcp_server/venv/bin/python mcp_server/figures_smoke.py
"""
import asyncio
import sys
from pathlib import Path

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import smoke as S
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

REPO = Path(__file__).resolve().parents[2]
DECK = str(REPO / "examples" / "stackwrap" / "flat_stack.k")
OK = []

def chk(name, cond, detail=""):
    print("  %-56s %s" % (name, "OK" if cond else "FAIL"))
    OK.append(bool(cond))
    if not cond and detail:
        print("      %s" % str(detail)[:400])

async def main():
    pat, tid = S._mint_token()
    if not pat:
        print("SKIP: API 에 닿지 않거나 토큰을 발급할 수 없다 (스택이 떠 있어야 한다)")
        return 0
    try:
        async with streamablehttp_client(S.MCP_URL, headers={"Authorization": f"Bearer {pat}"}) as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
                names = {t.name for t in (await s.list_tools()).tools}
                for t in ("mesh_section_figure", "mesh_surface_figure", "mesh_stack_diagram"):
                    chk("도구 %s 가 노출된다" % t, t in names)

                sess = S._data(await s.call_tool("create_session", {"name": "figsmoke"}))
                sid = sess.get("id") or sess.get("session_id")
                chk("세션 생성", bool(sid), sess)
                up = S._data(await s.call_tool("upload_local_path", {"session_id": sid, "path": DECK}))
                fid = up.get("id") if isinstance(up, dict) else None
                if fid is None:
                    files = S._data(await s.call_tool("list_session_files", {"session_id": sid}))
                    fid = files[0]["id"] if isinstance(files, list) and files else None
                chk("덱 업로드 (file_id=%s)" % fid, fid is not None, up)
                if not sid or fid is None:
                    return 1

                # ① 단면
                res = await s.call_tool("mesh_section_figure",
                                        {"session_id": sid, "file_id": fid, "axis": "z"})
                d = S._data(res)
                chk("① mesh_section_figure 가 성공한다", not res.isError, d)
                chk("① svg_file_id 가 온다", isinstance(d, dict) and d.get("svg_file_id"), d if not isinstance(d, dict) else list(d))
                if isinstance(d, dict):
                    chk("①★figure_numbers 에 확대 배율이 들어 있다",
                        "Magnified axis" in (d.get("figure_numbers") or ""), d.get("figure_numbers"))
                    chk("①★figure_numbers 에 최소피처 px 가 들어 있다",
                        "Min feature in px" in (d.get("figure_numbers") or ""), d.get("figure_numbers"))
                    sec = d.get("section") or {}
                    chk("① 매니페스트 숫자가 온다 (parts_hit·min_feature)",
                        "parts_hit" in sec and "min_feature" in sec, list(sec)[:12])
                    chk("① 다각형은 오지 않는다 (응답을 불리지 않는다)", "polys" not in sec)
                    print("      요지: %s" % (d.get("figure_numbers") or "").replace("\n", " | ")[:220])

                # ② 자유면
                res = await s.call_tool("mesh_surface_figure", {"session_id": sid, "file_id": fid})
                d = S._data(res)
                chk("② mesh_surface_figure 가 성공한다", not res.isError, d)
                if isinstance(d, dict):
                    chk("② svg_file_id · svg_bytes 가 온다",
                        d.get("svg_file_id") and d.get("svg_bytes", 0) > 0, {k: d.get(k) for k in ("svg_file_id","svg_bytes")})
                    chk("②★report 에 자유면 비율이 들어 있다",
                        "Free face share" in (d.get("report") or ""), (d.get("report") or "")[:200])

                # ③ 층 모식도
                res = await s.call_tool("mesh_stack_diagram",
                                        {"session_id": sid, "file_id": fid, "axis": "z"})
                d = S._data(res)
                chk("③ mesh_stack_diagram 가 성공한다", not res.isError, d)
                if isinstance(d, dict):
                    chk("③ svg_file_id 가 온다", bool(d.get("svg_file_id")), list(d))
                    rep = d.get("report") or ""
                    chk("③★report 에 중립축이 들어 있다", "Neutral axis" in rep, rep[:250])
                    chk("③★report 의 층 집계 합이 맞는다",
                        "E 읽음 3 · 두께만 0" in rep, [l for l in rep.splitlines() if "Layers" in l])

                # ④ 그림을 실제로 내려받을 수 있나
                svg = S._data(await s.call_tool("download_result",
                                                {"session_id": sid, "file_id": d.get("svg_file_id")}))
                body = svg.get("content", "") if isinstance(svg, dict) else ""
                chk("④ download_result 로 SVG 를 받는다", "<svg" in body and "</svg>" in body, str(svg)[:200])
                chk("④ 그 SVG 에 '모식도'·'단위 없음' 이 있다",
                    "모식도" in body and "단위 없음" in body)

                await s.call_tool("delete_session", {"session_id": sid})
    finally:
        if tid: S._revoke_token(tid)
    bad = OK.count(False)
    print()
    print("=== 그림 MCP 전수: %s (%d/%d) ===" % ("PASS" if bad == 0 else "FAIL", OK.count(True), len(OK)))
    return 0 if bad == 0 else 1

sys.exit(asyncio.run(main()))
