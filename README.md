# CHINNU Commerce

The complete source setup for the agreed grocery web application: a customer storefront plus a Super Admin and Branch/POS workspace, connected to one PostgreSQL inventory system. All application services run through Docker Compose. Payment gateway integration is deliberately deferred.

## Start on Windows

Install Docker Desktop with Linux containers and Docker Compose support. Start Docker Desktop and wait for its engine to become ready. No local Node.js, Python, or PostgreSQL installation is required.

Extract the ZIP, open the `grocery-commerce` folder in VS Code, and run:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Alternatively run `./start.ps1` from PowerShell. On macOS/Linux: `sh start.sh`.

Open **http://localhost:8080**. API documentation is at **http://localhost:8080/api/docs**. The first build downloads base images and dependencies and can take several minutes. `docker compose logs -f backend worker` shows API and reservation activity. The migration container should finish with exit code 0; that is normal.

If 8080 is occupied, change APP_PORT and ALLOWED_ORIGINS in `.env` together. Use the exact origin shown in your browser, without a trailing slash.

## Demo sign-ins

Every demo account uses the password set by DEMO_PASSWORD in `.env` (default: `DemoGrocery!2026`). These are local demonstration accounts, not production credentials.

| Role | Email | Access |
|---|---|---|
| Owner | admin@grove.local | All branches and central administration |
| Manager | manager@grove.local | Central Market branch |
| Cashier | cashier@grove.local | Central Market POS, orders, inventory viewing |
| Inventory | inventory@grove.local | Central Market receiving, transfers, counts |
| Customer | customer@grove.local | Own checkout and orders |

The seed is idempotent and runs only for an empty users table with SEED_DEMO=true. Changing DEMO_PASSWORD after accounts exist does not reset their passwords. Four example branches, eight products, sealed and loose variants, opening stock movements, and a supplier are included. These branches and contact data are illustrative.

## Try the complete workflow

1. Open the storefront, add rice and nuts, and go to the basket.
2. Choose home delivery or shop pickup. For the seed data choose **Use demo location**; enter contact details and a delivery address when needed.
3. Find available branches. The nearest branch that can supply the whole cart is highlighted; choose any eligible branch. Product prices are identical everywhere.
4. Sign in as the demo customer, return to checkout, and place the order. Open **My orders** for progress and the pickup code.
5. In another private browser window, sign in as owner or manager. Open **Workspace -> Online orders**, then confirm, prepare, and mark ready.
6. Delivery: dispatch, record cash collection, then confirm delivered. Pickup: record cash collection, enter the customer's pickup code, and hand over. Stock is deducted at dispatch/handover, once.
7. For walk-in billing open **Cashier shifts**, enter an opening float, and open a shift. Open **Point of sale**, scan/type the seeded SKU (for example RICE-1KG) or use product buttons. Complete a cash sale and print the receipt.
8. Inspect **Inventory -> Movement history**. Try purchasing/receiving and source/destination transfer receipts. Stock counts submitted by inventory staff can be approved by a different manager.
9. Open **Sales & receipts** to reprint or return an entire sale line. Review the dashboard, export a sales CSV, and close the cashier shift with counted cash.

Keep customer and staff sessions in separate browser profiles or private windows. A browser profile has one signed-in account at a time.

## Included features

- Responsive customer catalogue, search and categories, persistent basket, multiple pack/loose variants.
- Customer registration, cookie sessions, personal orders, cancellation policy, order history and pickup verification.
- Checkout-time full-cart branch availability, nearest recommendation, delivery-radius checks, delivery/pickup, central prices, delivery fee, cash/pay-at-shop.
- Owner dashboard, branch configuration, product/variant creation and central price changes, archive, staff creation and account disable/enable.
- Branch-scoped POS, quantity validation, SKU/barcode-keyboard entry, held bill on the current device, receipt reprints and cash returns.
- Cashier shifts and cash variance; stock receiving/damage/adjustments; stock-count submission and separate approval.
- Supplier setup, purchase orders and partial receipts; dispatched transfers and partial destination receipts.
- Transactional stock ledger, reservations, automatic unconfirmed-order expiry, retry keys, permission checks, audit history, dashboard and CSV reporting.
- Docker service health checks, ordered migrations/seed, persistent database volume, development override, isolated test database, backup/restore instructions.

## Services and repository

| Service | Purpose |
|---|---|
| db | PostgreSQL 17 with a named persistent volume |
| migrate | One-shot Alembic schema migration and optional seed |
| backend | FastAPI/Uvicorn application |
| worker | Reservation expiry, using the backend image |
| frontend | Built React/TypeScript/MUI app served by Nginx |
| proxy | Nginx same-origin web/API routing, bound to localhost |
| tests | Optional test-profile runner against grocery_test |

`backend/app` contains models, schemas, authentication, business services, routes, seed, worker, and administrator bootstrap. `backend/migrations` contains the frozen initial SQL and Alembic revision. `frontend/src` contains the customer and staff UI. `infra` holds reverse-proxy routing. `docs` describes architecture, operations, API examples, and actual validation.

## Development through Docker

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
```

React and FastAPI reload when source files change. Keep dependencies installed in images. If you change package/requirements inputs, rebuild the images. Return to normal mode using `docker compose up --build -d --force-recreate`.

## Tests and checks through Docker

```powershell
docker compose --profile test run --rm tests
docker compose run --rm --no-deps backend pytest tests_unit -q
docker compose run --rm --no-deps frontend nginx -t
docker compose config --quiet
```

The backend tests create/use only `grocery_test`; they refuse another database name and reset only that database. Tests cover isolation, retry handling, oversell races, reservations, fulfilment, transfers, purchasing, and returns. `npm run build` with strict TypeScript checking is part of the frontend Docker build. Consult `docs/VALIDATION.md` for which checks were actually executed when this ZIP was produced.

## Stop without losing data

```powershell
docker compose down
```

The database volume remains. Do not add `-v` unless you intentionally want to delete all database data. Containers can be replaced without losing records, but volumes are not backups.

## Fresh installation without demo data

On a fresh database, set SEED_DEMO=false, use a strong unique POSTGRES_PASSWORD, and start the services. Then create the first administrator interactively:

```powershell
docker compose run --rm backend python -m app.bootstrap
```

Sign in, open Workspace -> Branches, create the first branch, add products and staff, and receive opening stock. Disabling seed does not delete demo data already stored in an existing volume. Use a separate Compose project/volume for real data.

## Deployment boundary

This ZIP provides a runnable local application and container setup, not a remotely deployed service. Before public deployment configure HTTPS, Secure cookies, a real business catalogue, branch coverage, secrets, backups, staff procedures, and the required legal/tax rules. The default proxy binds to loopback for local use. See `docs/OPERATIONS.md` for production preparation and recovery commands.

No gateway, mobile app, external geocoder, road routing, driver app, push/SMS/email delivery, offline synchronisation, supplier accounting, automatic sealed-to-loose conversion, or statutory tax engine is included. Those integrations are not silently substituted with mock implementations. The order branch recommendation and all stock transactions use the real backend/database, not browser-only data.
