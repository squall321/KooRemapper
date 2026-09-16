#!/usr/bin/env bash
# 리포트 분석 CLI 를 자립 번들로 추출 — SmartTwin 전처리 파이프라인 등에 드롭인.
# python3 만 있으면 되고(표준라이브러리만), 러닝 서비스·DB 불필요. 정본은 DynaForge 이고
# 이 스크립트로 복사 동기화한다(손으로 중복 유지 금지).
#   ./bundle-report-cli.sh [OUT_DIR]      # 기본: platform/dist/koo-report-cli
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$(cd "$SCRIPT_DIR/../../backend" && pwd)"
OUT="${1:-$(cd "$SCRIPT_DIR/../.." && pwd)/dist/koo-report-cli}"

rm -rf "$OUT"
mkdir -p "$OUT/app/reports"
# 빈 패키지 마커 — 실제 app/__init__ 은 FastAPI 를 끌어오므로 번들엔 빈 것으로(모듈은 stdlib-only).
: > "$OUT/app/__init__.py"
for f in __init__.py parser.py analyze.py cli.py; do
  cp "$BACKEND/app/reports/$f" "$OUT/app/reports/$f"
done

cat > "$OUT/koo-report-analyze" <<'LAUNCH'
#!/usr/bin/env bash
# DynaForge 리포트 분석 CLI(자립 번들) — python3 만 있으면 된다(외부 패키지 불요).
# CWD 는 유지(리포트 상대경로 보존)하고 번들 루트만 PYTHONPATH 에 얹는다.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec env PYTHONPATH="$here${PYTHONPATH:+:$PYTHONPATH}" "${PYTHON:-python3}" -m app.reports.cli "$@"
LAUNCH
chmod +x "$OUT/koo-report-analyze"

echo "✓ 번들 생성: $OUT"
echo "  실행 예: $OUT/koo-report-analyze REPORT.html[.gz] --do summary,angle-stats,scatter"
echo "  SmartTwin 반입: 이 디렉터리를 lib/ 에 두고 bin/ 에 koo-report-analyze 를 링크(또는 tar 소스에 편입)."
