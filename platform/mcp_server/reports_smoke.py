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
import hashlib
import io
import json
import pathlib
import shutil
import sys
import uuid
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
#: 새 판 전각도 낙하 리포트(운영 이미지로 만든 고정본 — README 에 출처). 없으면 그 항만 건너뛴다.
SPHERE_NEW = pathlib.Path("/data/koopark/report_fixtures/sphere_hotspot_v1018/report.html")
# 렌더 결과(C-11) 폴더 — MCP 가 읽을 수 있는 자리여야 한다(allops_smoke 의 STAGE_ROOT 와 같은 규칙)
RENDER_ROOT = pathlib.Path(__file__).resolve().parents[2] / "build" / "scratch" / "render_smoke"
#: StepForge fe_cad 묶음(P2 뷰어 기준, 10-29) — 이 박스에만 있다. 없으면 그 항만 건너뛴다.
CAD_REAL = pathlib.Path("/data/appdata/step_forge/projects/001a184fed0639fc4477054/export/fe_cad/2b8061b6990f")


def _cad_copy(*, broken: bool = False) -> pathlib.Path:
    """실제 묶음을 MCP 가 읽을 수 있는 자리로 베낀다(MCP 컨테이너에는 /data/appdata 가 안 보인다 — 10-30 실측).
    broken 이면 parts.json 의 한 바이트를 크기는 그대로 둔 채 바꿔 manifest sha256 과만 어긋나게 한다."""
    d = RENDER_ROOT / uuid.uuid4().hex
    shutil.copytree(CAD_REAL, d)
    if broken:
        b = bytearray((d / "parts.json").read_bytes())
        b[100] = ord("X") if b[100] != ord("X") else ord("Y")
        (d / "parts.json").write_bytes(bytes(b))
    return d


def _render_dir(report_id: str, case_key: str, *, broken: bool = False) -> pathlib.Path:
    """SceneForge 렌더 결과 폴더 하나(render_result.json + mp4 · png). broken 이면 mp4 sha 를 틀리게 적는다."""
    d = RENDER_ROOT / uuid.uuid4().hex
    d.mkdir(parents=True)
    mp4, png = b"\x00\x00\x00\x18ftypmp42" + b"x" * 64, b"\x89PNG\r\n\x1a\n" + b"y" * 32
    (d / "render.mp4").write_bytes(mp4)
    (d / "still_0.500ms.png").write_bytes(png)
    out = lambda k, n, b: {"kind": k, "file": n, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
    outs = [out("mp4", "render.mp4", mp4), out("still", "still_0.500ms.png", png)]
    if broken:
        outs[0]["sha256"] = "0" * 64
    (d / "render_result.json").write_text(json.dumps({
        "format": "sceneforge.render_result", "version": 1, "render_id": "smoke-r1", "request_id": "smoke-q1",
        "ok": True, "reason": None, "warnings": [],
        "run": {"report_id": report_id, "case_key": case_key, "run_id": f"{report_id}:{case_key}"},
        "outputs": outs,
        "meta": {"mode": "report", "deform_scale": 10, "deform_label": "변형 ×10", "notice": "보기 전용"}}))
    return d

TOOLS = ("report_blocks", "report_block", "report_hotspots", "report_behavior_clusters",
         "report_analytics", "report_media", "report_image", "report_compare",
         "report_contact_profile", "report_energy_flow")
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
    rid = sid = srid = ssid = None
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
        if SPHERE_NEW.exists():
            with httpx.Client(base_url=S.API, timeout=900.0) as c:
                r2 = c.post("/reports/intake", headers=H,
                            files={"file": ("report.html", SPHERE_NEW.read_bytes(), "text/html")},
                            data={"session_name": "reports smoke sphere"})
                d2 = (r2.json().get("data") or {}) if r2.status_code < 400 else {}
                srid, ssid = d2.get("report_id"), d2.get("session_id")
            chk("새 판 sphere 리포트 반입", bool(srid), r2.text[:300])
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
                # ── 렌더 결과(C-11) — 새 MCP 도구를 플랫폼으로 부른다(세는 관문은 안 부른 도구도 초록이다) ──
                rd1 = _render_dir(rid, "F5_DOE_001")
                ar = S._data(await s.call_tool("attach_render", {"report_id": rid, "path": str(rd1)})) or {}
                chk("렌더 결과를 붙였다 (mp4 · png 둘)", ar.get("ok") is True and ar.get("stored") == 2, ar)
                rm = S._data(await s.call_tool("report_media", {"report_id": rid, "role": "render"})) or {}
                chk("렌더 그림은 더해졌고 번들 그림 16장은 그대로", rm.get("n_returned") == 2 and rm.get("n_total") == 18,
                    {k: rm.get(k) for k in ("n_total", "n_returned")})
                ar2 = S._data(await s.call_tool("attach_render", {"report_id": rid, "path": str(rd1)})) or {}
                chk("같은 렌더를 다시 붙이면 바꾸는 것이 없다 (멱등)", ar2.get("already") is True, ar2)
                bad = await s.call_tool("attach_render", {"report_id": rid, "path": str(_render_dir(rid, "F5_DOE_001", broken=True))})
                chk("sha256 이 틀린 렌더는 통째로 거절한다", bad.isError and "sha256" in bad.content[0].text,
                    bad.content[0].text[:200] if bad.content else bad)

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
                # ── 과제 · 개정 (온톨로지) ────────────────────────────────
                # ★**쓰지 않는다.** 개정 객체를 지우는 API 가 없어서(일부러 — 과제·개정은
                #   전사 축이다) 쓰면 관문이 돌 때마다 잔재가 쌓인다. 그래서 읽는 길과
                #   **거절하는 길**만 본다. 거절은 쓰지 않고도 확인된다.
                # ★기능 스위치가 꺼져 있을 수도 있다(허브 설정이 없는 박스가 정상이다).
                #   그때는 **꺼졌다고 거절하는 것**이 맞는 동작이므로 그쪽을 판정한다 —
                #   꺼짐을 "통과" 로 접으면 켜졌을 때 깨진 것을 영영 못 본다.
                caps = S._data(await s.call_tool("system_capabilities", {})) \
                    if any(t.name == "system_capabilities"
                           for t in (await s.list_tools()).tools) else {}
                onto_on = bool((caps.get("ontology") or {}).get("enabled")) \
                    if isinstance(caps, dict) else False
                if not onto_on:
                    off = await s.call_tool("list_tasks", {})
                    chk("기능이 꺼져 있으면 **꺼졌다고 사유와 함께 거절한다**(조용히 빈 답 금지)",
                        bool(off.isError) and "꺼져" in str(off.content), str(off.content)[:200])
                    print("  (과제·개정 기능이 꺼져 있다 — 켜진 뒤의 항은 건너뛴다)")
                if onto_on:
                  tk = S._data(await s.call_tool("list_tasks", {}))
                  chk("과제 목록이 비면 **왜 비었는지** 말한다(빈 목록은 「없다」로 읽힌다)",
                      isinstance(tk, dict) and "sync_enabled" in tk
                      and bool(tk.get("items") or tk.get("reason") is not None), tk)
                  rv = S._data(await s.call_tool("report_revision", {"report_id": rid}))
                  shaped = isinstance(rv, dict) and {"mismatch", "candidates", "free_task"} <= set(rv)
                  chk("개정 조회가 **어긋남·후보를 함께** 준다", shaped, rv)
                  # 기능이 없는 스택에서는 위가 FAIL 이고, 그러면 아래는 **묻지 않는다** —
                  # 없는 것에 `.get` 을 걸면 관문이 역추적으로 죽어 다른 항까지 못 본다.
                  chk("아무것도 안 이었으니 어긋남이 없다(없는 것을 있다고 하지 않는다)",
                      shaped and rv.get("mismatch") is None, rv if not shaped else rv.get("mismatch"))
                  # ⚠`call_tool` 은 **예외를 던지지 않는다** — `isError` 로 알려 준다(실측).
                  #   예외만 보면 "거절됐다" 를 영영 못 보고 관문이 조용히 통과한다.
                  bad = await s.call_tool("set_report_revision",
                                          {"report_id": rid, "task_key": "SMOKE-NOPE", "code": "dv"})
                  chk("형식이 아닌 개정 코드는 **거절된다**(dv/pv 는 차수 필수)",
                      bool(bad.isError), str(bad.content)[:200])
                  pl = S._data(await s.call_tool("plan_task_links", {}))
                  chk("과거 붙이기 계획이 **붙는 것·후보·못 붙인 것**을 갈라 준다",
                      isinstance(pl, dict) and isinstance(pl.get("counts"), dict)
                      and {"links", "proposal", "unmatched", "reports_without_a_name"}
                      <= set(pl["counts"]), pl)

                hs = S._data(await s.call_tool("report_hotspots", {"report_id": rid}))
                chk("핫스팟이 없는 종류에서는 **없다고 말한다**(빈 목록으로 넘기지 않는다)",
                    hs.get("available") is False and "hotspot-clusters" in (hs.get("note") or ""), hs)

                # ── 파트쌍 접촉 프로파일 · 하중경로 (10-23) ────────────────────
                # 도구 수(73)만 세면 새 도구를 한 번도 안 불러도 초록이다. 값으로 본다.
                cp = S._data(await s.call_tool("report_contact_profile", {"report_id": rid}))
                ax = (cp.get("axis_summary") or [{}])[0] if isinstance(cp, dict) else {}
                chk("report_contact_profile — impact 23쌍 × 25위치",
                    cp.get("available") is True and cp.get("axis_kind") == "position"
                    and cp.get("n_pairs") == 23 and cp.get("n_axis") == 25, cp)
                # ★앞 12개 위치는 접촉이 없다(전부 None) — 축 순서로 내면 「가장 센 위치」가 빈 위치가 된다.
                chk("★축 요약이 **세기 순**이다(첫째 F5_DOE_025 · 23쌍이 닿았다)",
                    ax.get("case_key") == "F5_DOE_025" and ax.get("n_engaged") == 23
                    and isinstance(ax.get("top_value"), (int, float)), ax)
                at = (S._data(await s.call_tool("report_contact_profile", {
                    "report_id": rid, "case_key": "F5_DOE_025"})) or {}).get("at") or {}
                chk("그 위치의 파트쌍 엣지 23 · 피크 접촉력이 다 있다",
                    at.get("found") is True and len(at.get("edges") or []) == 23
                    and all(e.get("peak_force") is not None for e in at.get("edges") or []), at)
                ef = S._data(await s.call_tool("report_energy_flow", {"report_id": rid, "case_key": "F5_DOE_013"}))
                eg = ((ef or {}).get("energy_flow") or {}).get("edges") or []
                # ★impact 압축본은 엣지 이름이 `peak_f` 다 — 중립 이름만 읽던 때는 23개가 **전부 null** 이었다.
                chk("★하중경로 엣지 23 · peak_force 가 null 이 아니다(압축 꼴을 읽는다)",
                    len(eg) == 23 and all(e.get("peak_force") is not None for e in eg),
                    [e.get("peak_force") for e in eg][:5])
                miss = S._data(await s.call_tool("report_energy_flow", {"report_id": rid, "case_key": "NO_SUCH"}))
                chk("★없는 케이스는 **다른 케이스로 떨어지지 않는다**(null + 고를 수 있는 키)",
                    miss.get("energy_flow") is None and miss.get("flow_case_key") is None
                    and len(miss.get("available_case_keys") or []) == 25, miss)
                if srid:
                    sh = S._data(await s.call_tool("report_hotspots", {"report_id": srid}))
                    chk("★sphere 핫스팟 — 13항목 · 58군집 · 포락 13",
                        sh.get("available") is True and sh.get("n_records") == 13
                        and sh.get("n_clusters_all") == 58 and len(sh.get("envelope") or []) == 13, sh)
                    sp = S._data(await s.call_tool("report_contact_profile", {"report_id": srid}))
                    chk("sphere 접촉 프로파일 — 22쌍 · 각도 축 · 신뢰 요약",
                        sp.get("n_pairs") == 22 and sp.get("axis_kind") == "angle"
                        and isinstance(sp.get("trust"), dict), sp)
                    se = S._data(await s.call_tool("report_energy_flow", {"report_id": srid}))
                    sg = ((se or {}).get("energy_flow") or {}).get("edges") or []
                    chk("sphere 하중경로 — 엣지 22 · 피크 값 · 쓴 케이스를 적는다",
                        len(sg) == 22 and all(e.get("peak_force") is not None for e in sg)
                        and bool(se.get("flow_case_key")), se.get("flow_case_key"))
                    if CAD_REAL.exists():
                        # ── CAD 형상 묶음(뷰어 1단계) — 새 MCP 도구를 플랫폼으로 부른다(세는 관문은 안 부른 도구도 초록이다) ──
                        good = str(_cad_copy())
                        ac = S._data(await s.call_tool("attach_cad", {"report_id": srid, "path": good}))
                        ac = ac if isinstance(ac, dict) else {"text": ac}
                        chk("CAD 묶음을 붙였다 (22파트 · 파일 6 — manifest 포함)", ac.get("stored") == 6 and ac.get("n_parts") == 22, ac)
                        ac2 = S._data(await s.call_tool("attach_cad", {"report_id": srid, "path": good}))
                        ac2 = ac2 if isinstance(ac2, dict) else {"text": ac2}
                        chk("같은 묶음을 다시 붙이면 바꾸는 것이 없다 (멱등)", ac2.get("already") is True, ac2)
                        badc = await s.call_tool("attach_cad", {"report_id": srid, "path": str(_cad_copy(broken=True))})
                        chk("파일 하나가 바뀐 묶음은 통째로 거절한다", badc.isError and "sha256" in badc.content[0].text,
                            badc.content[0].text[:200] if badc.content else badc)
    finally:
        shutil.rmtree(RENDER_ROOT, ignore_errors=True)
        with httpx.Client(base_url=S.API, timeout=120.0) as c:
            for r_id in (rid, srid):
                if r_id:
                    c.delete(f"/reports/{r_id}", headers=H)
            for s_id in (sid, ssid):
                if s_id:
                    c.delete(f"/sessions/{s_id}", headers=H)
        if tid:
            S._revoke_token(tid)
    bad = OK.count(False)
    print("\n=== 리포트 MCP 전수: %s (%d/%d) ===" %
          ("PASS" if bad == 0 else "FAIL", len(OK) - bad, len(OK)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
