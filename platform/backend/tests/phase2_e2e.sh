#!/usr/bin/env bash
# Phase 2 end-to-end smoke: login → /me → issue PAT → use PAT → revoke → denied.
# Assumes the stack is running (start.sh) and admin seeded (seed.sh).
set -uo pipefail
BASE="${1:-http://127.0.0.1:8700/api/v1}"
EMAIL="${KOORM_ADMIN_EMAIL:-admin@local}"
PASS="${KOORM_ADMIN_PASSWORD:-admin}"
pass=0; fail=0
chk() { if [ "$1" = "$2" ]; then echo "  ✓ $3"; pass=$((pass+1)); else echo "  ✗ $3 (got '$1' want '$2')"; fail=$((fail+1)); fi; }

echo "== login =="
LOGIN=$(curl -fsS -X POST "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}")
JWT=$(echo "$LOGIN" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["access_token"])')
[ -n "$JWT" ] && echo "  ✓ got JWT" || { echo "  ✗ no JWT: $LOGIN"; exit 1; }

echo "== wrong password rejected =="
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' -d "{\"email\":\"$EMAIL\",\"password\":\"WRONG\"}")
chk "$CODE" "401" "bad login → 401"

echo "== /me with JWT =="
ME=$(curl -fsS "$BASE/me" -H "Authorization: Bearer $JWT")
ADMIN=$(echo "$ME" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["is_system_admin"])')
chk "$ADMIN" "True" "/me returns admin"

echo "== /me without token → 401 =="
CODE=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/me")
chk "$CODE" "401" "no token → 401"

echo "== issue PAT =="
TOK=$(curl -fsS -X POST "$BASE/me/tokens" -H "Authorization: Bearer $JWT" \
  -H 'Content-Type: application/json' -d '{"name":"phase2-test"}')
PAT=$(echo "$TOK" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["token"])')
TID=$(echo "$TOK" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["info"]["id"])')
case "$PAT" in kr_*) echo "  ✓ PAT has kr_ prefix"; pass=$((pass+1));; *) echo "  ✗ PAT prefix: $PAT"; fail=$((fail+1));; esac

echo "== use PAT on /me =="
MEPAT=$(curl -fsS "$BASE/me" -H "Authorization: Bearer $PAT")
EMAIL2=$(echo "$MEPAT" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["email"])')
chk "$EMAIL2" "$EMAIL" "PAT authenticates /me"

echo "== list tokens =="
LIST=$(curl -fsS "$BASE/me/tokens" -H "Authorization: Bearer $JWT")
ST=$(echo "$LIST" | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];print(d[0]["status"])')
chk "$ST" "active" "listed token active"

echo "== revoke PAT =="
curl -fsS -X DELETE "$BASE/me/tokens/$TID" -H "Authorization: Bearer $JWT" >/dev/null
CODE=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/me" -H "Authorization: Bearer $PAT")
chk "$CODE" "401" "revoked PAT → 401"

echo
echo "RESULT: $pass passed, $fail failed"
[ "$fail" = 0 ]
