#!/usr/bin/env bash
#
# publish-release.sh — publish a notarized Rigel DMG to its distribution channel
# and then announce it to beta subscribers (rigel-beta). Option "A".
#
# It expects the DMG already built by the app's build-dmg.sh (dist/<name>-vX.Y.Z.dmg
# and dist/<name>-latest.dmg, both stapled).
#
# Modes:
#   public — copy the versioned DMG + its -latest into
#            ~/developer/rigel-releases/dl/<subdir>/, git commit + push (LFS),
#            optionally trigger the Dokploy deploy (RIGEL_DEPLOY_HOOK), poll the
#            public -latest URL until it serves the new build, then notify beta.
#   drive  — rclone the versioned DMG to the access-controlled Drive folder, then
#            notify beta using --download-url (Drive has no stable public link).
#
# Usage:
#   publish-release.sh --mode public --repo <path> --beta-key <key> \
#       [--subdir nocboard] [--replace <old-versioned-dmg-name>] [--notes "..."]
#
#   publish-release.sh --mode drive  --repo <path> --beta-key <key> \
#       --download-url <url> [--drive-dest "gdrive:NOCBoard - Builds Operaciones"] \
#       [--replace <old-versioned-dmg-name>] [--notes "..."]
#
# Env:
#   RIGEL_RELEASES_DIR   default ~/developer/rigel-releases
#   RELEASES_BASE_URL    default https://releases.vivesincables.com/dl
#   RIGEL_DEPLOY_HOOK    optional Dokploy webhook URL for the rigel-releases compose.
#                        If set, POSTed to trigger the rebuild. If unset, the script
#                        polls anyway (trigger the deploy in Dokploy / via MCP).
#   BETA_API_URL         forwarded to notify-beta.sh (default https://beta.vivesincables.com)
#   BETA_ADMIN_KEY       forwarded to notify-beta.sh (required for a real notify)
#   SKIP_NOTIFY=1        publish only; skip the beta announcement
#   POLL_TIMEOUT         seconds to wait for the public URL to go live (default 600)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RIGEL_RELEASES_DIR="${RIGEL_RELEASES_DIR:-$HOME/developer/rigel-releases}"
RELEASES_BASE_URL="${RELEASES_BASE_URL:-https://releases.vivesincables.com/dl}"
DRIVE_DEST_DEFAULT="gdrive:NOCBoard - Builds Operaciones"
POLL_TIMEOUT="${POLL_TIMEOUT:-600}"

MODE="" REPO="" BETA_KEY="" SUBDIR="nocboard" REPLACE="" NOTES="" DOWNLOAD_URL="" DRIVE_DEST="$DRIVE_DEST_DEFAULT" DRYRUN=0

die() { echo "✘ $*" >&2; exit 1; }
info() { echo "▸ $*"; }

while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode) MODE="$2"; shift 2;;
    --repo) REPO="$2"; shift 2;;
    --beta-key) BETA_KEY="$2"; shift 2;;
    --subdir) SUBDIR="$2"; shift 2;;
    --replace) REPLACE="$2"; shift 2;;
    --notes) NOTES="$2"; shift 2;;
    --download-url) DOWNLOAD_URL="$2"; shift 2;;
    --drive-dest) DRIVE_DEST="$2"; shift 2;;
    --dry-run) DRYRUN=1; shift;;
    -h|--help) sed -n '2,40p' "$0"; exit 0;;
    *) die "unknown arg: $1";;
  esac
done

[ -n "$MODE" ] || die "missing --mode (public|drive)"
[ -n "$REPO" ] || die "missing --repo <path>"
[ -n "$BETA_KEY" ] || die "missing --beta-key <key>"
REPO="${REPO/#\~/$HOME}"
[ -d "$REPO" ] || die "repo not found: $REPO"
[ -f "$REPO/project.yml" ] || die "no project.yml in $REPO"

# --- Derive version + DMG names from the repo (same conventions as build-dmg.sh) ---
VERSION="$(awk '/^[[:space:]]*MARKETING_VERSION:/ {gsub(/[\"]/,""); print $2; exit}' "$REPO/project.yml")"
[ -n "$VERSION" ] || die "could not read MARKETING_VERSION"
BASENAME="$(awk -F'"' '/^DMG_BASENAME=/{print $2; exit}' "$REPO/build-dmg.sh")"
[ -n "$BASENAME" ] || BASENAME="$(awk -F'"' '/^APP_NAME=/{print $2; exit}' "$REPO/build-dmg.sh")"
[ -n "$BASENAME" ] || die "could not derive DMG basename from build-dmg.sh"

VERSIONED="$REPO/dist/${BASENAME}-v${VERSION}.dmg"
LATEST="$REPO/dist/${BASENAME}-latest.dmg"
[ -f "$VERSIONED" ] || die "missing $VERSIONED (build it first: NOTARIZE=1 ./build-dmg.sh)"

info "App:      $BASENAME  v$VERSION"
info "Beta key: $BETA_KEY"
info "DMG:      $VERSIONED"

# Sanity: notarization stapled (warn only).
if ! xcrun stapler validate "$VERSIONED" >/dev/null 2>&1; then
  echo "⚠ warning: $VERSIONED is not stapled (notarize before publishing to the public server)" >&2
fi

LOCAL_SHA="$(shasum -a 256 "$VERSIONED" | awk '{print $1}')"

notify() {
  local url="$1"
  if [ "${SKIP_NOTIFY:-0}" = "1" ]; then info "SKIP_NOTIFY=1 → not announcing to beta."; return 0; fi
  info "Announcing to beta subscribers ($BETA_KEY v$VERSION)..."
  "$SCRIPT_DIR/notify-beta.sh" "$BETA_KEY" "$VERSION" "$url" "$NOTES"
}

case "$MODE" in
  public)
    DEST_DIR="$RIGEL_RELEASES_DIR/dl/$SUBDIR"
    [ -d "$DEST_DIR" ] || die "releases dir not found: $DEST_DIR (is RIGEL_RELEASES_DIR right?)"
    [ -f "$LATEST" ] || die "missing $LATEST (the -latest copy; rebuild with build-dmg.sh)"
    PUB_URL="$RELEASES_BASE_URL/$SUBDIR/${BASENAME}-latest.dmg"

    if [ "$DRYRUN" = "1" ]; then
      echo "[dry-run] cp $VERSIONED $LATEST -> $DEST_DIR/"
      [ -n "$REPLACE" ] && echo "[dry-run] git rm $DEST_DIR/$REPLACE"
      echo "[dry-run] git commit + push (in $RIGEL_RELEASES_DIR)"
      echo "[dry-run] trigger deploy: ${RIGEL_DEPLOY_HOOK:-<none, poll only>}"
      echo "[dry-run] poll $PUB_URL until 200 + sha==$LOCAL_SHA"
      echo "[dry-run] notify-beta.sh $BETA_KEY $VERSION $PUB_URL"
      exit 0
    fi

    info "Publishing to $DEST_DIR ..."
    cp "$VERSIONED" "$LATEST" "$DEST_DIR/"
    ( cd "$RIGEL_RELEASES_DIR"
      git fetch origin -q || true
      [ -n "$REPLACE" ] && git rm -q --ignore-unmatch "dl/$SUBDIR/$REPLACE" || true
      git add "dl/$SUBDIR/${BASENAME}-v${VERSION}.dmg" "dl/$SUBDIR/${BASENAME}-latest.dmg"
      git commit -q -m "publish ${BASENAME} v${VERSION} + refresh -latest" || { echo "nothing to commit"; }
      git push origin main )

    if [ -n "${RIGEL_DEPLOY_HOOK:-}" ]; then
      info "Triggering Dokploy deploy hook..."
      curl -fsS -X POST "$RIGEL_DEPLOY_HOOK" >/dev/null && info "deploy triggered" || echo "⚠ deploy hook failed; trigger it manually in Dokploy" >&2
    else
      echo "ℹ RIGEL_DEPLOY_HOOK not set — trigger the rigel-releases compose deploy in Dokploy (or via MCP). Polling meanwhile..."
    fi

    info "Polling $PUB_URL (up to ${POLL_TIMEOUT}s) ..."
    waited=0
    while [ "$waited" -lt "$POLL_TIMEOUT" ]; do
      sleep 15; waited=$((waited+15))
      code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$PUB_URL" || echo 000)"
      if [ "$code" = "200" ]; then
        served="$(curl -s --max-time 90 "$PUB_URL" | shasum -a 256 | awk '{print $1}')"
        if [ "$served" = "$LOCAL_SHA" ]; then
          info "✔ live: $PUB_URL (sha matches, t+${waited}s)"
          notify "$PUB_URL"
          echo "✅ Done."
          exit 0
        fi
      fi
      echo "  t+${waited}s  http=$code (waiting for new build to serve)"
    done
    die "timed out after ${POLL_TIMEOUT}s — the deploy may not have been triggered. Deploy rigel-releases, then re-run (or run notify-beta.sh manually)."
    ;;

  drive)
    [ -n "$DOWNLOAD_URL" ] || die "--download-url is required in drive mode (Drive has no stable public link)"
    if [ "$DRYRUN" = "1" ]; then
      echo "[dry-run] rclone copy $VERSIONED -> $DRIVE_DEST/"
      [ -n "$REPLACE" ] && echo "[dry-run] rclone deletefile $DRIVE_DEST/$REPLACE"
      echo "[dry-run] notify-beta.sh $BETA_KEY $VERSION $DOWNLOAD_URL"
      exit 0
    fi
    info "Uploading to Drive: $DRIVE_DEST ..."
    rclone copy "$VERSIONED" "$DRIVE_DEST/"
    [ -n "$REPLACE" ] && { rclone deletefile "$DRIVE_DEST/$REPLACE" && info "removed old $REPLACE" || echo "⚠ could not remove $REPLACE"; }
    notify "$DOWNLOAD_URL"
    echo "✅ Done."
    ;;

  *) die "unknown --mode '$MODE' (use public|drive)";;
esac
