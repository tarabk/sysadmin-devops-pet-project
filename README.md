# SysAdmin to DevOps Pet Project

A hands-on project documenting my progress from Linux administration
to DevOps. I use Server Taskboard, a small web application, to practise
deployment, security, backups and recovery, then move on to containers
and monitoring.

The application supports creating tasks, marking them complete and
deleting them. It was first deployed manually on Oracle Linux in Azure
and now runs with Docker Compose.

## Stack

- Oracle Linux 9.8 on an Azure VM — 2 vCPU, 4 GiB RAM.
- Python 3.11, FastAPI, SQLAlchemy and Alembic.
- PostgreSQL 16.
- Plain HTML, CSS and JavaScript frontend.
- Nginx, systemd, firewalld and SELinux.
- Let's Encrypt and Certbot.
- Docker Engine and Docker Compose.
- Prometheus, Node Exporter, cAdvisor, Blackbox Exporter and Grafana.
- Alertmanager and a Python Telegram bot.

## Current Status

The application runs on the Azure VM without containers.

- Backend managed by systemd under a dedicated Linux account.
- Persistent PostgreSQL data and a separate service for Alembic migrations.
- Separate PostgreSQL roles for migrations and runtime access.
- SSH key authentication; root SSH login and password login disabled.
- Network access restricted through Azure NSG, firewalld and nginx.
- SELinux enforcing.
- Environment files stored outside the repository with restricted permissions.
- HTTPS configured, with HTTP-to-HTTPS redirection.
- Daily PostgreSQL backups uploaded to Azure Blob Storage using AzCopy and the VM's managed identity.
- Local backups retained for seven days; Azure lifecycle deletion configured after 30 days.
- Blob and container soft delete enabled for seven days.
- Grafana dashboard for VM resources, containers and application checks.
- Telegram menus for VM, container and website metrics, with critical alerts.
- Deployment configurations and scripts tracked in `deploy/`. 

The app has no user authentication, so SSH and HTTPS access are restricted
to my public IP. The HTTP ACME challenge path remains publicly accessible
for certificate renewal.

## Deployment Layout

Host nginx handles HTTPS and forwards requests to container nginx on
`127.0.0.1:18080`. Container nginx serves the frontend and proxies `/api/`
requests to the backend. PostgreSQL is available inside the Docker network;
its port is not published on the host.

The original backend and PostgreSQL systemd services are disabled.
Host nginx, certificate renewal and the container backup timer remain in use.

Monitoring runs as a separate Compose project on the same VM.
Grafana is accessed through an SSH tunnel. Website probes run locally,
so they do not verify public access through Azure NSG. Monitoring cannot
send notifications during a complete VM outage.

The files in `deploy/` reflect my Azure VM configuration.
Review domain names, IP restrictions and paths before reusing them.
Credentials, private keys and database dumps are excluded from Git.

## Running Locally

For a Docker setup, see [Local Docker deployment](docs/DOCKER.md).

For development without containers, Python 3.11 and PostgreSQL 16 are required.
Configuration variables are listed in `.env.example`.
See [Application setup](docs/APPLICATION.md) for installation,
database migrations and startup instructions.

The frontend has no build step or npm dependencies.

## Verification

- Application tests passed during local setup.
- Health and database readiness endpoints checked.
- Task creation, updates, deletion and persistence tested.
- Container deployment and HTTPS access verified on Azure.
- Certificate renewal dry run passed, including the nginx reload hook.
- Container database backup downloaded from Azure; SHA-256 checksums matched.
- Backup restored into a separate test database.
- Backup service tested manually; daily timer enabled.
- Telegram menus, VM and container metrics, and website checks verified.
- Bot tests and Prometheus alert-rule tests passed.
- Telegram alert delivery and recovery notifications tested end to end.

VM reboot and backend recovery after SIGKILL were tested during the original
systemd deployment. Details are retained in the server setup notes.

## Repository

| Path | Contents |
|---|---|
| `app/` | FastAPI backend |
| `frontend/` | HTML, CSS and JavaScript |
| `migrations/` | Alembic migrations |
| `tests/` | Application, Telegram bot and alert-rule tests |
| `compose.yaml` | Application containers and migrations |
| `compose.monitoring.yaml` | Base monitoring stack |
| `compose.telegram.yaml` | Telegram bot and monitoring overrides |
| `deploy/nginx/` | Host and container nginx configurations |
| `deploy/systemd/` | Backend service and backup services/timers |
| `deploy/scripts/` | Backup and certificate reload scripts |
| `deploy/monitoring/` | Metrics, probes and alert rules |
| `deploy/telegram-bot/` | Telegram bot and example configuration |
| `docs/` | Setup instructions and troubleshooting notes |

## Next Steps

an optional next step:
- Automate server configuration with Ansible.
- Set up CI/CD with GitHub Actions.

## Documentation

- [Application setup](docs/APPLICATION.md)
- [Local Docker deployment](docs/DOCKER.md)
- [Azure Docker deployment](docs/AZURE-DOCKER.md)
- [Initial server setup and troubleshooting](docs/SRV-SETUP.md)
- [Telegram monitoring](docs/TELEGRAM-MONITORING.md)
- [Deployment configurations](deploy/)
