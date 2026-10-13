# 리포트 번들(.zip/.tar)에서 HTML 과 **사이드카 미디어**를 뽑는다 — 순수 함수, I/O 없음
"""Unpack a report bundle into (html, media) without touching the filesystem.

왜 이것이 있나 (2026-10-13). 결과 이미지는 리포트 HTML 안에 임베드되지 **않는다** —
옆에 딸린 파일이다(실측).

    impact : impact_report_data/set_media/pos_<POS>_s0_peak.png  (+ _view.mp4)
    deep   : custom_report/set_reports/<zone>/peak_<view>_<field>.png (+ view_*.mp4)

HTML 하나만 올리면 이미지는 **애초에 플랫폼에 들어오지 않는다.** 그러면 LLM 도, 화면도
결과 그림을 볼 수 없다. 그래서 번들을 받아 함께 푼다.

⚠ 압축 해제는 **신뢰할 수 없는 입력**이다. 가드를 전부 여기서 건다.
  · 경로 탈출 — 멤버 이름을 `..`·절대경로·드라이브 접두 기준으로 거른다(쓰는 쪽
    `storage.safe_relpath` + `resolve_within` 이 두 번째·세 번째 방어다).
  · 심볼릭/하드 링크·장치 파일 — tar 에서만 생기고, 통째로 **거부**한다(따라가지 않는다).
  · 폭탄 — 멤버 수·멤버 하나 크기·합계 해제 크기에 상한을 둔다.
  · 확장자 — 리포트 HTML 과 **알려진 미디어**만 꺼낸다. 그 밖은 조용히 버리지 않고 **센다**.
"""
from __future__ import annotations

import io
import posixpath
import tarfile
import zipfile

#: LLM 이 볼 수 있는 것은 이미지다(png/jpeg/gif/webp). mp4 는 모델이 못 보지만 화면·사람용으로
#: 나른다 — 대신 어느 쪽인지 `can_llm_view` 로 구분해 적는다.
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VIDEO_EXT = {".mp4", ".webm", ".mov"}
MEDIA_EXT = IMAGE_EXT | VIDEO_EXT

MAX_MEMBERS = 4000
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024


class BundleError(ValueError):
    """번들을 안전하게 풀 수 없다 — 이유를 사람 말로 담는다."""


def looks_like_bundle(filename: str | None, raw: bytes) -> bool:
    """이름이나 선두 바이트로 번들인지 본다(이름을 못 믿는 클라이언트가 있다)."""
    n = (filename or "").lower()
    if n.endswith((".zip", ".tar", ".tar.gz", ".tgz")):
        return True
    return raw[:4] == b"PK\x03\x04" or _is_tar(raw)


def _is_tar(raw: bytes) -> bool:
    # tar 는 매직이 오프셋 257 의 "ustar" 다(POSIX/GNU 둘 다).
    return len(raw) > 262 and raw[257:262] == b"ustar"


def _unsafe_name(name: str) -> bool:
    n = (name or "").replace("\\", "/")
    if not n or n.startswith("/") or ":" in n.split("/")[0]:
        return True
    return any(part in ("..",) for part in n.split("/"))


def _classify(name: str) -> str:
    ext = posixpath.splitext(name.lower())[1]
    if ext in (".html", ".htm"):
        return "html"
    if ext in MEDIA_EXT:
        return "media"
    return "other"


def _pick_html(cands: list[tuple[str, bytes]]) -> tuple[str, bytes]:
    """HTML 이 여러 개면 **리포트 본문**을 고른다.

    규칙(실측 기준) — 이름에 `report` 가 들어간 것 우선, 그다음 **얕은 깊이**, 그다음 **큰 것**.
    `deep_reports/<run>/report.html` 가 여럿 섞인 번들에서 통합 리포트를 집으려는 것이다.
    """
    def key(item):
        name, data = item
        depth = name.count("/")
        has_report = 0 if "report" in posixpath.basename(name).lower() else 1
        return (has_report, depth, -len(data))
    return sorted(cands, key=key)[0]


def extract(raw: bytes, filename: str | None = None) -> dict:
    """번들을 풀어 `{html_name, html, media:[{path,bytes,kind,can_llm_view}], skipped, note}`.

    HTML 이 없으면 `BundleError` — 리포트 없이 미디어만 반입하는 길은 두지 않는다
    (리포트에 붙지 않는 이미지는 어느 케이스의 것인지 알 수 없다).
    """
    name = (filename or "").lower()
    members: list[tuple[str, bytes]] = []
    skipped = {"unsafe_path": 0, "link_or_device": 0, "too_big": 0, "other_ext": 0}
    total = 0

    def take(mname: str, reader, size_hint: int | None) -> None:
        nonlocal total
        if _unsafe_name(mname):
            skipped["unsafe_path"] += 1
            return
        cls = _classify(mname)
        if cls == "other":
            skipped["other_ext"] += 1
            return
        if size_hint is not None and size_hint > MAX_MEMBER_BYTES:
            skipped["too_big"] += 1
            return
        data = reader()
        if len(data) > MAX_MEMBER_BYTES:
            skipped["too_big"] += 1
            return
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise BundleError(
                f"번들 해제 합계가 상한을 넘습니다 ({MAX_TOTAL_BYTES // (1024*1024)}MB) — "
                "이미지·영상을 줄여서 다시 묶으세요")
        members.append((mname.replace("\\", "/"), data))

    if raw[:4] == b"PK\x03\x04" or name.endswith(".zip"):
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile as exc:
            raise BundleError(f"zip 을 읽을 수 없습니다: {exc}") from exc
        infos = zf.infolist()
        if len(infos) > MAX_MEMBERS:
            raise BundleError(f"번들 항목이 너무 많습니다 ({len(infos)} > {MAX_MEMBERS})")
        for zi in infos:
            if zi.is_dir():
                continue
            take(zi.filename, lambda zi=zi: zf.read(zi), zi.file_size)
    elif _is_tar(raw) or name.endswith((".tar", ".tar.gz", ".tgz")):
        try:
            tf = tarfile.open(fileobj=io.BytesIO(raw), mode="r:*")
        except tarfile.TarError as exc:
            raise BundleError(f"tar 을 읽을 수 없습니다: {exc}") from exc
        with tf:
            infos = tf.getmembers()
            if len(infos) > MAX_MEMBERS:
                raise BundleError(f"번들 항목이 너무 많습니다 ({len(infos)} > {MAX_MEMBERS})")
            for ti in infos:
                if ti.isdir():
                    continue
                # ⚠ 링크·장치는 따라가지 않는다 — 번들 밖을 가리킬 수 있다.
                if not ti.isfile():
                    skipped["link_or_device"] += 1
                    continue
                def rd(ti=ti):
                    f = tf.extractfile(ti)
                    return f.read() if f is not None else b""
                take(ti.name, rd, ti.size)
    else:
        raise BundleError("번들이 아닙니다 — .zip 또는 .tar(.gz) 로 묶어 주세요")

    htmls = [(n, d) for n, d in members if _classify(n) == "html"]
    if not htmls:
        raise BundleError("번들에 리포트 HTML 이 없습니다 — 리포트와 이미지를 함께 묶어 주세요")
    html_name, html = _pick_html(htmls)
    media = []
    for n, d in members:
        if _classify(n) != "media" or n == html_name:
            continue
        ext = posixpath.splitext(n.lower())[1]
        media.append({"path": n, "bytes": len(d), "data": d, "ext": ext,
                      "kind": "image" if ext in IMAGE_EXT else "video",
                      "can_llm_view": ext in IMAGE_EXT})
    out = {
        "html_name": html_name,
        "html": html,
        "media": media,
        "n_html": len(htmls),
        "skipped": {k: v for k, v in skipped.items() if v},
        "total_bytes": total,
    }
    if len(htmls) > 1:
        out["note"] = ("HTML 이 %d 개여서 `%s` 를 리포트 본문으로 골랐다(이름에 report·얕은 깊이·"
                       "큰 것 순). 다른 것을 쓰려면 그 HTML 만 따로 올려라" % (len(htmls), html_name))
    return out
