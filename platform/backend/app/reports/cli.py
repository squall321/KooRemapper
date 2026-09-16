# 낙하/충격 리포트(deep/sphere/impact) HTML 을 서버·DB 없이 분석하는 CLI — SmartTwin 파이프라인 번들용.
# 표준라이브러리 + parser/analyze(모두 stdlib-only)만 쓴다. 사용:
#   python -m app.reports.cli REPORT.html[.gz] --do summary,scatter,angle-stats [--metric ..] [--part-id N]
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

from app.reports import analyze, parser

_ALL = ["summary", "available-metrics", "angle-stats", "directional", "scatter",
        "energy", "part-series", "part-energy", "geometry"]


def _read_text(path: str) -> str:
    """리포트 파일을 텍스트로 — .gz(매직바이트/확장자)면 해제."""
    raw = Path(path).read_bytes()
    if raw[:2] == b"\x1f\x8b" or path.lower().endswith(".gz"):
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def _summary(study: dict) -> dict:
    return {
        "kind": study.get("kind"),
        "project": study.get("project"),
        "n_cases": len(study.get("cases") or []),
        "n_parts": len(study.get("parts") or []),
        "summary": study.get("summary"),
        "findings": study.get("findings"),
    }


def run(args: argparse.Namespace) -> dict:
    """요청한 분석들을 실행해 {분석명: 결과} 로 모은다."""
    text = _read_text(args.report)
    data = parser.extract_embedded_data(text)
    kind = args.kind or parser.detect_kind(data)
    study = parser.parse_data(data, kind_hint=kind)
    kind = study.get("kind", kind)
    cases = study.get("cases") or []
    parts = study.get("parts") or []
    do = _ALL if args.do == "all" else [d.strip() for d in args.do.split(",") if d.strip()]

    out: dict = {}
    for d in do:
        if d == "summary":
            out[d] = _summary(study)
        elif d == "available-metrics":
            out[d] = analyze.available_metrics(cases)
        elif d == "angle-stats":
            out[d] = analyze.angle_group_stats(
                cases, kind, parts, metric=args.metric, part_id=args.part_id,
                category=args.category, angle_name=args.angle_name, near_lon=args.near_lon,
                near_lat=args.near_lat, tol_deg=args.tol_deg, top_parts=args.top_parts)
        elif d == "directional":
            out[d] = analyze.directional(cases, kind, parts, args.part_id)
        elif d == "scatter":
            out[d] = parser.scatter_analysis(data, kind, metric=args.metric, part_id=args.part_id)
        elif d == "energy":
            out[d] = parser.case_energy(data, kind, args.case_key)
        elif d == "part-series":
            if not args.case_key or args.part_id is None:
                out[d] = {"error": "part-series 는 --case-key 와 --part-id 가 필요합니다."}
            else:
                out[d] = parser.part_series(data, kind, args.case_key, args.part_id)
        elif d == "part-energy":
            out[d] = parser.part_energy_series(data, kind, args.part_id)
        elif d == "geometry":
            out[d] = parser.extract_geometry(data, kind)
        else:
            out[d] = {"error": f"알 수 없는 분석: {d} (가능: {','.join(_ALL)})"}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m app.reports.cli",
        description="낙하/충격 리포트 HTML 분석(서버·DB 불필요) — 결과 JSON 을 stdout 으로.")
    ap.add_argument("report", help="리포트 HTML 경로(.gz 가능)")
    ap.add_argument("--do", default="summary",
                    help=f"분석 목록(쉼표) 또는 'all'. 가능: {','.join(_ALL)}")
    ap.add_argument("--metric", default="peak_stress", help="물리량(peak_stress/peak_strain/peak_plastic_strain/peak_g/peak_disp/peak_vel/peak_ie/peak_ke …)")
    ap.add_argument("--part-id", type=int, default=None)
    ap.add_argument("--category", default=None, help="각도군: 면/엣지/코너 또는 impact face(F1..)")
    ap.add_argument("--angle-name", default=None, help="기준방향명(퍼터베이션 구름, sphere)")
    ap.add_argument("--near-lon", type=float, default=None)
    ap.add_argument("--near-lat", type=float, default=None)
    ap.add_argument("--tol-deg", type=float, default=15.0)
    ap.add_argument("--top-parts", type=int, default=5)
    ap.add_argument("--case-key", default=None, help="energy/part-series 대상 케이스")
    ap.add_argument("--kind", default=None, choices=["deep", "sphere", "impact"], help="자동판별 덮어쓰기")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args(argv)
    try:
        out = run(args)
    except parser.ReportParseError as exc:
        print(json.dumps({"error": f"리포트 파싱 실패: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2 if args.pretty else None, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
