# 레시피 서비스 — 제안(정적 검사·자기 시험·호환 관문) · 검색 · 실행 잡 · 평가 · 등록 관문 · 내리기.
"""Service layer for recipes. See docs/01-plan/features/recipes-1026.plan.md.

A recipe accumulates without rebuilds: an LLM proposes a Python function, the
sandbox self-tests it, a real run gathers evidence, and if a positive evaluation
lands, the automatic gate registers it and exports it to git.
"""
from __future__ import annotations

import ast
import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Optional

import ulid
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ImpactCase, ImpactReport, Recipe, RecipeRun, RecipeVersion, Session
from app.recipes import registry
from app.recipes.check import RecipeCheckError, check_recipe
from app.recipes.sandbox import run_in_sandbox
from app.modules.reports import services as report_svc

logger = logging.getLogger("koorm.recipes")

_KINDS = {"deep", "sphere", "impact"}
_NEEDS = {"data"}
_MIN_NOTE = 20   # 등록 근거가 되는 평가 글의 최소 길이


class RecipeServiceError(Exception):
    """사용자에게 그대로 보여 줄 수 있는 까닭(라우트가 400 으로 바꾼다)."""


# ── 메타 정규화 ───────────────────────────────────────────────────────
def normalize_meta(meta: dict | None) -> dict:
    meta = dict(meta or {})
    kinds = meta.get("kinds") or sorted(_KINDS)
    if not isinstance(kinds, list) or any(k not in _KINDS for k in kinds):
        raise RecipeServiceError(f"kinds 는 {sorted(_KINDS)} 의 부분집합이어야 한다")
    needs = meta.get("needs") or []
    if not isinstance(needs, list) or any(n not in _NEEDS for n in needs):
        raise RecipeServiceError(f"needs 는 {sorted(_NEEDS)} 안에서만(지금은 data 뿐)")
    inputs = meta.get("inputs") or {}
    mn = int(inputs.get("min_reports", 1))
    mx = int(inputs.get("max_reports", 8))
    if mn < 0 or mx < mn:
        raise RecipeServiceError("inputs.min_reports·max_reports 가 올바르지 않다")
    return {
        "title": str(meta.get("title", ""))[:200],
        "question": str(meta.get("question", ""))[:1000],
        "when_to_use": str(meta.get("when_to_use", ""))[:1000],
        "kinds": sorted(set(kinds)),
        "needs": sorted(set(needs)),
        "inputs": {"min_reports": mn, "max_reports": mx},
        "params": meta.get("params") or {},
        "tags": [str(t)[:40] for t in (meta.get("tags") or [])][:12],
    }


# ── 조회 ──────────────────────────────────────────────────────────────
async def get_recipe(db: AsyncSession, name: str) -> Optional[Recipe]:
    return (await db.execute(select(Recipe).where(Recipe.name == name))).scalars().first()


async def get_version(db: AsyncSession, recipe_id: int, version: int) -> Optional[RecipeVersion]:
    return (await db.execute(
        select(RecipeVersion).where(
            RecipeVersion.recipe_id == recipe_id, RecipeVersion.version == version
        )
    )).scalars().first()


async def _versions(db: AsyncSession, recipe_id: int) -> list[RecipeVersion]:
    return list((await db.execute(
        select(RecipeVersion).where(RecipeVersion.recipe_id == recipe_id)
        .order_by(RecipeVersion.version.desc())
    )).scalars())


async def search(db: AsyncSession, user_id: int, *, q: str = "", kind: str = "",
                 tag: str = "", limit: int = 50) -> list[dict]:
    """등록된(그리고 자기 소유의 초안·후보) 레시피 — 검색어·종류·태그로 좁힌다.

    순위: 등록 판 가운데 '쓸모 있었다' 평가가 많은 것부터(경험이 쌓이는 길). 내려진 것은 뺀다.
    """
    rows = list((await db.execute(
        select(Recipe).where(Recipe.deprecated_at.is_(None))
    )).scalars())
    out = []
    for r in rows:
        cur = None
        if r.current_version is not None:
            cur = await get_version(db, r.id, r.current_version)
        visible = cur is not None
        mine_vers = []
        if not visible or r.created_by == user_id:
            mine_vers = [v for v in await _versions(db, r.id)
                         if v.status in ("draft", "candidate") and r.created_by == user_id]
        if not visible and not mine_vers:
            continue
        meta = (cur.meta if cur else (mine_vers[0].meta if mine_vers else {})) or {}
        hay = " ".join([r.name, meta.get("title", ""), meta.get("question", ""),
                        meta.get("when_to_use", ""), " ".join(meta.get("tags", []))]).lower()
        if q and q.lower() not in hay:
            continue
        if kind and kind not in (meta.get("kinds") or []):
            continue
        if tag and tag not in (meta.get("tags") or []):
            continue
        useful_n = 0
        if cur is not None:
            useful_n = (await db.execute(
                select(func.count()).select_from(RecipeRun).where(
                    RecipeRun.version_id == cur.id, RecipeRun.useful.is_(True))
            )).scalar() or 0
        out.append({
            "name": r.name, "domain": r.domain,
            "registered": visible, "current_version": r.current_version,
            "meta": meta, "useful_count": int(useful_n),
            "has_draft": bool(mine_vers),
        })
    out.sort(key=lambda d: (not d["registered"], -d["useful_count"], d["name"]))
    return out[:limit]


async def get_detail(db: AsyncSession, name: str, user_id: int) -> dict:
    r = await get_recipe(db, name)
    if r is None:
        raise RecipeServiceError(f"레시피를 찾을 수 없다: {name}")
    vers = await _versions(db, r.id)
    def _vis(v: RecipeVersion) -> bool:
        return v.status in ("registered", "superseded") or r.created_by == user_id
    return {
        "name": r.name, "domain": r.domain, "origin": r.origin,
        "current_version": r.current_version,
        "deprecated_at": r.deprecated_at.isoformat() if r.deprecated_at else None,
        "deprecated_reason": r.deprecated_reason,
        "versions": [{
            "version": v.version, "status": v.status, "meta": v.meta,
            "checks": v.checks, "gate": v.gate,
            "code": v.code if _vis(v) else None,
            "created_at": v.created_at.isoformat(),
            "registered_at": v.registered_at.isoformat() if v.registered_at else None,
        } for v in vers],
    }


async def get_version_code(db: AsyncSession, name: str, version: int | None, user_id: int) -> tuple[Recipe, RecipeVersion]:
    """실행·등록이 쓸 판을 고른다. version 미지정이면 등록된 current_version.

    등록 판은 누구나, 초안·후보는 올린 사람만. 없으면 RecipeServiceError.
    """
    r = await get_recipe(db, name)
    if r is None:
        raise RecipeServiceError(f"레시피를 찾을 수 없다: {name}")
    if version is None:
        if r.current_version is None:
            raise RecipeServiceError(f"{name} 에 등록된 판이 없다 — version 을 지정하라")
        version = r.current_version
    v = await get_version(db, r.id, version)
    if v is None:
        raise RecipeServiceError(f"{name} v{version} 를 찾을 수 없다")
    if v.status not in ("registered", "superseded") and r.created_by != user_id:
        raise RecipeServiceError(f"{name} v{version} 는 아직 등록 전이라 올린 사람만 쓸 수 있다")
    return r, v


# ── 제안 ──────────────────────────────────────────────────────────────
def _rename_tests(code: str, prefix: str) -> str:
    """최상위 test_ 함수 이름 앞에 prefix 를 붙인다(호환 관문에서 앞 판 시험을 섞어 돌리려고)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ""
    out = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"):
            seg = ast.get_source_segment(code, n)
            if seg:
                out.append(re.sub(r"^def\s+test_", f"def {prefix}", seg, count=1))
    return "\n\n".join(out)


async def propose(db: AsyncSession, user, *, name: str, code: str, meta: dict | None) -> dict:
    """레시피 판을 올린다 — 정적 검사 → 저장 → 자기 시험 + 앞 판 호환 시험(샌드박스) → candidate/draft.

    이름이 처음이면 레시피를 만들고, 있으면 다음 판 번호로 올린다(누구나 새 판을 올릴 수 있다).
    """
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", name):
        raise RecipeServiceError("이름은 소문자·숫자·밑줄 3~64자, 첫 글자는 소문자여야 한다")
    try:
        info = check_recipe(code)
    except RecipeCheckError as exc:
        raise RecipeServiceError(f"정적 검사 실패: {exc}") from exc
    nmeta = normalize_meta(meta)

    r = await get_recipe(db, name)
    if r is None:
        r = Recipe(name=name, domain="report", created_by=user.id, origin="platform")
        db.add(r)
        await db.flush()
    # 앞 등록 판(호환 관문의 기준)
    prev = None
    if r.current_version is not None:
        prev = await get_version(db, r.id, r.current_version)

    next_v = ((await db.execute(
        select(func.max(RecipeVersion.version)).where(RecipeVersion.recipe_id == r.id)
    )).scalar() or 0) + 1

    combined = code
    if prev is not None:
        prev_tests = _rename_tests(prev.code, "test_prev_")
        if prev_tests:
            combined = code + "\n\n# ── 앞 판 호환 시험 ──\n" + prev_tests

    sb = await run_in_sandbox(code=combined, mode="selftest")
    checks = {
        "static_ok": True, "tests": info["tests"],
        "selftest_ok": sb.ok, "tests_passed": sb.tests_passed,
        "compat_base": (prev.version if prev else None),
        "compat_ok": sb.ok if prev is not None else None,
        "layers": sb.layers, "error": sb.error, "stdout_tail": sb.stdout_tail,
    }
    status = "candidate" if sb.ok else "draft"
    v = RecipeVersion(
        recipe_id=r.id, version=next_v, code=code,
        code_sha256=registry.sha256_text(code), meta=nmeta,
        status=status, checks=checks, created_by=user.id,
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    similar = await search(db, user.id, q=(nmeta.get("tags") or [""])[0], limit=5)
    return {
        "name": name, "version": next_v, "status": status,
        "checks": checks,
        "message": ("자기 시험 통과 — 후보가 되었다. 실데이터로 recipe_run 한 뒤 평가를 붙이면 등록 관문에 걸 수 있다."
                    if sb.ok else f"자기 시험 실패 — 초안으로 둔다: {sb.error}"),
        "similar": [s["name"] for s in similar if s["name"] != name][:5],
    }


# ── 리포트 번들 ───────────────────────────────────────────────────────
def _report_meta(r: ImpactReport) -> dict:
    return {
        "id": r.id, "kind": r.kind, "label": r.label,
        "project_name": r.project_name, "drop_height": r.drop_height,
        "scenario_type": r.scenario_type, "doe_strategy": r.doe_strategy,
        "generator": r.generator, "generator_version": r.generator_version,
        "worst_stress": r.worst_stress, "worst_g": r.worst_g,
        "max_severity": r.max_severity, "n_cases": r.n_cases,
        "sim_params": r.sim_params, "scenario": r.scenario, "eng_meta": r.eng_meta,
        "parts": r.parts, "summary": r.summary, "findings": r.findings,
    }


async def build_report_bundle(db: AsyncSession, report: ImpactReport, dst: Path, *, with_data: bool) -> str:
    """리포트 하나를 번들 디렉터리로 쓴다(meta.json · cases.json · 필요 시 data.json). kind 반환."""
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "meta.json").write_text(json.dumps(_report_meta(report), ensure_ascii=False), encoding="utf-8")
    cases = list((await db.execute(
        select(ImpactCase).where(ImpactCase.report_id == report.id)
    )).scalars())
    case_rows = [{
        "case_key": c.case_key, "identity": c.identity, "num_states": c.num_states,
        "success": c.success, "parts_metrics": c.parts_metrics,
        "max_stress": c.max_stress, "max_g": c.max_g, "max_disp": c.max_disp,
        "min_safety_factor": c.min_safety_factor,
    } for c in cases]
    (dst / "cases.json").write_text(json.dumps(case_rows, ensure_ascii=False), encoding="utf-8")
    if with_data:
        data, _kind = await report_svc._load_html_data(db, report)
        (dst / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return report.kind


# ── 실행 잡 생성 ──────────────────────────────────────────────────────
async def create_run(db: AsyncSession, user, session: Session, *, recipe_name: str,
                     version: int | None, report_ids: list[str], params: dict | None):
    """레시피 실행 잡을 만든다 — 판을 고르고, 리포트 접근을 확인하고, Job + RecipeRun(queued)을 남긴다.

    실제 실행은 워커가 한다(operation="recipe"). 돌려주는 것은 (job, run).
    """
    from app.models import Job   # 지연 import — 순환 피함

    r, v = await get_version_code(db, recipe_name, version, user.id)
    meta = v.meta or {}
    mn = (meta.get("inputs") or {}).get("min_reports", 1)
    mx = (meta.get("inputs") or {}).get("max_reports", 8)
    if not (mn <= len(report_ids) <= mx):
        raise RecipeServiceError(f"리포트 수가 {mn}~{mx} 여야 한다(받은 것 {len(report_ids)})")
    kinds_ok = set(meta.get("kinds") or _KINDS)

    report_kinds = []
    for rid in report_ids:
        rep = await report_svc.get_readable_report(db, user.id, rid)
        if rep is None:
            raise RecipeServiceError(f"리포트를 찾을 수 없거나 권한이 없다: {rid}")
        if rep.kind not in kinds_ok:
            raise RecipeServiceError(f"이 레시피는 {sorted(kinds_ok)} 만 받는다 — {rid} 는 {rep.kind}")
        report_kinds.append(rep.kind)

    run_id = ulid.new().str
    job = Job(
        id=ulid.new().str, session_id=session.id, user_id=user.id,
        operation="recipe",
        args={"recipe": recipe_name, "version": v.version, "recipe_id": r.id,
              "version_id": v.id, "run_id": run_id, "report_ids": report_ids,
              "params": params or {}, "with_data": ("data" in (meta.get("needs") or []))},
        status="queued",
    )
    db.add(job)
    run = RecipeRun(
        id=run_id, recipe_id=r.id, version_id=v.id, version=v.version,
        job_id=job.id, session_id=session.id, user_id=user.id,
        report_ids=report_ids, report_kinds=report_kinds, params=params or {},
        status="queued",
    )
    db.add(run)
    await db.commit()
    await db.refresh(job)
    await db.refresh(run)
    return job, run


# ── 워커가 부르는 실행 ────────────────────────────────────────────────
async def execute_run(db: AsyncSession, job) -> None:
    """워커(_run_recipe)가 부른다 — 번들을 만들고 샌드박스에서 돌려 RecipeRun·Job 을 적는다."""
    from datetime import datetime, timezone
    from app.models import SessionFile
    from app.shared import storage

    args = job.args or {}
    run = await db.get(RecipeRun, args.get("run_id"))
    v = await db.get(RecipeVersion, args.get("version_id"))
    if run is None or v is None:
        job.status = "failed"
        job.error_summary = "recipe run/version row missing"
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()
        return
    run.status = "running"
    await db.commit()

    work_dir = storage.ensure_session_dir(job.user_id, job.session_id)
    tmp = Path(tempfile.mkdtemp(prefix="recipe_bundles_"))
    report_dirs: list[str] = []
    try:
        for i, rid in enumerate(args.get("report_ids") or []):
            rep = await db.get(ImpactReport, rid)
            if rep is None:
                raise RecipeServiceError(f"리포트가 사라졌다: {rid}")
            d = tmp / f"r{i}"
            await build_report_bundle(db, rep, d, with_data=bool(args.get("with_data")))
            report_dirs.append(str(d))

        sb = await run_in_sandbox(
            code=v.code, mode="run", report_dirs=report_dirs, params=args.get("params") or {},
        )

        # 결과를 세션 산출 파일로 — 다운로드되고, 큰 결과의 정본이다.
        out_name = f"recipe_{args['recipe']}_v{v.version}_{run.id}.json"
        out_path = work_dir / out_name
        full = {"ok": sb.ok, "error": sb.error, "result": sb.result,
                "layers": sb.layers, "elapsed_ms": sb.elapsed_ms}
        out_path.write_text(json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8")
        sha = storage.sha256_of(out_path)
        rel = f"{storage.session_rel_dir(job.user_id, job.session_id)}/{out_name}"
        existing = (await db.execute(
            select(SessionFile).where(SessionFile.session_id == job.session_id,
                                      SessionFile.filename == out_name)
        )).scalar_one_or_none()
        if existing is not None:
            existing.kind = "output"; existing.origin_job_id = job.id
            existing.size_bytes = out_path.stat().st_size; existing.sha256 = sha
            await db.flush()
            fid = existing.id
        else:
            sf = SessionFile(session_id=job.session_id, filename=out_name, rel_path=rel,
                             kind="output", origin_job_id=job.id,
                             size_bytes=out_path.stat().st_size, sha256=sha)
            db.add(sf)
            await db.flush()
            fid = sf.id

        # DB 에 담는 결과는 상한 — 넘으면 앞부분만, 전체는 산출 파일에.
        cap = settings.recipe_result_cap_kb * 1024
        result = sb.result
        truncated = False
        if result is not None and len(json.dumps(result, ensure_ascii=False)) > cap:
            result = {"note": "결과가 커서 DB 에는 담지 않았다 — 산출 파일을 보라", "output_file_id": fid}
            truncated = True

        run.status = "succeeded" if sb.ok else "failed"
        run.result = result
        run.result_truncated = truncated
        run.output_file_id = fid
        run.error = sb.error
        run.stdout_tail = sb.stdout_tail
        run.elapsed_ms = sb.elapsed_ms
        run.sandbox = sb.layers
        run.finished_at = datetime.now(timezone.utc)

        job.status = "succeeded" if sb.ok else "failed"
        job.output_file_ids = [fid]
        job.error_summary = None if sb.ok else (sb.error or "recipe run failed")[:2000]
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()
    except Exception as exc:   # noqa: BLE001 — 실패도 기록으로 남긴다
        logger.exception("recipe run %s failed", run.id if run else "?")
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {exc}"[:2000]
        run.finished_at = datetime.now(timezone.utc)
        job.status = "failed"
        job.error_summary = run.error
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


# ── 평가 ──────────────────────────────────────────────────────────────
async def evaluate(db: AsyncSession, user, *, run_id: str, useful: bool, note: str) -> dict:
    from datetime import datetime, timezone
    run = await db.get(RecipeRun, run_id)
    if run is None:
        raise RecipeServiceError(f"실행 기록을 찾을 수 없다: {run_id}")
    if run.user_id != user.id and not user.is_system_admin:
        raise RecipeServiceError("자기 실행만 평가할 수 있다")
    run.useful = bool(useful)
    run.note = (note or "")[:2000]
    run.evaluated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"run_id": run_id, "useful": run.useful, "note": run.note}


# ── 등록 관문 ─────────────────────────────────────────────────────────
async def register(db: AsyncSession, user, *, name: str, version: int | None) -> dict:
    """자동 관문 — 통과하면 LLM 이 바로 등록한다(사용자 선택: LLM 자동 + 자동 관문).

    관문: 정적 검사 · 자기 시험 · (있으면)앞 판 호환 시험 통과 + 이 판으로 실데이터 실행 성공 ≥1 +
    useful=true 평가(글 20자↑) ≥1. 통과하면 등록 · 앞 판은 물러나고(superseded) · 파일로 내보낸다.
    """
    from datetime import datetime, timezone

    r, v = await get_version_code(db, name, version, user.id)
    reasons = []
    ck = v.checks or {}
    if not ck.get("static_ok"):
        reasons.append("정적 검사 미통과")
    if not ck.get("selftest_ok"):
        reasons.append("자기 시험 미통과")
    if ck.get("compat_ok") is False:
        reasons.append(f"앞 판(v{ck.get('compat_base')}) 호환 시험 미통과")

    runs = list((await db.execute(
        select(RecipeRun).where(RecipeRun.version_id == v.id)
    )).scalars())
    ok_runs = [x for x in runs if x.status == "succeeded"]
    good_evals = [x for x in ok_runs if x.useful is True and len((x.note or "").strip()) >= _MIN_NOTE]
    if not ok_runs:
        reasons.append("이 판으로 성공한 실데이터 실행이 없다")
    if not good_evals:
        reasons.append(f"'쓸모 있었다' 평가(글 {_MIN_NOTE}자↑)가 없다")

    if reasons:
        raise RecipeServiceError("등록 관문 미통과: " + " · ".join(reasons))

    prev_v = r.current_version
    gate = {
        "registered_by": user.id,
        "evidence_runs": [x.id for x in ok_runs][:20],
        "evidence_evals": [{"run_id": x.id, "note": x.note} for x in good_evals][:10],
        "superseded": prev_v,
        "checks": {k: ck.get(k) for k in ("selftest_ok", "compat_ok", "compat_base")},
    }
    if prev_v is not None and prev_v != v.version:
        old = await get_version(db, r.id, prev_v)
        if old is not None and old.status == "registered":
            old.status = "superseded"
    v.status = "registered"
    v.gate = gate
    v.registered_at = datetime.now(timezone.utc)
    r.current_version = v.version
    await db.commit()

    try:
        p = registry.export_version(name, v.version, v.code, v.meta, gate)
        exported = str(p)
    except OSError as exc:
        logger.warning("recipe %s v%s 파일 내보내기 실패: %s", name, v.version, exc)
        exported = None
    return {
        "name": name, "version": v.version, "status": "registered",
        "superseded": prev_v, "exported": exported,
        "message": "등록했다. git 반영은 tools/recipes_publish.sh 로(서버는 커밋·푸시하지 않는다).",
    }


async def deprecate(db: AsyncSession, user, *, name: str, reason: str) -> dict:
    from datetime import datetime, timezone
    r = await get_recipe(db, name)
    if r is None:
        raise RecipeServiceError(f"레시피를 찾을 수 없다: {name}")
    if r.created_by != user.id and not user.is_system_admin:
        raise RecipeServiceError("올린 사람 또는 관리자만 내릴 수 있다")
    r.deprecated_at = datetime.now(timezone.utc)
    r.deprecated_reason = (reason or "")[:1000]
    await db.commit()
    return {"name": name, "deprecated": True, "reason": r.deprecated_reason}


# ── 기동 때 git 에서 읽어 들이기 ──────────────────────────────────────
async def load_exported(db: AsyncSession) -> int:
    """platform/recipes/*/ 의 등록 판을 DB 에 없으면 넣는다(origin=git). 넣은 수 반환."""
    from datetime import datetime, timezone
    added = 0
    for doc in registry.iter_exported():
        name, version, code = doc["name"], int(doc["version"]), doc["code"]
        sha = registry.sha256_text(code)
        r = await get_recipe(db, name)
        if r is None:
            r = Recipe(name=name, domain="report", created_by=None, origin="git")
            db.add(r)
            await db.flush()
        existing = await get_version(db, r.id, version)
        if existing is not None:
            continue
        v = RecipeVersion(
            recipe_id=r.id, version=version, code=code, code_sha256=sha,
            meta=doc.get("meta") or {}, status="registered",
            checks={"static_ok": True, "selftest_ok": True, "from_git": True},
            gate=doc.get("gate") or {"from_git": True},
            registered_at=datetime.now(timezone.utc),
        )
        db.add(v)
        if r.current_version is None or version > r.current_version:
            r.current_version = version
        added += 1
    if added:
        await db.commit()
    return added
