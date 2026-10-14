#!/bin/sh
# Start (or restart) the bridge under a nohup restart loop (watch.sh).
# Usage: scripts/supervise.sh [--callback-only] [--tunnel]
#   --callback-only  run only the /reply + /health server (no Discord token needed)
#   --tunnel         also start a Cloudflare quick tunnel and write .public_url
# Default callback URL is http://127.0.0.1:8787 (Grok Bots on this same box POST there).
# Does not survive a reboot unless cron @reboot / a keep-alive routine re-runs ensure-up.sh.
set -eu
DIR=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$DIR"
PYTHON="${DIR}/.venv/bin/python"
[ -x "$PYTHON" ] || { echo "run: python3 -m venv .venv && .venv/bin/pip install -e ." >&2; exit 1; }

MODE=""
TUNNEL=0
for arg in "$@"; do
  case "$arg" in
    --callback-only) MODE=--callback-only ;;
    --tunnel) TUNNEL=1 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

"$DIR/scripts/gen-callback-secret.sh"
. "$DIR/.env" 2>/dev/null || true
PORT="${CALLBACK_PORT:-8787}"

if [ -z "${DISCORD_BOT_TOKEN:-}" ] && [ -z "$MODE" ]; then
  echo "DISCORD_BOT_TOKEN empty; forcing --callback-only" >&2
  MODE=--callback-only
fi

for name in tunnel bridge; do
  if [ -f "$DIR/${name}.pid" ]; then
    kill "$(cat "$DIR/${name}.pid")" 2>/dev/null || true
    rm -f "$DIR/${name}.pid"
  fi
done
pkill -f "$DIR/watch.sh" 2>/dev/null || true
pkill -f "python -m grokbot_discord" 2>/dev/null || true
pkill -f "cloudflared tunnel" 2>/dev/null || true
sleep 1

if [ "$TUNNEL" = 1 ]; then
  "$DIR/scripts/tunnel.sh"
  echo "set CALLBACK_PUBLIC_URL_FILE=$DIR/.public_url in .env so wakes use the tunnel URL"
fi

nohup "$DIR/watch.sh" $MODE >>"$DIR/bridge.log" 2>&1 &
echo $! > "$DIR/bridge.pid"
echo "bridge supervisor pid $(cat "$DIR/bridge.pid") mode=${MODE:-gateway}"
i=0
while [ "$i" -lt 30 ]; do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "health ok: http://127.0.0.1:${PORT}/health"
    exit 0
  fi
  i=$((i + 1))
  sleep 1
done
echo "bridge did not become healthy; see bridge.log" >&2
exit 1
