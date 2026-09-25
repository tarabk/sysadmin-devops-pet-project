#!/bin/bash
set -euo pipefail
umask 077

export PATH=/usr/bin:/bin

project_dir="/home/azureuser/sysadmin-devops-pet-project"
compose_env="/etc/taskboard-container/compose.env"
backup_dir="/var/backups/taskboard-container"
container_url="https://tarabkbackup.blob.core.windows.net/taskboard-backups"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)

export AZCOPY_AUTO_LOGIN_TYPE=MSI
export AZCOPY_LOG_LOCATION=/var/lib/taskboard-container-azcopy
export AZCOPY_JOB_PLAN_LOCATION=/var/lib/taskboard-container-azcopy

temp_file=$(mktemp "$backup_dir/taskboard-$timestamp-XXXXXX.dump.tmp")
final_file="${temp_file%.tmp}"
trap 'rm -f -- "$temp_file"' EXIT

echo "Starting container database backup"

docker compose \
    --project-directory "$project_dir" \
    --env-file "$compose_env" \
    -f "$project_dir/compose.yaml" \
    exec -T db pg_dump \
        --username=postgres \
        --dbname=taskboard \
        --format=custom > "$temp_file"

mv -- "$temp_file" "$final_file"
echo "Backup created: $final_file"

# Retry completed archives from previous runs as well.
for archive in "$backup_dir"/taskboard-*.dump; do
    [[ -f "$archive" ]] || continue
    archive_name="${archive##*/}"

    echo "Uploading: $archive_name"

    /usr/local/bin/azcopy copy \
        "$archive" \
        "$container_url/$archive_name" \
        --overwrite=false
done

# Retain local archives if any upload fails.
find "$backup_dir" -maxdepth 1 -type f \
    -name 'taskboard-*.dump' -mmin +10080 \
    -print -delete

echo "Container backup, Azure upload and local cleanup completed"
