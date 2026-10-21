#!/usr/bin/env bash
set -euo pipefail

# Restore an encrypted StockLab backup.
# Usage:
#   STOCKLAB_DATABASE_URL=... BACKUP_ENCRYPTION_KEY=... \
#     scripts/restore_backup.sh stocklab-2026-10-21.dump.enc

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <encrypted.dump.enc>" >&2
  exit 2
fi

: "${STOCKLAB_DATABASE_URL:?set STOCKLAB_DATABASE_URL}"
: "${BACKUP_ENCRYPTION_KEY:?set BACKUP_ENCRYPTION_KEY}"

encrypted="$1"
if [ ! -f "$encrypted" ]; then
  echo "file not found: $encrypted" >&2
  exit 2
fi

echo "WARNING: this will overwrite objects in the target database."
echo "target: $STOCKLAB_DATABASE_URL"
read -r -p "type RESTORE to continue: " confirm
[ "$confirm" = "RESTORE" ] || exit 1

dump="$(mktemp)"
trap 'rm -f "$dump"' EXIT

openssl enc -d -aes-256-cbc -pbkdf2 \
  -in "$encrypted" \
  -out "$dump" \
  -pass env:BACKUP_ENCRYPTION_KEY

DB_URL="${STOCKLAB_DATABASE_URL/postgresql+psycopg/postgresql}"
pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --dbname "$DB_URL" \
  "$dump"

echo "restore complete"
