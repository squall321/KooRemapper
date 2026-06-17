#!/usr/bin/env bash
# Phase 3 e2e: create session → upload .k → meta parsed → list → inspect →
# download (byte-match) → delete file → delete session.
set -uo pipefail
BASE="${1:-http://127.0.0.1:8700/api/v1}"
EMAIL="${KOORM_ADMIN_EMAIL:-admin@kooremapper.local}"
PASS="${KOORM_ADMIN_PASSWORD:-admin}"
KFILE="${KFILE:-/home/koopark/claude/KooRemapper/arc30_flat.k}"
pass=0; fail=0
chk() { if [ "$1" = "$2" ]; then echo "  ✓ $3"; pass=$((pass+1)); else echo "  ✗ $3 (got '$1' want '$2')"; fail=$((fail+1)); fi; }
jget() { python3 -c "import sys,json;d=json.load(sys.stdin);print($1)"; }

JWT=$(curl -fsS -X POST "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" | jget 'd["data"]["access_token"]')
AUTH=(-H "Authorization: Bearer $JWT")

echo "== create session =="
SID=$(curl -fsS -X POST "$BASE/sessions" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d '{"name":"phase3-test","description":"e2e"}' | jget 'd["data"]["id"]')
[ -n "$SID" ] && echo "  ✓ session $SID" || { echo "  ✗ no session"; exit 1; }

echo "== upload .k =="
UP=$(curl -fsS -X POST "$BASE/sessions/$SID/files" "${AUTH[@]}" -F "files=@$KFILE")
FID=$(echo "$UP" | jget 'd["data"][0]["id"]')
NODES=$(echo "$UP" | jget 'd["data"][0]["meta"].get("nodes")')
chk "$NODES" "363" "uploaded .k meta.nodes parsed (info ran)"

echo "== inspect =="
INSP=$(curl -fsS "$BASE/sessions/$SID/files/$FID/inspect" "${AUTH[@]}")
VALID=$(echo "$INSP" | jget 'd["data"]["meta"].get("valid")')
chk "$VALID" "True" "inspect shows valid mesh"
HASKW=$(echo "$INSP" | jget '"yes" if d["data"]["meta"].get("keyword_counts") else "no"')
chk "$HASKW" "yes" "inspect has keyword_counts"

echo "== list files =="
CNT=$(curl -fsS "$BASE/sessions/$SID/files" "${AUTH[@]}" | jget 'len(d["data"])')
chk "$CNT" "1" "one file listed"

echo "== download byte-match =="
curl -fsS "$BASE/sessions/$SID/files/$FID/download" "${AUTH[@]}" -o /tmp/koorm_dl.k
if cmp -s "$KFILE" /tmp/koorm_dl.k; then echo "  ✓ downloaded bytes match original"; pass=$((pass+1)); else echo "  ✗ byte mismatch"; fail=$((fail+1)); fi

echo "== session detail includes files =="
FC=$(curl -fsS "$BASE/sessions/$SID" "${AUTH[@]}" | jget 'd["data"]["file_count"]')
chk "$FC" "1" "session detail file_count=1"

echo "== delete file =="
curl -fsS -X DELETE "$BASE/sessions/$SID/files/$FID" "${AUTH[@]}" >/dev/null
CNT=$(curl -fsS "$BASE/sessions/$SID/files" "${AUTH[@]}" | jget 'len(d["data"])')
chk "$CNT" "0" "file deleted"

echo "== delete session =="
curl -fsS -X DELETE "$BASE/sessions/$SID" "${AUTH[@]}" >/dev/null
CODE=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/sessions/$SID" "${AUTH[@]}")
chk "$CODE" "404" "session deleted → 404"

echo
echo "RESULT: $pass passed, $fail failed"
[ "$fail" = 0 ]
