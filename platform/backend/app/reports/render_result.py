# SceneForge 렌더 결과(C-11) zip 을 풀고 계약대로 검사하는 순수 함수 — I/O 없음, 붙이기는 services 가 한다
"""계약 — SceneForge `docs/contracts/c10-c11-render-request-result-draft-2026-10-29.md` §2, DynaForge 반입 규칙
다섯(10-29 합의) · 총괄 `drop-twin-1028.checklist.md` P3.

- 결과 폴더 = `render_result.json` + `outputs` 에 적은 파일만. 이름은 폴더 없는 이름.
- **전부 아니면 전무** — 출력마다 sha256 · 크기가 맞아야 하고, 목록에 없는 파일이 끼면 통째로 거절한다.
- `ok: false` 는 붙이지 않고 렌더 기록으로만 남긴다(그때 `outputs` 는 비어 있어야 한다).
- 지어내지 않는다 — 모르는 꼴 · 판이면 거절하고 까닭을 말한다.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile

FORMAT = "sceneforge.render_result"
VERSION = 1
RESULT_NAME = "render_result.json"
MAX_MEMBERS = 64
# 결과 폴더 하나는 512 MB 를 넘지 않는다(SceneForge 가 지키기로 함) — 손으로 올릴 때와 같은 상한이다.
MAX_TOTAL_BYTES = 512 * 1024 * 1024
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")
_EXT = {"mp4": (".mp4",), "still": (".png", ".jpg", ".jpeg", ".webp")}


class RenderResultError(ValueError):
    """계약에 맞지 않는 결과 — 까닭을 그대로 사람에게 보인다."""


def unzip(raw: bytes) -> tuple[dict, dict[str, bytes]]:
    """zip → (render_result.json, {파일 이름: 바이트}). 폴더 · 상위 경로 · 너무 큰 묶음은 거절한다."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise RenderResultError(f"zip 이 아니다: {exc}")
    infos = [i for i in zf.infolist() if not i.is_dir()]
    if len(infos) > MAX_MEMBERS:
        raise RenderResultError(f"파일이 너무 많다({len(infos)} > {MAX_MEMBERS})")
    if sum(i.file_size for i in infos) > MAX_TOTAL_BYTES:
        raise RenderResultError("풀면 512 MB 를 넘는다 — 결과 폴더 하나는 512 MB 이하다")
    files: dict[str, bytes] = {}
    for i in infos:
        if "/" in i.filename or "\\" in i.filename or not _SAFE_NAME.match(i.filename):
            raise RenderResultError(f"폴더 없는 이름만 받는다: {i.filename!r}")
        files[i.filename] = zf.read(i)
    if RESULT_NAME not in files:
        raise RenderResultError(f"{RESULT_NAME} 이 맨 위에 없다")
    try:
        result = json.loads(files.pop(RESULT_NAME))
    except ValueError as exc:
        raise RenderResultError(f"{RESULT_NAME} 을 JSON 으로 읽지 못했다: {exc}")
    if not isinstance(result, dict):
        raise RenderResultError(f"{RESULT_NAME} 이 JSON 객체가 아니다")
    return result, files


def check(result: dict, files: dict[str, bytes], *, report_id: str, case_keys: set[str]) -> dict:
    """계약 검사 — 통과하면 정리한 결과(`render_id` · `ok` · `outputs` …)를, 아니면 RenderResultError.

    `outputs` 의 항목에는 `data`(바이트)를 붙여 돌려준다 — 붙이는 쪽이 다시 풀지 않게.
    """
    if result.get("format") != FORMAT or result.get("version") != VERSION:
        raise RenderResultError(f"모르는 결과 꼴이다(format={result.get('format')!r}, version={result.get('version')!r})"
                                f" — {FORMAT} v{VERSION} 만 받는다")
    render_id = str(result.get("render_id") or "")
    if not _SAFE_ID.match(render_id):
        raise RenderResultError(f"render_id 가 없거나 꼴이 틀렸다: {render_id!r}")
    run = result.get("run") if isinstance(result.get("run"), dict) else {}
    if run.get("report_id") != report_id:
        raise RenderResultError(f"다른 리포트의 결과다(run.report_id={run.get('report_id')!r})")
    case_key = str(run.get("case_key") or "")
    if case_key not in case_keys:
        raise RenderResultError(f"이 리포트에 없는 각도다(run.case_key={case_key!r})")
    ok = result.get("ok") is True
    outs = result.get("outputs") if isinstance(result.get("outputs"), list) else None
    if outs is None:
        raise RenderResultError("outputs 가 목록이 아니다")
    if not ok:
        if outs or files:
            raise RenderResultError("ok:false 인데 출력이 있다 — 실패는 outputs: [] 로 온다")
        return {"render_id": render_id, "ok": False, "case_key": case_key, "outputs": [], "result": result}
    if not outs:
        raise RenderResultError("ok:true 인데 outputs 가 비었다")

    seen: set[str] = set()
    checked = []
    for o in outs:
        if not isinstance(o, dict):
            raise RenderResultError("outputs 항목이 객체가 아니다")
        kind, name = o.get("kind"), str(o.get("file") or "")
        if kind not in _EXT:
            raise RenderResultError(f"모르는 출력 종류다: {kind!r}")
        if not _SAFE_NAME.match(name) or name == RESULT_NAME:
            raise RenderResultError(f"출력 이름이 틀렸다: {name!r}")
        if not name.lower().endswith(_EXT[kind]):
            raise RenderResultError(f"{kind} 인데 확장자가 다르다: {name!r}")
        if name in seen:
            raise RenderResultError(f"같은 출력이 두 번 적혔다: {name!r}")
        seen.add(name)
        data = files.get(name)
        if data is None:
            raise RenderResultError(f"적힌 출력이 묶음에 없다: {name!r}")
        if o.get("bytes") != len(data):
            raise RenderResultError(f"{name} 크기가 다르다(적힌 {o.get('bytes')} · 받은 {len(data)})")
        if str(o.get("sha256") or "").lower() != hashlib.sha256(data).hexdigest():
            raise RenderResultError(f"{name} sha256 이 다르다")
        checked.append({**o, "data": data})
    extra = sorted(set(files) - seen)
    if extra:
        raise RenderResultError(f"outputs 에 없는 파일이 끼어 있다: {', '.join(extra[:5])}")
    return {"render_id": render_id, "ok": True, "case_key": case_key, "outputs": checked, "result": result}
