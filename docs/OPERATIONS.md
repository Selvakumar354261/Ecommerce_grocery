# Setup and operations

## Configuration

Use `.env.example` as the local template. Compose substitutes database credentials into the database connection URL. Use a password containing URL-safe characters, or percent-encode URL-special characters in a separately configured DATABASE_URL if you adapt the setup. Never commit `.env` or database dumps. The application does not require cloud credentials.

| Variable | Meaning |
|---|---|
| COMPOSE_PROJECT_NAME | Isolates service names and volumes; change for a separate installation |
| APP_PORT | Local proxy port, default 8080 |
| POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD | PostgreSQL setup and application connection |
| SEED_DEMO | Enables demo data only if no users exist |
| DEMO_PASSWORD | Initial password used only when demo users are first created |
| COOKIE_SECURE | false on localhost HTTP; true for HTTPS deployment |
| ALLOWED_ORIGINS | Comma-separated exact browser origins for unsafe requests |
| RESERVATION_MINUTES | Expiry window for unconfirmed online orders |

## Startup and migrations

Compose starts db, waits for its health check, executes the one-shot migration/seed container, then starts backend and worker. The frontend waits for backend readiness and the proxy waits for the frontend. Services restart unless stopped; migrations do not loop on failure.

```powershell
docker compose up --build -d
docker compose ps -a
docker compose logs --tail 100 migrate backend worker proxy
```

Do not execute two independent schema migration processes against the same database. On subsequent code releases, rebuild and rerun the migration service before accepting traffic. Add new Alembic revisions for schema changes; do not edit the frozen `migrations/initial.sql` of an existing installation.

```powershell
docker compose stop proxy backend worker
docker compose build
docker compose run --rm migrate
docker compose up -d
```

Back up before releases. Downgrades can remove data; an application image rollback may not be compatible with a new schema. Verify release and restore procedures in staging.

## Backup

Run pg_dump inside the database container and copy the binary archive using Docker. This avoids PowerShell output redirection corrupting binary data.

```powershell
New-Item -ItemType Directory -Force backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/grove-backup.dump'
docker compose cp db:/tmp/grove-backup.dump ./backups/grove-backup.dump
```

Use dated filenames, encrypt copies, store them outside the application host, and restrict access. Automate backup scheduling in your deployment environment. A persistent Docker volume is not a backup. Choose retention and recovery targets with the business.

## Restore

Restore only into the intended database after checking the project name and taking a backup of its current contents. These commands replace database objects with the saved snapshot. Test with a separate staging Compose project first.

```powershell
docker compose stop proxy backend worker
docker compose cp ./backups/grove-backup.dump db:/tmp/grove-backup.dump
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner /tmp/grove-backup.dump'
docker compose up -d backend worker frontend proxy
```

Verify login, catalogue, order history, stock balances, and ledger reconciliation after restoration. Test the process regularly rather than assuming a successfully written dump is recoverable.

## Production preparation

The default local proxy publishes HTTP only to 127.0.0.1. Before exposing the application:

1. Use a new database volume and project name; SEED_DEMO=false. Create a real administrator with the interactive bootstrap command.
2. Configure trusted TLS certificates in the Nginx proxy and serve the site over HTTPS. Set COOKIE_SECURE=true and ALLOWED_ORIGINS to the real origin. A sample TLS server configuration is in `infra/nginx.tls.conf.example`; mount it and the certificate directory in your production Compose configuration. Do not expose private service ports.
3. Replace all demo records, choose real store coordinates and service radii, and define how staff open/pause accepting orders. Review delivery fee and stock rules.
4. Set secrets through deployment environment configuration; control database and Docker access. Keep source/build versions and base images reviewed and updated.
5. Establish backup/restore, host monitoring, reservation/order monitoring, payment collection procedures, and account recovery procedures.
6. Verify the actual scanner, browser, receipt printer, paper width, keyboard workflow, and staff permissions.
7. Review tax/invoice obligations, customer privacy/retention, cancellation/refund procedures, and operational capacity for the business location. This source does not claim compliance certification.

The sample stack is a single-host deployment. High availability, automatic certificate renewal, central log retention, external alert delivery, and point-in-time recovery are deployment tasks that require explicit infrastructure configuration.

## Troubleshooting

- Engine pipe/socket not found: Docker is installed but its engine is not running. Start Docker Desktop in Linux container mode and wait for readiness.
- Port occupied: change APP_PORT and ALLOWED_ORIGINS together, then restart Compose.
- Database login fails after changing password: changing POSTGRES_PASSWORD does not change the password already stored in an existing PostgreSQL volume. Apply a controlled database credential change or use a separate new project for a fresh database.
- 403 origin: match the exact protocol/hostname/port in ALLOWED_ORIGINS. 403 session validation: refresh the session; do not disable CSRF checks.
- No branches match: check location, requested quantity, variant, branch accepting state, and delivery radius. Demo data is in Erode; use the demo location to exercise it.
- A reservation remains after confirmation: confirmed orders no longer auto-expire. Staff must fulfil or explicitly cancel unpaid orders.
- Stock count cannot approve: another manager must approve; reject and recount after on-hand stock movement.
- POS cannot complete: open the cashier's shift at the same branch and ensure available stock and quantity increments are valid.
- Payment gateway: there is none in this release; record only actual cash received, not an assumed online success.

