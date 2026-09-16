#!/usr/bin/env bash
# Take a compressed PostgreSQL backup and delete ones older than $KEEP_DAYS.
#
# Your platform's own snapshots are the first line of defence; this exists so
# a copy also lives somewhere the platform can't delete — an account
# suspension or a mistaken "delete database" takes their snapshots with it.
#
#   DATABASE_URL=postgresql://... ./scripts/backup-db.sh /var/backups/petrolead
#
# Restore with:
#   gunzip -c petrolead-YYYYmmdd-HHMMSS.sql.gz | psql "$DATABASE_URL"
#
# Run it from cron on a machine that is not the database host, e.g. daily at
# 03:00:  0 3 * * *  /path/to/backup-db.sh /var/backups/petrolead >> /var/log/petrolead-backup.log 2>&1

set -euo pipefail

DEST="${1:-./db-backup}"
KEEP_DAYS="${KEEP_DAYS:-14}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is not set." >&2
  exit 1
fi

# pg_dump doesn't understand SQLAlchemy's +psycopg driver suffix.
PG_URL="${DATABASE_URL/postgresql+psycopg:\/\//postgresql://}"

if [[ "$PG_URL" == sqlite* ]]; then
  echo "DATABASE_URL points at SQLite, not PostgreSQL — nothing to dump." >&2
  exit 1
fi

mkdir -p "$DEST"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
FILE="$DEST/petrolead-$STAMP.sql.gz"

# Dump to a temporary name first, so an interrupted run can't leave a
# truncated file that looks like a good backup.
pg_dump --no-owner --no-privileges "$PG_URL" | gzip > "$FILE.partial"
mv "$FILE.partial" "$FILE"

SIZE="$(du -h "$FILE" | cut -f1)"
echo "Wrote $FILE ($SIZE)"

# Refuse to report success on an empty dump.
if [[ ! -s "$FILE" ]]; then
  echo "Backup file is empty — check the connection string and permissions." >&2
  exit 1
fi

DELETED="$(find "$DEST" -name 'petrolead-*.sql.gz' -mtime "+$KEEP_DAYS" -print -delete | wc -l)"
echo "Removed $DELETED backup(s) older than $KEEP_DAYS days."
