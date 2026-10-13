# 리포트 도구를 **살아 있는 플랫폼**에서 끝까지 — 특히 결과 이미지가 **그림으로** 오는지
"""KooRemapper 리포트 MCP 스모크 (2026-10-13).

왜 이것이 따로 있나.

  "LLM 이 결과 이미지까지 리포트에 쓰면서 비교" 를 하려면 두 가지가 막혀 있었다(실측).
    ① 결과 이미지는 리포트 HTML 안에 **없다** — 옆에 딸린 파일이라 HTML 하나만 올리면
       애초에 플랫폼에 들어오지 않는다. → 번들(.zip) 반입으로 고쳤다.
    ② 들어와도 `download_result` 는 base64 를 **dict 안에** 넣어 돌려준다 — 모델에게는
       **글자**로 온다. 그림을 본 것이 아니다. → `report_image` 가 `Image` 로 돌려준다.

  ②는 **콘텐츠 블록의 종류**를 봐야만 판정된다. 수를 세는 관문으로는 절대 안 잡힌다
  (dict 에 base64 가 들어 있어도 "성공" 이다). 그래서 이 스모크가 `ImageContent` 인지 본다.

  `smoke.py`·`figures_smoke.py`·`deckops_smoke.py` 와 같은 전제(스택이 떠 있어야 한다)이고,
  닿지 않으면 건너뛴다(rc=0).

실행:
    mcp_server/venv/bin/python mcp_server/reports_smoke.py
"""
import asyncio
import io
import pathlib
import sys
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import smoke as S
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

#: 실제 리포트 + 사이드카가 있는 자리. 없으면 건너뛴다(합성으로는 ①의 뜻이 없다).
ROOT = pathlib.Path("/data/koopark/Test_Impact_A")
HTML = ROOT / "impact_report.html"
MEDIA = ROOT / "impact_report_data"

TOOLS = ("report_blocks", "report_block", "report_hotspots", "report_behavior_clusters",
         "report_analytics", "report_media", "report_image", "report_compare")
OK = []


def chk(name, cond, detail=""):
    print("  %-58s %s" % (name, "OK" if cond else "FAIL"))
    OK.append(bool(cond))
    if not cond and detail:
        print("      %s" % str(detail)[:400])


def _bundle() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(HTML, HTML.name)
        for p in sorted(MEDIA.rglob("*")):
            if p.is_file():
                z.write(p, str(p.relative_to(ROOT)))
    return buf.getvalue()


async def main():
    if not HTML.exists():
        print("SKIP: 실제 리포트가 없다 — %s" % HTML)
        return 0
    pat, tid = S._mint_token()
    if not pat:
        print("SKIP: API 에 닿지 않거나 토큰을 발급할 수 없다 (스택이 떠 있어야 한다)")
        return 0
    H = {"Authorization": f"Bearer {pat}"}
    rid = sid = None
    try:
        # 반입은 REST 다 — MCP 로 GB 를 나르지 않는다(`report_upload_instructions` 와 같은 규율).
        with httpx.Client(base_url=S.API, timeout=900.0) as c:
            r = c.post("/reports/intake", headers=H,
                       files={"file": ("bundle.zip", _bundle(), "application/zip")},
                       data={"session_name": "reports smoke"})
            d = (r.json().get("data") or {}) if r.status_code < 400 else {}
            rid, sid = d.get("report_id"), d.get("session_id")
        chk("번들 반입(HTML + 사이드카)", bool(rid), r.text[:300])
        if not rid:
            return 1
        med = (d.get("media") or {})
        chk("미디어가 리포트에 붙었다 (이미지 8 · 영상 8)",
            med.get("n_images") == 8 and med.get("n_videos") == 8, med)
        chk("매핑은 리포트 선언을 따랐다", med.get("mapped_by") == "set_report.media[set][position]", med)
        chk("빈 슬롯을 센다 (그림 없는 위치를 있다고 하지 않는다)",
            med.get("n_empty_slots") == 17, med)

        async with streamablehttp_client(S.MCP_URL, headers=H) as (rd, w, _):
            async with ClientSession(rd, w) as s:
                await s.initialize()
                names = {t.name for t in (await s.list_tools()).tools}
                for t in TOOLS:
                    chk("도구 %s 가 노출된다" % t, t in names)

                md = S._data(await s.call_tool("report_media", {"report_id": rid, "images_only": True}))
                chk("report_media — 이미지 8 · 케이스 8",
                    md.get("n_images") == 8 and len(md.get("cases_with_media") or []) == 8, md)

                # ★핵심 ① 이미지가 **그림으로** 온다
                res = await s.call_tool("report_image", {"report_id": rid, "case_key": "F5_DOE_001"})
                kinds = [type(c).__name__ for c in res.content]
                img = [c for c in res.content if type(c).__name__ == "ImageContent"]
                chk("★report_image 가 ImageContent 로 돌려준다 (글자가 아니다)", bool(img), kinds)
                if img:
                    chk("★mimeType 이 image/png (모델이 볼 수 있는 형식)",
                        img[0].mimeType == "image/png", img[0].mimeType)

                # ★핵심 ② 영상은 **거절하고 대안을 말한다**(모델이 못 보므로)
                mv = S._data(await s.call_tool("report_media", {"report_id": rid, "kind": "video"}))
                vp = (mv.get("media") or [{}])[0].get("path")
                res2 = await s.call_tool("report_image", {"report_id": rid, "path": vp})
                t2 = " ".join(getattr(c, "text", "") for c in res2.content)
                chk("★mp4 는 거절하고 peak png 를 권한다", "볼 수 없" in t2 or "못 본다" in t2, t2[:200])

                # ★핵심 ③ 비교 — 표 + 이미지 여러 장
                res3 = await s.call_tool("report_compare", {
                    "report_id": rid, "case_keys": ["F5_DOE_001", "F5_DOE_002", "F5_DOE_003"]})
                k3 = [type(c).__name__ for c in res3.content]
                nimg = k3.count("ImageContent")
                txt = next((c.text for c in res3.content if hasattr(c, "text")), "")
                chk("★report_compare 가 이미지 3장을 함께 돌려준다", nimg == 3, k3)
                chk("★그 앞에 지표 표가 온다", txt.lstrip().startswith("# 비교") and "| case |" in txt,
                    txt[:160])

                # 블록·군집·요약
                bl = S._data(await s.call_tool("report_blocks", {"report_id": rid}))
                chk("report_blocks — 블록 27 · 미해석 수를 숨기지 않는다",
                    bl.get("n_blocks") == 27 and bl.get("n_unread", 0) > 0, bl.get("n_blocks"))
                cl = S._data(await s.call_tool("report_behavior_clusters", {"report_id": rid}))
                chk("★report_behavior_clusters 가 degenerate 를 말한다 (선언 4 / 사용 1)",
                    cl.get("degenerate") is True and cl.get("n_archetypes_used") == 1, cl)
                an = S._data(await s.call_tool("report_analytics", {"report_id": rid, "block": "physics"}))
                subs = {x["name"] for x in (an.get("blocks") or [{}])[0].get("subs", [])}
                chk("report_analytics — physics 하위 4종",
                    {"RestitutionMap", "StressWaveVelocity"} <= subs, sorted(subs))
                raw = S._data(await s.call_tool("report_block", {
                    "report_id": rid, "name": "doe_analysis", "path": "worst_position"}))
                chk("report_block 으로 원본을 끝까지 되짚는다",
                    raw.get("found") and isinstance(raw.get("value"), dict), raw)
                hs = S._data(await s.call_tool("report_hotspots", {"report_id": rid}))
                chk("핫스팟이 없는 종류에서는 **없다고 말한다**(빈 목록으로 넘기지 않는다)",
                    hs.get("available") is False and "hotspot-clusters" in (hs.get("note") or ""), hs)
    finally:
        with httpx.Client(base_url=S.API, timeout=120.0) as c:
            if rid:
                c.delete(f"/reports/{rid}", headers=H)
            if sid:
                c.delete(f"/sessions/{sid}", headers=H)
        if tid:
            S._revoke_token(tid)
    bad = OK.count(False)
    print("\n=== 리포트 MCP 전수: %s (%d/%d) ===" %
          ("PASS" if bad == 0 else "FAIL", len(OK) - bad, len(OK)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
