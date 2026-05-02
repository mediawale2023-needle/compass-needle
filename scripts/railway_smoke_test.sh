#!/usr/bin/env bash
set -euo pipefail

PASS_COUNT=0
FAIL_COUNT=0

red() { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
blue() { printf '\033[34m%s\033[0m\n' "$*"; }

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  green "PASS: $*"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  red "FAIL: $*"
}

step() {
  printf '\n'
  blue "==> $*"
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    red "Missing required command: $cmd"
    exit 1
  fi
}

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    red "Missing required env var: $name"
    exit 1
  fi
}

http_code() {
  local method="$1"
  local url="$2"
  shift 2
  curl -sS -o /tmp/railway_smoke_body.$$ -w "%{http_code}" -X "$method" "$url" "$@"
}

json_field() {
  local expr="$1"
  jq -r "$expr // empty" 2>/dev/null
}

print_body() {
  if [[ -f /tmp/railway_smoke_body.$$ ]]; then
    sed -n '1,120p' /tmp/railway_smoke_body.$$
  fi
}

cleanup() {
  rm -f /tmp/railway_smoke_body.$$ >/dev/null 2>&1 || true
}
trap cleanup EXIT

require_cmd curl
require_cmd jq
require_cmd openssl

require_env BACKEND_URL
require_env MP_URL
require_env ADMIN_URL
require_env MP_USERNAME
require_env MP_PASSWORD
require_env ADMIN_USERNAME
require_env ADMIN_PASSWORD
require_env META_APP_SECRET
require_env TEST_SENDER
require_env WA_DISPLAY_NUMBER

SMOKE_TEXT="${SMOKE_TEXT:-Smoke test grievance: no water supply in Whitefield for 2 days}"
SMOKE_REPLY="${SMOKE_REPLY:-Production smoke test reply from Compass Needle.}"
SMOKE_PREFIX="${SMOKE_PREFIX:-SMOKETEST}"
SMOKE_ID="${SMOKE_PREFIX}$(date +%s)"

step "Public Surface Checks"
code=$(http_code GET "$BACKEND_URL/health")
if [[ "$code" == "200" ]]; then
  pass "Backend /health returned 200"
else
  fail "Backend /health returned $code"
  print_body
fi

code=$(http_code GET "$BACKEND_URL/docs")
if [[ "$code" == "200" ]]; then
  pass "Backend /docs returned 200"
else
  fail "Backend /docs returned $code"
fi

code=$(http_code HEAD "$MP_URL")
if [[ "$code" =~ ^(200|301|302|307|308)$ ]]; then
  pass "MP frontend returned $code"
else
  fail "MP frontend returned $code"
fi

code=$(http_code HEAD "$ADMIN_URL")
if [[ "$code" =~ ^(200|301|302|307|308)$ ]]; then
  pass "Admin frontend returned $code"
else
  fail "Admin frontend returned $code"
fi

step "MP Login"
MP_LOGIN_PAYLOAD=$(jq -n --arg u "$MP_USERNAME" --arg p "$MP_PASSWORD" '{username:$u,password:$p}')
code=$(http_code POST "$BACKEND_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  --data "$MP_LOGIN_PAYLOAD")
if [[ "$code" == "200" ]]; then
  MP_TOKEN=$(json_field '.token' < /tmp/railway_smoke_body.$$)
  if [[ -n "${MP_TOKEN:-}" ]]; then
    pass "MP login succeeded"
  else
    fail "MP login response missing token"
  fi
else
  fail "MP login returned $code"
  print_body
fi

code=$(http_code GET "$BACKEND_URL/api/auth/me" \
  -H "Authorization: Bearer ${MP_TOKEN:-invalid}")
if [[ "$code" == "200" ]]; then
  pass "MP token validated via /api/auth/me"
else
  fail "MP /api/auth/me returned $code"
  print_body
fi

step "Admin Login"
ADMIN_LOGIN_PAYLOAD=$(jq -n --arg u "$ADMIN_USERNAME" --arg p "$ADMIN_PASSWORD" '{username:$u,password:$p}')
code=$(http_code POST "$BACKEND_URL/api/admin/auth/login" \
  -H "Content-Type: application/json" \
  --data "$ADMIN_LOGIN_PAYLOAD")
if [[ "$code" == "200" ]]; then
  ADMIN_TOKEN=$(json_field '.token' < /tmp/railway_smoke_body.$$)
  if [[ -n "${ADMIN_TOKEN:-}" ]]; then
    pass "Admin login succeeded"
  else
    fail "Admin login response missing token"
  fi
else
  fail "Admin login returned $code"
  print_body
fi

code=$(http_code GET "$BACKEND_URL/api/admin/stats" \
  -H "Authorization: Bearer ${ADMIN_TOKEN:-invalid}")
if [[ "$code" == "200" ]]; then
  pass "Admin token validated via /api/admin/stats"
else
  fail "Admin /api/admin/stats returned $code"
  print_body
fi

step "Signed Webhook"
BODY=$(jq -nc \
  --arg display "$WA_DISPLAY_NUMBER" \
  --arg msg_id "wamid.${SMOKE_ID}" \
  --arg sender "$TEST_SENDER" \
  --arg text "$SMOKE_TEXT" \
  '{
    entry: [{
      changes: [{
        value: {
          metadata: {display_phone_number: $display},
          messages: [{
            id: $msg_id,
            from: $sender,
            type: "text",
            text: {body: $text}
          }]
        }
      }]
    }]
  }')

SIG="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$META_APP_SECRET" -hex | awk '{print $NF}')"
code=$(http_code POST "$BACKEND_URL/whatsapp/webhook" \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $SIG" \
  --data "$BODY")
if [[ "$code" == "200" ]]; then
  pass "Signed webhook accepted"
else
  fail "Signed webhook returned $code"
  print_body
fi

step "Case Visibility"
sleep "${CASE_SEARCH_DELAY_SECONDS:-2}"
code=$(http_code GET "$BACKEND_URL/api/cases?search=$TEST_SENDER" \
  -H "Authorization: Bearer ${MP_TOKEN:-invalid}")
if [[ "$code" == "200" ]]; then
  CASE_ID=$(json_field '.cases[0].id' < /tmp/railway_smoke_body.$$)
  if [[ -n "${CASE_ID:-}" && "${CASE_ID:-null}" != "null" ]]; then
    pass "Smoke-test case visible to MP (case_id=$CASE_ID)"
  else
    fail "Case search succeeded but no case found for $TEST_SENDER"
    print_body
  fi
else
  fail "Case search returned $code"
  print_body
fi

step "Outbound Citizen Notify"
if [[ -n "${CASE_ID:-}" && "${CASE_ID:-null}" != "null" ]]; then
  PATCH_PAYLOAD=$(jq -n --arg reply "$SMOKE_REPLY" '{response_to_citizen:$reply,notes_for_staff:"Smoke test note."}')
  code=$(http_code PATCH "$BACKEND_URL/api/cases/$CASE_ID" \
    -H "Authorization: Bearer $MP_TOKEN" \
    -H "Content-Type: application/json" \
    --data "$PATCH_PAYLOAD")
  if [[ "$code" == "200" ]]; then
    pass "Case patch succeeded"
  else
    fail "Case patch returned $code"
    print_body
  fi

  NOTIFY_PAYLOAD=$(jq -n --arg msg "$SMOKE_REPLY" '{message:$msg}')
  code=$(http_code POST "$BACKEND_URL/api/cases/$CASE_ID/notify/send" \
    -H "Authorization: Bearer $MP_TOKEN" \
    -H "Content-Type: application/json" \
    --data "$NOTIFY_PAYLOAD")
  if [[ "$code" == "200" ]]; then
    pass "Citizen notify/send endpoint succeeded"
  else
    fail "Citizen notify/send returned $code"
    print_body
  fi
else
  fail "Skipping outbound notify because CASE_ID is missing"
fi

step "Webhook Rejection Checks"
code=$(http_code POST "$BACKEND_URL/whatsapp/webhook" \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=badbadbad" \
  --data "$BODY")
if [[ "$code" == "403" ]]; then
  pass "Bad webhook signature rejected with 403"
else
  fail "Bad webhook signature returned $code"
  print_body
fi

BAD='}{bad json}'
BAD_SIG="sha256=$(printf '%s' "$BAD" | openssl dgst -sha256 -hmac "$META_APP_SECRET" -hex | awk '{print $NF}')"
code=$(http_code POST "$BACKEND_URL/whatsapp/webhook" \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $BAD_SIG" \
  --data "$BAD")
if [[ "$code" == "400" ]]; then
  pass "Malformed JSON rejected with 400"
else
  fail "Malformed JSON returned $code"
  print_body
fi

printf '\n'
blue "Smoke Test Summary"
printf 'Passed: %d\n' "$PASS_COUNT"
printf 'Failed: %d\n' "$FAIL_COUNT"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
