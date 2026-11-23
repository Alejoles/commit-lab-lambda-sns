#!/usr/bin/env bash
# Smoke tests against the deployed API.
# Usage: URL=https://<API_ID>.execute-api.<REGION>.amazonaws.com/dev/register ./scripts/smoke.sh
set -u

if [ -z "${URL:-}" ]; then
  echo "Set URL to the full Invoke URL, e.g. https://<API_ID>.execute-api.<REGION>.amazonaws.com/dev/register" >&2
  exit 1
fi

failures=0

# check <description> <expected status> <request body>
check() {
  local description="$1" expected="$2" body="$3"
  echo "== ${description} (expected HTTP ${expected})"
  local output status
  output=$(curl -s -i -X POST "$URL" -H 'Content-Type: application/json' -d "$body")
  echo "$output"
  status=$(printf '%s' "$output" | head -n 1 | awk '{print $2}')
  if [ "$status" != "$expected" ]; then
    echo "FAIL: got HTTP ${status:-none}" >&2
    failures=$((failures + 1))
  fi
  echo
}

check "Success" 200 '{"name":"Carlos López","email":"carlos@email.com"}'
check "Missing field (email)" 400 '{"name":"Carlos López"}'
check "Invalid JSON" 400 '{"name":'

if [ "$failures" -gt 0 ]; then
  echo "${failures} check(s) failed" >&2
  exit 1
fi
echo "All checks passed"
