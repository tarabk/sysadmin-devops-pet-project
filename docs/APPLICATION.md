# Server Taskboard — Application Setup

A task board for creating, updating and deleting server maintenance tasks.

## Components

- `app/` — FastAPI backend with SQLAlchemy.
- `frontend/` — HTML, CSS and JavaScript; no build step or npm dependencies.
- PostgreSQL — task storage.
- `migrations/` — Alembic database migrations.
- `tests/` — API, validation and database failure tests.
- `deploy/` — nginx, systemd and maintenance scripts for the Azure deployment.

These instructions cover local development with Python and PostgreSQL on the host.
For local containers, see [Docker deployment](DOCKER.md). For the running server,
see [Azure Docker deployment](AZURE-DOCKER.md).
[Server setup](SRV-SETUP.md) records the initial systemd deployment.

## Requirements

Tested with:

- Python 3.11.
- PostgreSQL 16.

Create the PostgreSQL role and database before starting.
The application does not install PostgreSQL, create roles or create the database.

For local setup, the migration role needs permission to create database
objects. A separate runtime role needs access to the application tables
and sequences. The container initialization script is
[`deploy/postgres/init/10-taskboard.sh`](../deploy/postgres/init/10-taskboard.sh).
The original host PostgreSQL setup is recorded in [Server Setup](SRV-SETUP.md).

## Backend Setup

Run from the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
```

For the first setup, copy the configuration template:

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` with your local database settings:

```dotenv
APP_HOST=127.0.0.1
APP_PORT=8000
DATABASE_URL=postgresql+psycopg://taskboard_user:change_me@127.0.0.1:5432/taskboard
CORS_ORIGINS=http://127.0.0.1:8080,http://localhost:8080
LOG_LEVEL=INFO
```

| Variable | Purpose |
|---|---|
| `APP_HOST`, `APP_PORT` | Application settings; the Uvicorn commands below set the listener explicitly |
| `DATABASE_URL` | PostgreSQL connection URL |
| `CORS_ORIGINS` | Comma-separated browser origins allowed to access the API |
| `LOG_LEVEL` | Application logging level |

Replace `change_me` with the database password. Percent-encode special
characters in credentials when placing them in a connection URL.

Settings are loaded from `.env` in the working directory.
Environment variables take precedence.

`.env` is excluded from Git. Keep real credentials out of tracked files.

`requirements.lock.txt` contains pinned dependencies.
`requirements.txt` lists direct project dependencies.

## Database Migrations

From the repository root, with the virtual environment active:

```bash
python -m alembic upgrade head
```

Alembic uses `DATABASE_URL`. For this command, it must refer to a role
with migration privileges. Use the runtime role when starting the backend.

On the Azure VM, migration and runtime credentials are stored in separate
environment files. Do not replace the backend credentials with migration
credentials.

Migrations run separately; starting the API does not apply them.

## Start the Backend

From the repository root:

```bash
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

This binds the API to localhost on port 8000. Changing `APP_HOST` or
`APP_PORT` in `.env` does not override these explicit command-line arguments.

Logs are written to stdout/stderr. Under systemd, they are available
through the service journal.

## Start the Frontend

For local development, set `frontend/config.js` to:

```javascript
window.APP_CONFIG = {
  API_BASE_URL: "http://127.0.0.1:8000"
};
```

In a second terminal, from the repository root:

```bash
python3.11 -m http.server 8080 --bind 127.0.0.1 --directory frontend
```

Open `http://127.0.0.1:8080`.

The frontend origin must match an entry in `CORS_ORIGINS`, including
the protocol and port.

For the nginx deployment, use:

```javascript
window.APP_CONFIG = {
  API_BASE_URL: window.location.origin
};
```

This requires nginx to serve the frontend and proxy `/api/` under the
same origin. The local Python static server does not provide that proxy.

## Check the Application

Backend health:

```bash
curl -i http://127.0.0.1:8000/health
```

Expected: HTTP 200 and `{"status":"ok"}`.

Database readiness:

```bash
curl -i http://127.0.0.1:8000/ready
```

Expected: HTTP 200 and `{"status":"ready","database":"ok"}`.
A database connection failure returns HTTP 503.

Readiness checks connectivity, not all table permissions.
Test a task operation as well:

```bash
curl -i -X POST http://127.0.0.1:8000/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"Check disk space","description":"Review available storage"}'

curl -i http://127.0.0.1:8000/api/tasks
```

In the browser, create a task, change its status, refresh the page
and delete it.

Interactive API documentation:
`http://127.0.0.1:8000/docs`.

These URLs access the backend directly. The deployed nginx configuration
proxies `/api/`; it does not expose `/health`, `/ready` or `/docs`.

## Tests

From the repository root:

```bash
source .venv/bin/activate
pytest
```

Tests use a temporary SQLite database and simulate database failures.
A running PostgreSQL instance is not required.

Coverage includes task operations, input validation, health checks
and database error responses. PostgreSQL permissions and deployment
behaviour are checked separately against the running application.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Backend health |
| `GET` | `/ready` | Database connectivity |
| `GET` | `/api/tasks` | List tasks |
| `POST` | `/api/tasks` | Create a task |
| `PATCH` | `/api/tasks/{id}` | Update task fields or completion status |
| `DELETE` | `/api/tasks/{id}` | Delete a task |

## Access

The application has no authentication. Local examples bind to loopback.
The Azure deployment restricts access through NSG and nginx rules.

See [deployment configuration](../deploy/) and
[server setup notes](SRV-SETUP.md) for the current server settings.
Telegram menu and alert-rule tests are documented in
[Telegram monitoring](TELEGRAM-MONITORING.md).
