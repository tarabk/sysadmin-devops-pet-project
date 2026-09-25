# Server Setup

The sections below record the initial native deployment.
The current container deployment is documented in
[Azure Docker deployment](AZURE-DOCKER.md).

## Infrastructure
- Azure VM: vm-lab, Poland Central, availability zone 2.
- OS: Oracle Linux 9.8, x64.
- Size: Standard_D2ls_v5 — 2 vCPU, 4 GiB RAM.
- OS disk: 64 GiB Standard SSD LRS.

## Initial Configuration
- System packages updated; reboot and SSH reconnection verified.
- Administration uses azureuser with sudo.
- SSH key authentication enabled.
- Direct root SSH login disabled in:
  /etc/ssh/sshd_config.d/00-local-security.conf
- Password and keyboard-interactive SSH authentication disabled.
- SELinux is enforcing.
- Azure NSG restricts inbound SSH to the administrator's public IPv4.
- firewalld public zone allows ssh and dhcpv6-client.
- Cockpit access removed from runtime and permanent firewall rules.
- rpcbind.service and rpcbind.socket stopped and disabled.
- Verified that port 111 is no longer listening.

## Application Files and Service Account
- Application deployed to `/opt/taskboard`.
- Python 3.11 virtual environment: `/opt/taskboard/.venv`.
- Dependencies installed; `pip check` passed.
- Service account: `taskboard-user`, group: `taskboard`, shell: `/sbin/nologin`.
- Source files owned by root, readable by the service group.

## PostgreSQL
- PostgreSQL 16 enabled and running.
- Listens only on `127.0.0.1:5432` and `[::1]:5432`.
- Database: `taskboard`, owner: `taskboard_migrator`.
- Separate roles for migrations and runtime access.
- Local IPv4 authentication uses SCRAM-SHA-256.
- Initial Alembic migration applied successfully.
- Runtime role has schema USAGE, table SELECT/INSERT/UPDATE/DELETE
  and sequence USAGE.
- Both role logins and application CRUD operations tested.

## Environment Files
- Configuration directory: `/etc/taskboard`, `root:taskboard`, mode `0750`.
- `backend.env`: `root:taskboard`, mode `0640`.
- `migration.env`: `root:root`, mode `0600`.
- Migrations run through a transient systemd service.
- Backend uses runtime credentials only.
- Secrets and private keys excluded from Git.

## Backend Service
- Unit: `/etc/systemd/system/taskboard.service`.
- Runs Uvicorn as `taskboard-user:taskboard`.
- Working directory: `/opt/taskboard`.
- Loads `/etc/taskboard/backend.env`.
- Listens on `127.0.0.1:8000`.
- Enabled at boot, starts after PostgreSQL, restarts on failure.
- `/health` returned `ok`; `/ready` confirmed database connectivity.

## Nginx and SELinux
- Site configuration: `/etc/nginx/conf.d/taskboard.conf`.
- Frontend served from `/usr/share/nginx/taskboard`.
- `/api/` proxied to `127.0.0.1:8000`, preserving the request path.
- Frontend API URL uses `window.location.origin`.
- SELinux remains enforcing.
- Persistent `httpd_sys_content_t` context applied to frontend files.
- `httpd_can_network_connect` enabled for nginx-to-backend connections.

## Network Access
- Azure NSG: SSH (22) and HTTPS (443) allowed from my public IPv4 `/32`.
- HTTP (80) allowed from the Internet for ACME validation.
- firewalld allows `ssh`, `dhcpv6-client`, `http` and `https`,
  in runtime and permanent configuration.
- Nginx restricts application and API access to localhost and my IP.
- `/.well-known/acme-challenge/` publicly accessible over HTTP.
- External ACME test-file access verified from another network.
- Backend and database ports remain bound to loopback.

## HTTPS
- Domain: `tarabk-pet.polandcentral.cloudapp.azure.com`.
- Certificate issued through Certbot `certonly --webroot`.
- Webroot: `/usr/share/nginx/taskboard`.
- Certificate files: `fullchain.pem` and `privkey.pem` under
  `/etc/letsencrypt/live/tarabk-pet.polandcentral.cloudapp.azure.com/`.
- Nginx configured for TLS 1.2 and TLS 1.3 on port 443.
- Browser certificate check passed; API available over HTTPS.
- Task persistence verified after page refresh.

## Issues Resolved
- Duplicate nginx default server: moved backup `.conf` outside the include directory.
- External HTTP timeout: corrected the NSG source for port 80.
- Missing HTTPS listener: fixed a missing semicolon and reloaded nginx.

## Certificate Renewal
- HTTP redirects to HTTPS; the ACME path remains accessible over HTTP.
- `snap.certbot.renew.timer` is active with a scheduled next run.
- Deploy hook: `/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh`.
- Hook owned by `root:root`, mode `0750`.
- Hook validates nginx configuration before reloading the service.
- Renewal dry run with deploy hooks completed successfully.

## Database Backups
- Custom-format dumps stored in `/var/backups/taskboard`.
- Backup directory: `postgres:postgres`, mode `0700`; archives: `0600`.
- Script: `/usr/local/sbin/taskboard-backup.sh`, `root:postgres`, mode `0750`.
- `taskboard-backup.service` runs the script as `postgres`.
- `taskboard-backup.timer` schedules daily backups at 03:00 UTC.
- Persistent timer enabled to catch up after a missed run.
- Archives older than seven days removed after a successful backup.
- Manual restore to `taskboard_restore_test` verified.
- One archive copied to local WSL and verified with SHA-256.

## Backend Recovery Test
- Sent SIGKILL to the main Taskboard process.
- systemd restarted the backend automatically.
- Verified a new MainPID and an increased NRestarts counter.
- `/ready` confirmed database connectivity after recovery.
- API access restored without a manual service restart.

## Azure Blob Backups

- Storage account: `tarabkbackup`, resource group: `rg-lab-backups`.
- Poland Central, Standard LRS, Hot tier.
- Private container: `taskboard-backups`.
- Network access restricted to the VM subnet and administrator's public IP.
- Anonymous access and Shared Key authorization disabled.
- VM system-assigned managed identity has Storage Blob Data Contributor access to the backup container.
- AzCopy 10.32.7 runs as `postgres` from the backup service.
- Each run uploads completed local dumps and skips existing blobs.
- Upload failures stop the script before local cleanup.
- Local retention: 7 days. Azure lifecycle deletion: more than 30 days since last modification.
- Blob and container soft delete: 7 days.
- Upload and download verified; SHA-256 checksums matched.
- Updated backup service completed successfully during a manual run.

## Deployment Status

- Application migrated to Docker Compose on the Azure VM.
- PostgreSQL, backend and frontend run in separate containers.
- Host nginx retains HTTPS, certificate renewal and IP restrictions.
- Final database transfer completed after stopping application writes.
- HTTPS access and browser CRUD operations verified.
- Container database backups scheduled daily and uploaded to Azure Blob Storage.
- Downloaded archive verified with SHA-256 and restored into a test database.
- Native Taskboard, PostgreSQL and the old backup timer disabled.
- Previous application files and database retained for recovery.
- Operational procedures: [Azure Docker deployment](AZURE-DOCKER.md).
