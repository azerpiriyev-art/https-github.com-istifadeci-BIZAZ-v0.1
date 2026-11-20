# BIZAZ Production Deployment Runbook

## 1. Status

Production deployment is not yet confirmed. No live production server, domain, production secrets, or verified restore process has been confirmed.

The current production Compose architecture uses PostgreSQL in a container with persistent Docker storage, not a managed database.

## 2. Prerequisites

Before deployment, verify that:

- A supported, patched Linux server is available.
- Docker Engine and Docker Compose v2 are installed.
- A real domain points to the server.
- TCP ports 80 and 443 are allowed through the firewall.
- SSH access is secured.
- Persistent storage and off-server backup storage are available.
- Production credentials are stored securely.

Do not use example domains or placeholder secrets in production.

## 3. Production environment file

On the deployment server, create a private environment file:

    cp deploy/production.env.example .env.production
    chmod 600 .env.production

Set the real domain and HTTPS origin, unique database passwords, and a cryptographically random JWT secret.
Generate random secrets with a trusted tool, for example: openssl rand -hex 32
Never commit .env.production or use example secret values in production.

## 4. Validate the Compose configuration

On the deployment server, run:

    docker compose --env-file .env.production -f compose.production.yml config --quiet

Do not start production services if validation fails. Verify the domain and configuration values first.

## 4.1 Trusted proxy headers and rate limiting

The API rate limiter uses the client IP address, so Uvicorn must trust forwarded headers only from the Caddy reverse proxy. The Compose file assigns Caddy a static address on the configured proxy subnet and sets `FORWARDED_ALLOW_IPS` to that exact address. Do not replace this allowlist with `*`.

Before deployment, confirm that `BIZAZ_PROXY_SUBNET` does not overlap with the host, VPN, or VCN routes and that `BIZAZ_CADDY_IP` is inside that subnet. If either value changes, keep the Compose network, Caddy address, and Uvicorn trust setting consistent.

## 5. Apply database migrations before starting the application

The migration service belongs to the tools profile and is not run by a normal docker compose up command.

Run migrations first:

    docker compose --env-file .env.production -f compose.production.yml --profile tools run --rm migrate

Proceed only if the command exits successfully and reports Migration run completed. If it fails, do not start the application. Preserve logs and investigate the failure.

The migration runner records applied filenames in public.schema_migrations. Repeated runs should skip migrations already recorded as applied.

## 6. Start the application services

Only after migrations succeed, start the regular services:

    docker compose --env-file .env.production -f compose.production.yml up -d --build

Inspect service status:

    docker compose --env-file .env.production -f compose.production.yml ps

Wait for the database, backend, and frontend services to become healthy. The backend container's internal health check calls `/ready`, which executes a database query using the application connection. The public `/health` endpoint is a liveness check only; it does not prove database readiness.

Inspect recent logs when required:

    docker compose --env-file .env.production -f compose.production.yml logs --tail=100 db backend frontend caddy

PostgreSQL, backend, and frontend must not be published directly on host ports. Caddy is the intended public entry point on ports 80 and 443.

## 7. DNS and HTTPS verification

Ensure the real domain points to the server and inbound TCP ports 80 and 443 are reachable before expecting Caddy to obtain a TLS certificate.

Verify public endpoints after deployment:

    curl -fsS https://YOUR_REAL_DOMAIN/health
    curl -fsSI https://YOUR_REAL_DOMAIN/login

Replace YOUR_REAL_DOMAIN with the actual hostname. Investigate Caddy logs if TLS issuance or routing fails.

## 8. Database backups and recovery

A persistent Docker volume is not a backup. Before production migrations, create a database backup and copy it to protected off-server storage.

Example command to create a custom-format dump on the server:

    mkdir -p /var/backups/bizaz
    docker compose --env-file .env.production -f compose.production.yml exec -T db pg_dump -U bizaz_admin -d bizaz -Fc > /var/backups/bizaz/bizaz-backup.dump

Check the command exit code and ensure the dump file is non-empty. Protect backup files because they may contain sensitive business data.

Before declaring production ready, restore a backup into an isolated test database and verify that it is usable. Do not consider an untested dump a verified recovery plan.

Never use docker compose down -v as a routine deployment command; it can remove persistent database data.

## 9. Rollback and schema changes

Application rollback and database rollback are different operations.

Before each release or migration, record the application revision, identify the previous working image, create a verified database backup, and review schema compatibility.

Do not assume that an older application version can safely use a newer database schema. Do not automatically reverse migration changes. Database restoration must be an explicit, reviewed recovery operation.

## 10. Production readiness checklist

Do not approve production until all applicable checks have been completed:

- Real server, domain, DNS, firewall, and HTTPS have been verified.
- Production secrets are unique, private, and excluded from Git.
- Database ports are not publicly published.
- Database migrations complete successfully before the application starts.
- Backend, frontend, Caddy routing, and health checks work in the target environment.
- A database backup is stored off-server and has been restored successfully in an isolated test environment.
- Logs, failure detection, and recovery procedures are documented and tested.

Passing local image builds and Compose configuration checks alone does not establish production readiness.
## 11. ARM64 pilot and notification retention

For the controlled Oracle Cloud ARM64 pilot, use [FREE-TIER-DEPLOYMENT.md](FREE-TIER-DEPLOYMENT.md). Its commands must follow this runbook's canonical `compose.production.yml` configuration and `deploy/production.env.example`.

The 180-day notification purge task is not configured automatically by Compose. After deployment and successful backup/restore verification, follow [BASIC-NOTIFICATIONS-OPERATIONS.md](BASIC-NOTIFICATIONS-OPERATIONS.md), update the scheduled command to the deployed path, and verify its exit code, logs, and deleted-row count.

Do not claim production readiness until the host, TLS, backups, restore, monitoring, and scheduled task are verified.
