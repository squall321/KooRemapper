#!/usr/bin/env bash
# Phase 5 e2e: upload meshes → run `map` job → poll → outputs registered →
# download result; plus an `info` job; plus a failing job surfaces error.
set -uo pipefail
BASE="${1:-http://127.0.0.1:8700/api/v1}"
EMAIL="${KOORM_ADMIN_EMAIL:-admin@kooremapper.local}"
PASS="${KOORM_ADMIN_PASSWORD:-admin}"
EX=/home/koopark/claude/KooRemapper/examples/arc30
pass=0; fail=0
chk(){ if [ "$1" = "$2" ]; then echo "  ✓ $3"; pass=$((pass+1)); else echo "  ✗ $3 (got '$1' want '$2')"; fail=$((fail+1)); fi; }
jget(){ python3 -c "import sys,json;d=json.load(sys.stdin);print($1)"; }

JWT=$(curl -fsS -X POST "$BASE/auth/login" -H 'Content-Type: application/json' -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" | jget 'd["data"]["access_token"]')
AUTH=(-H "Authorization: Bearer $JWT")

echo "== setup session + upload bent/flat =="
SID=$(curl -fsS -X POST "$BASE/sessions" "${AUTH[@]}" -H 'Content-Type: application/json' -d '{"name":"phase5"}' | jget 'd["data"]["id"]')
ls "$EX"/arc30_bent.k "$EX"/arc30_flat.k >/dev/null || { echo "missing example files"; exit 1; }
curl -fsS -X POST "$BASE/sessions/$SID/files" "${AUTH[@]}" -F "files=@$EX/arc30_bent.k" -F "files=@$EX/arc30_flat.k" >/dev/null
echo "  session $SID + 2 files"

poll(){  # $1 job_id -> echoes final status
  local jid="$1" st=""
  for i in $(seq 1 60); do
    st=$(curl -fsS "$BASE/jobs/$jid" "${AUTH[@]}" | jget 'd["data"]["status"]')
    case "$st" in succeeded|failed|canceled) echo "$st"; return;; esac
    sleep 1
  done
  echo "$st"
}

echo "== run map job =="
JID=$(curl -fsS -X POST "$BASE/sessions/$SID/jobs" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d '{"operation":"map","args":{"bent_mesh":"arc30_bent.k","flat_mesh":"arc30_flat.k","output":"mapped.k"}}' | jget 'd["data"]["id"]')
ST=$(poll "$JID"); chk "$ST" "succeeded" "map job succeeded"
NOUT=$(curl -fsS "$BASE/jobs/$JID/outputs" "${AUTH[@]}" | jget 'len(d["data"])')
[ "$NOUT" -ge 1 ] && { echo "  ✓ map produced $NOUT output(s)"; pass=$((pass+1)); } || { echo "  ✗ no outputs"; fail=$((fail+1)); }
OFID=$(curl -fsS "$BASE/jobs/$JID/outputs" "${AUTH[@]}" | jget '[f for f in d["data"] if f["filename"]=="mapped.k"][0]["id"]')
MNODES=$(curl -fsS "$BASE/jobs/$JID/outputs" "${AUTH[@]}" | jget '[f for f in d["data"] if f["filename"]=="mapped.k"][0]["meta"].get("nodes",0)')
[ "${MNODES:-0}" -gt 0 ] && { echo "  ✓ output mapped.k auto-inspected (nodes=$MNODES)"; pass=$((pass+1)); } || { echo "  ✗ output not inspected"; fail=$((fail+1)); }
curl -fsS "$BASE/sessions/$SID/files/$OFID/download" "${AUTH[@]}" -o /tmp/koorm_mapped.k
[ -s /tmp/koorm_mapped.k ] && { echo "  ✓ output downloadable ($(wc -c </tmp/koorm_mapped.k) bytes)"; pass=$((pass+1)); } || { echo "  ✗ download empty"; fail=$((fail+1)); }

echo "== run info job (logs) =="
JID2=$(curl -fsS -X POST "$BASE/sessions/$SID/jobs" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d '{"operation":"info","args":{"mesh_file":"arc30_bent.k"}}' | jget 'd["data"]["id"]')
ST2=$(poll "$JID2"); chk "$ST2" "succeeded" "info job succeeded"
LOG=$(curl -fsS "$BASE/jobs/$JID2/logs" "${AUTH[@]}")
echo "$LOG" | grep -q "Nodes:" && { echo "  ✓ info job logs captured"; pass=$((pass+1)); } || { echo "  ✗ no log content"; fail=$((fail+1)); }

echo "== failing job surfaces error =="
# pre-validation: missing input file → 422 at creation (not a worker failure)
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/sessions/$SID/jobs" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d '{"operation":"map","args":{"bent_mesh":"nonexistent.k","flat_mesh":"arc30_flat.k","output":"x.k"}}')
chk "$CODE" "422" "missing input file rejected at creation (422)"

# worker-level failure: corrupt .k passes pre-validation but the binary fails → status failed + error_summary
printf 'this is not a valid k-file\n' > /tmp/koorm_bad.k
curl -fsS -X POST "$BASE/sessions/$SID/files" "${AUTH[@]}" -F "files=@/tmp/koorm_bad.k" >/dev/null
JID3=$(curl -fsS -X POST "$BASE/sessions/$SID/jobs" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d '{"operation":"map","args":{"bent_mesh":"koorm_bad.k","flat_mesh":"arc30_flat.k","output":"x.k"}}' | jget 'd["data"]["id"]')
ST3=$(poll "$JID3"); chk "$ST3" "failed" "map with corrupt input → failed"
ERR=$(curl -fsS "$BASE/jobs/$JID3" "${AUTH[@]}" | jget 'bool(d["data"]["error_summary"])')
chk "$ERR" "True" "failed job has error_summary"

echo "== job history =="
NJOBS=$(curl -fsS "$BASE/sessions/$SID/jobs" "${AUTH[@]}" | jget 'len(d["data"])')
chk "$NJOBS" "3" "session has 3 jobs in history"

curl -fsS -X DELETE "$BASE/sessions/$SID" "${AUTH[@]}" >/dev/null
echo; echo "RESULT: $pass passed, $fail failed"
[ "$fail" = 0 ]
