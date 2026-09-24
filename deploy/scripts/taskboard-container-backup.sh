#!/bin/bash
set -euo pipefail
umask 077

export PATH=/usr/bin:/bin

project_dir="/home/tarabk/projects/sysadmin-devops-pet-project"
backup_dir="/var/backups/taskboard-container"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)

temp_file=$(mktemp "$backup_dir/taskboard-$timestamp-XXXXXX.dump.tmp")
final_file="${temp_file%.tmp}"

trap 'rm -f -- "$temp_file"' EXIT

echo "Starting taskboard database backup"

docker compose \
    --project-directory "$project_dir" \
    -f "$project_dir/compose.yaml" \
    exec -T db \
    pg_dump -U postgres -d taskboard -Fc \
    > "$temp_file"

mv -- "$temp_file" "$final_file"
echo "Backup created: $final_file"

find "$backup_dir" -maxdepth 1 -type f \
    -name 'taskboard-*.dump' -mmin +10080 \
    -print -delete

echo "Backup and local cleanup completed"
