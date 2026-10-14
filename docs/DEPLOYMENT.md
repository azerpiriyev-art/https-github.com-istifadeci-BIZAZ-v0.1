# BIZAZ Deployment Documentation

## Current deployment state

- Live production server: **not provisioned**.
- Production DNS/domain and HTTPS endpoint: **not configured**.
- The current local `docker-compose.yml` is for local PostgreSQL development; do not expose its database port on a public server.
- The production-oriented container configuration is being prepared on a feature branch and must pass CI before it is approved for use.

## Target architecture

- Linux VM, Docker Compose, PostgreSQL 16, FastAPI backend, Next.js frontend, and Caddy reverse proxy with automatic HTTPS.
- PostgreSQL is not published to the host and is reachable only on a private Docker network.
- FastAPI uses a dedicated non-superuser database role; the database bootstrap account is not used by the application.
- Credentials are provided by a server-only environment file, never baked into an image or committed to Git.
- Database backups must be encrypted or otherwise access-controlled and stored away from the VM. Restores must be tested before production use.

## Free pilot

See [FREE-TIER-DEPLOYMENT.md](FREE-TIER-DEPLOYMENT.md) for an Oracle Cloud Always Free pilot path and its reliability limitations. A free-tier host is for technical validation and a controlled pilot, not a guarantee of production availability or support.

## Release gates

A production deployment is not complete until:

1. the chosen host and account limits are confirmed;
2. DNS points to the host and inbound firewall rules permit only required ports;
3. production secrets are generated and stored outside Git;
4. the initial schema is applied to a new empty database, with a verified backup/restore plan;
5. HTTPS, authentication, tenant isolation, health checks, logs, backups, and restore are verified;
6. the daily 180-day notification retention task is registered and its last-run result is checked;
7. the release and rollback evidence is recorded.

Do not run the initial schema bootstrap against an existing/non-empty database. Future schema upgrades must apply only reviewed, unapplied migration files after a verified backup.
