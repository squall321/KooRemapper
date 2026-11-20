"""System status + capabilities — powers the frontend status/parity view and the
MCP system tools. Shows what's healthy and what web/MCP each support."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import MCP_PUBLIC_URL_ENV, settings
from app.database import get_db
from app.models import ImpactReport, Job, User
from app.runner import catalog
from app.shared.auth import get_current_user
from app.shared.features import ontology_state
from app.modules.campaigns.services import STATES as CAMPAIGN_STATES
from app.modules.users.routes import mcp_add_command, mcp_public_url
from app.shared.responses import ok

router = APIRouter(tags=["system"])

APP_VERSION = "0.1.0"

# MCP 서버 소스 경로 — 도구 수를 하드코딩하지 않고 여기서 @mcp.tool( 을 세어 산출한다.
_MCP_SERVER_SRC = Path(__file__).resolve().parents[4] / "mcp_server" / "server.py"


def _mcp_tool_count() -> int | None:
    """MCP 서버 소스의 @mcp.tool( 개수(단일 소스). 소스를 못 찾으면 None.

    별도 프로세스라 런타임 introspection 이 어려워 소스를 직접 센다. None 이면 프론트는
    개수 없이 'MCP 도구' 로만 표시한다(하드코딩 리터럴을 두지 않기 위함).
    """
    try:
        return _MCP_SERVER_SRC.read_text(encoding="utf-8").count("@mcp.tool(")
    except OSError:
        return None


def _gmsh_available() -> bool:
    # next to the binary (findGmshExe convention) or on PATH
    bindir = settings.kooremapper_bin.parent
    for c in (bindir / "gmsh" / "gmsh.exe", bindir / "gmsh" / "gmsh"):
        if c.exists():
            return True
    return shutil.which("gmsh") is not None


#: 후처리 판을 볼 기간 · 판 수 — 운영에서 「지금 어느 판이 도는가」 를 보는 칸이라 오래된 판은 뺀다.
POSTPROCESS_VERSION_DAYS = 90
POSTPROCESS_VERSION_MAX = 10


#: 남이 지은 글(꾸러미의 producer)을 목록에 낼 때의 상한 — 찍히는 글자 한 줄.
POSTPROCESS_TEXT_MAX = 80


def _one_line(v, cap: int = POSTPROCESS_TEXT_MAX) -> str | None:
    """찍히는 글자 한 줄 · 상한 — 줄바꿈 · 제어 문자는 빈칸으로 접는다. 비면 None."""
    if v is None:
        return None
    # 훑기 전에 먼저 자른다 — 긴 글 전체를 글자마다 훑지 않게(11-15 검토). 빈칸 접기로 줄어들 몫을 넉넉히 둔다.
    raw = str(v)[: cap * 4]
    s = " ".join("".join(ch if ch.isprintable() else " " for ch in raw).split())
    return s[:cap] or None


async def _postprocess_versions(db: AsyncSession) -> list[dict]:
    """최근 7-1 반입 리포트에 실려 온 후처리 판 — `ontology.producer` 의 서로 다른 {name, adapter, version} · 수 · 마지막 시각.

    왜(2026-11-12, 포털 낙하 파이프라인 (c)) — stcx 에 접속하지 않고도 운영에서 실제로 어느 후처리 판(예 v51)이
    도는지 본다. 꾸러미가 없거나 판이 빈 리포트는 세지 않는다 — 판을 모르는 것을 판이 없다고 하지 않는다.

    합친 판 검토(kooremapper-4a, 11-15)가 셋을 고쳤다 —
    · 후처리(koo_deep_report)가 쓰는 칸은 `tool` · `adapter` · `version` · `created_utc` 다(`name` 이 아니다 — 픽스처
      `cae_package_v14_min.json`). 이름은 `tool`(없으면 옛 `name`), 어댑터가 다르면 다른 줄이다. 빈 `version`(dev 호스트)은 건너뛴다.
    · **7-1 로 들어온 리포트(`external_job_key` 가 있는 것)만** 센다 — 손으로 붙이는 꾸러미의 producer 는 아무나 지을 수
      있어 「운영에서 실제로 도는 판」 이 아니고, 지어낸 판이 진짜 판을 목록에서 밀어낼 수 있다.
    · 그래도 남이 지은 글이다 — 로그인한 모두에게 나가므로 찍히는 글자 한 줄 · 80자로 접는다.
    """
    from datetime import datetime, timedelta, timezone
    prod = ImpactReport.ontology["producer"]
    # 앞부분만 가져온다 — 남이 지은 긴 글이 DB 에서 통째로 넘어오지 않게(어차피 80자로 접는다).
    head = POSTPROCESS_TEXT_MAX * 4
    tool = func.substr(func.coalesce(prod["tool"].astext, prod["name"].astext), 1, head)
    adapter = func.substr(prod["adapter"].astext, 1, head)
    ver = func.substr(prod["version"].astext, 1, head)
    last = func.max(ImpactReport.created_at)
    since = datetime.now(timezone.utc) - timedelta(days=POSTPROCESS_VERSION_DAYS)
    rows = (await db.execute(
        select(tool, adapter, ver, func.count(), last)
        .where(ImpactReport.external_job_key.is_not(None), ver.is_not(None), ver != "",
               ImpactReport.created_at >= since)
        .group_by(tool, adapter, ver).order_by(last.desc()).limit(POSTPROCESS_VERSION_MAX * 5))).all()
    # 접은 뒤 같아진 줄은 합친다 — 접기 전에는 달랐어도 사람에게는 같은 판이다.
    merged: dict[tuple, dict] = {}
    for n, a, v, c, t in rows:
        key = (_one_line(n), _one_line(a), _one_line(v))
        if key[2] is None:
            continue
        m = merged.setdefault(key, {"name": key[0], "adapter": key[1], "version": key[2], "n": 0, "last": None})
        m["n"] += c
        m["last"] = t if m["last"] is None or (t and t > m["last"]) else m["last"]
    out = sorted(merged.values(), key=lambda m: m["last"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return [{"name": m["name"], "adapter": m["adapter"], "version": m["version"], "n": m["n"],
             "last_at": m["last"].isoformat() if m["last"] else None} for m in out[:POSTPROCESS_VERSION_MAX]]


@router.get("/system/status")
async def system_status(request: Request, _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _mcp_url = mcp_public_url(request)
    db_ok = True
    queued = running = 0
    try:
        await db.execute(text("SELECT 1"))
        queued = (await db.execute(select(func.count(Job.id)).where(Job.status == "queued"))).scalar_one()
        running = (await db.execute(select(func.count(Job.id)).where(Job.status == "running"))).scalar_one()
    except Exception:
        db_ok = False
    try:
        pp_versions = await _postprocess_versions(db) if db_ok else None
    except Exception:          # 덧붙인 칸이 상태 응답 전체를 깨지 않게 — 못 셌다는 것은 None 으로 말한다
        pp_versions = None
    return ok({
        "version": APP_VERSION,
        "env": settings.app_env,
        "api": {"ok": True, "port": settings.api_port},
        "database": {"ok": db_ok, "port": None},
        "worker": {"concurrency": settings.worker_concurrency, "queued": queued, "running": running},
        "binary": {"present": settings.kooremapper_bin.exists()},
        "gmsh": {"available": _gmsh_available(), "note": "meshfix 전용"},
        # ⚠ 공개 주소는 **설정에 있을 때만** 낸다 — 예전엔 `http://<host>:<port>/mcp` 라는 자리표시자를
        # 줬는데, 사람은 그것을 주소로 읽고 `<host>` 만 자기 호스트로 바꿔 붙였다(포트·경로가 틀린 채).
        # 세 자리(여기·capabilities·토큰 화면)가 **같은 함수**를 써야 한 요청에서 서로 다른 답이 안 나온다.
        "mcp": {"port": settings.mcp_port,
                "url": _mcp_url or None,
                "url_note": None if _mcp_url
                else f"{MCP_PUBLIC_URL_ENV} 미설정 — 공개 주소를 모른다(지어내지 않는다). "
                     "토큰 발급 화면의 접속 명령도 이 값이 있어야 나온다"},
        "rate_limit": {"enabled": settings.ratelimit_enabled},
        "signup": {"enabled": settings.allow_signup},
        "operations": len(catalog.operation_names()),
        # 최근 리포트가 실어 온 후처리 판 — None 이면 못 셌다, [] 이면 그 기간에 꾸러미 실린 리포트가 없다
        "postprocess_versions": pp_versions,
        "postprocess_versions_window_days": POSTPROCESS_VERSION_DAYS,
    })


# Capability parity matrix: which features are reachable via web and via MCP.
_PARITY = [
    {"feature": "세션 관리", "web": True, "mcp": True},
    {"feature": "파일 업로드/조회/다운로드", "web": True, "mcp": True, "note": "MCP는 로컬경로 업로드도 지원"},
    {"feature": "오퍼레이션 카탈로그/옵션", "web": True, "mcp": True},
    {"feature": "오퍼레이션 실행/Job/로그/취소", "web": True, "mcp": True},
    {"feature": "낙하/충격 리포트 인제스트/분석", "web": True, "mcp": True,
     "note": "웹은 업로드·원샷 반입·분석 7탭(ReportsPanel/ReportAnalysis)"},
    {"feature": "해석 온톨로지 보기·붙이기(리포트)", "web": True, "mcp": True,
     "note": "리포트 상세 「해석 온톨로지」(파트 판정 · 하중 경로 · 꾸러미 붙이기) · report_cae · attach_cae_package"},
    {"feature": "해석 온톨로지 질의(리포트를 건너)", "web": False, "mcp": True,
     "note": "find_cae_parts · find_cae_load_paths(REST /cae/parts · /cae/load-paths) — 웹 화면은 아직 없다"},
    {"feature": "해석 온톨로지 코어 다리(cae → 코어 · 사람 선 확정)", "web": False, "mcp": True,
     "note": "보기는 report_cae 의 bridges(선 · 끊긴 사람 선 · 후보) — 확정 · 지우기는 REST POST · DELETE /reports/{id}/cae/bridges"
             "(리포트 주인 · 시스템 관리자). 웹 화면은 아직 없다"},
    {"feature": "캠페인 묶음 적재(런 목록 · 적재 상태)", "web": False, "mcp": True,
     "note": "create_campaign · ingest_campaign_manifest · campaign_ingest_status(REST /campaigns …) — 리포트 본문은 REST intake 에 "
             "campaign_id · run_key 를 붙여 보낸다. 웹 화면은 아직 없다"},
    {"feature": "내 정보(whoami)", "web": True, "mcp": True},
    {"feature": "시스템 상태", "web": True, "mcp": True},
    {"feature": "허브 기준정보 보기(온톨로지)", "web": True, "mcp": True,
     "note": "읽기 전용 — 정본은 SP 허브(ontology_types · ontology_find · ontology_object)"},
    {"feature": "허브 받기 관리(admin)", "web": True, "mcp": False,
     "note": "지금 받기 · 처음부터 · 강제 정리 · 합친 과제 옮기기 — 전사 데이터를 움직이므로 관리자 화면 전용"},
    {"feature": "MCP 토큰 발급", "web": True, "mcp": False, "note": "보안상 웹 전용"},
    {"feature": "사용자 관리(admin)", "web": True, "mcp": False},
]


@router.get("/system/capabilities")
async def capabilities(request: Request, _user: User = Depends(get_current_user)):
    return ok({
        "operations": len(catalog.operation_names()),
        # 하드코딩 대신 MCP 소스의 @mcp.tool( 을 세어 산출(None 이면 프론트가 개수 생략).
        "mcp_tools": _mcp_tool_count(),
        # 과제·개정 기능의 **스위치 상태**. 화면이 이것으로 숨기고, 포탈의 설정 항목이
        # 「켜졌나」를 여기서 확인한다. 꺼짐은 **사유와 함께** 낸다 — 꺼짐과 고장을 같은
        # 모양으로 만들지 않는다. 판정은 `shared/features.py` 한 곳에서만 한다.
        "ontology": ontology_state(),
        "parity": _PARITY,
        # ⚠ 주소를 모를 때 f-string 에 빈 값을 끼우면 **URL 칸만 빈 명령**이 나온다 — 화면이 그것을
        # 복사 버튼과 함께 그리고, 붙여넣으면 claude 가 `--header` 값을 URL 로 먹는다. 토큰 화면과
        # 같은 함수를 써서 그때는 명령 대신 '무엇을 설정해야 하는지' 를 낸다(요청서 ④ 고침 2).
        "mcp_url": mcp_public_url(request) or None,
        "mcp_add_hint": mcp_add_command(request, "kr_..."),
        "mcp_desktop_hint": "Claude Desktop은 mcp-remote 브리지 사용 (mcp_server/CLAUDE_DESKTOP.md)",
        # ★외부 적재의 공식 답(2026-11-17 · 결정 문서 D4) — 게이트웨이 카탈로그(GW-01)가 이것을 그대로 싣는다. 토큰은 이 서버가
        #   발급한 kr_ PAT(Authorization: Bearer)이고 API 가 스스로 검증하므로 포털 관문(portal_auth)이 필요 없다. 운영 게이트웨이가
        #   그 헤더를 실제로 넘기는지는 이 칸이 보증하지 않는다 — 401 이면 detail 글로 가른다(MCP `upload_instructions`).
        #   공개 주소는 운영자가 KOORM_PUBLIC_BASE 를 넣어야 채워진다(비면 null).
        #   ★`batch` 는 캠페인 묶음 적재(2026-11-20 · DF-01)가 있다는 뜻이다 — 런 목록을 먼저 올리고 런마다 이 길에
        #   `campaign_id` · `run_key` 를 붙여 보내면 같은 내용은 건너뛴다. 한 호출에 리포트 하나인 것은 그대로다
        #   (`reports_per_call`). 분당 한도는 올리기 길 전체가 토큰 하나에 나눠 쓴다(넘으면 429 `Retry-After`).
        "intake": {
            "method": "POST",
            "path": "/api/v1/reports/intake",
            "public_url": (settings.public_base.rstrip("/") + "/apps/kooremapper_api/api/v1/reports/intake")
                          if settings.public_base.strip() else None,
            "mcp_url": mcp_public_url(request) or None,
            "token": "kr_pat",
            "portal_auth_required": False,
            "max_upload_mb": settings.max_upload_mb,
            "max_report_mb": settings.max_report_mb,
            "batch": True,
            "reports_per_call": 1,
            "rate_limit_per_min": (settings.ratelimit_upload_per_min
                                   if settings.ratelimit_enabled and settings.ratelimit_upload_per_min > 0 else None),
            "campaign": {
                "create": "/api/v1/campaigns",
                "manifest": "/api/v1/campaigns/{campaign_id}/runs",
                "status": "/api/v1/campaigns/{campaign_id}/ingest-status",
                "form_fields": ["campaign_id", "run_key"],
                "states": list(CAMPAIGN_STATES),
            },
        },
    })
