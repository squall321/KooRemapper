# MCP 그림 도구의 래스터 블록(figure_png.py) — 실패 갈래와 SIF 안 실렌더를 고정한다
"""메시 그림 SVG → PNG/JPEG (2026-11-02, 포털 요청 — 게이트웨이가 이미지 블록만 리포트로 옮긴다).

두 층이다.

1. **호스트** — 가짜 `rsvg-convert` 로 실패 갈래를 고정한다. 까닭 문자열이 응답의 `figure_png_error` 로
   그대로 나가므로 꼬리표(`renderer_missing`·`timeout`·`render_failed`)가 앞에 와야 한다.
2. **mcp.sif 안** — 진짜 렌더러·한글 글꼴·크기 줄이기. 이 SIF 가 낡으면(렌더러 없음) 건너뛰는 대신
   **빨개진다** — 관문은 초록인데 플랫폼에서 그림이 안 나오는 일을 막으려고.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
PLATFORM = Path(__file__).resolve().parents[2]
MCP_DIR = PLATFORM / "mcp_server"
MCP_SIF = PLATFORM / "infra" / "apptainer" / "mcp.sif"
sys.path.insert(0, str(MCP_DIR))

import figure_png as fp  # noqa: E402


def _png(w: int, h: int) -> bytes:
    """흰 RGB PNG 하나 — 의존 없이 만든다."""
    raw = b"".join(b"\x00" + b"\xff" * (3 * w) for _ in range(h))

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _fake_renderer(tmp: Path, monkeypatch, body: str) -> None:
    exe = tmp / "rsvg-convert"
    exe.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp}:{os.environ.get('PATH', '')}")


# ── ① 호스트: 실패 갈래 ───────────────────────────────────────────────────────

def test_a_missing_renderer_is_a_short_tagged_reason(monkeypatch):
    monkeypatch.setattr(fp.shutil, "which", lambda _n: None)
    with pytest.raises(fp.FigurePngError) as e:
        asyncio.run(fp.rasterize(b"<svg/>"))
    assert str(e.value).startswith("renderer_missing:")


def test_a_hung_renderer_is_killed_at_the_deadline(tmp_path, monkeypatch):
    _fake_renderer(tmp_path, monkeypatch, "sleep 30\n")
    monkeypatch.setattr(fp, "RENDER_TIMEOUT_S", 0.5)
    t0 = time.monotonic()
    with pytest.raises(fp.FigurePngError) as e:
        asyncio.run(fp.rasterize(b"<svg/>"))
    assert str(e.value).startswith("timeout:")
    assert time.monotonic() - t0 < 5, "기한에 끊어야 한다 — 렌더러를 기다리면 도구 호출 전체가 묶인다"


def test_a_failing_renderer_says_its_rc_and_first_stderr_line(tmp_path, monkeypatch):
    _fake_renderer(tmp_path, monkeypatch, "echo 'Error reading SVG: bad' >&2\nexit 3\n")
    with pytest.raises(fp.FigurePngError) as e:
        asyncio.run(fp.rasterize(b"<svg/>"))
    msg = str(e.value)
    assert msg.startswith("render_failed:") and "rc=3" in msg and "Error reading SVG" in msg


def test_an_empty_svg_is_refused_before_rendering(monkeypatch):
    monkeypatch.setattr(fp.shutil, "which", lambda _n: pytest.fail("렌더러를 부르면 안 된다"))
    with pytest.raises(fp.FigurePngError):
        asyncio.run(fp.rasterize(b""))


def test_a_small_png_goes_out_as_is(tmp_path, monkeypatch):
    png = _png(30, 20)
    (tmp_path / "out.png").write_bytes(png)
    _fake_renderer(tmp_path, monkeypatch, f"cat > /dev/null\ncat '{tmp_path / 'out.png'}'\n")
    data, fmt, w, h = asyncio.run(fp.rasterize(b"<svg/>"))
    assert (data, fmt, w, h) == (png, "png", 30, 20)


# ── ② mcp.sif 안: 진짜 렌더러 ────────────────────────────────────────────────

needs_sif = pytest.mark.skipif(not (MCP_SIF.exists() and shutil.which("apptainer")),
                               reason="mcp.sif 또는 apptainer 없음")

# 한글 글자 + 평평한 색 다각형 몇 개(단면·모식도 꼴)
_KOREAN_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" '
    'font-family="Malgun Gothic, Apple SD Gothic Neo, Noto Sans KR, NanumGothic, sans-serif">'
    '<rect width="1200" height="900" fill="#fff"/>'
    + "".join(f'<rect x="{40 + i * 110}" y="200" width="100" height="400" fill="#{(i * 40) % 256:02x}80c0"/>'
              for i in range(10))
    + '<text x="60" y="120" font-size="48">양극 집전체 — 가로 눈금 0.25</text></svg>')


def _heavy_svg(nx: int = 150, ny: int = 110) -> str:
    """이어 붙은 삼각형 격자 + 매끄러운 음영 + 가는 모서리선(표면 그림 `wire` 꼴) — 1500px PNG 가 900KB 쯤.

    ⚠ 무작위 색 삼각형으로 만들면 잡음이라 어떤 부호화로도 줄지 않는다(실측 960px JPEG 330KB) —
    실제 그림을 대표하지 않는다. 실측 37MB 배터리 덱 표면은 1500px JPEG 149KB 였다."""
    import math
    x0, y0, w, h = 100, 100, 1000, 700
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900">'
           '<rect width="1200" height="900" fill="#fff"/>']
    for i in range(nx):
        for j in range(ny):
            xa, xb = x0 + w * i / nx, x0 + w * (i + 1) / nx
            ya, yb = y0 + h * j / ny, y0 + h * (j + 1) / ny
            for tri in (((xa, ya), (xb, ya), (xa, yb)), ((xb, ya), (xb, yb), (xa, yb))):
                cx, cy = sum(p[0] for p in tri) / 3, sum(p[1] for p in tri) / 3
                g = int(70 + 160 * (0.55 + 0.45 * math.cos((cx - 600) / 400) * math.cos((cy - 450) / 500)))
                pts = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in tri)
                out.append(f'<polygon points="{pts}" fill="#{g:02x}{min(255, g + 15):02x}{min(255, g + 40):02x}" '
                           'stroke="#334" stroke-width="0.4"/>')
    return "".join(out) + "</svg>"


def _in_sif(tmp_path: Path, svg: str) -> dict:
    src = tmp_path / "in.svg"
    src.write_text(svg, encoding="utf-8")
    probe = (
        "import asyncio, json, sys; sys.path.insert(0, sys.argv[1]); import figure_png as fp\n"
        "try:\n"
        "    d, f, w, h = asyncio.run(fp.rasterize(open(sys.argv[2], 'rb').read()))\n"
        "    print(json.dumps({'fmt': f, 'w': w, 'h': h, 'bytes': len(d), 'target': fp.TARGET_BYTES}))\n"
        "except fp.FigurePngError as e:\n"
        "    print(json.dumps({'error': str(e)}))\n")
    got = subprocess.run(["apptainer", "exec", str(MCP_SIF), "python3", "-I", "-c", probe,
                          str(MCP_DIR), str(src)], capture_output=True, text=True, timeout=300)
    assert got.returncode == 0, got.stderr[-1500:]
    return json.loads(got.stdout.strip().splitlines()[-1])


@needs_sif
def test_the_sif_has_the_renderer_and_a_korean_font():
    """낡은 mcp.sif 면 여기서 빨개진다 — `infra/scripts/build.sh --force` 로 다시 굽는다."""
    got = subprocess.run(["apptainer", "exec", str(MCP_SIF), "sh", "-c",
                          "command -v rsvg-convert && fc-list :lang=ko family"],
                         capture_output=True, text=True, timeout=120)
    assert "rsvg-convert" in got.stdout, "mcp.sif 에 rsvg-convert 가 없다 — 그림 블록이 안 나간다"
    assert "Nanum" in got.stdout, "mcp.sif 에 한글 글꼴이 없다 — 눈금·제목이 두부(□)로 나온다"


@needs_sif
def test_a_korean_figure_renders_at_full_width_as_png(tmp_path):
    r = _in_sif(tmp_path, _KOREAN_SVG)
    assert "error" not in r, r
    assert (r["fmt"], r["w"], r["h"]) == ("png", 1500, 1125)
    assert r["bytes"] <= r["target"]


@needs_sif
def test_a_heavy_figure_is_shrunk_under_the_target(tmp_path):
    r = _in_sif(tmp_path, _heavy_svg())
    assert "error" not in r, r
    assert r["bytes"] <= r["target"], r
    assert r["fmt"] in ("png", "jpeg") and r["w"] >= fp.MIN_WIDTH
