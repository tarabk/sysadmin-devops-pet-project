# Docker Deployment

## Current Status

Backend, PostgreSQL and nginx run in separate containers in local WSL.
Nginx serves the frontend and proxies API requests to the backend.
The Azure deployment still runs without containers.

## Backend

- Image: `taskboard-backend:pet-lab`.
- Base image: `python:3.11-slim`.
- Dependencies installed from `requirements.lock.txt`.
- Runs as `taskboard`, UID 10001.
- Includes application code and Alembic migrations.
- Container: `taskboard-api-web`.
- Port mapping: `127.0.0.1:18000` to container port `8000`.

## PostgreSQL

- Image: `postgres:16`.
- Container: `taskboard-sql`.
- Database: `taskboard`.
- Database owner and migration role: `taskboard_migrator`.
- Runtime role: `taskboard_user`.
- Runtime permissions: schema usage, task CRUD and task ID sequence usage.
- Named volume: `taskboard-sqldata`.
- Container data directory: `/var/lib/postgresql/data`.
- Port 5432 is not published on the host.

## Network and Configuration

- Docker network: `taskboard-net`, bridge driver.
- Backend database address: `taskboard-sql:5432`.
- Configuration directory: `/home/tarabk/.config/taskboard/`, outside the repository.
- Environment files: `postgres.env`, `migration.env`, `backend.env`.
- Environment file permissions: `600`.
- Migrations run in a temporary container from the backend image.

## Verified

- `/health` and `/ready` return HTTP 200.
- Tasks can be created and retrieved through the API.
- PostgreSQL container recreated with the same volume;
  the test task remained available.
- Nginx configuration validated with `nginx -t`.
- Task creation, completion and deletion tested through the browser.
- Task completion state preserved after page reload.

## Frontend and Nginx

- Image: `taskboard-frontend:pet-lab`.
- Base image: `nginx:stable-alpine`.
- Dockerfile: `deploy/nginx/Dockerfile`.
- Configuration: `deploy/nginx/taskboard-container.conf`.
- Container: `taskboard-frontend`.
- Port mapping: `127.0.0.1:18080` to container port `80`.
- Static files served from `/usr/share/nginx/html`.
- `/api/` requests forwarded to `taskboard-api-web:8000`.
- Frontend uses `window.location.origin` as the API base URL.

## Next Steps

- Define the services in Docker Compose.
- Configure container health checks and restart policies.
- Test container database backups and restoration.
- Prepare the Azure deployment.
