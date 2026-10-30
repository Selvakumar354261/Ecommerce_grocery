# Validation report

Prepared with this source package on 16 October 2026. This report distinguishes executed checks from included tests that could not be run.

## Passed

- Strict TypeScript compilation and Vite production frontend build.
- Python compilation for application, migration, and test modules.
- FastAPI import and OpenAPI generation: 38 documented route paths.
- Docker Compose normal configuration validation.
- Docker Compose development override configuration validation.
- Six database-independent pytest checks: password salting/verification; duplicate and malformed cart quantities; sealed/loose variant configuration; exact monetary rounding and geographic distance; untrusted-origin/unauthenticated request handling; core OpenAPI contracts.
- Frozen PostgreSQL schema generated from 20 SQLAlchemy models and a pinned Python dependency lock generated from resolved package versions.

The pytest run reported one dependency deprecation warning from Starlette/AnyIO; it did not fail a test.

## Not verified in this environment

Docker CLI and Compose were available, but the Docker Desktop Linux engine socket was unavailable. Consequently image builds, full Compose startup, Nginx runtime validation, and PostgreSQL integration tests were not executed. A separate scratch PostgreSQL initialization also did not reach readiness. Existing databases were not used or modified.

No browser end-to-end run, physical barcode/receipt-printer test, HTTPS deployment, backup restoration, or load test was performed. The frontend build validates compilation, not browser interaction or production capacity. Run the following on the target computer with a working Docker engine:

```powershell
docker compose up --build -d
docker compose ps -a
docker compose --profile test run --rm tests
```

The integration suite uses the dedicated grocery_test database and covers: central prices, branch isolation/CSRF, nearest full-cart eligibility, POS retry keys, reservation cancellation/expiry, pickup fulfilment, a POS-versus-online oversell race, partial transfer receipt, reserved-stock protection, historical prices and cash returns, purchase receipt, quantity rules, and customer order privacy. These tests are included as executable checks; they are not represented here as passing.

## Acceptance before real trading

Complete the demo workflow in README using separate customer/staff sessions. Check the intended devices and actual branch data. Verify delivery coverage and cash collection processes, restore a database backup into staging, and approve tax/invoice and account recovery requirements. Only then consider a public deployment with HTTPS and real credentials. This package is a source implementation with explicit verification limits, not a claim of production certification.
