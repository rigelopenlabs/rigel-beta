#!/usr/bin/env bash
#
# notify-beta.sh — publish a new release to rigel-beta and email confirmed subscribers.
#
# Usage:
#   notify-beta.sh <app_key> <version> <download_url> [notes]
#
# Env:
#   BETA_API_URL    base URL of the rigel-beta service (default http://localhost:9486)
#   BETA_ADMIN_KEY  admin API key, must match the server's BETA_ADMIN_KEY (default dev-admin-key)
#
# Example:
#   BETA_ADMIN_KEY=secret notify-beta.sh nocboard-energia 3.5.0 \
#     https://releases.vivesincables.com/dl/nocboard/NOCBoard-Energia-latest.dmg "Fix crash"
#
set -euo pipefail

BETA_API_URL="${BETA_API_URL:-http://localhost:9486}"
BETA_ADMIN_KEY="${BETA_ADMIN_KEY:-dev-admin-key}"

usage() {
  echo "Usage: $(basename "$0") <app_key> <version> <download_url> [notes]" >&2
  echo "  BETA_API_URL (default http://localhost:9486), BETA_ADMIN_KEY required for auth." >&2
  exit 64
}

[ "$#" -ge 3 ] || usage

APP_KEY="$1"
VERSION="$2"
DOWNLOAD_URL="$3"
NOTES="${4:-}"

[ -n "$APP_KEY" ]      || { echo "error: app_key is empty" >&2; usage; }
[ -n "$VERSION" ]      || { echo "error: version is empty" >&2; usage; }
[ -n "$DOWNLOAD_URL" ] || { echo "error: download_url is empty" >&2; usage; }

# Build JSON safely. Prefer python3 for proper escaping; fall back to a minimal heredoc.
if command -v python3 >/dev/null 2>&1; then
  PAYLOAD="$(python3 - "$APP_KEY" "$VERSION" "$DOWNLOAD_URL" "$NOTES" <<'PY'
import json, sys
app_key, version, url, notes = sys.argv[1:5]
print(json.dumps({"app_key": app_key, "version": version,
                  "download_url": url, "notes": notes}))
PY
)"
else
  PAYLOAD="{\"app_key\":\"$APP_KEY\",\"version\":\"$VERSION\",\"download_url\":\"$DOWNLOAD_URL\",\"notes\":\"$NOTES\"}"
fi

echo ">> POST ${BETA_API_URL}/api/releases  (app=${APP_KEY} v${VERSION})" >&2

RESPONSE="$(curl -fsS -X POST "${BETA_API_URL}/api/releases" \
  -H "X-API-Key: ${BETA_ADMIN_KEY}" \
  -H 'Content-Type: application/json' \
  -d "${PAYLOAD}")"

echo "$RESPONSE"

# Pretty-print the sent count if python3 is around.
if command -v python3 >/dev/null 2>&1; then
  echo "$RESPONSE" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("sent:", d.get("sent"), "(recipients:", str(d.get("recipients"))+")")' 2>/dev/null || true
fi
