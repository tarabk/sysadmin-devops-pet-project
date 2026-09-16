# SysAdmin to DevOps Pet Project

A learning project demonstrating Linux system administration skills
and a gradual transition to automation.

## Goal

Deploy a web application with PostgreSQL on Oracle Linux in Azure,
configure security, backups, and recovery,
then implement containerization and automation.

## Current Status

The application runs locally on Oracle Linux 9.8 in WSL2.

- Python 3.11 with dependencies installed in a virtual environment.
- PostgreSQL 16 with a dedicated application role and database.
- Local database access using SCRAM-SHA-256 authentication.
- Alembic migration 0001 applied successfully.
- Backend running on 127.0.0.1:8000.
- Frontend running on 127.0.0.1:8080 with an English interface.
- Health and database readiness endpoints verified.
- Six automated tests passing.
- Task creation, completion, persistence after page reload,
  and deletion verified manually.

The application has not yet been deployed to Azure.

## Implementation Roadmap

1. Prepare the application and verify that it runs locally.
2. Create and configure an Azure virtual machine.
3. Configure SSH access, user accounts, firewalld, and SELinux.
4. Deploy PostgreSQL, run the backend as a systemd service, and configure Nginx.
5. Configure DNS and HTTPS.
6. Verify logging, backups, recovery, and failure handling.
7. Containerize the application using Docker Compose.
8. Automate server configuration with Ansible.
9. Set up CI/CD with GitHub Actions.
10. Add Prometheus, Grafana, and alerting.
11. Define the cloud infrastructure using Terraform.
