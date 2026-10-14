#!/bin/sh
# Append a CALLBACK_SECRET to .env if missing. Does not overwrite an existing one.
set -eu
DIR=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
ENV="$DIR/.env"
touch "$ENV"
chmod 600 "$ENV"
if grep -q '^CALLBACK_SECRET=.\+' "$ENV" 2>/dev/null; then
  echo "CALLBACK_SECRET already set in $ENV"
  exit 0
fi
SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
# Drop empty CALLBACK_SECRET= lines first.
grep -v '^CALLBACK_SECRET=' "$ENV" > "$ENV.tmp" || true
mv "$ENV.tmp" "$ENV"
printf 'CALLBACK_SECRET=%s\n' "$SECRET" >> "$ENV"
chmod 600 "$ENV"
echo "wrote CALLBACK_SECRET to $ENV"
