# StepForge fe_cad 묶음(C-6 가중치 · C-7 glb)을 풀고 받는 쪽 검사를 하는 순수 함수 — I/O 없음, 붙이기는 services 가 한다
"""계약 — StepForge fe_cad 산출(manifest · pairs · parts · weights · glb), 총괄 `drop-twin-1028.plan.md` C-6 · C-7,
뷰어 계획 `docs/01-plan/features/deform-viewer-1030.plan.md`.

- 묶음 = `manifest.json` + manifest `files[]` 에 적은 파일만. 이름은 폴더 없는 이름.
- **전부 아니면 전무** — 파일마다 bytes · sha256 이 맞아야 하고, 목록에 없는 파일이 끼면 통째로 거절한다.
- 받는 쪽 검사는 여기 한 자리다 — 화면은 통과한 묶음만 받는다(같은 규칙을 화면에 또 두면 사본이 된다).
- 지어내지 않는다 — 모르는 꼴 · 판이면 거절하고 까닭을 말한다.
"""
from __future__ import annotations

import array
import hashlib
import io
import json
import re
import struct
import sys
import zipfile

MANIFEST_NAME = "manifest.json"
PARTS_NAME = "parts.json"
PAIRS_NAME = "pairs.json"
FORMATS = {"manifest": "stepforge.fe_cad_manifest", "weights": "stepforge.fe_cad_weights",
           "parts": "stepforge.fe_cad_parts", "pairs": "stepforge.fe_cad_pairs"}
VERSION = 1
MAX_MEMBERS = 64
# 렌더 판 glb 는 커질 수 있다 — 렌더 결과(C-11)와 같은 상한을 둔다.
MAX_TOTAL_BYTES = 512 * 1024 * 1024
# glb 이름은 STEP 파일 이름을 따른다 — 한글 · 공백이 올 수 있어 폴더 구분자 · 제어 문자 · 점으로 시작하는 이름만 막는다.
_SAFE_NAME = re.compile(r"^(?!\.)[^/\\\x00-\x1f:*?\"<>|]{1,200}$")
_KEY = re.compile(r"^[0-9a-f]{64}$")
_W_SUM_TOL = 1e-3            # 무게 셋(float32)의 합이 1 에서 이만큼까지
_ARRAYS = {"row_ptr": "uint32", "col": "uint32", "w": "float32", "dist": "float32"}
_TYPECODE = {"uint32": "I", "float32": "f"}
_GLB_JSON = 0x4E4F534A       # 'JSON'


class CadBundleError(ValueError):
    """계약에 맞지 않는 묶음 — 까닭을 그대로 사람에게 보인다."""


def unzip(raw: bytes) -> tuple[dict, dict[str, bytes]]:
    """zip → (manifest.json, {파일 이름: 바이트}). 폴더 · 상위 경로 · 너무 큰 묶음은 거절한다.

    파일 표에는 manifest.json 의 받은 바이트도 남긴다 — 붙이는 쪽이 출처를 그대로 보관하게.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise CadBundleError(f"zip 이 아니다: {exc}")
    infos = [i for i in zf.infolist() if not i.is_dir()]
    if len(infos) > MAX_MEMBERS:
        raise CadBundleError(f"파일이 너무 많다({len(infos)} > {MAX_MEMBERS})")
    if sum(i.file_size for i in infos) > MAX_TOTAL_BYTES:
        raise CadBundleError("풀면 512 MB 를 넘는다")
    files: dict[str, bytes] = {}
    for i in infos:
        if "/" in i.filename or "\\" in i.filename or not _SAFE_NAME.match(i.filename):
            raise CadBundleError(f"폴더 없는 이름만 받는다: {i.filename!r}")
        files[i.filename] = zf.read(i)
    if MANIFEST_NAME not in files:
        raise CadBundleError(f"{MANIFEST_NAME} 이 맨 위에 없다 — StepForge fe_cad 묶음 폴더를 통째로 올린다")
    return _parse(files[MANIFEST_NAME], MANIFEST_NAME), files


def _parse(raw: bytes, name: str) -> dict:
    try:
        obj = json.loads(raw)
    except ValueError as exc:
        raise CadBundleError(f"{name} 을 JSON 으로 읽지 못했다: {exc}")
    if not isinstance(obj, dict):
        raise CadBundleError(f"{name} 이 JSON 객체가 아니다")
    return obj


def _same_format(obj: dict, what: str, name: str) -> None:
    if obj.get("format") != FORMATS[what] or obj.get("version") != VERSION:
        raise CadBundleError(f"{name} 이 모르는 꼴이다(format={obj.get('format')!r}, version={obj.get('version')!r})"
                             f" — {FORMATS[what]} v{VERSION} 만 받는다")


def _glb_json(raw: bytes, name: str) -> dict:
    """glb(바이너리 glTF 2) 머리와 첫 JSON 덩이만 읽는다 — 바이너리 덩이는 풀지 않는다."""
    if len(raw) < 20:
        raise CadBundleError(f"{name} 이 glb 가 아니다(너무 짧다)")
    magic, version, length = struct.unpack_from("<4sII", raw, 0)
    if magic != b"glTF" or version != 2:
        raise CadBundleError(f"{name} 이 glTF 2 바이너리(glb)가 아니다")
    if length != len(raw):
        raise CadBundleError(f"{name} 머리의 길이({length})가 파일 크기({len(raw)})와 다르다")
    clen, ctype = struct.unpack_from("<II", raw, 12)
    if ctype != _GLB_JSON or 20 + clen > len(raw):
        raise CadBundleError(f"{name} 의 첫 덩이가 JSON 이 아니다")
    return _parse(raw[20:20 + clen], name)


def _read(binary: bytes, spec, dtype: str, what: str) -> array.array:
    """weights.bin 의 배열 하나 — 오프셋은 8 의 배수, bin 안에 들어야 한다."""
    if not isinstance(spec, dict):
        raise CadBundleError(f"{what} 배열 설명이 없다")
    off, count = spec.get("offset"), spec.get("count")
    if spec.get("dtype") != dtype:
        raise CadBundleError(f"{what} 형이 {spec.get('dtype')!r} 다 — {dtype} 이어야 한다")
    if not isinstance(off, int) or not isinstance(count, int) or off < 0 or count < 0:
        raise CadBundleError(f"{what} 오프셋 · 개수가 정수가 아니다")
    if off % 8:
        raise CadBundleError(f"{what} 오프셋({off})이 8 의 배수가 아니다")
    end = off + count * 4
    if end > len(binary):
        raise CadBundleError(f"{what} 이 weights.bin 밖으로 나간다({end} > {len(binary)})")
    a = array.array(_TYPECODE[dtype])
    a.frombytes(binary[off:end])
    if sys.byteorder != "little":
        a.byteswap()
    return a


def _check_part(p: dict, idx: int, binary: bytes, glbs: dict[str, dict], nnz_per_row: int) -> dict:
    """가중치 파트 하나 — glb 정점 수 · 배열 개수 · row_ptr · 무게 합."""
    pid = p.get("pid")
    where = f"weights.parts[{idx}](pid {pid})"
    if not isinstance(pid, int):
        raise CadBundleError(f"{where} 에 정수 pid 가 없다")
    g = p.get("glb") if isinstance(p.get("glb"), dict) else {}
    doc = glbs.get(g.get("file"))
    if doc is None:
        raise CadBundleError(f"{where} 의 glb {g.get('file')!r} 가 보기 판 glb 가 아니다")
    nodes, meshes, accessors = doc.get("nodes") or [], doc.get("meshes") or [], doc.get("accessors") or []
    node, mesh = g.get("node"), g.get("mesh")
    if not isinstance(node, int) or not 0 <= node < len(nodes) or nodes[node].get("mesh") != mesh \
            or not isinstance(mesh, int) or not 0 <= mesh < len(meshes):
        raise CadBundleError(f"{where} — glb 노드 {node} 가 없거나 mesh {mesh} 를 가리키지 않는다")
    prims = meshes[mesh].get("primitives") or []
    total = 0
    for q in g.get("primitives") or []:
        k = q.get("primitive")
        if not isinstance(k, int) or not 0 <= k < len(prims):
            raise CadBundleError(f"{where} — mesh {mesh} 에 primitive {k} 가 없다")
        acc = (prims[k].get("attributes") or {}).get("POSITION")
        if not isinstance(acc, int) or not 0 <= acc < len(accessors):
            raise CadBundleError(f"{where} — primitive {k} 에 POSITION 이 없다")
        if accessors[acc].get("count") != q.get("vertices"):
            raise CadBundleError(f"{where} — primitive {k} 정점이 glb {accessors[acc].get('count')} 개인데 "
                                 f"가중치 머리는 {q.get('vertices')} 개다")
        total += q.get("vertices")
    rows, nnz = p.get("rows"), p.get("nnz")
    if total != rows or g.get("vertices") != rows:
        raise CadBundleError(f"{where} — 행 수({rows})가 glb 정점 수({total})와 다르다(행 = glb 정점)")
    arrs = p.get("arrays") if isinstance(p.get("arrays"), dict) else {}
    a = {name: _read(binary, arrs.get(name), dtype, f"{where} {name}") for name, dtype in _ARRAYS.items()}
    if len(a["row_ptr"]) != rows + 1 or len(a["col"]) != nnz or len(a["w"]) != nnz or len(a["dist"]) != rows:
        raise CadBundleError(f"{where} — 배열 개수가 행 {rows} · nnz {nnz} 와 맞지 않는다")
    rp, w = a["row_ptr"], a["w"]
    if rp[0] != 0 or rp[-1] != nnz:
        raise CadBundleError(f"{where} — row_ptr 가 0 에서 시작해 nnz 로 끝나지 않는다")
    for i in range(rows):
        lo, hi = rp[i], rp[i + 1]
        if hi - lo != nnz_per_row:
            raise CadBundleError(f"{where} — 행 {i} 의 항이 {hi - lo} 개다(행마다 {nnz_per_row})")
        s = w[lo] + w[lo + 1] + w[lo + 2]
        if abs(s - 1.0) > _W_SUM_TOL:
            raise CadBundleError(f"{where} — 행 {i} 의 무게 합이 {s:.6f} 다(1 이어야 한다)")
    return {"pid": pid, "part_key": p.get("part_key"),
            "glb": {"file": g.get("file"), "node": node, "mesh": mesh},
            "rows": rows, "nnz": nnz,
            "dist_mm_max": (p.get("dist_mm") or {}).get("max") if isinstance(p.get("dist_mm"), dict) else None}


def check(manifest: dict, files: dict[str, bytes], *, report_part_ids: set[int]) -> dict:
    """받는 쪽 검사 — 통과하면 붙일 요약을, 아니면 CadBundleError.

    요약의 `parts` 는 화면이 glb 노드를 파트(pid · 이름 · 색)에 잇는 데 쓴다.
    """
    _same_format(manifest, "manifest", MANIFEST_NAME)
    key = str(manifest.get("key") or "")
    if not _KEY.match(key):
        raise CadBundleError(f"manifest 열쇠가 64자 소문자 hex 가 아니다: {key!r}")

    listed = manifest.get("files") if isinstance(manifest.get("files"), list) else None
    if not listed:
        raise CadBundleError("manifest files 가 비었다")
    metas: list[dict] = []
    for e in listed:
        name = e.get("file") if isinstance(e, dict) else None
        if not isinstance(name, str) or not _SAFE_NAME.match(name):
            raise CadBundleError(f"manifest files 의 이름이 틀렸다: {name!r}")
        if name not in files:
            raise CadBundleError(f"manifest 에 적힌 {name} 이 묶음에 없다")
        data = files[name]
        if e.get("bytes") != len(data):
            raise CadBundleError(f"{name} 크기가 manifest({e.get('bytes')})와 다르다({len(data)})")
        sha = hashlib.sha256(data).hexdigest()
        if str(e.get("sha256") or "").lower() != sha:
            raise CadBundleError(f"{name} sha256 이 manifest 와 다르다")
        metas.append({"file": name, "bytes": len(data), "sha256": sha})
    extra = sorted(set(files) - {m["file"] for m in metas} - {MANIFEST_NAME})
    if extra:
        raise CadBundleError(f"manifest 에 없는 파일이 끼었다: {', '.join(extra)}")

    view = (manifest.get("variants") or {}).get("view") if isinstance(manifest.get("variants"), dict) else None
    if not isinstance(view, dict) or view.get("key") != key:
        raise CadBundleError("manifest variants.view 가 없거나 열쇠가 다르다")
    glb_names = view.get("glb") if isinstance(view.get("glb"), list) else []
    if not glb_names or any(n not in files for n in glb_names):
        raise CadBundleError(f"보기 판 glb 가 묶음에 없다: {glb_names!r}")
    wname = view.get("weights")
    if wname not in files:
        raise CadBundleError(f"보기 판 가중치 {wname!r} 가 묶음에 없다")

    weights = _parse(files[wname], wname)
    _same_format(weights, "weights", wname)
    for name in (PARTS_NAME, PAIRS_NAME):
        if name not in files:
            raise CadBundleError(f"{name} 이 묶음에 없다")
    parts = _parse(files[PARTS_NAME], PARTS_NAME)
    pairs = _parse(files[PAIRS_NAME], PAIRS_NAME)
    _same_format(parts, "parts", PARTS_NAME)
    _same_format(pairs, "pairs", PAIRS_NAME)
    for obj, name in ((weights, wname), (parts, PARTS_NAME), (pairs, PAIRS_NAME)):
        if obj.get("key") != key:
            raise CadBundleError(f"{name} 열쇠가 manifest 와 다르다")
    if weights.get("byte_order") != "little" or weights.get("align_bytes") != 8:
        raise CadBundleError("가중치는 리틀엔디언 · 정렬 8 만 받는다")
    nnz_per_row = weights.get("nnz_per_row")
    if nnz_per_row != 3:
        raise CadBundleError(f"행마다 항 수가 {nnz_per_row!r} 다 — 무게중심 좌표 3 이어야 한다")
    b = weights.get("bin") if isinstance(weights.get("bin"), dict) else {}
    binary = files.get(b.get("file"))
    if binary is None or b.get("bytes") != len(binary) or str(b.get("sha256") or "").lower() != \
            hashlib.sha256(binary).hexdigest():
        raise CadBundleError(f"가중치 bin {b.get('file')!r} 이 없거나 크기 · sha256 이 머리와 다르다")

    glbs = {n: _glb_json(files[n], n) for n in glb_names}
    wparts = weights.get("parts") if isinstance(weights.get("parts"), list) else []
    if not wparts:
        raise CadBundleError("가중치에 파트가 없다")
    checked = [_check_part(p, i, binary, glbs, nnz_per_row) for i, p in enumerate(wparts)]

    # 이름 · 색 · 재질은 파트 표(parts.json)가 정본이다 — part_key 로 잇는다
    by_key = {p.get("part_key"): p for p in (parts.get("parts") or []) if isinstance(p, dict)}
    for c in checked:
        row = by_key.get(c["part_key"]) or {}
        c.update(name=row.get("name"), color=row.get("color"), material=row.get("material"))

    pids = {c["pid"] for c in checked}
    if not report_part_ids:
        raise CadBundleError("리포트에 파트 표가 없어 이 묶음이 그 기기인지 맞춰 볼 수 없다")
    matched = pids & set(report_part_ids)
    if not matched:
        raise CadBundleError(f"이 리포트의 기기가 아니다 — 묶음 파트 id {sorted(pids)[:8]}… 가 리포트 파트와 하나도 안 겹친다")
    warnings: list[str] = []
    if pids - matched:
        warnings.append(f"묶음 파트 {len(pids - matched)}개가 리포트에 없다: {sorted(pids - matched)[:10]}")
    if weights.get("unmapped"):
        warnings.append(f"가중치에 못 이은 것이 있다(unmapped {len(weights['unmapped'])}건)")
    deck = pairs.get("deck") if isinstance(pairs.get("deck"), dict) else None
    return {
        "key": key,
        "view": {"glb": glb_names, "weights": wname, "bin": b.get("file")},
        "render": isinstance((manifest.get("variants") or {}).get("render"), dict),
        "deck": deck, "cad_project": pairs.get("cad_project"), "step_revision": pairs.get("step_revision"),
        "units": weights.get("units"),
        "parts": checked, "n_parts": len(checked),
        "rows": sum(c["rows"] for c in checked), "nnz": sum(c["nnz"] for c in checked),
        "pids_matched": len(matched), "pids_bundle_only": sorted(pids - matched),
        "files": metas, "warnings": warnings,
    }
