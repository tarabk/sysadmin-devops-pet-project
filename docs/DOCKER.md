# Docker Deployment

This guide records the local WSL lab. Commands use the repository at
`/home/tarabk/projects/sysadmin-devops-pet-project` and local environment files.
Azure uses a separate configuration directory and backup service.

## Current Status

Backend, PostgreSQL and nginx run through Docker Compose in local WSL.
Nginx serves the frontend and proxies API requests to the backend.
The application also runs through Docker Compose on Azure.
See [Azure deployment](AZURE-DOCKER.md) for server operations and recovery.

## Docker Compose

- Configuration: `compose.yaml`.
- Project: `sysadmin-devops-pet-project`.
- Application services: `db`, `backend`, `frontend`.
- Migration service: `migrate`, assigned to the `tools` profile.
- Backend and migrations wait for the PostgreSQL health check to pass.
- Frontend waits for the backend health check to pass.
- PostgreSQL health check uses `pg_isready`.
- Backend health check requests `/ready`.
- Frontend health check requests `/`.
- PostgreSQL, backend and frontend use `restart: unless-stopped`.
- The migration service has no automatic restart policy.

## Backend

- Service: `backend`.
- Image: `taskboard-backend:pet-lab`.
- Base image: `python:3.11-slim`.
- Dockerfile: `Dockerfile`.
- Dependencies installed from `requirements.lock.txt`.
- Runs as `taskboard`, UID 10001.
- Includes application code and Alembic migrations.
- Port mapping: `127.0.0.1:18000` to container port `8000`.

## PostgreSQL

- Service: `db`.
- Image: `postgres:16`.
- Database: `taskboard`.
- Database owner and migration role: `taskboard_migrator`.
- Runtime role: `taskboard_user`.
- Runtime permissions: schema usage, task CRUD and task ID sequence usage.
- External volume: `taskboard-sqldata`.
- Container data directory: `/var/lib/postgresql/data`.
- Port 5432 is not published on the host.
- Health check: `pg_isready`, every 10 seconds, with a 5-second timeout,
  3 retries and a 30-second start period.

Compose uses the existing external volume `taskboard-sqldata`.
For a new deployment, create the volume before starting Compose.
The initialization script creates the database, roles and permissions
when the volume is empty.

## Frontend and Nginx

- Service: `frontend`.
- Image: `taskboard-frontend:pet-lab`.
- Base image: `nginx:stable-alpine`.
- Dockerfile: `deploy/nginx/Dockerfile`.
- Configuration: `deploy/nginx/taskboard-container.conf`.
- Port mapping: `127.0.0.1:18080` to container port `80`.
- Static files served from `/usr/share/nginx/html`.
- `/api/` requests forwarded to `backend:8000`.
- Frontend uses `window.location.origin` as the API base URL.

## Network and Configuration

- Compose creates the bridge network `sysadmin-devops-pet-project_default`.
- Services communicate using their Compose service names.
- Backend database address: `db:5432`.
- Configuration directory: `/home/tarabk/.config/taskboard/`, outside the repository.
- Environment files: `postgres.env`, `migration.env`, `backend.env`.
- Environment file permissions: `600`.
- Compose reads environment files with `format: raw`.
- Environment files: `postgres.env`, `bootstrap.env`, `migration.env`, `backend.env`.
- `TASKBOARD_ENV_DIR` overrides the configuration directory.

## Database Initialization

- Initialization script: `deploy/postgres/init/10-taskboard.sh`.
- Mounted read-only at `/docker-entrypoint-initdb.d`.
- Runs when PostgreSQL initializes an empty data directory.
- Creates the `taskboard` database and two login roles:
  `taskboard_migrator` and `taskboard_user`.
- `taskboard_migrator` owns the database.
- Default privileges grant runtime access to tables and sequences
  created by `taskboard_migrator` in the `public` schema.
- Role passwords are read from `bootstrap.env`, stored outside the repository.
- Alembic migrations run separately after database initialization.
- Existing database volumes are left unchanged by the initialization script.

Initialization was tested with a separate empty volume.
Migration `0001` completed, and CRUD operations passed using `taskboard_user`.

## Migrations

- The `migrate` service uses the backend image and `migration.env`.
- It waits for the PostgreSQL health check to pass.
- Its command is `python -m alembic upgrade head`.
- Migrations are run explicitly before starting the updated backend.
- A normal Compose startup without the `tools` profile skips `migrate`.

Run from the repository root:

```bash
sudo docker compose run --rm migrate
```

The temporary container is removed after completion. Applied migrations
remain in the database.

## Backup and Restore Check

- Custom-format dump: `/home/tarabk/taskboard-before-compose.dump`.
- File permissions: `600`.
- Archive contents listed with `pg_restore --list`.
- Restored into a separate database, `taskboard_restore_test`,
  using `pg_restore --single-transaction`.
- Restored migration version: `0001`.
- Restored tasks read successfully as `taskboard_user`.
- Runtime schema, table and sequence permissions verified.
- Test database removed after verification.

The restore used the existing PostgreSQL instance and roles.
Recovery on a fresh instance has not yet been tested.

## Resource Limits

| Service | Memory | CPU |
|---|---|---|
| PostgreSQL | 512 MiB | 1.0 |
| Backend | 256 MiB | 0.75 |
| Frontend | 128 MiB | 0.25 |

- Memory and CPU limits verified with Docker inspect.
- Swap disabled by setting `memswap_limit` equal to `mem_limit`.
- Initial limits for the local lab; sustained load has not been tested.

## Container Logs

- Logging driver: `json-file`.
- Rotation settings: `max-size: "10m"`, `max-file: "3"`.
- Settings verified with Docker inspect for PostgreSQL, backend and frontend.
- Rotation applies to stdout/stderr collected by Docker.
- Rotation at the size threshold has not been tested.

## Scheduled Backups

- Script: `deploy/scripts/taskboard-container-backup.sh`.
- Installed script: `/usr/local/sbin/taskboard-container-backup.sh`.
- Service: `taskboard-container-backup.service`, runs as root.
- Timer: `taskboard-container-backup.timer`, enabled.
- Schedule: daily at 03:00 UTC.
- Persistent timer catches up after a missed scheduled run.
- Backup directory: `/var/backups/taskboard-container`, mode `700`.
- Archives use PostgreSQL custom format, mode `600`.
- Temporary files are renamed after a successful dump.
- Completed archives older than seven days are removed after a successful backup.
- Manual service execution completed successfully.
- A successful manual run was recorded; a scheduled local run was not recorded.

This local backup script stores archives on the WSL host.
The Azure deployment uses a separate script that uploads to Blob Storage;
see [Azure backups](AZURE-DOCKER.md#backups).

## Verified

- Backend and frontend images built through Compose.
- PostgreSQL reports `healthy`.
- `/health` and `/ready` return HTTP 200.
- `/api/tasks` responds through nginx on port 18080.
- Existing tasks remained available after the Compose transition.
- The browser interface loads through nginx.
- Task creation, completion, deletion and persistence after page reload
  were tested during the manual container deployment.
- All three application services report healthy.
- With PostgreSQL stopped, `/health` returned 200 and `/ready` returned 503.
- Backend became unhealthy during the database outage and recovered
  after PostgreSQL started, without a manual backend restart.
- After SIGKILL, Docker restarted the backend automatically;
  RestartCount increased and API access through nginx recovered.
- With resource limits applied, 100 GET requests to `/api/tasks`
  through nginx completed with HTTP 200 using 5 concurrent workers.
- Average response time: 22 ms; maximum: 60 ms in the local test.
- All three services remained healthy without container restarts.

## Azure and Monitoring

The Azure migration is complete. Data transfer, HTTPS routing, backups and
rollback procedures are documented in [Azure deployment](AZURE-DOCKER.md).
The deployed monitoring stack is documented in
[Telegram monitoring](TELEGRAM-MONITORING.md).
