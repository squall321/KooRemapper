# 메시 그림 SVG 를 리포트·게이트웨이가 받는 래스터(PNG/JPEG)로 바꾸는 도우미
"""왜 있나 (2026-11-02, 포털 요청). 게이트웨이는 MCP 응답의 **이미지 블록**을 저장해 Report Archive
리포트로 넣는데(`figure_to_report`), RA 는 png/jpeg/gif/webp 만 받고 SVG 는 415 로 거절한다. 그림 op 셋
(section·surfview·stackdiagram)은 SVG 만 낸다 — 그래서 여기서 그것을 래스터로 바꾼다.

왜 C++ 이 아니라 여기인가. SVG 에 한글 `<text>`(축 눈금·파트 제목)가 있다. 글꼴을 다루는 렌더러가 필요하고,
글자를 빼먹는 경량 래스터라이저로 그리면 숫자가 사라진 **거짓 그림**이 된다. `mcp.sif` 에 rsvg-convert 와
나눔 글꼴을 넣었다(`infra/apptainer/mcp.def`).

크기 — 폭 1500px 로 그리고 256KB 를 넘으면 원본 PNG → 256색 PNG → JPEG → 폭 ×0.8(최소 800px) 순으로
줄인다. 평평한 색(단면·모식도)은 256색 PNG 가, 음영(표면)은 JPEG 가 작다(실측은
`docs/01-plan/features/mcp-figure-png-1102.context-notes.md`).

실패는 `FigurePngError` 하나로 올린다 — 메시지가 응답의 `figure_png_error` 로 그대로 나가므로 짧게, 앞에
갈래 꼬리표(`renderer_missing`·`timeout`·`render_failed`·`too_large`)를 붙인다.
"""
from __future__ import annotations

import asyncio
import io
import os
import shutil
import signal
import struct

RENDER_WIDTH = 1500
TARGET_BYTES = 256 * 1024
MIN_WIDTH = 800
#: 이보다 크면 싣지 않는다 — 게이트웨이 상한(이미지 한 장 8MiB)보다 한참 아래로 둔다.
MAX_BYTES = 2 * 1024 * 1024
#: 실측 최악(37MB 배터리 덱 표면, 다각형 101k)이 1.04초다.
RENDER_TIMEOUT_S = 60.0


class FigurePngError(RuntimeError):
    """그림을 못 만든 까닭 — 응답의 `figure_png_error` 로 나간다."""


def _png_size(png: bytes) -> tuple[int, int]:
    """PNG 머리(IHDR)의 폭·높이."""
    return struct.unpack(">II", png[16:24])


async def _render(svg: bytes, width: int) -> bytes:
    exe = shutil.which("rsvg-convert")
    if not exe:
        raise FigurePngError("renderer_missing: 이 mcp.sif 에 rsvg-convert 가 없다")
    proc = await asyncio.create_subprocess_exec(
        exe, "--width", str(width), "--keep-aspect-ratio", "--background-color", "white",
        "--format", "png",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, start_new_session=True)
    try:
        out, err = await asyncio.wait_for(proc.communicate(svg), RENDER_TIMEOUT_S)
    except asyncio.TimeoutError:
        # 그룹째 죽이고 파이프를 비운다 — 부모만 죽이면 자식이 파이프를 쥔 채 남아 닫히지 않는다.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await proc.communicate()
        raise FigurePngError(f"timeout: 그리기가 {RENDER_TIMEOUT_S:.0f}초를 넘었다") from None
    if proc.returncode != 0 or not out.startswith(b"\x89PNG"):
        why = (err.decode("utf-8", "replace").strip().splitlines() or [""])[0][:160]
        raise FigurePngError(f"render_failed: rsvg-convert rc={proc.returncode} {why}".rstrip())
    return out


def _shrink(png: bytes) -> tuple[bytes, str, int, int]:
    """목표 크기 안에 드는 첫 판 → (bytes, "png"|"jpeg", 폭, 높이)."""
    w, h = _png_size(png)
    if len(png) <= TARGET_BYTES:
        return png, "png", w, h
    try:
        from PIL import Image as PILImage
    except ImportError:
        if len(png) <= MAX_BYTES:
            return png, "png", w, h
        raise FigurePngError(f"too_large: PNG {len(png) // 1024}KB 인데 줄일 pillow 가 없다") from None

    def enc(img, fmt: str, **kw) -> bytes:
        buf = io.BytesIO()
        img.save(buf, fmt, **kw)
        return buf.getvalue()

    im = PILImage.open(io.BytesIO(png)).convert("RGB")
    tries = [(png, "png", w, h)]
    q = enc(im.quantize(colors=256), "PNG", optimize=True)
    if len(q) <= TARGET_BYTES:
        return q, "png", w, h
    tries.append((q, "png", w, h))
    while True:
        j = enc(im, "JPEG", quality=85, optimize=True)
        if len(j) <= TARGET_BYTES:
            return j, "jpeg", im.width, im.height
        tries.append((j, "jpeg", im.width, im.height))
        nw = int(im.width * 0.8)
        if nw < MIN_WIDTH:
            break
        im = im.resize((nw, max(1, int(im.height * 0.8))), PILImage.LANCZOS)
    best = min(tries, key=lambda t: len(t[0]))
    if len(best[0]) > MAX_BYTES:
        raise FigurePngError(f"too_large: 가장 작게 줄여도 {len(best[0]) // 1024}KB 다")
    return best


async def rasterize(svg: bytes) -> tuple[bytes, str, int, int]:
    """SVG → (bytes, "png"|"jpeg", 폭, 높이). 못 만들면 `FigurePngError`."""
    if not svg:
        raise FigurePngError("render_failed: SVG 가 비었다")
    png = await _render(svg, RENDER_WIDTH)
    return await asyncio.to_thread(_shrink, png)
