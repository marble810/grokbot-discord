#!/bin/sh
# Restart loop for the gateway. Prefer ./scripts/supervise.sh for box deploy.
DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
cd "$DIR"
PYTHON="${DIR}/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON=python3
while true; do
  "$PYTHON" -m grokbot_discord "$@" >> "$DIR/bridge.log" 2>&1
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) grokbot_discord exited $?, restart in 3s" >> "$DIR/bridge.log"
  sleep 3
done
