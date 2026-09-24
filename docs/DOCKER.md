# Docker Deployment

## Current Status

Backend, PostgreSQL and nginx run through Docker Compose in local WSL.
Nginx serves the frontend and proxies API requests to the backend.
The Azure deployment still runs without containers.

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

Compose reuses the existing volume. The database, roles and permissions
were created manually; setup for an empty volume is not yet automated.

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
- Environment file paths currently target the local WSL setup.

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

## Backup Check

- A custom-format dump was created before the Compose transition.
- File: `/home/tarabk/taskboard-before-compose.dump`.
- File permissions: `600`.
- `pg_dump` completed with exit code 0.
- The archive table of contents was read with `pg_restore --list`.
- Restoration from this container database backup has not yet been tested.

## Resource Limits

| Service | Memory | CPU |
|---|---|---|
| PostgreSQL | 512 MiB | 1.0 |
| Backend | 256 MiB | 0.75 |
| Frontend | 128 MiB | 0.25 |

- Memory and CPU limits verified with Docker inspect.
- Swap disabled by setting `memswap_limit` equal to `mem_limit`.
- Initial limits for the local lab; sustained load has not been tested.

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

## Next Steps

- Configure log rotation.
- Test database restoration and automate container database backups.
- Document setup for a new database volume, including roles and permissions.
- Prepare the Azure transition, including HTTPS, data transfer and rollback.
