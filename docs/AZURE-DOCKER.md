# Docker Deployment on Azure

## Current Setup

- VM: `vm-lab`, Oracle Linux 9.8.
- Repository: `/home/azureuser/sysadmin-devops-pet-project`.
- Docker Engine: 29.8.1.
- Docker Compose: v5.5.1.
- Compose services: `db`, `backend`, `frontend`.
- Migration service: `migrate`, in the `tools` profile.
- PostgreSQL data volume: `taskboard-sqldata`.
- Environment files: `/etc/taskboard-container`, owned by root.
- Directory permissions: `0700`; environment files: `0600`.
- Native Taskboard and PostgreSQL services stopped and disabled.
- Native application files and database retained for recovery.

## Request Routing

- Host nginx handles HTTPS, certificates and IP restrictions.
- Application access is restricted to localhost and the administrator's IP.
- Host nginx forwards application requests to `127.0.0.1:18080`.
- Container nginx serves the frontend and proxies `/api/` to `backend:8000`.
- Backend connects to PostgreSQL at `db:5432`.
- Backend port 8000 is published at `127.0.0.1:18000`.
- PostgreSQL port 5432 is not published.
- HTTP ACME validation remains available from the Internet.
- Certbot continues using `/usr/share/nginx/taskboard`.

Configuration files:

- Host nginx source: `deploy/nginx/taskboard-container-host.conf`.
- Active host configuration: `/etc/nginx/conf.d/taskboard.conf`.
- Container nginx: `deploy/nginx/taskboard-container.conf`.
- Previous host configuration: `/root/taskboard-migration/taskboard-native.conf`.

## Start and Check

Run from the repository directory:

```bash
sudo docker compose \
  --env-file /etc/taskboard-container/compose.env \
  up -d --wait db backend frontend
```

```bash
sudo docker compose \
  --env-file /etc/taskboard-container/compose.env \
  ps
```

```bash
sudo docker compose \
  --env-file /etc/taskboard-container/compose.env \
  logs --tail 50 backend
```

```bash
curl -i --max-time 10 http://127.0.0.1:18000/ready
curl -i --max-time 10 http://127.0.0.1:18080/api/tasks
```

These commands use the existing initialized volume.
Starting from an empty volume also requires database initialization
and migrations or restoration of a database backup.

## Database Migration

- A trial dump of the native database was restored into container PostgreSQL.
- Ownership, runtime permissions and API access were checked.
- Both backends were stopped before the final dump.
- The final dump replaced the trial data in container PostgreSQL.
- Host nginx was switched after the container application passed local checks.
- HTTPS access and browser CRUD operations were verified.
- Container PostgreSQL is now the active database.

## Backups

- Script: `/usr/local/sbin/taskboard-container-backup-azure.sh`.
- Service: `taskboard-container-backup-azure.service`.
- Timer: `taskboard-container-backup-azure.timer`.
- Schedule: daily at 03:00 UTC, with `Persistent=true`.
- Service runs as root and executes `pg_dump` inside the `db` container.
- Custom-format archives: `/var/backups/taskboard-container`.
- Backup directory permissions: `0700`; archives: `0600`.
- AzCopy state: `/var/lib/taskboard-container-azcopy`.
- Destination: `tarabkbackup`, container `taskboard-backups`.
- Authentication: VM system-assigned managed identity.
- Completed archives are uploaded before local cleanup.
- Existing blobs are not overwritten.
- Failed uploads leave local archives available for the next run.
- Local retention: seven days.
- Existing Azure lifecycle policy removes blobs older than 30 days
  since last modification; soft delete retention is seven days.
- The native database backup timer is disabled.

Manual backup:

```bash
sudo systemctl start taskboard-container-backup-azure.service
sudo systemctl show taskboard-container-backup-azure.service \
  -p Result -p ExecMainStatus
```

Backup logs:

```bash
sudo journalctl -u taskboard-container-backup-azure.service \
  -n 50 --no-pager
```

A container database backup was downloaded from Azure.
Its SHA-256 matched the local archive.
Restoration into a separate database succeeded;
migration version and task reads as `taskboard_user` were checked.

The dump contains database objects and data, not PostgreSQL role passwords.
Roles must exist before restoring into a new PostgreSQL instance.

## Update Procedure

1. Review the code, configuration and migration changes.
2. Run a backup and confirm that the Azure upload succeeds.
3. Record the current Git commit and preserve the current application
   images under separate rollback tags before rebuilding.
4. Update the repository and build the affected images.
5. If required by the migration, stop application writes.
6. Run the migration service explicitly.
7. Recreate the affected application containers.
8. Verify health checks, HTTPS and task operations.

Migration command:

```bash
sudo docker compose \
  --env-file /etc/taskboard-container/compose.env \
  run --rm migrate
```

Normal `compose up` does not run the migration service.
Review migration compatibility before updating the application.

## Rollback

Application rollback requires the previous images and matching configuration.
It also requires a database schema compatible with that application version.
Reverting Git alone does not revert images or database changes.

The retained native database is a snapshot from before the switch.
It no longer receives application writes.

To return to the native deployment after new writes:

1. Stop writes to the container application.
2. Back up the current container database.
3. Check compatibility with the native application and PostgreSQL.
4. Restore current data into the native database.
5. Start and verify the native backend.
6. Restore the previous host nginx configuration, validate it and reload nginx.
7. Switch backup scheduling to the active database.

Do not route users back to the retained native database without transferring
new data or explicitly accepting its loss.
