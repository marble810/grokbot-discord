#!/bin/sh
# Cloudflare quick tunnel for the local callback port.
# Writes the public https URL to $CALLBACK_PUBLIC_URL_FILE (default: .public_url).
# Quick-tunnel hostnames change on every restart — the bridge re-reads that file
# on every wake, so you do not need to restart the Python process.
set -eu
DIR=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$DIR"
. "$DIR/.env" 2>/dev/null || true
PORT="${CALLBACK_PORT:-8787}"
URL_FILE="${CALLBACK_PUBLIC_URL_FILE:-$DIR/.public_url}"
LOG="$DIR/tunnel.log"
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared not installed" >&2
  exit 1
fi
: > "$LOG"
# Start in background; scrape the trycloudflare.com URL as it appears.
cloudflared tunnel --protocol "${TUNNEL_PROTOCOL:-http2}" --url "http://127.0.0.1:${PORT}" --no-autoupdate >>"$LOG" 2>&1 &
echo $! > "$DIR/tunnel.pid"
echo "cloudflared pid $(cat "$DIR/tunnel.pid"); waiting for public URL…"
i=0
while [ "$i" -lt 60 ]; do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)
  if [ -n "$URL" ]; then
    printf '%s\n' "$URL" > "$URL_FILE"
    chmod 600 "$URL_FILE"
    echo "public URL: $URL (saved to $URL_FILE)"
    exit 0
  fi
  i=$((i + 1))
  sleep 1
done
echo "timed out waiting for trycloudflare URL; see $LOG" >&2
exit 1
