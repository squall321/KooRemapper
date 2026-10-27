# 레시피 도구를 **살아 있는 플랫폼**에서 값으로 잰다 — 씨앗을 실데이터로 돌려 결과가 비어 있지 않은지.
"""KooRemapper 레시피 MCP 스모크 (2026-10-27).

왜 따로 있나. 도구 수를 세는 관문은 **안 부른 새 도구도 초록**이다(green-gates-lie). 그래서 여기서
레시피를 **실제로** 돌려 값을 본다 — 등록된 씨앗을 실데이터 리포트로 recipe_run 해서 결과가
비어 있지 않은지(hotspot envelope ≥1 · contact pair ≥1)와 샌드박스 상한이 켜졌는지 확인한다.

smoke.py 와 같은 전제(api+mcp+worker 가 떠 있어야 한다)이고, 닿지 않으면 건너뛴다(rc=0).

실행:
    mcp_server/venv/bin/python mcp_server/recipe_smoke.py
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import smoke as S
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

SPHERE_NEW = pathlib.Path("/data/koopark/report_fixtures/sphere_hotspot_v1018/report.html")
SEEDS = {"compare_part_worst", "angles_over_threshold", "hotspot_envelope", "contact_pair_peaks"}


def _list(res):
    """리스트 반환 도구 — FastMCP 가 원소마다 text 블록 하나로 준다. 블록별로 JSON 을 푼다."""
    out = []
    import json as _json
    for c in res.content:
        if getattr(c, "type", None) == "text":
            try:
                out.append(_json.loads(c.text))
            except Exception:
                pass
    return out

OK = []


def chk(name, cond, detail=""):
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    OK.append(bool(cond))
    if not cond and detail:
        print("      %s" % str(detail)[:400])


async def _run(s, name, sid, rid, params):
    sub = S._data(await s.call_tool("recipe_run", {
        "name": name, "session_id": sid, "report_ids": [rid], "params": params, "wait_sec": 90}))
    return sub if isinstance(sub, dict) else {}


async def main():
    if not SPHERE_NEW.exists():
        print("SKIP: 새 판 sphere 리포트가 없다 — %s" % SPHERE_NEW)
        return 0
    pat, tid = S._mint_token()
    if not pat:
        print("SKIP: API 에 닿지 않거나 토큰을 발급할 수 없다 (스택이 떠 있어야 한다)")
        return 0
    H = {"Authorization": f"Bearer {pat}"}
    sid = rid = None
    try:
        with httpx.Client(base_url=S.API, timeout=900.0) as c:
            r = c.post("/reports/intake", headers=H,
                       files={"file": ("report.html", SPHERE_NEW.read_bytes(), "text/html")},
                       data={"session_name": "recipe smoke"})
            d = (r.json().get("data") or {}) if r.status_code < 400 else {}
            rid, sid = d.get("report_id"), d.get("session_id")
        chk("새 판 sphere 리포트 반입", bool(rid), r.text[:300])
        if not rid:
            return 1

        async with streamablehttp_client(S.MCP_URL, headers=H) as (rd, w, _):
            async with ClientSession(rd, w) as s:
                await s.initialize()
                names = {t.name for t in (await s.list_tools()).tools}
                for t in ("recipe_search", "recipe_get", "recipe_run", "recipe_propose",
                          "recipe_evaluate", "recipe_register", "recipe_deprecate"):
                    chk("도구 %s 노출" % t, t in names)

                # ① 검색 — 씨앗 넷이 등록돼 보인다(값으로)
                found = _list(await s.call_tool("recipe_search", {}))
                got = {x.get("name") for x in found} if isinstance(found, list) else set()
                chk("씨앗 넷이 검색된다", SEEDS <= got, sorted(got))
                chk("검색 결과가 등록 표식을 든다",
                    all(x.get("registered") for x in found if x.get("name") in SEEDS), found)

                # ② 상세 — current_version 1
                det = S._data(await s.call_tool("recipe_get", {"name": "hotspot_envelope"}))
                chk("recipe_get: hotspot_envelope v1 등록", det.get("current_version") == 1, det)

                # ③ 실행 — 핫스팟 포락이 비어 있지 않다(값) + 샌드박스 상한 켜짐
                he = await _run(s, "hotspot_envelope", sid, rid, {"top": 10})
                hr = (he.get("result") or {}).get("reports") or [{}]
                chk("hotspot_envelope 실행 succeeded", he.get("status") == "succeeded", he.get("error"))
                chk("hotspot_envelope 포락 ≥1 (값)", (hr[0].get("n_envelope") or 0) >= 1, hr[0])
                chk("샌드박스 상한이 켜졌다", bool((he.get("sandbox") or {}).get("limits")), he.get("sandbox"))

                # ④ 접촉쌍 피크 ≥1(값)
                cp = await _run(s, "contact_pair_peaks", sid, rid, {"metric": "pf", "top": 15})
                cr = (cp.get("result") or {}).get("reports") or [{}]
                chk("contact_pair_peaks 실행 succeeded", cp.get("status") == "succeeded", cp.get("error"))
                chk("contact_pair_peaks 쌍 ≥1 (값)", (cr[0].get("n_pairs") or 0) >= 1, cr[0])

                # ⑤ 각도 문턱 — 케이스가 돈다(값)
                an = await _run(s, "angles_over_threshold", sid, rid, {"metric": "max_stress", "threshold": 0.0})
                ar = (an.get("result") or {}).get("reports") or [{}]
                chk("angles_over_threshold 실행 succeeded", an.get("status") == "succeeded", an.get("error"))
                chk("angles_over_threshold 케이스 ≥1 (값)", (ar[0].get("n_over") or 0) >= 1, ar[0])

                # ⑥ 금지 코드는 제안 단계에서 막힌다(값)
                bad = await s.call_tool("recipe_propose", {
                    "name": "smoke_blocked_probe",
                    "code": "import os\ndef run(reports, params):\n return os.listdir('/')\ndef test_x():\n assert run([],{}) is not None",
                    "meta": {"kinds": ["sphere"]}})
                chk("금지 import 제안은 거절된다(값)", bool(bad.isError), bad.content[0].text[:200] if bad.content else "")
    finally:
        if sid:
            try:
                async with streamablehttp_client(S.MCP_URL, headers=H) as (rd, w, _):
                    async with ClientSession(rd, w) as s:
                        await s.initialize()
                        await s.call_tool("delete_session", {"session_id": sid})
            except Exception:
                pass
        if tid:
            S._revoke_token(tid)
    bad_n = OK.count(False)
    print("\n=== 레시피 스모크: %s (%d/%d) ===" % ("PASS" if bad_n == 0 else "FAIL", len(OK) - bad_n, len(OK)))
    return 1 if bad_n else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
