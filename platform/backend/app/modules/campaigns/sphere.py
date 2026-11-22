# 캠페인 구면 위험도 지도(DF-09) — 각도 값을 경위도 격자로 보간하고 Mollweide 로 칠한 그림(PNG · SVG)을 내는 순수 함수(numpy 없이)
"""구면 지도(요청서 DF-09 · 계획 docs/01-plan/features/df-campaign-analysis-1122.plan.md 4절).

격자 — 경도 −180 … 180(361) × 위도 −90 … 90(181), 1° 간격. 마디마다 각거리로 가장 가까운 8 방향을 고르고 가중 1 / max(θ, 0.5°)² 로
평균한다(θ 는 도). 가까운 방향 찾기는 위도 띠 · 경도 창으로 후보를 좁힌 뒤 정확한 각거리로 가린다 — 반지름 안에 8 개가 없으면 반지름을 두 배로
넓힌다(결과는 전부 훑기와 같다). 가운데 맞춤 — cos(위도) 가중 경도 열 평균이 가장 큰 열을 0° 로 돌린다.
그림 — Mollweide 투영 · 띠 칠(등급 10) · 등고선 · 방향 점. PNG 는 글자 없는 래스터, SVG 는 그 래스터 위에 선 · 점 · 글.
"""
from __future__ import annotations

import base64
import bisect
import math
import struct
import zlib

LON_N, LAT_N = 361, 181
K, MIN_DEG = 8, 0.5
BANDS = 10
# 띠 색(낮음 → 높음) — viridis 에서 고른 열 색
PALETTE = [(68, 1, 84), (72, 40, 120), (62, 74, 137), (49, 104, 142), (38, 130, 142),
           (31, 158, 137), (53, 183, 121), (109, 205, 89), (180, 222, 44), (253, 231, 37)]


def _unit(lon: float, lat: float) -> tuple[float, float, float]:
    lo, la = math.radians(lon), math.radians(lat)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def _ang(a, b) -> float:
    """각거리(도) — 현 길이로(작은 각에서도 정확하다)."""
    c = math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)
    return math.degrees(2.0 * math.asin(min(1.0, c / 2.0)))


class _Index:
    """위도 순으로 늘어놓은 방향 — 위도 띠 · 경도 창으로 후보를 고른다."""

    def __init__(self, pts: list[tuple[float, float, float]], vals: list[float]):
        self.items = sorted(((math.degrees(math.asin(max(-1.0, min(1.0, p[2])))), math.degrees(math.atan2(p[1], p[0])), i)
                             for i, p in enumerate(pts)))
        self.lats = [x[0] for x in self.items]
        self.pts, self.vals = pts, vals

    def nearest(self, lon: float, lat: float, k: int) -> list[tuple[float, int]]:
        u = _unit(lon, lat)
        n = len(self.pts)
        k = min(k, n)
        theta = 10.0
        while True:
            if theta >= 180.0:
                cand = range(n)
            else:
                lo = bisect.bisect_left(self.lats, lat - theta)
                hi = bisect.bisect_right(self.lats, lat + theta)
                if abs(lat) + theta >= 90.0:
                    cand = [self.items[j][2] for j in range(lo, hi)]
                else:
                    half = math.degrees(math.asin(min(1.0, math.sin(math.radians(theta)) / math.cos(math.radians(lat)))))
                    cand = []
                    for j in range(lo, hi):
                        dl = abs(self.items[j][1] - lon) % 360.0
                        if min(dl, 360.0 - dl) <= half + 1e-9:
                            cand.append(self.items[j][2])
            got = sorted((_ang(u, self.pts[i]), i) for i in cand)
            inside = [g for g in got if g[0] <= theta]
            if len(inside) >= k or theta >= 180.0:
                return (inside if theta < 180.0 else got)[:k]
            theta *= 2.0


def grid(points: list[dict]) -> list[list[float]]:
    """`points` = `[{lon, lat, value}]`(두께 틀 · 도) → 격자[위도 181][경도 361]. 방향이 하나도 없으면 빈 목록."""
    pts = [_unit(p["lon"], p["lat"]) for p in points]
    vals = [float(p["value"]) for p in points]
    if not pts:
        return []
    idx = _Index(pts, vals)
    out = []
    for j in range(LAT_N):
        lat = -90.0 + j
        row = []
        cache = None
        for i in range(LON_N):
            lon = -180.0 + i
            if abs(lat) == 90.0 and cache is not None:      # 극은 한 점이다 — 경도마다 같은 값
                row.append(cache)
                continue
            nb = idx.nearest(lon, lat, K)
            ws = [1.0 / max(d, MIN_DEG) ** 2 for d, _ in nb]
            v = sum(w * vals[i2] for w, (_, i2) in zip(ws, nb)) / sum(ws)
            row.append(v)
            if abs(lat) == 90.0:
                cache = v
        out.append(row)
    return out


def center_shift(g: list[list[float]]) -> int:
    """cos(위도) 가중 경도 열 평균이 가장 큰 열의 경도(도 · 정수) — 그 열을 0° 로 돌린다."""
    best, arg = None, 0
    for i in range(LON_N - 1):                      # 마지막 열(180°)은 첫 열(−180°)과 같은 자리
        s = w = 0.0
        for j in range(LAT_N):
            c = math.cos(math.radians(-90.0 + j))
            s += c * g[j][i]
            w += c
        m = s / w
        if best is None or m > best + 1e-12:
            best, arg = m, i
    return int(-180 + arg)


def rotate(g: list[list[float]], shift: int) -> list[list[float]]:
    """경도를 shift 만큼 돌린다 — 새 격자의 경도 L 열 = 옛 격자의 L + shift 열."""
    out = []
    for row in g:
        base = row[:LON_N - 1]
        new = [base[(i + shift) % (LON_N - 1)] for i in range(LON_N - 1)]
        out.append(new + [new[0]])
    return out


def wrap_lon(lon: float) -> float:
    return (lon + 180.0) % 360.0 - 180.0


# ── 그림 ─────────────────────────────────────────────────────────────────────

def _band(v: float, lo: float, hi: float) -> int:
    if hi <= lo:
        return BANDS - 1
    return max(0, min(BANDS - 1, int((v - lo) / (hi - lo) * BANDS)))


def _sample(g, lon: float, lat: float) -> float:
    x = lon + 180.0
    y = lat + 90.0
    i0 = max(0, min(LON_N - 2, int(math.floor(x))))
    j0 = max(0, min(LAT_N - 2, int(math.floor(y))))
    fx, fy = x - i0, y - j0
    a = g[j0][i0] * (1 - fx) + g[j0][i0 + 1] * fx
    b = g[j0 + 1][i0] * (1 - fx) + g[j0 + 1][i0 + 1] * fx
    return a * (1 - fy) + b * fy


def _moll_forward(lon: float, lat: float) -> tuple[float, float]:
    """Mollweide (x, y) — x ∈ [−2√2, 2√2], y ∈ [−√2, √2]."""
    phi = math.radians(lat)
    t = phi
    for _ in range(50):
        f = 2 * t + math.sin(2 * t) - math.pi * math.sin(phi)
        d = 2 + 2 * math.cos(2 * t)
        if abs(d) < 1e-12:
            break
        dt = f / d
        t -= dt
        if abs(dt) < 1e-12:
            break
    return 2 * math.sqrt(2) / math.pi * math.radians(lon) * math.cos(t), math.sqrt(2) * math.sin(t)


def _png(w: int, h: int, rgba: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def raster_png(g, lo: float, hi: float, width: int = 720) -> bytes:
    """Mollweide 띠 칠 래스터(타원 밖은 투명) — 글자 없는 PNG."""
    h = width // 2
    s2 = math.sqrt(2)
    buf = bytearray(width * h * 4)
    for py in range(h):
        y = s2 * (1 - 2 * (py + 0.5) / h)
        t = math.asin(max(-1.0, min(1.0, y / s2)))
        lat = math.degrees(math.asin(max(-1.0, min(1.0, (2 * t + math.sin(2 * t)) / math.pi))))
        ct = math.cos(t)
        for px in range(width):
            x = 2 * s2 * (2 * (px + 0.5) / width - 1)
            if ct < 1e-9:
                continue
            lon = math.degrees(math.pi * x / (2 * s2 * ct))
            if abs(lon) > 180.0:
                continue
            c = PALETTE[_band(_sample(g, lon, lat), lo, hi)]
            k = (py * width + px) * 4
            buf[k:k + 4] = bytes((c[0], c[1], c[2], 255))
    return _png(width, h, bytes(buf))


def contours(g, lo: float, hi: float) -> list[list[tuple[float, float]]]:
    """띠 경계(등급 사이 9 값)의 선분 — 경위도 격자의 마칭 스퀘어. 선분 하나 = [(lon, lat), (lon, lat)]."""
    segs = []
    if hi <= lo:
        return segs
    levels = [lo + (hi - lo) * k / BANDS for k in range(1, BANDS)]
    for lv in levels:
        for j in range(LAT_N - 1):
            for i in range(LON_N - 1):
                v = (g[j][i], g[j][i + 1], g[j + 1][i + 1], g[j + 1][i])
                idx = sum(1 << n for n, x in enumerate(v) if x >= lv)
                if idx in (0, 15):
                    continue
                corners = ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
                pts = []
                for e in range(4):
                    a, b = e, (e + 1) % 4
                    if (v[a] >= lv) != (v[b] >= lv):
                        t = (lv - v[a]) / (v[b] - v[a])
                        x = corners[a][0] + (corners[b][0] - corners[a][0]) * t
                        y = corners[a][1] + (corners[b][1] - corners[a][1]) * t
                        pts.append((-180.0 + x, -90.0 + y))
                for k in range(0, len(pts) - 1, 2):
                    segs.append([pts[k], pts[k + 1]])
    return segs


def svg(g, lo: float, hi: float, points: list[dict], *, title: str, unit: str) -> str:
    """래스터 위에 등고선 · 방향 점 · 제목 · 띠 범례를 그린 SVG."""
    W, H, ox, oy = 720, 360, 20, 40
    png = base64.b64encode(raster_png(g, lo, hi, W)).decode()
    s2 = math.sqrt(2)

    def px(lon, lat):
        x, y = _moll_forward(lon, lat)
        return ox + (x / (2 * s2) + 1) / 2 * W, oy + (1 - y / s2) / 2 * H
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W + 2 * ox}" height="{H + oy + 70}" '
             f'viewBox="0 0 {W + 2 * ox} {H + oy + 70}" font-family="sans-serif">',
             '<rect width="100%" height="100%" fill="white"/>',
             f'<text x="{ox}" y="24" font-size="14">{_esc(title)}</text>',
             f'<image x="{ox}" y="{oy}" width="{W}" height="{H}" href="data:image/png;base64,{png}"/>']
    d = []
    for (a, b) in contours(g, lo, hi):
        if abs(a[0] - b[0]) > 90:
            continue
        x1, y1 = px(*a)
        x2, y2 = px(*b)
        d.append(f"M{x1:.1f} {y1:.1f}L{x2:.1f} {y2:.1f}")
    if d:
        parts.append(f'<path d="{"".join(d)}" stroke="black" stroke-width="0.5" stroke-opacity="0.6" fill="none"/>')
    for p in points:
        x, y = px(p["lon"], p["lat"])
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.6" fill="white" stroke="black" stroke-width="0.4"/>')
    bw = W / BANDS
    for k in range(BANDS):
        c = PALETTE[k]
        parts.append(f'<rect x="{ox + k * bw:.1f}" y="{oy + H + 15}" width="{bw:.1f}" height="12" fill="rgb{c}"/>')
    for k in range(BANDS + 1):
        v = lo + (hi - lo) * k / BANDS
        parts.append(f'<text x="{ox + k * bw:.1f}" y="{oy + H + 42}" font-size="9" text-anchor="middle">{v:.4g}</text>')
    parts.append(f'<text x="{ox + W}" y="{oy + H + 58}" font-size="10" text-anchor="end">{_esc(unit)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
