#!/bin/sh
DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
if pgrep -f "$DIR/watch.sh" >/dev/null 2>&1; then
  echo "watch.sh already running"
  exit 0
fi
exec "$DIR/scripts/supervise.sh" "$@"
