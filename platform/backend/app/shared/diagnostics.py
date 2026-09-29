# 실패한 잡 하나를 "재현 없이 고칠 수 있는" 한 덩어리로 묶는다 — 요약 텍스트와 zip 두 가지
"""왜 이 모듈이 있나 (2026-09-29, 진단 체계).

사용자는 서버 셸이 없고 우리는 사용자 화면이 없다. 그 사이를 잇는 것이 이 모듈의 전부다.
성공 기준은 하나 — **재현 없이 고칠 수 있는가.** 번들을 열었을 때 "어느 빌드가 · 어떤 덱에 ·
어떤 argv 로 · 무엇을 출력하고 · 어디서 멈췄는지" 가 다 있어야 한다.

⚠ **덱 본문은 기본으로 담지 않는다.** 고객 CAE 모델이라 형상·물성이 IP 다. 에러가 가리키는 줄만
`deck_lines=True` 로 **사용자가 켤 때** 담는다(전후 2줄).

⚠ **레다ct 는 지우는 것이 아니라 접는 것이다.** 절대 경로를 `<storage>/…` 로 접어야 우리가 구조를
읽을 수 있다. 통째로 지우면 "어느 파일이었나" 를 잃는다.

⚠ **행이 사라진 잡은 이 모듈이 다루지 않는다.** 잡이 도는 중에 세션이 지워지면 `ON DELETE CASCADE`
로 행이 날아가는데(실측 4건), 행이 없으면 **소유권을 확인할 방법이 없다.** 인증 없이 내주면 접근
통제 구멍이 된다. 그 부류는 `runner_loop._note_crash` 가 잡의 stderr 파일에 적고 워커가 ERROR 줄을
남기는 쪽이 정본이다.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

SCHEMA = "koorm-diagnostic/1"

# 로그·요약에 실을 꼬리 길이. JSON 은 사람이 읽는 요약이라 짧게, zip 은 전문을 따로 넣는다.
TAIL_CHARS = 4000
# zip 안 로그 한 개의 상한. 폭주한 잡이 수백 MB 를 낼 수 있다.
MAX_LOG_BYTES = 2 << 20
# 에러가 가리키는 줄을 담을 때의 상한(줄 묶음 수 · 총 줄 수).
MAX_LINE_GROUPS = 20
MAX_DECK_LINES = 200

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 이 플랫폼의 API 토큰은 `kr_` 로 시작한다.
_KRTOKEN = re.compile(r"\bkr_[A-Za-z0-9_-]{8,}")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+")
# KooRemapper 는 `line 10 *SECTION: …` 꼴로 줄을 가리킨다.
_LINE_REF = re.compile(r"\bline\s+(\d+)\b")


def _fold_paths(text: str) -> str:
    """절대 경로를 접는다. **긴 것부터** 바꿔야 접두사가 서로를 먹지 않는다.

    ⚠ 스토리지는 **심링크일 수 있다.** 실측 — `platform/storage` 가
    `/data/svc/kooremapper/storage` 를 가리킨다(D9 이전). 해석한 형태만 접으면 실제 경로
    (`/home/…/platform/storage/…`)는 그대로 남아 `<home>` 으로 접히고, 그러면 번들을 읽는 쪽이
    "이게 스토리지인지" 를 알 수 없다. **양쪽 다** 접는다.
    """
    subs: list[tuple[str, str]] = [(str(settings.storage_dir), "<storage>")]
    try:
        subs.append((str(settings.storage_dir.resolve()), "<storage>"))
    except OSError:
        pass
    # 컨테이너 안에서는 리포가 /workspace 로 바인드된다.
    subs.append(("/workspace", "<repo>"))
    try:
        subs.append((str(Path.home()), "<home>"))
    except RuntimeError:
        pass
    for src, dst in sorted(subs, key=lambda p: len(p[0]), reverse=True):
        if src and src != "/":
            text = text.replace(src, dst)
    return text


def redact(text: str) -> str:
    """번들에 실을 모든 문자열이 지나는 자리. 경로는 접고, 이메일·토큰은 지운다."""
    if not text:
        return ""
    text = _fold_paths(text)
    text = _EMAIL.sub("<email>", text)
    text = _KRTOKEN.sub("<token>", text)
    text = _BEARER.sub("Bearer <token>", text)
    return text


def _redact_deep(value):
    """dict/list 를 타고 들어가 문자열마다 `redact` 를 걸친다."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: _redact_deep(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_deep(v) for v in value]
    return value


def _read_contained(path: str | None, *, limit: int | None = None) -> str:
    """스토리지 안의 파일만 읽는다(기존 `/logs` 라우트와 같은 규율)."""
    if not path:
        return ""
    try:
        rp = Path(path).resolve()
        root = settings.storage_dir.resolve()
        if root not in rp.parents:
            return ""
        data = rp.read_bytes()
        if limit is not None and len(data) > limit:
            # 앞이 아니라 **뒤**를 남긴다 — 실패는 끝에서 말한다.
            data = data[-limit:]
        return data.decode("utf-8", errors="replace")
    except OSError:
        return ""


def _iso(dt) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def instance_log_paths() -> list[Path]:
    """API 인스턴스 로그 후보. 못 찾으면 빈 목록이다 — 그 사실도 번들에 적는다.

    apptainer 가 `~/.apptainer/instances/logs/<host>/<user>/koorm_api.{out,err}` 에 쓰고 일별로
    회전한다(관측: 14세대). 컨테이너 안에서 홈이 안 보이는 배치도 있으므로 환경변수로 덮을 수 있게
    둔다.
    """
    override = (settings.instance_log_dir or "").strip()
    dirs: list[Path] = []
    if override:
        dirs.append(Path(override))
    else:
        try:
            base = Path.home() / ".apptainer" / "instances" / "logs"
            dirs.extend(p for p in base.glob("*/*") if p.is_dir())
        except (OSError, RuntimeError):
            pass
    out: list[Path] = []
    for d in dirs:
        for name in ("koorm_api.out", "koorm_api.err"):
            p = d / name
            try:
                if p.is_file():
                    out.append(p)
            except OSError:
                continue
    return out


def server_log_lines(correlator: str, *, limit: int = 400) -> tuple[list[str], str | None]:
    """상관자가 붙은 서버 줄만 고른다. 읽지 못하면 그 사실을 문장으로 돌려준다.

    ⚠ **타 사용자 줄을 섞지 않는다.** 그래서 파일을 통째로 넣지 않고 상관자로 고른다.
    """
    paths = instance_log_paths()
    if not paths:
        return [], "서버 로그를 찾지 못했다 — 인스턴스 로그 경로가 이 프로세스에서 보이지 않는다."
    picked: list[str] = []
    for p in paths:
        try:
            data = p.read_bytes()
        except OSError:
            continue
        if len(data) > MAX_LOG_BYTES:
            data = data[-MAX_LOG_BYTES:]
        for line in data.decode("utf-8", errors="replace").splitlines():
            if correlator and correlator in line:
                picked.append(f"{p.name}: {line}")
                if len(picked) >= limit:
                    return [redact(x) for x in picked], "상관자 줄이 상한에 닿아 잘렸다."
    if not picked:
        return [], "상관자가 붙은 서버 줄이 없다 — 이 잡 이전에 로그가 회전했을 수 있다."
    return [redact(x) for x in picked], None


def deck_line_excerpts(error_text: str, input_paths: list[tuple[str, str]]) -> dict:
    """에러가 가리키는 줄만 전후 2줄과 함께 뽑는다. **opt-in 일 때만** 부른다."""
    wanted = sorted({int(m) for m in _LINE_REF.findall(error_text or "")})[:MAX_LINE_GROUPS]
    if not wanted:
        return {}
    out: dict[str, list[str]] = {}
    budget = MAX_DECK_LINES
    for name, path in input_paths:
        if budget <= 0:
            break
        try:
            rp = Path(path).resolve()
            root = settings.storage_dir.resolve()
            if root not in rp.parents:
                continue
            lines = rp.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        picked: list[str] = []
        for n in wanted:
            lo, hi = max(1, n - 2), min(len(lines), n + 2)
            if lo > len(lines):
                continue
            for i in range(lo, hi + 1):
                if budget <= 0:
                    break
                picked.append(f"{i:>8}: {lines[i - 1]}")
                budget -= 1
        if picked:
            out[name] = picked
    return out


def build(job, *, inputs: list[tuple[str, str]], outputs: list[str], deck_lines: bool) -> dict:
    """번들의 본문. 이 dict 가 `diagnostic.json` 이고 요약 텍스트의 재료다."""
    corr = job.id
    stdout_tail = _read_contained(job.stdout_path, limit=TAIL_CHARS * 4)[-TAIL_CHARS:]
    stderr_tail = _read_contained(job.stderr_path, limit=TAIL_CHARS * 4)[-TAIL_CHARS:]
    srv, srv_note = server_log_lines(corr)

    notes: list[str] = []
    if srv_note:
        notes.append(srv_note)
    env = job.env_snapshot or {}
    if not env:
        notes.append(
            "이 잡에는 환경 스냅샷이 없다 — 0009 마이그레이션 이전에 만들어진 잡이다."
        )
    elif env.get("binary", {}).get("revision_matches_binary") is False:
        notes.append(
            "⚠ BUILD_INFO 의 해시와 실제 바이너리가 어긋난다 — 이 잡의 revision 을 믿을 수 없다."
        )

    diag = {
        "schema": SCHEMA,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "correlator": corr,
        "job": {
            "id": job.id,
            "operation": job.operation,
            "status": job.status,
            "exit_code": job.exit_code,
            "created_utc": _iso(job.created_at),
            "started_utc": _iso(job.started_at),
            "finished_utc": _iso(job.finished_at),
            "error_summary": redact(job.error_summary or ""),
            "warnings": _redact_deep(job.warnings or []),
            "args": _redact_deep(job.args or {}),
            "resolved_cmd": _redact_deep(job.resolved_cmd or {}),
            "env_snapshot": _redact_deep(env),
            "external_kind": job.external_kind,
            "external_ref": _redact_deep(job.external_ref or {}),
        },
        "files": {"inputs": [n for n, _ in inputs], "outputs": outputs},
        "logs": {
            "stdout_tail": redact(stdout_tail),
            "stderr_tail": redact(stderr_tail),
            "server_lines": srv,
        },
        "notes": notes,
    }
    if deck_lines:
        src = f"{job.error_summary or ''}\n{stderr_tail}\n{stdout_tail}"
        diag["deck_excerpts"] = _redact_deep(deck_line_excerpts(src, inputs))
    else:
        diag["deck_excerpts"] = None
    return diag


def summary_text(diag: dict) -> str:
    """클립보드용 짧은 판. 채팅·메일에 그대로 붙일 수 있어야 한다."""
    j = diag["job"]
    b = (j.get("env_snapshot") or {}).get("binary") or {}
    g = (j.get("env_snapshot") or {}).get("gmsh") or {}
    argv = (j.get("resolved_cmd") or {}).get("argv") or []
    lines = [
        "===== DynaForge 진단 요약 =====",
        f"생성    : {diag['generated_utc']}  (schema {diag['schema']})",
        f"잡      : {j['id']}  op={j['operation']}  status={j['status']}  exit={j['exit_code']}",
        f"시각    : queued {j['created_utc']} / started {j['started_utc']} / finished {j['finished_utc']}",
        f"빌드    : {b.get('revision') or '(없음)'}  sha256={(b.get('sha256') or '')[:12]}"
        f"  match={b.get('revision_matches_binary')}",
        f"gmsh    : available={g.get('available')} version={g.get('version')}",
        f"argv    : {' '.join(str(a) for a in argv) if argv else '(없음)'}",
        f"입력    : {', '.join(diag['files']['inputs']) or '(없음)'}",
        f"산출    : {', '.join(diag['files']['outputs']) or '(없음)'}",
        "",
        "-- error_summary --",
        j.get("error_summary") or "(없음)",
    ]
    if j.get("warnings"):
        lines += ["", "-- warnings --", json.dumps(j["warnings"], ensure_ascii=False)[:1000]]
    tail = (diag["logs"]["stderr_tail"] or diag["logs"]["stdout_tail"] or "").strip()
    if tail:
        lines += ["", "-- 로그 꼬리(마지막 40줄) --", "\n".join(tail.splitlines()[-40:])]
    if diag["logs"]["server_lines"]:
        lines += ["", "-- 서버 줄(이 잡) --", "\n".join(diag["logs"]["server_lines"][-20:])]
    if diag["notes"]:
        lines += ["", "-- 참고 --", *(f"· {n}" for n in diag["notes"])]
    lines += ["", "전문은 진단 파일(.zip) 에 있다.", "=============================="]
    return "\n".join(lines)


def zip_bytes(job, diag: dict) -> bytes:
    """전문 묶음. 로그는 전문(상한까지), 나머지는 레다ct 된 텍스트다."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("diagnostic.json", json.dumps(diag, ensure_ascii=False, indent=2))
        z.writestr("summary.txt", summary_text(diag))
        z.writestr(
            "stdout.log", redact(_read_contained(job.stdout_path, limit=MAX_LOG_BYTES))
        )
        z.writestr(
            "stderr.log", redact(_read_contained(job.stderr_path, limit=MAX_LOG_BYTES))
        )
        rc = diag["job"].get("resolved_cmd") or {}
        z.writestr("resolved_cmd.json", json.dumps(rc, ensure_ascii=False, indent=2))
        z.writestr("server.log", "\n".join(diag["logs"]["server_lines"]))
    return buf.getvalue()
