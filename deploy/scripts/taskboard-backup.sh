#!/bin/bash
set -euo pipefail
umask 077

export PATH=/usr/bin:/bin

backup_dir="/var/backups/taskboard"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)

# Create a unique temporary file in the backup directory.
temp_file=$(mktemp "$backup_dir/taskboard-$timestamp-XXXXXX.dump.tmp")
final_file="${temp_file%.tmp}"

# Remove the temporary file when the script exits.
trap 'rm -f -- "$temp_file"' EXIT

echo "Starting backup of taskboard"

pg_dump \
    --dbname=taskboard \
    --format=custom \
    --file="$temp_file"

# Publish the archive only after pg_dump succeeds.
mv -- "$temp_file" "$final_file"
echo "Backup created: $final_file"

# Delete completed archives older than seven days.
find "$backup_dir" -maxdepth 1 -type f \
    -name 'taskboard-*.dump' -mmin +10080 \
    -print -delete

echo "Backup and cleanup completed"
