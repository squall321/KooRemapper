"""KooRemapper MCP 서버 — Claude 가 K파일 세션을 관리하고 메쉬/해석 오퍼레이션을
실행·다운로드하게 하는 도구. (op 개수는 카탈로그 단일 소스에서 동적으로 결정된다.)

백엔드(FastAPI)와 의존성 충돌을 피하려고 **별도 venv·프로세스**로 돌리고, 백엔드와는
**REST API** 로만 통신한다. 들어온 MCP 요청의 `Authorization: Bearer kr_...`(개인 토큰)을
그대로 백엔드에 전달해 **그 사용자 권한**으로 동작한다.

실행:
    KOOREMAPPER_API_BASE=http://127.0.0.1:8700 \
    ./venv/bin/python server.py            # streamable-http, 기본 127.0.0.1:8701/mcp

Claude Code 등록(개인 토큰):
    claude mcp add --transport http kooremapper http://<host>:8701/mcp \
      --header "Authorization: Bearer kr_..."
"""
from __future__ import annotations

import base64
import os

import httpx
from mcp.server.fastmcp import Context, FastMCP

API_BASE = os.environ.get("KOOREMAPPER_API_BASE", "http://127.0.0.1:8700").rstrip("/")
API = f"{API_BASE}/api/v1"

# MCP serverInfo.name — 포탈/HEAX 카탈로그와 통일한 브랜드 표시명.
# (라우트 슬러그·URL 은 여전히 kooremapper 로 유지된다.)
mcp = FastMCP("DynaForge")


def _forward_headers(ctx: Context) -> dict:
    headers: dict[str, str] = {}
    req = getattr(getattr(ctx, "request_context", None), "request", None)
    if req is not None:
        v = req.headers.get("authorization")
        if v:
            headers["Authorization"] = v
    return headers


def _unwrap(r: httpx.Response):
    """Unwrap {success,data,message}. RAISE on error so Claude sees a tool error
    (a returned error dict would look like a successful result)."""
    try:
        body = r.json()
    except Exception:
        raise RuntimeError(f"Backend returned HTTP {r.status_code} (non-JSON)")
    if r.status_code >= 400 or (isinstance(body, dict) and not body.get("success", True)):
        msg = (body.get("message") if isinstance(body, dict) else None) or f"HTTP {r.status_code}"
        raise RuntimeError(msg)
    if not isinstance(body, dict):
        return body
    data = body.get("data")
    # Success responses with no data but a message (delete/cancel) would return
    # an empty result — surface the message so Claude sees the outcome.
    if data is None and body.get("message"):
        return {"message": body["message"]}
    return data if "data" in body else body


async def _get(ctx, path, params=None):
    async with httpx.AsyncClient(base_url=API, timeout=60) as c:
        return _unwrap(await c.get(path, params=params, headers=_forward_headers(ctx)))


async def _post(ctx, path, json_body=None):
    async with httpx.AsyncClient(base_url=API, timeout=120) as c:
        return _unwrap(await c.post(path, json=json_body, headers=_forward_headers(ctx)))


async def _delete(ctx, path):
    async with httpx.AsyncClient(base_url=API, timeout=60) as c:
        return _unwrap(await c.delete(path, headers=_forward_headers(ctx)))


# ── 오퍼레이션 카탈로그 ──────────────────────────────────────────────
@mcp.tool()
async def list_operations(ctx: Context) -> list:
    """사용 가능한 전체 오퍼레이션 요약(name, category, summary, 입력유형). 무엇을 할 수
    있는지 먼저 조회. 상세 인자는 describe_operation 으로."""
    return await _get(ctx, "/operations")


@mcp.tool()
async def describe_operation(operation: str, ctx: Context) -> dict:
    """한 오퍼레이션의 상세 — 인자 JSON Schema(args_schema), 입출력, 예제 args, 매뉴얼.
    run_operation 호출 전에 args 를 어떻게 구성할지 여기서 확인하라."""
    return await _get(ctx, f"/operations/{operation}")


# ── 세션 / 파일 ──────────────────────────────────────────────────────
@mcp.tool()
async def whoami(ctx: Context) -> dict:
    """현재 토큰의 사용자 정보. / The current authenticated user."""
    return await _get(ctx, "/me")


@mcp.tool()
async def system_status(ctx: Context) -> dict:
    """플랫폼 상태(api/db/worker 큐/gmsh/바이너리/op 수). / Platform health + worker queue."""
    return await _get(ctx, "/system/status")


@mcp.tool()
async def list_sessions(ctx: Context) -> list:
    """내 세션(프로젝트) 목록 — **user_id 스코프**(이 호출자 계정의 것만). 각 세션은
    업로드/생성된 K파일 묶음이다. 빈 배열 ≠ 전사에 없음 — 전사 집계는 corpus_summary."""
    return await _get(ctx, "/sessions")


@mcp.tool()
async def create_session(name: str, ctx: Context, description: str | None = None) -> dict:
    """새 세션(작업 공간)을 만든다 — K파일 업로드·오퍼레이션 실행의 컨테이너라 모든 작업의
    첫 도구다. 기존 작업을 이어가려면 list_sessions 로 먼저 찾는다."""
    return await _post(ctx, "/sessions", {"name": name, "description": description})


@mcp.tool()
async def get_session(session_id: str, ctx: Context) -> dict:
    """세션 상세와 포함 파일 목록(meta 포함)을 반환한다 — "이 세션에 뭐가 들어 있나"의 입구.
    파일 하나의 깊은 메타는 inspect_file, 잡 이력은 list_session_jobs."""
    return await _get(ctx, f"/sessions/{session_id}")


@mcp.tool()
async def upload_kfile(
    session_id: str, filename: str, content: str, ctx: Context, base64_encoded: bool = False
) -> dict:
    """세션에 파일 업로드. `content` 는 파일 내용(LS-DYNA .k 등 텍스트). 바이너리면
    base64 로 주고 base64_encoded=true. 업로드 즉시 백엔드가 `info` 로 노드/요소/파트/
    bbox/*INCLUDE 를 파싱해 meta 에 캐시한다."""
    raw = base64.b64decode(content) if base64_encoded else content.encode("utf-8")
    files = {"files": (filename, raw, "application/octet-stream")}
    async with httpx.AsyncClient(base_url=API, timeout=120) as c:
        return _unwrap(
            await c.post(
                f"/sessions/{session_id}/files", files=files, headers=_forward_headers(ctx)
            )
        )


@mcp.tool()
async def upload_local_path(session_id: str, path: str, ctx: Context, filename: str | None = None) -> dict:
    """로컬 디스크의 파일을 그대로 세션에 업로드한다(대형 메쉬에 적합). MCP 서버가 그 파일을
    읽을 수 있는 같은 머신에서 돌 때만 동작한다(예: Claude Desktop + 로컬 실행). 대화로
    내용을 실어나르지 않으므로 수십 MB도 OK.
    Upload a file straight from local disk (best for large meshes). Only works when the
    MCP server can read `path` (server runs on the same machine, e.g. Claude Desktop local)."""
    import os as _os
    if not _os.path.isfile(path):
        raise RuntimeError(f"file not found on the MCP host: {path}")
    name = filename or _os.path.basename(path)
    with open(path, "rb") as fh:
        raw = fh.read()
    files = {"files": (name, raw, "application/octet-stream")}
    async with httpx.AsyncClient(base_url=API, timeout=300) as c:
        return _unwrap(
            await c.post(
                f"/sessions/{session_id}/files", files=files, headers=_forward_headers(ctx)
            )
        )


@mcp.tool()
async def save_result_to_path(session_id: str, file_id: int, dest_path: str, ctx: Context) -> dict:
    """세션 파일(산출물)을 로컬 디스크 경로로 저장한다(대형 파일에 적합, 대화로 안 실어나름).
    MCP 서버가 dest_path 에 쓸 수 있는 같은 머신에서 돌 때만 동작.
    Save a session file to a local disk path (best for large outputs; same-machine only)."""
    import os as _os
    async with httpx.AsyncClient(base_url=API, timeout=300) as c:
        r = await c.get(
            f"/sessions/{session_id}/files/{file_id}/download", headers=_forward_headers(ctx)
        )
    if r.status_code >= 400:
        raise RuntimeError(f"download failed: HTTP {r.status_code}")
    d = _os.path.dirname(dest_path)
    if d:
        _os.makedirs(d, exist_ok=True)
    with open(dest_path, "wb") as fh:
        fh.write(r.content)
    return {"saved": dest_path, "bytes": len(r.content)}


@mcp.tool()
async def list_session_files(session_id: str, ctx: Context) -> list:
    """세션 안의 파일 목록 + 각 파일의 meta(노드/요소/파트/bbox/*INCLUDE/키워드).
    "이 K파일 안에 뭐가 들어있는지" 를 여기서 확인한다."""
    return await _get(ctx, f"/sessions/{session_id}/files")


@mcp.tool()
async def inspect_file(session_id: str, file_id: int, ctx: Context) -> dict:
    """단일 K파일의 상세 메타(info 결과 + *INCLUDE 내부 파일 목록)를 반환한다 — 업로드한
    덱의 구조·포함 관계를 확인할 때 쓴다. 파트 단위 정보는 part_info/list_parts."""
    return await _get(ctx, f"/sessions/{session_id}/files/{file_id}/inspect")


# ── 실행 / 결과 ──────────────────────────────────────────────────────
@mcp.tool()
async def run_operation(session_id: str, operation: str, args: dict, ctx: Context) -> dict:
    """세션 파일에 오퍼레이션을 적용(비동기 Job 생성) → job_id 반환. args 는
    describe_operation 의 args_schema 를 따른다(파일 인자는 세션 내 파일명). 진행상황은
    get_job 으로 폴링하고, 끝나면 download_result 로 산출물을 가져온다."""
    return await _post(
        ctx, f"/sessions/{session_id}/jobs", {"operation": operation, "args": args}
    )


@mcp.tool()
async def get_job(job_id: str, ctx: Context, include_logs: bool = False) -> dict:
    """Job 상태/진행/exit_code/산출 파일. include_logs=true 면 stdout/stderr 일부도."""
    job = await _get(ctx, f"/jobs/{job_id}")
    if include_logs and isinstance(job, dict):
        async with httpx.AsyncClient(base_url=API, timeout=60) as c:
            r = await c.get(f"/jobs/{job_id}/logs", headers=_forward_headers(ctx))
            job = {**job, "logs": r.text[-4000:] if r.status_code < 400 else f"(logs unavailable: HTTP {r.status_code})"}
    return job


@mcp.tool()
async def cancel_job(job_id: str, ctx: Context) -> dict:
    """실행 중이거나 대기 중인 Job 을 취소한다 — 잘못 낸 잡이나 매달린 잡을 정리할 때.
    상태 확인은 job_status, 취소 후 재실행은 run_job. / Cancel a queued or running job."""
    return await _post(ctx, f"/jobs/{job_id}/cancel", None)


@mcp.tool()
async def update_session(
    session_id: str, ctx: Context, name: str | None = None, description: str | None = None
) -> dict:
    """세션 이름·설명을 수정한다 — 작업이 진화해 이름이 안 맞을 때 정리용.
    / Rename or re-describe a session."""
    body = {k: v for k, v in {"name": name, "description": description}.items() if v is not None}
    async with httpx.AsyncClient(base_url=API, timeout=60) as c:
        return _unwrap(await c.patch(f"/sessions/{session_id}", json=body, headers=_forward_headers(ctx)))


@mcp.tool()
async def delete_session(session_id: str, ctx: Context) -> dict:
    """세션과 그 안의 모든 파일을 삭제. / Delete a session and all its files (irreversible)."""
    return await _delete(ctx, f"/sessions/{session_id}")


@mcp.tool()
async def delete_file(session_id: str, file_id: int, ctx: Context) -> dict:
    """세션에서 파일 1건을 삭제한다(복구 불가) — 잘못 올린 파일 정리용. 어떤 파일이 있는지는
    get_session 으로 먼저 확인. / Delete a single file from a session."""
    return await _delete(ctx, f"/sessions/{session_id}/files/{file_id}")


@mcp.tool()
async def get_job_outputs(job_id: str, ctx: Context) -> list:
    """Job 이 생성한 산출 파일 목록(session_file id/이름/meta)을 반환한다 — 잡이 끝난 뒤
    "무엇이 나왔나"의 입구. 내려받기는 download_result, 잡 로그는 slurm/job 로그 도구."""
    return await _get(ctx, f"/jobs/{job_id}/outputs")


@mcp.tool()
async def download_result(
    session_id: str, file_id: int, ctx: Context, as_base64: bool = False
) -> dict:
    """세션 파일 내용을 가져온다(오퍼레이션 산출물 회수). 기본은 텍스트로 반환하고,
    바이너리거나 큰 파일이면 as_base64=true 로 base64 반환."""
    async with httpx.AsyncClient(base_url=API, timeout=120) as c:
        r = await c.get(
            f"/sessions/{session_id}/files/{file_id}/download",
            headers=_forward_headers(ctx),
        )
    if r.status_code >= 400:
        # Surface as a tool error (like every other tool) instead of a dict that
        # would look like a successful result.
        try:
            msg = r.json().get("message") or f"HTTP {r.status_code}"
        except Exception:
            msg = f"HTTP {r.status_code}"
        raise RuntimeError(f"다운로드 실패: {msg}")
    data = r.content
    # Guard against dumping a huge file into the model context. The cap applies to
    # BOTH the text and base64 branches — base64 is ~33% bigger, so it can't be the
    # escape hatch. For genuinely large files use save_result_to_path (writes to
    # disk, same-machine) instead of pulling bytes through the conversation.
    MAX = int(os.environ.get("KOORM_MCP_MAX_DOWNLOAD_BYTES", str(5 * 1024 * 1024)))
    if len(data) > MAX:
        return {
            "filename_id": file_id, "bytes": len(data),
            "error": f"파일이 큽니다({len(data)} bytes > {MAX}). 대화로 실어나르기엔 큽니다. "
                     f"같은 머신이면 save_result_to_path 로 디스크에 저장하세요.",
            "preview": data[:2000].decode("utf-8", "ignore"),
        }
    if as_base64:
        return {"filename_id": file_id, "base64": base64.b64encode(data).decode(), "bytes": len(data)}
    try:
        return {"filename_id": file_id, "content": data.decode("utf-8"), "bytes": len(data)}
    except UnicodeDecodeError:
        return {"filename_id": file_id, "base64": base64.b64encode(data).decode(), "bytes": len(data),
                "note": "binary content returned as base64"}


@mcp.tool()
async def list_session_jobs(session_id: str, ctx: Context) -> list:
    """세션에서 실행된 Job 이력(상태/오퍼레이션/exit_code/생성시각).
    The job history of a session — status, operation, exit_code, timestamps."""
    return await _get(ctx, f"/sessions/{session_id}/jobs")


@mcp.tool()
async def system_capabilities(ctx: Context) -> dict:
    """플랫폼 기능 카탈로그 — 오퍼레이션 수, MCP 도구 수, 웹/MCP 패리티 매트릭스,
    Claude 연결 방법 힌트. / Capability + web-MCP parity matrix + connect hints."""
    return await _get(ctx, "/system/capabilities")


# ── 전사 코퍼스 통계 ──────────────────────────────────────────────────
# 개인 식별 없는 집계다. 세션·파일·잡·리포트는 user_id 스코프라 남의 모델을 열 수 없지만,
# '조직이 무엇을 어떻게 모델링해 왔는가' 라는 분포는 공개해도 된다. 심의(HWAX 시뮬심의·
# 시험계획)가 "일반적으로" 대신 "우리 조직은 이렇게" 를 말하려면 이 층이 필요하다.
# 전부 무인자 읽기 전용 — MCP 스모크의 실호출 검사 대상이 된다.
@mcp.tool()
async def corpus_summary(ctx: Context) -> dict:
    """전사 모델 규모 — 세션·파일·잡 수와 메시 규모 분포(개인 식별 없음).
    Org-wide model scale: counts and mesh-size distribution (no personal data)."""
    return await _get(ctx, "/corpus/summary")


@mcp.tool()
async def material_usage(ctx: Context, limit: int = 30) -> dict:
    """물성 카드별 사용 모델 수 — 어떤 *MAT_ 가 실제로 몇 개 K파일에 쓰였나.
    시험 계획의 우선순위를 '민감도 추정' 이 아니라 '실사용 빈도' 로 근거화할 때 쓴다.
    Material card usage across the corpus — evidence for test prioritization."""
    return await _get(ctx, "/corpus/materials", params={"limit": limit})


@mcp.tool()
async def operation_usage(ctx: Context) -> dict:
    """오퍼레이션 실행 이력 집계 — 조직이 실제로 쓰는 전처리 관행과 성공률.
    Which preprocessing operations the org actually runs, and how they fare."""
    return await _get(ctx, "/corpus/operations")


@mcp.tool()
async def section_contact_usage(ctx: Context, limit: int = 20) -> dict:
    """요소 정식(*SECTION_)·접촉(*CONTACT_) 카드 사용 분포 — 해석 설계 관행의 근거.
    Element-formulation and contact card usage distribution."""
    return await _get(ctx, "/corpus/sections-contacts", params={"limit": limit})


@mcp.tool()
async def report_corpus(ctx: Context) -> dict:
    """해석 결과 분포 — 리포트 종류·케이스 수·반복되는 findings(설계 규칙 후보).
    Simulation-result corpus: report kinds, case counts, recurring findings."""
    return await _get(ctx, "/corpus/reports")

# ── 낙하/충격 리포트 분석 ────────────────────────────────────────────
# SmartTwin 파이프라인이 만든 deep(단건 심층)·sphere(전각도 낙하)·impact(전위치
# 부분충격) 리포트 HTML 을 받아 구조화하고, 최악 케이스/파트 리스크/소견을 질의한다.
_WORST_METRICS = {"max_stress", "max_g", "max_disp", "min_safety_factor"}


@mcp.tool()
async def ingest_report(
    session_id: str,
    filename: str,
    html_content: str,
    ctx: Context,
    kind: str | None = None,
    label: str | None = None,
    base64_encoded: bool = False,
    scenario_content: str | None = None,
    kfile_id: int | None = None,
    project: str | None = None,
    dev_rev: str | None = None,
    variation: str | None = None,
    doe: str | None = None,
) -> dict:
    """낙하/충격 리포트 HTML 을 세션에 인제스트한다(deep/sphere/impact 자동판별).

    `html_content` 는 koo_deep_report / koo_sphere_report / koo_impact_report 가 생성한
    리포트 HTML 전체다(데이터가 임베드돼 있어 그대로 파싱된다). 큰 HTML 은 base64 로
    주고 base64_encoded=true. kind 를 명시하면 자동판별을 덮어쓴다.

    선택 동반물 — scenario_content: 시뮬 조건 scenario.json 텍스트(조건 요약 + template
    으로 세션 내 K파일 자동매칭 → 한 K에 여러 결과를 매달 수 있다), kfile_id: 원본
    K파일 수동 지정, project/dev_rev/variation/doe: 과제 메타(예: S26-X / dv1)."""
    raw = base64.b64decode(html_content) if base64_encoded else html_content.encode("utf-8")
    data = {}
    for k, v in (("kind", kind), ("label", label), ("kfile_id", kfile_id),
                 ("project", project), ("dev_rev", dev_rev),
                 ("variation", variation), ("doe", doe)):
        if v is not None:
            data[k] = str(v)
    files = {"file": (filename, raw, "text/html")}
    if scenario_content:
        files["scenario"] = ("scenario.json", scenario_content.encode("utf-8"), "application/json")
    async with httpx.AsyncClient(base_url=API, timeout=180) as c:
        return _unwrap(await c.post(
            f"/sessions/{session_id}/reports",
            files=files, data=data, headers=_forward_headers(ctx),
        ))


@mcp.tool()
async def update_report_meta(
    report_id: str,
    ctx: Context,
    label: str | None = None,
    project: str | None = None,
    dev_rev: str | None = None,
    variation: str | None = None,
    doe: str | None = None,
    kfile_id: int | None = None,
    focus: str | None = None,
) -> dict:
    """리포트의 과제명(project)·개발단계(dev_rev: pre|dv1..dvr|pv1..pvr|pra|mp)·설계안·
    DOE·초점(focus 예 camera-detail)·원본 K파일 링크를 수동 설정한다(부분 갱신).
    설정해두면 DataHub 등재 때 project/stage 재입력 불필요. ""(빈문자)=그 필드 삭제."""
    body = {k: v for k, v in {
        "label": label, "project": project, "dev_rev": dev_rev,
        "variation": variation, "doe": doe, "kfile_id": kfile_id, "focus": focus,
    }.items() if v is not None}
    async with httpx.AsyncClient(base_url=API, timeout=60) as c:
        return _unwrap(await c.patch(
            f"/reports/{report_id}", json=body, headers=_forward_headers(ctx)))


@mcp.tool()
async def attach_report_scenario(report_id: str, scenario_content: str, ctx: Context) -> dict:
    """이미 인제스트된 리포트에 시뮬 조건(scenario.json 텍스트)을 첨부한다.

    조건 요약(angle_source·tolerance·예상 run 수)이 리포트에 캐시되고, template(.k
    파일명)로 세션 내 원본 K파일이 자동 매칭된다(미연결일 때)."""
    files = {"file": ("scenario.json", scenario_content.encode("utf-8"), "application/json")}
    async with httpx.AsyncClient(base_url=API, timeout=60) as c:
        return _unwrap(await c.post(
            f"/reports/{report_id}/scenario", files=files, headers=_forward_headers(ctx)))


@mcp.tool()
async def list_reports(session_id: str, ctx: Context, kfile_id: int | None = None) -> list:
    """세션에 인제스트된 리포트 목록(id·kind·프로젝트·과제메타·케이스수·시각).
    kfile_id 를 주면 그 K파일에 매달린 리포트만 — 단일 K ↔ 다수 해석결과 조회.

    ⚠ **user_id 스코프다** — 빈 배열은 '전사에 리포트가 없다'가 아니라 '이 호출자
    계정에 없다'는 뜻이다. 전사 규모의 유사 해석 유무는 corpus_summary·report_corpus
    (개인 식별 없는 집계)로 물어라. 심의 좌석이 빈 배열을 부재 증거로 오독한 실사례 있음."""
    params = {"kfile_id": kfile_id} if kfile_id is not None else None
    return await _get(ctx, f"/sessions/{session_id}/reports", params=params)


@mcp.tool()
async def report_summary(report_id: str, ctx: Context) -> dict:
    """리포트 요약 — kind, 프로젝트/DOE, sim_params, parts, findings, 전역 최악 롤업.
    무엇을 분석할 수 있는지 먼저 여기서 파악하라."""
    return await _get(ctx, f"/reports/{report_id}")


@mcp.tool()
async def report_worst_cases(
    report_id: str, ctx: Context, metric: str = "max_stress", top_n: int = 10
) -> list:
    """최악 케이스 랭킹. sphere=최악 낙하 방향, impact=최악 충격 위치, deep=단건.

    metric ∈ {max_stress, max_g, max_disp, min_safety_factor}. min_safety_factor 는
    작을수록 위험하므로 오름차순으로 준다. 각 케이스의 identity(각도/위치)와 승격 메트릭 반환."""
    if metric not in _WORST_METRICS:
        raise RuntimeError(f"metric 은 {sorted(_WORST_METRICS)} 중 하나여야 합니다.")
    order = "asc" if metric == "min_safety_factor" else "desc"
    return await _get(
        ctx, f"/reports/{report_id}/cases",
        params={"sort": metric, "order": order, "limit": top_n},
    )


@mcp.tool()
async def report_part_risk(report_id: str, ctx: Context, part_id: int | None = None) -> dict:
    """파트별 최악값과 그게 발생한 케이스(각도/위치) + 최소 안전율. part_id 를 주면 그 파트만.
    "어느 파트가 어느 방향/위치에서 가장 위험한가" 를 답한다."""
    params = {"part_id": part_id} if part_id is not None else None
    return await _get(ctx, f"/reports/{report_id}/parts", params=params)


@mcp.tool()
async def report_case(report_id: str, case_key: str, ctx: Context) -> dict:
    """한 케이스(각도/위치)의 상세 — identity + 파트별 메트릭. case_key 는
    report_worst_cases 결과의 case_key(sphere=run_folder/각도명, impact=pos_id)."""
    return await _get(ctx, f"/reports/{report_id}/cases/{case_key}")


@mcp.tool()
async def report_directional(report_id: str, ctx: Context, part_id: int | None = None) -> dict:
    """방향 취약도 — 방향 범주(sphere: 면/엣지/코너, impact: F1~F6)별 최악 응력·G.
    part_id 를 주면 그 파트의 범주별 취약도. "어느 방향이 가장 위험한가"."""
    params = {"part_id": part_id} if part_id is not None else None
    return await _get(ctx, f"/reports/{report_id}/directional", params=params)


@mcp.tool()
async def report_facets(ctx: Context) -> dict:
    """리포트 검색 facet — 어떤 kind·과제·rev·설계안·방향컨셉(doe_strategy)·조건종류·초점·
    심각도·높이가 있나 + 각 건수. 목표를 정하기 전 '먼저 뭐가 있나'를 보고 find_reports 로
    좁힌다. 소유분(관리자는 전사)."""
    return await _get(ctx, "/reports/facets")


@mcp.tool()
async def find_reports(
    ctx: Context,
    kind: str | None = None,
    project: str | None = None,
    dev_rev: str | None = None,
    variation: str | None = None,
    doe: str | None = None,
    focus: str | None = None,
    doe_strategy: str | None = None,
    scenario_type: str | None = None,
    drop_height: float | None = None,
    severity: str | None = None,
    min_worst_stress: float | None = None,
    min_worst_g: float | None = None,
    has_part: str | None = None,
    q: str | None = None,
    since: str | None = None,
    until: str | None = None,
    session_id: str | None = None,
    kfile_id: int | None = None,
    sort: str = "created_at",
    order: str = "desc",
    limit: int = 100,
) -> list:
    """조건으로 리포트 검색(전 세션, 결과 폭증 대비 다축 서버 필터) — 소유분(관리자는 전사).

    같은 전각도라도 방향 컨셉·초점·조건·높이별로 각기 골라낸다. 필터는 서버(SQL)가 처리해
    리포트가 수천 개여도 슬라이스만. 축:
    - kind, project(과제·미기입분은 임베드 project_name 폴백), dev_rev, variation, doe
    - focus(초점 예 camera-detail), doe_strategy(cuboid_26·fibonacci_162 등), scenario_type
    - drop_height(특정 높이), severity(이 심각도 이상 소견 보유), min_worst_stress/min_worst_g
    - has_part(그 부품명 포함), q(라벨/과제 텍스트), since/until(ISO), session_id, kfile_id
    - sort(created_at|worst_stress|worst_g|drop_height)·order. 먼저 report_facets 로 값을 훑어라."""
    params: dict = {"sort": sort, "order": order, "limit": limit}
    for k, v in {
        "kind": kind, "project": project, "dev_rev": dev_rev, "variation": variation, "doe": doe,
        "focus": focus, "doe_strategy": doe_strategy, "scenario_type": scenario_type,
        "drop_height": drop_height, "severity": severity,
        "min_worst_stress": min_worst_stress, "min_worst_g": min_worst_g,
        "has_part": has_part, "q": q, "since": since, "until": until,
        "session_id": session_id, "kfile_id": kfile_id,
    }.items():
        if v is not None:
            params[k] = v
    return await _get(ctx, "/reports", params=params)


@mcp.tool()
async def report_query(
    report_id: str,
    ctx: Context,
    part_id: int | None = None,
    category: str | None = None,
    angle_name: str | None = None,
    near_roll: float | None = None,
    near_pitch: float | None = None,
    near_yaw: float | None = None,
    angle_tol_deg: float | None = None,
    metric: str = "peak_stress",
    min_value: float | None = None,
    max_value: float | None = None,
    sort: str = "desc",
    limit: int = 200,
) -> dict:
    """리포트 내부 fact 드릴다운 — 서버가 부품·각도·물리량·임계로 필터해 슬라이스만 준다.

    "특정 부품이 특정 각도에서 어떤 값" 을 한 콜로. 필터:
    - part_id: 특정 부품
    - category: 방향 범주(sphere face/edge/corner, impact F1~F6)
    - angle_name: 정확한 각도명(예 F1_Back, P0001)
    - near_roll/near_pitch/near_yaw + angle_tol_deg: 각도 근접(대원거리 ±도)
    - metric: peak_stress|peak_g|peak_disp|peak_strain|peak_principal|min_principal|peak_vm_strain|safety_factor
    - min_value/max_value: 값 임계, sort(desc|asc), limit
    반환: (case_key·각도·부품·물리량·값·at_time) 평탄 fact + n_matched·truncated.
    전 케이스를 LLM 이 훑지 않아도 되니 대형 sphere(수천 케이스)에서 효율적이다."""
    params: dict = {"metric": metric, "sort": sort, "limit": limit}
    for k, v in {
        "part_id": part_id, "category": category, "angle_name": angle_name,
        "near_roll": near_roll, "near_pitch": near_pitch, "near_yaw": near_yaw,
        "angle_tol_deg": angle_tol_deg, "min_value": min_value, "max_value": max_value,
    }.items():
        if v is not None:
            params[k] = v
    return await _get(ctx, f"/reports/{report_id}/query", params=params)


@mcp.tool()
async def report_scatter(
    report_id: str, ctx: Context, metric: str = "peak_stress", part_id: int | None = None
) -> dict:
    """방향 섭동 산포 분석(sphere 전용) — 26면 낙하 주변 방향 섭동에 대한 응답 산포.

    케이스를 최근접 26 정준방향(면/엣지/코너)으로 묶어 방향별 metric 산포(n·mean·std·
    CoV·최악)와 민감도(가장 산포 큰 방향)를 낸다. metric ∈ {peak_stress,peak_g,peak_disp}.
    방향당 표본이 1개뿐(순수 26면)이면 degenerate=true(산포 0) — 섭동 DOE 라야 의미 있다."""
    if metric not in ("peak_stress", "peak_g", "peak_disp"):
        raise RuntimeError("metric 은 peak_stress/peak_g/peak_disp 중 하나여야 합니다.")
    params = {"metric": metric}
    if part_id is not None:
        params["part_id"] = part_id
    return await _get(ctx, f"/reports/{report_id}/scatter", params=params)


@mcp.tool()
async def report_energy_flow(report_id: str, ctx: Context, case_key: str | None = None) -> dict:
    """에너지/접촉 상세(원본 재파싱). deep=에너지 밸런스(hourglass/energy_ratio)·접촉력(rcforc)·
    Newton-3 신뢰도, sphere/impact=하중경로 그래프(impactor→parts 전파, 접촉 엣지 work).
    deep 은 case_key 불필요, sphere/impact 는 case_key 로 특정 방향/위치 지정."""
    params = {"case_key": case_key} if case_key else None
    return await _get(ctx, f"/reports/{report_id}/energy", params=params)


@mcp.tool()
async def report_geometry(report_id: str, ctx: Context) -> dict:
    """공간 컨텍스트(부품 위치·시각화용) — impact=디바이스 외곽선(device_outline)+파트별
    footprint(XY 다각형)+z범위. "부품이 어디 있나"·충격 위치를 좌표로 안다. sphere/deep 은
    각도 기반이라 부품 형상은 원본 렌더에만 있다(geometry 비어 있음)."""
    return await _get(ctx, f"/reports/{report_id}/geometry")


@mcp.tool()
async def report_part_series(report_id: str, case_key: str, part_id: int, ctx: Context) -> dict:
    """한 케이스·파트의 시계열(원본 재파싱, 다운샘플) — 응력/변형률/G/변위 시간이력."""
    return await _get(ctx, f"/reports/{report_id}/cases/{case_key}/series", params={"part_id": part_id})


@mcp.tool()
async def report_findings(report_id: str, ctx: Context, severity: str | None = None) -> list:
    """리포트의 위험 소견(CRITICAL/WARNING/INFO). severity 로 필터 가능.
    항복 초과·과도 G 등 자동 판정된 항목을 준다(sphere/impact)."""
    params = {"severity": severity} if severity else None
    return await _get(ctx, f"/reports/{report_id}/findings", params=params)


@mcp.tool()
async def compare_reports(report_ids: list, ctx: Context, part_id: int | None = None) -> dict:
    """여러 리포트(리비전/조건)를 파트별 최악 응력으로 비교한다(federate 식 비교).

    각 리포트의 part_risk 를 모아 파트별로 리포트 간 최악 응력·안전율을 나란히 놓는다.
    같은 kind 끼리 비교해야 의미가 있다(sphere↔sphere, impact↔impact)."""
    if not report_ids or len(report_ids) < 2:
        raise RuntimeError("비교하려면 report_ids 가 2개 이상이어야 합니다.")
    rows = {}
    kinds = {}
    for rid in report_ids:
        summ = await _get(ctx, f"/reports/{rid}")
        kinds[rid] = summ.get("kind")
        pr = await _get(ctx, f"/reports/{rid}/parts",
                        params={"part_id": part_id} if part_id is not None else None)
        for p in pr.get("parts", []):
            key = p.get("part_id")
            slot = rows.setdefault(key, {"part_id": key, "part_name": p.get("part_name"), "by_report": {}})
            slot["by_report"][rid] = {
                "worst_stress": p.get("worst_stress", {}).get("value"),
                "worst_stress_case": p.get("worst_stress", {}).get("case_key"),
                "min_safety_factor": p.get("min_safety_factor"),
            }
    if len(set(kinds.values())) > 1:
        note = f"⚠ 서로 다른 kind 비교({kinds}) — 물리적으로 다른 시험일 수 있습니다."
    else:
        note = None
    return {"kinds": kinds, "note": note, "parts": sorted(rows.values(), key=lambda r: str(r["part_id"]))}


@mcp.tool()
async def publish_report_to_datahub(
    report_id: str,
    project: str,
    stage: str,
    ctx: Context,
    variation: str | None = None,
    doe: str | None = None,
    unit: str = "mm-t-s",
    title: str | None = None,
) -> dict:
    """리포트를 AI Data Hub 에 범용 sim_report 데이터 레코드로 등재한다.

    project=과제코드, stage=개발단계(pre|dv1..dvr|pv1..pvr|pra|mp), variation=설계안,
    doe=DOE 참조(study[:case]). 리포트 요약·소견·최악케이스·파트를 content 로 싣고 원본
    HTML 을 첨부한다. 도메인 무관 스키마라 검색·리비전 비교에 그대로 얹힌다."""
    body = {"project": project, "stage": stage, "unit": unit}
    if variation:
        body["variation"] = variation
    if doe:
        body["doe"] = doe
    if title:
        body["title"] = title
    return await _post(ctx, f"/reports/{report_id}/publish-datahub", body)


@mcp.tool()
async def delete_report(report_id: str, ctx: Context) -> dict:
    """인제스트된 리포트를 삭제한다(원본 HTML 포함). / Delete an ingested report."""
    return await _delete(ctx, f"/reports/{report_id}")


if __name__ == "__main__":
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    mcp.settings.host = host
    port = int(os.environ.get("KOORM_MCP_PORT", os.environ.get("MCP_PORT", "8701")))
    mcp.settings.port = port

    # DNS-rebinding 보호는 항상 ON으로 두되 허용 Host를 명시한다. 리버스 프록시
    # (nginx, HEAX Caddy)는 Host를 포트 없이(예: '127.0.0.1') 보내기도 하므로
    # 포트 유무 양쪽을 기본 허용에 넣는다 — 이게 없으면 프록시 경유가 421로 막힌다.
    from mcp.server.transport_security import TransportSecuritySettings

    extra = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    allowed = extra + [
        "127.0.0.1", "localhost", "::1",
        f"127.0.0.1:{port}", f"localhost:{port}",
    ]
    if host not in ("127.0.0.1", "localhost", "::1") and not extra:
        print(
            "⚠ MCP bound to non-localhost but MCP_ALLOWED_HOSTS is empty — 외부 도메인으로 "
            "접근하려면 MCP_ALLOWED_HOSTS(예: 'mcp.example.com')를 설정하라. 프록시(nginx/Caddy) "
            "뒤에서는 프록시가 보내는 Host를 넣어야 한다.",
            flush=True,
        )
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed,
        allowed_origins=[],
    )

    mcp.run(transport="streamable-http")
