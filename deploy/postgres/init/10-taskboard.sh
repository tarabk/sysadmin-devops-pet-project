#!/bin/bash
set -euo pipefail

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${TASKBOARD_MIGRATOR_PASSWORD:?Migration password is required}"
: "${TASKBOARD_USER_PASSWORD:?Application password is required}"

psql -X --set=ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname postgres <<'SQL'
\getenv migrator_password TASKBOARD_MIGRATOR_PASSWORD
\getenv runtime_password TASKBOARD_USER_PASSWORD

CREATE ROLE taskboard_migrator
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS
    PASSWORD :'migrator_password';

CREATE ROLE taskboard_user
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS
    PASSWORD :'runtime_password';

CREATE DATABASE taskboard OWNER taskboard_migrator;

\connect taskboard

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE taskboard TO taskboard_user;
GRANT USAGE ON SCHEMA public TO taskboard_user;

ALTER DEFAULT PRIVILEGES
    FOR ROLE taskboard_migrator IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES
    TO taskboard_user;

ALTER DEFAULT PRIVILEGES
    FOR ROLE taskboard_migrator IN SCHEMA public
    GRANT USAGE ON SEQUENCES
    TO taskboard_user;
SQL

echo "Taskboard database and roles initialized"
