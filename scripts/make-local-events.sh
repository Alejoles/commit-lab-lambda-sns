#!/usr/bin/env bash
# Generate events/local/*.json from the placeholder templates in events/.
# events/local/ is git-ignored, so real values never reach the repository.
#
# Usage:
#   ACCOUNT_ID=123456789012 REGION=eu-west-1 [API_ID=abc123defg] ./scripts/make-local-events.sh
set -euo pipefail

: "${ACCOUNT_ID:?Set ACCOUNT_ID}"
: "${REGION:?Set REGION}"
API_ID="${API_ID:-<API_ID>}"  # unknown until the REST API is created (lab step 5)

root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$root/events/local"

for template in "$root"/events/*.json; do
  python3 - "$template" "$root/events/local/$(basename "$template")" \
    "$ACCOUNT_ID" "$REGION" "$API_ID" <<'PY'
import sys
src, dst, account_id, region, api_id = sys.argv[1:]
text = open(src, encoding="utf-8").read()
text = (text.replace("<ACCOUNT_ID>", account_id)
            .replace("<REGION>", region)
            .replace("<API_ID>", api_id))
open(dst, "w", encoding="utf-8").write(text)
PY
done

echo "Generated events in events/local/"
