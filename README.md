# SysAdmin to DevOps Pet Project

A hands-on project documenting my progress from Linux administration
to DevOps. I use Server Taskboard, a small web application, to practise
deployment, security, backups and recovery, then move on to containers
and automation.

The application supports creating tasks, marking them complete and
deleting them.

The manual deployment on Oracle Linux in Azure is working.
Next steps include Docker Compose, Zabbix monitoring, Ansible
and CI/CD with GitHub Actions.

# Server Taskboard

My Linux administration pet project. I deployed a small task board on
Oracle Linux in Azure and configured the server, database, networking,
HTTPS and backups manually.

The application supports creating tasks, marking them complete and
deleting them. The next stage is containerization and automation.

## Stack

- Oracle Linux 9.8 on an Azure VM — 2 vCPU, 4 GiB RAM.
- Python 3.11, FastAPI, SQLAlchemy and Alembic.
- PostgreSQL 16.
- Plain HTML, CSS and JavaScript frontend.
- Nginx, systemd, firewalld and SELinux.
- Let's Encrypt and Certbot.

## Current Status

The application runs on the VM without containers.

- Backend managed by systemd under a dedicated Linux account.
- Separate PostgreSQL roles for migrations and runtime access.
- SSH key authentication; root SSH login and password login disabled.
- Network access restricted through Azure NSG, firewalld and nginx.
- SELinux enforcing.
- Environment files stored outside the repository with restricted permissions.
- HTTPS configured, with HTTP-to-HTTPS redirection.
- Certificate renewal scheduled, with a hook to validate and reload nginx.
- Daily database backups through a systemd timer, with seven-day retention.
- Deployment configurations and scripts tracked in `deploy/`.

The app has no user authentication, so SSH and HTTPS access are restricted
to my public IP. The HTTP ACME challenge path remains publicly accessible
for certificate renewal.

One database backup has been copied off the VM and verified with SHA-256.
Off-VM transfers are currently manual.

## Deployment Layout

Nginx serves the frontend and proxies `/api/` requests to Uvicorn on
`127.0.0.1:8000`. PostgreSQL listens on loopback addresses only.

The frontend uses the same origin as the API. SQLAlchemy handles database
access, and Alembic manages schema migrations.

The files in `deploy/` reflect my Azure VM configuration.
Review domain names, IP restrictions and paths before reusing them.
Credentials, private keys and database dumps are excluded from Git.

## Running Locally

Requires Python 3.11 and PostgreSQL 16.
Configuration variables are listed in `.env.example`.

See [Application setup](docs/APPLICATION.md) for installation,
database migrations and startup instructions.

The frontend has no build step or npm dependencies.

## Verification

- Six application tests passed during local setup.
- Health and database readiness endpoints checked.
- Task creation, updates, deletion and persistence tested.
- HTTPS certificate accepted by the browser.
- Certificate renewal dry run passed, including the nginx reload hook.
- Database backup restored into a separate test database.
- Backup service tested manually; daily timer enabled.

## Repository

| Path | Contents |
|---|---|
| `app/` | FastAPI backend |
| `frontend/` | HTML, CSS and JavaScript |
| `migrations/` | Alembic migrations |
| `tests/` | Application tests |
| `deploy/nginx/` | Nginx configuration |
| `deploy/systemd/` | Backend service and backup service/timer |
| `deploy/scripts/` | Backup and certificate reload scripts |
| `docs/` | Setup instructions and troubleshooting notes |

## Next Steps

- Verify startup after a VM reboot and test service failure recovery.
- Automate off-VM backup transfers.
- Containerize the application with Docker Compose.
- Add Zabbix monitoring and Telegram notifications.
- Automate server configuration with Ansible.
- Set up CI/CD with GitHub Actions.

## Documentation

- [Application setup](docs/APPLICATION.md)
- [Server setup and troubleshooting](docs/SRV-SETUP.md)
- [Deployment configurations](deploy/)
