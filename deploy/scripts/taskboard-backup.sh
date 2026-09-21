#!/bin/bash
set -euo pipefail
umask 077

export PATH=/usr/bin:/bin

backup_dir="/var/backups/taskboard"
container_url="https://tarabkbackup.blob.core.windows.net/taskboard-backups"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)

export AZCOPY_AUTO_LOGIN_TYPE=MSI
export AZCOPY_LOG_LOCATION=/var/lib/taskboard-azcopy
export AZCOPY_JOB_PLAN_LOCATION=/var/lib/taskboard-azcopy

# Remove an incomplete dump when the script exits.
temp_file=$(mktemp "$backup_dir/taskboard-$timestamp-XXXXXX.dump.tmp")
final_file="${temp_file%.tmp}"
trap 'rm -f -- "$temp_file"' EXIT

echo "Starting backup of taskboard"

pg_dump \
    --dbname=taskboard \
    --format=custom \
    --file="$temp_file"

# Publish the archive only after pg_dump succeeds.
mv -- "$temp_file" "$final_file"
echo "Backup created: $final_file"

# Upload completed archives, including any missed during previous runs.
for archive in "$backup_dir"/taskboard-*.dump; do
    [[ -f "$archive" ]] || continue
    archive_name="${archive##*/}"

    echo "Uploading: $archive_name"

    /usr/local/bin/azcopy copy \
        "$archive" \
        "$container_url/$archive_name" \
        --overwrite=false
done

# Clean up local archives only after all uploads succeed.
find "$backup_dir" -maxdepth 1 -type f \
    -name 'taskboard-*.dump' -mmin +10080 \
    -print -delete

echo "Backup, Azure upload and local cleanup completed"
