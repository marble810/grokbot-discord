#!/bin/sh
# Start (or restart) the Cloudflare quick tunnel + the Discord bridge under nohup.
# Survives the current shell; does not survive a full reboot unless something
# (cron @reboot, Grok Bot keep-alive) re-runs this script.
set -eu
DIR=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$DIR"
. "$DIR/.env" 2>/dev/null || true
PYTHON="${DIR}/.venv/bin/python"
[ -x "$PYTHON" ] || { echo "run: python3.12 -m venv .venv && .venv/bin/pip install -e ." >&2; exit 1; }

"$DIR/scripts/gen-callback-secret.sh"

# Point the bridge at the file the tunnel rewrites.
grep -q '^CALLBACK_PUBLIC_URL_FILE=' .env 2>/dev/null \
  || printf 'CALLBACK_PUBLIC_URL_FILE=%s\n' "$DIR/.public_url" >> .env
# Bind so cloudflared can reach us (still localhost-only from the outside).
grep -q '^CALLBACK_BIND=' .env 2>/dev/null || printf 'CALLBACK_BIND=127.0.0.1\n' >> .env

# Kill prior tunnel / bridge if we own their pid files.
for name in tunnel bridge; do
  if [ -f "$DIR/${name}.pid" ]; then
    kill "$(cat "$DIR/${name}.pid")" 2>/dev/null || true
    rm -f "$DIR/${name}.pid"
  fi
done
# Also kill a leftover watch.sh / bridge by pattern (best-effort).
pkill -f "$DIR/watch.sh" 2>/dev/null || true
pkill -f "python -m grokbot_discord" 2>/dev/null || true
pkill -f "cloudflared tunnel" 2>/dev/null || true
sleep 1

"$DIR/scripts/tunnel.sh"

MODE="${1:---callback-only}"
# Default is callback-only until DISCORD_BOT_TOKEN is set.
if [ -z "${DISCORD_BOT_TOKEN:-}" ] && [ "$MODE" != "--callback-only" ]; then
  echo "DISCORD_BOT_TOKEN empty; forcing --callback-only" >&2
  MODE=--callback-only
fi

nohup "$DIR/watch.sh" $MODE >>"$DIR/bridge.log" 2>&1 &
echo $! > "$DIR/bridge.pid"
echo "bridge supervisor pid $(cat "$DIR/bridge.pid") mode=$MODE"
# Wait until /health answers locally.
i=0
while [ "$i" -lt 30 ]; do
  if curl -fsS "http://127.0.0.1:${CALLBACK_PORT:-8787}/health" >/dev/null 2>&1; then
    URL=$(cat "$DIR/.public_url")
    echo "local health ok; public: $URL/health"
    curl -fsS "$URL/health" || true
    echo
    exit 0
  fi
  i=$((i + 1))
  sleep 1
done
echo "bridge did not become healthy; see bridge.log" >&2
exit 1
